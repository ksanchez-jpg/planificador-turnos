import streamlit as st
import math
import pandas as pd
import random
import io

# Configuración de la página
st.set_page_config(page_title="Planificador Maestro 44h", layout="wide")

st.title("🧮 PROGRAMACIÓN INTEGRAL DE PERSONAL")
st.markdown("### Solución: Cobertura Total + 44h Exactas + Equidad Nocturna")

# -----------------------
# INPUTS (Barra Lateral)
# -----------------------
with st.sidebar:
    st.header("📊 Parámetros de Demanda")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=5)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=5)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    
    st.header("⚙️ Ajustes de Modelo")
    # El promedio de 44h es el núcleo del cálculo
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.2, 1.05, 0.01)
    ausentismo = st.slider("Ausentismo proyectado (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales en nómina", min_value=0, value=15)

# -----------------------
# CONSTANTES SISTÉMICAS
# -----------------------
SEMANAS = 6
DIAS_TOTALES = SEMANAS * 7 # 42 días
TURNOS_FIJOS = 22 # 22 turnos * 12h = 264h. 264h / 6 sem = 44h promedio.
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, SEMANAS+1) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

def generar_programacion_integrada(n_ops, d_req, n_req):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42) # Estabilidad del resultado

    # 1. CREACIÓN DEL PATRÓN DE DÍAS (Regla 44h)
    # Cada operador tiene exactamente 22 días marcados como "Trabajo"
    trabajo_base = {}
    for i in range(n_ops):
        dias = [False] * DIAS_TOTALES
        # Patrón cíclico 4-4-3 (11 días cada 3 semanas = 22 cada 6)
        ciclo = [4, 4, 3, 4, 4, 3] 
        offset = (i * 3) % 7 
        for s in range(SEMANAS):
            n_dias_semana = ciclo[s]
            inicio_semana = s * 7
            for d in range(n_dias_semana):
                idx = inicio_semana + (offset + d) % 7
                dias[idx] = True
        trabajo_base[ops[i]] = dias

    # 2. ASIGNACIÓN DINÁMICA DE D/N (Regla Cobertura + Equidad Noches)
    noches_acum = {op: 0 for op in ops}
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    for d_idx in range(DIAS_TOTALES):
        # ¿Quiénes deben trabajar hoy según su contrato de 44h?
        quienes_trabajan_hoy = [op for op in ops if trabajo_base[op][d_idx]]
        
        # Restricción biológica: Noche ayer -> Noche hoy (para no perder descanso)
        hizo_noche_ayer = {op for op in ops if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE}
        
        asignados_n = []
        asignados_d = []

        # A. Forzar Noche a los que vienen de Noche (y les toca trabajar)
        must_n = [op for op in quienes_trabajan_hoy if op in hizo_noche_ayer]
        for op in must_n:
            if len(asignados_n) < (d_req + n_req): # Solo si no excedemos el total
                horario[op][d_idx] = TURNO_NOCHE
                noches_acum[op] += 1
                asignados_n.append(op)

        # B. Repartir el resto para cubrir la demanda de NOCHE (Equidad)
        restantes = [op for op in quienes_trabajan_hoy if op not in asignados_n]
        # ORDENAR POR CARGA NOCTURNA: El que lleva menos noches va primero a la Noche
        restantes.sort(key=lambda x: noches_acum[x])
        
        cupos_noche_libres = max(0, n_req - len(asignados_n))
        for i in range(len(restantes)):
            op = restantes[i]
            if i < cupos_noche_libres:
                horario[op][d_idx] = TURNO_NOCHE
                noches_acum[op] += 1
                asignados_n.append(op)
            else:
                # C. Los demás cubren el turno de DÍA
                horario[op][d_idx] = TURNO_DIA
                asignados_d.append(op)

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# -----------------------
# PROCESAMIENTO
# -----------------------
if st.button("🚀 Generar Plan Maestro Integrado"):
    # CÁLCULO DE OPERADORES (Integrando Error 1 y 2)
    turnos_totales_periodo = (demanda_dia + demanda_noche) * DIAS_TOTALES
    # Cada persona aporta exactamente 22 turnos
    op_matematicos = math.ceil(turnos_totales_periodo / TURNOS_FIJOS)
    # Aplicar holgura y ausentismo
    op_final = math.ceil((op_matematicos * factor_cobertura) / (1 - ausentismo))
    
    st.session_state["op_final"] = op_final
    st.session_state["df_horario"] = generar_programacion_integrada(op_final, demanda_dia, demanda_noche)
    st.session_state["calculado"] = True

if st.session_state.get("calculado"):
    df = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]
    
    # 1. Indicadores
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Operadores Necesarios", op_final)
    with c2: st.metric("Faltantes en Nómina", max(0, int(op_final - operadores_actuales)))
    with c3: st.info("🎯 Meta: 44h promedio / Equidad Noches")

    # 2. Visualización
    st.subheader("📅 Cuadrante de Turnos")
    st.dataframe(df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"), use_container_width=True)

    # 3. Balance de Equidad (Muestra Error 2 y 3 resueltos)
    st.subheader("📊 Reporte de Equidad y Carga")
    resumen = []
    for op in df.index:
        n = (df.loc[op] == "N").sum()
        d = (df.loc[op] == "D").sum()
        resumen.append({
            "Operador": op, "Días (D)": d, "Noches (N)": n, 
            "Total Turnos": n+d, "Total Horas": (n+d)*12, 
            "Promedio h/sem": round(((n+d)*12)/6, 2)
        })
    df_res = pd.DataFrame(resumen).set_index("Operador")
    # Formato visual: Verde si es exactamente 44h
    st.dataframe(df_res.style.map(lambda x: "background-color: #D4EDDA; font-weight: bold" if x == 44.0 else "", subset=["Promedio h/sem"]), use_container_width=True)

    # 4. Cumplimiento (Muestra Error 1 resuelto)
    st.subheader("✅ Validación de Cobertura Diaria")
    cumplimiento = []
    for dia in NOMBRES_DIAS:
        cd = (df[dia] == "D").sum()
        cn = (df[dia] == "N").sum()
        cumplimiento.append({
            "Día": dia, "Día (Req)": demanda_dia, "Día (Asig)": cd, 
            "Noche (Req)": demanda_noche, "Noche (Asig)": cn, 
            "Estado": "✅ COMPLETO" if cd >= demanda_dia and cn >= demanda_noche else "❌ REVISAR"
        })
    st.dataframe(pd.DataFrame(cumplimiento).set_index("Día").T, use_container_width=True)

    # 5. Exportación
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Programacion")
        df_res.to_excel(writer, sheet_name="Balance_Equidad")
    st.download_button("📥 Descargar Plan Integrado (Excel)", data=output.getvalue(), file_name="plan_maestro_operativo.xlsx")
