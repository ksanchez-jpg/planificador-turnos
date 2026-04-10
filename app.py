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
st.caption("Modelo Dinámico: 132h exactas por ciclo, máximo 3 días seguidos permitidos para cumplimiento.")

# 2. SIDEBAR - TODOS LOS PARÁMETROS SOLICITADOS
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input("Operadores requeridos (Día)", min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales (Nómina)", min_value=0, value=16)

# 3. CONSTANTES
SEMANAS = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN DINÁMICO
def generar_programacion_flexible(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}
    racha = {op: 0 for op in ops}

    # Procesar por bloques de 3 semanas (21 días) para asegurar las 132h
    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        
        for d in bloque:
            dia_sem = d % 7
            if dia_sem >= d_semana: continue

            # 1. Candidatos: No más de 3 seguidos y que no hayan llegado a 11 en el ciclo
            aptos = [op for op in ops if racha[op] < 3 and turnos_bloque[op] < 11]
            
            # 2. Asignar NOCHE primero (Equidad)
            aptos.sort(key=lambda x: (turnos_bloque[x], noches_acum[x]))
            asignados_n = []
            for op in aptos:
                if len(asignados_n) < n_req:
                    horario[op][d] = TURNO_NOCHE
                    asignados_n.append(op)
                    turnos_bloque[op] += 1
                    noches_acum[op] += 1
                    racha[op] += 1
            
            # 3. Asignar DÍA (Respetando regla N->D)
            ya_n = set(asignados_n)
            hizo_n_ayer = {op for op in aptos if d > 0 and horario[op][d-1] == TURNO_NOCHE}
            aptos_d = [op for op in aptos if op not in ya_n and op not in hizo_n_ayer]
            
            # Prioridad a los que llevan menos turnos para que todos lleguen a 11
            aptos_d.sort(key=lambda x: (turnos_bloque[x], -noches_acum[x]))
            
            # Cálculo dinámico de cupo (para absorber los 8 turnos extra del ciclo)
            turnos_restantes_ciclo = (n_ops * 11) - sum(turnos_bloque.values())
            dias_restantes_ciclo = bloque.stop - d
            cupo_dia = d_req
            if turnos_restantes_ciclo > (dias_restantes_ciclo * (d_req + n_req)):
                cupo_dia = d_req + 1 # Permitimos un refuerzo para completar horas

            asignados_d = []
            for op in aptos_d:
                if len(asignados_d) < cupo_dia:
                    horario[op][d] = TURNO_DIA
                    asignados_d.append(op)
                    turnos_bloque[op] += 1
                    racha[op] += 1

            # 4. Resetear racha para los que descansan
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron:
                    racha[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button("🚀 Calcular Programación Perfecta 132h"):
    # Con 16 personas para 4+4, el cálculo es exacto.
    op_final = math.ceil(((demanda_dia + demanda_noche) * 42 / 22) * factor_cobertura / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 

    df = generar_programacion_flexible(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["df"] = df
    st.session_state["op_final"] = op_final

# 6. RESULTADOS
if "df" in st.session_state:
    df = st.session_state["df"]
    op_final = st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)

    col1, col2, col3 = st.columns(3)
    with col1: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Operadores</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with col2: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Contratar</div><div class="metric-value-dark">{faltantes}</div></div>', unsafe_allow_html=True)
    with col3: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Horas Ciclo</div><div class="metric-value-dark">132.0 (44h)</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Cuadrante (Flexible: Máx 3 días seguidos)")
    st.dataframe(df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"), use_container_width=True)

    # Validación 132h (Regla de Oro)
    st.subheader("📊 Validación: 132 Horas cada 3 Semanas")
    stats = []
    for op in df.index:
        c1 = sum(1 for x in df.loc[op][:21] if x != DESCANSO)
        c2 = sum(1 for x in df.loc[op][21:] if x != DESCANSO)
        stats.append({"Operador": op, "Turnos S1-3": c1, "Horas C1": c1*12, "Turnos S4-6": c2, "Horas C2": c2*12, "Promedio h/sem": round(((c1+c2)*12)/6, 1), "Cumple 44h": "✅ SI" if c1 == 11 and c2 == 11 else "❌ NO"})
    st.dataframe(pd.DataFrame(stats).set_index("Operador"), use_container_width=True)

    # Cobertura Diaria
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Estado": "✅ OK" if ad >= demanda_dia and an >= demanda_noche else "❌ FALTA"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}").to_excel(writer, sheet_name="Cuadrante")
    st.download_button("⬇️ Descargar Excel", output.getvalue(), "plan_44h_flexible.xlsx")
