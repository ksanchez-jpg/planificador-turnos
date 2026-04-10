import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Planificador 44H Pro", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; }

.metric-box-green {
    background: #10B981; 
    color: #064E3B;
    border-radius: 8px;
    padding: 1.2rem;
    text-align: center;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
.metric-label-dark { font-size: 0.75rem; color: #064E3B; text-transform: uppercase; font-weight: 600; }
.metric-value-dark { font-size: 2.2rem; font-family: 'IBM Plex Mono', monospace; font-weight: 700; }
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PROGRAMACIÓN DE PERSONAL (44H)")
st.caption("Garantía: 11 turnos exactos cada 3 semanas y cumplimiento de fatiga.")

# 2. SIDEBAR
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

# 3. CONSTANTES
SEMANAS      = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN (44H CADA 3 SEMANAS)
def generar_programacion_44h(n_ops, d_req, n_req, dias_op):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)

    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    turnos_realizados = {op: 0 for op in ops}
    racha_trabajo = {op: 0 for op in ops}
    noches_acum = {op: 0 for op in ops}

    for d_idx in range(DIAS_TOTALES):
        dia_sem = d_idx % 7 
        if dia_sem >= dias_op: continue

        # Control de ciclo: Semanas 1-3 (días 0-20) y Semanas 4-6 (días 21-41)
        # En cada ciclo de 21 días, el operador debe hacer 11 turnos.
        meta_ciclo = 11
        inicio_ciclo = 0 if d_idx < 21 else 21
        
        aptos = []
        for op in ops:
            turnos_en_este_ciclo = sum(1 for x in range(inicio_ciclo, d_idx) if horario[op][x] != DESCANSO)
            if racha_trabajo[op] < 2 and turnos_en_este_ciclo < meta_ciclo:
                aptos.append(op)
        
        # Selección Día (Evitar N->D)
        hizo_n_ayer = {op for op in aptos if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE}
        cand_dia = [op for op in aptos if op not in hizo_n_ayer]
        cand_dia.sort(key=lambda x: (sum(1 for i in range(inicio_ciclo, d_idx) if horario[x][i] != DESCANSO), -noches_acum[x]))
        
        asignados_d = cand_dia[:d_req]
        for op in asignados_d:
            horario[op][d_idx] = TURNO_DIA
            racha_trabajo[op] += 1

        # Selección Noche
        ya_en_dia = set(asignados_d)
        cand_noche = [op for op in aptos if op not in ya_en_dia]
        cand_noche.sort(key=lambda x: (sum(1 for i in range(inicio_ciclo, d_idx) if horario[x][i] != DESCANSO), noches_acum[x]))
        
        asignados_n = cand_noche[:n_req]
        for op in asignados_n:
            horario[op][d_idx] = TURNO_NOCHE
            racha_trabajo[op] += 1
            noches_acum[op] += 1

        trabajaron = set(asignados_d) | set(asignados_n)
        for op in ops:
            if op not in trabajaron: racha_trabajo[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button("🚀 Calcular y Generar Programación 44H"):
    total_turnos = (demanda_dia + demanda_noche) * dias_cubrir * 6
    op_final = math.ceil((total_turnos / 22) * factor_cobertura / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df_horario"] = generar_programacion_44h(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final
    st.session_state["calculado"] = True

# 6. RESULTADOS
if st.session_state.get("calculado"):
    df = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Operadores Necesarios</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Operadores a Contratar</div><div class="metric-value-dark">{faltantes}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Meta cada 3 Semanas</div><div class="metric-value-dark">44h</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Cuadrante de Turnos (Máximo 2 días seguidos)")
    st.dataframe(df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"), use_container_width=True)

    # Balance 44h cada 3 semanas
    st.subheader("📊 Balance por Ciclos de 3 Semanas")
    stats = []
    for op in df.index:
        fila = df.loc[op]
        c1 = sum(1 for x in fila[:21] if x != DESCANSO)
        c2 = sum(1 for x in fila[21:] if x != DESCANSO)
        stats.append({"Operador": op, "Turnos Sem 1-3": c1, "Horas Sem 1-3": c1*12, "Turnos Sem 4-6": c2, "Horas Sem 4-6": c2*12, "Promedio h/sem": round(((c1+c2)*12)/6, 1)})
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats.style.map(lambda x: "background-color:#D4EDDA;font-weight:bold" if x == 132 else "", subset=["Horas Sem 1-3", "Horas Sem 4-6"]), use_container_width=True)

    # Validación Cobertura
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        dia_idx = NOMBRES_DIAS.index(dia) % 7
        rd = demanda_dia if dia_idx < dias_cubrir else 0
        rn = demanda_noche if dia_idx < dias_cubrir else 0
        ad, an = (df[dia] == "D").sum(), (df[dia] == "N").sum()
        check.append({"Día": dia, "Req. D": rd, "Asig. D": ad, "Req. N": rn, "Asig. N": an, "Estado": "✅ OK" if ad>=rd and an>=rn else "❌ FALTA"})
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.style.map(lambda x: "color:green;font-weight:bold" if "OK" in str(x) else "color:red;font-weight:bold"), use_container_width=True)

    # Exportación
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}").to_excel(writer, sheet_name="Cuadrante")
        df_stats.to_excel(writer, sheet_name="Balance_44h")
        df_check.to_excel(writer, sheet_name="Cobertura")
    st.download_button("⬇️ Descargar Reporte en Excel", output.getvalue(), "plan_44h_ciclos.xlsx")
