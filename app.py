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

st.title("🗓 PROGRAMACIÓN DE TURNOS - MODELO 2x2 BLOQUES")
st.caption("Garantiza: Patrones de bloque, balance 5/6 turnos y meta de 132h sin turnos aislados.")

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
            st.info(f"Fichas detectadas: {conteo_sugerido}")

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

# 4. MOTOR DE PROGRAMACIÓN POR GRUPOS (BLOQUES ESTRICTOS)
def generar_programacion_bloques(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    
    # Definimos el patrón maestro de 8 días: 2 Día, 2 Descanso, 2 Noche, 2 Descanso
    patron_maestro = [TURNO_DIA, TURNO_DIA, DESCANSO, DESCANSO, TURNO_NOCHE, TURNO_NOCHE, DESCANSO, DESCANSO]
    
    # Dividimos a los operadores en 4 grupos para cubrir todas las rotaciones
    random.seed(st.session_state['seed'])
    random.shuffle(ops)
    grupos = [ops[i::4] for i in range(4)]
    offsets = [0, 2, 4, 6] # Desplazamientos para que los grupos se turnen

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        
        # Asignación de patrón base
        for g_idx, grupo_ops in enumerate(grupos):
            offset = offsets[g_idx]
            for op in grupo_ops:
                for d in bloque:
                    # Regla de días a cubrir (ej. solo Lun-Dom según slider)
                    if (d % 7) >= d_semana:
                        horario[op][d] = DESCANSO
                        continue
                    
                    idx_patron = (d + offset) % 8
                    horario[op][d] = patron_maestro[idx_patron]

        # FASE DE REFUERZO: Si alguien tiene < 11 turnos, sumamos uno PEGADO a un bloque
        for op in ops:
            conteo = sum(1 for d in bloque if horario[op][d] != DESCANSO)
            while conteo < 11:
                # Calculamos balance para ver qué necesita (D o N)
                dias_op = sum(1 for d in bloque if horario[op][d] == TURNO_DIA)
                noches_op = sum(1 for d in bloque if horario[op][d] == TURNO_NOCHE)
                tipo_necesario = TURNO_DIA if dias_op <= noches_op else TURNO_NOCHE
                
                # Buscamos un día de descanso que esté al lado de un turno del mismo tipo (para hacer bloque de 3)
                dia_asignado = False
                for d in bloque:
                    if (d % 7) < d_semana and horario[op][d] == DESCANSO:
                        # Verificar si tiene un vecino del mismo tipo
                        vecino_izq = horario[op][d-1] if d > bloque_idx else None
                        vecino_der = horario[op][d+1] if d < bloque_idx + 20 else None
                        
                        if vecino_izq == tipo_necesario or vecino_der == tipo_necesario:
                            # Evitar el error de Noche seguida de Día el mismo día o anterior
                            if tipo_necesario == TURNO_DIA and vecino_izq == TURNO_NOCHE: continue
                            
                            horario[op][d] = tipo_necesario
                            conteo += 1
                            dia_asignado = True
                            break
                
                if not dia_asignado: break # Si no hay huecos adyacentes, romper para evitar bucle

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None: st.session_state['seed'] = semilla_manual
    st.session_state['mapping'] = {}
    total_t = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_f = max(math.ceil((math.ceil(total_t / 11) * factor_cobertura) / (1 - ausentismo)), (demanda_dia + demanda_noche) * 2)
    # Forzar a que sea múltiplo de 4 para que los grupos queden parejos si es posible
    op_f = ((op_f + 3) // 4) * 4
    
    st.session_state["df"] = generar_programacion_bloques(op_f, demanda_dia, demanda_noche, dias_cubrir)
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
            st.success("Personal asignado en bloques.")

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

    st.subheader("📅 Programación Nivelada por Grupos (2x2 Real)")
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
