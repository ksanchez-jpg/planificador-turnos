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
st.caption("Objetivo: 132h por ciclo, balance D/N equitativo y modelo 2x2 mixto.") [cite: 1]

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
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7) [cite: 2]

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input(f"{cargo} actual (Nómina)", min_value=0, value=20) [cite: 3]

# 3. CONSTANTES [cite: 3]
SEMANAS = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN (BALANCE D/N Y 132H) [cite: 4]
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(st.session_state['seed'])
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_totales = {op: 0 for op in ops} # Tracking para balance D/N
    
    for inicio_bloque in [0, 21]:
        fin_bloque = inicio_bloque + 21
        turnos_bloque = {op: 0 for op in ops}
        racha = {op: 0 for op in ops} 

        for d in range(inicio_bloque, fin_bloque):
            if (d % 7) >= d_semana:
                for op in ops: racha[op] = 0
                continue
            
            random.shuffle(ops)
            
            # --- ASIGNACIÓN NOCHE (Prioriza a quienes llevan menos noches) --- [cite: 7, 9]
            asignados_n = []
            # Prioridad 2x2 Noche
            for op in ops:
                if d > inicio_bloque and horario[op][d-1] == TURNO_NOCHE and racha[op] == 1 and turnos_bloque[op] < 11:
                    if len(asignados_n) < n_req: asignados_n.append(op)
            
            # Resto Noche: Priorizar menor conteo de noches totales para balance
            cand_n = [o for o in ops if o not in asignados_n and racha[o] == 0 and turnos_bloque[o] < 11]
            cand_n.sort(key=lambda x: (noches_totales[x], turnos_bloque[x])) [cite: 9]
            
            while len(asignados_n) < n_req and cand_n:
                asignados_n.append(cand_n.pop(0))

            for op in asignados_n:
                horario[op][d], turnos_bloque[op], noches_totales[op], racha[op] = TURNO_NOCHE, turnos_bloque[op] + 1, noches_totales[op] + 1, racha[op] + 1 [cite: 10]

            # --- ASIGNACIÓN DÍA --- [cite: 11]
            asignados_d = []
            ya_n = set(asignados_n)
            # Prioridad 2x2 Día
            for op in ops:
                if op not in ya_n and d > inicio_bloque and horario[op][d-1] == TURNO_DIA and racha[op] == 1 and turnos_bloque[op] < 11:
                    if len(asignados_d) < d_req: asignados_d.append(op)
            
            # Resto Día (Evitar Noche -> Día y priorizar equidad de carga) [cite: 11, 13]
            cand_d = [o for o in ops if o not in ya_n and o not in asignados_d and racha[o] == 0 and turnos_bloque[o] < 11]
            if d > inicio_bloque:
                cand_d = [o for o in cand_d if horario[o][d-1] != TURNO_NOCHE]
            
            cand_d.sort(key=lambda x: turnos_bloque[x])
            while len(asignados_d) < d_req and cand_d:
                asignados_d.append(cand_d.pop(0))

            for op in asignados_d:
                horario[op][d], turnos_bloque[op], racha[op] = TURNO_DIA, turnos_bloque[op] + 1, racha[op] + 1 [cite: 14]

            # Reset racha [cite: 15]
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron: racha[op] = 0

        # Fase de Balanceo de Horas (Garantiza 11 turnos sin romper balance D/N) [cite: 16, 17]
        for op in ops:
            intentos = 0
            while turnos_bloque[op] < 11 and intentos < 500:
                intentos += 1
                d_rand = random.randint(inicio_bloque, fin_bloque - 1)
                if (d_rand % 7) >= d_semana or horario[op][d_rand] != DESCANSO: continue
                
                # Respetar racha max 2 y descanso post-noche [cite: 11, 17]
                racha_prev = (1 if d_rand > inicio_bloque and horario[op][d_rand-1] != DESCANSO else 0)
                racha_post = (1 if d_rand < fin_bloque-1 and horario[op][d_rand+1] != DESCANSO else 0)
                if (racha_prev + racha_post + 1) > 2: continue
                if d_rand > inicio_bloque and horario[op][d_rand-1] == TURNO_NOCHE: continue
                
                # Decidir si agregar Día o Noche según el balance actual del operador
                if noches_totales[op] < (turnos_bloque[op] / 2):
                    horario[op][d_rand] = TURNO_NOCHE
                    noches_totales[op] += 1
                else:
                    horario[op][d_rand] = TURNO_DIA
                
                turnos_bloque[op] += 1 [cite: 18]

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN [cite: 18]
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None:
        st.session_state['seed'] = semilla_manual
    
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_base = math.ceil(total_turnos_ciclo / 11)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_equitativa(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final [cite: 19]

col1, col2 = st.columns(2)
with col1:
    if st.button(f"🚀 Generar Programación (Base)"):
        procesar_generacion(42)
with col2:
    if st.button("🔄 Generar Otra Versión Diferente"):
        procesar_generacion(random.randint(1, 100000))

# 6. RENDERIZADO [cite: 20]
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div>{cargo} requerido</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True) [cite: 20]
    with c2: st.markdown(f'<div class="metric-box-green"><div>Contratación necesaria</div><div class="metric-value-dark">{faltantes}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div>Meta Horas Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación del Personal (Bloques 2x2)")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold" [cite: 21]
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader(f"📊 Balance Detallado: {cargo}") [cite: 22]
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
    st.dataframe(df_stats, use_container_width=True) [cite: 23]

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ad-demanda_dia, "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "⚠️"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # EXPORTACIÓN [cite: 24]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Programación")
        df_stats.to_excel(writer, sheet_name="Balance")
    st.download_button(label=f"⬇️ Descargar Programación {cargo} (Excel)", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx") [cite: 24]
