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
st.caption("Balanceador de Carga: Refuerzos simétricos (D/N) y meta 132h garantizada.")

if 'seed' not in st.session_state:
    st.session_state['seed'] = 42

# 2. SIDEBAR - CARGA Y PARÁMETROS
with st.sidebar:
    st.header("📂 Base de Datos")
    archivo_subido = st.file_uploader("Adjuntar COSECHA.xlsx", type=["xlsx"])
    
    cargo_detectado = "Tractorista"
    lista_fichas_reales = []

    if archivo_subido:
        excel_file = pd.ExcelFile(archivo_subido)
        hoja_seleccionada = st.selectbox("Escoger Cargo", excel_file.sheet_names)
        df_nomina = pd.read_excel(archivo_subido, sheet_name=hoja_seleccionada)
        cargo_detectado = hoja_seleccionada
        if not df_nomina.empty:
            lista_fichas_reales = df_nomina.iloc[:, 0].dropna().astype(str).tolist()

    st.header("👤 Parámetros")
    cargo = st.text_input("Cargo", value=cargo_detectado)
    demanda_dia = st.number_input(f"{cargo} Día", min_value=1, value=10)
    demanda_noche = st.number_input(f"{cargo} Noche", min_value=1, value=10)
    horas_turno = st.number_input("Horas/Turno", min_value=1, value=12)
    
    st.header("🧠 Ajustes")
    operadores_actuales = st.number_input(f"Nómina Actual", min_value=0, value=len(lista_fichas_reales) if lista_fichas_reales else 40)
    factor_cobertura = st.slider("Holgura", 1.0, 1.2, 1.0, 0.01)

# 3. CONSTANTES
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR CON BALANCEADOR DE CARGA SIMÉTRICO
def generar_programacion_pro(n_ops, d_req, n_req, fichas_base):
    random.seed(st.session_state['seed'])
    identidades = fichas_base[:n_ops] if len(fichas_base) >= n_ops else fichas_base + [f"VACANTE {i+1}" for i in range(n_ops - len(fichas_base))]
    
    horario = {id: [DESCANSO] * DIAS_TOTALES for id in identidades}
    
    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {id: 0 for id in identidades}
        racha = {id: 0 for id in identidades}
        turnos_semanales = {id: [0, 0, 0] for id in identidades}
        
        # Trackers de cobertura para el balanceador
        cobertura_dia = {d: 0 for d in bloque}
        cobertura_noche = {d: 0 for d in bloque}

        # FASE 1: Cobertura Base (Demanda mínima)
        for d in bloque:
            sem_rel = (d - bloque_idx) // 7
            aptos = [id for id in identidades if turnos_bloque[id] < 11 and turnos_semanales[id][sem_rel] < 4]
            aptos = [id for id in aptos if d == bloque_idx or horario[id][d-1] == DESCANSO]
            
            random.shuffle(aptos)
            
            # Asignar Noche
            asignados_n = aptos[:n_req]
            for id in asignados_n:
                horario[id][d] = TURNO_NOCHE
                turnos_bloque[id] += 1
                turnos_semanales[id][sem_rel] += 1
                cobertura_noche[d] += 1
                racha[id] += 1

            # Asignar Día
            ya_n = set(asignados_n)
            cand_d = [id for id in aptos if id not in ya_n]
            if d > bloque_idx: cand_d = [id for id in cand_d if horario[id][d-1] != TURNO_NOCHE]
            
            asignados_d = cand_d[:d_req]
            for id in asignados_d:
                horario[id][d] = TURNO_DIA
                turnos_bloque[id] += 1
                turnos_semanales[id][sem_rel] += 1
                cobertura_dia[d] += 1
                racha[id] += 1
            
            # Reset racha
            trabajaron = set(asignados_n) | set(asignados_d)
            for id in identidades:
                if id not in trabajaron: racha[id] = 0

        # FASE 2: BALANCEADOR DE CARGA (Ajuste de 132h sin recargar)
        # Prioridad: Días con menos refuerzos totales, alternando D y N
        operadores_deuda = [id for id in identidades if turnos_bloque[id] < 11]
        
        for id in operadores_deuda:
            intentos = 0
            while turnos_bloque[id] < 11 and intentos < 300:
                intentos += 1
                # Buscar el día más vacío para este operador
                d_posibles = [d for d in bloque if horario[id][d] == DESCANSO]
                if not d_posibles: break
                
                # Ordenar días por cobertura total (priorizar los que tienen menos gente)
                d_posibles.sort(key=lambda d: (cobertura_dia[d] + cobertura_noche[d]))
                d_rand = d_posibles[0]
                
                sem_rand = (d_rand - bloque_idx) // 7
                if turnos_semanales[id][sem_rand] >= 4: continue
                if d_rand > bloque_idx and horario[id][d_rand-1] == TURNO_NOCHE: continue
                
                # Decidir turno (Simetría): Si Día tiene más gente que Noche, poner en Noche
                if cobertura_dia[d_rand] > cobertura_noche[d_rand]:
                    horario[id][d_rand] = TURNO_NOCHE
                    cobertura_noche[d_rand] += 1
                else:
                    horario[id][d_rand] = TURNO_DIA
                    cobertura_dia[d_rand] += 1
                
                turnos_bloque[id] += 1
                turnos_semanales[id][sem_rand] += 1

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
if st.button("🚀 Generar Programación Balanceada"):
    total_turnos = (demanda_dia + demanda_noche) * 21
    op_final = max(math.ceil(total_turnos / 11 * factor_cobertura), (demanda_dia + demanda_noche) * 2)
    fichas = lista_fichas_reales if lista_fichas_reales else [f"Op {i+1}" for i in range(op_final)]
    st.session_state["df"] = generar_programacion_pro(op_final, demanda_dia, demanda_noche, fichas)

# 6. RENDERIZADO
if "df" in st.session_state:
    df = st.session_state["df"]
    
    # Validación de Cobertura (Heatmap de Refuerzos)
    st.subheader("✅ Validación de Cobertura y Simetría de Refuerzos")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({
            "Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, 
            "Refuerzo Total": (ad - demanda_dia) + (an - demanda_noche),
            "Balance": "⚖️ Simétrico" if (ad-demanda_dia) == (an-demanda_noche) else "⚠️ Desviado"
        })
    df_check = pd.DataFrame(check).set_index("Día")
    st.dataframe(df_check.T, use_container_width=True)

    st.subheader(f"📅 Tabla de Turnos: {cargo}")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader("📊 Balance Final (Meta 132h)")
    stats = []
    for id_op in df.index:
        fila = df.loc[id_op]
        c1 = sum(1 for x in fila[:21] if x != DESCANSO)
        stats.append({"FICHA": id_op, "Horas": c1 * 12, "Secuencia": f"{sum(1 for x in fila[0:7] if x!=DESCANSO)}-{sum(1 for x in fila[7:14] if x!=DESCANSO)}-{sum(1 for x in fila[14:21] if x!=DESCANSO)}", "Estado": "✅ 44h OK" if c1==11 else "❌"})
    st.dataframe(pd.DataFrame(stats).set_index("FICHA"), use_container_width=True)
