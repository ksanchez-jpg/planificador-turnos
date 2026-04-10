import streamlit as st
import math
import pandas as pd
import io
from ortools.sat.python import cp_model

# ─────────────────────────────────────────────
# CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(page_title="Programación de Personal", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; }

.stButton > button {
    background: #0F172A;
    color: #F8FAFC;
    border: none;
    border-radius: 4px;
    padding: 0.6rem 2rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.9rem;
    letter-spacing: 0.05em;
}
.stButton > button:hover { background: #1E3A5F; }

.metric-box {
    background: #0F172A;
    color: #F8FAFC;
    border-radius: 8px;
    padding: 1.2rem 1.5rem;
    text-align: center;
}
.metric-label { font-size: 0.75rem; letter-spacing: 0.1em; color: #94A3B8; text-transform: uppercase; }
.metric-value { font-size: 2rem; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PROGRAMACIÓN DE PERSONAL")
st.caption("Genera cuadrante con balance de carga, cobertura y cumplimiento de reglas.")

# ─────────────────────────────────────────────
# SIDEBAR — PARÁMETROS
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia   = st.number_input("Operadores requeridos (Día)",   min_value=1, value=3)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=3)
    horas_turno   = st.number_input("Horas por turno",               min_value=1, value=12)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura   = st.slider("Factor de cobertura",  1.0, 2.0, 1.2, 0.05)
    ausentismo         = st.slider("Ausentismo (%)",       0.0, 0.3, 0.0, 0.01)
    factor_restric     = st.slider("Factor por restricciones (R5/R6)", 1.0, 1.5, 1.15, 0.01,
                                   help="Compensa la pérdida de flexibilidad por máximo 2 días seguidos y transiciones prohibidas")
    operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=6)

# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────
SEMANAS      = 6
DIAS_TOTALES = SEMANAS * 7          # 42 días continuos
TURNO_DIA    = "D"
TURNO_NOCHE  = "N"
DESCANSO     = "R"

NOMBRES_DIAS = [
    f"S{s}-{d}"
    for s in range(1, SEMANAS + 1)
    for d in ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
]

# Esquemas base (días trabajados por semana en ciclo de 3 semanas)
ESQUEMAS_BASE = [
    [4, 4, 3],
    [4, 3, 4],
    [3, 4, 4],
]


# ─────────────────────────────────────────────
# CÁLCULO DE DOTACIÓN MÍNIMA (MEJORADO)
# ─────────────────────────────────────────────
def calcular_operadores_necesarios(d_req, n_req, horas_turno, factor_cob, ausentismo, factor_rest):
    """
    Calcula el número mínimo de operadores para cubrir la demanda,
    teniendo en cuenta:
      - horas semanales requeridas
      - promedio 44h/sem por operador
      - factor de cobertura
      - ausentismo
      - factor adicional por restricciones (máx 2 días, transiciones)
    """
    puestos_diarios = d_req + n_req
    horas_semanales_req = puestos_diarios * horas_turno * 7
    # Operadores teóricos si no hubiera restricciones
    op_teoricos = horas_semanales_req / 44.0
    # Aplicamos todos los factores
    op_ajustados = op_teoricos * factor_cob / (1 - ausentismo) * factor_rest
    return math.ceil(op_ajustados)


# ─────────────────────────────────────────────
# PROGRAMACIÓN CON OR-TOOLS (CP-SAT)
# ─────────────────────────────────────────────
def programar_con_ortools(num_operadores, d_req, n_req):
    """
    Construye y resuelve el modelo de programación de turnos para 6 semanas (42 días).
    Retorna:
      - df: DataFrame con el cuadrante (si hay solución)
      - status: string con el resultado ('OPTIMAL', 'FEASIBLE', 'INFEASIBLE')
      - infeasible_details: lista de restricciones conflictivas (si aplica)
    """
    dias_totales = DIAS_TOTALES
    operadores = range(num_operadores)
    dias = range(dias_totales)
    turnos = ['D', 'N']

    model = cp_model.CpModel()

    # Variables de decisión
    x = {}
    for i in operadores:
        for d in dias:
            for t in turnos:
                x[i, d, t] = model.NewBoolVar(f'x_{i}_{d}_{t}')

    # Restricción: máximo un turno por día
    for i in operadores:
        for d in dias:
            model.Add(sum(x[i, d, t] for t in turnos) <= 1)

    # R1: Demanda exacta por día y turno
    for d in dias:
        model.Add(sum(x[i, d, 'D'] for i in operadores) == d_req)
        model.Add(sum(x[i, d, 'N'] for i in operadores) == n_req)

    # R5 + R6: Máximo 2 días consecutivos trabajados (cualquier turno)
    for i in operadores:
        for d in range(dias_totales - 2):
            model.Add(
                sum(x[i, d + k, t] for k in range(3) for t in turnos) <= 2
            )

    # R5: Prohibido Noche -> Día siguiente
    for i in operadores:
        for d in range(dias_totales - 1):
            model.Add(x[i, d, 'N'] + x[i, d + 1, 'D'] <= 1)

    # R2: 11 días trabajados en cada bloque de 3 semanas (21 días)
    bloques = [(0, 21), (21, 42)]
    for i in operadores:
        for inicio, fin in bloques:
            model.Add(
                sum(x[i, d, t] for d in range(inicio, fin) for t in turnos) == 11
            )

    # R2 (distribución semanal): 4,4,3 en cada bloque
    for i in operadores:
        for b_idx, (inicio, fin) in enumerate(bloques):
            for s in range(3):
                semana_inicio = inicio + s * 7
                semana_fin = semana_inicio + 7
                trab_sem = model.NewIntVar(3, 4, f'trab_sem_{i}_{b_idx}_{s}')
                model.Add(
                    sum(x[i, d, t] for d in range(semana_inicio, semana_fin) for t in turnos)
                    == trab_sem
                )

    # R3 (blanda): Balance día/noche
    total_D = {i: sum(x[i, d, 'D'] for d in dias) for i in operadores}
    total_N = {i: sum(x[i, d, 'N'] for d in dias) for i in operadores}
    diff_vars = []
    for i in operadores:
        diff = model.NewIntVar(0, dias_totales, f'diff_{i}')
        model.AddAbsEquality(diff, total_D[i] - total_N[i])
        diff_vars.append(diff)

    # R4 (blanda simplificada): penalizar que un operador tenga exactamente
    # los mismos días de descanso en todas las semanas (no implementada aquí)

    # Objetivo: minimizar suma de diferencias D/N
    model.Minimize(sum(diff_vars))

    # Parámetros del solver
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    solver.parameters.log_search_progress = False  # cambiar a True para depuración local

    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Construir DataFrame
        horario = {}
        for i in operadores:
            fila = []
            for d in dias:
                if solver.Value(x[i, d, 'D']) == 1:
                    fila.append(TURNO_DIA)
                elif solver.Value(x[i, d, 'N']) == 1:
                    fila.append(TURNO_NOCHE)
                else:
                    fila.append(DESCANSO)
            horario[f'Op {i+1}'] = fila
        df = pd.DataFrame(horario, index=NOMBRES_DIAS).T
        return df, "OPTIMAL", None
    else:
        # Si es INFEASIBLE, intentamos identificar restricciones conflictivas
        return None, "INFEASIBLE", ["El modelo no tiene solución con estos parámetros."]


# ─────────────────────────────────────────────
# VALIDACIÓN DE REGLAS (la misma que tenías)
# ─────────────────────────────────────────────
def validar_programacion(df: pd.DataFrame, d_req: int, n_req: int, horas_turno: int) -> list:
    errores = []

    # R1 — Cobertura
    for dia in NOMBRES_DIAS:
        asig_d = (df[dia] == TURNO_DIA).sum()
        asig_n = (df[dia] == TURNO_NOCHE).sum()
        if asig_d < d_req:
            errores.append(f"❌ R1 — {dia}: faltan {d_req - asig_d} operador(es) en turno Día")
        if asig_n < n_req:
            errores.append(f"❌ R1 — {dia}: faltan {n_req - asig_n} operador(es) en turno Noche")

    for op in df.index:
        fila = df.loc[op].tolist()

        # R2 — Horas promedio en ciclos de 3 semanas
        for ciclo_inicio in range(0, SEMANAS, 3):
            dias_ciclo = fila[ciclo_inicio*7 : (ciclo_inicio+3)*7]
            trabajados = sum(1 for v in dias_ciclo if v != DESCANSO)
            if trabajados != 11:
                errores.append(
                    f"⚠️ R2 — {op} semanas {ciclo_inicio+1}-{ciclo_inicio+3}: "
                    f"{trabajados} días trabajados (esperado 11)"
                )

        # R4 — Descansos no siempre en los mismos días
        descansos_por_semana = []
        for s in range(SEMANAS):
            dias_sem = fila[s*7:(s+1)*7]
            desc_sem = frozenset(d for d, v in enumerate(dias_sem) if v == DESCANSO)
            descansos_por_semana.append(desc_sem)
        if len(set(descansos_por_semana)) == 1:
            errores.append(f"⚠️ R4 — {op}: los descansos son idénticos todas las semanas")

        # R5+R6 — Máximo 2 consecutivos (continuo entre semanas)
        racha = 0
        for d_idx, val in enumerate(fila):
            if val != DESCANSO:
                racha += 1
                if racha > 2:
                    sem = d_idx // 7 + 1
                    errores.append(
                        f"❌ R5/R6 — {op}: más de 2 turnos consecutivos "
                        f"(día {d_idx+1}, semana {sem})"
                    )
                    break
            else:
                racha = 0

        # R5 — N→D prohibido
        for d_idx in range(1, DIAS_TOTALES):
            if fila[d_idx-1] == TURNO_NOCHE and fila[d_idx] == TURNO_DIA:
                errores.append(
                    f"❌ R5 — {op}: cambio N→D en día {d_idx+1} "
                    f"(semana {d_idx//7+1})"
                )
                break

    return errores


# ─────────────────────────────────────────────
# INTERFAZ PRINCIPAL
# ─────────────────────────────────────────────
if "calculado" not in st.session_state:
    st.session_state["calculado"] = False

if st.button("⚙️ Calcular y Generar Programación"):
    # 1. Calcular operadores necesarios
    op_necesarios = calcular_operadores_necesarios(
        demanda_dia, demanda_noche, horas_turno,
        factor_cobertura, ausentismo, factor_restric
    )
    st.session_state["op_calculado"] = op_necesarios

    # 2. Intentar resolver con OR-Tools
    with st.spinner("🔄 Resolviendo modelo de programación (puede tardar hasta 60 segundos)..."):
        df, status, detalles = programar_con_ortools(op_necesarios, demanda_dia, demanda_noche)

    if df is not None:
        # Validar resultado
        errores = validar_programacion(df, demanda_dia, demanda_noche, horas_turno)
        st.session_state["df_horario"] = df
        st.session_state["errores"] = errores
        st.session_state["status"] = status
        st.session_state["calculado"] = True
        st.success(f"✅ Solución encontrada ({status})")
    else:
        st.error("❌ No se pudo encontrar una solución factible con los parámetros actuales.")
        st.info("💡 Sugerencias:\n"
                "- Aumenta el **Factor de cobertura** o el **Factor por restricciones**.\n"
                "- Reduce la demanda de turnos (si es posible).\n"
                "- Aumenta manualmente el número de operadores actuales (el cálculo automático puede quedarse corto).")
        st.session_state["calculado"] = False

# ─────────────────────────────────────────────
# MOSTRAR RESULTADOS SI EXISTEN
# ─────────────────────────────────────────────
if st.session_state.get("calculado", False):
    df       = st.session_state["df_horario"]
    op_final = st.session_state["op_calculado"]
    errores  = st.session_state["errores"]

    # Métricas
    diferencia = int(op_final - operadores_actuales)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">Operadores Necesarios</div>
            <div class="metric-value">{op_final}</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        faltantes = max(0, diferencia)
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">Operadores Faltantes</div>
            <div class="metric-value" style="color:{'#F87171' if faltantes > 0 else '#4ADE80'}">{faltantes}</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        errores_r1 = sum(1 for e in errores if "R1" in e)
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">Errores de Cobertura</div>
            <div class="metric-value" style="color:{'#F87171' if errores_r1 > 0 else '#4ADE80'}">{errores_r1}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Cuadrante
    st.subheader("📅 Cuadrante de Turnos")
    def color_turnos(val):
        if val == "D": return "background-color:#FFF3CD;color:#856404;font-weight:bold"
        if val == "N": return "background-color:#CCE5FF;color:#004085;font-weight:bold"
        return "background-color:#F8F9FA;color:#ADB5BD"
    st.dataframe(df.style.map(color_turnos), use_container_width=True)

    # Balance de carga
    st.subheader("📊 Balance de Carga Laboral")
    stats = []
    for op in df.index:
        dias_t  = (df.loc[op] != DESCANSO).sum()
        dias_d  = (df.loc[op] == TURNO_DIA).sum()
        noches  = (df.loc[op] == TURNO_NOCHE).sum()
        h_total = dias_t * horas_turno
        prom    = round(h_total / SEMANAS, 2)
        stats.append({
            "Operador":           op,
            "Total Días":         dias_t,
            "Día (D)":            dias_d,
            "Noche (N)":          noches,
            "Total Horas (6sem)": h_total,
            "Prom h/sem":         prom,
            "Balance D/N":        f"{dias_d}D / {noches}N"
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    def resaltar_prom(val):
        try:
            ok = 42 <= float(val) <= 46
            return f"background-color:{'#D4EDDA' if ok else '#F8D7DA'};font-weight:bold"
        except:
            return ""
    st.dataframe(df_stats.style.map(resaltar_prom, subset=["Prom h/sem"]), use_container_width=True)

    # Cumplimiento por turno
    st.subheader("✅ Cumplimiento de Personal por Turno")
    cumplimiento = []
    for dia in NOMBRES_DIAS:
        asig_d = (df[dia] == TURNO_DIA).sum()
        asig_n = (df[dia] == TURNO_NOCHE).sum()
        cumplimiento.append({
            "Día":          dia,
            "Req. D":       demanda_dia,
            "Asig. D":      asig_d,
            "Cumple D":     "✅ OK" if asig_d >= demanda_dia else "❌ FALTA",
            "Req. N":       demanda_noche,
            "Asig. N":      asig_n,
            "Cumple N":     "✅ OK" if asig_n >= demanda_noche else "❌ FALTA",
        })
    df_cumple = pd.DataFrame(cumplimiento).set_index("Día")
    def color_cumple(val):
        if "OK"    in str(val): return "color:green;font-weight:bold"
        if "FALTA" in str(val): return "color:red;font-weight:bold"
        return ""
    st.dataframe(df_cumple.style.map(color_cumple), use_container_width=True)

    # Diagnóstico de reglas
    st.subheader("🔍 Diagnóstico de Reglas")
    if errores:
        r1 = [e for e in errores if "R1" in e]
        r2 = [e for e in errores if "R2" in e]
        r4 = [e for e in errores if "R4" in e]
        r5 = [e for e in errores if "R5" in e or "R6" in e]
        if r1:
            st.error(f"**Regla 1 — Cobertura:** {len(r1)} incumplimiento(s)")
            with st.expander("Ver detalle R1"):
                for e in r1: st.write(e)
        if r2:
            st.warning(f"**Regla 2 — Horas:** {len(r2)} incumplimiento(s)")
            with st.expander("Ver detalle R2"):
                for e in r2: st.write(e)
        if r4:
            st.warning(f"**Regla 4 — Descansos rotativos:** {len(r4)} incumplimiento(s)")
            with st.expander("Ver detalle R4"):
                for e in r4: st.write(e)
        if r5:
            st.error(f"**Regla 5/6 — Consecutivos / N→D:** {len(r5)} incumplimiento(s)")
            with st.expander("Ver detalle R5/R6"):
                for e in r5: st.write(e)
    else:
        st.success("✅ Todas las reglas se cumplen correctamente.")

    # Exportación
    st.subheader("📥 Exportar Resultados")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Cuadrante")
        df_stats.to_excel(writer, sheet_name="Balance")
        df_cumple.to_excel(writer, sheet_name="Cumplimiento")
    st.download_button(
        label="⬇️ Descargar Excel Completo",
        data=output.getvalue(),
        file_name="programacion_personal.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
