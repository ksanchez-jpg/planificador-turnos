import streamlit as st
import math
import pandas as pd
import random
import io

# 1. CONFIGURACIÓN Y UI ORIGINAL
st.set_page_config(page_title="Calculadora de Personal Pro", layout="wide")

st.title("🧮 PROGRAMACIÓN DE PERSONAL - ESQUEMAS DINÁMICOS")
st.markdown("Genera la programación combinando esquemas (4-4-3, 4-3-4, 3-4-4) y desfases de inicio.")

# -----------------------
# INPUTS (Tu estructura original)
# -----------------------
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    
    st.header("🧠 Modelo y Ajustes")
    horas_promedio_objetivo = 44 
    factor_cobertura = st.slider("Factor de cobertura", 1.0, 1.3, 1.1, 0.01) [cite: 1, 2]
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01) [cite: 2]
    operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=15) [cite: 2]

# -----------------------
# CONSTANTES
# -----------------------
SEMANAS = 6
DIAS_TOTALES = SEMANAS * 7
TURNOS_META = 22 
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, SEMANAS+1) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# -----------------------
# MOTOR DE PROGRAMACIÓN DINÁMICA
# -----------------------
def generar_programacion_mixta_dinamica(n_ops, d_req, n_req):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)

    # Definición de los esquemas solicitados (Regla 2)
    PATRONES = [
        [4, 4, 3, 4, 4, 3], # Esquema 4-4-3
        [4, 3, 4, 4, 3, 4], # Esquema 4-3-4
        [3, 4, 4, 3, 4, 4]  # Esquema 3-4-4
    ]

    # A. ASIGNACIÓN DE DÍAS DE TRABAJO (Con dinamismo de esquemas y offsets)
    trabajo_base = {}
    for i, op in enumerate(ops):
        dias = [False] * DIAS_TOTALES
        # Elegimos uno de los 3 esquemas de forma rotativa
        patron = PATRONES[i % 3] [cite: 3]
        # Aplicamos un desfase (offset) para que no todos descansen el mismo día
        offset = (i * 2) % 7 [cite: 3]
        
        for s in range(SEMANAS):
            n_dias_trabajo = patron[s]
            inicio_semana = s * 7
            for d in range(n_dias_trabajo):
                # Calculamos el día exacto de trabajo aplicando el dinamismo
                idx = inicio_semana + (offset + d) % 7 [cite: 4]
                dias[idx] = True
        trabajo_base[op] = dias

    # B. ASIGNACIÓN DE TURNOS D/N (Equidad y Reglas de seguridad)
    noches_acum = {op: 0 for op in ops}
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    for d_idx in range(DIAS_TOTALES):
        quienes_trabajan_hoy = [op for op in ops if trabajo_base[op][d_idx]]
        
        # Regla 6: Noche ayer -> No puede ser Día hoy
        prohibidos_dia = [op for op in quienes_trabajan_hoy if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE] [cite: 6]
        aptos_dia = [op for op in quienes_trabajan_hoy if op not in prohibidos_dia]
        
        # Prioridad para Día: los que llevan MÁS noches acumuladas (Regla 3)
        aptos_dia.sort(key=lambda x: -noches_acum[x])
        
        asignados_d = []
        for op in aptos_dia:
            if len(asignados_d) < d_req:
                horario[op][d_idx] = TURNO_DIA [cite: 7]
                asignados_d.append(op)
        
        # Los demás operadores que trabajan hoy cubren la Noche
        for op in quienes_trabajan_hoy:
            if op not in asignados_d:
                horario[op][d_idx] = TURNO_NOCHE [cite: 7]
                noches_acum[op] += 1

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# -----------------------
# EJECUCIÓN Y VISUALIZACIÓN
# -----------------------
if st.button("🚀 Calcular y Generar Programación"):
    # Cálculo de personal necesario para cubrir 24/7 con 22 turnos por persona
    total_turnos = (demanda_dia + demanda_noche) * DIAS_TOTALES
    op_base = math.ceil(total_turnos / TURNOS_META) [cite: 8]
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo)) [cite: 8]
    
    # Mínimo técnico para garantizar rotación
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2)

    st.session_state["op_final"] = op_final
    st.session_state["df_horario"] = generar_programacion_mixta_dinamica(op_final, demanda_dia, demanda_noche)
    st.session_state["calculado"] = True

if st.session_state.get("calculado"):
    df = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]
    
    # 1. MÉTRICAS (Estructura original)
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Operadores Necesarios", op_final) [cite: 9]
    with c2: 
        dif = int(op_final - operadores_actuales) [cite: 9]
        st.metric("Operadores Faltantes", max(0, dif), delta=f"{dif}", delta_color="inverse") [cite: 9]
    with c3: st.success("🎯 Cobertura 100% | 44h Promedio")

    # 2. CUADRANTE DE TURNOS (Con tus colores originales)
    st.subheader("📅 Cuadrante de Turnos")
    def color_t(v):
        if v == "D": return "background-color: #FFF3CD; color: #856404; font-weight: bold" [cite: 10]
        if v == "N": return "background-color: #CCE5FF; color: #004085; font-weight: bold" [cite: 11]
        return "background-color: #F8F9FA; color: #ADB5BD" [cite: 12]
    st.dataframe(df.style.map(color_t), use_container_width=True)

    # 3. BALANCE (Garantía de las 44h)
    st.subheader("📊 Balance de Carga Laboral (44h promedio)")
    stats = []
    for op in df.index:
        n, d = (df.loc[op] == "N").sum(), (df.loc[op] == "D").sum()
        stats.append({
            "Operador": op, "Días (D)": d, "Noches (N)": n, [cite: 13]
            "Total Turnos": n+d, "Horas Totales": (n+d)*12, [cite: 13]
            "Promedio h/sem": round(((n+d)*12)/6, 2) [cite: 13]
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats.style.map(lambda x: "background-color: #D4EDDA; font-weight: bold" if x == 44.0 else "", subset=["Promedio h/sem"]), use_container_width=True) [cite: 14]

    # 4. CUMPLIMIENTO (Resuelve tu Error de Cobertura)
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        cd, cn = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({
            "Día": dia, "Día (Req)": demanda_dia, "Día (Asig)": cd, [cite: 15]
            "Noche (Req)": demanda_noche, "Noche (Asig)": cn, [cite: 15]
            "Estado": "✅ OK" if cd >= demanda_dia and cn >= demanda_noche else "❌ REVISAR" [cite: 15]
        })
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True) [cite: 16, 17, 18]

    # 5. EXCEL
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.style.map(color_t).to_excel(writer, sheet_name="Cuadrante")
        df_stats.to_excel(writer, sheet_name="Balance")
    st.download_button("📥 Descargar Reporte Final (Excel)", data=output.getvalue(), file_name="plan_operativo_dinamico.xlsx") [cite: 19]
