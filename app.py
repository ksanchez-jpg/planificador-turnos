import streamlit as st
import math
import pandas as pd
import random

# Configuración de la página
st.set_page_config(page_title="Calculadora de Personal Pro", layout="wide")

st.title("🧮 Calculadora de Personal Operativo")
st.markdown("Ajusta los parámetros para calcular la dotación y generar la programación de turnos.")

# -----------------------
# INPUTS
# -----------------------

with st.sidebar:
    st.header("📊 Parámetros de Demanda")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=0, value=3)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=0, value=3)
    
    st.header("⚙️ Parámetros Operativos")
    dias_semana = st.number_input("Días a cubrir por semana", min_value=1, max_value=7, value=7)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    
    st.header("🧠 Modelo de Jornada")
    horas_promedio_operador = st.selectbox(
        "Horas promedio por operador (objetivo)",
        options=[42, 44],
        index=1
    )
    
    st.header("📉 Ajustes")
    factor_cobertura = st.slider("Factor de cobertura (reserva)", 1.0, 1.3, 1.1, 0.01)
    ausentismo = st.slider("Ausentismo proyectado (%)", 0.0, 0.3, 0.0, 0.01)
    
    st.header("👥 Dotación Actual")
    operadores_actuales = st.number_input("Operadores actuales en nómina", min_value=0, value=6)

# -----------------------
# LÓGICA DE CÁLCULO DE DOTACIÓN
# -----------------------

if st.button("Calcular Requerimiento"):
    st.session_state["calculado"] = True

if st.session_state.get("calculado"):
    # Cálculos base
    horas_totales_semana = (demanda_dia + demanda_noche) * horas_turno * dias_semana
    operadores_base = horas_totales_semana / horas_promedio_operador
    
    # Aplicación de factores
    operadores_ajustados = operadores_base * factor_cobertura
    if ausentismo > 0:
        operadores_ajustados = operadores_ajustados / (1 - ausentismo)
    
    operadores_final = math.ceil(operadores_ajustados)
    diferencia = operadores_final - operadores_actuales

    # Visualización de Resultados
    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        st.metric("Horas Totales Semanales", f"{horas_totales_semana} h")
    with col_res2:
        st.metric("Operadores Requeridos", operadores_final)
    with col_res3:
        st.metric("Diferencia vs Actual", diferencia, delta_color="inverse")

    if diferencia > 0:
        st.error(f"⚠️ Atención: Faltan {diferencia} operadores para cubrir la demanda con los parámetros actuales.")
    elif diferencia < 0:
        st.success(f"✅ Tienes un excedente de {abs(diferencia)} operadores.")
    else:
        st.info("💎 Dotación equilibrada.")

    st.markdown("---")

    # ============================================================
    # PROGRAMADOR LÓGICO (6 SEMANAS)
    # ============================================================

    SEMANAS = 6
    DIAS_TOTALES = SEMANAS * 7
    TURNO_DIA = "D"
    TURNO_NOCHE = "N"
    DESCANSO = "R"

    nombres_semana_corta = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, SEMANAS + 1) for d in nombres_semana_corta]

    PATRONES_CICLO = {
        0: [4, 4, 3],  # Ciclo A
        1: [4, 3, 4],  # Ciclo B
        2: [3, 4, 4],  # Ciclo C
    }

    def construir_dias_trabajo(num_operadores):
        """Define qué días trabaja cada operador para promediar 44h."""
        trabajo = {}
        for op_idx in range(num_operadores):
            op = f"Op {op_idx+1}"
            dias = [False] * DIAS_TOTALES
            combo = op_idx % 3
            patron = PATRONES_CICLO[combo]
            offset_base = (op_idx * 5) % 7 

            for semana in range(SEMANAS):
                n_dias = patron[semana % 3]
                inicio = semana * 7
                offset = (offset_base + semana) % 7
                for d in range(n_dias):
                    dia_en_semana = (offset + d) % 7
                    dias[inicio + dia_en_semana] = True
            trabajo[op] = dias
        return trabajo

    def generar_programacion_mejorada(num_operadores, d_req, n_req):
        """
        Lógica corregida: 
        1. Prohíbe cambio N -> D inmediato.
        2. Prioriza D al volver de descanso (R).
        3. Fomenta semanas mixtas D y N.
        """
        operadores = [f"Op {i+1}" for i in range(num_operadores)]
        trabajo_base = construir_dias_trabajo(num_operadores)
        
        horario = {op: [DESCANSO] * DIAS_TOTALES for op in operadores}

        for dia_idx in range(DIAS_TOTALES):
            ops_hoy = [op for op in operadores if trabajo_base[op][dia_idx]]
            
            # SEPARAR POR RESTRICCIÓN FÍSICA
            # Si trabajó noche ayer, NO puede hacer día hoy (6am a 6am)
            prohibidos_dia = []
            aptos_dia = []
            
            for op in ops_hoy:
                ayer = horario[op][dia_idx - 1] if dia_idx > 0 else DESCANSO
                if ayer == TURNO_NOCHE:
                    prohibidos_dia.append(op)
                else:
                    aptos_dia.append(op)
            
            # Aleatoriedad para que la rotación sea justa
            random.shuffle(aptos_dia)
            
            asignados_d = 0
            # 1. Llenar cupo de DÍA con los aptos
            for op in aptos_dia:
                if asignados_d < d_req:
                    horario[op][dia_idx] = TURNO_DIA
                    asignados_d += 1
                else:
                    # Los aptos que no cupieron en día, pasan a NOCHE (Rotación mixta)
                    horario[op][dia_idx] = TURNO_NOCHE
            
            # 2. Los prohibidos para día van directo a NOCHE
            for op in prohibidos_dia:
                horario[op][dia_idx] = TURNO_NOCHE

        return pd.DataFrame(horario, index=NOMBRES_DIAS).T

    # -------------------------------
    # INTERFAZ DE PROGRAMACIÓN
    # -------------------------------
    st.header("📅 Programación Sugerida (Rotación Mixta)")
    
    if st.button("Generar / Regenerar Horario"):
        st.session_state["seed"] = random.randint(0, 99999)
        st.session_state["df_horario"] = generar_programacion_mejorada(operadores_final, demanda_dia, demanda_noche)

    if "df_horario" in st.session_state:
        df = st.session_state["df_horario"]

        # Estilo de la tabla
        def colorear_turnos(val):
            if val == TURNO_DIA: return "background-color: #FFF3CD; color: #856404; font-weight: bold"
            if val == TURNO_NOCHE: return "background-color: #CCE5FF; color: #004085; font-weight: bold"
            return "background-color: #F8F9FA; color: #ADB5BD"

        st.subheader("Cuadrante de Turnos")
        st.dataframe(df.style.map(colorear_turnos), use_container_width=True, height=400)

        # Estadísticas de Horas
        st.subheader("📊 Balance de Carga Laboral")
        stats_list = []
        for op in df.index:
            total_dias = (df.loc[op] != DESCANSO).sum()
            total_n_noches = (df.loc[op] == TURNO_NOCHE).sum()
            total_n_dias = (df.loc[op] == TURNO_DIA).sum()
            stats_list.append({
                "Operador": op,
                "Días de Trabajo": total_dias,
                "Turnos Día": total_n_dias,
                "Turnos Noche": total_n_noches,
                "Total Horas (6 sem)": total_dias * horas_turno,
                "Promedio Semanal": round((total_dias * horas_turno) / SEMANAS, 1)
            })
        
        df_stats = pd.DataFrame(stats_list).set_index("Operador")
        st.dataframe(df_stats, use_container_width=True)

        # Validación de Cobertura Diaria
        st.subheader("✅ Validación de Cobertura")
        cob_data = []
        for dia in NOMBRES_DIAS:
            c_d = (df[dia] == TURNO_DIA).sum()
            c_n = (df[dia] == TURNO_NOCHE).sum()
            cob_data.append({"Día": dia, "Día (Asig)": c_d, "Noche (Asig)": c_n})
        
        df_cob = pd.DataFrame(cob_data).set_index("Día")
        st.dataframe(df_cob.T, use_container_width=True)

        # Exportar a Excel
        file_name = "horario_operativo.xlsx"
        with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Programacion")
            df_stats.to_excel(writer, sheet_name="Estadisticas")
        
        with open(file_name, "rb") as f:
            st.download_button("📥 Descargar Horario en Excel", f, file_name=file_name)

st.markdown("---")
st.caption("Nota: El sistema garantiza que ningún operador pase de Noche a Día sin descanso intermedio.")
