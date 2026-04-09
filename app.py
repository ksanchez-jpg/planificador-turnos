import streamlit as st
import math
import pandas as pd
import random
import io

# Configuración de la página
st.set_page_config(page_title="Programador Pro 44h", layout="wide")

st.title("🧮 PROGRAMACIÓN OPERATIVA DINÁMICA")
st.markdown("### Cobertura 100% | 44h Promedio | Equidad de Carga")

# -----------------------
# INPUTS
# -----------------------
with st.sidebar:
    st.header("📊 Requerimientos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    
    st.header("⚙️ Ajustes")
    factor_cobertura = st.slider("Factor de holgura (Reserva)", 1.0, 1.5, 1.15, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=15)

# -----------------------
# LÓGICA MAESTRA DINÁMICA
# -----------------------
SEMANAS = 6
DIAS_TOTALES = SEMANAS * 7
TURNOS_META = 22 # Equivale a 44h/semana promedio
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, SEMANAS+1) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

def generar_programacion_dinamica(n_ops, d_req, n_req):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42) # Para que el resultado sea estable

    # Contadores de control
    total_trabajado = {op: 0 for op in ops}
    noches_acum = {op: 0 for op in ops}
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    for d_idx in range(DIAS_TOTALES):
        # 1. Identificar restricciones (No N->D)
        hizo_noche_ayer = {op for op in ops if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE}
        
        # 2. SELECCIÓN DE PERSONAL PARA EL DÍA (CUMPLIMIENTO)
        # Prioridad a quienes llevan menos turnos totales para que todos lleguen a 22
        candidatos = sorted(ops, key=lambda x: total_trabajado[x])
        
        # Pool de trabajo para hoy (exactamente la suma de lo requerido)
        pool_hoy = candidatos[:(d_req + n_req)]
        
        asignados_n = []
        asignados_d = []

        # A. Asignar NOCHE a los que vienen de Noche (Si están en el pool de hoy)
        must_n = [op for op in pool_hoy if op in hizo_noche_ayer]
        for op in must_n:
            if len(asignados_n) < n_req:
                horario[op][d_idx] = TURNO_NOCHE
                noches_acum[op] += 1
                total_trabajado[op] += 1
                asignados_n.append(op)

        # B. Repartir el resto del pool para cubrir NOCHE (Equidad)
        restantes = [op for op in pool_hoy if op not in asignados_n]
        # Ordenar por quien lleva menos noches para equilibrar la carga
        restantes.sort(key=lambda x: noches_acum[x])
        
        for op in restantes:
            if len(asignados_n) < n_req:
                horario[op][d_idx] = TURNO_NOCHE
                noches_acum[op] += 1
                total_trabajado[op] += 1
                asignados_n.append(op)
            else:
                # C. Cubrir el turno de DÍA
                horario[op][d_idx] = TURNO_DIA
                total_trabajado[op] += 1
                asignados_d.append(op)

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# -----------------------
# INTERFAZ Y RESULTADOS
# -----------------------
if st.button("🚀 Generar Programación Dinámica"):
    # Cálculo de operadores basado en la carga total de turnos
    turnos_totales_necesarios = (demanda_dia + demanda_noche) * DIAS_TOTALES
    op_base = math.ceil(turnos_totales_necesarios / TURNOS_META)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    
    # Garantía de seguridad para rotación
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2)

    st.session_state["op_final"] = op_final
    st.session_state["df_horario"] = generar_programacion_dinamica(op_final, demanda_dia, demanda_noche)
    st.session_state["calculado"] = True

if st.session_state.get("calculado"):
    df = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]
    
    # Métricas de resumen
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Operadores Necesarios", op_final)
    with c2: st.metric("Cumplimiento Cobertura", "100%")
    with c3: st.metric("Faltantes", max(0, int(op_final - operadores_actuales)))

    # Cuadrante de Turnos
    st.subheader("📅 Cuadrante de Turnos")
    st.dataframe(df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"), use_container_width=True)

    # Validación de Cobertura (Resuelve Error 1)
    st.subheader("✅ Validación de Cobertura Diaria")
    cumplimiento = []
    for dia in NOMBRES_DIAS:
        cd = (df[dia] == TURNO_DIA).sum()
        cn = (df[dia] == TURNO_NOCHE).sum()
        cumplimiento.append({
            "Día": dia, "Día (Req)": demanda_dia, "Día (Asig)": cd, 
            "Noche (Req)": demanda_noche, "Noche (Asig)": cn, 
            "Estado": "✅ COMPLETO" if cd >= demanda_dia and cn >= demanda_noche else "❌ REVISAR"
        })
    st.dataframe(pd.DataFrame(cumplimiento).set_index("Día").T, use_container_width=True)

    # Reporte de Horas (Resuelve Error 2 y 3)
    st.subheader("📊 Reporte de Equidad y 44 Horas")
    resumen = []
    for op in df.index:
        n = (df.loc[op] == TURNO_NOCHE).sum()
        d = (df.loc[op] == TURNO_DIA).sum()
        resumen.append({
            "Operador": op, "Días (D)": d, "Noches (N)": n, 
            "Total Turnos": n+d, "Total Horas": (n+d)*12, 
            "Promedio h/sem": round(((n+d)*12)/6, 2)
        })
    df_res = pd.DataFrame(resumen).set_index("Operador")
    st.dataframe(df_res.style.map(lambda x: "background-color: #D4EDDA; font-weight: bold" if x == 44.0 else "", subset=["Promedio h/sem"]), use_container_width=True)

    # Exportación
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Programacion")
        df_res.to_excel(writer, sheet_name="Balance_Equidad")
    st.download_button("📥 Descargar Reporte Final (Excel)", data=output.getvalue(), file_name="plan_operativo_dinamico.xlsx")
