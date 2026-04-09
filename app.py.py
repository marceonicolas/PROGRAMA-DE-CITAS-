import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('agenda_clientes.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            apellido TEXT,
            ci TEXT,
            telefono TEXT,
            fecha DATE,
            estado TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- FUNCIONES DE LÓGICA ---
def agregar_cliente(nombre, apellido, ci, telefono, fecha):
    conn = sqlite3.connect('agenda_clientes.db')
    c = conn.cursor()
    c.execute('INSERT INTO clientes (nombre, apellido, ci, telefono, fecha, estado) VALUES (?,?,?,?,?,?)',
              (nombre, apellido, ci, telefono, fecha, 'Pendiente'))
    conn.commit()
    conn.close()

def actualizar_estado(id_cliente, nuevo_estado):
    conn = sqlite3.connect('agenda_clientes.db')
    c = conn.cursor()
    c.execute('UPDATE clientes SET estado = ? WHERE id = ?', (nuevo_estado, id_cliente))
    conn.commit()
    conn.close()

# --- INTERFAZ DE USUARIO (STREAMLIT) ---
st.set_page_config(page_title="Gestión de Citas", layout="wide")
init_db()

st.title("🏥 Sistema de Gestión de Pacientes")

menu = ["Registrar Cliente", "Agenda del Día", "Historial Completo"]
choice = st.sidebar.selectbox("Menú", menu)

if choice == "Registrar Cliente":
    st.subheader("Cargar nuevo agendamiento")
    with st.form("form_registro"):
        col1, col2 = st.columns(2)
        nombre = col1.text_input("Nombre")
        apellido = col2.text_input("Apellido")
        ci = col1.text_input("C.I. / Documento")
        tel = col2.text_input("Teléfono")
        fecha = st.date_input("Fecha de la cita", datetime.now())
        
        submit = st.form_submit_button("Guardar Agendamiento")
        
        if submit:
            agregar_cliente(nombre, apellido, ci, tel, fecha)
            st.success(f"Cliente {nombre} {apellido} agendado correctamente.")

elif choice == "Agenda del Día":
    fecha_hoy = st.date_input("Filtrar por fecha", datetime.now())
    st.subheader(f"Pacientes para el día: {fecha_hoy}")
    
    conn = sqlite3.connect('agenda_clientes.db')
    df = pd.read_sql_query(f"SELECT * FROM clientes WHERE fecha = '{fecha_hoy}'", conn)
    conn.close()

    if not df.empty:
        for index, row in df.iterrows():
            with st.expander(f"{row['nombre']} {row['apellido']} - Estado: {row['estado']}"):
                st.write(f"**CI:** {row['ci']} | **Tel:** {row['telefono']}")
                nuevo_estado = st.selectbox("Cambiar estado", 
                                          ["Pendiente", "Asistió", "No Asistió", "Reagendado"], 
                                          key=row['id'])
                if st.button("Actualizar", key=f"btn_{row['id']}"):
                    actualizar_estado(row['id'], nuevo_estado)
                    st.rerun()
    else:
        st.info("No hay citas para esta fecha.")

elif choice == "Historial Completo":
    st.subheader("Todos los registros")
    conn = sqlite3.connect('agenda_clientes.db')
    df_total = pd.read_sql_query("SELECT * FROM clientes", conn)
    conn.close()
    st.dataframe(df_total, use_container_width=True)