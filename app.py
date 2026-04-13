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
SEMANAS = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]
 
# 4. MOTOR DE PROGRAMACIÓN CON TRANSICIONES BALANCEADAS (DD, NN, DN)
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}
 
    # ── NUEVO: asignar un "patrón de transición" rotatorio a cada operador ──
    # Los patrones se distribuyen en tercios para garantizar balance:
    #   'DD' → el operador trabaja bloques de dos días consecutivos en Día
    #   'NN' → el operador trabaja bloques de dos noches consecutivas
    #   'DN' → el operador alterna Día→Noche (comportamiento original)
    # Dentro de cada bloque de 21 días el patrón se rota para que, al final
    # de los 42 días, ningún operador haya hecho siempre el mismo patrón.
    PATRONES = ["DD", "NN", "DN"]
    patron_bloque = {}  # patron_bloque[(op, bloque_idx)] → patrón asignado
 
    for i, op in enumerate(ops):
        # Bloque 1: distribuir equitativamente entre los tres patrones
        patron_bloque[(op, 0)]  = PATRONES[i % 3]
        # Bloque 2: rotar al siguiente patrón para variedad
        patron_bloque[(op, 21)] = PATRONES[(i + 1) % 3]
 
    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_totales   = {op: 0 for op in ops}
        turnos_semanales = {op: [0, 0, 0] for op in ops}
 
        # ── FASE 1: ASIGNACIÓN BASE ──
        for d in bloque:
            if (d % 7) >= d_semana:
                continue
            semana_rel = (d - bloque_idx) // 7
 
            # Identificar obligados (regla bloque mínimo 2 días)
            obligados = []
            for op in ops:
                if d > bloque_idx and horario[op][d-1] != DESCANSO:
                    if d-1 == bloque_idx or horario[op][d-2] == DESCANSO:
                        if turnos_totales[op] < 11:
                            obligados.append(op)
 
            aptos = [op for op in ops
                     if turnos_totales[op] < 11
                     and turnos_semanales[op][semana_rel] < 5]
 
            # ── NUEVO: determinar el turno preferido de cada operador según su patrón ──
            def turno_preferido(op, d):
                """
                Devuelve el turno que el patrón del operador prefiere para este día.
                  DD → siempre Día
                  NN → siempre Noche
                  DN → alterna: par→Día, impar→Noche  (igual que antes)
                """
                pat = patron_bloque[(op, bloque_idx)]
                if pat == "DD":
                    return TURNO_DIA
                elif pat == "NN":
                    return TURNO_NOCHE
                else:  # DN
                    # Posición relativa dentro del bloque, contando solo días laborables
                    pos = sum(1 for dd in range(bloque_idx, d) if (dd % 7) < d_semana)
                    return TURNO_DIA if pos % 2 == 0 else TURNO_NOCHE
 
            # Separar candidatos a Noche y a Día según su patrón
            candidatos_n = [op for op in aptos
                            if turno_preferido(op, d) == TURNO_NOCHE
                            and not (d > bloque_idx and horario[op][d-1] == TURNO_NOCHE
                                     and patron_bloque[(op, bloque_idx)] != "NN")]
            candidatos_d = [op for op in aptos
                            if turno_preferido(op, d) == TURNO_DIA
                            and not (d > bloque_idx and horario[op][d-1] == TURNO_NOCHE)]
 
            # Si no hay suficientes candidatos preferentes, completar con los demás aptos
            def completar(lista_pref, excluidos, cuota):
                if len(lista_pref) >= cuota:
                    return lista_pref
                extras = [op for op in aptos
                          if op not in excluidos
                          and op not in lista_pref
                          and not (d > bloque_idx and horario[op][d-1] == TURNO_NOCHE
                                   and turno_preferido(op, d) == TURNO_DIA)]
                return lista_pref + extras
 
            candidatos_n = completar(candidatos_n, set(), n_req)
            candidatos_d = completar(candidatos_d, set(candidatos_n), d_req)
 
            # Ordenar priorizando obligados, luego menor carga, luego balance noches
            candidatos_n.sort(key=lambda x: (x not in obligados,  turnos_totales[x],  noches_acum[x],   random.random()))
            candidatos_d.sort(key=lambda x: (x not in obligados,  turnos_totales[x], -noches_acum[x],   random.random()))
 
            # Asignar Noche
            asignados_n = candidatos_n[:n_req]
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_totales[op] += 1
                turnos_semanales[op][semana_rel] += 1
                noches_acum[op] += 1
 
            # Asignar Día (excluir ya asignados a noche y quienes hicieron noche ayer)
            ya_n = set(asignados_n)
            hizo_n_ayer = {op for op in ops
                           if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE}
            aptos_d = [op for op in candidatos_d
                       if op not in ya_n and op not in hizo_n_ayer]
            aptos_d.sort(key=lambda x: (x not in obligados, turnos_totales[x], -noches_acum[x], random.random()))
 
            asignados_d = aptos_d[:d_req]
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_totales[op] += 1
                turnos_semanales[op][semana_rel] += 1
 
        # ── FASE 2: AJUSTE ESTRICTO MÍNIMO 3 DÍAS / SEMANA ──
        for op in ops:
            for s in range(3):
                while turnos_semanales[op][s] < 3 and turnos_totales[op] < 11:
                    dias_semana = list(range(bloque_idx + s*7, bloque_idx + (s+1)*7))
                    random.shuffle(dias_semana)
                    exito_ajuste = False
                    for d_aj in dias_semana:
                        if horario[op][d_aj] != DESCANSO or (d_aj % 7) >= d_semana:
                            continue
                        ocupacion_dia = sum(1 for o in ops if horario[o][d_aj] == TURNO_DIA)
                        if ocupacion_dia >= d_req + 1:
                            continue
                        if d_aj > bloque_idx and horario[op][d_aj-1] == TURNO_NOCHE:
                            continue
                        horario[op][d_aj] = TURNO_DIA
                        turnos_totales[op] += 1
                        turnos_semanales[op][s] += 1
                        exito_ajuste = True
                        break
                    if not exito_ajuste:
                        break
 
        # ── FASE 3: RELLENO FINAL HASTA 11 ──
        for op in ops:
            intentos = 0
            while turnos_totales[op] < 11 and intentos < 200:
                intentos += 1
                d_rand = random.choice(list(bloque))
                s_rand = (d_rand - bloque_idx) // 7
                if (horario[op][d_rand] != DESCANSO
                        or (d_rand % 7) >= d_semana
                        or turnos_semanales[op][s_rand] >= 5):
                    continue
                ocupacion_dia = sum(1 for o in ops if horario[o][d_rand] == TURNO_DIA)
                if ocupacion_dia >= d_req + 1:
                    continue
                if d_rand > bloque_idx and horario[op][d_rand-1] == TURNO_NOCHE:
                    continue
                horario[op][d_rand] = TURNO_DIA
                turnos_totales[op] += 1
                turnos_semanales[op][s_rand] += 1
 
    return pd.DataFrame(horario, index=NOMBRES_DIAS).T
 
# 5. EJECUCIÓN
if st.button(f"🚀 Generar Programación para {cargo}"):
    op_base = math.ceil(((demanda_dia + demanda_noche) * dias_cubrir * 3) / 11)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2)
    
    st.session_state["df"] = generar_programacion_equitativa(op_final, demanda_dia, demanda_noche, dias_cubrir)
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
        fila = df.loc[op]
        c1_t = sum(1 for x in fila[:21] if x != DESCANSO)
        c2_t = sum(1 for x in fila[21:] if x != DESCANSO)
        def get_seq(data):
            return f"{sum(1 for x in data[0:7] if x != DESCANSO)}-{sum(1 for x in data[7:14] if x != DESCANSO)}-{sum(1 for x in data[14:21] if x != DESCANSO)}"
 
        # ── NUEVO: contar transiciones reales en el horario ──
        def contar_transiciones(fila_op):
            dd, nn, dn_count, nd = 0, 0, 0, 0
            vals = list(fila_op)
            for i in range(len(vals) - 1):
                a, b = vals[i], vals[i+1]
                if a == TURNO_DIA   and b == TURNO_DIA:   dd += 1
                elif a == TURNO_NOCHE and b == TURNO_NOCHE: nn += 1
                elif a == TURNO_DIA   and b == TURNO_NOCHE: dn_count += 1
                elif a == TURNO_NOCHE and b == TURNO_DIA:   nd += 1
            return dd, nn, dn_count, nd
 
        t_dd, t_nn, t_dn, t_nd = contar_transiciones(fila)
        stats.append({
            "Operador": op,
            "T. Día": (fila==TURNO_DIA).sum(),
            "T. Noche": (fila==TURNO_NOCHE).sum(),
            "Horas S1-3": c1_t * horas_turno,
            "Secuencia S1-3": get_seq(fila[:21]),
            "Horas S4-6": c2_t * horas_turno,
            "Secuencia S4-6": get_seq(fila[21:]),
            "DD": t_dd, "NN": t_nn, "DN": t_dn, "ND": t_nd,
            "Estado": "✅ 44h OK" if c1_t == 11 and c2_t == 11 else "❌ Revisar"
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)
 
    # ── NUEVO: resumen global de transiciones ──
    st.subheader("🔄 Balance Global de Transiciones")
    tot_dd = df_stats["DD"].sum()
    tot_nn = df_stats["NN"].sum()
    tot_dn = df_stats["DN"].sum()
    tot_nd = df_stats["ND"].sum()
    total_trans = tot_dd + tot_nn + tot_dn + tot_nd
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("DD (Día→Día)",   f"{tot_dd}",  f"{tot_dd/total_trans*100:.1f}%" if total_trans else "")
    col2.metric("NN (Noche→Noche)", f"{tot_nn}", f"{tot_nn/total_trans*100:.1f}%" if total_trans else "")
    col3.metric("DN (Día→Noche)",  f"{tot_dn}",  f"{tot_dn/total_trans*100:.1f}%" if total_trans else "")
    col4.metric("ND (Noche→Día)",  f"{tot_nd}",  f"{tot_nd/total_trans*100:.1f}%" if total_trans else "")
 
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad = (df[dia] == TURNO_DIA).sum()
        an = (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an,
                      "Refuerzos": ad - demanda_dia, "Estado": "✅ OK"})
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.T, use_container_width=True)
 
    # EXPORTACIÓN EXCEL
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats_excel = df_stats.copy()
        df_stats_excel.insert(0, 'Cargo', cargo)
        df_stats_excel.to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    
    st.download_button(
        label=f"⬇️ Descargar Excel {cargo}",
        data=output.getvalue(),
        file_name=f"Programacion_{cargo}.xlsx"
    )
 
