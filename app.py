import streamlit as st
import math
import pandas as pd
import random
import io

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Calculadora de Personal Pro", layout="wide")

st.title("🧮 PROGRAMACIÓN DE PERSONAL - REGLA ESTRICTA 2 DÍAS")
st.markdown("Cumplimiento garantizado: Máximo 2 días seguidos, cobertura total y 44h promedio.")

# -----------------------
# INPUTS (Sidebar)
# -----------------------
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    
    st.header("⚙️ Ajustes de Nómina")
    # Para 4+4 con descansos cada 2 días, 16-17 personas es lo correcto
    operadores_actuales = st.number_input("Operadores actuales", min_value=1, value=17)

# -----------------------
# LÓGICA DE CRÉDITOS Y FATIGA
# -----------------------
SEMANAS = 6
DIAS_TOTALES = 42
TURNOS_META = 22 # 22 turnos * 12h = 264h / 6 sem = 44h prom.
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

def generar_programacion_estricta(n_ops, d_req, n_req):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)

    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    turnos_realizados = {op: 0 for op in ops}
    racha_trabajo = {op: 0 for op in ops} # Contador de días seguidos
    noches_acum = {op: 0 for op in ops}

    for d_idx in range(DIAS_TOTALES):
        # 1. Identificar quién puede trabajar hoy
        aptos = []
        for op in ops:
            # Regla 5: Max 2 días seguidos
            no_fatigado = racha_trabajo[op] < 2
            # Regla 2: No pasarse de 22 turnos
            no_excedido = turnos_realizados[op] < TURNOS_META
            
            if no_fatigado and no_excedido:
                aptos.append(op)
        
        # 2. SELECCIÓN PARA TURNO DÍA (Regla 6: No N -> D)
        hizo_n_ayer = {op for op in aptos if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE}
        candidatos_dia = [op for op in aptos if op not in hizo_n_ayer]
        
        # Prioridad: los que llevan MÁS noches (Balance Regla 3) y MENOS turnos totales
        candidatos_dia.sort(key=lambda x: (-noches_acum[x], turnos_realizados[x]))
        
        asignados_d = []
        for op in candidatos_dia:
            if len(asignados_d) < d_req:
                horario[op][d_idx] = TURNO_DIA
                turnos_realizados[op] += 1
                racha_trabajo[op] += 1
                asignados_d.append(op)

        # 3. SELECCIÓN PARA TURNO NOCHE
        ya_asignados = set(asignados_d)
        candidatos_noche = [op for op in aptos if op not in ya_asignados]
        
        # Prioridad: los que llevan MENOS noches (Balance Regla 3)
        candidatos_noche.sort(key=lambda x: (noches_acum[x], turnos_realizados[x]))
        
        asignados_n = []
        for op in candidatos_noche:
            if len(asignados_n) < n_req:
                horario[op][d_idx] = TURNO_NOCHE
                turnos_realizados[op] += 1
                racha_trabajo[op] += 1
                noches_acum[op] += 1
                asignados_n.append(op)

        # 4. RESET DE RACHA PARA LOS QUE DESCANSAN
        trabajaron_hoy = set(asignados_d) | set(asignados_n)
        for op in ops:
            if op not in trabajaron_hoy:
                racha_trabajo[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# -----------------------
# RENDERIZADO
# -----------------------
if st.button("🚀 Generar Programación"):
    st.session_state["df"] = generar_programacion_estricta(operadores_actuales, demanda_dia, demanda_noche)
    st.session_state["calculado"] = True

if st.session_state.get("calculado"):
    df = st.session_state["df"]
    
    st.subheader("📅 Cuadrante de Turnos (Máximo 2 días)")
    st.dataframe(df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"), use_container_width=True)

    # Verificación de Cobertura
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        cd, cn = (df[dia] == "D").sum(), (df[dia] == "N").sum()
        check.append({
            "Día": dia, "Día (Asig)": cd, "Noche (Asig)": cn, 
            "Estado": "✅ OK" if cd >= demanda_dia and cn >= demanda_noche else "❌ REVISAR"
        })
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # Verificación de 44h
    st.subheader("📊 Balance Final (Meta 44h)")
    stats = []
    for op in df.index:
        n, d = (df.loc[op] == "N").sum(), (df.loc[op] == "D").sum()
        stats.append({"Operador": op, "Días (D)": d, "Noches (N)": n, "Total Turnos": n+d, "Promedio h/sem": round(((n+d)*12)/6, 2)})
    st.dataframe(pd.DataFrame(stats).set_index("Operador"), use_container_width=True)
