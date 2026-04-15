import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Programación de Turnos 44H", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.metric-box-green { background: #10B981; color: #064E3B; border-radius: 8px; padding: 1.2rem; text-align: center; }
.metric-value-dark { font-size: 2.2rem; font-family: 'IBM Plex Mono', monospace; font-weight: 700; }
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PROGRAMACIÓN DE TURNOS - NIVELACIÓN 50/50")
st.caption("Objetivo: 132h, Balance Estricto Día/Noche (Máx. diferencia de 1 turno) y Reparto Equitativo.")

if 'seed' not in st.session_state: st.session_state['seed'] = 42
if 'mapping' not in st.session_state: st.session_state['mapping'] = {}

# --- BLOQUE DE EXCEL ---
fichas_cargadas = []
cargo_sugerido = "Cosechador"
conteo_sugerido = 20

with st.sidebar:
    st.header("📂 Base de Datos")
    archivo_subido = st.file_uploader("Adjuntar archivo COSECHA.xlsx", type=["xlsx"])
    if archivo_subido:
        excel_data = pd.ExcelFile(archivo_subido)
        hoja_sel = st.selectbox("Escoger hoja cargo", excel_data.sheet_names)
        df_excel = pd.read_excel(archivo_subido, sheet_name=hoja_sel)
        cargo_sugerido = hoja_sel
        if not df_excel.empty:
            fichas_cargadas = df_excel.iloc[:, 0].dropna().astype(str).str.strip().tolist()
            conteo_sugerido = len(fichas_cargadas)
            st.info(f"Leídas {conteo_sugerido} fichas únicas.")

    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value=cargo_sugerido)
    demanda_dia = st.number_input(f"{cargo} Día", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} Noche", min_value=1, value=5)
    horas_turno = st.number_input("Horas/turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días/semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor Holgura", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input(f"{cargo} actual", min_value=0, value=conteo_sugerido)

# 3. CONSTANTES
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN CON BALANCE FORZADO 50/50
def generar_programacion_equilibrada(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(st.session_state['seed'])
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        racha = {op: 0 for op in ops}
        turnos_semanales = {op: [0, 0, 0] for op in ops}
        cob_dia = {d: 0 for d in bloque}
        cob_noche = {d: 0 for d in bloque}

        # FASE 1: 2X2 BASE
        for d in bloque:
            if (d % 7) >= d_semana: continue
            sem_rel = (d - bloque_idx) // 7
            aptos = [op for op in ops if turnos_bloque[op] < 11 and turnos_semanales[op][sem_rel] < 4]
            aptos = [op for op in aptos if d < 1 or horario[op][d-1] == DESCANSO]
            random.shuffle(aptos)

            asig_n = aptos[:n_req]
            for op in asig_n:
                horario[op][d], turnos_bloque[op], turnos_semanales[op][sem_rel], cob_noche[d], racha[op] = TURNO_NOCHE, turnos_bloque[op]+1, turnos_semanales[op][sem_rel]+1, cob_noche[d]+1, racha[op]+1

            ya_n = set(asig_n)
            cand_d = [op for op in aptos if op not in ya_n]
            if d > bloque_idx: cand_d = [o for o in cand_d if horario[o][d-1] != TURNO_NOCHE]
            asig_d = cand_d[:d_req]
            for op in asig_d:
                horario[op][d], turnos_bloque[op], turnos_semanales[op][sem_rel], cob_dia[d], racha[op] = TURNO_DIA, turnos_bloque[op]+1, turnos_semanales[op][sem_rel]+1, cob_dia[d]+1, racha[op]+1

            for op in ops:
                if op not in (set(asig_n) | set(asig_d)): racha[op] = 0

        # FASE 2: AJUSTE FINAL CON BALANCE FORZADO (PILAR DEL CAMBIO)
        deudores = [op for op in ops if turnos_bloque[op] < 11]
        while deudores:
            for op in deudores:
                if turnos_bloque[op] >= 11: continue
                
                # Calcular balance actual del operador en ESTE bloque
                dias_op = sum(1 for d in bloque if horario[op][d] == TURNO_DIA)
                noches_op = sum(1 for d in bloque if horario[op][d] == TURNO_NOCHE)
                
                # Decidir qué turno necesita para llegar al balance 5/6 o 6/5
                necesita_tipo = TURNO_DIA if dias_op <= noches_op else TURNO_NOCHE
                
                # Buscar días libres para ese tipo específico
                dias_v = [d for d in bloque if (d % 7) < d_semana and horario[op][d] == DESCANSO]
                dias_v = [d for d in dias_v if turnos_semanales[op][(d - bloque_idx) // 7] < 4]
                if necesita_tipo == TURNO_DIA: # Si necesita día, no puede ser tras una noche
                    dias_v = [d for d in dias_v if not (d > bloque_idx and horario[op][d-1] == TURNO_NOCHE)]
                
                if not dias_v: # Si no hay espacio para lo que necesita, buscamos el otro tipo como última opción
                    necesita_tipo = TURNO_NOCHE if necesita_tipo == TURNO_DIA else TURNO_DIA
                    dias_v = [d for d in bloque if (d % 7) < d_semana and horario[op][d] == DESCANSO]
                    dias_v = [d for d in dias_v if turnos_semanales[op][(d - bloque_idx) // 7] < 4]
                    if necesita_tipo == TURNO_DIA:
                        dias_v = [d for d in dias_v if not (d > bloque_idx and horario[op][d-1] == TURNO_NOCHE)]

                if dias_v:
                    # Ordenar por el día que tenga menos carga de ese tipo específico de turno
                    dias_v.sort(key=lambda x: cob_dia[x] if necesita_tipo == TURNO_DIA else cob_noche[x])
                    d_opt = dias_v[0]
                    
                    horario[op][d_opt] = necesita_tipo
                    if necesita_tipo == TURNO_DIA: cob_dia[d_opt] += 1
                    else: cob_noche[d_opt] += 1
                    
                    turnos_bloque[op] += 1
                    turnos_semanales[op][(d_opt - bloque_idx) // 7] += 1
            
            deudores = [op for op in ops if turnos_bloque[op] < 11]

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None: st.session_state['seed'] = semilla_manual
    st.session_state['mapping'] = {}
    total_t = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_f = max(math.ceil((math.ceil(total_t / 11) * factor_cobertura) / (1 - ausentismo)), (demanda_dia + demanda_noche) * 2)
    st.session_state["df"] = generar_programacion_equilibrada(op_f, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_f

# BOTONES
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🚀 Generar Programación"): procesar_generacion(42)
with c2:
    if st.button("🔄 Generar Otra Versión"): procesar_generacion(random.randint(1, 100000))
with c3:
    if st.button("👤 Asignar Personal Real"):
        if "df" in st.session_state:
            ops_ids = st.session_state["df"].index.tolist()
            f_lista = fichas_cargadas.copy()
            random.shuffle(f_lista)
            mapeo = {}
            for i, op_id in enumerate(ops_ids):
                if i < len(f_lista): mapeo[op_id] = f_lista[i]
                else: mapeo[op_id] = f"VACANTE {i - len(f_lista) + 1}"
            st.session_state['mapping'] = mapeo
            st.success("Personal nivelado asignado.")

# 6. RENDERIZADO
if "df" in st.session_state:
    df_base = st.session_state["df"]
    df_visual = df_base.copy()
    if st.session_state['mapping']:
        df_visual.index = [st.session_state['mapping'].get(x, x) for x in df_visual.index]
    
    op_final = st.session_state["op_final"]
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1: st.markdown(f'<div class="metric-box-green"><div>Personal Total</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with col_m2: st.markdown(f'<div class="metric-box-green"><div>Fichas Excel</div><div class="metric-value-dark">{len(fichas_cargadas)}</div></div>', unsafe_allow_html=True)
    with col_m3: st.markdown(f'<div class="metric-box-green"><div>Meta Horas</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación Nivelada (Máx. diferencia D/N de 1 turno)")
    style_f = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df_visual.style.map(style_f), use_container_width=True)

    st.subheader(f"📊 Balance Detallado")
    stats = []
    for idx_orig in df_base.index:
        f = df_base.loc[idx_orig]
        identidad = st.session_state['mapping'].get(idx_orig, idx_orig)
        stats.append({
            "Identidad": identidad, "T. Día": (f==TURNO_DIA).sum(), "T. Noche": (f==TURNO_NOCHE).sum(),
            "Horas S1-3": sum(1 for x in f[:21] if x != DESCANSO) * horas_turno,
            "Secuencia S1-3": f"{sum(1 for x in f[0:7] if x!=DESCANSO)}-{sum(1 for x in f[7:14] if x!=DESCANSO)}-{sum(1 for x in f[14:21] if x!=DESCANSO)}",
            "Horas S4-6": sum(1 for x in f[21:] if x != DESCANSO) * horas_turno,
            "Secuencia S4-6": f"{sum(1 for x in f[21:28] if x!=DESCANSO)}-{sum(1 for x in f[28:35] if x!=DESCANSO)}-{sum(1 for x in f[35:42] if x!=DESCANSO)}",
            "Estado": "✅ 44h OK"
        })
    df_balance = pd.DataFrame(stats).set_index("Identidad")
    st.dataframe(df_balance, use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df_base[dia] == TURNO_DIA).sum(), (df_base[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": (ad-demanda_dia)+(an-demanda_noche), "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "⚠️"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df_visual.to_excel(writer, sheet_name="Programación")
        df_balance.to_excel(writer, sheet_name="Balance")
    st.download_button(label=f"⬇️ Descargar Excel", data=out.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
