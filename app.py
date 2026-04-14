import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN Y ESTILO [cite: 21]
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
st.caption("Objetivo: 132h por ciclo, Prioridad 4-4-3 y variantes, Minimización de 5-3-3.")

if 'seed' not in st.session_state:
    st.session_state['seed'] = 42 [cite: 21]

# 2. SIDEBAR - PARÁMETROS [cite: 22]
with st.sidebar:
    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value="Cosechador")
    demanda_dia = st.number_input(f"{cargo} requerido (Día)", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} requerido (Noche)", min_value=1, value=5)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)
    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01) [cite: 23]
    operadores_actuales = st.number_input(f"{cargo} actual (Nómina)", min_value=0, value=20)

# 3. CONSTANTES [cite: 23]
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN [cite: 23, 24]
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(st.session_state['seed']) [cite: 23]
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops} [cite: 24]
    
    # Memoria para evitar 5-días consecutivos entre ciclos
    historial_5_dias = {op: False for op in ops}

    for bloque_idx in [0, 21]: [cite: 24]
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops} [cite: 24]
        racha = {op: 0 for op in ops} 
        turnos_semanales = {op: [0, 0, 0] for op in ops}

        for d in bloque:
            if (d % 7) >= d_semana: continue [cite: 24]
            sem_rel = (d - bloque_idx) // 7
            
            # FILTRO DE PRIORIDAD: Evitar a quienes ya tienen 4 turnos esta semana
            aptos = []
            for op in ops:
                if turnos_bloque[op] < 11: [cite: 24]
                    # Solo es apto si no rompe racha de 2 y no supera tope semanal
                    if d < 1 or horario[op][d-1] == DESCANSO or (d > 1 and horario[op][d-2] == DESCANSO): [cite: 25]
                        aptos.append(op)
            
            # Ordenamos priorizando:
            # 1. No haber llegado a 4 turnos en la semana
            # 2. Total de turnos en el bloque (equidad)
            # 3. Noches acumuladas
            aptos.sort(key=lambda x: (turnos_semanales[x][sem_rel] >= 4, turnos_bloque[x], noches_acum[x], random.random()))
            
            asignados_n = aptos[:n_req] [cite: 27]
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE [cite: 30]
                turnos_bloque[op] += 1
                turnos_semanales[op][sem_rel] += 1
                noches_acum[op] += 1
                racha[op] += 1

            ya_n = set(asignados_n) [cite: 30]
            cand_d = [op for op in aptos if op not in ya_n] [cite: 31]
            # No N->D [cite: 31]
            if d > bloque_idx:
                cand_d = [o for o in cand_d if horario[o][d-1] != TURNO_NOCHE]
            
            cand_d.sort(key=lambda x: (turnos_semanales[x][sem_rel] >= 4, turnos_bloque[x], -noches_acum[x], random.random()))
            
            asignados_d = cand_d[:d_req] [cite: 33]
            for op in asignados_d:
                horario[op][d] = TURNO_DIA [cite: 34]
                turnos_bloque[op] += 1
                turnos_semanales[op][sem_rel] += 1
                racha[op] += 1

            for op in ops:
                if op not in (set(asignados_n) | set(asignados_d)): racha[op] = 0 [cite: 35]

        # RELLENO FINAL: Máxima restricción para el 5to día 
        for op in ops:
            # Si en el bloque anterior hizo 5 días, aquí el límite es 4 estrictos
            max_permitido = 4 if (bloque_idx == 21 and historial_5_dias[op]) else 5
            
            intentos = 0
            while turnos_bloque[op] < 11 and intentos < 200: [cite: 36]
                intentos += 1
                d_rand = random.choice(list(bloque)) [cite: 36]
                sem_rand = (d_rand - bloque_idx) // 7
                
                if horario[op][d_rand] != DESCANSO or (d_rand % 7) >= d_semana: continue [cite: 37]
                
                # Solo permitir el 5to si es estrictamente necesario para llegar a 11
                if turnos_semanales[op][sem_rand] >= max_permitido: continue
                
                # No N->D y cobertura extra
                if sum(1 for o in ops if horario[o][d_rand] == TURNO_DIA) >= d_req + 1: continue [cite: 37]
                if d_rand > bloque_idx and horario[op][d_rand-1] == TURNO_NOCHE: continue [cite: 37]
                
                horario[op][d_rand] = TURNO_DIA [cite: 37]
                turnos_bloque[op] += 1
                turnos_semanales[op][sem_rand] += 1
                
            # Registrar si este operador terminó con una semana de 5 para el siguiente ciclo
            if any(count >= 5 for count in turnos_semanales[op]):
                historial_5_dias[op] = True

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN [cite: 38, 39]
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None:
        st.session_state['seed'] = semilla_manual
    
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_base = math.ceil(total_turnos_ciclo / 11)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_equitativa(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# Botones 
col1, col2 = st.columns(2)
with col1:
    if st.button(f"🚀 Generar Programación (Base)"):
        procesar_generacion(42)

with col2:
    if st.button("🔄 Generar Otra Versión Diferente"):
        procesar_generacion(random.randint(1, 100000))

# 6. RENDERIZADO [cite: 40, 41]
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales) [cite: 40]
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div>Requerido</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div>Contratación</div><div class="metric-value-dark">{faltantes}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div>Meta Horas</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación (Balance Secuencias)")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True) [cite: 41]

    st.subheader(f"📊 Balance Detallado")
    stats = []
    for op in df.index:
        fila = df.loc[op]
        c1_t = sum(1 for x in fila[:21] if x != DESCANSO) [cite: 42]
        c2_t = sum(1 for x in fila[21:] if x != DESCANSO)
        def get_seq(data):
            return f"{sum(1 for x in data[0:7] if x != DESCANSO)}-{sum(1 for x in data[7:14] if x != DESCANSO)}-{sum(1 for x in data[14:21] if x != DESCANSO)}"

        stats.append({
            "Operador": op, "T. Día": (fila==TURNO_DIA).sum(), "T. Noche": (fila==TURNO_NOCHE).sum(),
            "Horas S1-3": c1_t * horas_turno, "Secuencia S1-3": get_seq(fila[:21]),
            "Horas S4-6": c2_t * horas_turno, "Secuencia S4-6": get_seq(fila[21:]),
            "Estado": "✅ 44h OK" if c1_t == 11 and c2_t == 11 else "❌ Revisar" [cite: 43]
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)

    # Exportación [cite: 44]
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo 
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats.to_excel(writer, sheet_name="Balance")
    st.download_button(label="📥 Descargar Excel", data=output.getvalue(), file_name="Programacion_Equilibrada.xlsx")
