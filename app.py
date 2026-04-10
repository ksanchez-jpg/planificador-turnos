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
# CONSTANTES
# -----------------------
SEMANAS = 6
DIAS_TOTALES = SEMANAS * 7
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, SEMANAS + 1)
                for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# Esquemas posibles: días trabajados por semana en ciclo de 3 semanas
# Cada esquema suma 11 días en 3 semanas → 132h / 3sem = 44h/sem promedio
ESQUEMAS = [
    [4, 4, 3],
    [4, 3, 4],
    [3, 4, 4],
]


# -----------------------
# PASO 1: GENERAR DISPONIBILIDAD
# Determina qué días trabaja cada operador respetando:
#   - Esquema 4-4-3 / 4-3-4 / 3-4-4 (rotativos entre operadores)
#   - Máximo 2 días consecutivos trabajados (Regla 5)
#   - Descansos rotativos semana a semana (Regla 4)
# -----------------------
def generar_disponibilidad(n_ops):
    """
    Retorna un dict {op: [bool]*DIAS_TOTALES}
    True = el operador está disponible (trabaja) ese día.
    """
    disponibilidad = {}

    for i in range(n_ops):
        esquema_base = ESQUEMAS[i % len(ESQUEMAS)]
        # Offset rotativo del día libre cambia cada semana y por operador
        # Esto garantiza que los descansos no sean siempre los mismos días
        dias = []

        for s in range(SEMANAS):
            # Cuántos días trabaja esta semana según el esquema (ciclo de 3 semanas)
            n_trabajo = esquema_base[s % 3]
            n_descanso = 7 - n_trabajo

            # El offset del primer descanso rota por semana y por operador
            # Usamos (i * 3 + s * 2) % 7 para garantizar rotación real
            offset_desc = (i * 3 + s * 2) % 7

            # Construir máscara semanal respetando máximo 2 consecutivos
            semana = _construir_semana(n_trabajo, offset_desc)
            dias.extend(semana)

        disponibilidad[f"Op {i+1}"] = dias

    return disponibilidad


def _construir_semana(n_trabajo, offset_desc):
    """
    Construye una semana de 7 días con n_trabajo días True,
    garantizando que no haya más de 2 días True consecutivos.
    El offset determina desde qué posición empiezan los descansos.
    """
    # Posiciones de descanso distribuidas con el offset
    n_descanso = 7 - n_trabajo
    descansos = set()

    for k in range(n_descanso):
        pos = (offset_desc + k * (7 // max(n_descanso, 1))) % 7
        descansos.add(pos)

    # Si por redondeo no alcanzamos los descansos necesarios, completar
    pos = 0
    while len(descansos) < n_descanso:
        if pos not in descansos:
            descansos.add(pos)
        pos = (pos + 1) % 7

    semana = [i not in descansos for i in range(7)]

    # Verificar y corregir consecutivos > 2
    semana = _corregir_consecutivos(semana)
    return semana


def _corregir_consecutivos(semana):
    """
    Si hay 3 o más días True consecutivos, mueve un día True a un gap
    de descanso para no superar el límite de 2 consecutivos (Regla 5).
    Opera sobre lista de 7 bools, retorna lista corregida.
    """
    semana = semana[:]
    max_iter = 20
    for _ in range(max_iter):
        racha = 0
        pos_quitar = -1
        for d in range(7):
            if semana[d]:
                racha += 1
                if racha == 3:
                    pos_quitar = d  # tercer consecutivo
                    break
            else:
                racha = 0

        if pos_quitar == -1:
            break  # sin rachas de 3, ok

        # Mover ese día a un descanso que no genere nueva racha
        semana[pos_quitar] = False
        for candidato in range(7):
            if not semana[candidato]:
                # Verificar que poner True aquí no genera racha de 3
                semana[candidato] = True
                if _max_consecutivos(semana) <= 2:
                    break
                semana[candidato] = False  # revertir y probar otro

    return semana


def _max_consecutivos(semana):
    max_r = racha = 0
    for v in semana:
        racha = racha + 1 if v else 0
        max_r = max(max_r, racha)
    return max_r


# -----------------------
# PASO 2: ASIGNAR TURNOS D / N
# Respeta:
#   - Cobertura exacta demanda_dia y demanda_noche (Regla 1)
#   - No N→D consecutivo (Regla 6)
#   - Balance D/N por operador lo más equilibrado posible (Regla 3)
# -----------------------
def asignar_turnos(disponibilidad, d_req, n_req):
    """
    Recibe disponibilidad {op: [bool]*DIAS_TOTALES}
    Retorna horario {op: [str]*DIAS_TOTALES} con D, N o R
    """
    ops = list(disponibilidad.keys())
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    # Contadores de balance D/N por operador
    conteo_d = {op: 0 for op in ops}
    conteo_n = {op: 0 for op in ops}

    for d_idx in range(DIAS_TOTALES):
        disponibles = [op for op in ops if disponibilidad[op][d_idx]]

        # Regla 6: operadores que NO pueden hacer día (vienen de noche el día anterior)
        bloqueados_para_d = set()
        if d_idx > 0:
            bloqueados_para_d = {op for op in disponibles
                                  if horario[op][d_idx - 1] == TURNO_NOCHE}

        aptos_d = [op for op in disponibles if op not in bloqueados_para_d]
        aptos_n = disponibles  # todos los disponibles pueden hacer noche

        # Ordenar aptos_d priorizando quien tenga más N acumuladas (balance Regla 3)
        aptos_d.sort(key=lambda op: (conteo_d[op] - conteo_n[op]))  # más negativo = más noches → prioridad en día

        # Ordenar aptos_n priorizando quien tenga más D acumuladas
        aptos_n_ordenados = sorted(aptos_n, key=lambda op: (conteo_n[op] - conteo_d[op]))

        asignados_d = []
        asignados_n = []

        # ── Asignar turno DÍA ──
        for op in aptos_d:
            if len(asignados_d) >= d_req:
                break
            if op not in asignados_n:
                horario[op][d_idx] = TURNO_DIA
                conteo_d[op] += 1
                asignados_d.append(op)

        # Si no hay suficientes aptos para día, completar con disponibles (aunque vengan de noche)
        # Solo como fallback de último recurso para no violar Regla 1
        if len(asignados_d) < d_req:
            for op in disponibles:
                if len(asignados_d) >= d_req:
                    break
                if op not in asignados_d and op not in asignados_n:
                    horario[op][d_idx] = TURNO_DIA
                    conteo_d[op] += 1
                    asignados_d.append(op)

        # ── Asignar turno NOCHE ──
        for op in aptos_n_ordenados:
            if len(asignados_n) >= n_req:
                break
            if op not in asignados_d:
                horario[op][d_idx] = TURNO_NOCHE
                conteo_n[op] += 1
                asignados_n.append(op)

        # Fallback noche
        if len(asignados_n) < n_req:
            for op in disponibles:
                if len(asignados_n) >= n_req:
                    break
                if op not in asignados_d and op not in asignados_n:
                    horario[op][d_idx] = TURNO_NOCHE
                    conteo_n[op] += 1
                    asignados_n.append(op)

    return horario


# -----------------------
# FUNCIÓN PRINCIPAL
# -----------------------
def generar_programacion(n_ops, d_req, n_req):
    disponibilidad = generar_disponibilidad(n_ops)
    horario = asignar_turnos(disponibilidad, d_req, n_req)
    df = pd.DataFrame(horario, index=NOMBRES_DIAS).T
    return df


# -----------------------
# EJECUCIÓN PRINCIPAL
# -----------------------
if st.button("Calcular y Generar Programación"):
    horas_totales_req = (demanda_dia + demanda_noche) * horas_turno * 7
    op_necesarios = math.ceil(
        ((horas_totales_req / horas_promedio_objetivo) * factor_cobertura) / (1 - ausentismo)
    )

    st.session_state["op_final"] = op_necesarios
    st.session_state["df_horario"] = generar_programacion(op_necesarios, demanda_dia, demanda_noche)
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
        st.metric("Operadores Faltantes", max(0, diferencia),
                  delta=f"{diferencia}", delta_color="inverse")

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
            "Operador": op,
            "Total Días": dias_t,
            "Día (D)": dias_d,
            "Noche (N)": noches,
            "Total Horas (6 sem)": h_totales,
            "Promedio h/sem": round(h_totales / SEMANAS, 2)
        })
    df_stats = pd.DataFrame(stats_data).set_index("Operador")

    def resaltar_promedio(val):
        color = "#D4EDDA" if val >= float(horas_promedio_objetivo) else "#F8D7DA"
        return f"background-color: {color}; font-weight: bold"

    st.dataframe(df_stats.style.map(resaltar_promedio, subset=["Promedio h/sem"]),
                 use_container_width=True)

    # 4. TABLA DE CUMPLIMIENTO
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

    # 5. VALIDACIÓN DE REGLAS (diagnóstico visual)
    st.subheader("🔍 Diagnóstico de Reglas")
    errores = []

    for dia_idx, dia in enumerate(NOMBRES_DIAS):
        asig_d = (df[dia] == TURNO_DIA).sum()
        asig_n = (df[dia] == TURNO_NOCHE).sum()
        if asig_d < demanda_dia:
            errores.append(f"❌ R1 — {dia}: faltan {demanda_dia - asig_d} en turno Día")
        if asig_n < demanda_noche:
            errores.append(f"❌ R1 — {dia}: faltan {demanda_noche - asig_n} en turno Noche")

    for op in df.index:
        fila = df.loc[op].tolist()
        # Regla 5: no más de 2 consecutivos
        racha = 0
        for v in fila:
            racha = racha + 1 if v != DESCANSO else 0
            if racha > 2:
                errores.append(f"❌ R5 — {op}: más de 2 turnos consecutivos")
                break
        # Regla 6: no N→D consecutivo
        for d in range(1, DIAS_TOTALES):
            if fila[d - 1] == TURNO_NOCHE and fila[d] == TURNO_DIA:
                errores.append(f"❌ R6 — {op}: turno N→D consecutivo en día {d}")
                break

    if errores:
        for e in errores:
            st.warning(e)
    else:
        st.success("✅ Todas las reglas se cumplen correctamente.")

    # 6. EXPORTACIÓN
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
