import streamlit as st
import math
import pandas as pd
import random

# Configuración
st.set_page_config(page_title="Calculadora de Personal Pro", layout="wide")

st.title("🧮 Calculadora de Personal - Rotación Mixta Semanal")
st.markdown("Esta versión asegura que los operadores **cambien de turno (D a N) dentro de la misma semana**.")

# -----------------------
# INPUTS
# -----------------------
with st.sidebar:
    st.header("📊 Parámetros")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=0, value=3)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=0, value=3)
    dias_semana = st.number_input("Días a cubrir por semana", min_value=1, max_value=7, value=7)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    
    st.header("🧠 Modelo")
    horas_promedio_operador = st.selectbox("Horas promedio objetivo", options=[42, 44], index=1)
    factor_cobertura = st.slider("Factor de cobertura", 1.0, 1.3, 1.1, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=6)

# -----------------------
# CÁLCULOS
# -----------------------
if st.button("Calcular Requerimiento"):
    st.session_state["calculado"] = True

if st.session_state.get("calculado"):
    horas_totales = (demanda_dia + demanda_noche) * horas_turno * dias_semana
    op_base = horas_totales / horas_promedio_operador
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    
    st.metric("Operadores Necesarios", op_final, delta=op_final - operadores_actuales, delta_color="inverse")

    # ============================================================
    # PROGRAMADOR CON ROTACIÓN D -> N (MISMA SEMANA)
    # ============================================================
    SEMANAS = 6
    DIAS_TOTALES = SEMANAS * 7
    TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
    NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, SEMANAS+1) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

    def generar_programacion_mixta(n_ops, d_req, n_req):
        ops = [f"Op {i+1}" for i in range(n_ops)]
        
        # 1. Crear el patrón de días de trabajo (4-4-3)
        trabajo_base = {}
        for i in range(n_ops):
            dias = [False] * DIAS_TOTALES
            patron = [4, 4, 3] if i % 3 == 0 else ([4, 3, 4] if i % 3 == 1 else [3, 4, 4])
            offset = (i * 5) % 7
            for s in range(SEMANAS):
                n_dias = patron[s % 3]
                inicio = s * 7
                for d in range(n_dias):
                    dias[inicio + (offset + s + d) % 7] = True
            trabajo_base[ops[i]] = dias

        # 2. Calcular la posición dentro de cada bloque de trabajo (1º día, 2º día...)
        posicion_bloque = {op: [0]*DIAS_TOTALES for op in ops}
        for op in ops:
            contador = 0
            for d in range(DIAS_TOTALES):
                if trabajo_base[op][d]:
                    contador += 1
                    posicion_bloque[op][d] = contador
                else:
                    contador = 0

        # 3. Asignación con lógica de rotación interna
        horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
        
        for d_idx in range(DIAS_TOTALES):
            quienes_trabajan = [op for op in ops if trabajo_base[op][d_idx]]
            
            # Clasificación de seguridad y preferencia
            must_n = []       # Trabajó Noche ayer -> Obligatorio Noche hoy
            aptos_pref_d = [] # Inicio de bloque -> Prefiere Día
            aptos_pref_n = [] # Final de bloque -> Prefiere Noche
            
            for op in quienes_trabajan:
                ayer = horario[op][d_idx-1] if d_idx > 0 else DESCANSO
                if ayer == TURNO_NOCHE:
                    must_n.append(op)
                else:
                    # Si está en sus primeros 2 días de trabajo, va a Día. Si no, a Noche.
                    if posicion_bloque[op][d_idx] <= 2:
                        aptos_pref_d.append(op)
                    else:
                        aptos_pref_n.append(op)
            
            random.shuffle(aptos_pref_d)
            random.shuffle(aptos_pref_n)
            
            asignados_d = []
            # Llenar DÍA: 1° los que prefieren Día, 2° los que prefieren Noche (pero pueden)
            candidatos_dia = aptos_pref_d + aptos_pref_n
            for op in candidatos_dia:
                if len(asignados_d) < d_req:
                    horario[op][d_idx] = TURNO_DIA
                    asignados_d.append(op)
            
            # Llenar NOCHE: Todos los demás (must_n + los aptos que no entraron en Día)
            for op in quienes_trabajan:
                if op not in asignados_d:
                    horario[op][d_idx] = TURNO_NOCHE

        return pd.DataFrame(horario, index=NOMBRES_DIAS).T

    # -------------------------------
    # VISUALIZACIÓN
    # -------------------------------
    st.header("📅 Cuadrante de Turnos (Rotación D-D-N-N)")
    if st.button("Generar Nueva Programación Mixta"):
        st.session_state["df_mixto"] = generar_programacion_mixta(op_final, demanda_dia, demanda_noche)

    if "df_mixto" in st.session_state:
        df = st.session_state["df_mixto"]
        
        def estilo(val):
            if val == "D": return "background-color: #FFF3CD; color: #856404; font-weight: bold"
            if val == "N": return "background-color: #CCE5FF; color: #004085; font-weight: bold"
            return "background-color: #F8F9FA; color: #ADB5BD"

        st.dataframe(df.style.map(estilo), use_container_width=True)

        # Balance de carga
        st.subheader("📊 Balance de Turnos por Operador")
        stats = []
        for op in df.index:
            stats.append({
                "Operador": op,
                "Total Días": (df.loc[op] != "R").sum(),
                "Turnos Día (D)": (df.loc[op] == "D").sum(),
                "Turnos Noche (N)": (df.loc[op] == "N").sum()
            })
        st.table(pd.DataFrame(stats))

        # Validación de cobertura
        st.subheader("✅ Cobertura Diaria")
        cob = []
        for col in df.columns:
            cob.append({"Día": col, "Día (Asig)": (df[col]=="D").sum(), "Noche (Asig)": (df[col]=="N").sum()})
        st.dataframe(pd.DataFrame(cob).set_index("Día").T, use_container_width=True)
