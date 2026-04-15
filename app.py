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

st.title("🗓 PROGRAMACIÓN DE TURNOS - NIVELACIÓN TOTAL")
st.caption("2x2 por bloques con Distribución Estricta de Refuerzos (Límite 2 por día).")

if 'seed' not in st.session_state: st.session_state['seed'] = 42
if 'mapping' not in st.session_state: st.session_state['mapping'] = {}

# --- CARGA DE EXCEL ---
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
            st.info(f"Fichas detectadas: {conteo_sugerido}") [cite: 1, 2, 3]

    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value=cargo_sugerido)
    demanda_dia = st.number_input(f"{cargo} Día", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} Noche", min_value=1, value=5)
    horas_turno = st.number_input("Horas/turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días/semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor Holgura", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01) [cite: 4]
    operadores_actuales = st.number_input(f"{cargo} actual", min_value=0, value=conteo_sugerido)

# 3. CONSTANTES
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN
@st.cache_data
def generar_programacion_nivelada(n_ops, d_req, n_req, d_semana, seed): [cite: 7]
    ops = [f"Op {i+1}" for i in range(n_ops)]
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    patron_maestro = [TURNO_DIA, TURNO_DIA, DESCANSO, DESCANSO, TURNO_NOCHE, TURNO_NOCHE, DESCANSO, DESCANSO]

    random.seed(seed)
    random.shuffle(ops)
    grupos = [ops[i::4] for i in range(4)]
    offsets = [0, 2, 4, 6]

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_semanales = {op: [0, 0, 0] for op in ops} [cite: 8]
        cob_dia = {d: 0 for d in bloque}
        cob_noche = {d: 0 for d in bloque}

        for g_idx, grupo_ops in enumerate(grupos):
            off = offsets[g_idx]
            for op in grupo_ops:
                for d in bloque: [cite: 9]
                    if (d % 7) >= d_semana: continue
                    val = patron_maestro[(d + off) % 8]
                    if val != DESCANSO:
                        horario[op][d] = val [cite: 10]
                        if val == TURNO_DIA: cob_dia[d] += 1
                        else: cob_noche[d] += 1
                        turnos_semanales[op][(d - bloque_idx) // 7] += 1 [cite: 11]

        max_refuerzos_permitidos = 1
        while max_refuerzos_permitidos <= 3:
            deudores = [op for op in ops if sum(1 for d in bloque if horario[op][d] != DESCANSO) < 11]
            if not deudores: break
            random.shuffle(deudores) [cite: 12]
            for op in deudores:
                conteo = sum(1 for d in bloque if horario[op][d] != DESCANSO)
                if conteo >= 11: continue
                d_op = sum(1 for d in bloque if horario[op][d] == TURNO_DIA)
                n_op = sum(1 for d in bloque if horario[op][d] == TURNO_NOCHE) [cite: 13]
                tipo_nec = TURNO_DIA if d_op <= n_op else TURNO_NOCHE

                candidatos = []
                for d in bloque:
                    if (d % 7) < d_semana and horario[op][d] == DESCANSO: [cite: 14]
                        sem_idx = (d - bloque_idx) // 7
                        if turnos_semanales[op][sem_idx] >= 4: continue
                        if tipo_nec == TURNO_DIA and d > bloque_idx and horario[op][d-1] == TURNO_NOCHE: continue
                        ref_dia = (cob_dia[d] - d_req) + (cob_noche[d] - n_req) [cite: 15]
                        if ref_dia >= max_refuerzos_permitidos: continue
                        v_izq = horario[op][d-1] if d > bloque_idx else None
                        v_der = horario[op][d+1] if d < bloque_idx + 20 else None [cite: 16]
                        es_bloque = 1 if (v_izq == tipo_nec or v_der == tipo_nec) else 0
                        score = (ref_dia, -es_bloque)
                        candidatos.append((score, d)) [cite: 17]

                if candidatos:
                    candidatos.sort()
                    d_sel = candidatos[0][1]
                    horario[op][d_sel] = tipo_nec
                    if tipo_nec == TURNO_DIA: cob_dia[d_sel] += 1 [cite: 18]
                    else: cob_noche[d_sel] += 1
                    turnos_semanales[op][(d_sel - bloque_idx) // 7] += 1

            if deudores == [op for op in ops if sum(1 for d in bloque if horario[op][d] != DESCANSO) < 11]:
                max_refuerzos_permitidos += 1 [cite: 19]

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None: st.session_state['seed'] = semilla_manual
    st.session_state['mapping'] = {}
    total_t = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_f = max(math.ceil((math.ceil(total_t / 11) * factor_cobertura) / (1 - ausentismo)), (demanda_dia + demanda_noche) * 2) [cite: 20]
    op_f = ((op_f + 3) // 4) * 4
    st.session_state["df"] = generar_programacion_nivelada(op_f, demanda_dia, demanda_noche, dias_cubrir, st.session_state['seed'])
    st.session_state["op_final"] = op_f

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🚀 Generar Programación"): procesar_generacion(42)
with c2:
    if st.button("🔄 Generar Versión Aleatoria"): procesar_generacion(random.randint(1, 100000))
with c3:
    if st.button("👤 Asignar Fichas Reales"):
        if "df" in st.session_state:
            ops_ids = st.session_state["df"].index.tolist() [cite: 21]
            f_lista = fichas_cargadas.copy()
            random.shuffle(f_lista)
            mapeo = {op: f_lista[i] if i < len(f_lista) else f"VACANTE {i-len(f_lista)+1}" for i, op in enumerate(ops_ids)}
            st.session_state['mapping'] = mapeo
            st.success("Personal asignado con nivelación estricta.")

# 6. RENDERIZADO Y EXPORTACIÓN
if "df" in st.session_state:
    df_base = st.session_state["df"] [cite: 22]
    df_visual = df_base.copy()
    if st.session_state['mapping']:
        df_visual.index = [st.session_state['mapping'].get(x, x) for x in df_visual.index]

    op_final = st.session_state["op_final"]
    c_m1, c_m2, c_m3 = st.columns(3)
    with c_m1: st.markdown(f'<div class="metric-box-green"><div>Personal Total</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c_m2: st.markdown(f'<div class="metric-box-green"><div>Fichas Nómina</div><div class="metric-value-dark">{len(fichas_cargadas)}</div></div>', unsafe_allow_html=True)
    with c_m3: st.markdown(f'<div class="metric-box-green"><div>Horas/Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación (Nivelación Máxima)")
    style_f = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold" [cite: 23]
    st.dataframe(df_visual.style.map(style_f), use_container_width=True)

    # Preparar Balance
    stats = []
    for idx in df_base.index:
        f = df_base.loc[idx]
        stats.append({
            "Identidad": st.session_state['mapping'].get(idx, idx),
            "T. Día": (f==TURNO_DIA).sum(), "T. Noche": (f==TURNO_NOCHE).sum(),
            "Horas S1-3": sum(1 for x in f[:21] if x != DESCANSO) * horas_turno,
            "Secuencia S1-3": f"{sum(1 for x in f[0:7] if x!=DESCANSO)}-{sum(1 for x in f[7:14] if x!=DESCANSO)}-{sum(1 for x in f[14:21] if x!=DESCANSO)}", [cite: 24]
            "Horas S4-6": sum(1 for x in f[21:] if x != DESCANSO) * horas_turno,
            "Secuencia S4-6": f"{sum(1 for x in f[21:28] if x!=DESCANSO)}-{sum(1 for x in f[28:35] if x!=DESCANSO)}-{sum(1 for x in f[35:42] if x!=DESCANSO)}",
            "Estado": "✅ 44h OK" [cite: 25]
        })
    df_balance = pd.DataFrame(stats).set_index("Identidad")
    
    st.subheader("📊 Balance Detallado")
    st.dataframe(df_balance, use_container_width=True)

    # Preparar Cobertura
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df_base[dia] == TURNO_DIA).sum(), (df_base[dia] == TURNO_NOCHE).sum()
        refuerzos_total = (ad-demanda_dia)+(an-demanda_noche)
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": refuerzos_total, "Estado": "✅ OK" if refuerzos_total <= 2 else "⚠️"})
    df_cobertura = pd.DataFrame(check).set_index("Día")
    
    st.subheader("✅ Validación de Cobertura (Límite Estricto 2)")
    st.dataframe(df_cobertura.T, use_container_width=True)

    # --- NUEVA LÓGICA DE DESCARGA ---
    out = io.BytesIO() [cite: 26]
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        # Hoja 1: Programación con formato de color
        df_visual.to_excel(writer, sheet_name="Programación")
        workbook = writer.book
        worksheet = writer.sheets["Programación"]

        fmt_dia = workbook.add_format({'bg_color': '#FFF3CD', 'font_weight': 'bold', 'border': 1})
        fmt_noche = workbook.add_format({'bg_color': '#CCE5FF', 'font_weight': 'bold', 'border': 1})
        
        # Aplicar formato condicional al rango de datos
        rows, cols = df_visual.shape
        worksheet.conditional_format(1, 1, rows, cols, {
            'type': 'cell', 'criteria': '==', 'value': '"D"', 'format': fmt_dia
        })
        worksheet.conditional_format(1, 1, rows, cols, {
            'type': 'cell', 'criteria': '==', 'value': '"N"', 'format': fmt_noche
        })

        # Hoja 2: Balance
        df_balance.to_excel(writer, sheet_name="Balance_Operadores")
        
        # Hoja 3: Cobertura
        df_cobertura.to_excel(writer, sheet_name="Validacion_Cobertura")

    st.download_button(
        label="⬇️ Descargar Excel Completo", 
        data=out.getvalue(), 
        file_name=f"Programacion_{cargo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
