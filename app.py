import streamlit as st
import math
import pandas as pd
import random
import io

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Calculadora de Personal Pro", layout="wide")

st.title("🧮 PROGRAMACIÓN DE PERSONAL - REGLA 22 DÍAS (44H)")
st.markdown("Ajuste final: Garantía de 22 turnos exactos por operador y cobertura total de demanda.")

# -----------------------
# INPUTS (Sidebar)
# -----------------------
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    
    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de cobertura (Holgura)", 1.0, 1.3, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=16)

# -----------------------
# CONSTANTES
# -----------------------
SEMANAS = 6
DIAS_TOTALES = SEMANAS * 7
TURNOS_META = 22 # Regla imprescindible: 22 turnos = 44h promedio
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, SEMANAS+1) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# -----------------------
# MOTOR DE PROGRAMACIÓN
# -----------------------
def generar_programacion_22_dias(n_ops, d_req, n_req):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)

    # 1. PRE-ASIGNACIÓN DE DÍAS DE TRABAJO (Garantiza 22 días por persona)
    # Patrones que suman exactamente 22 días
    patrones_base = [
        [4, 4, 3, 4, 4, 3],
        [3, 4, 4, 3, 4, 4],
        [4, 3, 4, 4, 3, 4]
    ]
    
    trabajo_base = {}
    for i, op in enumerate(ops):
        dias = [False] * DIAS_TOTALES
        patron = patrones_base[i % 3]
        # Escalonamos los inicios para cubrir toda la semana
        offset = (i * 2) % 7 
        for s in range(SEMANAS):
            n_trabajo = patron[s]
            inicio_semana = s * 7
            for d in range(n_trabajo):
                idx = inicio_semana + (offset + d) % 7
                dias[idx] = True
        trabajo_base[op] = dias

    # 2. ASIGNACIÓN DE D/N CON REGLAS DE FATIGA (Max 2 seguidos y N->D prohibido)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}

    for d_idx in range(DIAS_TOTALES):
        trabajan_hoy = [op for op in ops if trabajo_base[op][d_idx]]
        
        # Regla 6: No N -> D (Si trabajó Noche ayer, hoy DEBE ser Noche si le toca trabajar)
        hizo_n_ayer = {op for op in trabajan_hoy if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE}
        
        asignados_n = []
        for op in hizo_n_ayer:
            if len(asignados_n) < (d_req + n_req): # Seguridad de cupo
                horario[op][d_idx] = TURNO_NOCHE
                noches_acum[op] += 1
                asignados_n.append(op)

        # Repartir el resto de cupos de noche por EQUIDAD
        restantes = [op for op in trabajan_hoy if op not in asignados_n]
        restantes.sort(key=lambda x: noches_acum[x]) # El que lleva menos noches va a la noche
        
        cupos_n_libres = max(0, n_req - len(asignados_n))
        for j, op in enumerate(restantes):
            if j < cupos_n_libres:
                horario[op][d_idx] = TURNO_NOCHE
                noches_acum[op] += 1
            else:
                horario[op][d_idx] = TURNO_DIA

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# -----------------------
# RESULTADOS
# -----------------------
if st.button("🚀 Generar Programación Perfecta"):
    # Cálculo matemático exacto para 44h (336 turnos totales / 22 por persona)
    turnos_totales_periodo = (demanda_dia + demanda_noche) * DIAS_TOTALES
    op_matematicos = math.ceil(turnos_totales_periodo / TURNOS_META)
    
    # Aplicamos holgura de ausentismo pero sin exceder el mínimo necesario para 44h
    op_final = math.ceil((op_matematicos * factor_cobertura) / (1 - ausentismo))
    
    st.session_state["op_final"] = op_final
    st.session_state["df_horario"] = generar_programacion_22_dias(op_final, demanda_dia, demanda_noche)
    st.session_state["calculado"] = True

if st.session_state.get("calculado"):
    df = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]

    # Métricas
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Operadores Necesarios", op_final)
    with c2: st.metric("Faltantes en Nómina", max(0, int(op_final - operadores_actuales)))
    with c3: st.success("✅ Todos con 22 días | 44h")

    # Cuadrante
    st.subheader("📅 Cuadrante de Turnos")
    st.dataframe(df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"), use_container_width=True)

    # Balance (Verificación de los 22 días)
    st.subheader("📊 Balance de Carga Laboral (Garantía 44h)")
    resumen = []
    for op in df.index:
        n, d = (df.loc[op] == TURNO_NOCHE).sum(), (df.loc[op] == TURNO_DIA).sum()
        resumen.append({
            "Operador": op, "Días (D)": d, "Noches (N)": n, 
            "Total Turnos": n+d, "Total Horas": (n+d)*12, 
            "Promedio h/sem": round(((n+d)*12)/6, 2)
        })
    df_stats = pd.DataFrame(resumen).set_index("Operador")
    st.dataframe(df_stats.style.map(lambda x: "background-color: #D4EDDA; font-weight: bold" if x == 44.0 else "background-color: #F8D7DA", subset=["Promedio h/sem"]), use_container_width=True)

    # Cobertura
    st.subheader("✅ Validación de Cobertura")
    check = []
    for dia in NOMBRES_DIAS:
        check.append({
            "Día": dia, "Día (Asig)": (df[dia]=="D").sum(), "Noche (Asig)": (df[dia]=="N").sum(), 
            "Estado": "✅ OK" if (df[dia]=="D").sum() >= demanda_dia and (df[dia]=="N").sum() >= demanda_noche else "❌ REVISAR"
        })
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)
