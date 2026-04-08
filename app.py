import streamlit as st
import math

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
# CÁLCULO
# -----------------------

if st.button("Calcular"):

    horas_totales = (demanda_dia + demanda_noche) * horas_turno * dias_semana
    
    operadores_base = horas_totales / horas_promedio_operador
    
    operadores_ajustados = operadores_base * factor_cobertura
    
    if ausentismo > 0:
        operadores_ajustados = operadores_ajustados / (1 - ausentismo)
    
    operadores_final = math.ceil(operadores_ajustados)
    
    diferencia = operadores_final - operadores_actuales

    # -----------------------
    # RESULTADOS
    # -----------------------

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