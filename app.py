import streamlit as st
import math
import pandas as pd
import random

st.set_page_config(page_title="Calculadora de Personal", layout="wide")
st.title("Calculadora de Personal Operativo")

# -----------------------
# INPUTS
# -----------------------
st.header("Demanda")
demanda_dia = st.number_input("Operadores requeridos turno dia", min_value=1, value=5)
demanda_noche = st.number_input("Operadores requeridos turno noche", min_value=1, value=5)

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
    st.write(f"**Operadores teoricos (sin ajustes):** {round(operadores_base, 2)}")
    st.write(f"**Operadores requeridos (ajustados):** {operadores_final}")
    if diferencia > 0:
        st.error(f"Faltan {diferencia} operadores")
    elif diferencia < 0:
        st.success(f"Sobran {abs(diferencia)} operadores")
    else:
        st.info("Dotacion exacta")

    st.markdown("---")

    # ============================================================
    # PROGRAMADOR INTELIGENTE
    # ============================================================
    st.header("Programacion de Turnos (6 semanas)")

    SEMANAS = 6
    DIAS_TOTALES = SEMANAS * 7
    DIA = "D"
    NOCHE = "N"
    DESCANSO = "R"
    PATRONES_CICLO = {"A": [4, 4, 3], "B": [4, 3, 4], "C": [3, 4, 4]}
    nombres_semana = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    NOMBRES_DIAS = [f"S{s+1}-{nombres_semana[d]}" for s in range(SEMANAS) for d in range(7)]
    dias_trabajo_op = round(horas_promedio_operador * SEMANAS / horas_turno)  # 22 con 44h y 12h/turno

    # ----------------------------------------------------------
    # ANALIZADOR DE ESQUEMAS
    # ----------------------------------------------------------
    def analizar_esquemas(dd, dn):
        """
        Encuentra combinaciones (demanda_dia, demanda_noche, N_ops) donde
        N_ops * dias_trabajo_op = D_total * DIAS_TOTALES (distribucion perfecta).
        Retorna lista de opciones ordenadas de mejor a peor.
        """
        opciones = []
        vistos = set()

        for delta_d in range(0, 4):
            for delta_n in range(0, 4):
                d_d = dd + delta_d
                d_n = dn + delta_n
                Dt = d_d + d_n
                # N minimo para distribucion perfecta
                # N * dias_trabajo_op debe ser divisible por DIAS_TOTALES y N*d_t/DIAS_TOTALES = Dt
                N = (Dt * DIAS_TOTALES) // dias_trabajo_op
                if N * dias_trabajo_op == Dt * DIAS_TOTALES:
                    key = (d_d, d_n, N)
                    if key not in vistos:
                        vistos.add(key)
                        es_original = (delta_d == 0 and delta_n == 0)
                        opciones.append({
                            "demanda_dia": d_d,
                            "demanda_noche": d_n,
                            "N_ops": N,
                            "D_total": Dt,
                            "es_original": es_original,
                            "delta_d": delta_d,
                            "delta_n": delta_n,
                            "ajuste": delta_d + delta_n,
                            "perfecto": True,
                        })

        # Si la demanda original no tiene solucion perfecta, agregar como opcion con advertencia
        Dt_orig = dd + dn
        N_orig = math.ceil(Dt_orig * DIAS_TOTALES / dias_trabajo_op)
        key_orig = (dd, dn, N_orig)
        if key_orig not in vistos:
            total_j = N_orig * dias_trabajo_op
            exceso = total_j - Dt_orig * DIAS_TOTALES
            vistos.add(key_orig)
            opciones.append({
                "demanda_dia": dd,
                "demanda_noche": dn,
                "N_ops": N_orig,
                "D_total": Dt_orig,
                "es_original": True,
                "delta_d": 0,
                "delta_n": 0,
                "ajuste": 0,
                "perfecto": False,
                "exceso_jornadas": exceso,
            })

        # Ordenar: perfectos primero, luego por menor ajuste
        opciones.sort(key=lambda x: (not x["perfecto"], x["ajuste"], x["N_ops"]))
        return opciones[:5]

    # ----------------------------------------------------------
    # CONSTRUCTOR DE DIAS DE TRABAJO (BALANCEADO)
    # ----------------------------------------------------------
    def construir_dias_trabajo(N_ops, D_total, combos, seed):
        """
        Construye patron de trabajo con exactamente D_total disponibles cada dia.
        Garantiza 22 dias por operador = 264h = 44h/sem promedio.
        """
        rng = random.Random(seed)
        operadores = [f"Op {i+1}" for i in range(N_ops)]
        trabajo = {}

        for op_idx, op in enumerate(operadores):
            patron = PATRONES_CICLO[combos[op_idx]]
            dias = [False] * DIAS_TOTALES
            offset_base = (op_idx * DIAS_TOTALES) // (N_ops * 1)
            offset_base = offset_base % 7
            for semana in range(SEMANAS):
                n_dias = patron[semana % 3]
                inicio = semana * 7
                offset = (offset_base + semana) % 7
                for d in range(n_dias):
                    dias[inicio + (offset + d) % 7] = True
            trabajo[op] = dias

        # Ajustar disponibles: mover dias dentro de la semana para lograr exactamente D_total por dia
        for dia_idx in range(DIAS_TOTALES):
            semana = dia_idx // 7
            disp = sum(1 for op in operadores if trabajo[op][dia_idx])

            iteraciones = 0
            while disp > D_total and iteraciones < 50:
                ops_hoy = [op for op in operadores if trabajo[op][dia_idx]]
                rng.shuffle(ops_hoy)
                movido = False
                for op in ops_hoy:
                    for dia_alt in range(semana * 7, (semana + 1) * 7):
                        if not trabajo[op][dia_alt]:
                            disp_alt = sum(1 for o in operadores if trabajo[o][dia_alt])
                            if disp_alt < D_total:
                                trabajo[op][dia_idx] = False
                                trabajo[op][dia_alt] = True
                                movido = True
                                break
                    if movido:
                        break
                disp = sum(1 for op in operadores if trabajo[op][dia_idx])
                iteraciones += 1

        return trabajo

    # ----------------------------------------------------------
    # GENERADOR DE PROGRAMACION
    # ----------------------------------------------------------
    def generar_programacion(demanda_dia_uso, demanda_noche_uso, N_ops, seed):
        D_total = demanda_dia_uso + demanda_noche_uso
        rng = random.Random(seed + 1)

        operadores = [f"Op {i+1}" for i in range(N_ops)]
        combos = (["A", "B", "C"] * math.ceil(N_ops / 3))[:N_ops]
        rng.shuffle(combos)
        combo_dict = {f"Op {i+1}": combos[i] for i in range(N_ops)}

        trabajo = construir_dias_trabajo(N_ops, D_total, combos, seed)
        horario = {op: ["W" if trabajo[op][i] else DESCANSO for i in range(DIAS_TOTALES)]
                   for op in operadores}

        for dia_idx in range(DIAS_TOTALES):
            ops_hoy = [op for op in operadores if horario[op][dia_idx] == "W"]
            ops_libre = []
            ops_forzado_noche = []
            for op in ops_hoy:
                ayer = horario[op][dia_idx - 1] if dia_idx > 0 else DESCANSO
                if ayer == NOCHE:
                    ops_forzado_noche.append(op)
                else:
                    ops_libre.append(op)

            rng.shuffle(ops_libre)
            rng.shuffle(ops_forzado_noche)
            cnt_d = 0
            cnt_n = 0

            # Forzados a noche (Regla 5)
            for op in ops_forzado_noche:
                horario[op][dia_idx] = NOCHE
                cnt_n += 1

            # Llenar dia
            for op in ops_libre:
                if cnt_d < demanda_dia_uso and horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = DIA
                    cnt_d += 1

            # Llenar noche
            for op in ops_libre:
                if cnt_n < demanda_noche_uso and horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = NOCHE
                    cnt_n += 1

            # Sobrantes -> descanso (en esquema perfecto nunca deberia haber sobrantes)
            for op in ops_libre:
                if horario[op][dia_idx] == "W":
                    horario[op][dia_idx] = DESCANSO

        # Verificar cobertura
        dias_incompletos = []
        for dia_idx in range(DIAS_TOTALES):
            c_d = sum(1 for op in operadores if horario[op][dia_idx] == DIA)
            c_n = sum(1 for op in operadores if horario[op][dia_idx] == NOCHE)
            if c_d < demanda_dia_uso or c_n < demanda_noche_uso:
                dias_incompletos.append({
                    "Dia": NOMBRES_DIAS[dia_idx],
                    "Dia asignado": c_d, "Dia requerido": demanda_dia_uso,
                    "Noche asignada": c_n, "Noche requerida": demanda_noche_uso
                })

        df = pd.DataFrame(horario, index=NOMBRES_DIAS).T
        df.index.name = "Operador"
        return df, dias_incompletos, combo_dict

    def calcular_estadisticas(df, operadores_list):
        filas = []
        for op in operadores_list:
            fila = {"Operador": op}
            total = 0
            for s in range(SEMANAS):
                dias = NOMBRES_DIAS[s * 7:(s + 1) * 7]
                trabajados = sum(1 for d in dias if df.loc[op, d] in [DIA, NOCHE])
                h = trabajados * horas_turno
                fila[f"S{s+1} dias"] = trabajados
                fila[f"S{s+1} horas"] = h
                total += h
            fila["Total horas"] = total
            fila["Prom h/sem"] = round(total / SEMANAS, 1)
            filas.append(fila)
        return pd.DataFrame(filas).set_index("Operador")

    # ----------------------------------------------------------
    # MOSTRAR OPCIONES DE ESQUEMA
    # ----------------------------------------------------------
    st.subheader("Selecciona el esquema de programacion")

    opciones = analizar_esquemas(demanda_dia, demanda_noche)

    st.info(
        f"El modelo analizo las combinaciones posibles para tu demanda de "
        f"**{demanda_dia}D + {demanda_noche}N**. "
        f"Un esquema es **perfecto** cuando garantiza cobertura exacta todos los dias "
        f"Y exactamente 44h promedio para todos los operadores simultaneamente."
    )

    # Mostrar tabla de opciones
    tabla_opciones = []
    for i, op in enumerate(opciones):
        ajuste_txt = "Sin ajuste" if op["ajuste"] == 0 else f"+{op['delta_d']}D / +{op['delta_n']}N"
        perfecto_txt = "✅ Perfecto" if op["perfecto"] else "⚠️ Aproximado"
        tabla_opciones.append({
            "Opcion": f"Opcion {i+1}",
            "Turno Dia": op["demanda_dia"],
            "Turno Noche": op["demanda_noche"],
            "Ops necesarios": op["N_ops"],
            "Ajuste demanda": ajuste_txt,
            "Calidad": perfecto_txt,
        })
    st.dataframe(pd.DataFrame(tabla_opciones).set_index("Opcion"), use_container_width=True)

    opcion_labels = [
        f"Opcion {i+1}: {op['demanda_dia']}D + {op['demanda_noche']}N | "
        f"{op['N_ops']} ops | {'Perfecto' if op['perfecto'] else 'Aproximado'}"
        for i, op in enumerate(opciones)
    ]
    seleccion_idx = st.radio("Elige el esquema a programar:", range(len(opciones)),
                              format_func=lambda i: opcion_labels[i])
    esquema_sel = opciones[seleccion_idx]

    st.markdown(f"""
    **Esquema seleccionado:**
    - Turno dia: **{esquema_sel['demanda_dia']} operadores**
    - Turno noche: **{esquema_sel['demanda_noche']} operadores**
    - Total operadores a programar: **{esquema_sel['N_ops']}**
    - Calidad: **{'Cobertura exacta + 44h iguales para todos' if esquema_sel['perfecto'] else 'Puede haber variaciones menores en horas'}**
    """)

    # ----------------------------------------------------------
    # BOTONES GENERAR / REGENERAR
    # ----------------------------------------------------------
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

        df, dias_incompletos, combo_dict = generar_programacion(
            esquema_sel["demanda_dia"],
            esquema_sel["demanda_noche"],
            esquema_sel["N_ops"],
            seed
        )
        operadores_list = df.index.tolist()

        # Cobertura
        if not dias_incompletos:
            st.success("Cobertura completa - Todos los dias tienen los operadores requeridos")
        else:
            st.error(f"{len(dias_incompletos)} dias con cobertura incompleta")
            with st.expander("Ver dias incompletos"):
                st.dataframe(pd.DataFrame(dias_incompletos).set_index("Dia"))

        st.markdown("**Leyenda:** D = Turno Dia (6am-6pm) | N = Turno Noche (6pm-6am) | R = Descanso")

        # Horario con colores
        def colorear(val):
            if val == DIA:
                return "background-color: #FFF3CD; color: #856404; font-weight: bold"
            elif val == NOCHE:
                return "background-color: #CCE5FF; color: #004085; font-weight: bold"
            return "background-color: #F8F9FA; color: #ADB5BD"

        st.subheader("Horario completo")
        st.dataframe(df.style.map(colorear), use_container_width=True, height=500)

        # Cobertura diaria
        st.subheader("Cobertura diaria")
        cobertura = []
        for dia in NOMBRES_DIAS:
            c_d = (df[dia] == DIA).sum()
            c_n = (df[dia] == NOCHE).sum()
            ok_d = "OK" if c_d >= esquema_sel["demanda_dia"] else "FALTA"
            ok_n = "OK" if c_n >= esquema_sel["demanda_noche"] else "FALTA"
            cobertura.append({"Dia": dia, f"Dia({ok_d})": c_d, f"Noche({ok_n})": c_n})
        st.dataframe(pd.DataFrame(cobertura).set_index("Dia").T, use_container_width=True)

        # Horas por operador
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

        # Combinaciones
        st.subheader("Combinacion de ciclo por operador")
        combos_nombre = {"A": "A (4-4-3)", "B": "B (4-3-4)", "C": "C (3-4-4)"}
        datos_combo = [{"Operador": op, "Combinacion": combos_nombre[combo_dict[op]]}
                       for op in operadores_list]
        st.dataframe(pd.DataFrame(datos_combo).set_index("Operador"), use_container_width=True)

        # Excel
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
