import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Planificador Maestro 44H", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.metric-box-green { background: #10B981; color: #064E3B; border-radius: 8px; padding: 1.2rem; text-align: center; }
.metric-value-dark { font-size: 2.2rem; font-family: 'IBM Plex Mono', monospace; font-weight: 700; }
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PROGRAMACIÓN DE PERSONAL (44H)")
st.caption("Ajuste Final: Restricción de Máximo 1 Refuerzo por turno para mayor equidad.")

# 2. SIDEBAR
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=5)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=5)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales (Nómina)", min_value=0, value=20)

# 3. CONSTANTES
SEMANAS = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR CON RESTRICCIÓN REQ + 1
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        
        # FASE 1: COBERTURA BASE (Estricta al Requerimiento)
        for d in bloque:
            if (d % 7) >= d_semana: continue
            
            aptos = [op for op in ops if turnos_bloque[op] < 11]
            # No más de 2 seguidos en la base para dejar aire
            aptos = [op for op in aptos if d < 1 or horario[op][d-1] == DESCANSO or (d > 1 and horario[op][d-2] == DESCANSO)]
            
            # Asignar Noche
            aptos.sort(key=lambda x: (turnos_bloque[x], noches_acum[x], random.random()))
            asignados_n = aptos[:n_req]
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_bloque[op] += 1
                noches_acum[op] += 1
            
            # Asignar Día (Respetando N->D)
            ya_n = set(asignados_n)
            hizo_n_ayer = {op for op in ops if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE}
            aptos_d = [op for op in aptos if op not in ya_n and op not in hizo_n_ayer]
            aptos_d.sort(key=lambda x: (turnos_bloque[x], -noches_acum[x], random.random()))
            
            asignados_d = aptos_d[:d_req]
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_bloque[op] += 1

        # FASE 2: INYECCIÓN DE REFUERZOS (Restricción: Max Req + 1)
        for op in ops:
            intentos = 0
            while turnos_bloque[op] < 11 and intentos < 100:
                intentos += 1
                d_rand = random.choice(list(bloque))
                
                # 1. Solo días laborables y que sea descanso
                if horario[op][d_rand] != DESCANSO or (d_rand % 7) >= d_semana: continue
                
                # 2. RESTRICCIÓN NUEVA: No más de (Req + 1) en el día
                ocupacion_dia = sum(1 for o in ops if horario[o][d_rand] == TURNO_DIA)
                if ocupacion_dia >= d_req + 1: continue 
                
                # 3. No Noche -> Día
                if d_rand > bloque_idx and horario[op][d_rand-1] == TURNO_NOCHE: continue
                
                # 4. Máximo 3 días seguidos (para completar los 11)
                racha = 0
                for i in range(d_rand-1, bloque_idx-1, -1):
                    if horario[op][i] != DESCANSO: racha += 1
                    else: break
                for i in range(d_rand+1, bloque.stop):
                    if horario[op][i] != DESCANSO: racha += 1
                    else: break
                
                if (racha + 1) <= 3:
                    horario[op][d_rand] = TURNO_DIA
                    turnos_bloque[op] += 1

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button("🚀 Generar Programación con Límite de Refuerzos"):
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_final = math.ceil((total_turnos_ciclo / 11) * factor_cobertura / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_equitativa(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# 6. RENDERIZADO
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Operadores</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Contratar</div><div class="metric-value-dark">{max(0, op_final-operadores_actuales)}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Horas Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    # Cuadrante
    st.subheader("📅 Cuadrante General (Equidad de Refuerzos)")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    # Balance
    st.subheader("📊 Balance de Turnos (132h Exactas)")
    stats = []
    for op in df.index:
        c1 = sum(1 for x in df.loc[op][:21] if x != DESCANSO)
        c2 = sum(1 for x in df.loc[op][21:] if x != DESCANSO)
        stats.append({"Operador": op, "Total S1-3": c1, "Horas C1": c1*12, "Total S4-6": c2, "Horas C2": c2*12, "Cumple 44h": "✅ SI" if c1==11 and c2==11 else "❌ NO"})
    st.dataframe(pd.DataFrame(stats).set_index("Operador"), use_container_width=True)

    # Cobertura Diaria (Aquí verás que ya no hay 8, solo 5 o 6)
    st.subheader("✅ Validación de Cobertura Diaria (Max Req + 1)")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ad-demanda_dia, "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "❌ FALTA"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.style.map(style_func).to_excel(writer, sheet_name="Cuadrante")
        pd.DataFrame(stats).to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    st.download_button("📥 Descargar Reporte Final Equitativo", output.getvalue(), "plan_44h_equitativo.xlsx")
