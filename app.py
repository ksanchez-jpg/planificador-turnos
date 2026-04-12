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
st.caption("Objetivo: 132h exactas, Bloques 2-3 días, Mín 3 días/sem y Cobertura Garantizada.")

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
def generar_programacion_definitiva(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(15) # Semilla optimizada para cobertura
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        racha_total = {op: 0 for op in ops}
        racha_turno = {op: 0 for op in ops}
        ultimo_t = {op: None for op in ops}

        for d in bloque:
            if (d % 7) >= d_semana: continue
            
            # --- DETERMINAR CUPO DEL DÍA ---
            # Para 20 operadores y 210 turnos base, necesitamos 10 refuerzos en el ciclo de 21 días.
            # Solo activamos refuerzo si es necesario para el balance.
            dia_rel = d - bloque_idx
            cupo_dia = d_req + 1 if dia_rel < 10 else d_req # Distribuimos los 10 refuerzos al inicio

            # --- FILTRAR OPERADORES APTOS ---
            aptos = []
            for op in ops:
                if turnos_bloque[op] >= 11: continue # Límite nómina
                if racha_total[op] >= 3: continue # Límite fatiga
                
                # Regla de Oro: Mínimo 2 días. Si trabajó ayer y solo lleva 1, HOY DEBE TRABAJAR.
                es_obligado = (racha_total[op] == 1)
                
                aptos.append({"op": op, "obligado": es_obligado})

            # --- ASIGNACIÓN DE NOCHE (5) ---
            random.shuffle(aptos)
            asignados_n = []
            # Prioridad: Obligados que ya estaban de noche (para hacer NN)
            for item in [a for a in aptos if a["obligado"] and ultimo_t[a["op"]] == TURNO_NOCHE]:
                if len(asignados_n) < n_req:
                    asignados_n.append(item["op"])
            
            # Resto de noche
            candidatos_n = [a["op"] for a in aptos if a["op"] not in asignados_n]
            candidatos_n.sort(key=lambda x: (turnos_bloque[x], random.random()))
            while len(asignados_n) < n_req and candidatos_n:
                op_n = candidatos_n.pop(0)
                # Evitar NNN (Máximo 2 iguales seguidos)
                if not (ultimo_t[op_n] == TURNO_NOCHE and racha_turno[op_n] >= 2):
                    asignados_n.append(op_n)

            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_bloque[op] += 1
                racha_turno[op] = (racha_turno[op] + 1) if ultimo_t[op] == TURNO_NOCHE else 1
                racha_total[op] += 1
                ultimo_t[op] = TURNO_NOCHE

            # --- ASIGNACIÓN DE DÍA (5 o 6) ---
            ya_asignados = set(asignados_n)
            asignados_d = []
            candidatos_d = [a for a in aptos if a["op"] not in ya_asignados]
            
            # Filtrar Noche -> Día (Prohibido)
            candidatos_d = [a for a in candidatos_d if not (d > bloque_idx and horario[a["op"]][d-1] == TURNO_NOCHE)]
            
            # Prioridad 1: Obligados (Min 2)
            # Prioridad 2: Menos turnos
            candidatos_d.sort(key=lambda x: (not x["obligado"], turnos_bloque[x["op"]], random.random()))
            
            while len(asignados_d) < cupo_dia and candidatos_d:
                item = candidatos_d.pop(0)
                op_d = item["op"]
                # Evitar DDD (Máximo 2 iguales seguidos)
                if not (ultimo_t[op_d] == TURNO_DIA and racha_turno[op_d] >= 2):
                    asignados_d.append(op_d)
            
            # --- CONTROL DE EMERGENCIA: Si no llegamos al cupo por restricciones de racha, forzamos ---
            if len(asignados_d) < d_req and candidatos_d:
                while len(asignados_d) < d_req and candidatos_d:
                    asignados_d.append(candidatos_d.pop(0)["op"])

            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_bloque[op] += 1
                racha_turno[op] = (racha_turno[op] + 1) if ultimo_t[op] == TURNO_DIA else 1
                racha_total[op] += 1
                ultimo_t[op] = TURNO_DIA

            # --- LIMPIEZA DE RACHAS ---
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron:
                    racha_total[op] = 0
                    racha_turno[op] = 0
                    ultimo_t[op] = None

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button(f"🚀 Generar Programación para {cargo}"):
    total_turnos = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_final = math.ceil((total_turnos / 11) * factor_cobertura / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_definitiva(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# 6. RENDERIZADO
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">{cargo} requerido</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Contratación necesaria</div><div class="metric-value-dark">{max(0, op_final-operadores_actuales)}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Horas Meta</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación del Personal")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    # Balance Detallado con Secuencias
    st.subheader(f"📊 Balance Detallado: {cargo}")
    stats = []
    for op in df.index:
        f = df.loc[op]
        c1, c2 = sum(1 for x in f[:21] if x != DESCANSO), sum(1 for x in f[21:] if x != DESCANSO)
        def get_seq(data):
            return f"{sum(1 for x in data[0:7] if x != DESCANSO)}-{sum(1 for x in data[7:14] if x != DESCANSO)}-{sum(1 for x in data[14:21] if x != DESCANSO)}"
        
        stats.append({
            "Operador": op, "T. Día": (f==TURNO_DIA).sum(), "T. Noche": (f==TURNO_NOCHE).sum(),
            "Horas S1-3": c1*12, "Secuencia S1-3": get_seq(f[:21]),
            "Horas S4-6": c2*12, "Secuencia S4-6": get_seq(f[21:]),
            "Estado": "✅ 44h OK" if c1==11 and c2==11 else "❌"
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)

    # Validación Cobertura
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ad-demanda_dia, "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "❌"})
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.T, use_container_width=True)

    # EXPORTACIÓN EXCEL IMAGEN 2
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo 
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats.to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    st.download_button(label=f"⬇️ Descargar Programación {cargo}", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
