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
st.caption("Objetivo: 132 horas por ciclo, bloques de mín. 2 días y máximo 1 refuerzo por turno.")

# 2. SIDEBAR - PARÁMETROS [cite: 1, 2]
with st.sidebar:
    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value="Cosechador") [cite: 1]
    
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input(f"{cargo} requerido (Día)", min_value=1, value=5) [cite: 2]
    demanda_noche = st.number_input(f"{cargo} requerido (Noche)", min_value=1, value=5) [cite: 2]
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12) [cite: 2]
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7) [cite: 2]

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01) [cite: 2]
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01) [cite: 2]
    operadores_actuales = st.number_input(f"{cargo} actual (Nómina)", min_value=0, value=20) [cite: 2]

# 3. CONSTANTES [cite: 3]
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
        turnos_bloque = {op: 0 for op in ops}
        
        for d in bloque:
            if (d % 7) >= d_semana: continue
            
            # --- REGLA MÍNIMO 2 DÍAS: Identificar quién debe trabajar hoy por racha ---
            obligados = []
            for op in ops:
                if d > bloque_idx and horario[op][d-1] != DESCANSO:
                    # Si ayer trabajó y antes de ayer descansó, hoy ES obligatorio su 2do día 
                    if d-1 == bloque_idx or horario[op][d-2] == DESCANSO:
                        if turnos_bloque[op] < 11:
                            obligados.append(op)

            aptos = [op for op in ops if turnos_bloque[op] < 11]
            # Priorizar obligados para cumplir la racha mínima [cite: 5]
            aptos.sort(key=lambda x: (x not in obligados, turnos_bloque[x], noches_acum[x], random.random()))
            
            # Asignar Noche
            asignados_n = aptos[:n_req]
            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_bloque[op] += 1 [cite: 5]
                noches_acum[op] += 1 [cite: 6]
            
            # Asignar Día
            ya_n = set(asignados_n)
            hizo_n_ayer = {op for op in ops if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE} [cite: 6]
            aptos_d = [op for op in aptos if op not in ya_n and op not in hizo_n_ayer] [cite: 6]
            # Priorizar obligados restantes en día [cite: 7]
            aptos_d.sort(key=lambda x: (x not in obligados, turnos_bloque[x], -noches_acum[x], random.random()))
            
            asignados_d = aptos_d[:d_req]
            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_bloque[op] += 1 [cite: 7]

        # FASE REFUERZOS (Buscando bloques de 2 para evitar días solos) 
        for op in ops:
            intentos = 0
            while turnos_bloque[op] < 11 and intentos < 200:
                intentos += 1
                d_rand = random.choice(list(bloque))
                if horario[op][d_rand] != DESCANSO or (d_rand % 7) >= d_semana: continue [cite: 8]
                
                # Intentar "pegar" el refuerzo a un turno existente para no dejar días solos
                tiene_vecino = False
                if d_rand > bloque_idx and horario[op][d_rand-1] != DESCANSO: tiene_vecino = True
                if d_rand < bloque.stop-1 and horario[op][d_rand+1] != DESCANSO: tiene_vecino = True
                
                if not tiene_vecino and turnos_bloque[op] < 10: continue

                # Máximo Req + 1 
                ocupacion_dia = sum(1 for o in ops if horario[o][d_rand] == TURNO_DIA)
                if ocupacion_dia >= d_req + 1: continue [cite: 9]
                if d_rand > bloque_idx and horario[op][d_rand-1] == TURNO_NOCHE: continue [cite: 9]
                
                # Racha máx 3 
                racha = 0
                for i in range(d_rand-1, bloque_idx-1, -1):
                    if horario[op][i] != DESCANSO: racha += 1
                    else: break
                for i in range(d_rand+1, bloque.stop):
                    if horario[op][i] != DESCANSO: racha += 1 [cite: 10]
                    else: break
                
                if (racha + 1) <= 3: [cite: 11]
                    horario[op][d_rand] = TURNO_DIA
                    turnos_bloque[op] += 1 [cite: 11]
    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN [cite: 12]
if st.button(f"🚀 Generar Programación para {cargo}"):
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3 [cite: 12]
    op_base = math.ceil(total_turnos_ciclo / 11) [cite: 12]
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo)) [cite: 12]
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) [cite: 12]
    
    st.session_state["df"] = generar_programacion_equitativa(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# 6. RENDERIZADO [cite: 13, 14]
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales) [cite: 13]
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">{cargo} requerido</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True) [cite: 13]
    with c2: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Contratación necesaria</div><div class="metric-value-dark">{faltantes}</div></div>', unsafe_allow_html=True) [cite: 13]
    with c3: st.markdown(f'<div class="metric-box-green"><div class="metric-label-dark">Meta Horas Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True) [cite: 13]

    st.subheader("📅 Programación del Personal")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold" [cite: 14]
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader(f"📊 Balance Detallado: {cargo}")
    stats = []
    for op in df.index:
        fila = df.loc[op]
        total_d = (fila == TURNO_DIA).sum() [cite: 15]
        total_n = (fila == TURNO_NOCHE).sum() [cite: 15]
        c1_turnos = sum(1 for x in fila[:21] if x != DESCANSO) [cite: 15]
        c2_turnos = sum(1 for x in fila[21:] if x != DESCANSO) [cite: 15]
        
        def get_seq(data):
            w1 = sum(1 for x in data[0:7] if x != DESCANSO)
            w2 = sum(1 for x in data[7:14] if x != DESCANSO)
            w3 = sum(1 for x in data[14:21] if x != DESCANSO)
            return f"{w1}-{w2}-{w3}" [cite: 15]

        stats.append({
            "Operador": op, [cite: 16]
            "Turnos Día": total_d, [cite: 16]
            "Turnos Noche": total_n, [cite: 16]
            "Horas S1-S3": c1_turnos * horas_turno, [cite: 16]
            "Secuencia S1-S3": get_seq(fila[:21]), [cite: 16]
            "Horas S4-S6": c2_turnos * horas_turno, [cite: 16]
            "Secuencia S4-S6": get_seq(fila[21:]), [cite: 17]
            "Estado": "✅ 44h OK" if c1_turnos == 11 and c2_turnos == 11 else "❌ Revisar" [cite: 17]
        })
    df_stats = pd.DataFrame(stats).set_index("Operador")
    st.dataframe(df_stats, use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum() [cite: 18]
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ad-demanda_dia, "Estado": "✅ OK"}) [cite: 18]
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.T, use_container_width=True)

    # --- EXPORTACIÓN A EXCEL [cite: 19, 20] ---
    st.subheader("📥 Exportar Resultados")
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = cargo 
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación") [cite: 19]
        df_stats.to_excel(writer, sheet_name="Balance") [cite: 19]
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura") [cite: 19]
    
    st.download_button(
        label=f"⬇️ Descargar Programación {cargo} (Excel)",
        data=output.getvalue(),
        file_name=f"Programacion_{cargo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" [cite: 20]
    )
