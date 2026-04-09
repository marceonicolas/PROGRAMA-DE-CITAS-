import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('agenda_alborada.db')
    c = conn.cursor()
    # Tabla de Clientes
    c.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT, apellido TEXT, ci TEXT, telefono TEXT,
            fecha DATE, hora TEXT, estado TEXT, creado_por TEXT
        )
    ''')
    # Tabla de Usuarios (Contraseñas)
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, password TEXT, rol TEXT
        )
    ''')
    # Crear usuario administrador por defecto si no existe (Pass: admin123)
    admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
    c.execute('INSERT OR IGNORE INTO usuarios VALUES (?,?,?)', ("admin", admin_pass, "Administrador"))
    conn.commit()
    conn.close()

# --- FUNCIONES DE SEGURIDAD Y DATOS ---
def check_login(user, pwd):
    hashed = hashlib.sha256(pwd.encode()).hexdigest()
    conn = sqlite3.connect('agenda_alborada.db')
    df = pd.read_sql_query(f"SELECT * FROM usuarios WHERE username='{user}' AND password='{hashed}'", conn)
    conn.close()
    return df

def eliminar_paciente(id_p):
    conn = sqlite3.connect('agenda_alborada.db')
    c = conn.cursor()
    c.execute('DELETE FROM clientes WHERE id = ?', (id_p,))
    conn.commit()
    conn.close()

# --- INTERFAZ ---
st.set_page_config(page_title="Alborada Control", layout="wide")
init_db()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- PANTALLA DE LOGIN ---
if not st.session_state['logged_in']:
    st.title("🔐 Acceso Sistema Alborada")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        res = check_login(user, pwd)
        if not res.empty:
            st.session_state['logged_in'] = True
            st.session_state['user'] = user
            st.session_state['rol'] = res.iloc[0]['rol']
            st.rerun()
        else:
            st.error("Usuario o clave incorrectos")
else:
    # --- SISTEMA PRINCIPAL ---
    st.sidebar.title(f"Bienvenido, {st.session_state['user']}")
    st.sidebar.write(f"Rol: {st.session_state['rol']}")
    
    menu = ["Agenda del Día", "Registrar Cliente", "Panel Supervisor"]
    if st.session_state['rol'] != "Administrador":
        menu = ["Agenda del Día", "Registrar Cliente"]
        
    choice = st.sidebar.selectbox("Menú", menu)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

    # 1. AGENDA DEL DÍA
    if choice == "Agenda del Día":
        st.header("📋 Gestión de Citas")
        fecha_sel = st.date_input("Fecha", datetime.now())
        conn = sqlite3.connect('agenda_alborada.db')
        df = pd.read_sql_query(f"SELECT * FROM clientes WHERE fecha='{fecha_sel}' ORDER BY hora ASC", conn)
        
        if not df.empty:
            for i, row in df.iterrows():
                with st.expander(f"🕒 {row['hora']} - {row['nombre']} {row['apellido']} | Estado: {row['estado']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nuevo_est = st.selectbox("Actualizar Estado", 
                            ["Pendiente", "Asistió", "No Asistió", "Reagendado", "Cliente firmó"], 
                            key=f"est_{row['id']}")
                        if st.button("Guardar Cambio", key=f"btn_{row['id']}"):
                            c = conn.cursor()
                            c.execute('UPDATE clientes SET estado=? WHERE id=?', (nuevo_est, row['id']))
                            conn.commit()
                            st.rerun()
                    with col2:
                        if st.session_state['rol'] == "Administrador":
                            if st.button("🗑️ Eliminar Paciente", key=f"del_{row['id']}"):
                                eliminar_paciente(row['id'])
                                st.rerun()
        else:
            st.info("No hay agendados.")
        conn.close()

    # 2. REGISTRAR CLIENTE
    elif choice == "Registrar Cliente":
        st.header("➕ Nuevo Agendamiento")
        with st.form("registro"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nombre")
            a = c2.text_input("Apellido")
            ci = c1.text_input("CI")
            tel = c2.text_input("Teléfono")
            f = c1.date_input("Fecha", datetime.now())
            h = c2.time_input("Hora", datetime.now())
            if st.form_submit_button("Agendar"):
                conn = sqlite3.connect('agenda_alborada.db')
                c = conn.cursor()
                c.execute('INSERT INTO clientes (nombre, apellido, ci, telefono, fecha, hora, estado, creado_por) VALUES (?,?,?,?,?,?,?,?)',
                          (n, a, ci, tel, f, h.strftime("%H:%M"), "Pendiente", st.session_state['user']))
                conn.commit()
                conn.close()
                st.success("Agendado con éxito")

    # 3. PANEL SUPERVISOR (Solo Admin)
    elif choice == "Panel Supervisor":
        st.header("📊 Control Total de Gestión")
        conn = sqlite3.connect('agenda_alborada.db')
        df_all = pd.read_sql_query("SELECT * FROM clientes", conn)
        
        # Métricas rápidas
        c_hoy = len(df_all[df_all['fecha'] == str(datetime.now().date())])
        firmas = len(df_all[df_all['estado'] == "Cliente firmó"])
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Agendados hoy", c_hoy)
        m2.metric("Total Firmas (Ventas)", firmas)
        m3.metric("Total Clientes Base", len(df_all))
        
        st.subheader("Buscador Global")
        buscar = st.text_input("Buscar por Nombre o CI")
        if buscar:
            df_filtered = df_all[df_all['nombre'].str.contains(buscar, case=False) | df_all['ci'].contains(buscar)]
            st.dataframe(df_filtered)
        else:
            st.dataframe(df_all)
        conn.close()