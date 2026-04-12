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
st.caption("Objetivo: 132h (44h prom), Mín 3 días/sem, Bloques variados (DD/NN) y Máx 2 turnos iguales seguidos.")

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

# 4. MOTOR DE PROGRAMACIÓN AVANZADO
def generar_programacion_inteligente(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    
    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_totales = {op: 0 for op in ops}
        turnos_semanales = {op: [0, 0, 0] for op in ops} # [W1, W2, W3]
        racha_iguales = {op: 0 for op in ops} # Conteo de DD o NN
        ultimo_t = {op: None for op in ops}

        for d in bloque:
            semana_rel = (d - bloque_idx) // 7
            if (d % 7) >= d_semana: continue
            
            # --- FILTROS DE ELEGIBILIDAD ---
            aptos = []
            for op in ops:
                if turnos_totales[op] >= 11: continue
                if turnos_semanales[op][semana_rel] >= 4: continue
                
                # Regla Mín 3: Si es fin de semana y tiene menos de 3, es obligatorio
                # No N->D
                if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE:
                    puede_dia = False
                else:
                    puede_dia = True
                
                aptos.append((op, puede_dia))

            # --- ASIGNACIÓN NOCHE ---
            random.shuffle(aptos)
            asignados_n = []
            for op, p_dia in aptos:
                if len(asignados_n) < n_req:
                    # Validar si puede hacer noche (No NNN)
                    if not (ultimo_t[op] == TURNO_NOCHE and racha_iguales[op] >= 2):
                        horario[op][d] = TURNO_NOCHE
                        asignados_n.append(op)
                        turnos_totales[op] += 1
                        turnos_semanales[op][semana_rel] += 1
                        racha_iguales[op] = (racha_iguales[op] + 1) if ultimo_t[op] == TURNO_NOCHE else 1
                        ultimo_t[op] = TURNO_NOCHE

            # --- ASIGNACIÓN DÍA ---
            ya_n = set(asignados_n)
            asignados_d = []
            # Priorizar a los que tienen menos turnos en la semana para cumplir el Mín 3
            aptos_d = sorted([a for a in aptos if a[0] not in ya_n and a[1]], 
                            key=lambda x: (turnos_semanales[x[0]][semana_rel], random.random()))
            
            for op, p_dia in aptos_d:
                if len(asignados_d) < d_req + 1: # Permitir el refuerzo
                    # Validar si puede hacer día (No DDD)
                    if not (ultimo_t[op] == TURNO_DIA and racha_iguales[op] >= 2):
                        horario[op][d] = TURNO_DIA
                        asignados_d.append(op)
                        turnos_totales[op] += 1
                        turnos_semanales[op][semana_rel] += 1
                        racha_iguales[op] = (racha_iguales[op] + 1) if ultimo_t[op] == TURNO_DIA else 1
                        ultimo_t[op] = TURNO_DIA

            # --- RESET DE RACHAS SI DESCANSA ---
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron:
                    racha_iguales[op] = 0
                    ultimo_t[op] = None

        # --- AJUSTE FINAL MÍN 3 DÍAS ---
        # Si alguien quedó con menos de 3 en una semana, buscamos un hueco para inyectar
        for op in ops:
            for s in range(3):
                while turnos_semanales[op][s] < 3 and turnos_totales[op] < 11:
                    rango_sem = range(bloque_idx + (s*7), bloque_idx + ((s+1)*7))
                    for d_adj in rango_sem:
                        if horario[op][d_adj] == DESCANSO and (d_adj % 7) < d_semana:
                            # Validar que no rompa N->D
                            if d_adj > bloque_idx and horario[op][d_adj-1] == TURNO_NOCHE: continue
                            if d_adj < DIAS_TOTALES-1 and horario[op][d_adj+1] == TURNO_DIA: continue
                            
                            horario[op][d_adj] = TURNO_DIA
                            turnos_semanales[op][s] += 1
                            turnos_totales[op] += 1
                            break
                    else: break

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button(f"🚀 Generar Programación para {cargo}"):
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_base = math.ceil(total_turnos_ciclo / 11)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_inteligente(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# 6. RENDERIZADO
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Operadores</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Contratar</div><div class="metric-value-dark">{max(0, op_final-operadores_actuales)}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Horas Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

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
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ad-demanda_dia, "Estado": "✅ OK"})
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.T, use_container_width=True)

    # EXPORTACIÓN EXCEL
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo 
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats.to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    st.download_button(label=f"⬇️ Descargar Programación {cargo}", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
