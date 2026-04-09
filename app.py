import streamlit as st
import math
import pandas as pd
import random

st.set_page_config(page_title="Calculadora de Personal", layout="wide")

st.title("🧮 Calculadora de Personal Operativo")
st.markdown("Ajusta los parámetros para calcular la cantidad de operadores necesarios")

# -----------------------
# INPUTS
# -----------------------

st.header("📊 Demanda")
demanda_dia = st.number_input("Operadores requeridos turno día", min_value=0, value=3)
demanda_noche = st.number_input("Operadores requeridos turno noche", min_value=0, value=3)

st.header("⚙️ Parámetros Operativos")
dias_semana = st.number_input("Días a cubrir por semana", min_value=1, max_value=7, value=7)
horas_turno = st.number_input("Horas por turno", min_value=1, value=12)

st.header("🧠 Modelo de Jornada")
horas_promedio_operador = st.selectbox(
    "Horas promedio por operador",
    options=[42, 44],
    index=1
)

st.header("📉 Ajustes")
factor_cobertura = st.slider("Factor de cobertura", 1.0, 1.3, 1.1, 0.01)
ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)

st.header("👥 Dotación actual")
operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=6)

# -----------------------
# BOTON CALCULAR
# -----------------------

if st.button("Calcular"):
    st.session_state["calculado"] = True

# -----------------------
# RESULTADOS (PERSISTENTES)
# -----------------------

if st.session_state.get("calculado"):

    horas_totales = (demanda_dia + demanda_noche) * horas_turno * dias_semana
    operadores_base = horas_totales / horas_promedio_operador
    operadores_ajustados = operadores_base * factor_cobertura

    if ausentismo > 0:
        operadores_ajustados = operadores_ajustados / (1 - ausentismo)

    operadores_final = math.ceil(operadores_ajustados)
    diferencia = operadores_final - operadores_actuales

    st.header("📈 Resultados")
    st.write(f"**Horas totales requeridas:** {horas_totales}")
    st.write(f"**Operadores teoricos (sin ajustes):** {round(operadores_base,2)}")
    st.write(f"**Operadores requeridos (ajustados):** {operadores_final}")

    if diferencia > 0:
        st.error(f"Faltan {diferencia} operadores")
    elif diferencia < 0:
        st.success(f"Sobran {abs(diferencia)} operadores")
    else:
        st.info("Dotacion exacta")

    st.markdown("---")
    st.subheader("Explicacion")
    st.write("""
    - Se calcula la carga total de horas semanales
    - Se divide entre las horas promedio por operador (ciclo 3 semanas: 4+4+3 dias x 12h = 44h promedio)
    - Se ajusta por cobertura y ausentismo
    - Se redondea hacia arriba
    """)

    # ============================================================
    # PROGRAMADOR
    # ============================================================

    st.header("📅 Programacion de Turnos (6 semanas)")

    SEMANAS = 6
    DIAS_TOTALES = SEMANAS * 7
    TURNO_DIA = "D"
    TURNO_NOCHE = "N"
    DESCANSO = "R"

    nombres_semana = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    NOMBRES_DIAS = []
    for s in range(1, SEMANAS + 1):
        for d in range(7):
            NOMBRES_DIAS.append(f"S{s}-{nombres_semana[d]}")

    PATRONES_CICLO = {
        0: [4, 4, 3],
        1: [4, 3, 4],
        2: [3, 4, 4],
    }

    def construir_dias_trabajo(num_operadores):
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

    def generar_programacion(num_operadores, demanda_dia, demanda_noche):

        operadores = [f"Op {i+1}" for i in range(num_operadores)]
        trabajo = construir_dias_trabajo(num_operadores)

        horario = {}
        for op in operadores:
            horario[op] = ["W" if trabajo[op][i] else DESCANSO for i in range(DIAS_TOTALES)]

        for dia_idx in range(DIAS_TOTALES):
            ops_hoy = [op for op in operadores if horario[op][dia_idx] == "W"]

            # ✅ NUEVA LOGICA (ÚNICO CAMBIO)
            ops_libre = []
            ops_vienen_de_noche = []

            for op in ops_hoy:
                turno_ayer = horario[op][dia_idx - 1] if dia_idx > 0 else DESCANSO
                if turno_ayer == TURNO_NOCHE:
                    ops_vienen_de_noche.append(op)
                else:
                    ops_libre.append(op)

            random.shuffle(ops_libre)
            random.shuffle(ops_vienen_de_noche)

            asignados_dia = 0
            asignados_noche = 0

            # Día
            for op in ops_libre:
                if asignados_dia < demanda_dia and horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = TURNO_DIA
                    asignados_dia += 1

            # Noche
            for op in ops_libre + ops_vienen_de_noche:
                if asignados_noche < demanda_noche and horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = TURNO_NOCHE
                    asignados_noche += 1

            # Sobrantes
            for op in ops_libre + ops_vienen_de_noche:
                if horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = TURNO_NOCHE

        # Verificar cobertura
        dias_incompletos = []
        for dia_idx in range(DIAS_TOTALES):
            cnt_d = sum(1 for op in operadores if horario[op][dia_idx] == TURNO_DIA)
            cnt_n = sum(1 for op in operadores if horario[op][dia_idx] == TURNO_NOCHE)
            if cnt_d < demanda_dia or cnt_n < demanda_noche:
                dias_incompletos.append({
                    "Dia": NOMBRES_DIAS[dia_idx],
                    "Dia asignado": cnt_d,
                    "Dia requerido": demanda_dia,
                    "Noche asignada": cnt_n,
                    "Noche requerida": demanda_noche
                })

        df = pd.DataFrame(horario, index=NOMBRES_DIAS).T
        df.index.name = "Operador"
        return df, dias_incompletos

    def calcular_estadisticas(df, operadores_list):
        filas = []
        for op in operadores_list:
            fila = {"Operador": op}
            total_horas = 0
            for s in range(SEMANAS):
                dias = NOMBRES_DIAS[s*7:(s+1)*7]
                trabajados = sum(1 for d in dias if df.loc[op, d] in [TURNO_DIA, TURNO_NOCHE])
                h = trabajados * horas_turno
                fila[f"S{s+1} dias"] = trabajados
                fila[f"S{s+1} horas"] = h
                total_horas += h
            fila["Total horas"] = total_horas
            fila["Prom h/sem"] = round(total_horas / SEMANAS, 1)
            filas.append(fila)
        return pd.DataFrame(filas).set_index("Operador")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Generar programacion"):
            st.session_state["generar"] = True
            st.session_state["seed"] = random.randint(0, 9999)
    with col2:
        if st.session_state.get("generar"):
            if st.button("Regenerar (nueva aleatoriedad)"):
                st.session_state["seed"] = random.randint(0, 9999)

    if st.session_state.get("generar"):

        random.seed(st.session_state.get("seed", 42))

        df, dias_incompletos = generar_programacion(
            operadores_final,
            demanda_dia,
            demanda_noche
        )

        operadores_list = df.index.tolist()

        if not dias_incompletos:
            st.success("Cobertura completa")
        else:
            st.error("Cobertura incompleta")

        st.markdown("**Leyenda:** D = Turno Dia | N = Turno Noche | R = Descanso")

        def colorear(val):
            if val == TURNO_DIA:
                return "background-color: #FFF3CD"
            elif val == TURNO_NOCHE:
                return "background-color: #CCE5FF"
            else:
                return "background-color: #F8F9FA"

        st.dataframe(df.style.map(colorear), use_container_width=True)

        st.subheader("Horas trabajadas por operador")
        df_stats = calcular_estadisticas(df, operadores_list)
        st.dataframe(df_stats)

        file = "programacion_turnos.xlsx"
        with pd.ExcelWriter(file) as writer:
            df.to_excel(writer)

        with open(file, "rb") as f:
            st.download_button("Descargar Excel", f)
