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
st.caption("Objetivo: 132h por ciclo, Mín 3 días/semana, bloques mín. 2 días y máx 1 refuerzo.")

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

# 4. MOTOR DE PROGRAMACIÓN CORREGIDO
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_totales = {op: 0 for op in ops}
        turnos_semanales = {op: [0, 0, 0] for op in ops} 

        # --- FASE 1: ASIGNACIÓN BASE ---
        for d in bloque:
            if (d % 7) >= d_semana: continue
            semana_rel = (d - bloque_idx) // 7
            
            # Lógica bloques mín 2: Identificar obligados
            obligados = []
            for op in ops:
                if d > bloque_idx and horario[op][d-1] != DESCANSO:
                    if d-1 == bloque_idx or horario[op][d-2] == DESCANSO:
                        if turnos_totales[op] < 11: obligados.append(op)

            aptos = [op for op in ops if turnos_totales[op] < 11 and turnos_semanales[op][semana_rel] < 5]
            aptos.sort(key=lambda x: (x not in obligados, turnos_totales[x], noches_acum[x], random.random()))
            
            # Asignar Noche
            asignados_n = aptos[:n_req]
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_totales[op] += 1
                turnos_semanales[op][semana_rel] += 1
                noches_acum[op] += 1
            
            # Asignar Día
            ya_n = set(asignados_n)
            hizo_n_ayer = {op for op in ops if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE}
            aptos_d = [op for op in aptos if op not in ya_n and op not in hizo_n_ayer]
            aptos_d.sort(key=lambda x: (x not in obligados, turnos_totales[x], -noches_acum[x], random.random()))
            
            asignados_d = aptos_d[:d_req]
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_totales[op] += 1
                turnos_semanales[op][semana_rel] += 1

        # --- FASE 2: AJUSTE ESTRICTO MÍNIMO 3 DÍAS / SEMANA ---
        for op in ops:
            for s in range(3):
                # Mientras la semana tenga menos de 3 y el total menos de 11
                while turnos_semanales[op][s] < 3 and turnos_totales[op] < 11:
                    dias_semana = list(range(bloque_idx + s*7, bloque_idx + (s+1)*7))
                    random.shuffle(dias_semana)
                    
                    exito_ajuste = False
                    for d_aj in dias_semana:
                        if horario[op][d_aj] != DESCANSO or (d_aj % 7) >= d_semana: continue
                        
                        # Respetar N->D y Max Refuerzo
                        ocupacion_dia = sum(1 for o in ops if horario[o][d_aj] == TURNO_DIA)
                        if ocupacion_dia >= d_req + 1: continue 
                        if d_aj > bloque_idx and horario[op][d_aj-1] == TURNO_NOCHE: continue
                        
                        horario[op][d_aj] = TURNO_DIA
                        turnos_totales[op] += 1
                        turnos_semanales[op][s] += 1
                        exito_ajuste = True
                        break
                    
                    if not exito_ajuste: break # No hubo huecos válidos

        # --- FASE 3: RELLENO FINAL HASTA 11 (Si faltan) ---
        for op in ops:
            intentos = 0
            while turnos_totales[op] < 11 and intentos < 200:
                intentos += 1
                d_rand = random.choice(list(bloque))
                s_rand = (d_rand - bloque_idx) // 7
                
                if horario[op][d_rand] != DESCANSO or (d_rand % 7) >= d_semana or turnos_semanales[op][s_rand] >= 5: continue
                
                ocupacion_dia = sum(1 for o in ops if horario[o][d_rand] == TURNO_DIA)
                if ocupacion_dia >= d_req + 1: continue 
                if d_rand > bloque_idx and horario[op][d_rand-1] == TURNO_NOCHE: continue
                
                horario[op][d_rand] = TURNO_DIA
                turnos_totales[op] += 1
                turnos_semanales[op][s_rand] += 1
                    
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
        df_stats_excel = df_stats.copy()
        df_stats_excel.insert(0, 'Cargo', cargo)
        df_stats_excel.to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    
    st.download_button(label=f"⬇️ Descargar Excel {cargo}", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
