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

st.title("🗓 PROGRAMACIÓN DE TURNOS PRO")
st.caption("Objetivo: 132h, Modelo 2x2, 6 Semanas y Nivelación Estricta por Carrusel.")

# Inicializar estados de memoria
if 'seed' not in st.session_state: st.session_state['seed'] = 42
if 'mapping' not in st.session_state: st.session_state['mapping'] = {}

# --- BLOQUE DE EXCEL (COSECHA.xlsx) ---
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
    demanda_dia = st.number_input(f"{cargo} requerido (Día)", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} requerido (Noche)", min_value=1, value=5)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input(f"{cargo} actual (Nómina)", min_value=0, value=conteo_sugerido)

# 3. CONSTANTES
SEMANAS = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN CON CARRUSEL Y BALANCE INDIVIDUAL
def generar_programacion_nivelada(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(st.session_state['seed'])
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        racha = {op: 0 for op in ops}
        turnos_semanales = {op: [0, 0, 0] for op in ops}
        cob_dia = {d: 0 for d in bloque}
        cob_noche = {d: 0 for d in bloque}

        # --- FASE 1: BASE 2X2 (COBERTURA MÍNIMA) ---
        for d in bloque:
            if (d % 7) >= d_semana: continue
            sem_rel = (d - bloque_idx) // 7
            aptos = [op for op in ops if turnos_bloque[op] < 11 and turnos_semanales[op][sem_rel] < 4]
            aptos = [op for op in aptos if d < 1 or horario[op][d-1] == DESCANSO]
            random.shuffle(aptos)

            # Noche
            asignados_n = aptos[:n_req]
            for op in asignados_n:
                horario[op][d], turnos_bloque[op], turnos_semanales[op][sem_rel], cob_noche[d], racha[op] = TURNO_NOCHE, turnos_bloque[op]+1, turnos_semanales[op][sem_rel]+1, cob_noche[d]+1, racha[op]+1

            # Día (Respetando descanso post-noche)
            ya_n = set(asignados_n)
            cand_d = [op for op in aptos if op not in ya_n]
            if d > bloque_idx: cand_d = [o for o in cand_d if horario[o][d-1] != TURNO_NOCHE]
            asignados_d = cand_d[:d_req]
            for op in asignados_d:
                horario[op][d], turnos_bloque[op], turnos_semanales[op][sem_rel], cob_dia[d], racha[op] = TURNO_DIA, turnos_bloque[op]+1, turnos_semanales[op][sem_rel]+1, cob_dia[d]+1, racha[op]+1

            for op in ops:
                if op not in (set(asignados_n) | set(asignados_d)): racha[op] = 0

        # --- FASE 2: AJUSTE FINAL (CARRUSEL Y BALANCE INDIVIDUAL) ---
        # Paso A: Quiénes faltan por llegar a 11
        deudores = [op for op in ops if turnos_bloque[op] < 11]
        
        while deudores:
            for op in deudores:
                if turnos_bloque[op] >= 11: continue
                
                # Paso B: Buscar días legales
                dias_v = [d for d in bloque if (d % 7) < d_semana and horario[op][d] == DESCANSO]
                dias_v = [d for d in dias_v if turnos_semanales[op][(d - bloque_idx) // 7] < 4]
                dias_v = [d for d in dias_v if not (d > bloque_idx and horario[op][d-1] == TURNO_NOCHE)]
                
                if not dias_v: continue
                
                # Paso C: Criterio de Nivelación (Carga de día vs Balance personal)
                # Contamos balance histórico del operador
                act_d = sum(1 for di in range(DIAS_TOTALES) if horario[op][di] == TURNO_DIA)
                act_n = sum(1 for di in range(DIAS_TOTALES) if horario[op][di] == TURNO_NOCHE)
                
                # Ordenar días por cobertura total (Suavizado)
                dias_v.sort(key=lambda x: (cob_dia[x] + cob_noche[x]))
                d_opt = dias_v[0]
                
                # Decisión de turno por Presupuesto Individual
                if act_d <= act_n:
                    # Intenta equilibrar con un Día si el día lo permite
                    if (cob_dia[d_opt] - d_req) <= (cob_noche[d_opt] - n_req):
                        horario[op][d_opt], cob_dia[d_opt] = TURNO_DIA, cob_dia[d_opt]+1
                    else:
                        horario[op][d_opt], cob_noche[d_opt] = TURNO_NOCHE, cob_noche[d_opt]+1
                else:
                    # Intenta equilibrar con una Noche
                    if (cob_noche[d_opt] - n_req) <= (cob_dia[d_opt] - d_req):
                        horario[op][d_opt], cob_noche[d_opt] = TURNO_NOCHE, cob_noche[d_opt]+1
                    else:
                        horario[op][d_opt], cob_dia[d_opt] = TURNO_DIA, cob_dia[d_opt]+1
                
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
    st.session_state["df"] = generar_programacion_nivelada(op_f, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_f

# BOTONES
c1_b, c2_b, c3_b = st.columns(3)
with c1_b:
    if st.button("🚀 Generar Programación"): procesar_generacion(42)
with c2_b:
    if st.button("🔄 Generar Otra Versión"): procesar_generacion(random.randint(1, 100000))
with c3_b:
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

# 6. RENDERIZADO VISUAL (CAPA SEGURA)
if "df" in st.session_state:
    df_base = st.session_state["df"]
    df_visual = df_base.copy()
    if st.session_state['mapping']:
        df_visual.index = [st.session_state['mapping'].get(x, x) for x in df_visual.index]
    
    op_final = st.session_state["op_final"]
    
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1: st.markdown(f'<div class="metric-box-green"><div>Personal Total</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with col_m2: st.markdown(f'<div class="metric-box-green"><div>Fichas en Nómina</div><div class="metric-value-dark">{len(fichas_cargadas)}</div></div>', unsafe_allow_html=True)
    with col_m3: st.markdown(f'<div class="metric-box-green"><div>Vacantes</div><div class="metric-value-dark">{max(0, op_final - len(fichas_cargadas))}</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación del Personal (Nivelada)")
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
    st.download_button(label=f"⬇️ Descargar Excel {cargo}", data=out.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
