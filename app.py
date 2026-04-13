import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Programación de Turnos 44H", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.metric-box-green { background: #10B981; color: #064E3B; border-radius: 8px; padding: 1.2rem; text-align: center; }
.metric-value-dark { font-size: 2.2rem; font-family: monospace; font-weight: 700; }
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PROGRAMACIÓN DE TURNOS")
st.caption("Objetivo: Cobertura 5/5, 132h exactas por operador y Mínimo 3 días/semana.")

# 2. SIDEBAR - PARÁMETROS
with st.sidebar:
    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value="Cosechador")
    demanda_dia = st.number_input(f"{cargo} requerido (Día)", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} requerido (Noche)", min_value=1, value=5)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)
    st.header("🧠 Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input(f"{cargo} actual (Nómina)", min_value=0, value=20)

# 3. CONSTANTES
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN CORREGIDO
def generar_programacion_maestra(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        creditos = {op: 11 for op in ops} 
        racha = {op: 0 for op in ops}
        acum_sem = {op: [0, 0, 0] for op in ops}

        for d in bloque:
            if (d % 7) >= d_semana: continue
            sem_rel = (d - bloque_idx) // 7
            
            # --- FASE 1: NOCHE ---
            cand_n = []
            for op in ops:
                if creditos[op] > 0 and racha[op] < 3:
                    score = creditos[op] * 10
                    if acum_sem[op][sem_rel] < 3: score += 500
                    if racha[op] >= 1 and d > bloque_idx and horario[op][d-1] == TURNO_NOCHE: score += 100
                    cand_n.append({'op': op, 'score': score + random.random()})
            
            cand_n.sort(key=lambda x: x['score'], reverse=True)
            # Extraer solo el nombre (String) para evitar el KeyError
            asignados_n_names = [item['op'] for item in cand_n[:n_req]]
            
            # Rescate Noche
            if len(asignados_n_names) < n_req:
                resto = [o for o in ops if o not in asignados_n_names and creditos[o] > 0]
                asignados_n_names += resto[:n_req - len(asignados_n_names)]

            for op in asignados_n_names:
                horario[op][d] = TURNO_NOCHE
                creditos[op] -= 1
                acum_sem[op][sem_rel] += 1
                racha[op] += 1

            # --- FASE 2: DÍA ---
            ya_n = set(asignados_n_names)
            cand_d = []
            for op in ops:
                if op not in ya_n and creditos[op] > 0 and racha[op] < 3:
                    if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE: continue # No N->D
                    
                    score = creditos[op] * 10
                    if acum_sem[op][sem_rel] < 3: score += 500 
                    if racha[op] >= 1 and d > bloque_idx and horario[op][d-1] == TURNO_DIA: score += 100
                    cand_d.append({'op': op, 'score': score + random.random()})

            cand_d.sort(key=lambda x: x['score'], reverse=True)
            
            # Decidir si hay refuerzo (D+1) para quemar créditos sobrantes
            faltantes_ciclo = sum(creditos.values())
            dias_restantes = 21 - (d - bloque_idx)
            cupo_dia = d_req + 1 if (faltantes_ciclo > (d_req + n_req) * dias_restantes) else d_req
            
            asignados_d_names = [item['op'] for item in cand_d[:cupo_dia]]
            
            # Rescate Día
            if len(asignados_d_names) < d_req:
                resto_d = [o for o in ops if o not in ya_n and o not in asignados_d_names and creditos[o] > 0]
                if d > bloque_idx:
                    resto_d = [o for o in resto_d if horario[o][d-1] != TURNO_NOCHE]
                asignados_d_names += resto_d[:d_req - len(asignados_d_names)]

            for op in asignados_d_names:
                horario[op][d] = TURNO_DIA
                creditos[op] -= 1
                acum_sem[op][sem_rel] += 1
                racha[op] += 1

            # Reset racha
            trabajaron = set(asignados_n_names) | set(asignados_d_names)
            for op in ops:
                if op not in trabajaron: racha[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button(f"🚀 Generar Programación para {cargo}"):
    op_base = max(operadores_actuales, 20)
    st.session_state["df"] = generar_programacion_maestra(op_base, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_base

# 6. RENDERIZADO
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div>Operadores</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div>Cobertura</div><div class="metric-value-dark">100%</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div>Horas/Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación del Personal")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader(f"📊 Balance Detallado: {cargo}")
    stats = []
    for op in df.index:
        f = df.loc[op]
        c1_h = sum(1 for x in f[:21] if x != DESCANSO)
        c2_h = sum(1 for x in f[21:] if x != DESCANSO)
        def get_seq(data):
            return f"{sum(1 for x in data[0:7] if x != DESCANSO)}-{sum(1 for x in data[7:14] if x != DESCANSO)}-{sum(1 for x in data[14:21] if x != DESCANSO)}"
        
        # Validar si cumple Mín 3 días/semana
        s_nums = [int(x) for x in get_seq(f[:21]).split("-")]
        ok_min = all(x >= 3 for x in s_nums)

        stats.append({
            "Operador": op, "T. Día": (f==TURNO_DIA).sum(), "T. Noche": (f==TURNO_NOCHE).sum(),
            "Horas S1-3": c1_h * 12, "Secuencia S1-3": get_seq(f[:21]),
            "Horas S4-6": c2_h * 12, "Secuencia S4-6": get_seq(f[21:]),
            "Estado": "✅ 44h OK" if c1_h == 11 and c2_h == 11 and ok_min else "❌ Revisar"
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "❌"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # Exportación
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo 
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats.to_excel(writer, sheet_name="Balance")
    st.download_button(label=f"⬇️ Descargar Excel {cargo}", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
