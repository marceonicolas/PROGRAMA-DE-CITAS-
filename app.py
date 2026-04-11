import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import hashlib
from io import BytesIO
import urllib.parse

# --- 1. CONFIGURACIÓN DE CONEXIÓN (NUBE) ---
# REEMPLAZA ESTOS DATOS con los de tu panel de Supabase (Settings > API)
URL_NUBE = "https://aaoezefzcfgpfupuqfur.supabase.co" 
KEY_NUBE = "sb_publishable_7lZS0TMERbN27D-MX9SNEA_ih-6YTdL" 

supabase: Client = create_client(URL_NUBE, KEY_NUBE)

# --- 2. FUNCIONES DE SEGURIDAD ---
def hash_pass(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# --- 3. FUNCIONES DE DATOS (NUBE) ---
def registrar_cliente_nube(n, a, ci, tel, f, h, usuario):
    datos = {
        "nombre": n, "apellido": a, "ci": ci, 
        "telefono": tel, "fecha": str(f), 
        "hora": h.strftime("%H:%M"), "estado": "Pendiente",
        "creado_por": usuario
    }
    supabase.table("clientes").insert(datos).execute()

def actualizar_estado_nube(id_cliente, nuevo_estado):
    supabase.table("clientes").update({"estado": nuevo_estado}).eq("id", id_cliente).execute()

def reagendar_cita_nube(id_cliente, nueva_f, nueva_h):
    supabase.table("clientes").update({
        "fecha": str(nueva_f), 
        "hora": nueva_h.strftime("%H:%M"),
        "estado": "Pendiente"
    }).eq("id", id_cliente).execute()

def eliminar_cliente_nube(id_cliente):
    supabase.table("clientes").delete().eq("id", id_cliente).execute()

# --- 4. FUNCIÓN PARA WHATSAPP ---
def crear_link_wa(telefono, mensaje):
    tel_limpio = "".join(filter(str.isdigit, str(telefono)))
    if tel_limpio.startswith("0"):
        tel_limpio = "595" + tel_limpio[1:]
    msg_url = urllib.parse.quote(mensaje)
    return f"https://wa.me/{tel_limpio}?text={msg_url}"

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Control Alborada Cloud", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- LOGIN ---
if not st.session_state['logged_in']:
    st.title("🔐 Acceso Sistema Alborada Cloud")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    
    if st.button("Entrar"):
        hashed = hash_pass(pwd)
        # Consulta de usuarios en la nube
        res = supabase.table("usuarios").select("*").eq("username", user).eq("password", hashed).execute()
        
        if res.data:
            st.session_state['logged_in'] = True
            st.session_state['user'] = user
            st.session_state['rol'] = res.data[0]['rol']
            st.rerun()
        else:
            st.error("Usuario o clave incorrectos")

else:
    # --- INTERFAZ PRINCIPAL ---
    st.sidebar.title(f"👤 {st.session_state['user']}")
    st.sidebar.write(f"Rol: {st.session_state['rol']}")
    
    menu = ["Agenda", "Registrar Cliente", "Mi Cuenta"]
    if st.session_state['rol'] == "Administrador":
        menu += ["Gestión de Asesores", "Panel Supervisor"]
        
    choice = st.sidebar.selectbox("Menú", menu)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

    # --- LÓGICA DE MENÚS ---
    if choice == "Agenda":
        st.header("📋 Mis Agendamientos (Nube)")
        
        col_fecha, col_mes = st.columns([2, 1])
        with col_fecha:
            rango = st.date_input("Rango de fechas", value=[datetime.now(), datetime.now()])
        
        # Consulta filtrada
        query = supabase.table("clientes").select("*")
        if len(rango) == 2:
            query = query.gte("fecha", str(rango[0])).lte("fecha", str(rango[1]))
        
        if st.session_state['rol'] != "Administrador":
            query = query.eq("creado_por", st.session_state['user'])
        
        res = query.order("fecha").order("hora").execute()
        df = pd.DataFrame(res.data)

        if not df.empty:
            for i, row in df.iterrows():
                with st.expander(f"📅 {row['fecha']} | 🕒 {row['hora']} - {row['nombre']} {row['apellido']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        nuevo_est = st.selectbox("Estado", ["Pendiente", "Asistió", "No Asistió", "Reagendado", "Cliente firmó"], index=0, key=f"st_{row['id']}")
                        if nuevo_est == "Reagendado":
                            nf = st.date_input("Nueva Fecha", key=f"nf_{row['id']}")
                            nh = st.time_input("Nueva Hora", key=f"nh_{row['id']}")
                            if st.button("Confirmar Reagendamiento", key=f"rb_{row['id']}"):
                                reagendar_cita_nube(row['id'], nf, nh)
                                st.rerun()
                        elif st.button("Actualizar Estado", key=f"ub_{row['id']}"):
                            actualizar_estado_nube(row['id'], nuevo_est)
                            st.rerun()
                    with c2:
                        st.write(f"CI: {row['ci']} | Tel: {row['telefono']}")
                        msg = f"Hola {row['nombre']}, te recordamos tu cita..."
                        st.link_button("🔔 WhatsApp", crear_link_wa(row['telefono'], msg))
                        if st.button("🗑️ Eliminar", key=f"del_{row['id']}"):
                            eliminar_cliente_nube(row['id'])
                            st.rerun()

    elif choice == "Registrar Cliente":
        st.header("➕ Nuevo Registro")
        with st.form("registro"):
            n = st.text_input("Nombre")
            a = st.text_input("Apellido")
            ci = st.text_input("CI")
            tel = st.text_input("Teléfono")
            f = st.date_input("Fecha")
            h = st.time_input("Hora")
            if st.form_submit_button("Guardar en la Nube"):
                registrar_cliente_nube(n, a, ci, tel, f, h, st.session_state['user'])
                st.success("Guardado exitosamente")

    elif choice == "Panel Supervisor":
        st.header("📊 Reporte General")
        res = supabase.table("clientes").select("*").execute()
        df_all = pd.DataFrame(res.data)
        st.dataframe(df_all)
        # Botón para descargar Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_all.to_excel(writer, index=False)
        st.download_button("📥 Descargar Excel", output.getvalue(), "reporte.xlsx")