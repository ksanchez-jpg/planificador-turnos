import streamlit as st
import math
import pandas as pd
import io
import random

# ─────────────────────────────────────────────
# CONFIGURACIÓN Y ESTILO (Basado en tus preferencias)
# ─────────────────────────────────────────────
st.set_page_config(page_title="Planificador de Contratación", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; }

/* Bloques de Métricas Verdes */
.metric-box-green {
    background: #10B981; 
    color: #064E3B;
    border-radius: 8px;
    padding: 1.2rem;
    text-align: center;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
.metric-label-dark { 
    font-size: 0.75rem; 
    color: #064E3B; 
    text-transform: uppercase; 
    font-weight: 600; 
    letter-spacing: 0.05em;
}
.metric-value-dark { 
    font-size: 2.2rem; 
    font-family: 'IBM Plex Mono', monospace; 
    font-weight: 700; 
}
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PROGRAMACIÓN Y CONTRATACIÓN")
st.caption("Cálculo de brecha de personal y generación de cuadrante con exportación a color.")

# ─────────────────────────────────────────────
# SIDEBAR — PARÁMETROS OPERATIVOS
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia   = st.number_input("Operadores requeridos (Día)",   min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    horas_turno   = st.number_input("Horas por turno",               min_value=1, value=12)
    dias_cubrir   = st.slider("Días a cubrir por semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura   = st.slider("Factor de holgura técnica",  1.0, 1.5, 1.0, 0.01)
    ausentismo         = st.slider("Ausentismo (%)",       0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales (Nómina)", min_value=0, value=12)

# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────
SEMANAS      = 6
DIAS_TOTALES = 42
TURNOS_META  = 22 # Meta para 44h promedio
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]]

# ─────────────────────────────────────────────
# FUNCIONES DE ESTILO
# ─────────────────────────────────────────────
def style_t(v):
    if v == "D": return "background-color:#FFF3CD;color:#856404;font-weight:bold"
    if v == "N": return "background-color:#CCE5FF;color:#004085;font-weight:bold"
    return "background-color:#F8F9FA;color:#ADB5BD"

def color_cumple(val):
    if "OK" in str(val): return "color:green;font-weight:bold"
    if "FALTA" in str(val): return "color:red;font-weight:bold"
    return ""

# ─────────────────────────────────────────────
# MOTOR DE PROGRAMACIÓN
# ─────────────────────────────────────────────
def generar_programacion_final(n_ops, d_req, n_req, dias_op):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)

    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    turnos_realizados = {op: 0 for op in ops}
    racha_trabajo = {op: 0 for op in ops}
    noches_acum = {op: 0 for op in ops}

    for d_idx in range(DIAS_TOTALES):
        dia_semana_index = d_idx % 7 
        if dia_semana_index >= dias_op:
            continue

        aptos = [op for op in ops if racha_trabajo[op] < 2 and turnos_realizados[op] < TURNOS_META]
        hizo_n_ayer = {op for op in aptos if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE}
        
        candidatos_dia = [op for op in aptos if op not in hizo_n_ayer]
        candidatos_dia.sort(key=lambda x: (turnos_realizados[x], -noches_acum[x]))
        
        asignados_d = candidatos_dia[:d_req]
        for op in asignados_d:
            horario[op][d_idx] = TURNO_DIA
            turnos_realizados[op] += 1
            racha_trabajo[op] += 1

        ya_en_dia = set(asignados_d)
        candidatos_noche = [op for op in aptos if op not in ya_en_dia]
        candidatos_noche.sort(key=lambda x: (turnos_realizados[x], noches_acum[x]))
        
        asignados_n = candidatos_noche[:n_req]
        for op in asignados_n:
            horario[op][d_idx] = TURNO_NOCHE
            turnos_realizados[op] += 1
            racha_trabajo[op] += 1
            noches_acum[op] += 1

        trabajaron_hoy = set(asignados_d) | set(asignados_n)
        for op in ops:
            if op not in trabajaron_hoy:
                racha_trabajo[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# ─────────────────────────────────────────────
# EJECUCIÓN
# ─────────────────────────────────────────────
if st.button("🚀 Calcular y Generar Programación"):
    total_turnos_necesarios = (demanda_dia + demanda_noche) * dias_cubrir * 6
    op_base = math.ceil(total_turnos_necesarios / TURNOS_META)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df_horario"] = generar_programacion_final(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final
    st.session_state["calculado"] = True

# ─────────────────────────────────────────────
# RESULTADOS VISUALES
# ─────────────────────────────────────────────
if st.session_state.get("calculado"):
    df = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)

    # MÉTRICAS EN BLOQUES VERDES
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'''<div class="metric-box-green">
            <div class="metric-label-dark">Operadores Necesarios</div>
            <div class="metric-value-dark">{op_final}</div>
        </div>''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''<div class="metric-box-green">
            <div class="metric-label-dark">Operadores a Contratar</div>
            <div class="metric-value-dark">{faltantes}</div>
        </div>''', unsafe_allow_html=True)
    with col3:
        st.markdown(f'''<div class="metric-box-green">
            <div class="metric-label-dark">Promedio h/sem</div>
            <div class="metric-value-dark">44.0</div>
        </div>''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # CUADRANTE WEB
    st.subheader("📅 Cuadrante de Turnos")
    st.dataframe(df.style.map(style_t), use_container_width=True)

    # BALANCE DE CARGA
    st.subheader("📊 Balance de Carga Laboral")
    stats = []
    for op in df.index:
        n, d = (df.loc[op] == "N").sum(), (df.loc[op] == "D").sum()
        stats.append({"Operador": op, "Día (D)": d, "Noche (N)": n, "Total Turnos": n+d, "Prom h/sem": round((n+d)*12/6, 1)})
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats.style.map(lambda x: "background-color:#D4EDDA;font-weight:bold" if x == 44.0 else "", subset=["Prom h/sem"]), use_container_width=True)

    # VALIDACIÓN DE COBERTURA
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        dia_idx = NOMBRES_DIAS.index(dia) % 7
        req_d_hoy = demanda_dia if dia_idx < dias_cubrir else 0
        req_n_hoy = demanda_noche if dia_idx < dias_cubrir else 0
        asig_d, asig_n = (df[dia] == "D").sum(), (df[dia] == "N").sum()
        
        check.append({
            "Día": dia, "Req. D": req_d_hoy, "Asig. D": asig_d, 
            "Req. N": req_n_hoy, "Asig. N": asig_n,
            "Estado": "✅ OK" if asig_d >= req_d_hoy and asig_n >= req_n_hoy else "❌ FALTA"
        })
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.style.map(color_cumple), use_container_width=True)

    # EXPORTACIÓN A EXCEL CON COLORES
    st.subheader("📥 Exportar Resultados")
    output = io.BytesIO()
    
    # Aplicamos el estilo de colores al dataframe para Excel
    df_styled = df.style.map(style_t)
    
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_styled.to_excel(writer, sheet_name="Cuadrante")
        df_stats.to_excel(writer, sheet_name="Balance")
        df_check.to_excel(writer, sheet_name="Cobertura")
    
    st.download_button(
        label="⬇️ Descargar Excel con Colores",
        data=output.getvalue(),
        file_name="plan_operativo_colores.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
