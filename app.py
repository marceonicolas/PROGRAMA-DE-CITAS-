import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib
from io import BytesIO
import urllib.parse # Necesario para los links de WhatsApp

# --- BLOQUE DE REPARACIÓN DE BASE DE DATOS ---
def parchear_base_datos():
    # Nos conectamos al nombre de archivo que usa tu sistema actual
    conn = sqlite3.connect('agenda_alborada_v3.db') 
    cursor = conn.cursor()
    try:
        # Intentamos agregar las columnas que le faltan a tu archivo antiguo
        cursor.execute('ALTER TABLE clientes ADD COLUMN hora TEXT DEFAULT "00:00"')
        cursor.execute('ALTER TABLE clientes ADD COLUMN creado_por TEXT DEFAULT "admin"')
        conn.commit()
    except Exception:
        # Si las columnas ya existen, el programa simplemente sigue adelante
        pass
    finally:
        conn.close()

# Ejecutamos la reparación antes de iniciar la interfaz
parchear_base_datos()

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

# --- FUNCIÓN PARA WHATSAPP ---
def crear_link_wa(telefono, mensaje):
    tel_limpio = "".join(filter(str.isdigit, str(telefono)))
    if tel_limpio.startswith("0"):
        tel_limpio = "595" + tel_limpio[1:]
    elif len(tel_limpio) == 9 and tel_limpio.startswith("9"):
        tel_limpio = "595" + tel_limpio
    
    msg_url = urllib.parse.quote(mensaje)
    return f"https://wa.me/{tel_limpio}?text={msg_url}"

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
    if choice == "Agenda":
        st.header("📋 Mis Agendamientos")
        
        col_fecha, col_mes = st.columns([2, 1])
        
        with col_fecha:
            rango_fechas = st.date_input(
                "Selecciona el rango de días",
                value=[datetime.now(), datetime.now()],
                help="Haz clic en la fecha de inicio y luego en la fecha de fin para seleccionar un rango."
            )
            
        with col_mes:
            if st.button("📅 Seleccionar Mes Actual"):
                hoy = datetime.now()
                inicio_mes = hoy.replace(day=1)
                if hoy.month == 12:
                    fin_mes = hoy.replace(year=hoy.year + 1, month=1, day=1)
                else:
                    fin_mes = hoy.replace(month=hoy.month + 1, day=1)
                st.session_state['rango_manual'] = [inicio_mes.date(), fin_mes.date()]
                st.rerun()

        if isinstance(rango_fechas, list) or isinstance(rango_fechas, tuple):
            if len(rango_fechas) == 2:
                inicio, fin = rango_fechas
                query = f"SELECT * FROM clientes WHERE fecha BETWEEN '{inicio}' AND '{fin}'"
            else:
                inicio = rango_fechas[0]
                query = f"SELECT * FROM clientes WHERE fecha = '{inicio}'"
        
        if st.session_state['rol'] != "Administrador":
            query += f" AND creado_por='{st.session_state['user']}'"
        
        df = pd.read_sql_query(query + " ORDER BY fecha ASC, hora ASC", conn)
        
        if not df.empty:
            st.write(f"Mostrando **{len(df)}** registros encontrados.")
            for i, row in df.iterrows():
                try:
                    fecha_formato = datetime.strptime(row['fecha'], '%Y-%m-%d').strftime('%d/%m/%Y')
                except:
                    fecha_formato = row['fecha']
                
                with st.expander(f"📅 {fecha_formato} | 🕒 {row['hora']} - {row['nombre']} {row['apellido']} ({row['estado']})"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        nuevo_est = st.selectbox(
                            "Cambiar Estado", 
                            ["Pendiente", "Asistió", "No Asistió", "Reagendado", "Cliente firmó"], 
                            index=["Pendiente", "Asistió", "No Asistió", "Reagendado", "Cliente firmó"].index(row['estado']),
                            key=f"est_{row['id']}"
                        )
                        
                        if nuevo_est == "Reagendado":
                            st.info("Seleccione la nueva cita:")
                            nueva_f = st.date_input("Nueva Fecha", value=datetime.now(), key=f"nf_{row['id']}")
                            nueva_h = st.time_input("Nueva Hora", key=f"nh_{row['id']}")
                            
                            if st.button("Confirmar Reagendamiento", key=f"re_btn_{row['id']}", type="primary"):
                                conn.execute('UPDATE clientes SET fecha=?, hora=?, estado=? WHERE id=?', 
                                             (nueva_f, nueva_h.strftime("%H:%M"), "Pendiente", row['id']))
                                conn.commit()
                                st.success("Cita reagendada.")
                                st.rerun()
                        else:
                            if st.button("Guardar Estado", key=f"btn_{row['id']}"):
                                conn.execute('UPDATE clientes SET estado=? WHERE id=?', (nuevo_est, row['id']))
                                conn.commit()
                                st.rerun()

                    with col2:
                        st.write("**Datos de contacto y Acciones:**")
                        st.write(f"CI: {row['ci']} | Tel: {row['telefono']}")
                        st.divider()
                        nombre_full = f"{row['nombre']} {row['apellido']}"
                        
                        if row['estado'] == "Pendiente":
                            msg_rec = f"Hola {nombre_full}, te recordamos tu cita en Alborada para el {fecha_formato} a las {row['hora']}. ¡Te esperamos!"
                            st.link_button("🔔 Recordar Cita", crear_link_wa(row['telefono'], msg_rec), use_container_width=True)
                        
                        if row['estado'] == "No Asistió":
                            msg_reag = f"Hola {nombre_full}, lamentamos que no hayas podido asistir a tu cita el {fecha_formato}. ¿Para qué fecha te gustaría reagendar?"
                            st.link_button("🔄 Invitar a Reagendar", crear_link_wa(row['telefono'], msg_reag), use_container_width=True)
                        
                        st.write("✨ **Seguimiento Estratégico**")
                        msg_s1 = f"Hola {nombre_full}, ¿cómo estás? Paso a saludarte para recordarte que seguimos con espacio disponible. ¡Cuidar tu salud es la mejor inversión!"
                        st.link_button("💬 Seguimiento", crear_link_wa(row['telefono'], msg_s1), use_container_width=True)
                        
                        st.divider()
                        if st.button("🗑️ Eliminar Registro", key=f"del_{row['id']}"):
                            conn.execute('DELETE FROM clientes WHERE id=?', (row['id'],))
                            conn.commit()
                            st.rerun()
        else:
            st.info("No hay agendamientos para el rango seleccionado.")

    # 2. REGISTRAR CLIENTE
    elif choice == "Registrar Cliente":
        st.header("➕ Nuevo Registro")
        with st.form("form_registro", clear_on_submit=True):
            row1_col1, row1_col2 = st.columns(2)
            n = row1_col1.text_input("Nombre")
            a = row1_col2.text_input("Apellido")
            row2_col1, row2_col2 = st.columns(2)
            ci = row2_col1.text_input("CI")
            tel = row2_col2.text_input("Teléfono")
            row3_col1, row3_col2 = st.columns(2)
            f = row3_col1.date_input("Fecha")
            h = row3_col2.time_input("Hora")
            
            submit_button = st.form_submit_button("Guardar Registro", type="primary")

            if submit_button:
                if n and a:
                    conn.execute('INSERT INTO clientes (nombre, apellido, ci, telefono, fecha, hora, estado, creado_por) VALUES (?,?,?,?,?,?,?,?)',
                                 (n, a, ci, tel, f, h.strftime("%H:%M"), "Pendiente", st.session_state['user']))
                    conn.commit()
                    st.success(f"¡Cliente {n} {a} guardado!")
                else:
                    st.error("Por favor, completa Nombre y Apellido.")

    # 3. MI CUENTA
    elif choice == "Mi Cuenta":
        st.header("🔐 Configuración de Seguridad")
        st.subheader(f"Usuario: {st.session_state['user']}")
        with st.form("change_password_form"):
            nueva_pass = st.text_input("Nueva Contraseña", type="password")
            confirmar_pass = st.text_input("Confirmar Nueva Contraseña", type="password")
            if st.form_submit_button("Actualizar Contraseña", type="primary"):
                if nueva_pass and nueva_pass == confirmar_pass:
                    hashed_new_pass = hash_pass(nueva_pass)
                    conn.execute('UPDATE usuarios SET password=? WHERE username=?', (hashed_new_pass, st.session_state['user']))
                    conn.commit()
                    st.success("✅ Contraseña actualizada.")
                else:
                    st.error("Las contraseñas no coinciden.")

    # 4. GESTIÓN DE ASESORES
    elif choice == "Gestión de Asesores":
        st.header("👥 Administración de Equipo")
        tab1, tab2 = st.tabs(["Crear Asesor", "Listado"])
        with tab1:
            with st.form("new_user"):
                new_u = st.text_input("Nombre de Usuario")
                new_p_u = st.text_input("Contraseña", type="password")
                rol = st.selectbox("Rol", ["Asesor", "Administrador"])
                if st.form_submit_button("Crear"):
                    try:
                        conn.execute('INSERT INTO usuarios VALUES (?,?,?)', (new_u, hash_pass(new_p_u), rol))
                        conn.commit()
                        st.success(f"Usuario {new_u} creado.")
                        st.rerun()
                    except:
                        st.error("El usuario ya existe.")
        with tab2:
            usuarios_df = pd.read_sql_query("SELECT username, rol FROM usuarios", conn)
            st.dataframe(usuarios_df, use_container_width=True)

    # 5. PANEL SUPERVISOR
    elif choice == "Panel Supervisor":
        st.header("📊 Reasignación y Reportes")
        df_all = pd.read_sql_query("SELECT * FROM clientes", conn)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_all.to_excel(writer, index=False, sheet_name='Reporte')
        st.download_button(label="📥 Descargar Reporte en Excel", data=output.getvalue(), file_name="reporte_alborada.xlsx")
        st.dataframe(df_all, use_container_width=True)

    conn.close()