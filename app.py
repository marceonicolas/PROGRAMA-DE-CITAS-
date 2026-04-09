import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib
from io import BytesIO

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('agenda_alborada_v3.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT, apellido TEXT, ci TEXT, telefono TEXT,
            fecha DATE, hora TEXT, estado TEXT, creado_por TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    
    admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
    c.execute('INSERT OR IGNORE INTO usuarios VALUES (?,?,?)', ("admin", admin_pass, "Administrador"))
    conn.commit()
    conn.close()

def hash_pass(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# --- INTERFAZ ---
st.set_page_config(page_title="Control Alborada", layout="wide")
init_db()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔐 Acceso Sistema Alborada")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        hashed = hash_pass(pwd)
        conn = sqlite3.connect('agenda_alborada_v3.db')
        res = pd.read_sql_query(f"SELECT * FROM usuarios WHERE username='{user}' AND password='{hashed}'", conn)
        conn.close()
        if not res.empty:
            st.session_state['logged_in'] = True
            st.session_state['user'] = user
            st.session_state['rol'] = res.iloc[0]['rol']
            st.rerun()
        else:
            st.error("Usuario o clave incorrectos")
else:
    st.sidebar.title(f"👤 {st.session_state['user']}")
    st.sidebar.write(f"Rol: {st.session_state['rol']}")
    
    menu = ["Agenda", "Registrar Cliente", "Mi Cuenta"]
    if st.session_state['rol'] == "Administrador":
        menu += ["Gestión de Asesores", "Panel Supervisor"]
        
    choice = st.sidebar.selectbox("Menú", menu)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

    conn = sqlite3.connect('agenda_alborada_v3.db')

    # 1. AGENDA
    # 1. AGENDA
    if choice == "Agenda":
        st.header("📋 Mis Agendamientos")
        fecha_sel = st.date_input("Fecha", datetime.now())
        
        # Filtro de seguridad por rol
        query = f"SELECT * FROM clientes WHERE fecha='{fecha_sel}'"
        if st.session_state['rol'] != "Administrador":
            query += f" AND creado_por='{st.session_state['user']}'"
        
        df = pd.read_sql_query(query + " ORDER BY hora ASC", conn)
        
        if not df.empty:
            for i, row in df.iterrows():
                # Usamos un ID único para los estados de edición
                with st.expander(f"🕒 {row['hora']} - {row['nombre']} {row['apellido']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        nuevo_est = st.selectbox(
                            "Estado", 
                            ["Pendiente", "Asistió", "No Asistió", "Reagendado", "Cliente firmó"], 
                            index=["Pendiente", "Asistió", "No Asistió", "Reagendado", "Cliente firmó"].index(row['estado']),
                            key=f"est_{row['id']}"
                        )
                        
                        # Si elige Reagendado, mostramos campos extra dentro del mismo expander
                        if nuevo_est == "Reagendado":
                            st.info("Seleccione la nueva cita:")
                            nueva_f = st.date_input("Nueva Fecha", value=datetime.now(), key=f"nf_{row['id']}")
                            nueva_h = st.time_input("Nueva Hora", key=f"nh_{row['id']}")
                            
                            if st.button("Confirmar Reagendamiento", key=f"re_btn_{row['id']}", type="primary"):
                                # ACTUALIZAMOS el mismo registro, no creamos uno nuevo
                                conn.execute('''
                                    UPDATE clientes 
                                    SET fecha=?, hora=?, estado=?, creado_por=? 
                                    WHERE id=?
                                ''', (nueva_f, nueva_h.strftime("%H:%M"), "Pendiente", st.session_state['user'], row['id']))
                                conn.commit()
                                st.success(f"Cita movida al {nueva_f}")
                                st.rerun()
                        else:
                            if st.button("Guardar Estado", key=f"btn_{row['id']}"):
                                conn.execute('UPDATE clientes SET estado=? WHERE id=?', (nuevo_est, row['id']))
                                conn.commit()
                                st.rerun()

                    with col2:
                        if st.button("🗑️ Eliminar", key=f"del_{row['id']}"):
                            conn.execute('DELETE FROM clientes WHERE id=?', (row['id'],))
                            conn.commit()
                            st.rerun()
        else:
            st.info("Sin registros para esta fecha.")

    # 2. REGISTRAR CLIENTE
    elif choice == "Registrar Cliente":
        st.header("➕ Nuevo Registro")
        with st.form("reg"):
            c1, c2 = st.columns(2)
            n, a = c1.text_input("Nombre"), c2.text_input("Apellido")
            ci, tel = c1.text_input("CI"), c2.text_input("Teléfono")
            f, h = c1.date_input("Fecha"), c2.time_input("Hora")
            if st.form_submit_button("Guardar"):
                conn.execute('INSERT INTO clientes (nombre, apellido, ci, telefono, fecha, hora, estado, creado_por) VALUES (?,?,?,?,?,?,?,?)',
                             (n, a, ci, tel, f, h.strftime("%H:%M"), "Pendiente", st.session_state['user']))
                conn.commit()
                st.success("¡Cliente guardado!")

    # 3. MI CUENTA
    elif choice == "Mi Cuenta":
        st.header("⚙️ Configuración de Cuenta")
        st.subheader("Cambiar mi contraseña")
        new_p = st.text_input("Nueva Contraseña", type="password")
        conf_p = st.text_input("Confirmar Nueva Contraseña", type="password")
        if st.button("Actualizar Clave"):
            if new_p == conf_p and new_p != "":
                h_p = hash_pass(new_p)
                conn.execute('UPDATE usuarios SET password=? WHERE username=?', (h_p, st.session_state['user']))
                conn.commit()
                st.success("✅ Contraseña actualizada correctamente.")
            else:
                st.error("Las contraseñas no coinciden.")

    # 4. GESTIÓN DE ASESORES (MEJORADO)
    elif choice == "Gestión de Asesores":
        st.header("👥 Administración de Equipo")
        
        tab1, tab2 = st.tabs(["Crear Asesor", "Listado y Eliminación"])
        
        with tab1:
            with st.form("new_user"):
                new_u = st.text_input("Nombre de Usuario")
                new_p_u = st.text_input("Contraseña", type="password")
                rol = st.selectbox("Rol", ["Asesor", "Administrador"])
                if st.form_submit_button("Crear"):
                    h_p = hash_pass(new_p_u)
                    try:
                        conn.execute('INSERT INTO usuarios VALUES (?,?,?)', (new_u, h_p, rol))
                        conn.commit()
                        st.success(f"Usuario {new_u} creado.")
                        st.rerun()
                    except:
                        st.error("El usuario ya existe.")
        
        with tab2:
            usuarios_df = pd.read_sql_query("SELECT username, rol FROM usuarios", conn)
            for i, u_row in usuarios_df.iterrows():
                col_u1, col_u2 = st.columns([3, 1])
                col_u1.write(f"**{u_row['username']}** - Rol: {u_row['rol']}")
                if u_row['username'] != 'admin': # No permitir borrar al admin principal
                    if col_u2.button("Eliminar", key=f"del_user_{u_row['username']}"):
                        conn.execute('DELETE FROM usuarios WHERE username=?', (u_row['username'],))
                        conn.commit()
                        st.warning(f"Usuario {u_row['username']} eliminado.")
                        st.rerun()

    # 5. PANEL SUPERVISOR (REASIGNACIÓN DE CLIENTES)
    elif choice == "Panel Supervisor":
        st.header("📊 Reasignación y Reportes")
        
        # --- SECCIÓN DE REASIGNACIÓN ---
        st.subheader("🔄 Reasignar Clientes")
        st.info("Usa esta sección si un asesor ya no está y quieres pasar sus clientes a otro.")
        
        df_completo = pd.read_sql_query("SELECT DISTINCT creado_por FROM clientes", conn)
        asesores_con_data = df_completo['creado_por'].tolist()
        asesores_actuales = pd.read_sql_query("SELECT username FROM usuarios", conn)['username'].tolist()
        
        c_re1, c_re2 = st.columns(2)
        vendedor_saliente = c_re1.selectbox("Pasar clientes de:", asesores_con_data)
        vendedor_entrante = c_re2.selectbox("Asignar a:", asesores_actuales)
        
        if st.button("Confirmar Traspaso de Clientes"):
            if vendedor_saliente != vendedor_entrante:
                conn.execute('UPDATE clientes SET creado_por=? WHERE creado_por=?', (vendedor_entrante, vendedor_saliente))
                conn.commit()
                st.success(f"¡Hecho! Los clientes de {vendedor_saliente} ahora pertenecen a {vendedor_entrante}.")
                st.rerun()
            else:
                st.error("Selecciona asesores diferentes para reasignar.")

        st.divider()
        
        # --- REPORTE GENERAL ---
        st.subheader("📝 Reporte de Clientes")
        df_all = pd.read_sql_query("SELECT * FROM clientes", conn)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_all.to_excel(writer, index=False, sheet_name='Reporte')
        st.download_button(label="📥 Descargar Reporte en Excel", data=output.getvalue(), file_name="reporte_alborada.xlsx")
        
        st.dataframe(df_all, use_container_width=True)

    conn.close()