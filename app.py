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
    
    # MENÚ EXTENDIDO
    menu = ["Mis Agendamientos", "Registrar Paciente", "Reporte Diario"]
    if user['rol'] == 'admin':
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
                    nuevo_p = {
                        "nombre": nombre, "apellido": apellido, "ci": ci,
                        "telefono": telefono, "fecha_cita": str(fecha_cita),
                        "hora": str(hora_cita), "estado": "pendiente",
                        "vendedor_id": user['id'], "observaciones": observaciones
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

        query = supabase.table("pacientes").select("*").gte("fecha_cita", str(f_inicio)).lte("fecha_cita", str(f_fin))
        if user['rol'] != 'admin':
            query = query.eq("vendedor_id", user['id'])
        
        data = query.execute().data
        
        if data:
            for row in data:
                emoji = "⏳" if row['estado'] == 'pendiente' else "✅" if row['estado'] == 'firmo' else "❌"
                with st.expander(f"{emoji} {row['nombre']} {row['apellido']} - {row['hora']}"):
                    st.write(f"**CI:** {row['ci']} | **Tel:** {row['telefono']}")
                    st.write(f"**Notas:** {row['observaciones']}")
                    
                    if row['estado'] != 'firmo':
                        if row['estado'] == 'pendiente':
                            st.link_button("Recordar Cita 📲", enviar_whatsapp(row['telefono'], f"Hola {row['nombre']}, recordamos tu cita para el {row['fecha_cita']} a las {row['hora']}."))
                        
                        st.divider()
                        nuevo_estado = st.selectbox("Actualizar Estado", ["pendiente", "no asistio", "firmo", "reagenda"], key=f"st_{row['id']}")
                        
                        if nuevo_estado == "reagenda":
                            n_fecha = st.date_input("Nueva Fecha", key=f"d_{row['id']}")
                            if st.button("Confirmar Reagendamiento", key=f"br_{row['id']}"):
                                supabase.table("pacientes").update({"estado": "pendiente", "fecha_cita": str(n_fecha)}).eq("id", row['id']).execute()
                                st.rerun()
                        elif st.button("Guardar Estado", key=f"sv_{row['id']}"):
                            supabase.table("pacientes").update({"estado": nuevo_estado}).eq("id", row['id']).execute()
                            st.rerun()
        else:
            st.info("Sin registros.")

    # --- SECCIÓN: REPORTE DIARIO ---
    elif choice == "Reporte Diario":
        st.header("📊 Reporte Matutino")
        f_rep = st.date_input("Fecha de Reporte", datetime.now())
        data_rep = supabase.table("pacientes").select("*, usuarios(usuario)").eq("fecha_cita", str(f_rep)).execute().data
        
        if data_rep:
            df = pd.DataFrame([{
                "Hora": r['hora'], "Paciente": f"{r['nombre']} {r['apellido']}",
                "CI": r['ci'], "Tel": r['telefono'], "Estado": r['estado'],
                "Asesor": r['usuarios']['usuario'] if r['usuarios'] else "N/A",
                "Notas": r['observaciones']
            } for r in data_rep])
            st.dataframe(df, use_container_width=True)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", data=buffer.getvalue(), file_name=f"Reporte_{f_rep}.xlsx", mime="application/vnd.ms-excel")
        else:
            st.warning("No hay datos para hoy.")

    # --- VISTA: PANEL SUPERVISOR ---
    elif choice == "Panel Supervisor":
        st.header("👨‍✈️ Panel de Supervisión")
        tab1, tab2 = st.tabs(["Crear Asesor", "Gestionar Equipo"])
        with tab1:
            with st.form("nuevo_u"):
                u_nom = st.text_input("Usuario")
                u_pass = st.text_input("Contraseña", type="password")
                u_rol = st.selectbox("Rol", ["asesor", "admin"])
                if st.form_submit_button("Crear"):
                    supabase.table("usuarios").insert({"usuario": u_nom, "password": hash_password(u_pass), "rol": u_rol}).execute()
                    st.success("Creado")
        with tab2:
            usuarios_bd = supabase.table("usuarios").select("*").execute().data
            for u in usuarios_bd:
                col_u, col_b = st.columns([3, 1])
                col_u.write(f"**{u['usuario']}** ({u['rol']})")
                if u['usuario'] != user['usuario'] and col_b.button("Eliminar", key=f"del_{u['id']}"):
                    supabase.table("usuarios").delete().eq("id", u['id']).execute()
                    st.rerun()