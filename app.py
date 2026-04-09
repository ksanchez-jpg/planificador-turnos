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
# BOTON CALCULAR
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
    st.write(f"**Operadores teoricos (sin ajustes):** {round(operadores_base,2)}")
    st.write(f"**Operadores requeridos (ajustados):** {operadores_final}")

    if diferencia > 0:
        st.error(f"Faltan {diferencia} operadores")
    elif diferencia < 0:
        st.success(f"Sobran {abs(diferencia)} operadores")
    else:
        st.info("Dotacion exacta")

    st.markdown("---")
    st.subheader("Explicacion")
    st.write("""
    - Se calcula la carga total de horas semanales
    - Se divide entre las horas promedio por operador (ciclo 3 semanas: 4+4+3 dias x 12h = 44h promedio)
    - Se ajusta por cobertura y ausentismo
    - Se redondea hacia arriba
    """)

    # ============================================================
    # PROGRAMADOR - Con las 8 reglas + reglas de rotación de turno
    #
    # REGLAS DE TURNO:
    #   1. N -> D directo está PROHIBIDO (sale 6am, entra 6am = sin descanso)
    #   2. D -> N permitido (sale 6pm, entra 6pm siguiente = 24h de diferencia)
    #   3. Máximo 2 turnos consecutivos del mismo tipo (no DDDD ni NNNN)
    #   4. Para pasar de N -> D debe haber al menos 1 día de descanso (R)
    # ============================================================

    st.header("📅 Programacion de Turnos (6 semanas)")

    SEMANAS = 6
    DIAS_TOTALES = SEMANAS * 7
    TURNO_DIA = "D"
    TURNO_NOCHE = "N"
    DESCANSO = "R"

    nombres_semana = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    NOMBRES_DIAS = []
    for s in range(1, SEMANAS + 1):
        for d in range(7):
            NOMBRES_DIAS.append(f"S{s}-{nombres_semana[d]}")

    # Combinaciones de ciclo A, B, C (Regla 7)
    PATRONES_CICLO = {
        0: [4, 4, 3],  # A
        1: [4, 3, 4],  # B
        2: [3, 4, 4],  # C
    }

    def construir_dias_trabajo(num_operadores):
        """
        Define exactamente que dias trabaja cada operador.
        Garantiza 22 dias exactos por operador en 6 semanas = 264h = 44h promedio.
        """
        trabajo = {}
        for op_idx in range(num_operadores):
            op = f"Op {op_idx+1}"
            dias = [False] * DIAS_TOTALES
            combo = op_idx % 3
            patron = PATRONES_CICLO[combo]

            offset_base = (op_idx * 5) % 7

            for semana in range(SEMANAS):
                n_dias = patron[semana % 3]
                inicio = semana * 7
                offset = (offset_base + semana) % 7
                for d in range(n_dias):
                    dia_en_semana = (offset + d) % 7
                    dias[inicio + dia_en_semana] = True

            # Verificar 22 dias exactos, corregir si hay solapamiento
            if sum(dias) != 22:
                dias = [False] * DIAS_TOTALES
                for semana in range(SEMANAS):
                    n_dias = patron[semana % 3]
                    inicio = semana * 7
                    offset = (op_idx * 3 + semana * 2) % 7
                    dias_semana_set = set()
                    d = 0
                    intentos = 0
                    while len(dias_semana_set) < n_dias and intentos < 14:
                        dia_en_semana = (offset + d) % 7
                        dias_semana_set.add(dia_en_semana)
                        d += 1
                        intentos += 1
                    for dia_en_semana in dias_semana_set:
                        dias[inicio + dia_en_semana] = True

            trabajo[op] = dias
        return trabajo

    def turno_permitido(horario_op, dia_idx, turno_propuesto):
        """
        Verifica si un turno propuesto es válido para un operador en un día dado.

        Reglas:
          - N -> D directo: PROHIBIDO
          - Máximo 2 consecutivos del mismo turno: PROHIBIDO más de 2
        """
        turno_ayer = horario_op[dia_idx - 1] if dia_idx > 0 else DESCANSO

        # Regla 1: N -> D prohibido
        if turno_ayer == TURNO_NOCHE and turno_propuesto == TURNO_DIA:
            return False

        # Regla 2: no más de 2 consecutivos del mismo turno
        if dia_idx >= 2:
            turno_anteayer = horario_op[dia_idx - 2]
            if turno_anteayer == turno_propuesto and turno_ayer == turno_propuesto:
                return False

        return True

    def generar_programacion(num_operadores, demanda_dia, demanda_noche):
        """
        Asigna turno D o N sobre los dias marcados como trabajo,
        respetando las reglas de rotación de turno:
          1. N -> D directo PROHIBIDO
          2. Máximo 2 turnos consecutivos del mismo tipo
          3. Para cambiar N -> D debe haber al menos 1 día R entre medias

        Estrategia:
          - Día a día, intentamos cubrir primero la demanda de D, luego N.
          - Si un operador no puede hacer D (porque ayer hizo N), se intenta N.
          - Si no puede hacer ninguno de los dos de forma válida, se convierte
            ese día en R (excepcionalmente) para proteger la regla, marcando
            el día como "forzado a descanso". Esto puede afectar levemente
            el conteo de horas pero garantiza la seguridad del operador.
        """
        operadores = [f"Op {i+1}" for i in range(num_operadores)]
        trabajo = construir_dias_trabajo(num_operadores)

        # Inicializar: dias de trabajo = None (pendiente), descanso = "R"
        horario = {}
        for op in operadores:
            horario[op] = [None if trabajo[op][i] else DESCANSO for i in range(DIAS_TOTALES)]

        # Procesar día a día
        for dia_idx in range(DIAS_TOTALES):
            ops_hoy = [op for op in operadores if horario[op][dia_idx] is None]

            # Clasificar operadores según qué turnos pueden hacer hoy
            puede_dia = []
            puede_noche = []
            solo_noche = []      # pueden N pero no D
            solo_dia = []        # pueden D pero no N (raro, pero posible)
            ninguno = []         # no pueden hacer ningún turno hoy (forzar R)

            for op in ops_hoy:
                ok_d = turno_permitido(horario[op], dia_idx, TURNO_DIA)
                ok_n = turno_permitido(horario[op], dia_idx, TURNO_NOCHE)

                if ok_d and ok_n:
                    puede_dia.append(op)
                    puede_noche.append(op)
                elif ok_d and not ok_n:
                    solo_dia.append(op)
                    puede_dia.append(op)
                elif ok_n and not ok_d:
                    solo_noche.append(op)
                    puede_noche.append(op)
                else:
                    ninguno.append(op)

            # Los que no pueden hacer nada hoy: forzar R (excepción de seguridad)
            for op in ninguno:
                horario[op][dia_idx] = DESCANSO

            # Mezclar para variedad
            random.shuffle(puede_dia)
            random.shuffle(puede_noche)

            asignados_dia = 0
            asignados_noche = 0

            # ---- Paso 1: Cubrir demanda de DÍA ----
            # Primero los que SOLO pueden día (para no desperdiciarlos)
            for op in solo_dia:
                if asignados_dia < demanda_dia and horario[op][dia_idx] is None:
                    horario[op][dia_idx] = TURNO_DIA
                    asignados_dia += 1

            # Luego los flexibles
            for op in puede_dia:
                if op in solo_dia:
                    continue  # ya procesado
                if asignados_dia < demanda_dia and horario[op][dia_idx] is None:
                    horario[op][dia_idx] = TURNO_DIA
                    asignados_dia += 1

            # ---- Paso 2: Cubrir demanda de NOCHE ----
            # Primero los que SOLO pueden noche
            for op in solo_noche:
                if asignados_noche < demanda_noche and horario[op][dia_idx] is None:
                    horario[op][dia_idx] = TURNO_NOCHE
                    asignados_noche += 1

            # Luego los flexibles restantes
            for op in puede_noche:
                if op in solo_noche:
                    continue
                if asignados_noche < demanda_noche and horario[op][dia_idx] is None:
                    horario[op][dia_idx] = TURNO_NOCHE
                    asignados_noche += 1

            # ---- Paso 3: Operadores con día de trabajo pendiente sin asignar ----
            # Ya cubrimos demanda; los sobrantes se asignan al turno que puedan
            # para no perder jornadas (priorizando el turno con menos asignados)
            for op in operadores:
                if horario[op][dia_idx] is not None:
                    continue  # ya asignado

                ok_d = turno_permitido(horario[op], dia_idx, TURNO_DIA)
                ok_n = turno_permitido(horario[op], dia_idx, TURNO_NOCHE)

                if ok_d and ok_n:
                    # Asignar al turno que tenga menos cobertura relativa
                    if asignados_dia <= asignados_noche:
                        horario[op][dia_idx] = TURNO_DIA
                        asignados_dia += 1
                    else:
                        horario[op][dia_idx] = TURNO_NOCHE
                        asignados_noche += 1
                elif ok_d:
                    horario[op][dia_idx] = TURNO_DIA
                    asignados_dia += 1
                elif ok_n:
                    horario[op][dia_idx] = TURNO_NOCHE
                    asignados_noche += 1
                else:
                    # Forzar R por seguridad (no debería llegar aquí si ya filtramos)
                    horario[op][dia_idx] = DESCANSO

        # Verificar cobertura
        dias_incompletos = []
        for dia_idx in range(DIAS_TOTALES):
            cnt_d = sum(1 for op in operadores if horario[op][dia_idx] == TURNO_DIA)
            cnt_n = sum(1 for op in operadores if horario[op][dia_idx] == TURNO_NOCHE)
            if cnt_d < demanda_dia or cnt_n < demanda_noche:
                dias_incompletos.append({
                    "Dia": NOMBRES_DIAS[dia_idx],
                    "Dia asignado": cnt_d,
                    "Dia requerido": demanda_dia,
                    "Noche asignada": cnt_n,
                    "Noche requerida": demanda_noche
                })

        df = pd.DataFrame(horario, index=NOMBRES_DIAS).T
        df.index.name = "Operador"
        return df, dias_incompletos

    def verificar_reglas(df, operadores_list):
        """
        Verifica que la programación cumpla las reglas de turno.
        Retorna lista de violaciones encontradas.
        """
        violaciones = []
        for op in operadores_list:
            turnos = df.loc[op].tolist()
            for i in range(1, len(turnos)):
                ayer = turnos[i-1]
                hoy = turnos[i]
                # Violación N -> D directo
                if ayer == TURNO_NOCHE and hoy == TURNO_DIA:
                    violaciones.append({
                        "Operador": op,
                        "Dia": NOMBRES_DIAS[i],
                        "Problema": f"N→D directo ({NOMBRES_DIAS[i-1]}=N, {NOMBRES_DIAS[i]}=D)"
                    })
            # Violación más de 2 consecutivos
            for i in range(2, len(turnos)):
                if turnos[i] in [TURNO_DIA, TURNO_NOCHE]:
                    if turnos[i] == turnos[i-1] == turnos[i-2]:
                        violaciones.append({
                            "Operador": op,
                            "Dia": NOMBRES_DIAS[i],
                            "Problema": f"3+ consecutivos {turnos[i]} ({NOMBRES_DIAS[i-2]}, {NOMBRES_DIAS[i-1]}, {NOMBRES_DIAS[i]})"
                        })
        return violaciones

    def calcular_estadisticas(df, operadores_list):
        filas = []
        for op in operadores_list:
            fila = {"Operador": op}
            total_horas = 0
            for s in range(SEMANAS):
                dias = NOMBRES_DIAS[s*7:(s+1)*7]
                trabajados = sum(1 for d in dias if df.loc[op, d] in [TURNO_DIA, TURNO_NOCHE])
                h = trabajados * horas_turno
                fila[f"S{s+1} dias"] = trabajados
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
        if st.button("Generar programacion"):
            st.session_state["generar"] = True
            st.session_state["seed"] = random.randint(0, 9999)
    with col2:
        if st.session_state.get("generar"):
            if st.button("Regenerar (nueva aleatoriedad)"):
                st.session_state["seed"] = random.randint(0, 9999)

    if st.session_state.get("generar"):

        random.seed(st.session_state.get("seed", 42))

        df, dias_incompletos = generar_programacion(
            operadores_final,
            demanda_dia,
            demanda_noche
        )

        operadores_list = df.index.tolist()

        # Cobertura
        if not dias_incompletos:
            st.success("✅ Cobertura completa - Todos los dias tienen los operadores requeridos")
        else:
            st.error(f"⚠️ {len(dias_incompletos)} dias con cobertura incompleta - Se necesitan mas operadores")
            with st.expander("Ver dias incompletos"):
                st.dataframe(pd.DataFrame(dias_incompletos).set_index("Dia"))

        # Verificar reglas de turno
        violaciones = verificar_reglas(df, operadores_list)
        if not violaciones:
            st.success("✅ Sin violaciones de reglas de turno (N→D directo: 0 | Consecutivos >2: 0)")
        else:
            st.error(f"❌ {len(violaciones)} violaciones de reglas de turno detectadas")
            with st.expander("Ver violaciones"):
                st.dataframe(pd.DataFrame(violaciones).set_index("Operador"))

        st.markdown("**Leyenda:** D = Turno Día (6am-6pm) | N = Turno Noche (6pm-6am) | R = Descanso")
        st.info("📋 **Reglas aplicadas:** ① N→D directo prohibido (mínimo 1R entre medias) | ② Máximo 2 turnos consecutivos del mismo tipo | ③ D→N permitido directamente")

        # Tabla con colores
        def colorear(val):
            if val == TURNO_DIA:
                return "background-color: #FFF3CD; color: #856404; font-weight: bold"
            elif val == TURNO_NOCHE:
                return "background-color: #CCE5FF; color: #004085; font-weight: bold"
            else:
                return "background-color: #F8F9FA; color: #ADB5BD"

        st.subheader("Horario completo")
        st.dataframe(df.style.map(colorear), use_container_width=True, height=450)

        # Cobertura diaria
        st.subheader("Cobertura diaria")
        cobertura = []
        for dia in NOMBRES_DIAS:
            cnt_d = (df[dia] == TURNO_DIA).sum()
            cnt_n = (df[dia] == TURNO_NOCHE).sum()
            ok_d = "OK" if cnt_d >= demanda_dia else "FALTA"
            ok_n = "OK" if cnt_n >= demanda_noche else "FALTA"
            cobertura.append({"Dia": dia, f"Dia({ok_d})": cnt_d, f"Noche({ok_n})": cnt_n})
        df_cob = pd.DataFrame(cobertura).set_index("Dia")
        st.dataframe(df_cob.T, use_container_width=True)

        # Estadisticas de horas
        st.subheader("Horas trabajadas por operador")
        df_stats = calcular_estadisticas(df, operadores_list)

        def resaltar_promedio(val):
            if isinstance(val, float) and val != 44.0:
                return "background-color: #F8D7DA; color: #721C24; font-weight: bold"
            elif isinstance(val, float) and val == 44.0:
                return "background-color: #D4EDDA; color: #155724; font-weight: bold"
            return ""

        st.dataframe(
            df_stats.style.map(resaltar_promedio, subset=["Prom h/sem"]),
            use_container_width=True
        )

        todos_44 = all(df_stats["Prom h/sem"] == 44.0)
        if todos_44:
            st.success("✅ Todos los operadores tienen exactamente 44h promedio/semana")
        else:
            fuera = df_stats[df_stats["Prom h/sem"] != 44.0]
            st.warning(f"⚠️ {len(fuera)} operadores con promedio diferente a 44h (puede ocurrir cuando se fuerza R por seguridad de turno)")

        # Combinaciones de ciclo
        st.subheader("Combinacion de ciclo por operador")
        combos_nombre = {0: "A (4-4-3)", 1: "B (4-3-4)", 2: "C (3-4-4)"}
        datos_combo = [{"Operador": op, "Combinacion": combos_nombre[i % 3]} for i, op in enumerate(operadores_list)]
        st.dataframe(pd.DataFrame(datos_combo).set_index("Operador"), use_container_width=True)

        # Descarga Excel
        file = "programacion_turnos.xlsx"
        with pd.ExcelWriter(file, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Programacion")
            df_stats.to_excel(writer, sheet_name="Horas por operador")
            if dias_incompletos:
                pd.DataFrame(dias_incompletos).to_excel(writer, sheet_name="Dias incompletos", index=False)
            if violaciones:
                pd.DataFrame(violaciones).to_excel(writer, sheet_name="Violaciones reglas", index=False)

        with open(file, "rb") as f:
            st.download_button(
                "Descargar Excel completo",
                data=f,
                file_name=file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
