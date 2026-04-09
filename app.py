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
# RESULTADOS
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

    # =========================
    # PROGRAMADOR
    # =========================

    st.header("📅 Programacion de Turnos (6 semanas)")

    SEMANAS = 6
    DIAS_TOTALES = SEMANAS * 7
    TURNO_DIA = "D"
    TURNO_NOCHE = "N"
    DESCANSO = "R"

    nombres_semana = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"]
    NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1,SEMANAS+1) for d in nombres_semana]

    PATRONES_CICLO = {
        0:[4,4,3],
        1:[4,3,4],
        2:[3,4,4],
    }

    def construir_dias_trabajo(num_operadores):
        trabajo={}
        for i in range(num_operadores):
            op=f"Op {i+1}"
            dias=[False]*DIAS_TOTALES
            patron=PATRONES_CICLO[i%3]
            offset_base=(i*5)%7

            for s in range(SEMANAS):
                n=patron[s%3]
                inicio=s*7
                offset=(offset_base+s)%7
                for d in range(n):
                    dias[inicio+(offset+d)%7]=True

            trabajo[op]=dias
        return trabajo

    def contar_consecutivos(op, dia_idx, turno):
        count=0
        i=dia_idx-1
        while i>=0 and horario[op][i]==turno:
            count+=1
            i-=1
        return count

    def generar_programacion(num_operadores, demanda_dia, demanda_noche):

        operadores=[f"Op {i+1}" for i in range(num_operadores)]
        trabajo=construir_dias_trabajo(num_operadores)

        global horario
        horario={op:["W" if trabajo[op][i] else DESCANSO for i in range(DIAS_TOTALES)] for op in operadores}

        for dia_idx in range(DIAS_TOTALES):

            ops_hoy=[op for op in operadores if horario[op][dia_idx]=="W"]

            random.shuffle(ops_hoy)

            asignados_dia=0
            asignados_noche=0

            # DIA
            for op in ops_hoy:

                if horario[op][dia_idx]!="W":
                    continue

                turno_ayer = horario[op][dia_idx - 1] if dia_idx > 0 else DESCANSO

                # ❌ NO permitir N → D
                if turno_ayer == TURNO_NOCHE:
                    continue

                # ❌ evitar más de 2 días seguidos
                if contar_consecutivos(op, dia_idx, TURNO_DIA) >= 2:
                    continue

                if asignados_dia < demanda_dia:
                    horario[op][dia_idx]=TURNO_DIA
                    asignados_dia+=1

            # NOCHE
            for op in ops_hoy:

                if horario[op][dia_idx]!="W":
                    continue

                # ❌ evitar más de 2 noches seguidas
                if contar_consecutivos(op, dia_idx, TURNO_NOCHE) >= 2:
                    continue

                if asignados_noche < demanda_noche:
                    horario[op][dia_idx]=TURNO_NOCHE
                    asignados_noche+=1

            # SOBRANTES → NOCHE (mantener jornadas)
            for op in ops_hoy:
                if horario[op][dia_idx]=="W":
                    horario[op][dia_idx]=TURNO_NOCHE

        df=pd.DataFrame(horario,index=NOMBRES_DIAS).T
        df.index.name="Operador"

        return df, []

    # ---------------- GENERAR ----------------

    if st.button("Generar programacion"):

        df,_=generar_programacion(operadores_final,demanda_dia,demanda_noche)

        st.markdown("**Leyenda:** D = Día | N = Noche | R = Descanso")

        def colorear(val):
            if val=="D": return "background-color:#FFF3CD"
            if val=="N": return "background-color:#CCE5FF"
            return "background-color:#F8F9FA"

        st.dataframe(df.style.map(colorear),use_container_width=True)
