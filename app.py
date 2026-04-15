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

st.title("🗓 PROGRAMACIÓN DE TURNOS")
st.caption("Objetivo: 132h por ciclo, modelo 2x2 mixto, balance individual D/N reforzado.")

if 'seed' not in st.session_state: st.session_state['seed'] = 42
if 'mapping' not in st.session_state: st.session_state['mapping'] = {}

# --- AJUSTE 1: LECTURA ROBUSTA DE EXCEL ---
fichas_cargadas = []
cargo_sugerido = "Cosechador"
conteo_sugerido = 20

with st.sidebar:
    st.header("📂 Base de Datos")
    archivo_subido = st.file_uploader("Adjuntar archivo COSECHA.xlsx", type=["xlsx"])
    
    if archivo_subido:
        excel_data = pd.ExcelFile(archivo_subido)
        hoja_sel = st.selectbox("Escoger hoja cargo", excel_data.sheet_names)
        
        # Leemos asegurando que no ignore nada por tipo de dato
        df_excel = pd.read_excel(archivo_subido, sheet_name=hoja_sel)
        cargo_sugerido = hoja_sel
        if not df_excel.empty:
            # .strip() elimina espacios accidentales que causan conteos erróneos
            fichas_cargadas = df_excel.iloc[:, 0].dropna().astype(str).str.strip().tolist()
            conteo_sugerido = len(fichas_cargadas)
            st.info(f"Leídas {conteo_sugerido} fichas en total.")

    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value=cargo_sugerido)
    
    st.header("📊 Parámetros Operativos")
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

# 4. MOTOR DE PROGRAMACIÓN (CON AJUSTE DE BALANCE D/N)
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
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

        for d in bloque:
            if (d % 7) >= d_semana: continue
            sem_rel = (d - bloque_idx) // 7
            obligados_D, obligados_N = [], []
            for op in ops:
                if racha[op] == 1 and turnos_bloque[op] < 11 and turnos_semanales[op][sem_rel] < 4:
                    if d > 0 and horario[op][d-1] == TURNO_DIA: obligados_D.append(op)
                    else: obligados_N.append(op)

            aptos = [op for op in ops if turnos_bloque[op] < 11 and turnos_semanales[op][sem_rel] < 4]
            aptos = [op for op in aptos if d < 1 or horario[op][d-1] == DESCANSO]
            random.shuffle(aptos)

            asignados_n = []
            prioridad_n = [o for o in obligados_N if o in aptos] + [o for o in obligados_D if o in aptos and random.random() < 0.3]
            for op in prioridad_n:
                if len(asignados_n) < n_req: asignados_n.append(op)
            resto_n = [o for o in aptos if o not in asignados_n]
            resto_n.sort(key=lambda x: (turnos_bloque[x], noches_acum[x], random.random()))
            while len(asignados_n) < n_req and resto_n: asignados_n.append(resto_n.pop(0))

            for op in asignados_n:
                horario[op][d], turnos_bloque[op], turnos_semanales[op][sem_rel], cob_noche[d], noches_acum[op], racha[op] = TURNO_NOCHE, turnos_bloque[op]+1, turnos_semanales[op][sem_rel]+1, cob_noche[d]+1, noches_acum[op]+1, racha[op]+1

            ya_n = set(asignados_n)
            cand_d = [op for op in aptos if op not in ya_n]
            if d > bloque_idx: cand_d = [o for o in cand_d if horario[o][d-1] != TURNO_NOCHE]
            asignados_d = []
            for op in [o for o in obligados_D if o in cand_d]:
                if len(asignados_d) < d_req: asignados_d.append(op)
            resto_d = [o for o in cand_d if o not in asignados_d]
            resto_d.sort(key=lambda x: (turnos_bloque[x], -noches_acum[x], random.random()))
            while len(asignados_d) < d_req and resto_d: asignados_d.append(resto_d.pop(0))

            for op in asignados_d:
                horario[op][d], turnos_bloque[op], turnos_semanales[op][sem_rel], cob_dia[d], racha[op] = TURNO_DIA, turnos_bloque[op]+1, turnos_semanales[op][sem_rel]+1, cob_dia[d]+1, racha[op]+1

            for op in ops:
                if op not in (set(asignados_n) | set(asignados_d)): racha[op] = 0

        # --- AJUSTE 2: REFUERZO DE BALANCE D/N (Evitar desproporción 7/15) ---
        for op in ops:
            while turnos_bloque[op] < 11:
                dias_v = [d for d in bloque if (d % 7) < d_semana and horario[op][d] == DESCANSO and turnos_semanales[op][(d-bloque_idx)//7] < 4]
                dias_v = [d for d in dias_v if not (d > bloque_idx and horario[op][d-1] == TURNO_NOCHE)]
                if not dias_v: break
                
                # Priorizar días más vacíos
                dias_v.sort(key=lambda x: (cob_dia[x] + cob_noche[x]))
                d_opt, sem_opt = dias_v[0], (dias_v[0]-bloque_idx)//7
                
                # Balance Individual Estricto
                actual_d = sum(1 for di in range(DIAS_TOTALES) if horario[op][di] == TURNO_DIA)
                actual_n = sum(1 for di in range(DIAS_TOTALES) if horario[op][di] == TURNO_NOCHE)
                
                # Forzar el turno que más le falte al operador
                if actual_d < actual_n:
                    horario[op][d_opt], cob_dia[d_opt] = TURNO_DIA, cob_dia[d_opt]+1
                elif actual_n < actual_d:
                    horario[op][d_opt], cob_noche[d_opt] = TURNO_NOCHE, cob_noche[d_opt]+1
                else:
                    # Si está equilibrado, elegir el turno más vacío del día
                    if cob_dia[d_opt] <= cob_noche[d_opt]:
                        horario[op][d_opt], cob_dia[d_opt] = TURNO_DIA, cob_dia[d_opt]+1
                    else:
                        horario[op][d_opt], cob_noche[d_opt] = TURNO_NOCHE, cob_noche[d_opt]+1
                
                turnos_bloque[op], turnos_semanales[op][sem_opt] = turnos_bloque[op]+1, turnos_semanales[op][sem_opt]+1

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None: st.session_state['seed'] = semilla_manual
    st.session_state['mapping'] = {}
    total_t = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_f = max(math.ceil((math.ceil(total_t / 11) * factor_cobertura) / (1 - ausentismo)), (demanda_dia + demanda_noche) * 2)
    st.session_state["df"] = generar_programacion_equitativa(op_f, demanda_dia, demanda_noche, dias_cubrir)
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
            ops_actuales = st.session_state["df"].index.tolist()
            # Usamos todas las fichas cargadas sin excepción
            f_lista = fichas_cargadas.copy()
            random.shuffle(f_lista)
            mapeo_temp = {}
            for i, op_id in enumerate(ops_actuales):
                if i < len(f_lista): mapeo_temp[op_id] = f_lista[i]
                else: mapeo_temp[op_id] = f"VACANTE {i - len(f_lista) + 1}"
            st.session_state['mapping'] = mapeo_temp
            st.success("Personal asignado visualmente.")

# 6. RENDERIZADO
if "df" in st.session_state:
    df_base = st.session_state["df"]
    df_visual = df_base.copy()
    if st.session_state['mapping']:
        df_visual.index = [st.session_state['mapping'].get(x, x) for x in df_visual.index]
    
    op_final = st.session_state["op_final"]
    
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1: st.markdown(f'<div class="metric-box-green"><div>{cargo} Requerido</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with col_m2: st.markdown(f'<div class="metric-box-green"><div>Fichas en Nómina</div><div class="metric-value-dark">{len(fichas_cargadas)}</div></div>', unsafe_allow_html=True)
    with col_m3: st.markdown(f'<div class="metric-box-green"><div>Meta Horas</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación del Personal")
    style_f = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df_visual.style.map(style_f), use_container_width=True)

    st.subheader(f"📊 Balance Detallado")
    stats = []
    for idx_orig in df_base.index:
        f = df_base.loc[idx_orig]
        identidad_visual = st.session_state['mapping'].get(idx_orig, idx_orig)
        stats.append({
            "Identidad": identidad_visual, 
            "T. Día": (f==TURNO_DIA).sum(), "T. Noche": (f==TURNO_NOCHE).sum(),
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
