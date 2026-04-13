import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Programación de Turnos 42H (2x2)", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.metric-box-blue { background: #DBEAFE; color: #1E3A8A; border-radius: 8px; padding: 1.2rem; text-align: center; border: 1px solid #BFDBFE; }
.metric-value { font-size: 2.2rem; font-family: monospace; font-weight: 700; }
.stButton > button { background: #1E3A8A; color: white; border-radius: 4px; width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PLANIFICADOR 42H (MODELO 2x2)")
st.caption("Objetivo: 42 horas promedio semanales (252h por ciclo de 6 semanas), bloques de 2 días y cobertura fija.")

# 2. SIDEBAR
with st.sidebar:
    st.header("👤 Configuración")
    cargo = st.text_input("Nombre del Cargo", value="Cosechador")
    demanda_dia = st.number_input(f"{cargo} por turno", min_value=1, value=5)
    operadores_actuales = st.number_input(f"Nómina Actual", min_value=1, value=20)
    
    st.info("💡 En este modelo de 42h, 20 personas cubren exactamente un requerimiento de 5D/5N.")

# 3. CONSTANTES
DIAS_TOTALES = 42 # Ciclo completo de 6 semanas
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN 2x2 (42 HORAS)
def generar_programacion_42h(n_ops, req_turno):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(99)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    
    # En 42 días, para promediar 42h semanales, cada op debe trabajar exactamente 21 turnos.
    # (21 turnos * 12h = 252h. 252h / 6 semanas = 42h/semana).
    creditos_totales = {op: 21 for op in ops}
    racha = {op: 0 for op in ops}

    for d in range(DIAS_TOTALES):
        # --- ASIGNACIÓN NOCHE ---
        # Prioridad a quien tiene racha de 1 (para hacer el 2x2)
        cand_n = []
        for op in ops:
            if creditos_totales[op] > 0 and racha[op] < 2:
                score = 0
                if racha[op] == 1 and d > 0 and horario[op][d-1] == TURNO_NOCHE: score += 1000
                cand_n.append({'op': op, 'score': score + creditos_totales[op] + random.random()})
        
        cand_n.sort(key=lambda x: x['score'], reverse=True)
        asignados_n = [item['op'] for item in cand_n[:req_turno]]
        
        # Rescate si falta gente
        if len(asignados_n) < req_turno:
            resto = [o for o in ops if o not in asignados_n and creditos_totales[o] > 0]
            asignados_n += resto[:req_turno - len(asignados_n)]

        for op in asignados_n:
            horario[op][d] = TURNO_NOCHE
            creditos_totales[op] -= 1
            racha[op] += 1

        # --- ASIGNACIÓN DÍA ---
        ya_n = set(asignados_n)
        cand_d = []
        for op in ops:
            if op not in ya_n and creditos_totales[op] > 0 and racha[op] < 2:
                # REGLA OBLIGATORIA: No N->D
                if d > 0 and horario[op][d-1] == TURNO_NOCHE: continue
                
                score = 0
                if racha[op] == 1 and d > 0 and horario[op][d-1] == TURNO_DIA: score += 1000
                cand_d.append({'op': op, 'score': score + creditos_totales[op] + random.random()})

        cand_d.sort(key=lambda x: x['score'], reverse=True)
        asignados_d = cand_d[:req_turno]
        asignados_d_names = [item['op'] for item in asignados_d]
        
        # Rescate Día
        if len(asignados_d_names) < req_turno:
            resto_d = [o for o in ops if o not in ya_n and o not in asignados_d_names and creditos_totales[o] > 0]
            if d > 0: resto_d = [o for o in resto_d if horario[o][d-1] != TURNO_NOCHE]
            asignados_d_names += resto_d[:req_turno - len(asignados_d_names)]

        for op in asignados_d_names:
            horario[op][d] = TURNO_DIA
            creditos_totales[op] -= 1
            racha[op] += 1

        # Reset racha si descansó
        trabajaron = set(asignados_n) | set(asignados_d_names)
        for op in ops:
            if op not in trabajaron: racha[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button(f"🚀 Generar Programación 2x2 para {cargo}"):
    st.session_state["df_42"] = generar_programacion_42h(operadores_actuales, demanda_dia)

# 6. RESULTADOS
if "df_42" in st.session_state:
    df = st.session_state["df_42"]
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-blue"><div>Total Operadores</div><div class="metric-value">{operadores_actuales}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-blue"><div>Horas Semanales</div><div class="metric-value">42.0</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-blue"><div>Días Trabajados / 42</div><div class="metric-value">21</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Cuadro de Turnos (Modelo 2x2)")
    style_func = lambda v: f"background-color: {'#FEF3C7' if v=='D' else '#DBEAFE' if v=='N' else '#F9FAFB'}; font-weight: bold; border: 0.5px solid #E5E7EB"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader("📊 Resumen de Nómina (6 Semanas)")
    stats = []
    for op in df.index:
        fila = df.loc[op]
        total_turnos = (fila != DESCANSO).sum()
        stats.append({
            "Operador": op,
            "Turnos Día": (fila == TURNO_DIA).sum(),
            "Turnos Noche": (fila == TURNO_NOCHE).sum(),
            "Total Horas": total_turnos * 12,
            "Promedio Semanal": (total_turnos * 12) / 6,
            "Estado": "✅ 42h OK" if total_turnos == 21 else "⚠️ Ajustar"
        })
    st.dataframe(pd.DataFrame(stats).set_index("Operador"), use_container_width=True)

    # Validación Cobertura
    st.subheader("✅ Verificación de Cobertura")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Estado": "✅ OK" if ad==demanda_dia and an==demanda_dia else "❌"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)
