import streamlit as st
import math
import pandas as pd
import random

st.set_page_config(page_title="Calculadora de Personal", layout="wide")

st.title("🧮 Calculadora de Personal Operativo")

# -----------------------
# INPUTS
# -----------------------

demanda_dia = st.number_input("Operadores turno día", value=5)
demanda_noche = st.number_input("Operadores turno noche", value=5)
horas_turno = 12
SEMANAS = 6

# -----------------------
# CALCULO BASE
# -----------------------

horas_totales = (demanda_dia + demanda_noche) * horas_turno * 7
operadores_final = math.ceil(horas_totales / 44)

st.write(f"Operadores requeridos: **{operadores_final}**")

# -----------------------
# CONSTANTES
# -----------------------

TURNO_DIA = "D"
TURNO_NOCHE = "N"
DESCANSO = "R"

nombres_semana = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"]
NOMBRES_DIAS = [f"S{s}-{d}" for s in range(1,SEMANAS+1) for d in nombres_semana]

PATRONES = {
    0:[4,4,3],
    1:[4,3,4],
    2:[3,4,4]
}

# -----------------------
# DIAS DE TRABAJO
# -----------------------

def construir_dias(num_ops):
    trabajo={}
    for i in range(num_ops):
        dias=[False]*42
        patron=PATRONES[i%3]
        for s in range(SEMANAS):
            n=patron[s%3]
            base=s*7
            offset=(i*3+s)%7
            for d in range(n):
                dias[base+(offset+d)%7]=True
        trabajo[f"Op {i+1}"]=dias
    return trabajo

# -----------------------
# GENERADOR (CON TU REGLA)
# -----------------------

def generar(num_ops):
    ops=[f"Op {i+1}" for i in range(num_ops)]
    trabajo=construir_dias(num_ops)

    horario={op:["W" if trabajo[op][i] else "R" for i in range(42)] for op in ops}

    for dia in range(42):
        hoy=[op for op in ops if horario[op][dia]=="W"]

        libres=[]
        vienen_noche=[]

        for op in hoy:
            ayer=horario[op][dia-1] if dia>0 else "R"
            if ayer=="N":
                vienen_noche.append(op)
            else:
                libres.append(op)

        random.shuffle(libres)
        random.shuffle(vienen_noche)

        d,n=0,0

        # Día
        for op in libres:
            if d<demanda_dia and horario[op][dia]=="W":
                horario[op][dia]="D"
                d+=1

        # Noche
        for op in libres+vienen_noche:
            if n<demanda_noche and horario[op][dia]=="W":
                horario[op][dia]="N"
                n+=1

        # sobrantes
        for op in libres+vienen_noche:
            if horario[op][dia]=="W":
                horario[op][dia]="N"

    return pd.DataFrame(horario,index=NOMBRES_DIAS).T

# -----------------------
# GENERAR
# -----------------------

if st.button("Generar programación"):

    df=generar(operadores_final)

    st.markdown("**Leyenda:** D = Día | N = Noche | R = Descanso")

    def color(val):
        if val=="D": return "background-color:#FFF3CD"
        if val=="N": return "background-color:#CCE5FF"
        return "background-color:#F8F9FA"

    st.subheader("Horario completo")
    st.dataframe(df.style.map(color),use_container_width=True)

    # -----------------------
    # COBERTURA
    # -----------------------

    cobertura=[]
    for d in NOMBRES_DIAS:
        cd=(df[d]=="D").sum()
        cn=(df[d]=="N").sum()
        cobertura.append({"Dia":d,"Dia":cd,"Noche":cn})

    st.subheader("Cobertura diaria")
    st.dataframe(pd.DataFrame(cobertura).set_index("Dia").T)

    # -----------------------
    # HORAS
    # -----------------------

    filas=[]
    for op in df.index:
        total=0
        fila={"Operador":op}
        for s in range(SEMANAS):
            dias=NOMBRES_DIAS[s*7:(s+1)*7]
            t=sum(df.loc[op,d]!="R" for d in dias)
            h=t*12
            fila[f"S{s+1} dias"]=t
            fila[f"S{s+1} horas"]=h
            total+=h
        fila["Total"]=total
        fila["Prom"]=round(total/SEMANAS,1)
        filas.append(fila)

    stats=pd.DataFrame(filas).set_index("Operador")

    st.subheader("Horas trabajadas por operador")
    st.dataframe(stats)

    # -----------------------
    # CICLOS
    # -----------------------

    combos={0:"A (4-4-3)",1:"B (4-3-4)",2:"C (3-4-4)"}
    data=[{"Operador":op,"Ciclo":combos[i%3]} for i,op in enumerate(df.index)]

    st.subheader("Combinación de ciclo")
    st.dataframe(pd.DataFrame(data).set_index("Operador"))

    # -----------------------
    # EXCEL
    # -----------------------

    file="turnos.xlsx"
    with pd.ExcelWriter(file) as writer:
        df.to_excel(writer,"Programacion")
        stats.to_excel(writer,"Horas")
        pd.DataFrame(cobertura).to_excel(writer,"Cobertura")

    with open(file,"rb") as f:
        st.download_button("Descargar Excel",f,file)
