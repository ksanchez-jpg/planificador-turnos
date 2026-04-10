import streamlit as st
import math
import pandas as pd
import io
import random

# ─────────────────────────────────────────────
# CONFIGURACIÓN
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
    factor_cobertura   = st.slider("Factor de cobertura",  1.0, 1.5, 1.1, 0.01)
    ausentismo         = st.slider("Ausentismo (%)",       0.0, 0.3, 0.0, 0.01)
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
# Todos suman 11 días → 11×12h = 132h / 3 sem = 44h/sem promedio
ESQUEMAS_BASE = [
    [4, 4, 3],
    [4, 3, 4],
    [3, 4, 4],
]


# ─────────────────────────────────────────────
# PASO 1 — GENERAR DISPONIBILIDAD (42 días continuos)
#
# Reglas que cumple:
#   R2 — 11 días cada 3 semanas (esquemas combinables)
#   R4 — Descansos rotativos (offset diferente cada semana y operador)
#   R5+R6 — Máximo 2 consecutivos contando frontera de semana
# ─────────────────────────────────────────────
def generar_disponibilidad(n_ops: int) -> dict:
    """
    Retorna {op_name: [bool]*42}
    True = disponible (trabaja) ese día.

    Estrategia:
    - Para cada operador construimos un vector de 42 días.
    - Dividimos en 2 ciclos de 3 semanas (semanas 1-3 y 4-6).
    - En cada ciclo de 3 semanas asignamos exactamente 11 días
      siguiendo el esquema elegido para ese operador.
    - Dentro de cada semana del ciclo distribuimos los días de trabajo
      respetando máx 2 consecutivos y verificando la frontera con
      la semana anterior.
    """
    disponibilidad = {}

    for i in range(n_ops):
        nombre = f"Op {i+1}"
        dias = [False] * DIAS_TOTALES

        # Cada operador tiene un esquema base rotado para diversidad
        esquema = ESQUEMAS_BASE[i % len(ESQUEMAS_BASE)]

        # Procesamos semana a semana (0..5), respetando frontera
        consecutivos_previos = 0  # cuántos días True vienen del final de la semana anterior

        for s in range(SEMANAS):
            n_trabajo = esquema[s % 3]
            inicio    = s * 7

            # Construir la semana conociendo cuántos consecutivos
            # vienen de la semana anterior (para R5+R6)
            semana_bool = _construir_semana_continua(
                n_trabajo    = n_trabajo,
                cons_previos = consecutivos_previos,
                offset_base  = (i * 5 + s * 3) % 7   # rotación real por op y semana
            )

            dias[inicio: inicio + 7] = semana_bool

            # Calcular cuántos días True quedan al final de esta semana
            # (para pasarlos a la siguiente como consecutivos_previos)
            consecutivos_previos = _trail_consecutivos(semana_bool)

        disponibilidad[nombre] = dias

    return disponibilidad


def _construir_semana_continua(n_trabajo: int, cons_previos: int, offset_base: int) -> list:
    """
    Construye lista de 7 bools con exactamente n_trabajo True,
    garantizando que:
    - No haya más de 2 True consecutivos en ningún punto.
    - Si cons_previos > 0, los primeros días disponibles respetan
      ese límite de 2 (es decir, si cons_previos == 2 el día 0
      debe ser False).
    - El offset_base rota el patrón de descansos.

    Algoritmo:
    1. Generamos todas las posiciones candidatas (0..6).
    2. Si cons_previos == 2, la posición 0 no puede ser True.
    3. Distribuimos los n_trabajo True evitando rachas > 2,
       usando el offset para rotar el punto de partida.
    """
    MAX_ITER = 200
    mejor = None

    for intento in range(MAX_ITER):
        semana = [False] * 7
        trabajados = 0
        # Orden en que intentamos llenar los días (rotado por offset+intento)
        orden = [(offset_base + intento + d) % 7 for d in range(7)]
        # Eliminamos duplicados manteniendo orden
        orden = list(dict.fromkeys(orden))

        for pos in orden:
            if trabajados >= n_trabajo:
                break
            # Verificar que poner True aquí no viola consecutivos
            semana[pos] = True
            if _max_cons_con_previos(semana, cons_previos if pos == 0 else 0) <= 2:
                # Verificación local: no crear racha > 2 en ningún punto
                if _max_consecutivos(semana) <= 2:
                    # Si es pos 0 y cons_previos == 2, prohibido
                    if pos == 0 and cons_previos >= 2:
                        semana[pos] = False
                        continue
                    trabajados += 1
                else:
                    semana[pos] = False
            else:
                semana[pos] = False

        if semana.count(True) == n_trabajo:
            mejor = semana
            break

    # Fallback: si no se encontró solución perfecta, construir de forma segura
    if mejor is None:
        mejor = _fallback_semana(n_trabajo, cons_previos)

    return mejor


def _fallback_semana(n_trabajo: int, cons_previos: int) -> list:
    """
    Construcción segura y determinista cuando el algoritmo principal falla.
    Coloca días de trabajo en bloques de máx 2 con descanso entre medio.
    """
    semana = [False] * 7
    trabajados = 0
    cons = cons_previos

    for d in range(7):
        if trabajados >= n_trabajo:
            break
        if cons >= 2:
            # Forzar descanso
            cons = 0
        else:
            semana[d] = True
            cons += 1
            trabajados += 1

    return semana


def _max_consecutivos(semana: list) -> int:
    max_r = racha = 0
    for v in semana:
        racha = racha + 1 if v else 0
        max_r = max(max_r, racha)
    return max_r


def _max_cons_con_previos(semana: list, cons_previos: int) -> int:
    """Calcula la racha máxima contando los consecutivos que vienen de antes."""
    max_r = 0
    racha = cons_previos
    for v in semana:
        if v:
            racha += 1
            max_r = max(max_r, racha)
        else:
            racha = 0
    return max_r


def _trail_consecutivos(semana: list) -> int:
    """Cuántos True hay al final de la semana (para pasarlos a la siguiente)."""
    count = 0
    for v in reversed(semana):
        if v:
            count += 1
        else:
            break
    return count


# ─────────────────────────────────────────────
# PASO 2 — ASIGNAR TURNOS D / N
#
# Reglas que cumple:
#   R1 — Cobertura exacta día y noche (sin fallback que viole otras reglas)
#   R3 — Balance D/N por operador (prioridad por desequilibrio acumulado)
#   R5 — No N→D consecutivo
# ─────────────────────────────────────────────
def asignar_turnos(disponibilidad: dict, d_req: int, n_req: int) -> dict:
    """
    Recibe disponibilidad {op: [bool]*42}
    Retorna horario {op: [str]*42} con D, N o R
    """
    ops     = list(disponibilidad.keys())
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    cnt_d   = {op: 0 for op in ops}
    cnt_n   = {op: 0 for op in ops}

    for d_idx in range(DIAS_TOTALES):
        disponibles = [op for op in ops if disponibilidad[op][d_idx]]

        # R5: operadores que vienen de Noche → bloqueados para Día
        bloqueados_d = set()
        if d_idx > 0:
            bloqueados_d = {
                op for op in disponibles
                if horario[op][d_idx - 1] == TURNO_NOCHE
            }

        aptos_d = [op for op in disponibles if op not in bloqueados_d]
        aptos_n = list(disponibles)  # todos los disponibles pueden hacer Noche

        # ── Ordenar para balance R3 ──
        # Para Día: priorizar quien tiene más Noches acumuladas (balance)
        aptos_d.sort(key=lambda op: cnt_d[op] - cnt_n[op])   # menor valor = más N → prioridad en D

        # Para Noche: priorizar quien tiene más Días acumulados
        aptos_n.sort(key=lambda op: cnt_n[op] - cnt_d[op])   # menor valor = más D → prioridad en N

        asignados_d = []
        asignados_n = []

        # ── Asignar Día ──
        for op in aptos_d:
            if len(asignados_d) >= d_req:
                break
            horario[op][d_idx] = TURNO_DIA
            cnt_d[op] += 1
            asignados_d.append(op)

        # ── Asignar Noche (solo entre quienes no fueron a Día) ──
        for op in aptos_n:
            if len(asignados_n) >= n_req:
                break
            if op not in asignados_d:
                horario[op][d_idx] = TURNO_NOCHE
                cnt_n[op] += 1
                asignados_n.append(op)

        # ── Reportar déficit sin violar reglas ──
        # (La validación posterior lo detectará)

    return horario


# ─────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────
def generar_programacion(n_ops: int, d_req: int, n_req: int) -> pd.DataFrame:
    disponibilidad = generar_disponibilidad(n_ops)
    horario        = asignar_turnos(disponibilidad, d_req, n_req)
    df = pd.DataFrame(horario, index=NOMBRES_DIAS).T
    return df


# ─────────────────────────────────────────────
# CÁLCULO DE DOTACIÓN MÍNIMA
# ─────────────────────────────────────────────
def calcular_operadores_necesarios(d_req, n_req, horas_turno, factor_cob, ausentismo):
    # Puestos diarios × horas × 7 días
    horas_semanales_req = (d_req + n_req) * horas_turno * 7
    # Operadores teóricos para cubrir con promedio 44h/sem
    op_teoricos = (horas_semanales_req / 44) * factor_cob / (1 - ausentismo)
    return math.ceil(op_teoricos)


# ─────────────────────────────────────────────
# VALIDACIÓN DE REGLAS
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
        # Verificar que no todas las semanas tienen exactamente los mismos días de descanso
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
# EJECUCIÓN PRINCIPAL
# ─────────────────────────────────────────────
if "calculado" not in st.session_state:
    st.session_state["calculado"] = False

if st.button("⚙️ Calcular y Generar Programación"):
    op_final = calcular_operadores_necesarios(
        demanda_dia, demanda_noche, horas_turno, factor_cobertura, ausentismo
    )
    df_horario = generar_programacion(op_final, demanda_dia, demanda_noche)
    errores    = validar_programacion(df_horario, demanda_dia, demanda_noche, horas_turno)

    st.session_state["op_final"]   = op_final
    st.session_state["df_horario"] = df_horario
    st.session_state["errores"]    = errores
    st.session_state["calculado"]  = True

# ─────────────────────────────────────────────
# RESULTADOS
# ─────────────────────────────────────────────
if st.session_state["calculado"]:
    df       = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]
    errores  = st.session_state["errores"]

    # ── Métricas ──
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

    # ── Cuadrante de Turnos ──
    st.subheader("📅 Cuadrante de Turnos")

    def color_turnos(val):
        if val == "D": return "background-color:#FFF3CD;color:#856404;font-weight:bold"
        if val == "N": return "background-color:#CCE5FF;color:#004085;font-weight:bold"
        return "background-color:#F8F9FA;color:#ADB5BD"

    st.dataframe(df.style.map(color_turnos), use_container_width=True)

    # ── Balance de Carga ──
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

    st.dataframe(
        df_stats.style.map(resaltar_prom, subset=["Prom h/sem"]),
        use_container_width=True
    )

    # ── Cumplimiento por Turno ──
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

    # ── Diagnóstico de Reglas ──
    st.subheader("🔍 Diagnóstico de Reglas")
    if errores:
        # Agrupar por tipo
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

    # ── Exportación ──
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
