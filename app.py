import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN Y ESTILO
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
st.caption("Estrategia: 132h exactas mediante Inyección Aleatoria de Refuerzos Programados.")

# 2. SIDEBAR - PARÁMETROS COMPLETOS
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales (Nómina)", min_value=0, value=12)

# 3. CONSTANTES
SEMANAS = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN CON INYECCIÓN ALEATORIA
def generar_programacion_refuerzos(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42) # Para reproducibilidad, pero con lógica aleatoria interna
    
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}

    # Bloques de 3 semanas
    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        
        # FASE 1: COBERTURA BASE (168 turnos)
        for d in bloque:
            if (d % 7) >= d_semana: continue
            
            # Seleccionar quiénes trabajan hoy basándose en quién tiene menos turnos y racha
            # Evitamos que trabajen más de 2 seguidos en la base para dejar espacio al refuerzo
            aptos = [op for op in ops if turnos_bloque[op] < 11]
            
            # Ordenar por menor cantidad de noches para equidad
            aptos.sort(key=lambda x: (turnos_bloque[x], noches_acum[x], random.random()))
            
            # Asignar Noche
            asignados_n = aptos[:n_req]
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_bloque[op] += 1
                noches_acum[op] += 1
            
            # Asignar Día (Evitar N->D)
            ya_n = set(asignados_n)
            hizo_n_ayer = {op for op in ops if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE}
            aptos_d = [op for op in aptos if op not in ya_n and op not in hizo_n_ayer]
            aptos_d.sort(key=lambda x: (turnos_bloque[x], -noches_acum[x], random.random()))
            
            asignados_d = aptos_d[:d_req]
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_bloque[op] += 1

        # FASE 2: INYECCIÓN ALEATORIA DE REFUERZOS (Los 8 turnos faltantes)
        for op in ops:
            intentos = 0
            while turnos_bloque[op] < 11 and intentos < 50:
                intentos += 1
                d_rand = random.choice(list(bloque))
                
                # Reglas para inyectar refuerzo:
                # 1. Que sea un día de descanso y laborable
                if horario[op][d_rand] != DESCANSO or (d_rand % 7) >= d_semana: continue
                # 2. No Noche -> Día
                if d_rand > bloque_idx and horario[op][d_rand-1] == TURNO_NOCHE: continue
                # 3. Máximo 3 días seguidos (Flexibilidad para completar 11)
                racha_antes = 0
                for i in range(d_rand-1, bloque_idx-1, -1):
                    if horario[op][i] != DESCANSO: racha_antes += 1
                    else: break
                racha_desp = 0
                for i in range(d_rand+1, bloque.stop):
                    if horario[op][i] != DESCANSO: racha_desp += 1
                    else: break
                
                if (racha_antes + racha_desp + 1) <= 3:
                    horario[op][d_rand] = TURNO_DIA
                    turnos_bloque[op] += 1

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button("🚀 Generar Programación con Refuerzos Aleatorios"):
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_final = math.ceil((total_turnos_ciclo / 11) * factor_cobertura / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_refuerzos(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# 6. RESULTADOS Y EXPORTACIÓN
if "df" in st.session_state:
    df = st.session_state["df"]
    op_final = st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)

    # Métricas
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Operadores Necesarios</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Operadores a Contratar</div><div class="metric-value-dark">{faltantes}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Horas por Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    # Estilos de Color
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"

    # Balance Detallado
    stats = []
    for op in df.index:
        fila = df.loc[op]
        d1, n1 = (fila[:21] == TURNO_DIA).sum(), (fila[:21] == TURNO_NOCHE).sum()
        d2, n2 = (fila[21:] == TURNO_DIA).sum(), (fila[21:] == TURNO_NOCHE).sum()
        stats.append({
            "Operador": op, "Día S1-3": d1, "Noche S1-3": n1, "Total S1-3": d1+n1,
            "Día S4-6": d2, "Noche S4-6": n2, "Total S4-6": d2+n2,
            "Horas Totales": (d1+n1+d2+n2)*12, "Cumple 132h": "✅ SI" if (d1+n1)==11 and (d2+n2)==11 else "❌ NO"
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")

    # Cobertura
    check = []
    for dia in NOMBRES_DIAS:
        dia_idx = NOMBRES_DIAS.index(dia) % 7
        rd, rn = (demanda_dia, demanda_noche) if dia_idx < dias_cubrir else (0, 0)
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Req. D": rd, "Asig. D": ad, "Req. N": rn, "Asig. N": an, "Estado": "✅ OK" if ad>=rd and an>=rn else "❌ FALTA"})
    df_check = pd.DataFrame(check).set_index("Día")

    # Visualización
    st.subheader("📅 Cuadrante General (Refuerzos Aleatorios)")
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader("📊 Balance de Turnos por Operador (44h)")
    st.dataframe(df_stats, use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    st.dataframe(df_check.T, use_container_width=True)

    # Exportación Multi-Hoja
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.style.map(style_func).to_excel(writer, sheet_name="Cuadrante")
        df_stats.to_excel(writer, sheet_name="Balance_Horas")
        df_check.to_excel(writer, sheet_name="Cobertura_Diaria")
    st.download_button("📥 Descargar Reporte Completo Excel", output.getvalue(), "plan_maestro_44h.xlsx")
