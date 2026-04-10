import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Planificador Maestro 44H", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.metric-box-green { background: #10B981; color: #064E3B; border-radius: 8px; padding: 1.2rem; text-align: center; }
.metric-value-dark { font-size: 2.2rem; font-family: 'IBM Plex Mono', monospace; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PROGRAMACIÓN DE PERSONAL (44H)")
st.caption("Solución final: 11 turnos exactos por ciclo (132h) y máximo 2 días de fatiga.")

# 2. SIDEBAR - PARÁMETROS RESTAURADOS
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales (Nómina)", min_value=0, value=16)

# 3. CONSTANTES
SEMANAS = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]]

# 4. MOTOR DE ASIGNACIÓN (CRÉDITOS 11 TURNOS)
def generar_programacion_estricta_132h(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    racha = {op: 0 for op in ops}
    noches_acum = {op: 0 for op in ops}

    # Procesar por bloques de 3 semanas (21 días)
    for bloque in [range(0, 21), range(21, 42)]:
        turnos_bloque = {op: 0 for op in ops}
        
        # Fase 1: Asignación base (respetando demanda y fatiga)
        for d in bloque:
            dia_sem = d % 7
            if dia_sem >= d_semana: continue

            # Candidatos: No más de 2 seguidos y que no hayan llegado a 11
            aptos = [op for op in ops if racha[op] < 2 and turnos_bloque[op] < 11]
            
            # Asignar Día (Evitar N->D)
            hizo_n_ayer = {op for op in aptos if d > 0 and horario[op][d-1] == TURNO_NOCHE}
            cand_dia = sorted([op for op in aptos if op not in hizo_n_ayer], 
                              key=lambda x: (turnos_bloque[x], -noches_acum[x]))
            
            asignados_d = cand_dia[:d_req]
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_bloque[op] += 1
                racha[op] += 1

            # Asignar Noche
            ya_d = set(asignados_d)
            cand_n = sorted([op for op in aptos if op not in ya_d], 
                            key=lambda x: (turnos_bloque[x], noches_acum[x]))
            
            asignados_n = cand_n[:n_req]
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_bloque[op] += 1
                racha[op] += 1
                noches_acum[op] += 1

            # Reset racha
            trabajaron = set(asignados_d) | set(asignados_n)
            for op in ops:
                if op not in trabajaron: racha[op] = 0

        # Fase 2: Forzar el cumplimiento de 11 turnos (Refuerzos)
        for op in ops:
            while turnos_bloque[op] < 11:
                # Buscar un día de descanso en el bloque que no rompa la regla de 2 seguidos
                for d_busqueda in bloque:
                    dia_sem = d_busqueda % 7
                    if dia_sem >= d_semana or horario[op][d_busqueda] != DESCANSO: continue
                    
                    # Checar si poner un turno aquí crea una racha de 3
                    cons_antes = 0
                    if d_busqueda > 0 and horario[op][d_busqueda-1] != DESCANSO:
                        cons_antes = 1
                        if d_busqueda > 1 and horario[op][d_busqueda-2] != DESCANSO: cons_antes = 2
                    
                    cons_despues = 0
                    if d_busqueda < 41 and horario[op][d_busqueda+1] != DESCANSO:
                        cons_despues = 1
                        if d_busqueda < 40 and horario[op][d_busqueda+2] != DESCANSO: cons_despues = 2
                    
                    if (cons_antes + cons_despues + 1) <= 2:
                        horario[op][d_busqueda] = TURNO_DIA # Refuerzo siempre de día
                        turnos_bloque[op] += 1
                        break
                else: # Si no encontró hueco perfecto, rompería fatiga (emergencia para nómina)
                    break 

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. RESULTADOS
if st.button("🚀 Generar Programación 132h Estricta"):
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_final = math.ceil((total_turnos_ciclo / 11) * factor_cobertura / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 

    df = generar_programacion_estricta_132h(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["df"] = df
    st.session_state["op_final"] = op_final

if "df" in st.session_state:
    df = st.session_state["df"]
    op_final = st.session_state["op_final"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Operadores</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Contratar</div><div class="metric-value-dark">{max(0, op_final-operadores_actuales)}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Meta Ciclo</div><div class="metric-value-dark">132h</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Cuadrante (Máximo 2 días seguidos)")
    st.dataframe(df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"), use_container_width=True)

    # Validación 132h
    st.subheader("📊 Validación: 132 Horas cada 3 Semanas")
    stats = []
    for op in df.index:
        fila = df.loc[op]
        c1 = sum(1 for x in fila[:21] if x != DESCANSO)
        c2 = sum(1 for x in fila[21:] if x != DESCANSO)
        stats.append({"Operador": op, "Turnos S1-3": c1, "Horas C1": c1*12, "Turnos S4-6": c2, "Horas C2": c2*12, "Cumple 44h": "✅ SI" if c1 == 11 and c2 == 11 else "❌ NO"})
    st.dataframe(pd.DataFrame(stats).set_index("Operador"), use_container_width=True)

    # Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}").to_excel(writer, sheet_name="Cuadrante")
    st.download_button("⬇️ Descargar Excel", output.getvalue(), "plan_44h_final.xlsx")
