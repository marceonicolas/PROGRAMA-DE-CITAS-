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

        query = supabase.table("pacientes").select("*").gte("fecha_cita", str(f_inicio)).lte("fecha_cita", str(f_fin))
        if user['rol'] != 'admin':
            query = query.eq("vendedor_id", user['id'])
        
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
                            msg_rec = f"Hola {row['nombre']}, te recordamos tu cita para el {row['fecha_cita']} a las {row['hora']}."
                            st.link_button("Recordar Cita 📲", enviar_whatsapp(row['telefono'], msg_rec), use_container_width=True)
                            
                            msg_reag = f"Hola {row['nombre']}, ¿te gustaría reagendar tu cita del {row['fecha_cita']}?"
                            st.link_button("Consultar Reagendar 🔄", enviar_whatsapp(row['telefono'], msg_reag), use_container_width=True)

                        if row['estado'] == 'no asistio':
                            st.write("**Seguimiento:**")
                            s_cols = st.columns(4)
                            for i in range(1, 5):
                                msg_s = f"Hola {row['nombre']}, seguimos pendientes de tu caso en Alborada (Seguimiento Semana {i})."
                                s_cols[i-1].link_button(f"S{i}", enviar_whatsapp(row['telefono'], msg_s))

                    with col_acc2:
                        # Campo de nota al cambiar estado
                        nueva_nota_input = st.text_input("Añadir nota al historial:", key=f"n_note_{row['id']}")
                        
                        nuevo_estado = st.selectbox("Actualizar Estado", ["pendiente", "no asistio", "firmo", "reagenda"], 
                                                  index=["pendiente", "no asistio", "firmo", "reagenda"].index(row['estado']) if row['estado'] in ["pendiente", "no asistio", "firmo", "reagenda"] else 0,
                                                  key=f"st_{row['id']}")
                        
                        if nuevo_estado == "reagenda":
                            n_fecha = st.date_input("Nueva Fecha", key=f"d_{row['id']}")
                            n_hora = st.time_input("Nueva Hora", key=f"h_{row['id']}")

                        if st.button("Guardar Cambios", key=f"sv_{row['id']}", use_container_width=True):
                            # Acumular nota
                            h_viejo = row['observaciones'] if row['observaciones'] else ""
                            ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
                            
                            nota_final = f"[{ahora}]: {nueva_nota_input}\n{h_viejo}" if nueva_nota_input else h_viejo

                            upd = {
                                "estado": "pendiente" if nuevo_estado == "reagenda" else nuevo_estado,
                                "observaciones": nota_final
                            }

                            if nuevo_estado == "reagenda":
                                upd["fecha_cita"] = str(n_fecha)
                                upd["hora"] = str(n_hora)

                            supabase.table("pacientes").update(upd).eq("id", row['id']).execute()
                            st.rerun()

                        if st.button("🗑️ Eliminar Paciente", key=f"del_p_{row['id']}", type="secondary", use_container_width=True):
                            supabase.table("pacientes").delete().eq("id", row['id']).execute()
                            st.rerun()
        else:
            st.info("Sin registros.")

    # --- SECCIÓN: REPORTE DIARIO (SOLO ADMIN - GLOBAL) ---
    elif choice == "Reporte Diario" and user['rol'] == 'admin':
        st.header("📊 Reporte Matutino Global")
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
            st.warning("No hay agendamientos registrados para esta fecha.")

    # --- VISTA: PANEL SUPERVISOR (SOLO ADMIN) ---
    elif choice == "Panel Supervisor" and user['rol'] == 'admin':
        st.header("👨‍✈️ Panel de Supervisión")
        tab1, tab2 = st.tabs(["Crear Asesor", "Equipo"])
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