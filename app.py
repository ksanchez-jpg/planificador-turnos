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
st.caption("Objetivo: 132h por ciclo, modelo 2x2 mixto, máximo 4 días/semana y refuerzos balanceados.")

if 'seed' not in st.session_state:
    st.session_state['seed'] = 42

# --- BLOQUE DE EXCEL (COSECHA.xlsx) ---
fichas_cargadas = []
cargo_sugerido = "Cosechador"
conteo_sugerido = 20

with st.sidebar:
    st.header("📂 Base de Datos")
    archivo_subido = st.file_uploader("Adjuntar archivo COSECHA.xlsx", type=["xlsx"])
    
    if archivo_subido:
        excel_data = pd.ExcelFile(archivo_subido)
        lista_hojas = excel_data.sheet_names
        hoja_sel = st.selectbox("Escoger hoja cargo", lista_hojas)
        
        # Leer columna A, fila 1 son rótulos (header=0 por defecto)
        df_excel = pd.read_excel(archivo_subido, sheet_name=hoja_sel)
        cargo_sugerido = hoja_sel
        if not df_excel.empty:
            # Captura columna A, quita vacíos y asegura que sean únicos para evitar el error KeyError
            fichas_cargadas = df_excel.iloc[:, 0].dropna().unique().astype(str).tolist()
            conteo_sugerido = len(fichas_cargadas)
            st.success(f"Cargadas {conteo_sugerido} fichas únicas.")

    st.header("👤 Parámetros")
    cargo = st.text_input("Nombre del Cargo", value=cargo_sugerido)
    
    st.header("📊 Parámetros Operativos")
    demanda_dia = st.number_input(f"{cargo} requerido (Día)", min_value=1, value=5)
    demanda_noche = st.number_input(f"{cargo} requerido (Noche)", min_value=1, value=5)
    horas_turno = st.number_input("Horas por turno", min_value=1, value=12)
    dias_cubrir = st.slider("Días a cubrir por semana", 1, 7, 7)

    st.header("🧠 Modelo y Ajustes")
    factor_cobertura = st.slider("Factor de holgura técnica", 1.0, 1.5, 1.0, 0.01)
    ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)
    operadores_actuales = st.number_input(f"{cargo} actual (Nómina)", min_value=0, value=conteo_sugerido)

# 3. CONSTANTES
SEMANAS = 6
DIAS_TOTALES = 42
TURNO_DIA, TURNO_NOCHE, DESCANSO = "D", "N", "R"
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1, 7) for d in ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]

# 4. MOTOR DE PROGRAMACIÓN (TU LÓGICA INTACTA)
def generar_programacion_equitativa(n_ops, d_req, n_req, d_semana):
    ops = [f"Op {i+1}" for i in range(n_ops)]
    random.seed(st.session_state['seed'])
    horario = {op: [DESCANSO] * DIAS_TOTALES for op in ops}
    noches_acum = {op: 0 for op in ops}

    for bloque_idx in [0, 21]:
        bloque = range(bloque_idx, bloque_idx + 21)
        turnos_bloque = {op: 0 for op in ops}
        racha = {op: 0 for op in ops}
        turnos_semanales = {op: [0, 0, 0] for op in ops}
        cob_dia = {d: 0 for d in bloque}
        cob_noche = {d: 0 for d in bloque}

        for d in bloque:
            if (d % 7) >= d_semana: continue
            sem_rel = (d - bloque_idx) // 7
            
            obligados_D, obligados_N = [], []
            for op in ops:
                if racha[op] == 1 and turnos_bloque[op] < 11 and turnos_semanales[op][sem_rel] < 4:
                    if d > 0 and horario[op][d-1] == TURNO_DIA: obligados_D.append(op)
                    else: obligados_N.append(op)

            aptos = [op for op in ops if turnos_bloque[op] < 11 and turnos_semanales[op][sem_rel] < 4]
            aptos = [op for op in aptos if d < 1 or horario[op][d-1] == DESCANSO]
            random.shuffle(aptos)

            asignados_n = []
            prioridad_n = [o for o in obligados_N if o in aptos] + [o for o in obligados_D if o in aptos and random.random() < 0.3]
            for op in prioridad_n:
                if len(asignados_n) < n_req: asignados_n.append(op)
            
            resto_n = [o for o in aptos if o not in asignados_n]
            resto_n.sort(key=lambda x: (turnos_bloque[x], noches_acum[x], random.random()))
            while len(asignados_n) < n_req and resto_n:
                asignados_n.append(resto_n.pop(0))

            for op in asignados_n:
                horario[op][d] = TURNO_NOCHE
                turnos_bloque[op] += 1
                turnos_semanales[op][sem_rel] += 1
                cob_noche[d] += 1
                noches_acum[op] += 1
                racha[op] += 1

            ya_n = set(asignados_n)
            cand_d = [op for op in aptos if op not in ya_n]
            if d > bloque_idx: cand_d = [o for o in cand_d if horario[o][d-1] != TURNO_NOCHE]
            
            asignados_d = []
            for op in [o for o in obligados_D if o in cand_d]:
                if len(asignados_d) < d_req: asignados_d.append(op)
            
            resto_d = [o for o in cand_d if o not in asignados_d]
            resto_d.sort(key=lambda x: (turnos_bloque[x], -noches_acum[x], random.random()))
            while len(asignados_d) < d_req and resto_d:
                asignados_d.append(resto_d.pop(0))

            for op in asignados_d:
                horario[op][d] = TURNO_DIA
                turnos_bloque[op] += 1
                turnos_semanales[op][sem_rel] += 1
                cob_dia[d] += 1
                racha[op] += 1

            trabajaron = set(asignados_n) | set(asignados_d)
            for op in ops:
                if op not in trabajaron: racha[op] = 0

        for op in ops:
            while turnos_bloque[op] < 11:
                dias_validos = []
                for d in bloque:
                    sem_rel = (d - bloque_idx) // 7
                    if (d % 7) < d_semana and horario[op][d] == DESCANSO and turnos_semanales[op][sem_rel] < 4:
                        if not (d > bloque_idx and horario[op][d-1] == TURNO_NOCHE):
                            dias_validos.append(d)
                if not dias_validos: break
                dias_validos.sort(key=lambda x: (cob_dia[x] + cob_noche[x]))
                d_optimo = dias_validos[0]
                sem_optimo = (d_optimo - bloque_idx) // 7
                if sum(1 for dia_idx in range(DIAS_TOTALES) if horario[op][dia_idx] == TURNO_DIA) <= sum(1 for dia_idx in range(DIAS_TOTALES) if horario[op][dia_idx] == TURNO_NOCHE):
                    if (cob_dia[d_optimo] - d_req) <= (cob_noche[d_optimo] - n_req):
                        horario[op][d_optimo] = TURNO_DIA
                        cob_dia[d_optimo] += 1
                    else:
                        horario[op][d_optimo] = TURNO_NOCHE
                        cob_noche[d_optimo] += 1
                else:
                    if (cob_noche[d_optimo] - n_req) <= (cob_dia[d_optimo] - d_req):
                        horario[op][d_optimo] = TURNO_NOCHE
                        cob_noche[d_optimo] += 1
                    else:
                        horario[op][d_optimo] = TURNO_DIA
                        cob_dia[d_optimo] += 1
                turnos_bloque[op] += 1
                turnos_semanales[op][sem_optimo] += 1

    return pd.DataFrame(horario, index=NOMBRES_DIAS).T

# 5. EJECUCIÓN
def procesar_generacion(semilla_manual=None):
    if semilla_manual is not None: st.session_state['seed'] = semilla_manual
    total_turnos_ciclo = (demanda_dia + demanda_noche) * d_semana_val * 3 if 'd_semana_val' in locals() else (demanda_dia + demanda_noche) * dias_cubrir * 3
    op_base = math.ceil(total_turnos_ciclo / 11)
    op_final = math.ceil((op_base * factor_cobertura) / (1 - ausentismo))
    op_final = max(op_final, (demanda_dia + demanda_noche) * 2) 
    st.session_state["df"] = generar_programacion_equitativa(op_final, demanda_dia, demanda_noche, dias_cubrir)
    st.session_state["op_final"] = op_final

# BOTONES
c_btn1, c_btn2, c_btn3 = st.columns(3)
with c_btn1:
    if st.button("🚀 Generar Programación (Base)"): procesar_generacion(42)
with c_btn2:
    if st.button("🔄 Generar Otra Versión"): procesar_generacion(random.randint(1, 100000))
with c_btn3:
    if st.button("👤 Asignar Personal Real"):
        if "df" in st.session_state:
            # Trabajamos sobre una copia limpia para evitar errores de Styler
            df_actual = st.session_state["df"].copy()
            indices_viejos = df_actual.index.tolist()
            
            fichas_mezcladas = random.sample(fichas_cargadas, len(fichas_cargadas)) if fichas_cargadas else []
            
            nuevo_mapeo = {}
            for i, idx_antiguo in enumerate(indices_viejos):
                if i < len(fichas_mezcladas):
                    nuevo_mapeo[idx_antiguo] = fichas_mezcladas[i]
                else:
                    nuevo_mapeo[idx_antiguo] = f"VACANTE {i - len(fichas_mezcladas) + 1}"
            
            # Reasignamos el DataFrame con el nuevo índice
            df_actual.index = [nuevo_mapeo[x] for x in indices_viejos]
            st.session_state["df"] = df_actual
            st.success("Nombres actualizados correctamente.")
        else:
            st.error("Primero genera una programación.")

# 6. RENDERIZADO
if "df" in st.session_state:
    df = st.session_state["df"]
    op_final = st.session_state["op_final"]
    
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box-green"><div>{cargo} requerido</div><div class="metric-value-dark">{op_final}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box-green"><div>Fichas en Nómina</div><div class="metric-value-dark">{len(fichas_cargadas)}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box-green"><div>Meta Horas Ciclo</div><div class="metric-value-dark">132.0</div></div>', unsafe_allow_html=True)

    st.subheader("📅 Programación del Personal")
    # style_func aplicado directamente a un DataFrame limpio
    style_func = lambda v: f"background-color: {'#FFF3CD' if v=='D' else '#CCE5FF' if v=='N' else '#F8F9FA'}; font-weight: bold"
    st.dataframe(df.style.map(style_func), use_container_width=True)

    st.subheader(f"📊 Balance Detallado: {cargo}")
    stats = []
    for op in df.index:
        fila = df.loc[op]
        c1_t = sum(1 for x in fila[:21] if x != DESCANSO)
        c2_t = sum(1 for x in fila[21:] if x != DESCANSO)
        stats.append({
            "Identidad": op, 
            "T. Día": (fila==TURNO_DIA).sum(), 
            "T. Noche": (fila==TURNO_NOCHE).sum(),
            "Horas S1-3": c1_t * horas_turno, 
            "Secuencia S1-3": f"{sum(1 for x in fila[0:7] if x!=DESCANSO)}-{sum(1 for x in fila[7:14] if x!=DESCANSO)}-{sum(1 for x in fila[14:21] if x!=DESCANSO)}",
            "Horas S4-6": c2_t * horas_turno, 
            "Secuencia S4-6": f"{sum(1 for x in fila[21:28] if x!=DESCANSO)}-{sum(1 for x in fila[28:35] if x!=DESCANSO)}-{sum(1 for x in fila[35:42] if x!=DESCANSO)}",
            "Estado": "✅ 44h OK" if c1_t == 11 and c2_t == 11 else "❌ Revisar"
        })
    df_balance = pd.DataFrame(stats).set_index("Identidad")
    st.dataframe(df_balance, use_container_width=True)

    st.subheader("✅ Validación de Cobertura Diaria")
    check = []
    for dia in NOMBRES_DIAS:
        ad, an = (df[dia] == TURNO_DIA).sum(), (df[dia] == TURNO_NOCHE).sum()
        check.append({"Día": dia, "Día (Asig)": ad, "Noche (Asig)": an, "Refuerzos": (ad-demanda_dia)+(an-demanda_noche), "Estado": "✅ OK" if ad>=demanda_dia and an>=demanda_noche else "⚠️"})
    st.dataframe(pd.DataFrame(check).set_index("Día").T, use_container_width=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Programación")
        df_balance.to_excel(writer, sheet_name="Balance")
    st.download_button(label=f"⬇️ Descargar Excel {cargo}", data=output.getvalue(), file_name=f"Programacion_{cargo}.xlsx")
