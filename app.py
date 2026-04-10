import streamlit as st
import math
import pandas as pd
import random
import io

# 1. CONFIGURACIÓN DE LA APP
st.set_page_config(page_title="Calculadora de Personal Pro", layout="wide")

st.title("🧮 PROGRAMACIÓN DE PERSONAL - REGLAS DINÁMICAS")
st.markdown("Cumplimiento estricto: Máximo 2 días seguidos, cobertura 100% y 44h promedio.")

# -----------------------
# INPUTS (Barra Lateral)
# -----------------------
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    
    st.header("⚙️ Ajustes de Nómina")
    # Para 4+4 con descansos cada 2 días, recomendamos 17 o 18 personas para no fallar
    operadores_actuales = st.number_input("Operadores en nómina", min_value=1, value=17)

# -----------------------
# LÓGICA DE PROGRAMACIÓN (Créditos y Fatiga)
# -----------------------
SEMANAS = 6
DIAS_TOTALES = 42
TURNOS_META = 22 # Regla 2: 44h promedio [cite: 2]
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

def generar_programacion_final(n_ops, d_req, n_req):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)

    # Contadores para control de reglas
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    turnos_realizados = {op: 0 for op in ops} # Regla 2 [cite: 2]
    racha_trabajo = {op: 0 for op in ops} # Regla 5 
    noches_acum = {op: 0 for op in ops} # Regla 3 

    for d_idx in range(DIAS_TOTALES):
        # 1. Filtrar quién puede trabajar hoy (Fatiga y Créditos)
        aptos = []
        for op in ops:
            # Regla 5: Máximo 2 turnos seguidos 
            no_fatigado = racha_trabajo[op] < 2
            # Regla 2: Límite de 22 turnos para 44h promedio [cite: 2]
            no_excedido = turnos_realizados[op] < TURNOS_META
            
            if no_fatigado and no_excedido:
                aptos.append(op)
        
        # 2. Asignar Turno Día (Regla 6: No Noche -> Día) [cite: 6]
        hizo_n_ayer = {op for op in aptos if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE}
        candidatos_dia = [op for op in aptos if op not in hizo_n_ayer]
        
        # Balancear Día/Noche: Priorizar para día a quien lleva más noches 
        candidatos_dia.sort(key=lambda x: (-noches_acum[x], turnos_realizados[x]))
        
        asignados_d = []
        for op in candidatos_dia:
            if len(asignados_d) < d_req:
                horario[op][d_idx] = TURNO_DIA
                turnos_realizados[op] += 1
                racha_trabajo[op] += 1
                asignados_d.append(op)

        # 3. Asignar Turno Noche (Regla 1 y 3) [cite: 1, 3]
        ya_en_dia = set(asignados_d)
        candidatos_noche = [op for op in aptos if op not in ya_en_dia]
        # Priorizar para noche a quien lleva menos noches para equilibrio 
        candidatos_noche.sort(key=lambda x: (noches_acum[x], turnos_realizados[x]))
        
        asignados_n = []
        for op in candidatos_noche:
            if len(asignados_n) < n_req:
                horario[op][d_idx] = TURNO_NOCHE
                turnos_realizados[op] += 1
                racha_trabajo[op] += 1
                noches_acum[op] += 1
                asignados_n.append(op)

        # 4. Resetear racha de fatiga si el operador descansó hoy 
        trabajaron_hoy = set(asignados_d) | set(asignados_n)
        for op in ops:
            if op not in trabajaron_hoy:
                racha_trabajo[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# -----------------------
# RENDERIZADO (Solución al KeyError)
# -----------------------
if st.button("🚀 Generar Programación"):
    # El sistema calcula el horario y lo guarda en el session_state
    st.session_state["df_resultado"] = generar_programacion_final(operadores_actuales, demanda_dia, demanda_noche)
    st.session_state["calculado"] = True

# Verificamos si existe la clave antes de mostrarla para evitar el KeyError
if st.session_state.get("calculado"):
    df = st.session_state["df_resultado"]
    
    st.subheader("📅 Cuadrante de Turnos (Máximo 2 días seguidos)")
    st.dataframe(df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"), use_container_width=True)

    # Validación de Cobertura (Regla 1)
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        cd, cn = (df[dia] == "D").sum(), (df[dia] == "N").sum()
        check.append({
            "Día": dia, "Día (Req)": demanda_dia, "Día (Asig)": cd, 
            "Noche (Req)": demanda_noche, "Noche (Asig)": cn, 
            "Estado": "✅ OK" if cd >= demanda_dia and cn >= demanda_noche else "❌ REVISAR"
        })
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # Balance Final (Regla 2 y 3)
    st.subheader("📊 Balance Final de Carga (Meta 44h)")
    stats = []
    for op in df.index:
        n, d = (df.loc[op] == "N").sum(), (df.loc[op] == "D").sum()
        stats.append({"Operador": op, "Días (D)": d, "Noches (N)": n, "Total Turnos": n+d, "Promedio h/sem": round(((n+d)*12)/6, 2)})
    st.dataframe(pd.DataFrame(stats).set_index("Operador"), use_container_width=True)
