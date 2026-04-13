import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Programación de Turnos 42H (2x2)", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.metric-box-blue { background: #1E3A8A; color: white; border-radius: 8px; padding: 1.2rem; text-align: center; }
.metric-value { font-size: 2.2rem; font-family: 'IBM Plex Mono', monospace; font-weight: 700; }
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PLANIFICADOR 42H (MODELO 2x2)")
st.caption("Objetivo: 42h promedio, bloques 2x2 mixtos (DD, NN, DN) y balance de 10.5 turnos.")

# Inicializar semilla en el estado de la sesión
if 'seed' not in st.session_state:
    st.session_state['seed'] = 42

# 2. SIDEBAR - PARÁMETROS
with st.sidebar:
    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value="Cosechador")
    
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input(f"{cargo} (Día)", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} (Noche)", min_value=1, value=5)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    operadores_actuales = st.number_input(f"{cargo} actual (Nómina)", min_value=0, value=20)

# 3. CONSTANTES
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN 2x2 DINÁMICO
def generar_programacion_42h(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(st.session_state['seed'])
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    # Meta de turnos: algunos 10 y otros 11 para promediar 10.5 en 21 días
    # En el balance de 42 días, todos tendrán 21 turnos exactos (42h prom)
    metas_b1 = {op: (10 if i < n_ops // 2 else 11) for i, op in enumerate(ops)}
    metas_b2 = {op: (11 if i < n_ops // 2 else 10) for i, op in enumerate(ops)}

    for bloque_idx, metas in [(0, metas_b1), (21, metas_b2)]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        racha = {op: 0 for op in ops}

        for d in bloque:
            if (d % 7) >= d_semana: continue
            
            # IDENTIFICAR OBLIGADOS (Día 2 del bloque 2x2)
            obligados_D = []
            obligados_N = []
            for op in ops:
                if racha[op] == 1: 
                    if horario[op][d-1] == TURNO_DIA: obligados_D.append(op)
                    else: obligados_N.append(op)

            # --- ASIGNACIÓN NOCHE ---
            cand_n = [op for op in ops if turnos_bloque[op] < metas[op] and racha[op] < 2]
            random.shuffle(cand_n)
            
            asignados_n = []
            # 1. Prioridad: NN (Sigue en noche)
            for op in [o for o in obligados_N if o in cand_n]:
                if len(asignados_n) < n_req: asignados_n.append(op)
            
            # 2. Variedad: DN (Pasa de día a noche)
            for op in [o for o in obligados_D if o in cand_n]:
                if len(asignados_n) < n_req and random.random() < 0.3: # 30% prob cambio
                    asignados_n.append(op)
            
            # 3. Resto de cupo
            resto_n = [o for o in cand_n if o not in asignados_n]
            resto_n.sort(key=lambda x: (turnos_bloque[x], random.random()))
            while len(asignados_n) < n_req and resto_n:
                asignados_n.append(resto_n.pop(0))

            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_bloque[op] += 1
                racha[op] += 1

            # --- ASIGNACIÓN DÍA ---
            ya_n = set(asignados_n)
            cand_d = [op for op in ops if op not in ya_n and turnos_bloque[op] < metas[op] and racha[op] < 2]
            # REGLA INVIOLABLE: No N->D
            if d > bloque_idx:
                cand_d = [o for o in cand_d if horario[o][d-1] != TURNO_NOCHE]
            
            asignados_d = []
            # 1. Prioridad: DD (Sigue en día)
            for op in [o for o in obligados_D if o in cand_d]:
                if len(asignados_d) < d_req: asignados_d.append(op)
            
            # 2. Resto (incluye ND si racha reset)
            resto_d = [o for o in cand_d if o not in asignados_d]
            resto_d.sort(key=lambda x: (turnos_bloque[x], random.random()))
            while len(asignados_d) < d_req + 1 and resto_d: # +1 para refuerzos inteligentes
                asignados_d.append(resto_d.pop(0))

            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_bloque[op] += 1
                racha[op] += 1

            # Reset racha para descansos
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron: racha[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None:
        st.session_state['seed'] = semilla_manual
    
    # Cálculo de operadores para 42h (10.5 turnos)
    op_base = math.ceil(((demanda_dia + demanda_noche) * dias_cubrir * 3) / 10.5)
    op_final = math.ceil(op_base * factor_cobertura)
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_42h(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# Botones
col1, col2 = st.columns(2)
with col1:
    if st.button(f"🚀 Generar Programación (Base)"):
        procesar_generacion(42)

with col2:
    if st.button("🔄 Generar Otra Versión Diferente"):
        procesar_generacion(random.randint(1, 100000))

# 6. RENDERIZADO
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-blue"><div>{cargo} Requerido</div><div class="metric-value">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-blue"><div>Promedio Semanal</div><div class="metric-value">42.0h</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-blue"><div>Horas/Ciclo (21d)</div><div class="metric-value">126.0h</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación del Personal (Modelo 2x2 Mixto)")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader(f"📊 Balance Detallado: {cargo}")
    stats = []
    for op in df.index:
        f = df.loc[op]
        c1_t, c2_t = (f[:21] != DESCANSO).sum(), (f[21:] != DESCANSO).sum()
        def get_seq(data):
            return f"{sum(1 for x in data[0:7] if x != DESCANSO)}-{sum(1 for x in data[7:14] if x != DESCANSO)}-{sum(1 for x in data[14:21] if x != DESCANSO)}"

        stats.append({
            "Operador": op, "T. Día": (f==TURNO_DIA).sum(), "T. Noche": (f==TURNO_NOCHE).sum(),
            "Horas S1-3": c1_t * 12, "Secuencia S1-3": get_seq(f[:21]),
            "Horas S4-6": c2_t * 12, "Secuencia S4-6": get_seq(f[21:]),
            "Estado": "✅ 42h OK" if (c1_t + c2_t) == 21 else "❌ Revisar"
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "❌"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # EXPORTACIÓN
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo 
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats_excel = df_stats.copy()
        df_stats_excel.insert(0, 'Cargo', cargo)
        df_stats_excel.to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    
    st.download_button(label=f"⬇️ Descargar Excel {cargo}", data=output.getvalue(), file_name=f"Programacion_42h_{cargo}.xlsx")
