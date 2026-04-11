import streamlit as st
from supabase import create_client, Client
import hashlib

# --- CONFIGURACIÓN DE CONEXIÓN REAL (Extraída de tus capturas) ---
URL_NUBE = "https://fclmqubtitqdfofidrvj.supabase.co"
KEY_NUBE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZjbG1xdWJ0aXRxZGZvZmlkcnZqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI5NTkxMTcsImV4cCI6MjA1ODUzNTExN30.C3eB-XfE5YpXU6S_4R_o5B-XfE5YpXU6S_4R_o"
supabase: Client = create_client(URL_NUBE, KEY_NUBE)

# --- FUNCIONES DE SEGURIDAD ---
def hash_pass(password):
    """Genera el hash SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

# --- INICIALIZACIÓN DEL ESTADO ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "rol" not in st.session_state:
    st.session_state.rol = None

# --- LÓGICA DE LOGIN ---
def login():
    st.title("🔐 Acceso Sistema Alborada Cloud")
    
    usuario = st.text_input("Usuario").strip()
    clave = st.text_input("Contraseña", type="password")
    
    if st.button("Entrar"):
        if usuario and clave:
            clave_hashed = hash_pass(clave)
            try:
                # Consultamos la tabla 'usuarios' que creamos en el SQL Editor
                res = supabase.table("usuarios").select("*").eq("username", usuario).eq("password", clave_hashed).execute()
                
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.user = res.data[0]['username']
                    st.session_state.rol = res.data[0]['rol']
                    st.rerun()
                else:
                    st.error("Usuario o clave incorrectos")
            except Exception as e:
                st.error(f"Error de conexión: {e}")

# --- CUERPO DE LA APP ---
if not st.session_state.logged_in:
    login()
else:
    st.sidebar.title(f"👤 {st.session_state.user}")
    st.sidebar.write(f"Rol: **{st.session_state.rol}**")
    
    # Menú dinámico
    menu = ["Agenda de Clientes"]
    if st.session_state.rol == "Administrador":
        menu.append("Gestión de Usuarios")
    
    opcion = st.sidebar.selectbox("Menú", menu)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()

    # --- MÓDULO: AGENDA DE CLIENTES ---
    if opcion == "Agenda de Clientes":
        st.header("📋 Gestión de Citas")
        
        with st.expander("➕ Agendar Nuevo Cliente"):
            nombre_c = st.text_input("Nombre del Cliente")
            tel_c = st.text_input("Teléfono")
            serv_c = st.selectbox("Servicio", ["Consulta", "Estética", "Limpieza", "Otros"])
            
            if st.button("Guardar"):
                nuevo_cliente = {
                    "nombre": nombre_c,
                    "telefono": tel_c,
                    "servicio": serv_c,
                    "creado_por": st.session_state.user
                }
                supabase.table("clientes").insert(nuevo_cliente).execute()
                st.success("Cliente guardado")
                st.rerun()

        # Filtro de privacidad
        st.subheader("Registros")
        if st.session_state.rol == "Administrador":
            query = supabase.table("clientes").select("*").execute()
        else:
            query = supabase.table("clientes").select("*").eq("creado_por", st.session_state.user).execute()
        
        if query.data:
            st.dataframe(query.data)

    # --- MÓDULO: GESTIÓN DE USUARIOS ---
    elif opcion == "Gestión de Usuarios":
        st.header("👥 Crear Asesores")
        new_u = st.text_input("Usuario Asesor")
        new_p = st.text_input("Contraseña", type="password")
        
        if st.button("Registrar"):
            datos_u = {
                "username": new_u,
                "password": hash_pass(new_p),
                "rol": "Asesor"
            }
            supabase.table("usuarios").insert(datos_u).execute()
            st.success(f"Asesor {new_u} creado correctamente.")
