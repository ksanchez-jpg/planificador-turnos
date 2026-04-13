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
st.caption("Objetivo: 132h exactas, Mín 3 / Máx 5 días sem, Bloques de 2-3 días y Cobertura 5/5.")

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
def generar_programacion_blindada(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_totales = {op: 0 for op in ops}
        turnos_semanales = {op: [0, 0, 0] for op in ops}
        racha_consecutiva = {op: 0 for op in ops}

        for d in bloque:
            if (d % 7) >= d_semana: continue
            semana_rel = (d - bloque_idx) // 7
            
            # --- SISTEMA DE PUNTUACIÓN DE CANDIDATOS ---
            candidatos = []
            for op in ops:
                if turnos_totales[op] >= 11: continue
                if turnos_semanales[op][semana_rel] >= 5: continue
                if racha_consecutiva[op] >= 3: continue
                
                score = 0
                # Prioridad 1: Mínimo 3 días por semana
                if turnos_semanales[op][semana_rel] < 3: score += 1000
                # Prioridad 2: Continuar bloque (Mínimo 2 días)
                if racha_consecutiva[op] == 1: score += 500
                # Prioridad 3: Balance general de créditos
                score += (11 - turnos_totales[op]) * 10
                
                candidatos.append({'op': op, 'score': score + random.random()})

            # --- ASIGNACIÓN NOCHE (Fijo n_req) ---
            candidatos.sort(key=lambda x: x['score'], reverse=True)
            asignados_n = [c['op'] for c in candidatos[:n_req]]
            
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_totales[op] += 1
                turnos_semanales[op][semana_rel] += 1
                racha_consecutiva[op] += 1

            # --- ASIGNACIÓN DÍA (Fijo d_req + refuerzo inteligente) ---
            ya_n = set(asignados_n)
            # No Noche -> Día prohibido
            cand_d = [c for c in candidatos if c['op'] not in ya_n]
            if d > bloque_idx:
                cand_d = [c for c in cand_d if horario[c['op']][d-1] != TURNO_NOCHE]
            
            cand_d.sort(key=lambda x: x['score'], reverse=True)
            
            # Cupo de día: Aseguramos d_req, y el refuerzo (+1) solo si alguien necesita turnos urgente
            cupo_dia = d_req + 1 if (cand_d and cand_d[0]['score'] > 500) else d_req
            asignados_d = [c['op'] for c in cand_d[:cupo_dia]]
            
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_totales[op] += 1
                turnos_semanales[op][semana_rel] += 1
                racha_consecutiva[op] += 1

            # --- RESET RACHAS ---
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron: racha_consecutiva[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button(f"🚀 Generar Programación para {cargo}"):
    total_turnos = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_final = math.ceil((total_turnos / 11) * factor_cobertura / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_blindada(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# 6. RENDERIZADO
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div class="metric-label">{cargo} requerido</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div class="metric-label">Contratar</div><div class="metric-value-dark">{faltantes}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div class="metric-label">Meta Horas</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

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
        
        # Validación estricta de 132h y Mínimo 3 días por semana
        s1, s2, s3 = [int(x) for x in get_seq(fila[:21]).split("-")]
        s4, s5, s6 = [int(x) for x in get_seq(fila[21:]).split("-")]
        ok_semanal = all(x >= 3 for x in [s1, s2, s3, s4, s5, s6])

        stats.append({
            "Operador": op, "T. Día": (fila==TURNO_DIA).sum(), "T. Noche": (fila==TURNO_NOCHE).sum(),
            "Horas S1-3": c1_t * 12, "Secuencia S1-3": get_seq(fila[:21]),
            "Horas S4-6": c2_t * 12, "Secuencia S4-6": get_seq(fila[21:]),
            "Estado": "✅ 44h OK" if c1_t == 11 and c2_t == 11 and ok_semanal else "❌ Revisar"
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ad-demanda_dia, "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "❌"})
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.T, use_container_width=True)

    # EXPORTACIÓN
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo 
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats.to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    st.download_button(label=f"⬇️ Descargar Excel {cargo}", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
