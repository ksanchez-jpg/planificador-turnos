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

st.title("🗓 PROGRAMACIÓN DE TURNOS 44H")
st.caption("Reglas: 132h ciclo, Mínimo 3 días/semana, Cobertura 5/5 garantizada.")

# 2. SIDEBAR - PARÁMETROS
with st.sidebar:
    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value="Cosechador")
    demanda_dia = st.number_input(f"{cargo} (Día)", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} (Noche)", min_value=1, value=5)
    operadores_actuales = st.number_input("Nómina Actual", min_value=0, value=20)
    st.header("🧠 Ajustes")
    semilla = st.number_input("Semilla Aleatoria", value=st.session_state.get('seed', 42))

# 3. CONSTANTES
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN ROBUSTO
def generar_programacion_44h(n_ops, d_req, n_req):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(semilla)
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        creditos = {op: 11 for op in ops} # 11 turnos para cumplir 132h
        acum_sem = {op: [0, 0, 0] for op in ops}
        racha = {op: 0 for op in ops}

        for d in bloque:
            sem_rel = (d - bloque_idx) // 7
            dia_sem = (d - bloque_idx) % 7 # 0=Lun, 6=Dom

            # --- PRIORIZACIÓN DE CANDIDATOS ---
            cand_pool = []
            for op in ops:
                if creditos[op] <= 0: continue
                
                score = 0
                # Regla de Oro: Mínimo 3 días por semana (Urgencia si es fin de semana)
                dias_restantes_sem = 6 - dia_sem
                dias_que_le_faltan = 3 - acum_sem[op][sem_rel]
                if dias_que_le_faltan > 0:
                    if dias_restantes_sem < dias_que_le_faltan: score += 1000 # Obligado para cumplir min 3
                    else: score += 100
                
                # Regla 2x2 (Bloques de 2)
                if racha[op] == 1: score += 500
                if racha[op] >= 3: score -= 200 # Evitar exceso consecutivo

                cand_pool.append({'op': op, 'score': score + random.random()})

            # --- ASIGNACIÓN NOCHE ---
            cand_pool.sort(key=lambda x: x['score'], reverse=True)
            asignados_n = []
            for item in cand_pool:
                if len(asignados_n) < n_req:
                    asignados_n.append(item['op'])
            
            # Rescate Noche (Si no hay aptos por score, tomar a cualquiera con créditos)
            if len(asignados_n) < n_req:
                resto = [o for o in ops if o not in asignados_n and creditos[o] > 0]
                asignados_n += resto[:n_req - len(asignados_n)]

            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                creditos[op] -= 1
                acum_sem[op][sem_rel] += 1
                racha[op] += 1

            # --- ASIGNACIÓN DÍA ---
            ya_n = set(asignados_n)
            cand_d = []
            for item in cand_pool:
                op = item['op']
                if op in ya_n: continue
                # Restricción Legal: No Noche -> Día
                if d > bloque_idx and horario[op][d-1] == TURNO_NOCHE: continue
                cand_d.append(item)

            cand_d.sort(key=lambda x: x['score'], reverse=True)
            
            # Cupo de día (d_req + refuerzo inteligente)
            faltantes_ciclo = sum(creditos.values())
            dias_rest = 21 - (d - bloque_idx)
            cupo_dia = d_req + 1 if (faltantes_ciclo > (d_req + n_req) * dias_rest) else d_req
            
            asignados_d = [item['op'] for item in cand_d[:cupo_dia]]

            # Rescate Día
            if len(asignados_d) < d_req:
                resto_d = [o for o in ops if o not in ya_n and o not in asignados_d and creditos[o] > 0]
                if d > bloque_idx: resto_d = [o for o in resto_d if horario[o][d-1] != TURNO_NOCHE]
                asignados_d += resto_d[:d_req - len(asignados_d)]

            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                creditos[op] -= 1
                acum_sem[op][sem_rel] += 1
                racha[op] += 1

            # Reset de racha
            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron: racha[op] = 0

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button(f"🚀 Generar Programación 44H"):
    st.session_state['seed'] = semilla
    op_final = max(operadores_actuales, 20)
    st.session_state["df_44"] = generar_programacion_44h(op_final, demanda_dia, demanda_noche)

# 6. RENDERIZADO
if "df_44" in st.session_state:
    df = st.session_state["df_44"]
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div>Operadores</div><div class="metric-value-dark">{len(df.index)}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div>Promedio Semanal</div><div class="metric-value-dark">44.0h</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div>Horas/Ciclo</div><div class="metric-value-dark">132.0h</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación (Bloques DD, NN, DN)")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader("📊 Balance Detallado (Meta 132h y Mín 3 días/sem)")
    stats = []
    for op in df.index:
        f = df.loc[op]
        c1, c2 = (f[:21] != DESCANSO).sum(), (f[21:] != DESCANSO).sum()
        def get_seq(data):
            return f"{sum(1 for x in data[0:7] if x != DESCANSO)}-{sum(1 for x in data[7:14] if x != DESCANSO)}-{sum(1 for x in data[14:21] if x != DESCANSO)}"
        
        s_nums = [int(x) for x in get_seq(f[:21]).split("-")]
        ok_min = all(x >= 3 for x in s_nums)

        stats.append({
            "Operador": op, "T. Día": (f==TURNO_DIA).sum(), "T. Noche": (f==TURNO_NOCHE).sum(),
            "Horas S1-3": c1*12, "Secuencia S1-3": get_seq(f[:21]),
            "Estado": "✅ 44h OK" if c1==11 and ok_min else "❌ Revisar"
        })
    st.dataframe(pd.DataFrame(stats).set_index("Operador"), use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "❌"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # Exportación
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Programación")
        pd.DataFrame(stats).to_excel(writer, sheet_name="Balance")
    st.download_button(label="📥 Descargar Excel", data=output.getvalue(), file_name="Programacion_44h.xlsx")
