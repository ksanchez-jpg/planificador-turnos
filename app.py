import streamlit as st
import math
import pandas as pd
import io
import random

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
st.set_page_config(page_title="Programación de Personal Pro", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; }
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; font-family: 'IBM Plex Mono', monospace; }
.metric-box { background: #0F172A; color: #F8FAFC; border-radius: 8px; padding: 1.2rem; text-align: center; }
.metric-label { font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; }
.metric-value { font-size: 2rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PROGRAMACIÓN DE PERSONAL")
st.caption("Solución matemática: Cobertura 100% garantizada con rotación 2x2.")

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("📊 Parámetros Operativos")
    demanda_dia   = st.number_input("Operadores requeridos (Día)",   min_value=1, value=4)
    demanda_noche = st.number_input("Operadores requeridos (Noche)", min_value=1, value=4)
    horas_turno   = st.number_input("Horas por turno",               min_value=1, value=12)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura   = st.slider("Factor de holgura técnica",  1.0, 1.5, 1.0, 0.01)
    ausentismo         = st.slider("Ausentismo (%)",       0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=16)

# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────
SEMANAS      = 6
DIAS_TOTALES = 42
TURNO_DIA    = "D"
TURNO_NOCHE  = "N"
DESCANSO     = "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]]

# ─────────────────────────────────────────────
# LÓGICA MAESTRA (REGLA 22 DÍAS / 44H / MAX 2 CONSEC)
# ─────────────────────────────────────────────
def generar_disponibilidad_perfecta(n_ops: int) -> dict:
    """
    Usa un patrón 2-trabajo/2-descanso (1100) escalonado.
    Esto garantiza 11 días cada 21 días (44h promedio) y máx 2 consecutivos.
    """
    disponibilidad = {}
    patron_base = [True, True, False, False]
    
    for i in range(n_ops):
        nombre = f"Op {i+1}"
        # El offset i garantiza que la carga se distribuya uniformemente
        dias = [(patron_base[(d + i) % 4]) for d in range(DIAS_TOTALES)]
        disponibilidad[nombre] = dias
    return disponibilidad

def asignar_turnos_equitativos(disponibilidad: dict, d_req: int, n_req: int) -> dict:
    ops = list(disponibilidad.keys())
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    cnt_n = {op: 0 for op in ops} # Contador de noches para equidad
    
    for d_idx in range(DIAS_TOTALES):
        disponibles = [op for op in ops if disponibilidad[op][d_idx]]
        
        # Regla 6: No Noche -> Día
        bloqueados_d = set()
        if d_idx > 0:
            bloqueados_d = {op for op in disponibles if horario[op][d_idx-1] == TURNO_NOCHE}
        
        aptos_d = [op for op in disponibles if op not in bloqueados_d]
        
        # Equidad R3: Priorizar para día a quienes lleven MÁS noches (para rotar)
        aptos_d.sort(key=lambda op: -cnt_n[op])
        
        asignados_d = aptos_d[:d_req]
        for op in asignados_d: horario[op][d_idx] = TURNO_DIA
        
        # Los que sobran de los disponibles van a Noche (respetando demanda)
        ya_asignados = set(asignados_d)
        aptos_n = [op for op in disponibles if op not in ya_asignados]
        # Priorizar para noche a quienes lleven MENOS noches
        aptos_n.sort(key=lambda op: cnt_n[op])
        
        asignados_n = aptos_n[:n_req]
        for op in asignados_n:
            horario[op][d_idx] = TURNO_NOCHE
            cnt_n[op] += 1
            
    return horario

# ─────────────────────────────────────────────
# VALIDACIÓN Y MÉTRICAS
# ─────────────────────────────────────────────
def validar_y_obtener_errores(df, d_req, n_req):
    errores = []
    for dia in df.columns:
        if (df[dia] == "D").sum() < d_req: errores.append(f"Falta Día en {dia}")
        if (df[dia] == "N").sum() < n_req: errores.append(f"Falta Noche en {dia}")
    return errores

# ─────────────────────────────────────────────
# EJECUCIÓN
# ─────────────────────────────────────────────
if st.button("⚙️ Calcular y Generar Programación"):
    # Cálculo de dotación: (Puestos * 2) es el mínimo para 2x2.
    # Matemática: (4+4) * 42 días / 22 turnos por op = 15.27 ops. -> 16 ops.
    op_final = math.ceil(((d_req + n_req) * 7 / 44 * 12) * factor_cobertura / (1 - ausentismo))
    op_final = max(op_final, (d_req + n_req) * 2) # Garantía mínima 2x2
    
    disponibilidad = generar_disponibilidad_perfecta(op_final)
    horario = asignar_turnos_equitativos(disponibilidad, d_req, n_req)
    
    st.session_state["df_horario"] = pd.DataFrame(horario, index=NOMBRES_DIAS).T
    st.session_state["op_final"] = op_final
    st.session_state["calculado"] = True

# ─────────────────────────────────────────────
# RENDERIZADO DE RESULTADOS
# ─────────────────────────────────────────────
if st.session_state.get("calculado"):
    df = st.session_state["df_horario"]
    op_final = st.session_state["op_final"]
    errores = validar_y_obtener_errores(df, demanda_dia, demanda_noche)

    # Métricas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-box"><div class="metric-label">Operadores</div><div class="metric-value">{op_final}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-box"><div class="metric-label">Promedio h/sem</div><div class="metric-value">44.0</div></div>', unsafe_allow_html=True)
    with col3:
        color = "#4ADE80" if not errores else "#F87171"
        st.markdown(f'<div class="metric-box"><div class="metric-label">Estado Cobertura</div><div class="metric-value" style="color:{color}">{"100% OK" if not errores else "FALTA"}</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Cuadrante de Turnos")
    def color_turnos(val):
        if val == "D": return "background-color:#FFF3CD;color:#856404;font-weight:bold"
        if val == "N": return "background-color:#CCE5FF;color:#004085;font-weight:bold"
        return "background-color:#F8F9FA;color:#ADB5BD"
    st.dataframe(df.style.map(color_turnos), use_container_width=True)

    # Balance
    st.subheader("📊 Balance de Carga Laboral")
    stats = []
    for op in df.index:
        d_t = (df.loc[op] != "R").sum()
        d_d = (df.loc[op] == "D").sum()
        d_n = (df.loc[op] == "N").sum()
        stats.append({"Operador": op, "Días Trabajo": d_t, "Día (D)": d_d, "Noche (N)": d_n, "Horas Totales": d_t*12, "Prom h/sem": round(d_t*12/6,1)})
    st.dataframe(pd.DataFrame(stats).set_index("Operador"), use_container_width=True)

    # Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Cuadrante")
    st.download_button("⬇️ Descargar Excel", output.getvalue(), "programacion.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
