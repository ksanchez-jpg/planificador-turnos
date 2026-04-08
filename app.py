import streamlit as st
import math
import pandas as pd
import random

st.set_page_config(page_title="Calculadora de Personal", layout="wide")

st.title("🧮 Calculadora de Personal Operativo")
st.markdown("Ajusta los parámetros para calcular la cantidad de operadores necesarios")

# -----------------------
# INPUTS
# -----------------------

st.header("📊 Demanda")
demanda_dia = st.number_input("Operadores requeridos turno día", min_value=0, value=3)
demanda_noche = st.number_input("Operadores requeridos turno noche", min_value=0, value=3)

st.header("⚙️ Parámetros Operativos")
dias_semana = st.number_input("Días a cubrir por semana", min_value=1, max_value=7, value=7)
horas_turno = st.number_input("Horas por turno", min_value=1, value=12)

st.header("🧠 Modelo de Jornada")
horas_promedio_operador = st.selectbox(
    "Horas promedio por operador",
    options=[42, 44],
    index=1
)

st.header("📉 Ajustes")
factor_cobertura = st.slider("Factor de cobertura", 1.0, 1.3, 1.1, 0.01)
ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)

st.header("👥 Dotación actual")
operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=6)

# -----------------------
# BOTÓN CALCULAR
# -----------------------

if st.button("Calcular"):
    st.session_state["calculado"] = True

# -----------------------
# RESULTADOS (PERSISTENTES)
# -----------------------

if st.session_state.get("calculado"):

    horas_totales = (demanda_dia + demanda_noche) * horas_turno * dias_semana
    operadores_base = horas_totales / horas_promedio_operador
    operadores_ajustados = operadores_base * factor_cobertura

    if ausentismo > 0:
        operadores_ajustados = operadores_ajustados / (1 - ausentismo)

    operadores_final = math.ceil(operadores_ajustados)
    diferencia = operadores_final - operadores_actuales

    st.header("📈 Resultados")
    st.write(f"**Horas totales requeridas:** {horas_totales}")
    st.write(f"**Operadores teóricos (sin ajustes):** {round(operadores_base,2)}")
    st.write(f"**Operadores requeridos (ajustados):** {operadores_final}")

    if diferencia > 0:
        st.error(f"❌ Faltan {diferencia} operadores")
    elif diferencia < 0:
        st.success(f"✅ Sobran {abs(diferencia)} operadores")
    else:
        st.info("✔️ Dotación exacta")

    st.markdown("---")
    st.subheader("🧠 Explicación")
    st.write("""
    - Se calcula la carga total de horas semanales
    - Se divide entre las horas promedio por operador (ciclo 3 semanas: 4+4+3 días × 12h = 44h promedio)
    - Se ajusta por cobertura y ausentismo
    - Se redondea hacia arriba
    """)

    # ============================================================
    # 🔥 PROGRAMADOR - Con las 8 reglas
    # ============================================================

    st.header("📅 Programación de Turnos (6 semanas)")

    # Constantes
    SEMANAS = 6
    DIAS_TOTALES = SEMANAS * 7
    TURNO_DIA = "D"
    TURNO_NOCHE = "N"
    DESCANSO = "R"

    nombres_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    NOMBRES_DIAS = []
    for s in range(1, SEMANAS + 1):
        for d in range(7):
            NOMBRES_DIAS.append(f"S{s}-{nombres_semana[d]}")

    def asignar_combinacion_ciclo(op_idx):
        """
        Regla 7: Distribuir combinaciones A, B, C equitativamente.
        A: 4-4-3 | B: 4-3-4 | C: 3-4-4
        """
        return op_idx % 3

    def dias_trabajo_semana(op_idx, semana_idx):
        """
        Regla 2 y 3: Máximo 4 días/semana, esquema 4x3.
        Regla 7: Cada operador tiene su combinación de ciclo.
        """
        ciclo_pos = semana_idx % 3
        patrones = {
            0: [4, 4, 3],  # Combinación A
            1: [4, 3, 4],  # Combinación B
            2: [3, 4, 4],  # Combinación C
        }
        return patrones[asignar_combinacion_ciclo(op_idx)][ciclo_pos]

    def generar_programacion(num_operadores, demanda_dia, demanda_noche):
        """
        Genera programación respetando las 8 reglas:
        1. Cobertura garantizada todos los días (D y N)
        2. Máximo 4 días por semana
        3. Esquema 4x3 (trabaja 4, descansa 3)
        4. Rotación día/noche equitativa
        5. Después de noche: solo noche o descanso (nunca día directo)
        6. No puede hacer día y noche el mismo día
        7. Combinaciones A, B, C distribuidas balanceadamente
        8. Días de descanso rotan entre semanas
        """
        operadores = [f"Op {i+1}" for i in range(num_operadores)]
        horario = {op: [DESCANSO] * DIAS_TOTALES for op in operadores}

        # PASO 1: Marcar días de trabajo por operador según combinación
        # Reglas 2, 3, 7, 8
        for op_idx, op in enumerate(operadores):
            # Offset para rotar días de descanso (Regla 8)
            # Cada operador empieza en un día diferente de la semana
            offset = (op_idx * 2) % 7

            for semana in range(SEMANAS):
                n_dias = dias_trabajo_semana(op_idx, semana)
                inicio_semana = semana * 7

                # Seleccionar qué días dentro de la semana trabaja
                # El offset rota para que no siempre descansen fines de semana
                dias_sel = [(inicio_semana + ((offset + d) % 7)) for d in range(n_dias)]

                for dia_idx in dias_sel:
                    horario[op][dia_idx] = "W"  # pendiente de asignar turno

        # PASO 2: Asignar turno D o N respetando reglas 4, 5 y 6
        # Primero intentamos cubrir demanda de cada día
        for dia_idx in range(DIAS_TOTALES):
            ops_trabajo_hoy = [op for op in operadores if horario[op][dia_idx] == "W"]

            # Clasificar según restricción de turno noche previo (Regla 5)
            ops_libre = []      # pueden hacer D o N
            ops_solo_noche = [] # venían de noche, solo pueden hacer N

            for op in ops_trabajo_hoy:
                turno_ayer = horario[op][dia_idx - 1] if dia_idx > 0 else DESCANSO
                if turno_ayer == TURNO_NOCHE:
                    ops_solo_noche.append(op)
                else:
                    ops_libre.append(op)

            asignados_dia = 0
            asignados_noche = 0

            # Asignar noche primero a los que vienen de noche (Regla 5)
            random.shuffle(ops_solo_noche)
            for op in ops_solo_noche:
                if asignados_noche < demanda_noche:
                    horario[op][dia_idx] = TURNO_NOCHE
                    asignados_noche += 1
                else:
                    # No hay cupo en noche, deben descansar (Regla 5)
                    horario[op][dia_idx] = DESCANSO

            # Asignar turno día con los libres (Regla 6: no puede hacer D y N)
            random.shuffle(ops_libre)
            for op in ops_libre:
                if asignados_dia < demanda_dia and horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = TURNO_DIA
                    asignados_dia += 1

            # Completar noche con los libres restantes
            for op in ops_libre:
                if asignados_noche < demanda_noche and horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = TURNO_NOCHE
                    asignados_noche += 1

            # Los que quedaron con "W" sin asignar -> descanso
            for op in operadores:
                if horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = DESCANSO

        # PASO 3: Verificar cobertura (Regla 1)
        dias_incompletos = []
        for dia_idx in range(DIAS_TOTALES):
            cnt_d = sum(1 for op in operadores if horario[op][dia_idx] == TURNO_DIA)
            cnt_n = sum(1 for op in operadores if horario[op][dia_idx] == TURNO_NOCHE)
            if cnt_d < demanda_dia or cnt_n < demanda_noche:
                dias_incompletos.append({
                    "Día": NOMBRES_DIAS[dia_idx],
                    "Día asignado": cnt_d,
                    "Día requerido": demanda_dia,
                    "Noche asignada": cnt_n,
                    "Noche requerida": demanda_noche
                })

        # Construir DataFrame
        df = pd.DataFrame(horario, index=NOMBRES_DIAS).T
        df.index.name = "Operador"

        return df, dias_incompletos

    def calcular_estadisticas(df, operadores_list):
        """Calcula horas y días trabajados por semana por operador."""
        filas = []
        for op in operadores_list:
            fila = {"Operador": op}
            total_horas = 0
            for s in range(SEMANAS):
                dias = NOMBRES_DIAS[s*7:(s+1)*7]
                trabajados = sum(1 for d in dias if df.loc[op, d] in [TURNO_DIA, TURNO_NOCHE])
                h = trabajados * horas_turno
                fila[f"S{s+1} días"] = trabajados
                fila[f"S{s+1} horas"] = h
                total_horas += h
            fila["Total horas"] = total_horas
            fila["Prom h/sem"] = round(total_horas / SEMANAS, 1)
            filas.append(fila)
        return pd.DataFrame(filas).set_index("Operador")

    # -------------------------------
    # BOTONES GENERAR / REGENERAR
    # -------------------------------

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Generar programación"):
            st.session_state["generar"] = True
            st.session_state["seed"] = random.randint(0, 9999)
    with col2:
        if st.session_state.get("generar"):
            if st.button("🔄 Regenerar (nueva aleatoriedad)"):
                st.session_state["seed"] = random.randint(0, 9999)

    if st.session_state.get("generar"):

        random.seed(st.session_state.get("seed", 42))

        df, dias_incompletos = generar_programacion(
            operadores_final,
            demanda_dia,
            demanda_noche
        )

        operadores_list = df.index.tolist()

        # ---- ESTADO DE COBERTURA ----
        if not dias_incompletos:
            st.success("✅ Cobertura completa — Todos los días tienen los operadores requeridos")
        else:
            st.error(f"❌ {len(dias_incompletos)} días con cobertura incompleta — Se necesitan más operadores")
            with st.expander("📋 Ver días incompletos"):
                st.dataframe(pd.DataFrame(dias_incompletos).set_index("Día"))

        # ---- LEYENDA ----
        st.markdown("""
        **Leyenda:** &nbsp;🟡 `D` = Turno Día (6am–6pm) &nbsp;|&nbsp; 🔵 `N` = Turno Noche (6pm–6am) &nbsp;|&nbsp; ⬜ `R` = Descanso
        """)

        # ---- TABLA PRINCIPAL CON COLORES ----
        def colorear(val):
            if val == TURNO_DIA:
                return "background-color: #FFF3CD; color: #856404; font-weight: bold; text-align: center"
            elif val == TURNO_NOCHE:
                return "background-color: #CCE5FF; color: #004085; font-weight: bold; text-align: center"
            else:
                return "background-color: #F8F9FA; color: #ADB5BD; text-align: center"

        st.subheader("📅 Horario completo")
        st.dataframe(
            df.style.applymap(colorear),
            use_container_width=True,
            height=450
        )

        # ---- VERIFICACIÓN COBERTURA POR DÍA ----
        st.subheader("📊 Cobertura diaria")
        cobertura = []
        for dia in NOMBRES_DIAS:
            cnt_d = (df[dia] == TURNO_DIA).sum()
            cnt_n = (df[dia] == TURNO_NOCHE).sum()
            cobertura.append({
                "Día": dia,
                "Día ✅" if cnt_d >= demanda_dia else "Día ❌": cnt_d,
                "Noche ✅" if cnt_n >= demanda_noche else "Noche ❌": cnt_n,
            })

        df_cob = pd.DataFrame(cobertura).set_index("Día")
        st.dataframe(df_cob.T, use_container_width=True)

        # ---- ESTADÍSTICAS DE HORAS ----
        st.subheader("⏱️ Horas trabajadas por operador")
        df_stats = calcular_estadisticas(df, operadores_list)
        st.dataframe(df_stats, use_container_width=True)

        # ---- COMBINACIONES DE CICLO ----
        st.subheader("🔄 Combinación de ciclo por operador")
        combos_nombre = {0: "A  →  4-4-3 semanas", 1: "B  →  4-3-4 semanas", 2: "C  →  3-4-4 semanas"}
        datos_combo = []
        for i, op in enumerate(operadores_list):
            combo = i % 3
            datos_combo.append({"Operador": op, "Combinación": combos_nombre[combo]})
        st.dataframe(pd.DataFrame(datos_combo).set_index("Operador"), use_container_width=True)

        # ---- DESCARGA EXCEL ----
        file = "programacion_turnos.xlsx"
        with pd.ExcelWriter(file, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Programación")
            df_stats.to_excel(writer, sheet_name="Horas por operador")
            pd.DataFrame(dias_incompletos).to_excel(writer, sheet_name="Días incompletos", index=False) if dias_incompletos else None

        with open(file, "rb") as f:
            st.download_button(
                "📥 Descargar Excel completo",
                data=f,
                file_name=file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
