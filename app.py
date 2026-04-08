import streamlit as st
import math
import pandas as pd
import random

st.set_page_config(page_title="Calculadora de Personal", layout="centered")

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
# BOTÓN CALCULAR
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
    st.write(f"**Operadores teóricos (sin ajustes):** {round(operadores_base,2)}")
    st.write(f"**Operadores requeridos (ajustados):** {operadores_final}")

    if diferencia > 0:
        st.error(f"❌ Faltan {diferencia} operadores")
    elif diferencia < 0:
        st.success(f"✅ Sobran {abs(diferencia)} operadores")
    else:
        st.info("✔️ Dotación exacta")

    st.markdown("---")

    st.subheader("🧠 Explicación")

    st.write("""
    - Se calcula la carga total de horas semanales
    - Se divide entre las horas promedio por operador
    - Se ajusta por cobertura y ausentismo
    - Se redondea hacia arriba
    """)

    # ============================================================
    # 🔥 PROGRAMADOR
    # ============================================================

    st.header("📅 Programación de Turnos (6 semanas)")

    # -------------------------------
    # FUNCIONES
    # -------------------------------

    def crear_operadores(num_base, num_ad):
        return [f"Operador {i}" for i in range(1, num_base+1)] + \
               [f"Operador AD {i}" for i in range(1, num_ad+1)]

    def crear_dias():
        return [f"Día {i}" for i in range(1, 43)]

    def crear_matriz(operadores, dias):
        df = pd.DataFrame(index=operadores, columns=dias)
        df[:] = "R"
        return df

    def inicializar_estado(operadores):
        return {op: {"turnos": 0, "ultimo_turno": None} for op in operadores}

    def ordenar_operadores(operadores, estado):
        ops = operadores.copy()
        random.shuffle(ops)
        return sorted(ops, key=lambda op: estado[op]["turnos"])

    def puede_iniciar_bloque(matriz, op, dias, idx, duracion):
        for i in range(duracion):
            if idx + i >= len(dias):
                break
            if matriz.loc[op, dias[idx+i]] != "R":
                return False
        return True

    def asignar_bloque(matriz, estado, op, dias, idx, turno):
        duracion = random.choice([2, 3])
        for i in range(duracion):
            if idx + i >= len(dias):
                break
            dia = dias[idx+i]
            matriz.loc[op, dia] = turno
            estado[op]["turnos"] += 1
            estado[op]["ultimo_turno"] = turno

    def generar_programacion(num_base, num_ad, demanda_dia, demanda_noche):

        operadores = crear_operadores(num_base, num_ad)
        dias = crear_dias()
        matriz = crear_matriz(operadores, dias)
        estado = inicializar_estado(operadores)

        warnings = []

        for idx, dia in enumerate(dias):

            ops = ordenar_operadores(operadores, estado)

            asignados_dia = 0
            asignados_noche = 0

            for op in ops:
                if asignados_dia >= demanda_dia:
                    break

                if estado[op]["ultimo_turno"] == "N":
                    continue

                duracion = random.choice([2,3])

                if not puede_iniciar_bloque(matriz, op, dias, idx, duracion):
                    continue

                asignar_bloque(matriz, estado, op, dias, idx, "D")
                asignados_dia += 1

            for op in ops:
                if asignados_noche >= demanda_noche:
                    break

                if matriz.loc[op, dia] != "R":
                    continue

                duracion = random.choice([2,3])

                if not puede_iniciar_bloque(matriz, op, dias, idx, duracion):
                    continue

                asignar_bloque(matriz, estado, op, dias, idx, "N")
                asignados_noche += 1

            if asignados_dia < demanda_dia or asignados_noche < demanda_noche:
                warnings.append(dia)

        return matriz, warnings

    # -------------------------------
    # BOTÓN GENERAR
    # -------------------------------

    if st.button("🚀 Generar programación"):

        personal_adicional = max(0, operadores_final - operadores_actuales)

        matriz, warnings = generar_programacion(
            operadores_actuales,
            personal_adicional,
            demanda_dia,
            demanda_noche
        )

        st.success("✅ Programación generada")

        if warnings:
            st.warning(f"⚠️ {len(warnings)} días con cobertura incompleta")

        st.dataframe(matriz)

        file = "programacion_turnos.xlsx"
        matriz.to_excel(file)

        with open(file, "rb") as f:
            st.download_button(
                "📥 Descargar Excel",
                f,
                file_name=file
            )
