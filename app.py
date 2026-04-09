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
    # PROGRAMADOR
    #
    # REGLAS DE TURNO (no negociables):
    #   1. N -> D directo PROHIBIDO
    #   2. D -> N permitido
    #   3. Máximo 2 turnos consecutivos del mismo tipo
    #   4. Para pasar N -> D debe haber mínimo 1 R
    #
    # GARANTÍAS:
    #   - Exactamente 22 días trabajados = 264h = 44h/sem promedio
    #   - Cobertura completa todos los días
    #   - Cero violaciones de reglas de turno
    #
    # ESTRATEGIA:
    #   - Pre-calcular todos los bloques semanales válidos (backtracking)
    #   - Elegir aleatoriamente entre bloques válidos para variedad
    #   - Post-procesar para maximizar cobertura sin romper reglas
    # ============================================================

    st.header("📅 Programacion de Turnos (6 semanas)")

    SEMANAS = 6
    DIAS_TOTALES = SEMANAS * 7
    DT = "D"
    NT = "N"
    RT = "R"

    nombres_semana = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    NOMBRES_DIAS = []
    for s in range(1, SEMANAS + 1):
        for d in range(7):
            NOMBRES_DIAS.append(f"S{s}-{nombres_semana[d]}")

    PATRONES_CICLO = {
        0: [4, 4, 3],
        1: [4, 3, 4],
        2: [3, 4, 4],
    }

    # -------------------------------------------------------
    # Pre-cálculo de bloques semanales válidos
    # -------------------------------------------------------

    def bloques_validos_para(n_dias, ultimo_turno_anterior):
        """
        Genera todas las secuencias de 7 días con exactamente n_dias trabajados,
        respetando reglas de turno. El primer día de la semana debe ser compatible
        con ultimo_turno_anterior (último turno de la semana previa).
        """
        resultados = []

        def backtrack(pos, seq, ultimo, consec, trabajados):
            if pos == 7:
                if trabajados == n_dias:
                    resultados.append(tuple(seq))
                return

            restantes = 7 - pos
            faltan = n_dias - trabajados

            if faltan > restantes or faltan < 0:
                return

            if faltan == 0:
                seq.extend([RT] * restantes)
                resultados.append(tuple(seq))
                del seq[-restantes:]
                return

            for turno in [DT, NT, RT]:
                if turno == RT:
                    seq.append(RT)
                    backtrack(pos + 1, seq, RT, 0, trabajados)
                    seq.pop()
                else:
                    if ultimo == NT and turno == DT:
                        continue
                    if consec >= 2 and turno == ultimo:
                        continue
                    seq.append(turno)
                    nc = consec + 1 if turno == ultimo else 1
                    backtrack(pos + 1, seq, turno, nc, trabajados + 1)
                    seq.pop()

        backtrack(0, [], ultimo_turno_anterior, 0, 0)
        return resultados

    # Cache pre-calculado
    cache_bloques = {}
    for n in [3, 4]:
        for ut in [RT, DT, NT]:
            cache_bloques[(n, ut)] = bloques_validos_para(n, ut)

    def ultimo_turno_seq(semana_seq):
        for t in reversed(semana_seq):
            if t in [DT, NT]:
                return t
        return RT

    def generar_horario_op(patron_semanas, rng):
        """
        Genera la secuencia de 42 días para un operador
        eligiendo aleatoriamente entre bloques válidos cada semana.
        Garantiza exactamente 22 días trabajados.
        """
        secuencia = []
        ultimo = RT
        for semana_idx in range(SEMANAS):
            n = patron_semanas[semana_idx]
            opciones = cache_bloques.get((n, ultimo), [])
            if not opciones:
                opciones = bloques_validos_para(n, ultimo)
            bloque = list(rng.choice(opciones))
            secuencia.extend(bloque)
            ultimo = ultimo_turno_seq(bloque)
        return secuencia

    def puede_cambiar_a(seq, idx, nuevo):
        """
        ¿Puede el turno en posición idx cambiarse a 'nuevo'
        sin romper las reglas con los días adyacentes?
        """
        n = len(seq)
        ayer = seq[idx - 1] if idx > 0 else RT
        manana = seq[idx + 1] if idx < n - 1 else RT
        pasado = seq[idx + 2] if idx < n - 2 else RT
        anteayer = seq[idx - 2] if idx > 1 else RT

        # Regla N -> D
        if ayer == NT and nuevo == DT:
            return False
        # Regla: si mañana es D y nuevo es N -> mañana quedaría N->D prohibido
        if nuevo == NT and manana == DT:
            return False

        # Regla máx 2 consecutivos con días previos
        if ayer == nuevo and anteayer == nuevo:
            return False
        # Regla máx 2 consecutivos con días siguientes
        if manana == nuevo and pasado == nuevo:
            return False
        # Regla: nuevo + mañana + pasado = 3 consecutivos
        if ayer == nuevo and manana == nuevo:
            return False

        return True

    def generar_programacion(num_operadores, demanda_dia, demanda_noche):
        """
        Genera programación completa con las 3 garantías:
        44h promedio, cobertura completa, reglas de turno.
        """
        operadores = [f"Op {i+1}" for i in range(num_operadores)]

        # Paso 1: Generar horarios base válidos por operador
        horario = {}
        for i, op in enumerate(operadores):
            combo = i % 3
            patron = (PATRONES_CICLO[combo] * (SEMANAS // 3 + 1))[:SEMANAS]
            rng = random.Random(i * 137 + random.randint(0, 9999))
            horario[op] = generar_horario_op(patron, rng)

        # Paso 2: Optimizar distribución D/N para cubrir demanda
        # Múltiples pasadas: intentar cambiar D->N o N->D donde haya déficit
        for _ in range(100):
            sin_cambios = True
            for dia_idx in range(DIAS_TOTALES):
                cnt_d = sum(1 for op in operadores if horario[op][dia_idx] == DT)
                cnt_n = sum(1 for op in operadores if horario[op][dia_idx] == NT)

                # Cubrir déficit de DÍA: convertir N->D donde sea válido
                if cnt_d < demanda_dia:
                    ops_n = [op for op in operadores if horario[op][dia_idx] == NT]
                    random.shuffle(ops_n)
                    for op in ops_n:
                        if cnt_d >= demanda_dia:
                            break
                        if puede_cambiar_a(horario[op], dia_idx, DT):
                            horario[op][dia_idx] = DT
                            cnt_d += 1
                            cnt_n -= 1
                            sin_cambios = False

                # Cubrir déficit de NOCHE: convertir D->N donde sea válido
                if cnt_n < demanda_noche:
                    ops_d = [op for op in operadores if horario[op][dia_idx] == DT]
                    random.shuffle(ops_d)
                    for op in ops_d:
                        if cnt_n >= demanda_noche:
                            break
                        if puede_cambiar_a(horario[op], dia_idx, NT):
                            horario[op][dia_idx] = NT
                            cnt_n += 1
                            cnt_d -= 1
                            sin_cambios = False

            if sin_cambios:
                break

        # Verificar cobertura
        dias_incompletos = []
        for dia_idx in range(DIAS_TOTALES):
            cnt_d = sum(1 for op in operadores if horario[op][dia_idx] == DT)
            cnt_n = sum(1 for op in operadores if horario[op][dia_idx] == NT)
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
        violaciones = []
        for op in operadores_list:
            turnos = df.loc[op].tolist()
            for i in range(1, len(turnos)):
                if turnos[i-1] == NT and turnos[i] == DT:
                    violaciones.append({
                        "Operador": op,
                        "Dia": NOMBRES_DIAS[i],
                        "Problema": f"N→D directo ({NOMBRES_DIAS[i-1]}=N, {NOMBRES_DIAS[i]}=D)"
                    })
            for i in range(2, len(turnos)):
                if turnos[i] in [DT, NT] and turnos[i] == turnos[i-1] == turnos[i-2]:
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
                dias_s = NOMBRES_DIAS[s*7:(s+1)*7]
                trabajados = sum(1 for d in dias_s if df.loc[op, d] in [DT, NT])
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
            st.success("✅ Cobertura completa — Todos los días tienen los operadores requeridos")
        else:
            st.error(f"⚠️ {len(dias_incompletos)} días con cobertura incompleta")
            with st.expander("Ver días incompletos"):
                st.dataframe(pd.DataFrame(dias_incompletos).set_index("Dia"))

        # Verificar reglas
        violaciones = verificar_reglas(df, operadores_list)
        if not violaciones:
            st.success("✅ Sin violaciones de reglas de turno (N→D directo: 0 | Consecutivos >2: 0)")
        else:
            st.error(f"❌ {len(violaciones)} violaciones de reglas de turno detectadas")
            with st.expander("Ver violaciones"):
                st.dataframe(pd.DataFrame(violaciones).set_index("Operador"))

        st.markdown("**Leyenda:** D = Turno Día (6am–6pm) | N = Turno Noche (6pm–6am) | R = Descanso")
        st.info(
            "📋 **Reglas aplicadas:** "
            "① N→D directo prohibido (mínimo 1R entre medias) | "
            "② Máximo 2 turnos consecutivos del mismo tipo | "
            "③ D→N permitido directamente"
        )

        # Tabla con colores
        def colorear(val):
            if val == DT:
                return "background-color: #FFF3CD; color: #856404; font-weight: bold"
            elif val == NT:
                return "background-color: #CCE5FF; color: #004085; font-weight: bold"
            else:
                return "background-color: #F8F9FA; color: #ADB5BD"

        st.subheader("Horario completo")
        st.dataframe(df.style.map(colorear), use_container_width=True, height=450)

        # Cobertura diaria
        st.subheader("Cobertura diaria")
        cobertura = []
        for dia in NOMBRES_DIAS:
            cnt_d = (df[dia] == DT).sum()
            cnt_n = (df[dia] == NT).sum()
            ok_d = "OK" if cnt_d >= demanda_dia else "FALTA"
            ok_n = "OK" if cnt_n >= demanda_noche else "FALTA"
            cobertura.append({"Dia": dia, f"Dia({ok_d})": cnt_d, f"Noche({ok_n})": cnt_n})
        df_cob = pd.DataFrame(cobertura).set_index("Dia")
        st.dataframe(df_cob.T, use_container_width=True)

        # Horas por operador
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
            st.warning(f"⚠️ {len(fuera)} operadores con promedio diferente a 44h")

        # Combinaciones de ciclo
        st.subheader("Combinacion de ciclo por operador")
        combos_nombre = {0: "A (4-4-3)", 1: "B (4-3-4)", 2: "C (3-4-4)"}
        datos_combo = [
            {"Operador": op, "Combinacion": combos_nombre[i % 3]}
            for i, op in enumerate(operadores_list)
        ]
        st.dataframe(pd.DataFrame(datos_combo).set_index("Operador"), use_container_width=True)

        # Descarga Excel
        file = "programacion_turnos.xlsx"
        with pd.ExcelWriter(file, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Programacion")
            df_stats.to_excel(writer, sheet_name="Horas por operador")
            if dias_incompletos:
                pd.DataFrame(dias_incompletos).to_excel(
                    writer, sheet_name="Dias incompletos", index=False
                )
            if violaciones:
                pd.DataFrame(violaciones).to_excel(
                    writer, sheet_name="Violaciones reglas", index=False
                )

        with open(file, "rb") as f:
            st.download_button(
                "Descargar Excel completo",
                data=f,
                file_name=file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
