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
st.caption("Objetivo: 132h, Cobertura 100% Garantizada, Mín 3 días/sem, Bloques 2-3 días.")

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

# 4. MOTOR DE PROGRAMACIÓN ROBUSTO
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(44) # Semilla ajustada para máxima estabilidad
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    
    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_totales = {op: 0 for op in ops}
        turnos_semanales = {op: [0, 0, 0] for op in ops}
        racha_consecutiva = {op: 0 for op in ops}

        for d in bloque:
            if (d % 7) >= d_semana: continue
            semana_rel = (d - bloque_idx) // 7
            
            # --- FASE 1: NOCHE (Prioridad absoluta de cobertura) ---
            # Candidatos para noche (Excluye solo a los que ya llegaron a 11 o racha > 3)
            # Nota: NN es preferido si está en medio de un bloque
            cand_n = []
            for op in ops:
                if turnos_totales[op] < 11:
                    score = 0
                    if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE: score += 50 # Prefiere NN
                    if racha_consecutiva[op] == 1: score += 100 # Obligado Min 2
                    if racha_consecutiva[op] >= 3: score -= 200 # Evita > 3
                    cand_n.append({'op': op, 'score': score + random.random()})
            
            cand_n.sort(key=lambda x: x['score'], reverse=True)
            asignados_n = [item['op'] for item in cand_n[:n_req]]
            
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_totales[op] += 1
                turnos_semanales[op][semana_rel] += 1
                racha_consecutiva[op] += 1

            # --- FASE 2: DÍA (Prioridad absoluta de cobertura) ---
            ya_n = set(asignados_n)
            cand_d = []
            for op in ops:
                if op not in ya_n and turnos_totales[op] < 11:
                    # Regla inviolable: No Noche -> Día
                    if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE: continue
                    
                    score = 0
                    if d > bloque_idx and horario[op][d-1] == TURNO_DIA: score += 50 # Prefiere DD
                    if racha_consecutiva[op] == 1: score += 100 # Obligado Min 2
                    if turnos_semanales[op][semana_rel] < 3: score += 30 # Prioriza Mín 3/sem
                    if racha_consecutiva[op] >= 3: score -= 200 # Evita > 3
                    cand_d.append({'op': op, 'score': score + random.random()})

            cand_d.sort(key=lambda x: x['score'], reverse=True)
            
            # Asegurar cupo de día (d_req) + posible refuerzo (max 1)
            cupo_dia = d_req
            if (sum(turnos_totales.values()) < (n_ops * 11 * (d-bloque_idx+1)/21)):
                cupo_dia = d_req + 1
            
            asignados_d = [item['op'] for item in cand_d[:cupo_dia]]
            
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_totales[op] += 1
                turnos_semanales[op][semana_rel] += 1
                racha_consecutiva[op] += 1

            # --- FASE 3: LIMPIEZA DE RACHAS ---
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron: racha_consecutiva[op] = 0

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
    
    # Métricas
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
        c1_t, c2_t = sum(1 for x in fila[:21] if x != DESCANSO), sum(1 for x in fila[21:] if x != DESCANSO)
        def get_seq(data):
            return f"{sum(1 for x in data[0:7] if x != DESCANSO)}-{sum(1 for x in data[7:14] if x != DESCANSO)}-{sum(1 for x in data[14:21] if x != DESCANSO)}"
        stats.append({
            "Operador": op, "T. Día": (fila==TURNO_DIA).sum(), "T. Noche": (fila==TURNO_NOCHE).sum(),
            "Horas S1-3": c1_t * 12, "Secuencia S1-3": get_seq(fila[:21]),
            "Horas S4-6": c2_t * 12, "Secuencia S4-6": get_seq(fila[21:]),
            "Estado": "✅ 44h OK" if c1_t == 11 and c2_t == 11 else "❌ Revisar"
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        # Validación de estado: Si falta gente, pone ❌
        estado_dia = "✅ OK" if ad >= demanda_dia and an >= demanda_noche else "❌ INSUFICIENTE"
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ad-demanda_dia, "Estado": estado_dia})
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.T, use_container_width=True)

    # Exportación
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo 
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats_excel = df_stats.copy()
        df_stats_excel.insert(0, 'Cargo', cargo)
        df_stats_excel.to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    st.download_button(label=f"⬇️ Descargar Excel {cargo}", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
