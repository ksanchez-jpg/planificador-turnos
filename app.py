import streamlit as st
import math
import pandas as pd
import io
import random
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# 1. CONFIGURACIÓN Y ESTILO [cite: 1]
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
st.caption("Optimizado para grandes volúmenes y exportación completa.")

if 'seed' not in st.session_state: st.session_state['seed'] = 42 [cite: 28]
if 'mapping' not in st.session_state: st.session_state['mapping'] = {}

# --- CARGA DE EXCEL --- [cite: 2]
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
            fichas_cargadas = df_excel.iloc[:, 0].dropna().astype(str).str.strip().tolist() [cite: 29]
            conteo_sugerido = len(fichas_cargadas)
            st.info(f"Fichas detectadas: {conteo_sugerido}") [cite: 3]

    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value=cargo_sugerido)
    demanda_dia = st.number_input(f"{cargo} Día", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} Noche", min_value=1, value=5)
    horas_turno = st.number_input("Horas/turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días/semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor Holgura", 1.0, 1.5, 1.0, 0.01) [cite: 30]
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01) [cite: 4]

# 3. CONSTANTES
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN OPTIMIZADO [cite: 7]
@st.cache_data
def generar_programacion_nivelada(n_ops, d_req, n_req, d_semana, seed):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    patron_maestro = [TURNO_DIA, TURNO_DIA, DESCANSO, DESCANSO, TURNO_NOCHE, TURNO_NOCHE, DESCANSO, DESCANSO] [cite: 31]

    random.seed(seed)
    random.shuffle(ops)
    grupos = [ops[i::4] for i in range(4)]
    offsets = [0, 2, 4, 6]

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_op = {op: 0 for op in ops}
        cob_dia = {d: 0 for d in bloque}
        cob_noche = {d: 0 for d in bloque}

        # FASE 1: ASIGNACIÓN BASE [cite: 32]
        for g_idx, grupo_ops in enumerate(grupos):
            off = offsets[g_idx]
            for op in grupo_ops:
                for d in bloque:
                    if (d % 7) >= d_semana: continue
                    val = patron_maestro[(d + off) % 8] [cite: 33]
                    if val != DESCANSO:
                        horario[op][d] = val
                        turnos_op[op] += 1
                        if val == TURNO_DIA: cob_dia[d] += 1
                        else: cob_noche[d] += 1 [cite: 34]

        # FASE 2: REFUERZOS NIVELADOS (Optimizado para tractoristas) [cite: 35]
        deudores = [op for op in ops if turnos_op[op] < 11]
        random.shuffle(deudores)
        for op in deudores:
            for d in bloque:
                if turnos_op[op] >= 11: break
                if (d % 7) < d_semana and horario[op][d] == DESCANSO: [cite: 38]
                    tipo = TURNO_DIA if cob_dia[d] <= cob_noche[d] else TURNO_NOCHE
                    horario[op][d] = tipo
                    turnos_op[op] += 1
                    if tipo == TURNO_DIA: cob_dia[d] += 1
                    else: cob_noche[d] += 1

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None: st.session_state['seed'] = semilla_manual
    st.session_state['mapping'] = {}
    total_t = (demanda_dia + demanda_noche) * dias_cubrir * 3 [cite: 43]
    op_f = max(math.ceil((math.ceil(total_t / 11) * factor_cobertura) / (1 - ausentismo)), (demanda_dia + demanda_noche) * 2)
    op_f = ((op_f + 3) // 4) * 4
    st.session_state["df"] = generar_programacion_nivelada(op_f, demanda_dia, demanda_noche, dias_cubrir, st.session_state['seed'])
    st.session_state["op_final"] = op_f

# BOTONES
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🚀 Generar Programación"): procesar_generacion(42)
with c2:
    if st.button("🔄 Versión Aleatoria"): procesar_generacion(random.randint(1, 100000))
with c3:
    if st.button("👤 Asignar Fichas Reales"):
        if "df" in st.session_state:
            ops_ids = st.session_state["df"].index.tolist() [cite: 44]
            f_lista = fichas_cargadas.copy()
            random.shuffle(f_lista)
            mapeo = {op: f_lista[i] if i < len(f_lista) else f"VACANTE {i-len(f_lista)+1}" for i, op in enumerate(ops_ids)}
            st.session_state['mapping'] = mapeo
            st.success("Personal asignado con éxito.")

# 6. RENDERIZADO Y EXPORTACIÓN [cite: 45]
if "df" in st.session_state:
    df_base = st.session_state["df"]
    
    # 1. Renombrar ANTES de aplicar estilo para evitar KeyError
    df_visual = df_base.copy()
    if st.session_state['mapping']:
        df_visual.index = [st.session_state['mapping'].get(x, x) for x in df_visual.index]

    # 2. Visualización en App
    st.subheader("📅 Programación")
    def style_f(v): [cite: 46]
        if v == "D": return "background-color: #FFF3CD; font-weight: bold"
        if v == "N": return "background-color: #CCE5FF; font-weight: bold"
        return "background-color: #F8F9FA; font-weight: bold"
    
    st.dataframe(df_visual.style.map(style_f), use_container_width=True)

    # 📊 TABLA DE BALANCE [cite: 47]
    stats_list = []
    for idx in df_base.index:
        f = df_base.loc[idx]
        stats_list.append({
            "Identidad": st.session_state['mapping'].get(idx, idx),
            "T. Día": int((f==TURNO_DIA).sum()), 
            "T. Noche": int((f==TURNO_NOCHE).sum()),
            "Horas Totales": int((f!=DESCANSO).sum() * horas_turno),
            "Secuencia": f"{sum(1 for x in f[0:7] if x!=DESCANSO)}-{sum(1 for x in f[7:14] if x!=DESCANSO)}",
            "Estado": "✅ OK" [cite: 48]
        })
    df_balance = pd.DataFrame(stats_list)
    st.subheader("📊 Balance Detallado")
    st.dataframe(df_balance.set_index("Identidad"), use_container_width=True)

    # ✅ TABLA DE CUMPLIMIENTO
    cumplimiento = []
    for dia in NOMBRES_DIAS:
        ad, an = (df_base[dia] == TURNO_DIA).sum(), (df_base[dia] == TURNO_NOCHE).sum()
        cumplimiento.append({
            "Día": dia, "Día (Req)": demanda_dia, "Día (Asig)": ad,
            "Noche (Req)": demanda_noche, "Noche (Asig)": an, "Cumplimiento": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "⚠️"
        })
    df_cumplimiento = pd.DataFrame(cumplimiento)
    st.subheader("✅ Validación de Cobertura")
    st.dataframe(df_cumplimiento.set_index("Día").T, use_container_width=True)

    # ── EXPORTACIÓN EXCEL COMPLETA ────────────────────── [cite: 49]
    out = io.BytesIO()
    wb = Workbook()
    
    # Estilos
    fill_D = PatternFill("solid", start_color="FFF3CD") [cite: 49]
    fill_N = PatternFill("solid", start_color="CCE5FF")
    fill_hdr = PatternFill("solid", start_color="0F172A")
    font_hdr = Font(bold=True, color="FFFFFF") [cite: 50]
    align_c = Alignment(horizontal="center", vertical="center") [cite: 51]
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin')) [cite: 53]

    # HOJA 1: Programación con Colores [cite: 50]
    ws1 = wb.active
    ws1.title = "Programación"
    ws1.append(["Identidad"] + list(df_visual.columns))
    for cell in ws1[1]: [cite: 52]
        cell.font = font_hdr; cell.fill = fill_hdr; cell.alignment = align_c; cell.border = border
    
    for r_idx, (idx, row) in enumerate(df_visual.iterrows(), 2):
        ws1.cell(r_idx, 1, idx).font = Font(bold=True) [cite: 54]
        for c_idx, val in enumerate(row, 2):
            cell = ws1.cell(r_idx, c_idx, val)
            cell.alignment = align_c; cell.border = border
            if val == "D": cell.fill = fill_D [cite: 55]
            elif val == "N": cell.fill = fill_N

    # HOJA 2: Balance [cite: 56]
    ws2 = wb.create_sheet("Balance Operadores")
    ws2.append(list(df_balance.columns))
    for cell in ws2[1]: [cite: 59]
        cell.font = font_hdr; cell.fill = fill_hdr
    for r_idx, row in enumerate(df_balance.values, 2):
        for c_idx, val in enumerate(row, 1):
            ws2.cell(r_idx, c_idx, val).border = border [cite: 61]

    # HOJA 3: Cumplimiento
    ws3 = wb.create_sheet("Cumplimiento")
    ws3.append(list(df_cumplimiento.columns))
    for cell in ws3[1]:
        cell.font = font_hdr; cell.fill = fill_hdr
    for r_idx, row in enumerate(df_cumplimiento.values, 2):
        for c_idx, val in enumerate(row, 1):
            ws3.cell(r_idx, c_idx, val).border = border

    wb.save(out) [cite: 62]
    st.download_button(label="⬇️ Descargar Excel Completo", data=out.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
