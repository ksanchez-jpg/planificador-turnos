import streamlit as st
import math
import pandas as pd
import io
import random
from openpyxl.styles import PatternFill

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Programación de Turnos 44H", layout="wide") [cite: 1]

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.metric-box-green { background: #10B981; color: #064E3B; border-radius: 8px; padding: 1.2rem; text-align: center; }
.metric-value-dark { font-size: 2.2rem; font-family: 'IBM Plex Mono', monospace; font-weight: 700; }
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; width: 100%; }
</style>
""", unsafe_allow_html=True) [cite: 1]

st.title("🗓 PROGRAMACIÓN DE TURNOS - SISTEMA INTEGRAL")
st.caption("2x2 por bloques, 132h, Balance D/N y Límite Estricto de 2 Refuerzos.")

# --- CONSTANTES ---
DIAS_TOTALES = 42 [cite: 4]
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R" [cite: 4]
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]] [cite: 4]

# --- MOTOR DE CÁLCULO ---
@st.cache_data(show_spinner="Calculando rotación perfecta...")
def calcular_motor_final(n_ops, d_req, n_req, d_semana, seed): [cite: 4, 12]
    ops = [f"Op {i+1}" for i in range(n_ops)] [cite: 5]
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops} [cite: 4, 5]
    patron_maestro = [TURNO_DIA, TURNO_DIA, DESCANSO, DESCANSO, TURNO_NOCHE, TURNO_NOCHE, DESCANSO, DESCANSO] [cite: 5]
    
    random.seed(seed) [cite: 5]
    random.shuffle(ops) [cite: 5]
    grupos = [ops[i::4] for i in range(4)] [cite: 5]
    offsets = [0, 2, 4, 6] [cite: 5]

    for bloque_idx in [0, 21]: [cite: 5]
        bloque = range(bloque_idx, bloque_idx + 21) [cite: 5]
        cob_dia = {d: 0 for d in bloque} [cite: 6]
        cob_noche = {d: 0 for d in bloque} [cite: 6]
        turnos_bloque = {op: 0 for op in ops} [cite: 6]
        turnos_semanales = {op: [0, 0, 0] for op in ops} [cite: 6]
        cnt_dia = {op: 0 for op in ops} [cite: 6]
        cnt_noche = {op: 0 for op in ops} [cite: 7]

        # FASE 1: ASIGNACIÓN BASE
        for g_idx, grupo_ops in enumerate(grupos): [cite: 8]
            off = offsets[g_idx] [cite: 8]
            for op in grupo_ops: [cite: 8]
                for d in bloque: [cite: 8]
                    if (d % 7) >= d_semana: continue [cite: 8]
                    val = patron_maestro[(d + off) % 8] [cite: 8, 9]
                    if val != DESCANSO: [cite: 9]
                        horario[op][d] = val [cite: 9]
                        if val == TURNO_DIA: [cite: 9]
                            cob_dia[d] += 1 [cite: 10]
                            cnt_dia[op] += 1 [cite: 10]
                        else: [cite: 11]
                            cob_noche[d] += 1 [cite: 11]
                            cnt_noche[op] += 1 [cite: 11]
                        turnos_bloque[op] += 1 [cite: 9]
                        turnos_semanales[op][(d - bloque_idx) // 7] += 1 [cite: 9]

        # FASE 2: REFUERZOS NIVELADOS (CAP 2)
        for limite_ref in [1, 2]: [cite: 12]
            deudores = [op for op in ops if turnos_bloque[op] < 11] [cite: 12]
            random.shuffle(deudores) [cite: 12]
            for op in deudores: [cite: 13]
                if turnos_bloque[op] >= 11: continue [cite: 13]
                tipo_nec = TURNO_DIA if cnt_dia[op] <= cnt_noche[op] else TURNO_NOCHE [cite: 13]
                candidatos = []
                for d in bloque: [cite: 14]
                    if (d % 7) < d_semana and horario[op][d] == DESCANSO: [cite: 14]
                        sem_idx = (d - bloque_idx) // 7 [cite: 14]
                        if turnos_semanales[op][sem_idx] >= 4: continue [cite: 14]
                        if tipo_nec == TURNO_DIA and d > bloque_idx and horario[op][d-1] == TURNO_NOCHE: continue [cite: 15]
                        ref_hoy = (cob_dia[d] - d_req) + (cob_noche[d] - n_req) [cite: 16]
                        if ref_hoy >= limite_ref: continue [cite: 16]
                        v_izq = horario[op][d-1] if d > bloque_idx else None [cite: 16]
                        v_der = horario[op][d+1] if d < bloque_idx + 20 else None [cite: 16]
                        es_bloque = 1 if (v_izq == tipo_nec or v_der == tipo_nec) else 0 [cite: 17]
                        candidatos.append(((ref_hoy, -es_bloque), d)) [cite: 17]
                if candidatos: [cite: 17]
                    candidatos.sort() [cite: 18]
                    d_sel = candidatos[0][1] [cite: 18]
                    horario[op][d_sel] = tipo_nec [cite: 18]
                    if tipo_nec == TURNO_DIA: [cite: 19]
                        cob_dia[d_sel] += 1 [cite: 19]
                        cnt_dia[op] += 1 [cite: 20]
                    else: [cite: 20]
                        cob_noche[d_sel] += 1 [cite: 20]
                        cnt_noche[op] += 1 [cite: 21]
                    turnos_bloque[op] += 1 [cite: 19]
                    turnos_semanales[op][(d_sel - bloque_idx) // 7] += 1 [cite: 19]
    return pd.DataFrame(horario, index=NOMBRES_DIAS).T [cite: 21]

# --- INICIALIZACIÓN ---
if 'seed' not in st.session_state: st.session_state['seed'] = 42 [cite: 1]
if 'mapping' not in st.session_state: st.session_state['mapping'] = {} [cite: 1]

with st.sidebar: [cite: 2]
    st.header("📂 Base de Datos") [cite: 2]
    archivo_subido = st.file_uploader("Adjuntar archivo COSECHA.xlsx", type=["xlsx"]) [cite: 2]
    fichas_cargadas = []
    cargo_sugerido = "Cosechador" [cite: 2]
    conteo_sugerido = 20 [cite: 2]
    
    if archivo_subido: [cite: 2]
        excel_data = pd.ExcelFile(archivo_subido) [cite: 2]
        hoja_sel = st.selectbox("Escoger hoja cargo", excel_data.sheet_names) [cite: 2]
        df_excel = pd.read_excel(archivo_subido, sheet_name=hoja_sel) [cite: 2]
        cargo_sugerido = hoja_sel [cite: 2]
        fichas_cargadas = df_excel.iloc[:, 0].dropna().astype(str).str.strip().tolist() [cite: 2]
        conteo_sugerido = len(fichas_cargadas) [cite: 3]
        st.info(f"Fichas detectadas: {conteo_sugerido}") [cite: 3]

    st.header("👤 Parámetros") [cite: 3]
    cargo = st.text_input("Nombre del Cargo", value=cargo_sugerido) [cite: 3]
    demanda_dia = st.number_input(f"{cargo} Día", min_value=1, value=5) [cite: 3]
    demanda_noche = st.number_input(f"{cargo} Noche", min_value=1, value=5) [cite: 3]
    horas_turno = st.number_input("Horas/turno", min_value=1, value=12) [cite: 3]
    dias_cubrir = st.slider("Días/semana", 1, 7, 7) [cite: 3]
    factor_cobertura = st.slider("Factor Holgura", 1.0, 1.5, 1.0, 0.01) [cite: 3]
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01) [cite: 3, 4]
    operadores_actuales = st.number_input(f"{cargo} actual", min_value=0, value=conteo_sugerido) [cite: 4]

# --- LÓGICA DE PROCESO ---
def procesar(): [cite: 22]
    total_t = (demanda_dia + demanda_noche) * dias_cubrir * 3 [cite: 21, 22]
    op_f = max(math.ceil((math.ceil(total_t / 11) * factor_cobertura) / (1 - ausentismo)), (demanda_dia + demanda_noche) * 2) [cite: 22]
    op_f = ((op_f + 3) // 4) * 4 [cite: 22]
    st.session_state["df"] = calcular_motor_final(op_f, demanda_dia, demanda_noche, dias_cubrir, st.session_state['seed']) [cite: 22]
    st.session_state["op_final"] = op_f [cite: 22]

c1, c2, c3 = st.columns(3) [cite: 22]
with c1: 
    if st.button("🚀 Generar Programación"): procesar() [cite: 22]
with c2: 
    if st.button("🔄 Versión Alternativa"): [cite: 22]
        st.session_state['seed'] = random.randint(1, 99999) [cite: 22]
        procesar() [cite: 22]
with c3: 
    if st.button("👤 Aplicar Fichas Reales"): [cite: 23]
        if "df" in st.session_state: [cite: 23]
            ops_ids = st.session_state["df"].index.tolist() [cite: 23]
            f_lista = fichas_cargadas.copy() [cite: 23]
            random.shuffle(f_lista) [cite: 23]
            st.session_state['mapping'] = {op: f_lista[i] if i < len(f_lista) else f"VACANTE {i-len(f_lista)+1}" for i, op in enumerate(ops_ids)} [cite: 23]

# --- RENDERIZADO ---
if "df" in st.session_state: [cite: 24]
    df_base = st.session_state["df"] [cite: 24]
    op_f = st.session_state["op_final"] [cite: 24]
    
    # Crear df visual limpio para evitar KeyError en Styler
    df_visual = df_base.copy() [cite: 24]
    if st.session_state['mapping']: [cite: 24]
        df_visual.index = [st.session_state['mapping'].get(x, x) for x in df_visual.index] [cite: 24]
    
    m_col1, m_col2, m_col3 = st.columns(3) [cite: 24]
    with m_col1: st.markdown(f'<div class="metric-box-green"><div>Personal Total</div><div class="metric-value-dark">{op_f}</div></div>', unsafe_allow_html=True) [cite: 24]
    with m_col2: st.markdown(f'<div class="metric-box-green"><div>Fichas Reales</div><div class="metric-value-dark">{len(fichas_cargadas)}</div></div>', unsafe_allow_html=True) [cite: 24]
    with m_col3: st.markdown(f'<div class="metric-box-green"><div>Horas Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True) [cite: 24]

    st.subheader("📅 Programación (Bloques 2x2)") [cite: 24]
    style_f = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold" [cite: 24, 25]
    st.dataframe(df_visual.style.map(style_f), use_container_width=True) [cite: 25]

    st.subheader("📊 Balance Detallado") [cite: 25]
    stats = [] [cite: 25]
    for idx_orig in df_base.index: [cite: 25]
        f = df_base.loc[idx_orig] [cite: 25]
        identidad = st.session_state['mapping'].get(idx_orig, idx_orig) [cite: 25]
        c1_t = sum(1 for x in f[:21] if x != DESCANSO) [cite: 25]
        c2_t = sum(1 for x in f[21:] if x != DESCANSO) [cite: 26]
        stats.append({
            "Identidad": identidad, [cite: 25]
            "T. Día": (f==TURNO_DIA).sum(), [cite: 25]
            "T. Noche": (f==TURNO_NOCHE).sum(), [cite: 25]
            "Horas S1-3": c1_t * horas_turno, [cite: 25]
            "Secuencia S1-3": f"{sum(1 for x in f[0:7] if x!=DESCANSO)}-{sum(1 for x in f[7:14] if x!=DESCANSO)}-{sum(1 for x in f[14:21] if x!=DESCANSO)}", [cite: 26]
            "Horas S4-6": c2_t * horas_turno, [cite: 26]
            "Secuencia S4-6": f"{sum(1 for x in f[21:28] if x!=DESCANSO)}-{sum(1 for x in f[28:35] if x!=DESCANSO)}-{sum(1 for x in f[35:42] if x!=DESCANSO)}", [cite: 26]
            "Estado": "✅ 44h OK" if c1_t == 11 and c2_t == 11 else "⚠️ Revisar" [cite: 26, 27]
        })
    df_balance = pd.DataFrame(stats).set_index("Identidad") [cite: 27]
    st.dataframe(df_balance, use_container_width=True) [cite: 27]

    st.subheader("✅ Cobertura Diaria") [cite: 27]
    check = [] [cite: 27]
    for dia in NOMBRES_DIAS: [cite: 27]
        ad, an = (df_base[dia] == TURNO_DIA).sum(), (df_base[dia] == TURNO_NOCHE).sum() [cite: 27]
        ref = (ad-demanda_dia) + (an-demanda_noche) [cite: 27]
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ref, "Estado": "✅ OK" if ref <= 2 else "❌"}) [cite: 27]
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True) [cite: 27]

    # --- EXCEL CON COLORES Y BALANCE ---
    out = io.BytesIO() [cite: 28]
    with pd.ExcelWriter(out, engine="openpyxl") as writer: [cite: 28]
        df_visual.to_excel(writer, sheet_name="Programación") [cite: 28]
        df_balance.to_excel(writer, sheet_name="Balance") [cite: 28]
        
        workbook = writer.book
        worksheet = workbook["Programación"]
        fill_dia = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
        fill_noche = PatternFill(start_color="CCE5FF", end_color="CCE5FF", fill_type="solid")
        
        for row in worksheet.iter_rows(min_row=2, min_col=2):
            for cell in row:
                if cell.value == "D": cell.fill = fill_dia
                elif cell.value == "N": cell.fill = fill_noche

    st.download_button(label="⬇️ Descargar Excel Completo", data=out.getvalue(), file_name=f"Programacion_{cargo}.xlsx") [cite: 28]
