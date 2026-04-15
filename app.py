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

st.title("🗓 PROGRAMACIÓN DE TURNOS PRO")
st.caption("Objetivo: 132h por ciclo, modelo 2x2 mixto, refuerzos simétricos y balance individual Día/Noche.")

if 'seed' not in st.session_state:
    st.session_state['seed'] = 42

# 2. SIDEBAR - PARÁMETROS E INTEGRACIÓN EXCEL [cite: 26-27]
with st.sidebar:
    st.header("📂 Base de Datos")
    archivo_subido = st.file_uploader("Adjuntar archivo COSECHA.xlsx", type=["xlsx"])
    
    cargo_detectado = "Cosechador"
    num_fichas_detectadas = 0
    lista_fichas_reales = []

    if archivo_subido:
        excel_file = pd.ExcelFile(archivo_subido)
        hoja_seleccionada = st.selectbox("Escoger hoja (Cargo)", excel_file.sheet_names)
        df_nomina = pd.read_excel(archivo_subido, sheet_name=hoja_seleccionada)
        cargo_detectado = hoja_seleccionada
        if not df_nomina.empty:
            lista_fichas_reales = df_nomina.iloc[:, 0].dropna().astype(str).tolist()
            num_fichas_detectadas = len(lista_fichas_reales)
            st.success(f"Detección: {num_fichas_detectadas} operadores.")

    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value=cargo_detectado)
    demanda_dia = st.number_input(f"{cargo} Día", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} Noche", min_value=1, value=5)
    horas_turno = st.number_input("Horas/turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir", 1, 7, 7)
    operadores_actuales = st.number_input(f"{cargo} actual", min_value=0, value=num_fichas_detectadas)
    factor_cobertura = st.slider("Holgura técnica", 1.0, 1.5, 1.0, 0.01)

# 3. CONSTANTES
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN (CON BALANCE INDIVIDUAL D/N) [cite: 28-42]
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana, fichas_base):
    random.seed(st.session_state['seed'])
    fichas_sorteadas = random.sample(fichas_base, len(fichas_base)) if fichas_base else []
    identidades = []
    for i in range(n_ops):
        if i < len(fichas_sorteadas): identidades.append(fichas_sorteadas[i])
        else: identidades.append(f"VACANTE {i - len(fichas_sorteadas) + 1}")

    horario = {id: [DESCANSO] * DIAS_TOTALES for id in identidades}
    
    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {id: 0 for id in identidades}
        racha = {id: 0 for id in identidades}
        turnos_semanales = {id: [0, 0, 0] for id in identidades}
        
        cob_dia = {d: 0 for d in bloque}
        cob_noche = {d: 0 for d in bloque}

        # FASE 1: Cobertura Base 2x2 [cite: 29-39]
        for d in bloque:
            if (d % 7) >= d_semana: continue
            sem_rel = (d - bloque_idx) // 7
            aptos = [id for id in identidades if turnos_bloque[id] < 11 and turnos_semanales[id][sem_rel] < 4]
            aptos = [id for id in aptos if d < 1 or horario[id][d-1] == DESCANSO]
            random.shuffle(aptos)

            # Noche
            asignados_n = aptos[:n_req]
            for id in asignados_n:
                horario[id][d], turnos_bloque[id], turnos_semanales[id][sem_rel] = TURNO_NOCHE, turnos_bloque[id]+1, turnos_semanales[id][sem_rel]+1
                cob_noche[d], racha[id] = cob_noche[d]+1, racha[id]+1

            # Día (Respetando descanso post-noche) [cite: 35]
            ya_n = set(asignados_n)
            cand_d = [id for id in aptos if id not in ya_n]
            if d > bloque_idx: cand_d = [o for o in cand_d if horario[o][d-1] != TURNO_NOCHE]
            asignados_d = cand_d[:d_req]
            for id in asignados_d:
                horario[id][d], turnos_bloque[id], turnos_semanales[id][sem_rel] = TURNO_DIA, turnos_bloque[id]+1, turnos_semanales[id][sem_rel]+1
                cob_dia[d], racha[id] = cob_dia[d]+1, racha[id]+1

            for id in identidades:
                if id not in (set(asignados_n) | set(asignados_d)): racha[id] = 0

        # FASE 2: AJUSTE FINAL CON BALANCE INDIVIDUAL (Evita 7D/15N) 
        for id in identidades:
            while turnos_bloque[id] < 11:
                dias_ordenados = sorted(list(bloque), key=lambda x: (cob_dia[x] + cob_noche[x]))
                asignado = False
                for d_optimo in dias_ordenados:
                    if (d_optimo % 7) >= d_semana or horario[id][d_optimo] != DESCANSO: continue
                    sem_rel = (d_optimo - bloque_idx) // 7
                    if turnos_semanales[id][sem_rel] >= 4 or (d_optimo > bloque_idx and horario[id][d_optimo-1] == TURNO_NOCHE): continue
                    
                    # --- BALANCEADOR PERSONAL ---
                    t_dia_op = sum(1 for d_idx in range(DIAS_TOTALES) if horario[id][d_idx] == TURNO_DIA)
                    t_noche_op = sum(1 for d_idx in range(DIAS_TOTALES) if horario[id][d_idx] == TURNO_NOCHE)
                    
                    # Preferencia según déficit personal
                    pref = TURNO_DIA if t_dia_op <= t_noche_op else TURNO_NOCHE
                    alt = TURNO_NOCHE if pref == TURNO_DIA else TURNO_DIA
                    
                    # Intentar preferencia respetando tope de 1 refuerzo por turno 
                    if pref == TURNO_DIA and cob_dia[d_optimo] < d_req + 1:
                        horario[id][d_optimo], cob_dia[d_optimo], asignado = TURNO_DIA, cob_dia[d_optimo]+1, True
                    elif pref == TURNO_NOCHE and cob_noche[d_optimo] < n_req + 1:
                        horario[id][d_optimo], cob_noche[d_optimo], asignado = TURNO_NOCHE, cob_noche[d_optimo]+1, True
                    # Si no, intentar la alternativa
                    elif alt == TURNO_DIA and cob_dia[d_optimo] < d_req + 1:
                        horario[id][d_optimo], cob_dia[d_optimo], asignado = TURNO_DIA, cob_dia[d_optimo]+1, True
                    elif alt == TURNO_NOCHE and cob_noche[d_optimo] < n_req + 1:
                        horario[id][d_optimo], cob_noche[d_optimo], asignado = TURNO_NOCHE, cob_noche[d_optimo]+1, True
                    
                    if asignado:
                        turnos_bloque[id], turnos_semanales[id][sem_rel] = turnos_bloque[id]+1, turnos_semanales[id][sem_rel]+1
                        break
                if not asignado: break
    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN [cite: 43]
def procesar_generacion():
    total_turnos = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_final = max(math.ceil(total_turnos / 11 * factor_cobertura), (demanda_dia + demanda_noche) * 2)
    st.session_state["df"] = generar_programacion_equitativa(op_final, demanda_dia, demanda_noche, dias_cubrir, lista_fichas_reales)
    st.session_state["op_final"] = op_final

if st.button("🚀 Generar Programación Balanceada"): procesar_generacion()

# 6. RENDERIZADO [cite: 44-48]
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    
    st.subheader(f"📊 Balance Detallado: {cargo}")
    stats = []
    for id_op in df.index:
        f = df.loc[id_op]
        c1, c2 = sum(1 for x in f[:21] if x != DESCANSO), sum(1 for x in f[21:] if x != DESCANSO)
        stats.append({
            "FICHA": id_op, "T. Día": (f==TURNO_DIA).sum(), "T. Noche": (f==TURNO_NOCHE).sum(),
            "Horas S1-3": c1 * horas_turno, "Secuencia S1-3": f"{sum(1 for x in f[0:7] if x!=DESCANSO)}-{sum(1 for x in f[7:14] if x!=DESCANSO)}-{sum(1 for x in f[14:21] if x!=DESCANSO)}",
            "Horas S4-6": c2 * horas_turno, "Secuencia S4-6": f"{sum(1 for x in f[21:28] if x!=DESCANSO)}-{sum(1 for x in f[28:35] if x!=DESCANSO)}-{sum(1 for x in f[35:42] if x!=DESCANSO)}",
            "Estado": "✅ 44h OK" if c1 == 11 and c2 == 11 else "❌"
        })
    st.dataframe(pd.DataFrame(stats).set_index("FICHA"), use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": (ad-demanda_dia)+(an-demanda_noche), "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "⚠️"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    st.subheader("📅 Programación Completa")
    st.dataframe(df.style.map(lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"), use_container_width=True)
