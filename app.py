import streamlit as st
from supabase import create_client, Client
import hashlib

# --- CONFIGURACIÓN DE CONEXIÓN REAL ---
URL_NUBE = "https://fclmqubtitqdfofidrvj.supabase.co"
KEY_NUBE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZjbG1xdWJ0aXRxZGZvZmlkcnZqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI5NTkxMTcsImV4cCI6MjA1ODUzNTExN30.C3eB-XfE5YpXU6S_4R_o5B-XfE5YpXU6S_4R_o"
supabase: Client = create_client(URL_NUBE, KEY_NUBE)

# --- FUNCIONES DE SEGURIDAD ---
def hash_pass(password):
    """Genera el hash SHA-256 para validación de contraseñas."""
    return hashlib.sha256(password.encode()).hexdigest()

# --- INICIALIZACIÓN DEL ESTADO (Solución al KeyError de image_887f4d.png) ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "rol" not in st.session_state:
    st.session_state.rol = None

# --- MÓDULO DE LOGIN ---
def login():
    st.title("🔐 Acceso Sistema Alborada Cloud")
    
    usuario = st.text_input("Usuario").strip()
    clave = st.text_input("Contraseña", type="password")
    
    if st.button("Entrar"):
        if usuario and clave:
            clave_hashed = hash_pass(clave)
            try:
                # Buscamos en la tabla 'usuarios'
                res = supabase.table("usuarios").select("*").eq("username", usuario).eq("password", clave_hashed).execute()
                
                if res.data:
                    st.session_state.logged_in = True
                    st.session_state.user = res.data[0]['username']
                    st.session_state.rol = res.data[0]['rol']
                    st.success("Acceso concedido")
                    st.rerun()
                else:
                    st.error("Usuario o clave incorrectos")
            except Exception as e:
                st.error(f"Error de conexión: {e}")
        else:
            st.warning("Por favor, completa los campos.")

# --- LÓGICA DE NAVEGACIÓN ---
if not st.session_state.logged_in:
    login()
else:
    # --- BARRA LATERAL ---
    st.sidebar.title(f"👤 {st.session_state.user}")
    st.sidebar.write(f"Acceso: **{st.session_state.rol}**")
    
    opciones = ["Agenda de Clientes"]
    if st.session_state.rol == "Administrador":
        opciones.append("Gestión de Usuarios")
    
    opcion = st.sidebar.selectbox("Seleccionar Módulo", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    # --- MÓDULO 1: AGENDA DE CLIENTES ---
    if opcion == "Agenda de Clientes":
        st.header("📋 Gestión de Citas")
        
        with st.expander("➕ Agendar Nuevo Cliente"):
            with st.form("nuevo_cliente"):
                nom = st.text_input("Nombre del Cliente")
                tel = st.text_input("Teléfono")
                ser = st.selectbox("Servicio", ["Consulta", "Estética", "Limpieza", "Otros"])
                
                if st.form_submit_button("Guardar Registro"):
                    if nom and tel:
                        data_cliente = {
                            "nombre": nom,
                            "telefono": tel,
                            "servicio": ser,
                            "creado_por": st.session_state.user
                        }
                        supabase.table("clientes").insert(data_cliente).execute()
                        st.success("✅ Registrado con éxito")
                        st.rerun()
                    else:
                        st.error("Faltan datos obligatorios.")

        # --- VISUALIZACIÓN CON FILTRO POR ROL ---
        st.subheader("Registros en Sistema")
        try:
            if st.session_state.rol == "Administrador":
                # Admin ve todo
                query = supabase.table("clientes").select("*").execute()
            else:
                # Asesor solo ve lo que él creó
                query = supabase.table("clientes").select("*").eq("creado_por", st.session_state.user).execute()
            
            if query.data:
                st.dataframe(query.data, use_container_width=True)
            else:
                st.info("No hay clientes registrados aún.")
        except Exception as e:
            st.error(f"Error al cargar clientes: {e}")

    # --- MÓDULO 2: GESTIÓN DE USUARIOS (Solo Admin) ---
    elif opcion == "Gestión de Usuarios":
        st.header("👥 Crear Cuentas de Asesores")
        
        with st.form("crear_asesor"):
            u_name = st.text_input("Nombre de Usuario").strip()
            u_pass = st.text_input("Contraseña", type="password")
            
            if st.form_submit_button("Dar de Alta"):
                if u_name and u_pass:
                    h_pass = hash_pass(u_pass)
                    data_u = {"username": u_name, "password": h_pass, "rol": "Asesor"}
                    try:
                        supabase.table("usuarios").insert(data_u).execute()
                        st.success(f"Asesor {u_name} creado con éxito.")
                    except:
                        st.error("El usuario ya existe o hubo un error.")
                else:
                    st.warning("Completa los campos.")
