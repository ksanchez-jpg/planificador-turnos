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
st.caption("Objetivo: 132h por ciclo, prioridad 4-4-3 y variantes, vinculación con COSECHA.xlsx.")

# Inicializar semilla
if 'seed' not in st.session_state:
    st.session_state['seed'] = 42

# 2. SIDEBAR - CARGA DE ARCHIVO Y PARÁMETROS
with st.sidebar:
    st.header("📂 Carga de Datos")
    # Función para adjuntar archivo Excel
    archivo_subido = st.file_uploader("Adjuntar archivo COSECHA.xlsx", type=["xlsx"])
    
    cargo_detectado = "Cosechador"
    num_fichas_detectadas = 0
    lista_fichas_reales = []

    if archivo_subido:
        # Leer todas las hojas disponibles
        excel_file = pd.ExcelFile(archivo_subido)
        hojas = excel_file.sheet_names
        # Opción para escoger hoja/cargo
        hoja_seleccionada = st.selectbox("Escoger hoja (Cargo)", hojas)
        
        # Leer la hoja seleccionada (empezando desde fila 2 automáticamente por pandas)
        df_nomina = pd.read_excel(archivo_subido, sheet_name=hoja_seleccionada)
        cargo_detectado = hoja_seleccionada
        
        # Contar fichas en columna A (índice 0)
        if not df_nomina.empty:
            lista_fichas_reales = df_nomina.iloc[:, 0].dropna().astype(str).tolist()
            num_fichas_detectadas = len(lista_fichas_reales)
            st.success(f"Detectadas {num_fichas_detectadas} fichas.")

    st.header("👤 Parámetros")
    # Se actualiza el nombre del cargo basado en la hoja
    cargo = st.text_input("Nombre del Cargo", value=cargo_detectado)
    
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input(f"{cargo} requerido (Día)", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} requerido (Noche)", min_value=1, value=5)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    # Se actualiza con la cantidad de fichas contadas
    operadores_actuales = st.number_input(f"{cargo} actual (Nómina)", min_value=0, value=num_fichas_detectadas)

# 3. CONSTANTES
SEMANAS = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN (MODELO 2x2 MIXTO + BALANCE DE SECUENCIAS)
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana, fichas_base):
    # Asignación aleatoria de fichas e identificación de vacantes
    random.seed(st.session_state['seed'])
    fichas_sorteadas = random.sample(fichas_base, len(fichas_base))
    
    identidades = []
    for i in range(n_ops):
        if i < len(fichas_sorteadas):
            identidades.append(fichas_sorteadas[i])
        else:
            identidades.append(f"VACANTE {i - len(fichas_sorteadas) + 1}")

    horario = {id: [DESCANSO] * DIAS_TOTALES for id in identidades}
    noches_acum = {id: 0 for id in identidades}
    historial_5_dias = {id: False for id in identidades}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {id: 0 for id in identidades}
        racha = {id: 0 for id in identidades} 
        turnos_semanales = {id: [0, 0, 0] for id in identidades}

        for d in bloque:
            if (d % 7) >= d_semana: continue
            sem_rel = (d - bloque_idx) // 7
            
            # Identificar obligados para completar bloque 2x2 [cite: 25]
            obligados_D, obligados_N = [], []
            for id in identidades:
                if racha[id] == 1 and turnos_bloque[id] < 11:
                    if d > 0 and horario[id][d-1] == TURNO_DIA: obligados_D.append(id)
                    else: obligados_N.append(id)

            # --- ASIGNACIÓN NOCHE ---
            cand_n = [id for id in identidades if turnos_bloque[id] < 11 and racha[id] < 2]
            random.shuffle(cand_n)
            
            asignados_n = []
            prioridad_n = [o for o in obligados_N if o in cand_n] + [o for o in obligados_D if o in cand_n and random.random() < 0.3]
            for id in prioridad_n:
                if len(asignados_n) < n_req: asignados_n.append(id)
            
            resto_n = [o for o in cand_n if o not in asignados_n]
            resto_n.sort(key=lambda x: (turnos_semanales[x][sem_rel] >= 4, turnos_bloque[x], noches_acum[x], random.random()))
            while len(asignados_n) < n_req and resto_n:
                asignados_n.append(resto_n.pop(0))

            for id in asignados_n:
                horario[id][d] = TURNO_NOCHE
                turnos_bloque[id] += 1
                turnos_semanales[id][sem_rel] += 1
                noches_acum[id] += 1
                racha[id] += 1

            # --- ASIGNACIÓN DÍA ---
            ya_n = set(asignados_n)
            cand_d = [id for id in identidades if id not in ya_n and turnos_bloque[id] < 11 and racha[id] < 2]
            if d > bloque_idx:
                cand_d = [o for o in cand_d if horario[o][d-1] != TURNO_NOCHE]
            
            asignados_d = []
            for id in [o for o in obligados_D if o in cand_d]:
                if len(asignados_d) < d_req: asignados_d.append(id)
            
            resto_d = [o for o in cand_d if o not in asignados_d]
            resto_d.sort(key=lambda x: (turnos_semanales[x][sem_rel] >= 4, turnos_bloque[x], -noches_acum[x], random.random()))
            while len(asignados_d) < d_req and resto_d:
                asignados_d.append(resto_d.pop(0))

            for id in asignados_d:
                horario[id][d] = TURNO_DIA
                turnos_bloque[id] += 1
                turnos_semanales[id][sem_rel] += 1
                racha[id] += 1

            trabajaron = set(asignados_n) | set(asignados_d)
            for id in identidades:
                if id not in trabajaron: racha[id] = 0

        # --- RELLENO FINAL PARA COMPLETAR 11 TURNOS ---
        for id in identidades:
            max_permitido = 4 if (bloque_idx == 21 and historial_5_dias[id]) else 5
            intentos = 0
            while turnos_bloque[id] < 11 and intentos < 200:
                intentos += 1
                d_rand = random.choice(list(bloque))
                sem_rand = (d_rand - bloque_idx) // 7
                if horario[id][d_rand] != DESCANSO or (d_rand % 7) >= d_semana: continue
                if turnos_semanales[id][sem_rand] >= max_permitido: continue 
                if sum(1 for o in identidades if horario[o][d_rand] == TURNO_DIA) >= d_req + 1: continue 
                if d_rand > bloque_idx and horario[id][d_rand-1] == TURNO_NOCHE: continue
                horario[id][d_rand] = TURNO_DIA
                turnos_bloque[id] += 1
                turnos_semanales[id][sem_rand] += 1
            
            if any(count >= 5 for count in turnos_semanales[id]):
                historial_5_dias[id] = True

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None:
        st.session_state['seed'] = semilla_manual
    
    total_turnos_ciclo = (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_base = math.ceil(total_turnos_ciclo / 11)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    
    # Identidades: Fichas cargadas o genéricas si no hay archivo
    fichas_a_usar = lista_fichas_reales if lista_fichas_reales else [f"Op {i+1}" for i in range(operadores_actuales)]
    
    st.session_state["df"] = generar_programacion_equitativa(op_final, demanda_dia, demanda_noche, dias_cubrir, fichas_a_usar)
    st.session_state["op_final"] = op_final

col1, col2 = st.columns(2)
with col1:
    if st.button(f"🚀 Generar Programación"):
        procesar_generacion(42)
with col2:
    if st.button("🔄 Generar Otra Versión"):
        procesar_generacion(random.randint(1, 100000))

# 6. RENDERIZADO
if "df" in st.session_state:
    df, op_final = st.session_state["df"], st.session_state["op_final"]
    faltantes = max(0, op_final - operadores_actuales)
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div>{cargo} requerido</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div>Fichas en Nómina</div><div class="metric-value-dark">{len(lista_fichas_reales)}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div>Vacantes</div><div class="metric-value-dark">{max(0, op_final - len(lista_fichas_reales))}</div></div>', unsafe_allow_html=True)

    st.subheader(f"📅 Programación: {cargo} (Por Ficha)")
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader(f"📊 Balance Detallado: {cargo}")
    stats = []
    for id_op in df.index:
        fila = df.loc[id_op]
        c1_t, c2_t = sum(1 for x in fila[:21] if x != DESCANSO), sum(1 for x in fila[21:] if x != DESCANSO)
        def get_seq(data):
            return f"{sum(1 for x in data[0:7] if x != DESCANSO)}-{sum(1 for x in data[7:14] if x != DESCANSO)}-{sum(1 for x in data[14:21] if x != DESCANSO)}"

        stats.append({
            "FICHA": id_op, "T. Día": (fila==TURNO_DIA).sum(), "T. Noche": (fila==TURNO_NOCHE).sum(),
            "Horas S1-3": c1_t * horas_turno, "Secuencia S1-3": get_seq(fila[:21]),
            "Horas S4-6": c2_t * horas_turno, "Secuencia S4-6": get_seq(fila[21:]),
            "Estado": "✅ 44h OK" if c1_t == 11 and c2_t == 11 else "❌ Revisar"
        })
    df_stats = pd.DataFrame(stats).set_index("FICHA")
    st.dataframe(df_stats, use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": ad-demanda_dia, "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "⚠️"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    # Exportación
    output = io.BytesIO()
    df_excel = df.copy()
    df_excel.index.name = "FICHA" 
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_excel.style.map(style_func).to_excel(writer, sheet_name="Programación")
        df_stats_excel = df_stats.copy()
        df_stats_excel.insert(0, 'Cargo', cargo)
        df_stats_excel.to_excel(writer, sheet_name="Balance")
        pd.DataFrame(check).to_excel(writer, sheet_name="Cobertura")
    
    st.download_button(label=f"⬇️ Descargar Excel {cargo}", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
