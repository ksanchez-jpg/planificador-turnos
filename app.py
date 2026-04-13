import streamlit as st
import math
import pandas as pd
import io
import random
 
# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Programación de Turnos 44H", layout="wide")
 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.metric-box-green { background: #10B981; color: #064E3B; border-radius: 8px; padding: 1.2rem; text-align: center; }
.metric-value-dark { font-size: 2.2rem; font-family: 'IBM Plex Mono', monospace; font-weight: 700; }
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; width: 100%; }
</style>
""", unsafe_allow_html=True)
 
st.title("🗓 PROGRAMACIÓN DE TURNOS")
st.caption("Objetivo: 132h por ciclo, Mín 3 días/semana, bloques mín. 2 días y máx 1 refuerzo.")
 
# 2. SIDEBAR - PARÁMETROS
with st.sidebar:
    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value="Cosechador")
    
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input(f"{cargo} requerido (Día)", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} requerido (Noche)", min_value=1, value=5)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)
 
    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input(f"{cargo} actual (Nómina)", min_value=0, value=20)
 
# 3. CONSTANTES
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]
 
# ─────────────────────────────────────────────────────────────
# 4. MOTOR CORREGIDO
# Reglas duras (igual que el original):
#   R1. Exactamente 11 turnos por bloque de 21 días (44h/sem promedio)
#   R2. Mínimo 3 turnos por semana (semanas de 7 días dentro del bloque)
#   R3. NUNCA asignar Día justo después de Noche (N→D prohibido)
#   R4. Refuerzo máximo +1 sobre la demanda de Día
#
# Nuevo:
#   R5. Cada operador recibe un patrón preferente (DD / NN / DN) que rota
#       entre bloque 1 y bloque 2, garantizando variedad en transiciones.
#       El patrón es una PREFERENCIA, nunca rompe R1-R4.
# ─────────────────────────────────────────────────────────────
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}
 
    # Patrón preferente por operador y bloque (rota entre bloques)
    PATRONES = ["DD", "NN", "DN"]
    patron = {}
    for i, op in enumerate(ops):
        patron[(op, 0)]  = PATRONES[i % 3]
        patron[(op, 21)] = PATRONES[(i + 1) % 3]   # rota en el segundo bloque
 
    def hizo_noche_ayer(op, d, bloque_idx):
        """True si el día anterior (dentro del bloque) fue Noche."""
        return d > bloque_idx and horario[op][d - 1] == TURNO_NOCHE
 
    def turno_preferido(op, d, bloque_idx, pos_laboral):
        """
        Devuelve el turno que el patrón del operador prefiere para este día.
        pos_laboral = contador de días laborables ya procesados en el bloque.
          DD → siempre Día
          NN → siempre Noche
          DN → alterna: posición par→Día, posición impar→Noche
        """
        pat = patron[(op, bloque_idx)]
        if pat == "DD":
            return TURNO_DIA
        elif pat == "NN":
            return TURNO_NOCHE
        else:  # DN
            return TURNO_DIA if pos_laboral % 2 == 0 else TURNO_NOCHE
 
    for bloque_idx in [0, 21]:
        bloque_dias = [d for d in range(bloque_idx, bloque_idx + 21)
                       if (d % 7) < d_semana]
 
        turnos_totales   = {op: 0 for op in ops}
        turnos_semanales = {op: [0, 0, 0] for op in ops}
        # Contador de días laborables procesados (para función DN)
        pos_laboral_bloque = 0
 
        # ── FASE 1: ASIGNACIÓN BASE ──────────────────────────────────────
        for d in range(bloque_idx, bloque_idx + 21):
            if (d % 7) >= d_semana:
                continue
 
            semana_rel = (d - bloque_idx) // 7
 
            # Operadores aptos: menos de 11 turnos en el bloque,
            # menos de 5 en la semana, y NO hicieron noche ayer (R3)
            def es_apto(op):
                return (turnos_totales[op] < 11
                        and turnos_semanales[op][semana_rel] < 5
                        and not hizo_noche_ayer(op, d, bloque_idx))
 
            # Operadores obligados a trabajar hoy (bloque mínimo 2 días):
            # trabajaron ayer y fue su primer día de racha
            obligados = []
            for op in ops:
                if (d > bloque_idx
                        and horario[op][d - 1] != DESCANSO
                        and (d - 1 == bloque_idx or horario[op][d - 2] == DESCANSO)
                        and turnos_totales[op] < 11
                        and turnos_semanales[op][semana_rel] < 5
                        and not hizo_noche_ayer(op, d, bloque_idx)):
                    obligados.append(op)
 
            aptos = [op for op in ops if es_apto(op)]
 
            # Clasificar aptos según preferencia y disponibilidad
            pref_n = [op for op in aptos if turno_preferido(op, d, bloque_idx, pos_laboral_bloque) == TURNO_NOCHE]
            pref_d = [op for op in aptos if turno_preferido(op, d, bloque_idx, pos_laboral_bloque) == TURNO_DIA]
 
            # Ordenar: obligados primero, luego menor carga, luego balance noches
            def orden_n(op):
                return (op not in obligados, turnos_totales[op], noches_acum[op], random.random())
            def orden_d(op):
                return (op not in obligados, turnos_totales[op], -noches_acum[op], random.random())
 
            pref_n.sort(key=orden_n)
            pref_d.sort(key=orden_d)
 
            # Si no hay suficientes preferentes, completar desde el otro grupo
            # (nunca se viola R3 porque es_apto ya lo filtra)
            def completar_con_resto(lista, excluidos, cuota, orden_fn):
                if len(lista) >= cuota:
                    return lista[:cuota]
                resto = [op for op in aptos if op not in excluidos and op not in lista]
                resto.sort(key=orden_fn)
                return (lista + resto)[:cuota]
 
            asignados_n = completar_con_resto(pref_n, set(), n_req, orden_n)
            ya_asignados = set(asignados_n)
            asignados_d = completar_con_resto(pref_d, ya_asignados, d_req, orden_d)
 
            # Aplicar asignaciones
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_totales[op] += 1
                turnos_semanales[op][semana_rel] += 1
                noches_acum[op] += 1
 
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_totales[op] += 1
                turnos_semanales[op][semana_rel] += 1
 
            pos_laboral_bloque += 1
 
        # ── FASE 2: AJUSTE MÍNIMO 3 DÍAS / SEMANA ────────────────────────
        # Si algún operador tiene menos de 3 en una semana, añadir Día
        # en un hueco válido (R3, R4 respetados)
        for op in ops:
            for s in range(3):
                dias_semana = [d for d in range(bloque_idx + s * 7, bloque_idx + (s + 1) * 7)
                               if (d % 7) < d_semana]
                intentos = list(dias_semana)
                random.shuffle(intentos)
 
                while turnos_semanales[op][s] < 3 and turnos_totales[op] < 11:
                    exito = False
                    for d_aj in intentos:
                        if horario[op][d_aj] != DESCANSO:
                            continue
                        if hizo_noche_ayer(op, d_aj, bloque_idx):   # R3
                            continue
                        # R4: no superar demanda + 1 refuerzo en turno Día
                        ocupacion_dia = sum(1 for o in ops if horario[o][d_aj] == TURNO_DIA)
                        if ocupacion_dia >= d_req + 1:
                            continue
                        horario[op][d_aj] = TURNO_DIA
                        turnos_totales[op] += 1
                        turnos_semanales[op][s] += 1
                        exito = True
                        break
                    if not exito:
                        break   # no hay hueco válido, pasar a la siguiente semana
 
        # ── FASE 3: RELLENO HASTA 11 TURNOS (R1) ────────────────────────
        for op in ops:
            intentos = 0
            while turnos_totales[op] < 11 and intentos < 400:
                intentos += 1
                d_rand = random.choice(bloque_dias)
                s_rand = (d_rand - bloque_idx) // 7
                if horario[op][d_rand] != DESCANSO:
                    continue
                if turnos_semanales[op][s_rand] >= 5:
                    continue
                if hizo_noche_ayer(op, d_rand, bloque_idx):          # R3
                    continue
                ocupacion_dia = sum(1 for o in ops if horario[o][d_rand] == TURNO_DIA)
                if ocupacion_dia >= d_req + 1:                        # R4
                    continue
                horario[op][d_rand] = TURNO_DIA
                turnos_totales[op] += 1
                turnos_semanales[op][s_rand] += 1
 
    return pd.DataFrame(horario, index=NOMBRES_DIAS).T
 
 
# 5. EJECUCIÓN
if st.button(f"🚀 Generar Programación para {cargo}"):
    op_base  = math.ceil(((demanda_dia + demanda_noche) * dias_cubrir * 3) / 11)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2)
 
    st.session_state["df"]       = generar_programacion_equitativa(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final
 
 
# 6. RENDERIZADO
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)
 
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">{cargo} requerido</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Contratar</div><div class="metric-value-dark">{faltantes}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Meta Horas</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)
 
    st.subheader("📅 Programación del Personal")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)
 
    st.subheader(f"📊 Balance Detallado: {cargo}")
    stats = []
    for op in df.index:
        fila   = df.loc[op]
        c1_t   = sum(1 for x in fila[:21] if x != DESCANSO)
        c2_t   = sum(1 for x in fila[21:] if x != DESCANSO)
 
        def get_seq(data):
            return (f"{sum(1 for x in data[0:7]  if x != DESCANSO)}-"
                    f"{sum(1 for x in data[7:14] if x != DESCANSO)}-"
                    f"{sum(1 for x in data[14:21] if x != DESCANSO)}")
 
        def contar_trans(fila_op):
            dd = nn = dn = nd_bad = 0
            vals = list(fila_op)
            for i in range(len(vals) - 1):
                a, b = vals[i], vals[i+1]
                if   a == "D" and b == "D": dd += 1
                elif a == "N" and b == "N": nn += 1
                elif a == "D" and b == "N": dn += 1
                elif a == "N" and b == "D": nd_bad += 1   # debe ser 0
            return dd, nn, dn, nd_bad
 
        t_dd, t_nn, t_dn, t_nd = contar_trans(fila)
        horas_s13 = c1_t * horas_turno
        horas_s46 = c2_t * horas_turno
 
        # Verificar mínimo 3 días por semana en cada semana
        min3_ok = all(
            sum(1 for x in list(fila)[s*7:(s+1)*7] if x != DESCANSO) >= 3
            for s in range(6)
            if dias_cubrir == 7   # solo validar si cubre 7 días
        )
 
        estado = "✅ OK" if (c1_t == 11 and c2_t == 11 and t_nd == 0 and min3_ok) else "❌ Revisar"
 
        stats.append({
            "Operador": op,
            "T. Día": (fila == TURNO_DIA).sum(),
            "T. Noche": (fila == TURNO_NOCHE).sum(),
            "Horas S1-3": horas_s13,
            "Secuencia S1-3": get_seq(list(fila)[:21]),
            "Horas S4-6": horas_s46,
            "Secuencia S4-6": get_seq(list(fila)[21:]),
            "DD": t_dd, "NN": t_nn, "DN": t_dn,
            "N→D (!!!)": t_nd,
            "Estado": estado,
        })
 
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)
 
    # Resumen global de transiciones
    st.subheader("🔄 Balance Global de Transiciones")
    tot_dd = int(df_stats["DD"].sum())
    tot_nn = int(df_stats["NN"].sum())
    tot_dn = int(df_stats["DN"].sum())
    tot_nd = int(df_stats["N→D (!!!)"].sum())
    total  = tot_dd + tot_nn + tot_dn + tot_nd or 1
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("DD (Día→Día)",    tot_dd, f"{tot_dd/total*100:.1f}%")
    col2.metric("NN (Noche→Noche)", tot_nn, f"{tot_nn/total*100:.1f}%")
    col3.metric("DN (Día→Noche)",  tot_dn, f"{tot_dn/total*100:.1f}%")
    col4.metric("N→D PROHIBIDO",   tot_nd, f"{tot_nd/total*100:.1f}%")
    if tot_nd > 0:
        st.error(f"⚠️ Se detectaron {tot_nd} transiciones N→D. Revisar operadores marcados con ❌.")
    else:
        st.success("✅ Sin transiciones N→D. Todas las reglas de descanso se cumplen.")
 
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad = (df[dia] == TURNO_DIA).sum()
        an = (df[dia] == TURNO_NOCHE).sum()
        estado_cob = "✅ OK" if ad >= demanda_dia and an >= demanda_noche else "❌ Déficit"
        check.append({
            "Día": dia, "Día (Asig)": ad, "Noche (Asig)": an,
            "Refuerzos Día": ad - demanda_dia, "Estado": estado_cob
        })
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.T, use_container_width=True)
 
    # EXPORTACIÓN EXCEL
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats_excel = df_stats.copy()
        df_stats_excel.insert(0, "Cargo", cargo)
        df_stats_excel.to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
 
    st.download_button(
        label=f"⬇️ Descargar Excel {cargo}",
        data=output.getvalue(),
        file_name=f"Programacion_{cargo}.xlsx",
    )
 
 
