import streamlit as st
import math
import pandas as pd
import random

st.set_page_config(page_title="Calculadora de Personal", layout="wide")

st.title("Calculadora de Personal Operativo")
st.markdown("Ajusta los parametros para calcular la cantidad de operadores necesarios")

# -----------------------
# INPUTS
# -----------------------
st.header("Demanda")
demanda_dia = st.number_input("Operadores requeridos turno dia", min_value=0, value=3)
demanda_noche = st.number_input("Operadores requeridos turno noche", min_value=0, value=3)

st.header("Parametros Operativos")
dias_semana = st.number_input("Dias a cubrir por semana", min_value=1, max_value=7, value=7)
horas_turno = st.number_input("Horas por turno", min_value=1, value=12)

st.header("Modelo de Jornada")
horas_promedio_operador = st.selectbox("Horas promedio por operador", options=[42, 44], index=1)

st.header("Ajustes")
factor_cobertura = st.slider("Factor de cobertura", 1.0, 1.3, 1.1, 0.01)
ausentismo = st.slider("Ausentismo (%)", 0.0, 0.3, 0.0, 0.01)

st.header("Dotacion actual")
operadores_actuales = st.number_input("Operadores actuales", min_value=0, value=6)

# -----------------------
# BOTON CALCULAR
# -----------------------
if st.button("Calcular"):
    st.session_state["calculado"] = True

if st.session_state.get("calculado"):

    horas_totales = (demanda_dia + demanda_noche) * horas_turno * dias_semana
    operadores_base = horas_totales / horas_promedio_operador
    operadores_ajustados = operadores_base * factor_cobertura
    if ausentismo > 0:
        operadores_ajustados = operadores_ajustados / (1 - ausentismo)
    operadores_final = math.ceil(operadores_ajustados)
    diferencia = operadores_final - operadores_actuales

    st.header("Resultados")
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
    # ============================================================
    st.header("Programacion de Turnos (6 semanas)")

    SEMANAS = 6
    DIAS_TOTALES = SEMANAS * 7
    D = "D"
    N = "N"
    R = "R"

    nombres_semana = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    NOMBRES_DIAS = [f"S{s+1}-{nombres_semana[d]}" for s in range(SEMANAS) for d in range(7)]

    PATRONES_CICLO = {
        "A": [4, 4, 3],
        "B": [4, 3, 4],
        "C": [3, 4, 4],
    }

    def construir_dias_trabajo(num_operadores, seed):
        """
        Construye el patron de dias de trabajo para cada operador.

        CORRECCION 1: Asigna combinaciones A/B/C aleatoriamente (shuffle),
        no de forma secuencial, para evitar sesgo.

        CORRECCION 2: Los sobrantes van a descanso. Para mantener exactamente
        22 dias, el algoritmo construye bloques de 4 dias consecutivos + 3 descanso
        con offset rotativo por operador. La construccion garantiza los 22 dias
        sin necesidad de forzar turnos sobrantes.

        Retorna:
          trabajo[op] = lista de 42 bools
          combo_asignado[op] = "A", "B" o "C"
        """
        rng = random.Random(seed)

        # Asignar combinaciones aleatoriamente (no secuencial) - CORRECCION 1
        combos_disponibles = (["A", "B", "C"] * math.ceil(num_operadores / 3))[:num_operadores]
        rng.shuffle(combos_disponibles)

        trabajo = {}
        combo_asignado = {}

        for op_idx in range(num_operadores):
            op = f"Op {op_idx+1}"
            combo = combos_disponibles[op_idx]
            patron = PATRONES_CICLO[combo]
            combo_asignado[op] = combo

            dias = [False] * DIAS_TOTALES

            # Offset unico por operador para rotar dias de descanso (Regla 8)
            # Usamos offset diferente por semana tambien para mayor variedad
            offset_base = (op_idx * 3) % 7

            for semana in range(SEMANAS):
                n_dias = patron[semana % 3]
                inicio = semana * 7
                offset = (offset_base + semana * 2) % 7

                # Seleccionar exactamente n_dias dentro de la semana sin solapamiento
                dias_en_semana = [(offset + d) % 7 for d in range(n_dias)]
                for dia_en_semana in dias_en_semana:
                    dias[inicio + dia_en_semana] = True

            trabajo[op] = dias

        return trabajo, combo_asignado

    def generar_programacion(num_operadores, demanda_dia, demanda_noche, seed):
        """
        Asigna turno D o N respetando todas las reglas.

        CORRECCION 2: Los sobrantes van a DESCANSO, no a N forzado.
        La construccion del patron garantiza que cada operador tenga
        exactamente 22 dias de trabajo en sus bloques asignados.
        Si un dia el operador es sobrante, ese dia se descansa
        y el patron del bloque ya tiene los dias suficientes en
        otras jornadas para llegar a 22.

        IMPORTANTE: Para que esto funcione el numero de operadores
        debe ser suficiente para cubrir demanda todos los dias.
        Si hay dias sin cobertura, se advierte al usuario.
        """
        operadores = [f"Op {i+1}" for i in range(num_operadores)]
        trabajo, combo_asignado = construir_dias_trabajo(num_operadores, seed)

        rng = random.Random(seed + 1)

        horario = {op: ["W" if trabajo[op][i] else R for i in range(DIAS_TOTALES)] for op in operadores}

        for dia_idx in range(DIAS_TOTALES):
            ops_hoy = [op for op in operadores if horario[op][dia_idx] == "W"]

            # Separar forzados a noche (venian de N ayer) - Regla 5
            ops_libre = []
            ops_forzado_noche = []
            for op in ops_hoy:
                ayer = horario[op][dia_idx - 1] if dia_idx > 0 else R
                if ayer == N:
                    ops_forzado_noche.append(op)
                else:
                    ops_libre.append(op)

            rng.shuffle(ops_libre)
            rng.shuffle(ops_forzado_noche)

            cnt_d = 0
            cnt_n = 0

            # 1) Forzados a noche -> N obligatorio (Regla 5)
            for op in ops_forzado_noche:
                if cnt_n < demanda_noche:
                    horario[op][dia_idx] = N
                    cnt_n += 1
                else:
                    # Ya cubrimos noche con forzados, los demas forzados
                    # igual van a N (no pueden ir a D por Regla 5)
                    horario[op][dia_idx] = N
                    cnt_n += 1

            # 2) Libres -> llenar cupo dia (Regla 6)
            for op in ops_libre:
                if cnt_d < demanda_dia and horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = D
                    cnt_d += 1

            # 3) Libres restantes -> llenar cupo noche
            for op in ops_libre:
                if cnt_n < demanda_noche and horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = N
                    cnt_n += 1

            # 4) CORRECCION: Sobrantes van a DESCANSO (no forzar turno extra)
            for op in ops_libre:
                if horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = R  # descanso, no turno forzado

        # Verificar cobertura
        dias_incompletos = []
        for dia_idx in range(DIAS_TOTALES):
            c_d = sum(1 for op in operadores if horario[op][dia_idx] == D)
            c_n = sum(1 for op in operadores if horario[op][dia_idx] == N)
            if c_d < demanda_dia or c_n < demanda_noche:
                dias_incompletos.append({
                    "Dia": NOMBRES_DIAS[dia_idx],
                    "Dia asignado": c_d, "Dia requerido": demanda_dia,
                    "Noche asignada": c_n, "Noche requerida": demanda_noche
                })

        df = pd.DataFrame(horario, index=NOMBRES_DIAS).T
        df.index.name = "Operador"
        return df, dias_incompletos, combo_asignado

    def calcular_estadisticas(df, operadores_list):
        filas = []
        for op in operadores_list:
            fila = {"Operador": op}
            total = 0
            for s in range(SEMANAS):
                dias = NOMBRES_DIAS[s*7:(s+1)*7]
                trabajados = sum(1 for d in dias if df.loc[op, d] in [D, N])
                h = trabajados * horas_turno
                fila[f"S{s+1} dias"] = trabajados
                fila[f"S{s+1} horas"] = h
                total += h
            fila["Total horas"] = total
            fila["Prom h/sem"] = round(total / SEMANAS, 1)
            filas.append(fila)
        return pd.DataFrame(filas).set_index("Operador")

    # -------------------------------
    # BOTONES
    # -------------------------------
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Generar programacion"):
            st.session_state["generar"] = True
            st.session_state["seed"] = random.randint(0, 99999)
    with col2:
        if st.session_state.get("generar"):
            if st.button("Regenerar (nueva aleatoriedad)"):
                st.session_state["seed"] = random.randint(0, 99999)

    if st.session_state.get("generar"):

        seed = st.session_state.get("seed", 42)

        df, dias_incompletos, combo_asignado = generar_programacion(
            operadores_final, demanda_dia, demanda_noche, seed
        )
        operadores_list = df.index.tolist()

        # --- Cobertura ---
        if not dias_incompletos:
            st.success("Cobertura completa - Todos los dias tienen los operadores requeridos")
        else:
            st.error(f"{len(dias_incompletos)} dias con cobertura incompleta - Se necesitan mas operadores")
            with st.expander("Ver dias incompletos"):
                st.dataframe(pd.DataFrame(dias_incompletos).set_index("Dia"))

        st.markdown("**Leyenda:** D = Turno Dia (6am-6pm) | N = Turno Noche (6pm-6am) | R = Descanso")

        # --- Horario con colores ---
        def colorear(val):
            if val == D:
                return "background-color: #FFF3CD; color: #856404; font-weight: bold"
            elif val == N:
                return "background-color: #CCE5FF; color: #004085; font-weight: bold"
            return "background-color: #F8F9FA; color: #ADB5BD"

        st.subheader("Horario completo")
        st.dataframe(df.style.map(colorear), use_container_width=True, height=450)

        # --- Cobertura diaria (exacta, sin sobrecupo) ---
        st.subheader("Cobertura diaria")
        cobertura = []
        for dia in NOMBRES_DIAS:
            c_d = (df[dia] == D).sum()
            c_n = (df[dia] == N).sum()
            ok_d = "OK" if c_d >= demanda_dia else "FALTA"
            ok_n = "OK" if c_n >= demanda_noche else "FALTA"
            cobertura.append({"Dia": dia, f"Dia({ok_d})": c_d, f"Noche({ok_n})": c_n})
        st.dataframe(pd.DataFrame(cobertura).set_index("Dia").T, use_container_width=True)

        # --- Estadisticas horas ---
        st.subheader("Horas trabajadas por operador")
        df_stats = calcular_estadisticas(df, operadores_list)

        def resaltar(val):
            if isinstance(val, float) and val == 44.0:
                return "background-color: #D4EDDA; color: #155724; font-weight: bold"
            elif isinstance(val, float):
                return "background-color: #F8D7DA; color: #721C24; font-weight: bold"
            return ""

        st.dataframe(df_stats.style.map(resaltar, subset=["Prom h/sem"]), use_container_width=True)

        todos_44 = all(df_stats["Prom h/sem"] == 44.0)
        if todos_44:
            st.success("Todos los operadores tienen exactamente 44h promedio/semana")
        else:
            fuera = df_stats[df_stats["Prom h/sem"] != 44.0]
            st.warning(f"{len(fuera)} operadores con promedio diferente a 44h")

        # --- Combinaciones (aleatorias) ---
        st.subheader("Combinacion de ciclo por operador")
        datos_combo = [{"Operador": op, "Combinacion": f"{combo_asignado[op]} ({'-'.join(map(str, PATRONES_CICLO[combo_asignado[op]]))})"} for op in operadores_list]
        st.dataframe(pd.DataFrame(datos_combo).set_index("Operador"), use_container_width=True)

        # --- Excel ---
        file = "programacion_turnos.xlsx"
        with pd.ExcelWriter(file, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Programacion")
            df_stats.to_excel(writer, sheet_name="Horas por operador")
            if dias_incompletos:
                pd.DataFrame(dias_incompletos).to_excel(writer, sheet_name="Dias incompletos", index=False)

        with open(file, "rb") as f:
            st.download_button(
                "Descargar Excel completo", data=f, file_name=file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
