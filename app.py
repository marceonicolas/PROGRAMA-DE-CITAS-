import streamlit as st
from supabase import create_client, Client
import hashlib

# --- CONFIGURACIÓN DE CONEXIÓN ---
URL_NUBE = "TU_URL_DE_SUPABASE"
KEY_NUBE = "TU_KEY_ANON_PUBLICA"
supabase: Client = create_client(URL_NUBE, KEY_NUBE)

# --- FUNCIONES DE SEGURIDAD ---
def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login():
    st.title("🔐 Acceso Sistema Alborada Cloud")
    
    usuario = st.text_input("Usuario")
    clave = st.text_input("Contraseña", type="password")
    
    if st.button("Entrar"):
        clave_hashed = hash_pass(clave)
        res = supabase.table("usuarios").select("*").eq("username", usuario).eq("password", clave_hashed).execute()
        
        if res.data:
            st.session_state.logged_in = True
            st.session_state.user = res.data[0]['username']
            st.session_state.rol = res.data[0]['rol']
            st.rerun()
        else:
            st.error("Usuario o clave incorrectos")

# --- INTERFAZ PRINCIPAL ---
if "logged_in" not in st.session_state:
    login()
else:
    st.sidebar.title(f"Bienvenido, {st.session_state.user}")
    st.sidebar.write(f"Rol: {st.session_state.rol}")
    
    opcion = st.sidebar.selectbox("Menú", ["Agenda de Clientes", "Gestión de Usuarios"])
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state.logged_in
        st.rerun()

    # --- MÓDULO: AGENDA DE CLIENTES ---
    if opcion == "Agenda de Clientes":
        st.header("📋 Gestión de Clientes")
        
        with st.expander("➕ Agendar Nuevo Cliente"):
            nombre_c = st.text_input("Nombre del Cliente")
            tel_c = st.text_input("Teléfono")
            serv_c = st.selectbox("Servicio", ["Limpieza", "Extracción", "Estética", "Consulta"])
            f_agenda = st.date_input("Fecha de Cita")
            
            if st.button("Guardar Cliente"):
                datos_cliente = {
                    "nombre": nombre_c,
                    "telefono": tel_c,
                    "servicio": serv_c,
                    "fecha_agenda": str(f_agenda),
                    "creado_por": st.session_state.user # Guardamos quién lo creó
                }
                supabase.table("clientes").insert(datos_cliente).execute()
                st.success("Cliente agendado con éxito")
                st.rerun()

        # --- LÓGICA DE VISUALIZACIÓN POR ROL ---
        st.subheader("Listado de Citas")
        if st.session_state.rol == "Administrador":
            # El Admin ve TODO
            query = supabase.table("clientes").select("*").execute()
        else:
            # El Asesor solo ve lo que ÉL creó
            query = supabase.table("clientes").select("*").eq("creado_por", st.session_state.user).execute()
        
        if query.data:
            st.table(query.data)
        else:
            st.info("No hay clientes registrados para mostrar.")

    # --- MÓDULO: GESTIÓN DE USUARIOS (Solo Admin) ---
    elif opcion == "Gestión de Usuarios":
        if st.session_state.rol == "Administrador":
            st.header("👥 Crear Nuevo Asesor")
            
            new_user = st.text_input("Nuevo nombre de usuario")
            new_pass = st.text_input("Contraseña para el asesor", type="password")
            
            if st.button("Registrar Asesor"):
                if new_user and new_pass:
                    datos_user = {
                        "username": new_user,
                        "password": hash_pass(new_pass), # Se guarda encriptado
                        "rol": "Asesor"
                    }
                    try:
                        supabase.table("usuarios").insert(datos_user).execute()
                        st.success(f"Asesor {new_user} creado correctamente")
                    except Exception as e:
                        st.error(f"Error: Tal vez el usuario ya existe.")
                else:
                    st.warning("Completa todos los campos")
        else:
            st.error("No tienes permisos para acceder a esta sección.")