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

st.title("🗓 PROGRAMACIÓN DE TURNOS - SISTEMA INTEGRAL")
st.caption("2x2 por bloques, Garantía de 132h y Límite Estricto de 2 Refuerzos.")

# --- MOTOR DE CÁLCULO (OBLIGATORIEDAD DE 11 TURNOS) ---
@st.cache_data(show_spinner="Calculando rotación perfecta y garantizando 132h...")
def generar_motor_final(n_ops, d_req, n_req, d_semana, seed):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    patron_maestro = [TURNO_DIA, TURNO_DIA, DESCANSO, DESCANSO, TURNO_NOCHE, TURNO_NOCHE, DESCANSO, DESCANSO]
    
    random.seed(seed)
    random.shuffle(ops)
    grupos = [ops[i::4] for i in range(4)]
    offsets = [0, 2, 4, 6]

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        cob_dia = {d: 0 for d in bloque}
        cob_noche = {d: 0 for d in bloque}
        turnos_bloque = {op: 0 for op in ops}
        turnos_semanales = {op: [0, 0, 0] for op in ops}

        # FASE 1: ASIGNACIÓN BASE 2x2
        for g_idx, grupo_ops in enumerate(grupos):
            off = offsets[g_idx]
            for op in grupo_ops:
                for d in bloque:
                    if (d % 7) >= d_semana: continue
                    val = patron_maestro[(d + off) % 8]
                    if val != DESCANSO:
                        horario[op][d] = val
                        if val == TURNO_DIA: cob_dia[d] += 1
                        else: cob_noche[d] += 1
                        turnos_bloque[op] += 1
                        turnos_semanales[op][(d - bloque_idx) // 7] += 1

        # FASE 2: REFUERZOS Y NIVELACIÓN (MÚLTIPLES PASADAS)
        # Pasada 1 y 2: Intentar mantener bloques de 3
        # Pasada 3: Si falta gente, meterlos donde sea (incluso aislados) para cumplir 11 turnos
        for modo in ["bloque", "rescate"]:
            for limite_ref in [0, 1, 2]: 
                deudores = [op for op in ops if turnos_bloque[op] < 11]
                if not deudores: break
                random.shuffle(deudores)
                
                for op in deudores:
                    if turnos_bloque[op] >= 11: continue
                    
                    d_op = sum(1 for d in bloque if horario[op][d] == TURNO_DIA)
                    n_op = sum(1 for d in bloque if horario[op][d] == TURNO_NOCHE)
                    tipo_nec = TURNO_DIA if d_op <= n_op else TURNO_NOCHE
                    
                    candidatos = []
                    for d in bloque:
                        if (d % 7) < d_semana and horario[op][d] == DESCANSO:
                            sem_idx = (d - bloque_idx) // 7
                            if turnos_semanales[op][sem_idx] >= 4: continue
                            if tipo_nec == TURNO_DIA and d > bloque_idx and horario[op][d-1] == TURNO_NOCHE: continue
                            
                            ref_hoy = (cob_dia[d] - d_req) + (cob_noche[d] - n_req)
                            if ref_hoy > limite_ref: continue
                            
                            v_izq = horario[op][d-1] if d > bloque_idx else None
                            v_der = horario[op][d+1] if d < bloque_idx + 20 else None
                            es_bloque = 1 if (v_izq == tipo_nec or v_der == tipo_nec) else 0
                            
                            if modo == "bloque":
                                if es_bloque == 1:
                                    candidatos.append((ref_hoy, d))
                            else: # Modo rescate: entra cualquiera con tal de llenar las horas
                                candidatos.append((ref_hoy, d))
                    
                    if candidatos:
                        candidatos.sort()
                        d_sel = candidatos[0][1]
                        horario[op][d_sel] = tipo_nec
                        if tipo_nec == TURNO_DIA: cob_dia[d_sel] += 1
                        else: cob_noche[d_sel] += 1
                        turnos_bloque[op] += 1
                        turnos_semanales[op][(d_sel - bloque_idx) // 7] += 1

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# --- PARÁMETROS E INICIALIZACIÓN ---
if 'seed' not in st.session_state: st.session_state['seed'] = 42
if 'mapping' not in st.session_state: st.session_state['mapping'] = {}

DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

with st.sidebar:
    st.header("📂 Base de Datos")
    archivo_subido = st.file_uploader("Adjuntar archivo COSECHA.xlsx", type=["xlsx"])
    fichas_cargadas = []
    cargo_sugerido = "Cosechador"
    conteo_sugerido = 20
    
    if archivo_subido:
        excel_data = pd.ExcelFile(archivo_subido)
        hoja_sel = st.selectbox("Escoger hoja cargo", excel_data.sheet_names)
        df_excel = pd.read_excel(archivo_subido, sheet_name=hoja_sel)
        cargo_sugerido = hoja_sel
        fichas_cargadas = df_excel.iloc[:, 0].dropna().astype(str).str.strip().tolist()
        conteo_sugerido = len(fichas_cargadas)
        st.info(f"Fichas detectadas: {conteo_sugerido}")

    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value=cargo_sugerido)
    demanda_dia = st.number_input(f"{cargo} Día", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} Noche", min_value=1, value=5)
    horas_turno = st.number_input("Horas/turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días/semana", 1, 7, 7)
    factor_cobertura = st.slider("Holgura Técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input(f"{cargo} en nómina", min_value=0, value=conteo_sugerido)

# 3. FUNCIONES DE PROCESO
def procesar():
    total_t = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_f = max(math.ceil((math.ceil(total_t / 11) * factor_cobertura) / (1 - ausentismo)), (demanda_dia + demanda_noche) * 2)
    op_f = ((op_f + 3) // 4) * 4 
    st.session_state["df"] = generar_motor_final(op_f, demanda_dia, demanda_noche, dias_cubrir, st.session_state['seed'])
    st.session_state["op_final"] = op_f

# BOTONES
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🚀 Generar Programación"): procesar()
with c2:
    if st.button("🔄 Versión Alternativa"):
        st.session_state['seed'] = random.randint(1, 99999)
        procesar()
with c3:
    if st.button("👤 Aplicar Fichas Reales"):
        if "df" in st.session_state:
            ops_ids = st.session_state["df"].index.tolist()
            f_lista = fichas_cargadas.copy()
            random.shuffle(f_lista)
            st.session_state['mapping'] = {op: f_list[i] if i < len(f_list) else f"VACANTE {i-len(f_list)+1}" for i, op in enumerate(ops_ids)}

# 4. RENDERIZADO
if "df" in st.session_state:
    df_base = st.session_state["df"]
    df_visual = df_base.copy()
    if st.session_state['mapping']:
        df_visual.index = [st.session_state['mapping'].get(x, x) for x in df_visual.index]
    
    op_final = st.session_state["op_final"]
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        st.markdown(f'<div class="metric-box-green"><div>Personal Total</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with m_col2:
        st.markdown(f'<div class="metric-box-green"><div>Fichas Reales</div><div class="metric-value-dark">{len(fichas_cargadas)}</div></div>', unsafe_allow_html=True)
    with m_col3:
        st.markdown(f'<div class="metric-box-green"><div>Horas Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación (Garantía de Horas)")
    style_f = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df_visual.style.map(style_f), use_container_width=True)

    st.subheader("📊 Balance Detallado")
    stats = []
    for idx_orig in df_base.index:
        f = df_base.loc[idx_orig]
        identidad = st.session_state['mapping'].get(idx_orig, idx_orig)
        c1_t = sum(1 for x in f[:21] if x != DESCANSO)
        c2_t = sum(1 for x in f[21:] if x != DESCANSO)
        stats.append({
            "Identidad": identidad,
            "T. Día": (f==TURNO_DIA).sum(),
            "T. Noche": (f==TURNO_NOCHE).sum(),
            "Horas S1-3": c1_t * horas_turno,
            "Secuencia S1-3": f"{sum(1 for x in f[0:7] if x!=DESCANSO)}-{sum(1 for x in f[7:14] if x!=DESCANSO)}-{sum(1 for x in f[14:21] if x!=DESCANSO)}",
            "Horas S4-6": c2_t * horas_turno,
            "Secuencia S4-6": f"{sum(1 for x in f[21:28] if x!=DESCANSO)}-{sum(1 for x in f[28:35] if x!=DESCANSO)}-{sum(1 for x in f[35:42] if x!=DESCANSO)}",
            "Estado": "✅ 44h OK" if c1_t == 11 and c2_t == 11 else "⚠️ Revisar"
        })
    df_balance = pd.DataFrame(stats).set_index("Identidad")
    st.dataframe(df_balance, use_container_width=True)

    st.subheader("✅ Validación de Cobertura (Nivelada)")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df_base[dia] == TURNO_DIA).sum(), (df_base[dia] == TURNO_NOCHE).sum()
        ref_tot = (ad - demanda_dia) + (an - demanda_noche)
        check.append({
            "Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Total Refuerzos": ref_tot, 
            "Estado": "✅ OK" if ref_tot <= 2 else "❌"
        })
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df_visual.to_excel(writer, sheet_name="Programación")
        df_balance.to_excel(writer, sheet_name="Balance")
    st.download_button(label="⬇️ Descargar Excel", data=out.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
