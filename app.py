import streamlit as st
import math
import pandas as pd
import io
import random

# 1. CONFIGURACIÓN Y ESTILO
st.set_page_config(page_title="Programación de Turnos 44H", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.metric-box-green { background: #10B981; color: #064E3B; border-radius: 8px; padding: 1.2rem; text-align: center; }
.metric-value-dark { font-size: 2.2rem; font-family: monospace; font-weight: 700; }
.stButton > button { background: #0F172A; color: #F8FAFC; border-radius: 4px; width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🗓 PROGRAMACIÓN DE TURNOS")
st.caption("Objetivo: 132h exactas, Bloques 2-3 días, Máximo 1 refuerzo/turno.")

# 2. SIDEBAR
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

# 4. MOTOR DE PROGRAMACIÓN RECONSTRUIDO
def generar_programacion_blindada(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(44) # Nueva semilla para balance
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    
    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        racha_consecutiva = {op: 0 for op in ops}
        ultimo_turno = {op: None for op in ops}

        for d in bloque:
            dia_sem = d % 7
            if dia_sem >= d_semana: continue

            # --- 1. PRIORIDAD: QUIÉNES TIENEN QUE TRABAJAR POR REGLA MIN 2 ---
            obligados = [op for op in ops if racha_consecutiva[op] == 1]
            # --- 2. ELIGIBLES: QUIÉNES PUEDEN TRABAJAR (No racha 3, No N->D, Turnos < 11) ---
            disponibles = []
            for op in ops:
                if op in obligados: continue
                if turnos_bloque[op] >= 11: continue
                if racha_consecutiva[op] >= 3: continue
                # Regla Noche -> Día
                if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE: continue
                disponibles.append(op)

            random.shuffle(disponibles)
            
            # --- 3. ASIGNACIÓN DE NOCHE (Cupo estricto) ---
            asignados_n = []
            # Primero obligados que venían de noche
            for op in obligados:
                if len(asignados_n) < n_req and ultimo_turno[op] == TURNO_NOCHE:
                    asignados_n.append(op)
            # Luego resto de obligados y luego disponibles
            resto_n = [o for o in obligados + disponibles if o not in asignados_n]
            resto_n.sort(key=lambda x: (turnos_bloque[x], random.random()))
            
            while len(asignados_n) < n_req and resto_n:
                asignados_n.append(resto_n.pop(0))

            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_bloque[op] += 1
                racha_consecutiva[op] += 1
                ultimo_turno[op] = TURNO_NOCHE

            # --- 4. ASIGNACIÓN DE DÍA (Cupo Req + 1 Máximo) ---
            asignados_d = []
            ya_asignados = set(asignados_n)
            
            # Candidatos para día: Obligados que faltan y disponibles (filtrando N->D)
            cand_d = [o for o in obligados + disponibles if o not in ya_asignados]
            # Filtro estricto N->D para disponibles
            cand_d = [o for o in cand_d if not (d > bloque_idx and horario[o][d-1] == TURNO_NOCHE)]
            
            cand_d.sort(key=lambda x: (turnos_bloque[x], random.random()))
            
            # Límite de refuerzo dinámico: si sobran muchos turnos en el ciclo, permitimos d_req + 1
            max_dia = d_req + 1 if (sum(turnos_bloque.values()) < (n_ops * 11 * 0.9)) else d_req
            # Forzamos que nunca pase de d_req + 1
            max_dia = min(max_dia, d_req + 1)

            while len(asignados_d) < max_dia and cand_d:
                asignados_d.append(cand_d.pop(0))
            
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_bloque[op] += 1
                racha_consecutiva[op] += 1
                ultimo_turno[op] = TURNO_DIA

            # --- 5. LIMPIEZA DE RACHAS ---
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron:
                    racha_consecutiva[op] = 0
                    ultimo_turno[op] = None

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button(f"🚀 Generar Programación Blindada {cargo}"):
    total_turnos = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_final = math.ceil((total_turnos / 11) * factor_cobertura / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    st.session_state["df"] = generar_programacion_blindada(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# 6. RENDERIZADO
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div class="metric-label">Necesarios</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div class="metric-label">Contratar</div><div class="metric-value-dark">{max(0, op_final-operadores_actuales)}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div class="metric-label">Meta</div><div class="metric-value-dark">132h</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación del Personal")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    # Balance Detallado (A1 con Cargo)
    st.subheader(f"📊 Balance Detallado: {cargo}")
    stats = []
    for op in df.index:
        f = df.loc[op]
        d1, n1 = (f[:21]==TURNO_DIA).sum(), (f[:21]==TURNO_NOCHE).sum()
        d2, n2 = (f[21:]==TURNO_DIA).sum(), (f[21:]==TURNO_NOCHE).sum()
        stats.append({"Operador": op, "T. Día": d1+d2, "T. Noche": n1+n2, "Horas S1-3": (d1+n1)*12, "Horas S4-6": (d2+n2)*12, "Estado": "✅ 44h OK" if (d1+n1)==11 else "❌"})
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)

    # Cobertura
    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ad-demanda_dia, "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "❌"})
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.T, use_container_width=True)

    # Exportación
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats.to_excel(writer, sheet_name="Balance")
        df_check.to_excel(writer, sheet_name="Cobertura")
    st.download_button(label=f"📥 Descargar Programación {cargo}", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
