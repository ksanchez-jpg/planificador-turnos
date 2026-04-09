import streamlit as st
import math
import pandas as pd
import random
import io

# Configuración de la página
st.set_page_config(page_title="Calculadora de Personal Pro", layout="wide")

st.title("🧮 Calculadora de Personal - Versión Final con Excel Colorizado")
st.markdown("Genera la programación mixta (D-D-N-N), calcula horas promedio y exporta con formato visual.")

# -----------------------
# INPUTS
# -----------------------
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=0, value=3)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=0, value=3)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    
    st.header("🧠 Modelo y Ajustes")
    horas_promedio_objetivo = st.selectbox("Horas promedio objetivo", options=[42, 44], index=1)
    factor_cobertura = st.slider("Factor de cobertura", 1.0, 1.3, 1.1, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=6)

# -----------------------
# LÓGICA DE PROGRAMACIÓN
# -----------------------
SEMANAS = 6
DIAS_TOTALES = SEMANAS * 7
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, SEMANAS+1) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

def generar_programacion_mixta(n_ops, d_req, n_req):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    
    # 1. Patrón base 44h (4-4-3)
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

    # 2. Posición en bloque para rotación interna
    posicion_bloque = {op: [0]*DIAS_TOTALES for op in ops}
    for op in ops:
        contador = 0
        for d in range(DIAS_TOTALES):
            if trabajo_base[op][d]:
                contador += 1
                posicion_bloque[op][d] = contador
            else:
                contador = 0

    # 3. Asignación
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    for d_idx in range(DIAS_TOTALES):
        quienes_trabajan = [op for op in ops if trabajo_base[op][d_idx]]
        prohibidos_dia = [op for op in quienes_trabajan if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE]
        aptos_d = [op for op in quienes_trabajan if op not in prohibidos_dia]
        
        # Priorizar Día a los que están empezando bloque (día 1 y 2)
        aptos_d.sort(key=lambda x: posicion_bloque[x][d_idx])
        
        asignados_d = []
        for op in aptos_d:
            if len(asignados_d) < d_req:
                horario[op][d_idx] = TURNO_DIA
                asignados_d.append(op)
        
        for op in quienes_trabajan:
            if op not in asignados_d:
                horario[op][d_idx] = TURNO_NOCHE

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# -----------------------
# EJECUCIÓN Y RENDERIZADO
# -----------------------
if st.button("Calcular y Generar Programación"):
    st.session_state["calculado"] = True
    
    # Cálculo de dotación
    horas_totales_req = (demanda_dia + demanda_noche) * horas_turno * 7
    op_necesarios = math.ceil(((horas_totales_req / horas_promedio_objetivo) * factor_cobertura) / (1 - ausentismo))
    st.session_state["op_final"] = op_necesarios
    st.session_state["df_horario"] = generar_programacion_mixta(op_necesarios, demanda_dia, demanda_noche)

if st.session_state.get("calculado"):
    df = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]
    
    st.metric("Operadores Necesarios", op_final, delta=int(op_final - operadores_actuales), delta_color="inverse")

    # 1. Tabla de Programación con Estilos
    st.subheader("📅 Cuadrante de Turnos")
    
    def aplicar_color_turnos(val):
        if val == "D": return "background-color: #FFF3CD; color: #856404; font-weight: bold"
        if val == "N": return "background-color: #CCE5FF; color: #004085; font-weight: bold"
        return "background-color: #F8F9FA; color: #ADB5BD"

    st.dataframe(df.style.map(aplicar_color_turnos), use_container_width=True)

    # 2. Balance de Carga Laboral (CON HORAS Y PROMEDIO)
    st.subheader("📊 Balance de Carga Laboral")
    stats_data = []
    for op in df.index:
        dias_t = (df.loc[op] != DESCANSO).sum()
        noches = (df.loc[op] == TURNO_NOCHE).sum()
        dias_d = (df.loc[op] == TURNO_DIA).sum()
        horas_totales = dias_t * horas_turno
        stats_data.append({
            "Operador": op,
            "Total Días": dias_t,
            "Turnos Día (D)": dias_d,
            "Turnos Noche (N)": noches,
            "Total Horas (6 sem)": horas_totales,
            "Promedio h/sem": round(horas_totales / SEMANAS, 1)
        })
    
    df_stats = pd.DataFrame(stats_data).set_index("Operador")
    
    # Resaltar si cumplen las 44h
    def resaltar_promedio(val):
        color = "#D4EDDA" if val == 44.0 else "#F8D7DA"
        return f"background-color: {color}"

    st.dataframe(df_stats.style.map(resaltar_promedio, subset=["Promedio h/sem"]), use_container_width=True)

    # 3. EXPORTACIÓN A EXCEL CON COLORES
    st.subheader("📥 Exportar Resultados")
    
    # Crear un buffer en memoria para el Excel
    output = io.BytesIO()
    
    # Aplicar estilos para la exportación
    # Nota: openpyxl es necesario para guardar estilos en Excel
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Hoja 1: Programación con colores
        df.style.map(aplicar_color_turnos).to_excel(writer, sheet_name="Programacion_Turnos")
        
        # Hoja 2: Estadísticas con colores en el promedio
        df_stats.style.map(resaltar_promedio, subset=["Promedio h/sem"]).to_excel(writer, sheet_name="Estadisticas_Horas")

    st.download_button(
        label="Descargar Excel con Colores",
        data=output.getvalue(),
        file_name="programacion_operativa_color.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Validación de Cobertura
    with st.expander("Verificar Cobertura Diaria"):
        cob_list = []
        for col in df.columns:
            cob_list.append({
                "Día": col, 
                "Día (Asig)": (df[col]==TURNO_DIA).sum(), 
                "Noche (Asig)": (df[col]==TURNO_NOCHE).sum(),
                "Estado": "✅ OK" if (df[col]==TURNO_DIA).sum() >= demanda_dia and (df[col]==TURNO_NOCHE).sum() >= demanda_noche else "❌ FALTA"
            })
        st.table(pd.DataFrame(cob_list).set_index("Día"))
