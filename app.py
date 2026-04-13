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
st.caption("Objetivo: 132 horas por ciclo, máximo 1 refuerzo por turno con programación inteligente.")

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

# 4. MOTOR DE PROGRAMACIÓN
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(42)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        
        for d in bloque:
            if (d % 7) >= d_semana: continue
            aptos = [op for op in ops if turnos_bloque[op] < 11]
            aptos = [op for op in aptos if d < 1 or horario[op][d-1] == DESCANSO or (d > 1 and horario[op][d-2] == DESCANSO)]
            
            aptos.sort(key=lambda x: (turnos_bloque[x], noches_acum[x], random.random()))
            asignados_n = aptos[:n_req]
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_bloque[op] += 1
                noches_acum[op] += 1
            
            ya_n = set(asignados_n)
            hizo_n_ayer = {op for op in ops if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE}
            aptos_d = [op for op in aptos if op not in ya_n and op not in hizo_n_ayer]
            aptos_d.sort(key=lambda x: (turnos_bloque[x], -noches_acum[x], random.random()))
            
            asignados_d = aptos_d[:d_req]
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_bloque[op] += 1

        for op in ops:
            intentos = 0
            while turnos_bloque[op] < 11 and intentos < 100:
                intentos += 1
                d_rand = random.choice(list(bloque))
                if horario[op][d_rand] != DESCANSO or (d_rand % 7) >= d_semana: continue
                ocupacion_dia = sum(1 for o in ops if horario[o][d_rand] == TURNO_DIA)
                if ocupacion_dia >= d_req + 1: continue 
                if d_rand > bloque_idx and horario[op][d_rand-1] == TURNO_NOCHE: continue
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
if st.button(f"🚀 Generar Programación para {cargo}"):
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_base = math.ceil(total_turnos_ciclo / 11)
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
    with c2: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Contratación necesaria</div><div class="metric-value-dark">{faltantes}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Meta Horas Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación del Personal")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader(f"📊 Balance Detallado: {cargo}")
    stats = []
    for op in df.index:
        fila = df.loc[op]
        total_d = (fila == TURNO_DIA).sum()
        total_n = (fila == TURNO_NOCHE).sum()
        c1_turnos = sum(1 for x in fila[:21] if x != DESCANSO)
        c2_turnos = sum(1 for x in fila[21:] if x != DESCANSO)
        
        def get_seq(data):
            w1 = sum(1 for x in data[0:7] if x != DESCANSO)
            w2 = sum(1 for x in data[7:14] if x != DESCANSO)
            w3 = sum(1 for x in data[14:21] if x != DESCANSO)
            return f"{w1}-{w2}-{w3}"

        stats.append({
            "Operador": op,
            "Turnos Día": total_d,
            "Turnos Noche": total_n,
            "Horas S1-S3": c1_turnos * horas_turno,
            "Secuencia S1-S3": get_seq(fila[:21]),
            "Horas S4-S6": c2_turnos * horas_turno,
            "Secuencia S4-S6": get_seq(fila[21:]),
            "Estado": "✅ 44h OK" if c1_turnos == 11 and c2_turnos == 11 else "❌ Revisar"
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

    # --- EXPORTACIÓN A EXCEL MEJORADA SEGÚN IMAGEN 2 ---
    st.subheader("📥 Exportar Resultados")
    output = io.BytesIO()
    
    # Preparar DF para exportación: El nombre del índice será el valor de la celda A1
    df_excel = df.copy()
    df_excel.index.name = cargo 

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Hoja 1: Programación (Empieza en A1 con el nombre del cargo como cabecera del índice)
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        
        # Hoja 2: Balance Detallado
        df_stats_excel = df_stats.copy()
        df_stats_excel.insert(0, 'Cargo', cargo) # Reinsertamos columna cargo para el balance
        df_stats_excel.to_excel(writer, sheet_name="Balance")
        
        # Hoja 3: Cobertura
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    
    st.download_button(
        label=f"⬇️ Descargar Programación {cargo} (Excel)",
        data=output.getvalue(),
        file_name=f"Programacion_{cargo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
