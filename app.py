import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN Y ESTILO [cite: 1]
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
st.caption("Objetivo: 132h por ciclo, modelo 2x2 mixto (DD, NN, DN) y cobertura garantizada.")

if 'seed' not in st.session_state:
    st.session_state['seed'] = 42

# 2. SIDEBAR - PARÁMETROS [cite: 2]
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

# 3. CONSTANTES [cite: 3]
SEMANAS = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN CORREGIDO (MODELO 2x2 MIXTO ROBUSTO) [cite: 4]
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(st.session_state['seed'])
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    racha = {op: 0 for op in ops} 

    # Dividimos en bloques de 21 días para asegurar las 132h (11 turnos) por bloque [cite: 4]
    for inicio_bloque in [0, 21]:
        fin_bloque = inicio_bloque + 21
        turnos_bloque = {op: 0 for op in ops}

        for d in range(inicio_bloque, fin_bloque):
            # Regla de días operativos [cite: 4]
            if (d % 7) >= d_semana:
                for op in ops: racha[op] = 0
                continue
            
            random.shuffle(ops) 
            
            # --- ASIGNACIÓN DE NOCHE ---
            asignados_n = []
            # Prioridad 1: Continuidad 2x2 (Si trabajó Noche ayer y lleva racha 1) [cite: 5, 6]
            for op in ops:
                if d > inicio_bloque and horario[op][d-1] == TURNO_NOCHE and racha[op] == 1:
                    if len(asignados_n) < n_req and turnos_bloque[op] < 11:
                        asignados_n.append(op)

            # Prioridad 2: Operadores con menos turnos en el bloque para equidad [cite: 9]
            candidatos_n = [o for o in ops if o not in asignados_n and racha[o] == 0 and turnos_bloque[o] < 11]
            candidatos_n.sort(key=lambda x: turnos_bloque[x])
            
            while len(asignados_n) < n_req and candidatos_n:
                asignados_n.append(candidatos_n.pop(0))

            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_bloque[op] += 1
                racha[op] += 1

            # --- ASIGNACIÓN DE DÍA ---
            asignados_d = []
            ya_n = set(asignados_n)
            
            # Prioridad 1: Continuidad 2x2 (Si trabajó Día ayer y lleva racha 1) 
            for op in ops:
                if op not in ya_n and d > inicio_bloque and horario[op][d-1] == TURNO_DIA and racha[op] == 1:
                    if len(asignados_d) < d_req and turnos_bloque[op] < 11:
                        asignados_d.append(op)

            # Prioridad 2: Nuevos ingresos a turno Día (Regla: No Noche -> Día) [cite: 11]
            candidatos_d = [o for o in ops if o not in ya_n and o not in asignados_d and racha[o] == 0 and turnos_bloque[o] < 11]
            if d > inicio_bloque:
                candidatos_d = [o for o in candidatos_d if horario[o][d-1] != TURNO_NOCHE]
            
            candidatos_d.sort(key=lambda x: turnos_bloque[x])

            while len(asignados_d) < d_req and candidatos_d:
                asignados_d.append(candidatos_d.pop(0))

            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_bloque[op] += 1
                racha[op] += 1

            # Reset de racha para quienes no trabajaron hoy [cite: 15]
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron: racha[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN 
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None:
        st.session_state['seed'] = semilla_manual
    
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_base = math.ceil(total_turnos_ciclo / 11)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_equitativa(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# Botones de Acción
col1, col2 = st.columns(2)
with col1:
    if st.button(f"🚀 Generar Programación (Base)"):
        procesar_generacion(42)

with col2:
    if st.button("🔄 Generar Otra Versión Diferente"):
        procesar_generacion(random.randint(1, 100000))

# 6. RENDERIZADO [cite: 14, 20, 21, 22, 23]
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">{cargo} requerido</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Contratación necesaria</div><div class="metric-value-dark">{faltantes}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Meta Horas Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación del Personal (Bloques 2x2)")
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

        stats.append({
            "Operador": op, "T. Día": (fila==TURNO_DIA).sum(), "T. Noche": (fila==TURNO_NOCHE).sum(),
            "Horas S1-3": c1_t * horas_turno, "Secuencia S1-3": get_seq(fila[:21]),
            "Horas S4-6": c2_t * horas_turno, "Secuencia S4-6": get_seq(fila[21:]),
            "Estado": "✅ 44h OK" if c1_t == 11 and c2_t == 11 else "❌ Revisar"
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ad-demanda_dia, "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "⚠️"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # --- EXPORTACIÓN --- [cite: 24]
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo 
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats_excel = df_stats.copy()
        df_stats_excel.insert(0, 'Cargo', cargo)
        df_stats_excel.to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    
    st.download_button(label=f"⬇️ Descargar Programación {cargo} (Excel)", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
