import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, timedelta
import bcrypt
import io

# --- CONFIGURACIÓN DE SUPABASE ---
URL_SUPABASE = "https://aaoezefzcfgpfupuqfur.supabase.co"
KEY_SUPABASE = "sb_publishable_7lZS0TMERbN27D-MX9SNEA_ih-6YTdL"
supabase: Client = create_client(URL_SUPABASE, KEY_SUPABASE)

# --- FUNCIONES AUXILIARES ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def enviar_whatsapp(telefono, mensaje):
    import urllib.parse
    msg = urllib.parse.quote(mensaje)
    return f"https://wa.me/{telefono}?text={msg}"

# --- FUNCIONES DE SEGURIDAD ---
def login():
    st.title("🦷 Control Alborada - Acceso")
    usuario_input = st.text_input("Usuario")
    clave_input = st.text_input("Contraseña", type="password")
    
    if st.button("Ingresar"):
        res = supabase.table("usuarios").select("*").eq("usuario", usuario_input).execute()
        
        if res.data:
            usuario_db = res.data[0]
            es_valida = False
            if clave_input == usuario_db['password']:
                es_valida = True
            else:
                try:
                    if bcrypt.checkpw(clave_input.encode('utf-8'), usuario_db['password'].encode('utf-8')):
                        es_valida = True
                except:
                    pass

            if es_valida:
                st.session_state.logged_in = True
                st.session_state.user_data = usuario_db
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        else:
            st.error("Usuario no encontrado")

# --- LÓGICA DE LA APP ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
else:
    user = st.session_state.user_data
    st.sidebar.title(f"Hola, {user['usuario']}")
    st.sidebar.info(f"Rol: {user['rol'].capitalize()}")
    
    # MENÚ EXTENDIDO (FILTRADO POR ROL)
    menu = ["Mis Agendamientos", "Registrar Paciente"]
    if user['rol'] == 'admin':
        menu.append("Reporte Diario")
        menu.append("Panel Supervisor")
    
    choice = st.sidebar.selectbox("Ir a:", menu)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()

    # --- SECCIÓN: REGISTRAR PACIENTE ---
    if choice == "Registrar Paciente":
        st.header("📝 Registro de Nuevo Agendamiento")
        with st.form("form_registro", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre")
                apellido = st.text_input("Apellido")
                ci = st.text_input("C.I. N°")
                telefono = st.text_input("Teléfono (Ej: 595981...)")
            with col2:
                fecha_cita = st.date_input("Fecha de la Cita", datetime.now())
                hora_cita = st.time_input("Hora de la Cita")
            
            observaciones = st.text_area("Observaciones / Notas")
            
            if st.form_submit_button("Guardar Paciente"):
                if nombre and apellido and telefono:
                    # Nota inicial con marca de tiempo
                    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
                    nota_inc = f"[{ahora}]: Registro inicial. {observaciones}" if observaciones else f"[{ahora}]: Registro inicial."
                    
                    nuevo_p = {
                        "nombre": nombre, "apellido": apellido, "ci": ci,
                        "telefono": telefono, "fecha_cita": str(fecha_cita),
                        "hora": str(hora_cita), "estado": "pendiente",
                        "vendedor_id": user['id'], "observaciones": nota_inc
                    }
                    supabase.table("pacientes").insert(nuevo_p).execute()
                    st.success(f"✅ Paciente {nombre} registrado correctamente.")
                else:
                    st.warning("Completa Nombre, Apellido y Teléfono.")

    # --- VISTA: MIS AGENDAMIENTOS ---
    elif choice == "Mis Agendamientos":
        st.header("📅 Mis Gestiones")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            f_inicio = st.date_input("Fecha Inicio", datetime.now())
        with col_f2:
            f_fin = st.date_input("Fecha Fin", datetime.now() + timedelta(days=30))

        # CORRECCIÓN: Filtramos SIEMPRE por el ID del usuario logueado. 
        # Así, el asesor ve solo lo suyo y tú, como admin, ves solo lo que tú agendaste personalmente.
        query = supabase.table("pacientes").select("*").eq("vendedor_id", user['id']).gte("fecha_cita", str(f_inicio)).lte("fecha_cita", str(f_fin))
        
        data = query.execute().data
        
        if data:
            for row in data:
                emoji = "⏳" if row['estado'] == 'pendiente' else "✅" if row['estado'] == 'firmo' else "❌"
                with st.expander(f"{emoji} {row['nombre']} {row['apellido']} - {row['fecha_cita']} {row['hora']}"):
                    st.write(f"**CI:** {row['ci']} | **Tel:** {row['telefono']}")
                    
                    # Bitácora de notas
                    st.caption("Historial de Notas:")
                    st.text_area("Historial", value=row['observaciones'], height=120, disabled=True, key=f"hist_{row['id']}")
                    
                    st.divider()

                    col_acc1, col_acc2 = st.columns(2)

                    with col_acc1:
                        if row['estado'] == 'pendiente':
                            msg_rec = f"Hola {row['nombre']}, te recordamos tu cita para el {row['fecha_cita']} a las {row