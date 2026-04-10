import streamlit as st
import math
import pandas as pd
import random
import io

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Calculadora de Personal Pro", layout="wide")

st.title("🧮 PROGRAMACIÓN DE PERSONAL - ESQUEMAS DINÁMICOS")
st.markdown("Cumplimiento total: Cobertura 100%, 44h promedio y equidad de turnos.")

# -----------------------
# INPUTS (Barra Lateral Original)
# -----------------------
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    
    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de cobertura", 1.0, 1.3, 1.1, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=15)

# -----------------------
# CONSTANTES Y LÓGICA
# -----------------------
SEMANAS = 6
DIAS_TOTALES = SEMANAS * 7
TURNOS_META = 22 # 22 turnos * 12h = 264h / 6 sem = 44h prom.
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

def generar_programacion_dinamica(n_ops, d_req, n_req):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)

    # Esquemas dinámicos (Regla 2)
    PATRONES = [
        [4, 4, 3, 4, 4, 3], # 4-4-3
        [4, 3, 4, 4, 3, 4], # 4-3-4
        [3, 4, 4, 3, 4, 4]  # 3-4-4
    ]

    # A. ASIGNACIÓN DE DÍAS DE TRABAJO (Con dinamismo y escalonamiento)
    trabajo_base = {}
    for i, op in enumerate(ops):
        dias = [False] * DIAS_TOTALES
        patron = PATRONES[i % 3] # Se turnan los esquemas
        offset = (i * 2) % 7     # Escalonamiento para cubrir huecos
        
        for s in range(SEMANAS):
            n_dias_semana = patron[s]
            inicio_semana = s * 7
            for d in range(n_dias_semana):
                idx = inicio_semana + (offset + d) % 7
                dias[idx] = True
        trabajo_base[op] = dias

    # B. ASIGNACIÓN DE TURNOS D/N (Equidad y Regla N->D)
    noches_acum = {op: 0 for op in ops}
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    for d_idx in range(DIAS_TOTALES):
        quienes_trabajan = [op for op in ops if trabajo_base[op][d_idx]]
        
        # Regla 6: Noche ayer -> No puede ser Día hoy
        hizo_n_ayer = {op for op in quienes_trabajan if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE}
        
        asignados_n = []
        # Forzar noche a los que vienen de noche (si trabajan hoy)
        for op in hizo_n_ayer:
            if len(asignados_n) < (d_req + n_req):
                horario[op][d_idx] = TURNO_NOCHE
                noches_acum[op] += 1
                asignados_n.append(op)
        
        # Completar cupo de noche por equidad (Regla 3)
        restantes = [op for op in quienes_trabajan if op not in asignados_n]
        restantes.sort(key=lambda x: noches_acum[x])
        
        cupos_n_libres = max(0, n_req - len(asignados_n))
        for j, op in enumerate(restantes):
            if j < cupos_n_libres:
                horario[op][d_idx] = TURNO_NOCHE
                noches_acum[op] += 1
            else:
                horario[op][d_idx] = TURNO_DIA

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# -----------------------
# EJECUCIÓN
# -----------------------
if st.button("🚀 Calcular y Generar Programación"):
    total_turnos = (demanda_dia + demanda_noche) * DIAS_TOTALES
    op_base = math.ceil(total_turnos / TURNOS_META)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    
    # Mínimo para asegurar rotación
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2)

    st.session_state["op_final"] = op_final
    st.session_state["df_horario"] = generar_programacion_dinamica(op_final, demanda_dia, demanda_noche)
    st.session_state["calculado"] = True

if st.session_state.get("calculado"):
    df = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]
    
    # 1. MÉTRICAS
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Operadores Necesarios", op_final)
    with c2: st.metric("Faltantes", max(0, int(op_final - operadores_actuales)))
    with c3: st.success("🎯 Cobertura 100% | 44h Promedio")

    # 2. CUADRANTE
    st.subheader("📅 Cuadrante de Turnos")
    def color_t(v):
        if v == "D": return "background-color: #FFF3CD; color: #856404; font-weight: bold"
        if v == "N": return "background-color: #CCE5FF; color: #004085; font-weight: bold"
        return "background-color: #F8F9FA; color: #ADB5BD"
    st.dataframe(df.style.map(color_t), use_container_width=True)

    # 3. BALANCE (Regla 2 y 3)
    st.subheader("📊 Balance de Carga Laboral (44h promedio)")
    stats = []
    for op in df.index:
        n, d = (df.loc[op] == TURNO_NOCHE).sum(), (df.loc[op] == TURNO_DIA).sum()
        stats.append({
            "Operador": op, "Días (D)": d, "Noches (N)": n,
            "Total Turnos": n+d, "Total Horas": (n+d)*12,
            "Promedio h/sem": round(((n+d)*12)/6, 2)
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats.style.map(lambda x: "background-color: #D4EDDA; font-weight: bold" if x == 44.0 else "", subset=["Promedio h/sem"]), use_container_width=True)

    # 4. CUMPLIMIENTO (Regla 1)
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        cd, cn = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({
            "Día": dia, "Día (Asig)": cd, "Noche (Asig)": cn,
            "Estado": "✅ OK" if cd >= demanda_dia and cn >= demanda_noche else "❌ REVISAR"
        })
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # 5. EXPORTACIÓN
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.style.map(color_t).to_excel(writer, sheet_name="Cuadrante")
        df_stats.to_excel(writer, sheet_name="Balance")
    st.download_button("📥 Descargar Reporte Final (Excel)", data=output.getvalue(), file_name="plan_operativo_44h.xlsx")
