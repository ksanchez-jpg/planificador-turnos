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
.metric-box-green { 
    background: #10B981; 
    color: #064E3B; 
    border-radius: 8px; 
    padding: 1.2rem; 
    text-align: center;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
.metric-label-dark { font-size: 0.75rem; color: #064E3B; text-transform: uppercase; font-weight: 600; }
.metric-value-dark { font-size: 2.2rem; font-family: 'IBM Plex Mono', monospace; font-weight: 700; }
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PROGRAMACIÓN DE PERSONAL (44H)")
st.caption("Reporte Completo: Cálculo de contratación, Balance de Horas y Validación de Cobertura.")

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
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN (44H CADA 3 SEMANAS)
def generar_programacion_flexible(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}
    racha = {op: 0 for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        for d in bloque:
            dia_sem = d % 7
            if dia_sem >= d_semana: continue
            
            # Candidatos: Máximo 3 seguidos y meta de 11 turnos por bloque
            aptos = [op for op in ops if racha[op] < 3 and turnos_bloque[op] < 11]
            aptos.sort(key=lambda x: (turnos_bloque[x], noches_acum[x]))
            
            asignados_n = []
            for op in aptos:
                if len(asignados_n) < n_req:
                    horario[op][d] = TURNO_NOCHE
                    asignados_n.append(op)
                    turnos_bloque[op] += 1
                    noches_acum[op] += 1
                    racha[op] += 1
            
            ya_n = set(asignados_n)
            hizo_n_ayer = {op for op in aptos if d > 0 and horario[op][d-1] == TURNO_NOCHE}
            aptos_d = sorted([op for op in aptos if op not in ya_n and op not in hizo_n_ayer], 
                             key=lambda x: (turnos_bloque[x], -noches_acum[x]))
            
            # Cálculo de cupo para distribuir refuerzos
            turnos_restantes = (n_ops * 11) - sum(turnos_bloque.values())
            dias_restantes = bloque.stop - d
            cupo_dia = d_req + 1 if turnos_restantes > (dias_restantes * (d_req + n_req)) else d_req
            
            asignados_d = []
            for op in aptos_d:
                if len(asignados_d) < cupo_dia:
                    horario[op][d] = TURNO_DIA
                    asignados_d.append(op)
                    turnos_bloque[op] += 1
                    racha[op] += 1
            
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron: racha[op] = 0
                
    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button("🚀 Calcular Programación y Reportes"):
    # Cálculo de personal: (Total turnos ciclo / 11 turnos por op)
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_base = math.ceil(total_turnos_ciclo / 11)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_flexible(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final
    st.session_state["calculado"] = True

# 6. RESULTADOS
if st.session_state.get("calculado"):
    df = st.session_state["df"]
    op_final = st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)
    
    # --- PANELES DE MÉTRICAS VERDES ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'''<div class="metric-box-green">
            <div class="metric-label-dark">Operadores Necesarios</div>
            <div class="metric-value-dark">{op_final}</div>
        </div>''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''<div class="metric-box-green">
            <div class="metric-label-dark">Operadores a Contratar</div>
            <div class="metric-value-dark">{faltantes}</div>
        </div>''', unsafe_allow_html=True)
    with col3:
        st.markdown(f'''<div class="metric-box-green">
            <div class="metric-label-dark">Meta cada 3 Semanas</div>
            <div class="metric-value-dark">132h</div>
        </div>''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Estilos de color para tablas y Excel
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"

    # --- TABLA DE BALANCE ---
    stats = []
    for op in df.index:
        c1 = sum(1 for x in df.loc[op][:21] if x != DESCANSO)
        c2 = sum(1 for x in df.loc[op][21:] if x != DESCANSO)
        stats.append({"Operador": op, "Turnos S1-3": c1, "Horas C1": c1*12, "Turnos S4-6": c2, "Horas C2": c2*12, "Cumple 132h": "✅ SI" if c1==11 and c2==11 else "❌ NO"})
    df_stats = pd.DataFrame(stats).set_index("Operador")

    # --- TABLA DE COBERTURA ---
    check = []
    for dia in NOMBRES_DIAS:
        dia_idx = NOMBRES_DIAS.index(dia) % 7
        rd, rn = (demanda_dia, demanda_noche) if dia_idx < dias_cubrir else (0, 0)
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCH).sum() if 'TURNO_NOCH' in locals() else (df[dia] == "N").sum()
        check.append({"Día": dia, "Req. D": rd, "Asig. D": ad, "Req. N": rn, "Asig. N": an, "Estado": "✅ OK" if ad>=rd and an>=rn else "❌ FALTA"})
    df_check = pd.DataFrame(check).set_index("Día")

    # Visualización en la App
    st.subheader("📅 Cuadrante de Turnos")
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader("📊 Balance de Carga Laboral")
    st.dataframe(df_stats.style.map(lambda x: "background-color: #D4EDDA; font-weight: bold" if x == 132 else "", subset=["Horas C1", "Horas C2"]), use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    st.dataframe(df_check.T, use_container_width=True)

    # EXPORTACIÓN MULTI-HOJA CON COLORES
    st.subheader("📥 Descargar Reporte Completo")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.style.map(style_func).to_excel(writer, sheet_name="Cuadrante")
        df_stats.to_excel(writer, sheet_name="Balance_44h")
        df_check.to_excel(writer, sheet_name="Validacion_Cobertura")
    
    st.download_button(
        label="⬇️ Descargar Excel (3 Hojas con Colores)",
        data=output.getvalue(),
        file_name="reporte_programacion_y_contratacion.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
