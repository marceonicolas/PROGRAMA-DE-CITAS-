import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, timedelta
import bcrypt

# --- CONFIGURACIÓN DE SUPABASE ---
URL_SUPABASE = "TU_URL_DE_SUPABASE"
KEY_SUPABASE = "TU_KEY_DE_SUPABASE"
supabase: Client = create_client(URL_SUPABASE, KEY_SUPABASE)

# --- FUNCIONES DE SEGURIDAD (BCRYPT) ---
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# --- UTILIDADES ---
def enviar_whatsapp(telefono, mensaje):
    # Formato internacional para Paraguay si es necesario (+595)
    url = f"https://wa.me/{telefono}?text={mensaje.replace(' ', '%20')}"
    return url

# --- COMPONENTES DE LA INTERFAZ ---
def login():
    st.title("🦷 Control Alborada - Acceso")
    with st.container(border=True):
        usuario_input = st.text_input("Usuario")
        clave_input = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar", use_container_width=True):
            res = supabase.table("usuarios").select("*").eq("usuario", usuario_input).execute()
            if res.data:
                usuario_db = res.data[0]
                if check_password(clave_input, usuario_db['password']):
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
    
    menu = ["Mis Agendamientos"]
    if user['rol'] == 'admin':
        menu.append("Panel Supervisor")
    
    choice = st.sidebar.selectbox("Ir a:", menu)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()

    # --- VISTA: MIS AGENDAMIENTOS ---
    if choice == "Mis Agendamientos":
        st.header("📅 Gestión de Agendamientos")
        
        # Filtros de Rango
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            f_inicio = st.date_input("Fecha Inicio", datetime.now())
        with col_f2:
            f_fin = st.date_input("Fecha Fin", datetime.now() + timedelta(days=30))

        # Consulta
        query = supabase.table("pacientes").select("*").gte("fecha_cita", str(f_inicio)).lte("fecha_cita", str(f_fin))
        if user['rol'] != 'admin':
            query = query.eq("vendedor_id", user['id'])
        
        data = query.execute().data
        
        if data:
            for row in data:
                # Estilo visual según estado
                emoji = "⏳" if row['estado'] == 'pendiente' else "✅" if row['estado'] == 'firmo' else "❌"
                with st.expander(f"{emoji} {row['nombre']} - {row['fecha_cita']} ({row['estado'].upper()})"):
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**Teléfono:** {row['telefono']}")
                        st.write(f"**Estado Actual:** {row['estado']}")
                    
                    with c2:
                        # Bloqueo total si ya firmó
                        if row['estado'] == 'firmo':
                            st.success("Cliente cerró contrato. No se requieren más acciones.")
                        else:
                            # 1. Botón de Recordatorio (Pendiente)
                            if row['estado'] == 'pendiente':
                                link_rec = enviar_whatsapp(row['telefono'], f"Hola {row['nombre']}, te recordamos tu cita para el {row['fecha_cita']}.")
                                st.link_button("Recordar Cita 📲", link_rec)

                            # 2. Botón de Reagendar (No asistió)
                            if row['estado'] == 'no asistio':
                                link_re = enviar_whatsapp(row['telefono'], "Vimos que no pudiste asistir. ¿Te gustaría reagendar?")
                                st.link_button("Enviar Mensaje Reagendar 🔄", link_re)

                            # 3. Seguimiento de 4 semanas
                            if row['estado'] == 'pendiente' or row['estado'] == 'no asistio':
                                st.write("**Seguimiento:**")
                                s_cols = st.columns(4)
                                for i in range(1, 5):
                                    if s_cols[i-1].button(f"S{i}", key=f"seg_{row['id']}_{i}"):
                                        link_s = enviar_whatsapp(row['telefono'], f"Hola {row['nombre']}, seguimos pendientes de tu caso (Seguimiento Semana {i}).")
                                        st.info(f"Link generado para Semana {i}")
                                        st.markdown(f"[Abrir WhatsApp Semana {i}]({link_s})")

                            # 4. Cambio de Estado y Reagendamiento
                            st.divider()
                            nuevo_estado = st.selectbox("Actualizar Estado", ["pendiente", "no asistio", "firmo", "reagenda"], key=f"st_{row['id']}")
                            
                            if nuevo_estado == "reagenda":
                                n_fecha = st.date_input("Seleccionar Nueva Fecha", key=f"date_{row['id']}")
                                if st.button("Confirmar Nueva Fecha", key=f"btn_re_{row['id']}"):
                                    supabase.table("pacientes").update({"estado": "pendiente", "fecha_cita": str(n_fecha)}).eq("id", row['id']).execute()
                                    st.success("Reagendado correctamente.")
                                    st.rerun()
                            elif st.button("Guardar Cambios", key=f"save_{row['id']}"):
                                supabase.table("pacientes").update({"estado": nuevo_estado}).eq("id", row['id']).execute()
                                st.rerun()
        else:
            st.info("No hay registros en este rango de fechas.")

    # --- VISTA: PANEL SUPERVISOR ---
    elif choice == "Panel Supervisor":
        st.header("👨‍✈️ Panel de Supervisión")
        
        tab1, tab2 = st.tabs(["Crear Asesor", "Gestionar Equipo"])
        
        with tab1:
            with st.form("nuevo_u"):
                u_nom = st.text_input("Nombre de Usuario")
                u_pass = st.text_input("Contraseña", type="password")
                u_rol = st.selectbox("Rol", ["asesor", "admin"])
                if st.form_submit_button("Crear Usuario"):
                    h_pass = hash_password(u_pass)
                    supabase.table("usuarios").insert({"usuario": u_nom, "password": h_pass, "rol": u_rol}).execute()
                    st.success("Usuario creado con éxito")
        
        with tab2:
            usuarios_bd = supabase.table("usuarios").select("*").execute().data
            for u in usuarios_bd:
                c_u, c_b = st.columns([3, 1])
                c_u.write(f"**{u['usuario']}** - {u['rol']}")
                if u['usuario'] != user['usuario']: # No borrarse a sí mismo
                    if c_b.button("Eliminar", key=f"del_{u['id']}"):
                        supabase.table("usuarios").delete().eq("id", u['id']).execute()
                        st.rerun()