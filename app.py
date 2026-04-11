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
    
    menu = ["Mis Agendamientos", "Registrar Paciente"]
    if user['rol'] == 'admin':
        menu.append("Reporte Diario")
        menu.append("Producción Diaria")
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

        # Filtro estricto: Cada asesor ve solo lo suyo.
        query = supabase.table("pacientes").select("*").eq("vendedor_id", user['id']).gte("fecha_cita", str(f_inicio)).lte("fecha_cita", str(f_fin))
        data = query.execute().data
        
        if data:
            for row in data:
                emoji = "⏳" if row['estado'] == 'pendiente' else "✅" if row['estado'] == 'firmo' else "❌"
                with st.expander(f"{emoji} {row['nombre']} {row['apellido']} - {row['fecha_cita']} {row['hora']}"):
                    st.write(f"**CI:** {row['ci']} | **Tel:** {row['telefono']}")
                    st.caption("Historial de Notas:")
                    st.text_area("Historial", value=row['observaciones'], height=120, disabled=True, key=f"hist_{row['id']}")
                    st.divider()
                    col_acc1, col_acc2 = st.columns(2)
                    with col_acc1:
                        if row['estado'] == 'pendiente':
                            # SOLUCIÓN ERROR F-STRING: Llave cerrada correctamente
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
                        nueva_nota_input = st.text_input("Añadir nota al historial:", key=f"n_note_{row['id']}")
                        nuevo_estado = st.selectbox("Actualizar Estado", ["pendiente", "no asistio", "firmo", "reagenda"], 
                                                  index=["pendiente", "no asistio", "firmo", "reagenda"].index(row['estado']) if row['estado'] in ["pendiente", "no asistio", "firmo", "reagenda"] else 0,
                                                  key=f"st_{row['id']}")
                        
                        if nuevo_estado == "reagenda":
                            n_fecha = st.date_input("Nueva Fecha", key=f"d_{row['id']}")
                            n_hora = st.time_input("Nueva Hora", key=f"h_{row['id']}")

                        if st.button("Guardar Cambios", key=f"sv_{row['id']}", use_container_width=True):
                            h_viejo = row['observaciones'] if row['observaciones'] else ""
                            ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
                            nota_final = f"[{ahora}]: {nueva_nota_input}\n{h_viejo}" if nueva_nota_input else h_viejo
                            upd = {"estado": "pendiente" if nuevo_estado == "reagenda" else nuevo_estado, "observaciones": nota_final}
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
        
        # 1. Traemos TODOS los registros de la tabla pacientes para esa fecha
        # Quitamos cualquier filtro de 'vendedor_id' para que sea global
        res_pacientes = supabase.table("pacientes").select("*").eq("fecha_cita", str(f_rep)).execute()
        data_p = res_pacientes.data
        
        if data_p:
            # 2. Traemos la lista de usuarios para ponerle nombre al ID del asesor
            res_usuarios = supabase.table("usuarios").select("id, usuario").execute()
            mapa_usuarios = {u['id']: u['usuario'] for u in res_usuarios.data}
            
            reporte_final = []
            for r in data_p:
                # 3. Cruzamos el dato manualmente
                id_vendedor = r.get('vendedor_id')
                nombre_asesor = mapa_usuarios.get(id_vendedor, f"Asesor ID: {id_vendedor}")
                
                reporte_final.append({
                    "Hora": r.get('hora', '00:00'),
                    "Paciente": f"{r.get('nombre', '')} {r.get('apellido', '')}",
                    "CI": r.get('ci', ''),
                    "Tel": r.get('telefono', ''),
                    "Estado": r.get('estado', 'pendiente'),
                    "Asesor": nombre_asesor, # Aquí aparecerá 'admin_alborada', 'Marta', etc.
                    "Notas": r.get('observaciones', '')
                })
            
            # Mostramos la tabla global
            df = pd.DataFrame(reporte_final)
            st.write(f"Mostrando {len(df)} registros totales del equipo:")
            st.dataframe(df, use_container_width=True)
            
            # Botón de descarga para tu control en Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Descargar Reporte Completo", buffer.getvalue(), f"Global_{f_rep}.xlsx")
        else:
            st.warning(f"No hay nada cargado para el {f_rep} por ningún usuario.")
    
    # --- SECCIÓN: REPORTE DIARIO (EXISTENTE) ---
    elif choice == "Reporte Diario" and user['rol'] == 'admin':
        # (Aquí va todo el código de tu reporte actual
    # --- PRODUCCION DIARIA ---
    elif choice == "Producción Diaria" and user['rol'] == 'admin':
        st.header("📈 Producción Diaria (Rendimiento)")
        st.write("Pacientes captados y registrados por el equipo el día de hoy.")
        
        hoy_str = datetime.now().strftime("%Y-%m-%d")
        
        res_p = supabase.table("pacientes").select("*").gte("creado_en", hoy_str).execute()
        data_prod = res_p.data
        
        if data_prod:
            res_u = supabase.table("usuarios").select("id, usuario").execute()
            mapa_asesores = {u['id']: u['usuario'] for u in res_u.data}
            
            prod_hoy = [r for r in data_prod if r['creado_en'].startswith(hoy_str)]
            
            if prod_hoy:
                df_p = pd.DataFrame([{
                    "Asesor": mapa_asesores.get(r['vendedor_id'], "N/A"),
                    "Paciente": f"{r['nombre']} {r['apellido']}",
                    "Fecha Cita": r['fecha_cita'],
                    "Hora de Carga": r['creado_en'][11:16],
                    "Estado": r['estado']
                } for r in prod_hoy])

                c1, c2 = st.columns(2)
                c1.metric("Total Registros Hoy", len(df_p))
                c2.metric("Asesor más activo", df_p['Asesor'].value_counts().idxmax())

                st.dataframe(df_p, use_container_width=True)
                
                st.subheader("Resumen de Cantidades")
                resumen = df_p['Asesor'].value_counts().reset_index()
                resumen.columns = ['Asesor', 'Cantidad']
                st.table(resumen)
            else:
                st.info("Aún no hay actividad de carga hoy.")
        else:
            st.warning("No se encontraron registros creados hoy.")
    elif choice == "Panel Supervisor" and user['rol'] == 'admin':
      
    # --- VISTA: PANEL SUPERVISOR (ADMIN) ---
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
