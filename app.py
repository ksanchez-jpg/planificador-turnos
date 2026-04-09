import streamlit as st
import math
import pandas as pd
import random
import io

# Configuración de la página
st.set_page_config(page_title="Calculadora de Personal Pro", layout="wide")

st.title("🧮 PROGRAMACIÓN DE PERSONAL")
st.markdown("Genera programación mixta, balance de carga y validación de cumplimiento.")

# -----------------------
# INPUTS (Barra Lateral)
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
# CONSTANTES Y LÓGICA
# -----------------------
SEMANAS = 6
DIAS_TOTALES = SEMANAS * 7
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, SEMANAS+1) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

def generar_programacion_mixta(n_ops, d_req, n_req):
    ops = [f"Op {i+1}" for i in range(n_ops)]

    # ── Patrón base: distribuir días de trabajo con offsets variados ──
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

    # ── Contadores de equidad (se actualizan en tiempo real) ──────────
    noches_acum  = {op: 0 for op in ops}
    dias_acum    = {op: 0 for op in ops}
    trabajo_acum = {op: 0 for op in ops}

    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    for d_idx in range(DIAS_TOTALES):

        # ── FASE 1: pool de trabajadores disponibles ese día ─────────────
        # Candidatos primarios: los que tienen trabajo_base = True ese día
        candidatos = [op for op in ops if trabajo_base[op][d_idx]]

        # Filtrar quien hizo Noche ayer (no puede hacer Día, pero sí Noche)
        hizo_noche_ayer = {
            op for op in ops
            if d_idx > 0 and horario[op][d_idx-1] == TURNO_NOCHE
        }

        # Verificar si hay suficientes para cubrir ambos turnos
        total_req = d_req + n_req
        if len(candidatos) < total_req:
            # Activar reservas: operadores en descanso, ordenados por menor carga
            # en los últimos 7 días y que no hicieron Noche ayer
            en_descanso = [
                op for op in ops
                if not trabajo_base[op][d_idx]
                and op not in hizo_noche_ayer
            ]
            en_descanso.sort(key=lambda x: trabajo_acum[x])
            faltan = total_req - len(candidatos)
            candidatos += en_descanso[:faltan]

        # ── FASE 2: distribuir día/noche con criterio de equidad ─────────
        # Aptos para día: candidatos que NO hicieron Noche ayer
        aptos_dia   = [op for op in candidatos if op not in hizo_noche_ayer]
        # Aptos para noche: todos los candidatos (hacer noche tras noche sí está permitido)
        aptos_noche = list(candidatos)

        # Ordenar aptos_dia: primero quien tiene MÁS noches acumuladas
        # (le "toca" compensar con un día)
        aptos_dia.sort(key=lambda x: -noches_acum[x])

        # Ordenar aptos_noche: primero quien tiene MÁS días acumulados
        # (le "toca" compensar con una noche) — excluyendo a los ya asignados a día
        aptos_noche.sort(key=lambda x: -dias_acum[x])

        asignados_d = []
        asignados_n = []

        # Asignar turno día
        for op in aptos_dia:
            if len(asignados_d) < d_req:
                horario[op][d_idx] = TURNO_DIA
                asignados_d.append(op)
                dias_acum[op]    += 1
                trabajo_acum[op] += 1

        # Asignar turno noche (excluir a los ya en día)
        ya_asignados = set(asignados_d)
        for op in aptos_noche:
            if len(asignados_n) < n_req and op not in ya_asignados:
                horario[op][d_idx] = TURNO_NOCHE
                asignados_n.append(op)
                noches_acum[op]  += 1
                trabajo_acum[op] += 1

        # ── FASE 3: rescate final si aún falta noche ─────────────────────
        deficit_n = n_req - len(asignados_n)
        if deficit_n > 0:
            ya_asignados = set(asignados_d) | set(asignados_n)
            rescate = [
                op for op in ops
                if op not in ya_asignados
                and op not in hizo_noche_ayer
            ]
            rescate.sort(key=lambda x: trabajo_acum[x])
            for op in rescate[:deficit_n]:
                horario[op][d_idx] = TURNO_NOCHE
                noches_acum[op]  += 1
                trabajo_acum[op] += 1

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# -----------------------
# EJECUCIÓN PRINCIPAL
# -----------------------
if st.button("Calcular y Generar Programación"):
    horas_totales_req = (demanda_dia + demanda_noche) * horas_turno * 7
    op_necesarios = math.ceil(((horas_totales_req / horas_promedio_objetivo) * factor_cobertura) / (1 - ausentismo))
    
    st.session_state["op_final"] = op_necesarios
    st.session_state["df_horario"] = generar_programacion_mixta(op_necesarios, demanda_dia, demanda_noche)
    st.session_state["calculado"] = True

if st.session_state.get("calculado"):
    df = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]
    
    # 1. MÉTRICAS PRINCIPALES
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("Operadores Necesarios", op_final)
    with col_m2:
        diferencia = int(op_final - operadores_actuales)
        st.metric("Operadores Faltantes", max(0, diferencia), delta=f"{diferencia}", delta_color="inverse")

    # 2. CUADRANTE DE TURNOS
    st.subheader("📅 Cuadrante de Turnos")
    def color_turnos(val):
        if val == "D": return "background-color: #FFF3CD; color: #856404; font-weight: bold"
        if val == "N": return "background-color: #CCE5FF; color: #004085; font-weight: bold"
        return "background-color: #F8F9FA; color: #ADB5BD"
    st.dataframe(df.style.map(color_turnos), use_container_width=True)

    # 3. BALANCE DE CARGA LABORAL
    st.subheader("📊 Balance de Carga Laboral")
    stats_data = []
    for op in df.index:
        dias_t = (df.loc[op] != DESCANSO).sum()
        noches = (df.loc[op] == TURNO_NOCHE).sum()
        dias_d = (df.loc[op] == TURNO_DIA).sum()
        h_totales = dias_t * horas_turno
        stats_data.append({
            "Operador": op, "Total Días": dias_t, "Día (D)": dias_d, "Noche (N)": noches,
            "Total Horas (6 sem)": h_totales, "Promedio h/sem": round(h_totales / SEMANAS, 2)
        })
    df_stats = pd.DataFrame(stats_data).set_index("Operador")
    
    # Solución al error de Matplotlib: Usamos una función manual para el color
    def resaltar_promedio(val):
        color = "#D4EDDA" if val >= float(horas_promedio_objetivo) else "#F8D7DA"
        return f"background-color: {color}; font-weight: bold"
    
    st.dataframe(df_stats.style.map(resaltar_promedio, subset=["Promedio h/sem"]), use_container_width=True)

    # 4. TABLA DE CUMPLIMIENTO (SOLICITADA)
    st.subheader("✅ Cumplimiento de Personal por Turno")
    cumplimiento = []
    for dia in NOMBRES_DIAS:
        asig_d = (df[dia] == TURNO_DIA).sum()
        asig_n = (df[dia] == TURNO_NOCHE).sum()
        cumplimiento.append({
            "Día": dia,
            "Req. Día": demanda_dia,
            "Asig. Día": asig_d,
            "Cumple Día": "✅ OK" if asig_d >= demanda_dia else "❌ FALTA",
            "Req. Noche": demanda_noche,
            "Asig. Noche": asig_n,
            "Cumple Noche": "✅ OK" if asig_n >= demanda_noche else "❌ FALTA"
        })
    df_cumple = pd.DataFrame(cumplimiento).set_index("Día")
    
    def color_cumplimiento(val):
        if "OK" in str(val): return "color: green; font-weight: bold"
        if "FALTA" in str(val): return "color: red; font-weight: bold"
        return ""
    st.dataframe(df_cumple.style.map(color_cumplimiento), use_container_width=True)

    # 5. EXPORTACIÓN
    st.subheader("📥 Exportar Resultados")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.style.map(color_turnos).to_excel(writer, sheet_name="Cuadrante")
        df_stats.style.map(resaltar_promedio, subset=["Promedio h/sem"]).to_excel(writer, sheet_name="Balance")
        df_cumple.to_excel(writer, sheet_name="Cumplimiento")

    st.download_button(
        label="Descargar Excel Completo",
        data=output.getvalue(),
        file_name="plan_operativo_final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
