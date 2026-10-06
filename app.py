import io
import zipfile
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
import bcrypt
import db
import compromisos
import consumo as calc_consumo
import estados
import moras
import recibo
import reportes

st.set_page_config(page_title="Residencial EQUIZ", page_icon="🏢", layout="wide")

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

PISOS = ["Planta Baja", "Primer Piso", "Segundo Piso", "Tercer Piso"]
ROLES = ["Administrador", "Cobrador"]

CATEGORIAS_GASTO = ["Mantenimiento de ascensores", "Artículos de limpieza", "Seguridad",
                    "Servicios públicos", "Mantenimiento general", "Otro"]
CATEGORIAS_PAGO = ["Servicios (luz, agua, internet)", "Sueldos y honorarios", "Impuestos y tasas",
                   "Pago a proveedor", "Otro"]
CONCEPTOS_VENTA = ["Alquiler de área común", "Venta de activos fijos", "Emisión de tag/control de acceso",
                   "Alquiler de parqueo de visitas", "Copias de llaves", "Otro"]
METODOS_PAGO_MOVIMIENTOS = ["Efectivo", "QR", "Transferencia Bancaria", "Tarjeta", "Otro"]

PRIORIDADES_PENDIENTE = ["Urgente", "Alta", "Media", "Baja"]
ESTADOS_PENDIENTE = ["Pendiente", "En Proceso", "Terminado"]
COLOR_PRIORIDAD = {"Urgente": "🔴", "Alta": "🟠", "Media": "🟡", "Baja": "🟢"}
ICONO_ESTADO = {"Pendiente": "⏳", "En Proceso": "🔧", "Terminado": "✅"}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ------------------------------------------------------------------
# Autenticación con usuario/contraseña y roles (Administrador / Cobrador)
# ------------------------------------------------------------------
def check_login():
    if st.session_state.get("usuario"):
        return True

    st.title("🏢 Residencial EQUIZ")
    st.caption("Sistema de control de apartamentos y alquileres")

    try:
        usuarios_existentes = db.listar_usuarios()
    except Exception as e:
        st.error(f"No se pudo conectar con la base de usuarios: {e}")
        st.info("¿Ya ejecutaste migracion_usuarios.sql en Supabase?")
        return False

    if not usuarios_existentes:
        st.info("Aún no hay usuarios creados. Crea la cuenta del **Administrador principal**:")
        with st.form("form_primer_admin"):
            username = st.text_input("Usuario (para iniciar sesión)")
            nombre = st.text_input("Nombre completo")
            pwd1 = st.text_input("Contraseña", type="password")
            pwd2 = st.text_input("Repetir contraseña", type="password")
            crear = st.form_submit_button("Crear administrador")
            if crear:
                if not username or not pwd1:
                    st.error("Usuario y contraseña son obligatorios.")
                elif pwd1 != pwd2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    try:
                        db.crear_usuario({
                            "username": username.strip().lower(),
                            "nombre": nombre or None,
                            "password_hash": hash_password(pwd1),
                            "rol": "Administrador",
                            "activo": True,
                        })
                        st.success("Administrador creado. Ahora inicia sesión.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear el usuario: {e}")
        return False

    username = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        usuario = db.obtener_usuario_por_username(username.strip().lower())
        if usuario and usuario.get("activo") and verificar_password(pwd, usuario["password_hash"]):
            st.session_state["usuario"] = usuario
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos, o el usuario está desactivado.")

    with st.expander("¿Problemas para entrar? Usar clave general de administrador"):
        pwd_general = st.text_input("Clave general", type="password", key="pwd_general")
        if st.button("Ingresar con clave general"):
            if pwd_general and pwd_general == st.secrets.get("APP_PASSWORD", ""):
                st.session_state["usuario"] = {"username": "admin", "nombre": "Administrador",
                                                "rol": "Administrador"}
                st.rerun()
            else:
                st.error("Clave incorrecta.")
    return False


if not check_login():
    st.stop()

usuario_actual = st.session_state["usuario"]
es_admin = usuario_actual.get("rol") == "Administrador"


# ------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------
def fmt_money(v):
    try:
        return f"Bs {float(v):,.2f}"
    except (TypeError, ValueError):
        return "Bs 0.00"


def detalle_monto_servicio(consumo, tarifa):
    """Resultado de consumo × tarifa para mostrar en pantalla: 'Bs 76.70 → **Bs 77.00** (redondeado al entero)'
    si el redondeo cambia el monto, o solo '**Bs 77.00**' si ya era entero."""
    exacto = calc_consumo.monto_exacto(consumo, tarifa)
    final = calc_consumo.calcular_monto(consumo, tarifa)
    if abs(exacto - final) > 0.004:
        return f"{fmt_money(exacto)} → **{fmt_money(final)}** (redondeado al entero)"
    return f"**{fmt_money(final)}**"


@st.cache_data(ttl=30)
def cargar_apartamentos():
    return db.listar_apartamentos()


@st.cache_data(ttl=30)
def cargar_periodos(apartamento_id=None, anio=None, mes=None):
    return db.listar_periodos(apartamento_id=apartamento_id, anio=anio, mes=mes)


@st.cache_data(ttl=30)
def cargar_periodos_electricidad(anio=None, mes=None):
    return db.listar_periodos_electricidad(anio=anio, mes=mes)


@st.cache_data(ttl=30)
def cargar_periodos_agua(anio=None, mes=None):
    return db.listar_periodos_agua(anio=anio, mes=mes)


@st.cache_data(ttl=60)
def cargar_periodos_abiertos(tipo):
    return db.listar_periodos_abiertos(tipo)


AVISO_MIGRACION_ESTADOS = (
    "El campo **Estado** todavía no está activo en la base de datos: ejecuta el archivo "
    "`migracion_estados_movimientos.sql` en el SQL Editor de Supabase. Mientras tanto, esta sección "
    "funciona normal, sin ese campo."
)


@st.cache_data(ttl=60)
def estado_disponible(tabla, columna):
    """¿Ya existe la columna de estado? (si aún no se ejecutó la migración, la app sigue funcionando sin ella)"""
    return db.columna_disponible(tabla, columna)


@st.cache_data(ttl=30)
def cargar_compromisos():
    return db.listar_compromisos()


@st.cache_data(ttl=30)
def cargar_actividad(desde, hasta):
    """Pagos, compras y ventas del rango (completos, sin el tope de 1000 filas)."""
    return {t: db.listar_actividad_rango(t, desde, hasta) for t in ("pagos_generales", "compras", "ventas")}


@st.cache_data(ttl=300, show_spinner=False)
def _actividad_excel_cache(reps, desde, hasta, emitido_por):
    return reportes.generar_excel_reporte(reps, desde, hasta, emitido_por=emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _actividad_pdf_cache(reps, desde, hasta, emitido_por):
    return reportes.generar_pdf_reporte(reps, desde, hasta, emitido_por=emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _reporte_pdf_cache(datos):
    return recibo.generar_reporte_inquilino_pdf(datos)


@st.cache_data(ttl=300, show_spinner=False)
def _reporte_png_cache(datos):
    return recibo.generar_reporte_inquilino_png(datos)


def _nombre_archivo_reporte(apt, hoy, extension):
    codigo = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(apt.get("codigo") or "apto"))
    return f"estado_cuenta_{codigo}_{hoy:%Y-%m-%d}.{extension}"


def total_pagado(periodo):
    return sum(float(p["monto"]) for p in (periodo.get("pagos") or []))


def mostrar_botones_recibo(pago, periodo, apartamento, total_pagado_periodo, key_sufijo):
    """Muestra dos botones de descarga (PDF y PNG) para el recibo de un abono
    de alquiler. Se usa tanto en la vista normal como en el historial."""
    try:
        datos_recibo = recibo.construir_datos_recibo(
            pago, periodo, apartamento, total_pagado_periodo,
            recibido_por=usuario_actual.get("nombre") or usuario_actual.get("username"),
        )
        col_pdf, col_png = st.columns(2)
        with col_pdf:
            st.download_button(
                "📄 Descargar recibo (PDF)",
                data=recibo.generar_recibo_pdf(datos_recibo),
                file_name=f'{datos_recibo["numero_recibo"]}.pdf',
                mime="application/pdf",
                use_container_width=True,
                key=f'recibo_pdf_{key_sufijo}',
            )
        with col_png:
            st.download_button(
                "🖼️ Descargar recibo (PNG)",
                data=recibo.generar_recibo_png(datos_recibo),
                file_name=f'{datos_recibo["numero_recibo"]}.png',
                mime="image/png",
                use_container_width=True,
                key=f'recibo_png_{key_sufijo}',
            )
    except Exception as e:
        st.caption(f"⚠️ No se pudo preparar el recibo: {e}")


@st.cache_data(ttl=30)
def cargar_pendientes(estado=None, prioridad=None, asignado_a=None):
    return db.listar_pendientes(estado=estado, prioridad=prioridad, asignado_a=asignado_a)


@st.cache_data(ttl=30)
def cargar_reuniones(fecha_desde=None, fecha_hasta=None):
    return db.listar_reuniones(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)


@st.cache_data(ttl=30)
def cargar_participantes_reuniones():
    return db.listar_participantes_reuniones()


@st.cache_data(ttl=60)
def cargar_usuarios_activos():
    return [u for u in db.listar_usuarios() if u.get("activo")]


@st.cache_data(ttl=60)
def cargar_todos_los_usuarios():
    return db.listar_usuarios()


def limpiar_cache():
    estado_disponible.clear()
    cargar_compromisos.clear()
    cargar_actividad.clear()
    cargar_apartamentos.clear()
    cargar_periodos.clear()
    cargar_periodos_electricidad.clear()
    cargar_periodos_agua.clear()
    cargar_periodos_abiertos.clear()
    cargar_pendientes.clear()
    cargar_reuniones.clear()
    cargar_participantes_reuniones.clear()
    cargar_usuarios_activos.clear()
    cargar_todos_los_usuarios.clear()


def parse_fecha(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def fecha_vencimiento_del_mes(fecha_ingreso: date, anio: int, mes_num: int):
    """Día de pago mensual = mismo día del mes que la fecha de ingreso (ajustado si el mes es más corto)."""
    ultimo_dia_mes = calendar.monthrange(anio, mes_num)[1]
    dia = min(fecha_ingreso.day, ultimo_dia_mes)
    return date(anio, mes_num, dia)


def calcular_mora_alquiler(apt, periodos_mes_actual_por_apt):
    """Devuelve (en_mora, dias_atraso, deuda) para un apartamento, según su fecha de pago mensual."""
    if apt["estado"] != "Ocupado":
        return False, 0, 0.0
    fecha_ingreso = parse_fecha(apt.get("fecha_ingreso"))
    hoy = date.today()
    dia_pago = fecha_ingreso if fecha_ingreso else date(hoy.year, hoy.month, 1)
    vencimiento = fecha_vencimiento_del_mes(dia_pago, hoy.year, hoy.month)
    if hoy <= vencimiento:
        return False, 0, 0.0  # todavía no vence el pago de este mes

    periodo = periodos_mes_actual_por_apt.get(apt["id"])
    monto_esperado = float(periodo["monto_esperado"]) if periodo else float(apt.get("monto_alquiler") or 0)
    pagado = total_pagado(periodo) if periodo else 0.0
    deuda = monto_esperado - pagado
    if deuda <= 0:
        return False, 0, 0.0
    dias_atraso = (hoy - vencimiento).days
    return True, dias_atraso, deuda


def estado_contrato_alerta(apt):
    """Devuelve (nivel, texto) para contratos vencidos o por vencer en los próximos 30 días. None si no aplica."""
    hoy = date.today()
    fecha_fin = parse_fecha(apt.get("contrato_fecha_fin"))
    estado = apt.get("estado_contrato") or "Sin Contrato"

    if estado == "Caducado":
        return "🔴 Vencido", None
    if fecha_fin:
        dias = (fecha_fin - hoy).days
        if dias < 0:
            return "🔴 Vencido", abs(dias)
        if dias <= 30:
            return "🟠 Por vencer", dias
    return None, None


def ultimos_n_meses(n=12):
    """Lista de (anio, mes_num) de los últimos n meses, terminando en el mes actual, en orden cronológico."""
    hoy = date.today()
    resultado = []
    for i in range(n - 1, -1, -1):
        offset = hoy.month - 1 - i
        anio = hoy.year + offset // 12
        mes_num = offset % 12 + 1
        resultado.append((anio, mes_num))
    return resultado


# ------------------------------------------------------------------
# Sidebar / navegación
# ------------------------------------------------------------------
st.sidebar.title("🏢 Residencial EQUIZ")
st.sidebar.caption(f'👤 {usuario_actual.get("nombre") or usuario_actual.get("username")} · {usuario_actual.get("rol")}')

if es_admin:
    opciones_principal = ["📊 Dashboard", "🏠 Apartamentos", "💵 Pagos de Alquiler", "⚡ Electricidad",
                          "💧 Agua", "🤝 Compromisos de pago", "👥 Usuarios"]
else:
    # "🏠 Inquilinos" es la consulta de solo lectura de los datos de cada apartamento
    opciones_principal = ["📊 Dashboard", "🏠 Inquilinos", "💵 Pagos de Alquiler", "⚡ Electricidad", "💧 Agua",
                          "🤝 Compromisos de pago"]

opciones_movimientos = ["(ninguno)", "🧾 Compras", "💳 Pagos", "💸 Ventas"]
opciones_administracion = ["(ninguno)", "✅ Pendientes", "🗒️ Reuniones"]
opciones_reportes = ["(ninguno)", "📑 Estado de cuenta", "📊 Actividad por usuario"]

# Los radios de abajo son independientes en el estado interno de Streamlit:
# si eliges algo en uno, los demás no se "enteran" y siguen marcando su
# propia opción. Eso es lo que hacía que a veces no se pudiera cambiar de
# sección (había que volver manualmente a "(ninguno)" primero). Estos
# callbacks resetean los demás radios apenas se elige uno, para que el
# cambio de sección sea siempre inmediato.
_MODULOS_NAV = ["nav_movimientos", "nav_administracion", "nav_reportes"]


def _reiniciar_modulos(excepto=None):
    """Deja en '(ninguno)' todos los módulos del menú salvo 'excepto'."""
    for clave in _MODULOS_NAV:
        if clave != excepto:
            st.session_state[clave] = "(ninguno)"


def _al_elegir_principal():
    _reiniciar_modulos()


def _al_elegir_movimientos():
    if st.session_state["nav_movimientos"] != "(ninguno)":
        _reiniciar_modulos("nav_movimientos")


def _al_elegir_administracion():
    if st.session_state["nav_administracion"] != "(ninguno)":
        _reiniciar_modulos("nav_administracion")


def _al_elegir_reportes():
    if st.session_state["nav_reportes"] != "(ninguno)":
        _reiniciar_modulos("nav_reportes")


pagina_principal = st.sidebar.radio("Gestión del Residencial", opciones_principal, key="nav_principal",
                                     on_change=_al_elegir_principal)
st.sidebar.divider()
st.sidebar.caption("📒 Módulo de Movimientos")
pagina_movimientos = st.sidebar.radio("Compras y Ventas", opciones_movimientos, key="nav_movimientos",
                                       label_visibility="collapsed", on_change=_al_elegir_movimientos)
st.sidebar.divider()
st.sidebar.caption("🗂️ Módulo Administración")
pagina_administracion = st.sidebar.radio("Administración", opciones_administracion, key="nav_administracion",
                                          label_visibility="collapsed", on_change=_al_elegir_administracion)
st.sidebar.divider()
st.sidebar.caption("📑 Módulo de Reportes")
pagina_reportes = st.sidebar.radio("Reportes", opciones_reportes, key="nav_reportes",
                                    label_visibility="collapsed", on_change=_al_elegir_reportes)

if pagina_movimientos != "(ninguno)":
    pagina = pagina_movimientos
elif pagina_administracion != "(ninguno)":
    pagina = pagina_administracion
elif pagina_reportes != "(ninguno)":
    pagina = pagina_reportes
else:
    pagina = pagina_principal
st.sidebar.divider()
if st.sidebar.button("🔄 Actualizar datos"):
    limpiar_cache()
    st.rerun()
if st.sidebar.button("🚪 Cerrar sesión"):
    del st.session_state["usuario"]
    st.rerun()


# ==================================================================
# PÁGINA: DASHBOARD
# ==================================================================
if pagina == "📊 Dashboard":
    st.title("📊 Dashboard General")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("Aún no hay apartamentos registrados. Ve a la sección **Apartamentos** para agregarlos.")
        st.stop()

    df_apt = pd.DataFrame(apartamentos)

    # ---------------- Moras: alquiler, electricidad y agua ----------------
    hoy = recibo.hoy_bolivia()
    cfg_col = {
        "Departamento": st.column_config.TextColumn("Departamento", width="small"),
        "Inquilino": st.column_config.TextColumn("Inquilino", width="large"),
        "Meses atrasados": st.column_config.NumberColumn("Meses atrasados", format="%d", width="small"),
        "Deuda total": st.column_config.NumberColumn("Deuda total", format="Bs %.2f", width="small"),
    }
    mora_alquiler = moras.calcular_mora_alquiler(apartamentos, cargar_periodos_abiertos("alquiler"), hoy)
    mora_elec = moras.calcular_mora_consumo(
        apartamentos, cargar_periodos_abiertos("electricidad"), "pagos_electricidad", hoy)
    mora_agua = moras.calcular_mora_consumo(
        apartamentos, cargar_periodos_abiertos("agua"), "pagos_agua", hoy)

    def _total(filas):
        return sum(f["Deuda total"] for f in filas)

    st.subheader("🚨 Moras (deudas pendientes)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"💵 Alquiler ({len(mora_alquiler)} deptos.)", fmt_money(_total(mora_alquiler)))
    m2.metric(f"⚡ Electricidad ({len(mora_elec)} deptos.)", fmt_money(_total(mora_elec)))
    m3.metric(f"💧 Agua ({len(mora_agua)} deptos.)", fmt_money(_total(mora_agua)))
    m4.metric("Total en mora", fmt_money(_total(mora_alquiler) + _total(mora_elec) + _total(mora_agua)))

    for titulo, filas, vacio in [
        ("💵 Mora de alquiler", mora_alquiler, "Sin alquileres atrasados."),
        ("⚡ Mora de electricidad", mora_elec, "Sin deudas de electricidad."),
        ("💧 Mora de agua", mora_agua, "Sin deudas de agua."),
    ]:
        with st.container(border=True):
            st.markdown(f"**{titulo}**")
            if filas:
                st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True,
                             column_config=cfg_col)
            else:
                st.success(vacio)
    st.caption(
        "Alquiler: deuda real. Cuenta los meses con saldo pendiente cuyo día de pago ya pasó (campo «Día de "
        "Pago» de la ficha; si no hay, el día de ingreso) y también los meses sin ningún registro desde el "
        "primer mes registrado (o la fecha de ingreso) hasta hoy; no incluye contratos de anticrético. "
        "Electricidad y agua: toda factura registrada con saldo pendiente. Solo se considera al inquilino "
        "actual de los apartamentos ocupados."
    )
    st.divider()

    # ---------------- Alertas: contratos ----------------
    filas_contrato = []
    for apt in apartamentos:
        nivel, dias = estado_contrato_alerta(apt)
        if nivel:
            filas_contrato.append({
                "Apartamento": apt["codigo"],
                "Inquilino": apt.get("inquilino_nombre") or "—",
                "Tipo": apt.get("tipo_contrato") or "—",
                "Fecha fin": apt.get("contrato_fecha_fin") or "—",
                "Estado": nivel,
                "Días": (f"{dias} días vencido" if nivel == "🔴 Vencido" and dias is not None
                         else (f"vence en {dias} días" if dias is not None else "—")),
                "_orden": 0 if nivel == "🔴 Vencido" else 1,
            })
    if filas_contrato:
        st.subheader("📄 Contratos vencidos o por vencer (30 días)")
        filas_contrato.sort(key=lambda f: f["_orden"])
        st.dataframe(pd.DataFrame(filas_contrato).drop(columns=["_orden"]),
                     use_container_width=True, hide_index=True)
        st.divider()

    col1, col2 = st.columns(2)
    with col1:
        anio_sel = st.selectbox("Año", options=list(range(date.today().year - 2, date.today().year + 2)),
                                 index=2)
    with col2:
        mes_sel = st.selectbox("Mes", options=MESES, index=date.today().month - 1)

    periodos = cargar_periodos(anio=anio_sel, mes=mes_sel)

    total_unidades = len(df_apt)
    ocupados = int((df_apt["estado"] == "Ocupado").sum())
    desocupados = total_unidades - ocupados

    total_esperado = sum(float(p["monto_esperado"]) for p in periodos)
    total_recaudado = sum(total_pagado(p) for p in periodos)
    total_deuda = total_esperado - total_recaudado

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unidades totales", total_unidades)
    c2.metric("Ocupados", ocupados)
    c3.metric("Desocupados", desocupados)
    c4.metric(f"Deuda de {mes_sel} {anio_sel}", fmt_money(total_deuda))

    c5, c6 = st.columns(2)
    c5.metric(f"Esperado en {mes_sel} {anio_sel}", fmt_money(total_esperado))
    c6.metric(f"Recaudado en {mes_sel} {anio_sel}", fmt_money(total_recaudado))

    st.divider()
    st.subheader("📈 Cobro de alquiler — últimos 12 meses")
    meses_grafica = ultimos_n_meses(12)
    valores_grafica = []
    etiquetas_grafica = []
    for (anio_g, mes_num_g) in meses_grafica:
        nombre_mes_g = MESES[mes_num_g - 1]
        periodos_g = cargar_periodos(anio=anio_g, mes=nombre_mes_g)
        total_g = sum(total_pagado(p) for p in periodos_g)
        valores_grafica.append(total_g)
        etiquetas_grafica.append(f"{nombre_mes_g[:3]} {anio_g}")
    df_grafica = pd.DataFrame({"Cobrado": valores_grafica}, index=etiquetas_grafica)
    st.line_chart(df_grafica)

    st.divider()
    st.subheader("🔝 Mayor consumo (Top 5)")
    colsel1, colsel2 = st.columns(2)
    with colsel1:
        anio_consumo = st.selectbox("Año ", options=list(range(date.today().year - 2, date.today().year + 2)),
                                     index=2, key="anio_consumo")
    with colsel2:
        mes_consumo = st.selectbox("Mes ", options=MESES, index=date.today().month - 1, key="mes_consumo")

    periodos_elec_sel = cargar_periodos_electricidad(anio=anio_consumo, mes=mes_consumo)
    periodos_agua_sel = cargar_periodos_agua(anio=anio_consumo, mes=mes_consumo)

    colE, colW = st.columns(2)
    with colE:
        st.markdown("**⚡ Electricidad (Kwh)**")
        filas_elec = []
        for p in periodos_elec_sel:
            apt_info = p.get("apartamentos") or {}
            consumo = calc_consumo.calcular_consumo(p["kwh_anterior"], p["kwh_actual"])
            filas_elec.append({
                "Apartamento": apt_info.get("codigo"),
                "Inquilino": apt_info.get("inquilino_nombre") or "—",
                "Consumo (Kwh)": consumo,
            })
        if filas_elec:
            filas_elec.sort(key=lambda f: -f["Consumo (Kwh)"])
            st.dataframe(pd.DataFrame(filas_elec[:5]), use_container_width=True, hide_index=True)
        else:
            st.info("Sin lecturas de electricidad registradas este periodo.")
    with colW:
        st.markdown("**💧 Agua (m³)**")
        filas_agua = []
        for p in periodos_agua_sel:
            apt_info = p.get("apartamentos") or {}
            consumo = calc_consumo.calcular_consumo(p["lectura_anterior"], p["lectura_actual"])
            filas_agua.append({
                "Apartamento": apt_info.get("codigo"),
                "Inquilino": apt_info.get("inquilino_nombre") or "—",
                "Consumo (m³)": consumo,
            })
        if filas_agua:
            filas_agua.sort(key=lambda f: -f["Consumo (m³)"])
            st.dataframe(pd.DataFrame(filas_agua[:5]), use_container_width=True, hide_index=True)
        else:
            st.info("Sin lecturas de agua registradas este periodo.")

    st.divider()
    st.subheader(f"Estado de pago por apartamento — {mes_sel} {anio_sel}")

    if not periodos:
        st.warning("No hay pagos registrados para este periodo todavía. Regístralos en **Pagos de Alquiler**.")
    else:
        periodos_by_apt = {p["apartamento_id"]: p for p in periodos}
        filas = []
        for _, apt in df_apt.iterrows():
            p = periodos_by_apt.get(apt["id"])
            if p:
                pagado = total_pagado(p)
                deuda = float(p["monto_esperado"]) - pagado
                estado_pago = "✅ Pagado" if deuda <= 0 else ("🟡 Parcial" if pagado else "🔴 Pendiente")
                filas.append({
                    "Apartamento": apt["codigo"],
                    "Piso": apt["piso"],
                    "Inquilino": apt.get("inquilino_nombre") or "—",
                    "Monto esperado": p["monto_esperado"],
                    "Pagado": pagado,
                    "Deuda": deuda,
                    "Estado": estado_pago,
                })
            else:
                filas.append({
                    "Apartamento": apt["codigo"],
                    "Piso": apt["piso"],
                    "Inquilino": apt.get("inquilino_nombre") or "—",
                    "Monto esperado": "—",
                    "Pagado": "—",
                    "Deuda": "—",
                    "Estado": "⚪ Sin registrar",
                })
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Resumen de todos los apartamentos")
    tabla = df_apt[["codigo", "piso", "estado", "inquilino_nombre", "monto_alquiler", "estado_contrato"]].rename(
        columns={"codigo": "Apartamento", "piso": "Piso", "estado": "Estado",
                 "inquilino_nombre": "Inquilino", "monto_alquiler": "Alquiler mensual",
                 "estado_contrato": "Contrato"}
    )
    st.dataframe(tabla, use_container_width=True, hide_index=True)


# ==================================================================
# PÁGINA: APARTAMENTOS
# ==================================================================
elif pagina == "🏠 Apartamentos":
    if not es_admin:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()
    st.title("🏠 Gestión de Apartamentos")

    tab_lista, tab_nuevo, tab_importar = st.tabs(["📋 Lista y edición", "➕ Nuevo apartamento", "📥 Importar CSV"])

    with tab_lista:
        apartamentos = cargar_apartamentos()
        if not apartamentos:
            st.info("No hay apartamentos registrados todavía.")
        else:
            codigos = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
            idx = st.selectbox("Selecciona un apartamento para ver o editar", range(len(apartamentos)),
                                format_func=lambda i: codigos[i])
            apt = apartamentos[idx]

            with st.form("editar_apartamento"):
                col1, col2 = st.columns(2)
                with col1:
                    codigo = st.text_input("Código", value=apt["codigo"])
                    piso = st.selectbox("Piso", PISOS, index=PISOS.index(apt["piso"]) if apt["piso"] in PISOS else 0)
                    estado = st.selectbox("Estado", ["Ocupado", "Desocupado"],
                                           index=0 if apt["estado"] == "Ocupado" else 1)
                    inquilino_nombre = st.text_input("Nombre del inquilino", value=apt.get("inquilino_nombre") or "")
                    celular = st.text_input("Celular", value=apt.get("celular") or "")
                    cedula_identidad = st.text_input("Cédula de identidad", value=apt.get("cedula_identidad") or "")
                    nacionalidad = st.text_input("Nacionalidad", value=apt.get("nacionalidad") or "")
                    monto_alquiler = st.number_input("Monto de alquiler mensual (Bs)", min_value=0.0,
                                                      value=float(apt.get("monto_alquiler") or 0), step=50.0)
                with col2:
                    referencia_nombre = st.text_input("Referencia - nombre", value=apt.get("referencia_nombre") or "")
                    referencia_celular = st.text_input("Referencia - celular", value=apt.get("referencia_celular") or "")
                    _raw_fecha = apt.get("fecha_ingreso")
                    try:
                        _fecha_val = date.fromisoformat(str(_raw_fecha)[:10]) if _raw_fecha else None
                    except ValueError:
                        _fecha_val = None
                    fecha_ingreso = st.date_input("Fecha de ingreso", value=_fecha_val, format="DD/MM/YYYY")
                    garantia = st.text_input("Garantía", value=apt.get("garantia") or "")
                    amoblado = st.text_area("Amoblado", value=apt.get("amoblado") or "", height=70)
                    detalle = st.text_area("Detalle (ej. incluye agua/internet)", value=apt.get("detalle") or "",
                                            height=70)
                    _opciones_dia_pago = ["(sin definir)"] + [str(d) for d in range(1, 32)]
                    _dia_pago_actual = apt.get("dia_pago")
                    _idx_dia_pago = _opciones_dia_pago.index(str(_dia_pago_actual)) if _dia_pago_actual else 0
                    dia_pago_sel = st.selectbox("Día de Pago (día fijo del mes)", _opciones_dia_pago,
                                                 index=_idx_dia_pago)

                st.divider()
                st.markdown("**📄 Datos del contrato**")
                colc1, colc2 = st.columns(2)
                with colc1:
                    _tipos_contrato = ["", "Alquiler", "Anticrético"]
                    tipo_contrato = st.selectbox(
                        "Tipo de contrato", _tipos_contrato,
                        index=_tipos_contrato.index(apt["tipo_contrato"]) if apt.get("tipo_contrato") in _tipos_contrato else 0
                    )
                with colc2:
                    _estados_contrato = ["Sin Contrato", "Vigente", "Caducado"]
                    estado_contrato = st.selectbox(
                        "Estado de contrato", _estados_contrato,
                        index=_estados_contrato.index(apt["estado_contrato"]) if apt.get("estado_contrato") in _estados_contrato else 0
                    )
                colc4, colc5 = st.columns(2)
                with colc4:
                    _raw_ci = apt.get("contrato_fecha_inicio")
                    try:
                        _ci_val = date.fromisoformat(str(_raw_ci)[:10]) if _raw_ci else None
                    except ValueError:
                        _ci_val = None
                    contrato_fecha_inicio = st.date_input("Fecha inicio", value=_ci_val, format="DD/MM/YYYY",
                                                           key="ci_edit")
                with colc5:
                    _raw_cf = apt.get("contrato_fecha_fin")
                    try:
                        _cf_val = date.fromisoformat(str(_raw_cf)[:10]) if _raw_cf else None
                    except ValueError:
                        _cf_val = None
                    contrato_fecha_fin = st.date_input("Fecha fin", value=_cf_val, format="DD/MM/YYYY",
                                                        key="cf_edit")
                contrato_observaciones = st.text_area("Observaciones del contrato",
                                                       value=apt.get("contrato_observaciones") or "")

                col_a, col_b = st.columns([1, 1])
                guardar = col_a.form_submit_button("💾 Guardar cambios", use_container_width=True)
                eliminar = col_b.form_submit_button("🗑️ Eliminar apartamento", use_container_width=True)

                if guardar:
                    payload = {
                        "codigo": codigo.strip().upper(),
                        "piso": piso,
                        "estado": estado,
                        "inquilino_nombre": inquilino_nombre or None,
                        "celular": celular or None,
                        "cedula_identidad": cedula_identidad or None,
                        "nacionalidad": nacionalidad or None,
                        "referencia_nombre": referencia_nombre or None,
                        "referencia_celular": referencia_celular or None,
                        "fecha_ingreso": str(fecha_ingreso) if fecha_ingreso else None,
                        "garantia": garantia or None,
                        "amoblado": amoblado or None,
                        "detalle": detalle or None,
                        "monto_alquiler": monto_alquiler,
                        "dia_pago": int(dia_pago_sel) if dia_pago_sel != "(sin definir)" else None,
                        "tipo_contrato": tipo_contrato or None,
                        "estado_contrato": estado_contrato,
                        "contrato_fecha_inicio": str(contrato_fecha_inicio) if contrato_fecha_inicio else None,
                        "contrato_fecha_fin": str(contrato_fecha_fin) if contrato_fecha_fin else None,
                        "contrato_observaciones": contrato_observaciones or None,
                    }
                    try:
                        db.actualizar_apartamento(apt["id"], payload)
                        limpiar_cache()
                        st.success("Apartamento actualizado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al actualizar: {e}")

                if eliminar:
                    try:
                        db.eliminar_apartamento(apt["id"])
                        limpiar_cache()
                        st.success("Apartamento eliminado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")

    with tab_nuevo:
        with st.form("nuevo_apartamento", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código (ej. PB-01)")
                piso = st.selectbox("Piso", PISOS)
                estado = st.selectbox("Estado", ["Ocupado", "Desocupado"])
                inquilino_nombre = st.text_input("Nombre del inquilino")
                celular = st.text_input("Celular")
                monto_alquiler = st.number_input("Monto de alquiler mensual (Bs)", min_value=0.0, step=50.0)
            with col2:
                cedula_identidad = st.text_input("Cédula de identidad")
                nacionalidad = st.text_input("Nacionalidad")
                fecha_ingreso = st.date_input("Fecha de ingreso", value=None, format="DD/MM/YYYY")
                garantia = st.text_input("Garantía")
                detalle = st.text_input("Detalle (ej. incluye agua/internet)")
                dia_pago_sel = st.selectbox("Día de Pago (día fijo del mes)",
                                             ["(sin definir)"] + [str(d) for d in range(1, 32)])

            st.divider()
            st.markdown("**📄 Datos del contrato**")
            colc1, colc2 = st.columns(2)
            with colc1:
                tipo_contrato = st.selectbox("Tipo de contrato", ["", "Alquiler", "Anticrético"], key="tipo_nuevo")
            with colc2:
                estado_contrato = st.selectbox("Estado de contrato", ["Sin Contrato", "Vigente", "Caducado"],
                                                key="estado_c_nuevo")
            colc3, colc4 = st.columns(2)
            with colc3:
                contrato_fecha_inicio = st.date_input("Fecha inicio", value=None, format="DD/MM/YYYY", key="ci_nuevo")
            with colc4:
                contrato_fecha_fin = st.date_input("Fecha fin", value=None, format="DD/MM/YYYY", key="cf_nuevo")
            contrato_observaciones = st.text_area("Observaciones del contrato", key="obs_c_nuevo")

            crear = st.form_submit_button("➕ Crear apartamento")
            if crear:
                if not codigo:
                    st.error("El código es obligatorio.")
                else:
                    payload = {
                        "codigo": codigo.strip().upper(),
                        "piso": piso,
                        "estado": estado,
                        "inquilino_nombre": inquilino_nombre or None,
                        "celular": celular or None,
                        "cedula_identidad": cedula_identidad or None,
                        "nacionalidad": nacionalidad or None,
                        "fecha_ingreso": str(fecha_ingreso) if fecha_ingreso else None,
                        "garantia": garantia or None,
                        "detalle": detalle or None,
                        "monto_alquiler": monto_alquiler,
                        "dia_pago": int(dia_pago_sel) if dia_pago_sel != "(sin definir)" else None,
                        "tipo_contrato": tipo_contrato or None,
                        "estado_contrato": estado_contrato,
                        "contrato_fecha_inicio": str(contrato_fecha_inicio) if contrato_fecha_inicio else None,
                        "contrato_fecha_fin": str(contrato_fecha_fin) if contrato_fecha_fin else None,
                        "contrato_observaciones": contrato_observaciones or None,
                    }
                    try:
                        db.crear_apartamento(payload)
                        limpiar_cache()
                        st.success(f"Apartamento {codigo} creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear (¿código repetido?): {e}")

    with tab_importar:
        st.write(
            "Sube un archivo CSV con columnas: `codigo, piso, estado, inquilino_nombre, celular, "
            "cedula_identidad, nacionalidad, fecha_ingreso, garantia, amoblado, detalle, monto_alquiler`. "
            "Se recomienda usar la plantilla generada a partir de tu Excel y revisar/corregir los datos antes de importar."
        )
        archivo = st.file_uploader("Archivo CSV", type=["csv"])
        if archivo is not None:
            df_csv = pd.read_csv(archivo)
            st.dataframe(df_csv, use_container_width=True)
            if st.button("📥 Importar estos apartamentos"):
                errores = []
                creados = 0
                for _, row in df_csv.iterrows():
                    payload = {k: (None if pd.isna(v) or v == "" else v) for k, v in row.to_dict().items()}
                    if "codigo" not in payload or not payload["codigo"]:
                        continue
                    try:
                        db.crear_apartamento(payload)
                        creados += 1
                    except Exception as e:
                        errores.append(f'{payload.get("codigo")}: {e}')
                limpiar_cache()
                st.success(f"{creados} apartamentos importados.")
                if errores:
                    st.warning("Algunos registros no se pudieron importar (puede que ya existan):")
                    for e in errores:
                        st.text(e)


# ==================================================================
# PÁGINA: PAGOS DE ALQUILER
# ==================================================================
elif pagina == "💵 Pagos de Alquiler":
    st.title("💵 Pagos de Alquiler")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("Primero registra apartamentos en la sección **Apartamentos**.")
        st.stop()

    tab_registrar, tab_historial = st.tabs(["➕ Registrar abono", "📜 Historial"])

    with tab_registrar:
        codigos = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
        idx = st.selectbox("Apartamento", range(len(apartamentos)), format_func=lambda i: codigos[i])
        apt = apartamentos[idx]

        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", MESES, index=date.today().month - 1)
        with col2:
            anio = st.number_input("Año", min_value=2000, max_value=2100, value=date.today().year, step=1)

        # obtiene (o prepara) el periodo de este apartamento/mes/año, con sus abonos ya hechos
        periodo = db.obtener_periodo(apt["id"], mes, int(anio))
        monto_esperado_actual = float(periodo["monto_esperado"]) if periodo else float(apt.get("monto_alquiler") or 0)
        abonos = periodo.get("pagos", []) if periodo else []
        pagado_hasta_ahora = sum(float(p["monto"]) for p in abonos)
        deuda_actual = monto_esperado_actual - pagado_hasta_ahora

        st.markdown(f"**Monto esperado del mes:** {fmt_money(monto_esperado_actual)}  |  "
                    f"**Pagado hasta ahora:** {fmt_money(pagado_hasta_ahora)}  |  "
                    f"**Deuda actual:** {fmt_money(deuda_actual)}")

        if es_admin:
            with st.expander("✏️ Cambiar el monto esperado de este mes (si es distinto al alquiler habitual)"):
                with st.form("form_monto_esperado"):
                    nuevo_monto_esperado = st.number_input(
                        "Monto esperado (Bs)", min_value=0.0, step=50.0, value=monto_esperado_actual
                    )
                    guardar_monto = st.form_submit_button("Guardar monto esperado")
                    if guardar_monto:
                        try:
                            if periodo:
                                db.actualizar_periodo(periodo["id"], {"monto_esperado": nuevo_monto_esperado})
                            else:
                                db.obtener_o_crear_periodo(apt["id"], mes, int(anio), nuevo_monto_esperado)
                            limpiar_cache()
                            st.success("Monto esperado actualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

        st.divider()
        st.subheader("➕ Registrar un nuevo abono")
        with st.form("form_pago", clear_on_submit=True):
            monto_pago = st.number_input("Monto abonado (Bs)", min_value=0.0, step=50.0)
            fecha_pago = st.date_input("Fecha del abono", value=date.today(), format="DD/MM/YYYY")
            metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"])
            observacion = st.text_input("Observación (opcional)")

            guardar = st.form_submit_button("💾 Registrar abono")
            if guardar:
                if monto_pago <= 0:
                    st.error("El monto abonado debe ser mayor a 0.")
                else:
                    try:
                        periodo_actual = db.obtener_o_crear_periodo(apt["id"], mes, int(anio), monto_esperado_actual)
                        db.crear_pago({
                            "periodo_id": periodo_actual["id"],
                            "fecha": str(fecha_pago),
                            "monto": monto_pago,
                            "metodo_pago": metodo_pago,
                            "observacion": observacion or None,
                        })
                        limpiar_cache()
                        st.success("Abono registrado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

        if abonos:
            st.divider()
            st.subheader(f"Abonos ya registrados — {mes} {int(anio)}")
            for p in sorted(abonos, key=lambda x: x["fecha"]):
                with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                    mostrar_botones_recibo(p, periodo, apt, pagado_hasta_ahora, key_sufijo=f'alq_{p["id"]}')
                    st.divider()
                    with st.form(f'form_editar_pago_{p["id"]}'):
                        colf, colm = st.columns(2)
                        with colf:
                            _f = date.fromisoformat(str(p["fecha"])[:10])
                            edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY",
                                                        key=f'alq_fecha_{p["id"]}')
                        with colm:
                            edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                          value=float(p["monto"]), key=f'alq_monto_{p["id"]}')
                        edit_metodo = st.selectbox(
                            "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                            index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                            if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0,
                            key=f'alq_metodo_{p["id"]}'
                        )
                        edit_obs = st.text_input("Observación", value=p.get("observacion") or "",
                                                  key=f'alq_obs_{p["id"]}')

                        if es_admin:
                            colg, cold = st.columns(2)
                            guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                            eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)
                        else:
                            guardar_edit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                            eliminar_edit = False

                        if guardar_edit:
                            try:
                                db.actualizar_pago(p["id"], {
                                    "fecha": str(edit_fecha),
                                    "monto": edit_monto,
                                    "metodo_pago": edit_metodo,
                                    "observacion": edit_obs or None,
                                })
                                limpiar_cache()
                                st.success("Abono actualizado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar: {e}")

                        if eliminar_edit:
                            try:
                                db.eliminar_pago(p["id"])
                                limpiar_cache()
                                st.success("Abono eliminado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al eliminar: {e}")

    with tab_historial:
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_apt = st.selectbox(
                "Filtrar por apartamento", ["Todos"] + [a["codigo"] for a in apartamentos]
            )
        with col2:
            filtro_anio = st.selectbox("Filtrar por año",
                                        ["Todos"] + list(range(date.today().year - 2, date.today().year + 2)))
        with col3:
            filtro_mes = st.selectbox("Filtrar por mes", ["Todos"] + MESES)

        apt_id = None
        if filtro_apt != "Todos":
            apt_id = next(a["id"] for a in apartamentos if a["codigo"] == filtro_apt)

        periodos = db.listar_periodos(
            apartamento_id=apt_id,
            anio=None if filtro_anio == "Todos" else filtro_anio,
            mes=None if filtro_mes == "Todos" else filtro_mes,
        )

        if not periodos:
            st.info("No hay periodos que coincidan con el filtro.")
        else:
            filas = []
            for p in periodos:
                apt_info = p.get("apartamentos") or {}
                pagado = total_pagado(p)
                deuda = float(p["monto_esperado"]) - pagado
                n_abonos = len(p.get("pagos") or [])
                filas.append({
                    "Apartamento": apt_info.get("codigo"),
                    "Inquilino": apt_info.get("inquilino_nombre"),
                    "Mes": p["mes"],
                    "Año": p["anio"],
                    "Esperado": p["monto_esperado"],
                    "Pagado": pagado,
                    "Deuda": deuda,
                    "N° de abonos": n_abonos,
                })
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

            total_esperado = sum(f["Esperado"] for f in filas)
            total_recaudado = sum(f["Pagado"] for f in filas)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total esperado", fmt_money(total_esperado))
            c2.metric("Total pagado", fmt_money(total_recaudado))
            c3.metric("Total deuda", fmt_money(total_esperado - total_recaudado))

            with st.expander("🔍 Ver y editar los abonos de un periodo específico"):
                opciones = [f'{f["Apartamento"]} — {f["Mes"]} {f["Año"]}' for f in filas]
                sel = st.selectbox("Periodo", range(len(opciones)), format_func=lambda i: opciones[i])
                detalle_periodo = periodos[sel]
                detalle_abonos = detalle_periodo.get("pagos") or []
                if not detalle_abonos:
                    st.write("Sin abonos registrados.")
                else:
                    for p in sorted(detalle_abonos, key=lambda x: x["fecha"]):
                        with st.expander(
                            f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'
                        ):
                            mostrar_botones_recibo(
                                p, detalle_periodo, detalle_periodo.get("apartamentos"),
                                total_pagado(detalle_periodo), key_sufijo=f'alq_hist_{p["id"]}'
                            )
                            st.divider()
                            with st.form(f'form_editar_pago_hist_{p["id"]}'):
                                colf, colm = st.columns(2)
                                with colf:
                                    _f = date.fromisoformat(str(p["fecha"])[:10])
                                    edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY",
                                                                key=f'alq_hist_fecha_{p["id"]}')
                                with colm:
                                    edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                                  value=float(p["monto"]),
                                                                  key=f'alq_hist_monto_{p["id"]}')
                                edit_metodo = st.selectbox(
                                    "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                    index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                    if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0,
                                    key=f'alq_hist_metodo_{p["id"]}'
                                )
                                edit_obs = st.text_input("Observación", value=p.get("observacion") or "",
                                                          key=f'alq_hist_obs_{p["id"]}')

                                if es_admin:
                                    colg, cold = st.columns(2)
                                    guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                    eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)
                                else:
                                    guardar_edit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                    eliminar_edit = False

                                if guardar_edit:
                                    try:
                                        db.actualizar_pago(p["id"], {
                                            "fecha": str(edit_fecha),
                                            "monto": edit_monto,
                                            "metodo_pago": edit_metodo,
                                            "observacion": edit_obs or None,
                                        })
                                        limpiar_cache()
                                        st.success("Abono actualizado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al actualizar: {e}")

                                if eliminar_edit:
                                    try:
                                        db.eliminar_pago(p["id"])
                                        limpiar_cache()
                                        st.success("Abono eliminado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: ELECTRICIDAD
# ==================================================================
elif pagina == "⚡ Electricidad":
    st.title("⚡ Control de Electricidad")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("Primero registra apartamentos en la sección **Apartamentos**.")
        st.stop()

    tarifa_actual = db.obtener_tarifa_kwh()
    if es_admin:
        with st.expander("⚙️ Tarifa por Kwh vigente"):
            with st.form("form_tarifa"):
                nueva_tarifa = st.number_input(
                    "Tarifa por Kwh (Bs)", min_value=0.0, step=0.01, format="%.4f", value=tarifa_actual
                )
                if st.form_submit_button("Guardar tarifa"):
                    try:
                        db.guardar_tarifa_kwh(nueva_tarifa)
                        st.success("Tarifa actualizada. Se usará como valor por defecto para nuevas lecturas.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar lectura y abono", "📜 Historial"])

    with tab_registrar:
        codigos = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
        idx = st.selectbox("Apartamento", range(len(apartamentos)), format_func=lambda i: codigos[i], key="elec_apt")
        apt = apartamentos[idx]

        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", MESES, index=date.today().month - 1, key="elec_mes")
        with col2:
            anio = st.number_input("Año", min_value=2000, max_value=2100, value=date.today().year, step=1,
                                    key="elec_anio")

        periodo = db.obtener_periodo_electricidad(apt["id"], mes, int(anio))

        if periodo:
            kwh_anterior_default = float(periodo["kwh_anterior"])
            kwh_actual_default = float(periodo["kwh_actual"])
            tarifa_default = float(periodo["tarifa_kwh"])
        else:
            anterior_periodo = db.ultimo_periodo_electricidad(apt["id"])
            kwh_anterior_default = float(anterior_periodo["kwh_actual"]) if anterior_periodo else 0.0
            kwh_actual_default = kwh_anterior_default
            tarifa_default = tarifa_actual

        st.subheader("📏 Lectura del medidor")
        with st.form("form_lectura"):
            colk1, colk2, colk3 = st.columns(3)
            with colk1:
                kwh_anterior = st.number_input("Kwh anterior", min_value=0.0, step=1.0, value=kwh_anterior_default)
            with colk2:
                kwh_actual = st.number_input("Kwh actual", min_value=0.0, step=1.0, value=kwh_actual_default)
            with colk3:
                tarifa_kwh = st.number_input("Tarifa por Kwh (Bs)", min_value=0.0, step=0.01, format="%.4f",
                                              value=tarifa_default)

            consumo = calc_consumo.calcular_consumo(kwh_anterior, kwh_actual)   # número entero (redondeo normal)
            monto_calculado = calc_consumo.calcular_monto(consumo, tarifa_kwh)
            st.caption(f"Consumo: {consumo} Kwh  ×  Bs {tarifa_kwh:.4f}  =  {detalle_monto_servicio(consumo, tarifa_kwh)}")
            nota_redondeo = calc_consumo.nota_redondeo(kwh_anterior, kwh_actual)
            if nota_redondeo:
                st.caption(f"ℹ️ El consumo se redondea a número entero: {nota_redondeo}.")

            guardar_lectura = st.form_submit_button("💾 Guardar lectura")
            if guardar_lectura:
                payload = {
                    "kwh_anterior": kwh_anterior,
                    "kwh_actual": kwh_actual,
                    "tarifa_kwh": tarifa_kwh,
                    "monto_esperado": monto_calculado,
                }
                try:
                    if periodo:
                        db.actualizar_periodo_electricidad(periodo["id"], payload)
                    else:
                        payload.update({"apartamento_id": apt["id"], "mes": mes, "anio": int(anio)})
                        db.crear_periodo_electricidad(payload)
                    limpiar_cache()
                    st.success("Lectura guardada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

        if periodo:
            abonos = periodo.get("pagos_electricidad", []) or []
            pagado_hasta_ahora = sum(float(p["monto"]) for p in abonos)
            deuda_actual = float(periodo["monto_esperado"]) - pagado_hasta_ahora

            st.markdown(f"**Monto esperado del mes:** {fmt_money(periodo['monto_esperado'])}  |  "
                        f"**Pagado hasta ahora:** {fmt_money(pagado_hasta_ahora)}  |  "
                        f"**Deuda actual:** {fmt_money(deuda_actual)}")

            st.divider()
            st.subheader("➕ Registrar un nuevo abono")
            with st.form("form_pago_elec", clear_on_submit=True):
                monto_pago = st.number_input("Monto abonado (Bs)", min_value=0.0, step=10.0)
                fecha_pago = st.date_input("Fecha del abono", value=date.today(), format="DD/MM/YYYY")
                metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                            key="metodo_elec")
                observacion = st.text_input("Observación (opcional)", key="obs_elec")

                guardar = st.form_submit_button("💾 Registrar abono")
                if guardar:
                    if monto_pago <= 0:
                        st.error("El monto abonado debe ser mayor a 0.")
                    else:
                        try:
                            db.crear_pago_electricidad({
                                "periodo_id": periodo["id"],
                                "fecha": str(fecha_pago),
                                "monto": monto_pago,
                                "metodo_pago": metodo_pago,
                                "observacion": observacion or None,
                            })
                            limpiar_cache()
                            st.success("Abono registrado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

            if abonos:
                st.divider()
                st.subheader(f"Abonos ya registrados — {mes} {int(anio)}")
                for p in sorted(abonos, key=lambda x: x["fecha"]):
                    with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                        with st.form(f'form_editar_pago_elec_{p["id"]}'):
                            colf, colm = st.columns(2)
                            with colf:
                                _f = date.fromisoformat(str(p["fecha"])[:10])
                                edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY",
                                                            key=f'elec_fecha_{p["id"]}')
                            with colm:
                                edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                              value=float(p["monto"]), key=f'elec_monto_{p["id"]}')
                            edit_metodo = st.selectbox(
                                "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0,
                                key=f'elec_metodo_{p["id"]}'
                            )
                            edit_obs = st.text_input("Observación", value=p.get("observacion") or "",
                                                      key=f'elec_obs_{p["id"]}')

                            if es_admin:
                                colg, cold = st.columns(2)
                                guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)
                            else:
                                guardar_edit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                eliminar_edit = False

                            if guardar_edit:
                                try:
                                    db.actualizar_pago_electricidad(p["id"], {
                                        "fecha": str(edit_fecha),
                                        "monto": edit_monto,
                                        "metodo_pago": edit_metodo,
                                        "observacion": edit_obs or None,
                                    })
                                    limpiar_cache()
                                    st.success("Abono actualizado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al actualizar: {e}")

                            if eliminar_edit:
                                try:
                                    db.eliminar_pago_electricidad(p["id"])
                                    limpiar_cache()
                                    st.success("Abono eliminado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al eliminar: {e}")
        else:
            st.info("Guarda primero la lectura del medidor para poder registrar abonos de este mes.")

    with tab_historial:
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_apt = st.selectbox(
                "Filtrar por apartamento", ["Todos"] + [a["codigo"] for a in apartamentos], key="elec_hist_apt"
            )
        with col2:
            filtro_anio = st.selectbox("Filtrar por año",
                                        ["Todos"] + list(range(date.today().year - 2, date.today().year + 2)),
                                        key="elec_hist_anio")
        with col3:
            filtro_mes = st.selectbox("Filtrar por mes", ["Todos"] + MESES, key="elec_hist_mes")

        apt_id = None
        if filtro_apt != "Todos":
            apt_id = next(a["id"] for a in apartamentos if a["codigo"] == filtro_apt)

        periodos_elec = db.listar_periodos_electricidad(
            apartamento_id=apt_id,
            anio=None if filtro_anio == "Todos" else filtro_anio,
            mes=None if filtro_mes == "Todos" else filtro_mes,
        )

        if not periodos_elec:
            st.info("No hay periodos que coincidan con el filtro.")
        else:
            filas = []
            for p in periodos_elec:
                apt_info = p.get("apartamentos") or {}
                pagado = sum(float(a["monto"]) for a in (p.get("pagos_electricidad") or []))
                deuda = float(p["monto_esperado"]) - pagado
                filas.append({
                    "Apartamento": apt_info.get("codigo"),
                    "Inquilino": apt_info.get("inquilino_nombre"),
                    "Mes": p["mes"],
                    "Año": p["anio"],
                    "Kwh anterior": p["kwh_anterior"],
                    "Kwh actual": p["kwh_actual"],
                    "Consumo": calc_consumo.calcular_consumo(p["kwh_anterior"], p["kwh_actual"]),
                    "Esperado": p["monto_esperado"],
                    "Pagado": pagado,
                    "Deuda": deuda,
                })
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

            total_esperado = sum(f["Esperado"] for f in filas)
            total_recaudado = sum(f["Pagado"] for f in filas)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total esperado", fmt_money(total_esperado))
            c2.metric("Total pagado", fmt_money(total_recaudado))
            c3.metric("Total deuda", fmt_money(total_esperado - total_recaudado))

            with st.expander("🔍 Ver y editar los abonos de un periodo específico"):
                opciones = [f'{f["Apartamento"]} — {f["Mes"]} {f["Año"]}' for f in filas]
                sel = st.selectbox("Periodo", range(len(opciones)), format_func=lambda i: opciones[i],
                                    key="sel_hist_elec")
                detalle_periodo = periodos_elec[sel]
                detalle_abonos = detalle_periodo.get("pagos_electricidad") or []
                if not detalle_abonos:
                    st.write("Sin abonos registrados.")
                else:
                    for p in sorted(detalle_abonos, key=lambda x: x["fecha"]):
                        with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                            with st.form(f'form_editar_pago_elec_hist_{p["id"]}'):
                                colf, colm = st.columns(2)
                                with colf:
                                    _f = date.fromisoformat(str(p["fecha"])[:10])
                                    edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY",
                                                                key=f'elec_hist_fecha_{p["id"]}')
                                with colm:
                                    edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                                  value=float(p["monto"]),
                                                                  key=f'elec_hist_monto_{p["id"]}')
                                edit_metodo = st.selectbox(
                                    "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                    index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                    if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0,
                                    key=f'elec_hist_metodo_{p["id"]}'
                                )
                                edit_obs = st.text_input("Observación", value=p.get("observacion") or "",
                                                          key=f'elec_hist_obs_{p["id"]}')

                                if es_admin:
                                    colg, cold = st.columns(2)
                                    guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                    eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)
                                else:
                                    guardar_edit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                    eliminar_edit = False

                                if guardar_edit:
                                    try:
                                        db.actualizar_pago_electricidad(p["id"], {
                                            "fecha": str(edit_fecha),
                                            "monto": edit_monto,
                                            "metodo_pago": edit_metodo,
                                            "observacion": edit_obs or None,
                                        })
                                        limpiar_cache()
                                        st.success("Abono actualizado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al actualizar: {e}")

                                if eliminar_edit:
                                    try:
                                        db.eliminar_pago_electricidad(p["id"])
                                        limpiar_cache()
                                        st.success("Abono eliminado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al eliminar: {e}")
# ==================================================================
elif pagina == "💧 Agua":
    st.title("💧 Control de Agua")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("Primero registra apartamentos en la sección **Apartamentos**.")
        st.stop()

    tarifa_actual = db.obtener_tarifa_agua()
    if es_admin:
        with st.expander("⚙️ Tarifa por m³ vigente"):
            with st.form("form_tarifa_agua"):
                nueva_tarifa = st.number_input(
                    "Tarifa por m³ (Bs)", min_value=0.0, step=0.01, format="%.4f", value=tarifa_actual
                )
                if st.form_submit_button("Guardar tarifa"):
                    try:
                        db.guardar_tarifa_agua(nueva_tarifa)
                        st.success("Tarifa actualizada. Se usará como valor por defecto para nuevas lecturas.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar lectura y abono", "📜 Historial"])

    with tab_registrar:
        codigos = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
        idx = st.selectbox("Apartamento", range(len(apartamentos)), format_func=lambda i: codigos[i], key="agua_apt")
        apt = apartamentos[idx]

        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", MESES, index=date.today().month - 1, key="agua_mes")
        with col2:
            anio = st.number_input("Año", min_value=2000, max_value=2100, value=date.today().year, step=1,
                                    key="agua_anio")

        periodo = db.obtener_periodo_agua(apt["id"], mes, int(anio))

        if periodo:
            lectura_anterior_default = float(periodo["lectura_anterior"])
            lectura_actual_default = float(periodo["lectura_actual"])
            tarifa_default = float(periodo["tarifa_agua"])
        else:
            anterior_periodo = db.ultimo_periodo_agua(apt["id"])
            lectura_anterior_default = float(anterior_periodo["lectura_actual"]) if anterior_periodo else 0.0
            lectura_actual_default = lectura_anterior_default
            tarifa_default = tarifa_actual

        st.subheader("📏 Lectura del medidor")
        with st.form("form_lectura_agua"):
            colk1, colk2, colk3 = st.columns(3)
            with colk1:
                lectura_anterior = st.number_input("Lectura anterior (m³)", min_value=0.0, step=1.0,
                                                     value=lectura_anterior_default)
            with colk2:
                lectura_actual = st.number_input("Lectura actual (m³)", min_value=0.0, step=1.0,
                                                   value=lectura_actual_default)
            with colk3:
                tarifa_agua = st.number_input("Tarifa por m³ (Bs)", min_value=0.0, step=0.01, format="%.4f",
                                               value=tarifa_default)

            consumo = calc_consumo.calcular_consumo(lectura_anterior, lectura_actual)   # número entero (redondeo normal)
            monto_calculado = calc_consumo.calcular_monto(consumo, tarifa_agua)
            st.caption(f"Consumo: {consumo} m³  ×  Bs {tarifa_agua:.4f}  =  {detalle_monto_servicio(consumo, tarifa_agua)}")
            nota_redondeo = calc_consumo.nota_redondeo(lectura_anterior, lectura_actual)
            if nota_redondeo:
                st.caption(f"ℹ️ El consumo se redondea a número entero: {nota_redondeo}.")

            guardar_lectura = st.form_submit_button("💾 Guardar lectura")
            if guardar_lectura:
                payload = {
                    "lectura_anterior": lectura_anterior,
                    "lectura_actual": lectura_actual,
                    "tarifa_agua": tarifa_agua,
                    "monto_esperado": monto_calculado,
                }
                try:
                    if periodo:
                        db.actualizar_periodo_agua(periodo["id"], payload)
                    else:
                        payload.update({"apartamento_id": apt["id"], "mes": mes, "anio": int(anio)})
                        db.crear_periodo_agua(payload)
                    limpiar_cache()
                    st.success("Lectura guardada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

        if periodo:
            abonos = periodo.get("pagos_agua", []) or []
            pagado_hasta_ahora = sum(float(p["monto"]) for p in abonos)
            deuda_actual = float(periodo["monto_esperado"]) - pagado_hasta_ahora

            st.markdown(f"**Monto esperado del mes:** {fmt_money(periodo['monto_esperado'])}  |  "
                        f"**Pagado hasta ahora:** {fmt_money(pagado_hasta_ahora)}  |  "
                        f"**Deuda actual:** {fmt_money(deuda_actual)}")

            st.divider()
            st.subheader("➕ Registrar un nuevo abono")
            with st.form("form_pago_agua", clear_on_submit=True):
                monto_pago = st.number_input("Monto abonado (Bs)", min_value=0.0, step=10.0)
                fecha_pago = st.date_input("Fecha del abono", value=date.today(), format="DD/MM/YYYY")
                metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                            key="metodo_agua")
                observacion = st.text_input("Observación (opcional)", key="obs_agua")

                guardar = st.form_submit_button("💾 Registrar abono")
                if guardar:
                    if monto_pago <= 0:
                        st.error("El monto abonado debe ser mayor a 0.")
                    else:
                        try:
                            db.crear_pago_agua({
                                "periodo_id": periodo["id"],
                                "fecha": str(fecha_pago),
                                "monto": monto_pago,
                                "metodo_pago": metodo_pago,
                                "observacion": observacion or None,
                            })
                            limpiar_cache()
                            st.success("Abono registrado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

            if abonos:
                st.divider()
                st.subheader(f"Abonos ya registrados — {mes} {int(anio)}")
                for p in sorted(abonos, key=lambda x: x["fecha"]):
                    with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                        with st.form(f'form_editar_pago_agua_{p["id"]}'):
                            colf, colm = st.columns(2)
                            with colf:
                                _f = date.fromisoformat(str(p["fecha"])[:10])
                                edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY",
                                                            key=f'agua_fecha_{p["id"]}')
                            with colm:
                                edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                              value=float(p["monto"]), key=f'agua_monto_{p["id"]}')
                            edit_metodo = st.selectbox(
                                "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0,
                                key=f'agua_metodo_{p["id"]}'
                            )
                            edit_obs = st.text_input("Observación", value=p.get("observacion") or "",
                                                      key=f'agua_obs_{p["id"]}')

                            if es_admin:
                                colg, cold = st.columns(2)
                                guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)
                            else:
                                guardar_edit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                eliminar_edit = False

                            if guardar_edit:
                                try:
                                    db.actualizar_pago_agua(p["id"], {
                                        "fecha": str(edit_fecha),
                                        "monto": edit_monto,
                                        "metodo_pago": edit_metodo,
                                        "observacion": edit_obs or None,
                                    })
                                    limpiar_cache()
                                    st.success("Abono actualizado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al actualizar: {e}")

                            if eliminar_edit:
                                try:
                                    db.eliminar_pago_agua(p["id"])
                                    limpiar_cache()
                                    st.success("Abono eliminado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al eliminar: {e}")
        else:
            st.info("Guarda primero la lectura del medidor para poder registrar abonos de este mes.")

    with tab_historial:
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_apt = st.selectbox(
                "Filtrar por apartamento", ["Todos"] + [a["codigo"] for a in apartamentos], key="agua_hist_apt"
            )
        with col2:
            filtro_anio = st.selectbox("Filtrar por año",
                                        ["Todos"] + list(range(date.today().year - 2, date.today().year + 2)),
                                        key="agua_hist_anio")
        with col3:
            filtro_mes = st.selectbox("Filtrar por mes", ["Todos"] + MESES, key="agua_hist_mes")

        apt_id = None
        if filtro_apt != "Todos":
            apt_id = next(a["id"] for a in apartamentos if a["codigo"] == filtro_apt)

        periodos_agua = db.listar_periodos_agua(
            apartamento_id=apt_id,
            anio=None if filtro_anio == "Todos" else filtro_anio,
            mes=None if filtro_mes == "Todos" else filtro_mes,
        )

        if not periodos_agua:
            st.info("No hay periodos que coincidan con el filtro.")
        else:
            filas = []
            for p in periodos_agua:
                apt_info = p.get("apartamentos") or {}
                pagado = sum(float(a["monto"]) for a in (p.get("pagos_agua") or []))
                deuda = float(p["monto_esperado"]) - pagado
                filas.append({
                    "Apartamento": apt_info.get("codigo"),
                    "Inquilino": apt_info.get("inquilino_nombre"),
                    "Mes": p["mes"],
                    "Año": p["anio"],
                    "Lectura anterior": p["lectura_anterior"],
                    "Lectura actual": p["lectura_actual"],
                    "Consumo": calc_consumo.calcular_consumo(p["lectura_anterior"], p["lectura_actual"]),
                    "Esperado": p["monto_esperado"],
                    "Pagado": pagado,
                    "Deuda": deuda,
                })
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

            total_esperado = sum(f["Esperado"] for f in filas)
            total_recaudado = sum(f["Pagado"] for f in filas)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total esperado", fmt_money(total_esperado))
            c2.metric("Total pagado", fmt_money(total_recaudado))
            c3.metric("Total deuda", fmt_money(total_esperado - total_recaudado))

            with st.expander("🔍 Ver y editar los abonos de un periodo específico"):
                opciones = [f'{f["Apartamento"]} — {f["Mes"]} {f["Año"]}' for f in filas]
                sel = st.selectbox("Periodo", range(len(opciones)), format_func=lambda i: opciones[i],
                                    key="sel_hist_agua")
                detalle_periodo = periodos_agua[sel]
                detalle_abonos = detalle_periodo.get("pagos_agua") or []
                if not detalle_abonos:
                    st.write("Sin abonos registrados.")
                else:
                    for p in sorted(detalle_abonos, key=lambda x: x["fecha"]):
                        with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                            with st.form(f'form_editar_pago_agua_hist_{p["id"]}'):
                                colf, colm = st.columns(2)
                                with colf:
                                    _f = date.fromisoformat(str(p["fecha"])[:10])
                                    edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY",
                                                                key=f'agua_hist_fecha_{p["id"]}')
                                with colm:
                                    edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                                  value=float(p["monto"]),
                                                                  key=f'agua_hist_monto_{p["id"]}')
                                edit_metodo = st.selectbox(
                                    "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                    index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                    if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0,
                                    key=f'agua_hist_metodo_{p["id"]}'
                                )
                                edit_obs = st.text_input("Observación", value=p.get("observacion") or "",
                                                          key=f'agua_hist_obs_{p["id"]}')

                                if es_admin:
                                    colg, cold = st.columns(2)
                                    guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                    eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)
                                else:
                                    guardar_edit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                    eliminar_edit = False

                                if guardar_edit:
                                    try:
                                        db.actualizar_pago_agua(p["id"], {
                                            "fecha": str(edit_fecha),
                                            "monto": edit_monto,
                                            "metodo_pago": edit_metodo,
                                            "observacion": edit_obs or None,
                                        })
                                        limpiar_cache()
                                        st.success("Abono actualizado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al actualizar: {e}")

                                if eliminar_edit:
                                    try:
                                        db.eliminar_pago_agua(p["id"])
                                        limpiar_cache()
                                        st.success("Abono eliminado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: PENDIENTES (tareas de colaboradores)
# ==================================================================
elif pagina == "📑 Estado de cuenta":
    st.title("📑 Estado de cuenta")
    st.subheader("Estado de cuenta por apartamento")
    st.caption(
        "Reporte para entregar al inquilino con sus pagos realizados y su deuda real de alquiler y "
        "electricidad, calculada a la fecha de hoy. Aplica a apartamentos ocupados con contrato de alquiler."
    )

    hoy_rep = recibo.hoy_bolivia()
    nombre_emisor = usuario_actual.get("nombre") or usuario_actual.get("username")
    apartamentos = cargar_apartamentos()
    alq_por_apt, elec_por_apt = {}, {}
    for p in cargar_periodos_abiertos("alquiler"):
        alq_por_apt.setdefault(p["apartamento_id"], []).append(p)
    for p in cargar_periodos_abiertos("electricidad"):
        elec_por_apt.setdefault(p["apartamento_id"], []).append(p)

    reportes, no_aplican = [], []
    for apt in apartamentos:
        d = moras.deuda_real_inquilino(apt, alq_por_apt.get(apt["id"], []), elec_por_apt.get(apt["id"], []), hoy_rep)
        if d["aplica"]:
            reportes.append((apt, d))
        else:
            no_aplican.append((apt, d["motivo"]))

    if not reportes:
        st.info("No hay apartamentos ocupados con contrato de alquiler.")
    else:
        # ---------- Resumen de todos los apartamentos ----------
        total_alq = sum(d["alquiler"]["deuda"] for _a, d in reportes)
        total_elec = sum(d["electricidad"]["deuda"] for _a, d in reportes)
        r1, r2, r3 = st.columns(3)
        r1.metric("💵 Deuda de alquiler", fmt_money(total_alq))
        r2.metric("⚡ Deuda de electricidad", fmt_money(total_elec))
        r3.metric("Deuda total", fmt_money(total_alq + total_elec))

        filas_resumen = []
        for apt, d in reportes:
            up = d["alquiler"]["ultimo_pago"]
            filas_resumen.append({
                "Departamento": apt.get("codigo") or "—",
                "Inquilino": apt.get("inquilino_nombre") or "—",
                "Meses atrasados": d["alquiler"]["meses_atrasados"],
                "Deuda alquiler": d["alquiler"]["deuda"],
                "Deuda electricidad": d["electricidad"]["deuda"],
                "Deuda total": d["deuda_total"],
                "Último pago de alquiler": up["fecha"].strftime("%d/%m/%Y") if up else "Sin pagos",
            })
        filas_resumen.sort(key=lambda f: (-f["Deuda total"], f["Departamento"]))
        with st.container(border=True):
            st.markdown("**Resumen de deuda real por apartamento**")
            st.dataframe(
                pd.DataFrame(filas_resumen), use_container_width=True, hide_index=True,
                column_config={
                    "Meses atrasados": st.column_config.NumberColumn(format="%d"),
                    "Deuda alquiler": st.column_config.NumberColumn(format="Bs %.2f"),
                    "Deuda electricidad": st.column_config.NumberColumn(format="Bs %.2f"),
                    "Deuda total": st.column_config.NumberColumn(format="Bs %.2f"),
                },
            )

        # ---------- Reporte individual (vista previa + descargas) ----------
        st.divider()
        st.markdown("### Reporte para entregar al inquilino")
        etiquetas = [f'{a.get("codigo")} — {a.get("inquilino_nombre") or "sin nombre"}' for a, _d in reportes]
        indice = st.selectbox("Apartamento", range(len(reportes)), format_func=lambda i: etiquetas[i],
                              key="rep_apartamento")
        apt_sel, deuda_sel = reportes[indice]
        datos_rep = recibo.construir_datos_reporte_inquilino(apt_sel, deuda_sel, emitido_por=nombre_emisor)
        pdf_rep = _reporte_pdf_cache(datos_rep)
        png_rep = _reporte_png_cache(datos_rep)

        b1, b2 = st.columns(2)
        with b1:
            st.download_button("📄 Descargar reporte (PDF)", data=pdf_rep,
                               file_name=_nombre_archivo_reporte(apt_sel, hoy_rep, "pdf"),
                               mime="application/pdf", key="rep_pdf", use_container_width=True)
        with b2:
            st.download_button("🖼️ Descargar reporte (PNG)", data=png_rep,
                               file_name=_nombre_archivo_reporte(apt_sel, hoy_rep, "png"),
                               mime="image/png", key="rep_png", use_container_width=True)
        st.image(png_rep, width=640)

        # ---------- Todos los apartamentos en un solo ZIP ----------
        st.divider()
        st.markdown("### Descargar todos los reportes")
        st.caption("Genera un ZIP con el PDF de cada apartamento ocupado en alquiler, listo para imprimir o enviar.")
        if st.button("📦 Preparar ZIP con todos los PDF"):
            with st.spinner("Generando reportes..."):
                memoria = io.BytesIO()
                with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zf:
                    for apt, d in reportes:
                        datos_i = recibo.construir_datos_reporte_inquilino(apt, d, emitido_por=nombre_emisor)
                        zf.writestr(_nombre_archivo_reporte(apt, hoy_rep, "pdf"), _reporte_pdf_cache(datos_i))
                st.session_state["rep_zip"] = (hoy_rep, memoria.getvalue(), len(reportes))
        zip_guardado = st.session_state.get("rep_zip")
        if zip_guardado and zip_guardado[0] == hoy_rep:
            st.download_button(f"⬇️ Descargar ZIP ({zip_guardado[2]} reportes)", data=zip_guardado[1],
                               file_name=f"estados_de_cuenta_{hoy_rep:%Y-%m-%d}.zip",
                               mime="application/zip", key="rep_zip_dl")

    if no_aplican:
        with st.expander(f"Apartamentos sin reporte ({len(no_aplican)})"):
            for apt, motivo in no_aplican:
                st.write(f'**{apt.get("codigo")}**: {motivo}')

elif pagina == "📊 Actividad por usuario":
    st.title("📊 Reporte de actividad por usuario")
    st.caption(
        "Pagos, compras y ventas registrados por cada usuario (campo «Encargado») entre dos fechas. "
        "Los abonos de alquiler, electricidad y agua no guardan quién los cobró, por eso no aparecen aquí."
    )
    hoy_act = recibo.hoy_bolivia()
    nombre_emisor = usuario_actual.get("nombre") or usuario_actual.get("username")
    ca1, ca2 = st.columns(2)
    with ca1:
        act_desde = st.date_input("Desde", value=hoy_act.replace(day=1), format="DD/MM/YYYY", key="act_desde")
    with ca2:
        act_hasta = st.date_input("Hasta", value=hoy_act, format="DD/MM/YYYY", key="act_hasta")
    if not act_desde or not act_hasta:
        st.warning("Elige las dos fechas.")
        st.stop()
    if act_desde > act_hasta:
        st.error("La fecha «Desde» no puede ser posterior a «Hasta».")
        st.stop()

    datos_act = cargar_actividad(str(act_desde), str(act_hasta))
    activos = sorted({(u.get("nombre") or u.get("username")) for u in cargar_todos_los_usuarios()
                      if u.get("activo")} - {None})
    grupos = reportes.agrupar_actividad_por_usuario(
        datos_act["pagos_generales"], datos_act["compras"], datos_act["ventas"], usuarios_extra=activos)

    OPCION_TODOS = "📋 Todos los usuarios (reporte general)"
    opcion = st.selectbox("Usuario", [OPCION_TODOS] + list(grupos.keys()), key="act_usuario")
    elegidos = list(grupos.items()) if opcion == OPCION_TODOS else [(opcion, grupos[opcion])]
    reps = [reportes.construir_reporte_usuario(n, d) for n, d in elegidos]

    n_mov = sum(len(f) for _n, d in elegidos for f in d.values())
    k1, k2, k3 = st.columns(3)
    k1.metric("Movimientos", n_mov)
    k2.metric("Egresos (pagos + compras)", fmt_money(sum(r["total_egresos"] for r in reps)))
    k3.metric("Ingresos (ventas)", fmt_money(sum(r["total_ingresos"] for r in reps)))

    if n_mov == 0:
        st.info("No hay pagos, compras ni ventas registrados en ese periodo para la selección.")
    else:
        cfg_bs = {c: st.column_config.NumberColumn(format="Bs %.2f")
                  for c in ("Pagos realizados", "Compras realizadas", "Ventas realizadas",
                            "Egresos", "Ingresos", "Monto")}
        if len(reps) > 1:
            with st.container(border=True):
                st.markdown("**Resumen por usuario**")
                st.dataframe(pd.DataFrame([{
                    "Usuario": r["usuario"],
                    "Pagos realizados": r["categorias"]["pagos_generales"]["total"],
                    "Compras realizadas": r["categorias"]["compras"]["total"],
                    "Ventas realizadas": r["categorias"]["ventas"]["total"],
                    "Egresos": r["total_egresos"], "Ingresos": r["total_ingresos"],
                } for r in reps]), use_container_width=True, hide_index=True, column_config=cfg_bs)

        for r in reps:
            with st.expander(f'{r["usuario"]} — egresos {fmt_money(r["total_egresos"])} · '
                             f'ingresos {fmt_money(r["total_ingresos"])}', expanded=(len(reps) == 1)):
                for clave, titulo, _tipo in reportes.CATEGORIAS:
                    cat = r["categorias"][clave]
                    st.markdown(f"**{titulo}** ({len(cat['filas'])})")
                    if cat["filas"]:
                        st.dataframe(pd.DataFrame(cat["filas"]), use_container_width=True, hide_index=True,
                                     column_config=cfg_bs)
                        st.caption(f"Subtotal: {fmt_money(cat['total'])}")
                    else:
                        st.caption("Sin registros en este periodo.")

        # ---------- Descargas ----------
        etiqueta_archivo = "general" if opcion == OPCION_TODOS else \
            "".join(c if c.isalnum() else "_" for c in opcion).strip("_")
        base_archivo = f"actividad_{etiqueta_archivo}_{act_desde:%Y-%m-%d}_{act_hasta:%Y-%m-%d}"
        txt_desde, txt_hasta = f"{act_desde:%d/%m/%Y}", f"{act_hasta:%d/%m/%Y}"
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "📊 Descargar Excel", data=_actividad_excel_cache(reps, txt_desde, txt_hasta, nombre_emisor),
                file_name=f"{base_archivo}.xlsx", key="act_xlsx", use_container_width=True,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with d2:
            st.download_button(
                "📄 Descargar PDF", data=_actividad_pdf_cache(reps, txt_desde, txt_hasta, nombre_emisor),
                file_name=f"{base_archivo}.pdf", mime="application/pdf", key="act_pdf", use_container_width=True)

# ==================================================================
# PÁGINA: INQUILINOS (solo lectura, para todos los usuarios)
# ==================================================================
elif pagina == "🏠 Inquilinos":
    st.title("🏠 Inquilinos por apartamento")
    st.caption("Consulta de datos. Es solo lectura: para corregir o actualizar un dato, avisa a un Administrador.")

    def _md(valor):
        """Texto del usuario seguro para st.markdown (sin interpretar *, _, $, etc.). Vacío -> —"""
        texto = str(valor).strip() if valor not in (None, "") else ""
        if not texto:
            return "—"
        for ch in "\\`*_[]$<>~|":
            texto = texto.replace(ch, "\\" + ch)
        return texto

    def _f(valor):
        fecha = parse_fecha(valor)
        return fecha.strftime("%d/%m/%Y") if fecha else "—"

    def _ficha(pares):
        for etiqueta, valor in pares:
            st.markdown(f"**{etiqueta}:** {valor}")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("No hay apartamentos registrados todavía.")
    else:
        with st.container(border=True):
            st.markdown("**Resumen de apartamentos**")
            st.dataframe(pd.DataFrame([{
                "Apartamento": a.get("codigo"), "Piso": a.get("piso"), "Estado": a.get("estado"),
                "Inquilino": a.get("inquilino_nombre") or "—", "Celular": a.get("celular") or "—",
                "Alquiler": float(a.get("monto_alquiler") or 0),
                "Contrato": a.get("estado_contrato") or "—",
            } for a in apartamentos]), use_container_width=True, hide_index=True,
                column_config={"Alquiler": st.column_config.NumberColumn(format="Bs %.2f")})

        etiquetas_inq = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
        idx_inq = st.selectbox("Apartamento", range(len(apartamentos)), format_func=lambda i: etiquetas_inq[i],
                               key="inq_apartamento")
        apt = apartamentos[idx_inq]

        st.subheader(f'{apt["codigo"]} · {apt.get("piso") or ""}')
        if apt.get("estado") != "Ocupado":
            st.info("Este apartamento está desocupado.")

        ci1, ci2 = st.columns(2)
        with ci1:
            with st.container(border=True):
                st.markdown("**👤 Inquilino**")
                _ficha([("Nombre", _md(apt.get("inquilino_nombre"))), ("Celular", _md(apt.get("celular"))),
                        ("Cédula de identidad", _md(apt.get("cedula_identidad"))),
                        ("Nacionalidad", _md(apt.get("nacionalidad"))),
                        ("Fecha de nacimiento", _f(apt.get("fecha_nacimiento")))])
            with st.container(border=True):
                st.markdown("**👥 Referencia**")
                _ficha([("Nombre", _md(apt.get("referencia_nombre"))),
                        ("Parentesco", _md(apt.get("referencia_parentesco"))),
                        ("Celular", _md(apt.get("referencia_celular")))])
        with ci2:
            with st.container(border=True):
                st.markdown("**🏠 Ocupación y alquiler**")
                _ficha([("Estado", _md(apt.get("estado"))), ("Fecha de ingreso", _f(apt.get("fecha_ingreso"))),
                        ("Día de pago", _md(apt.get("dia_pago"))),
                        ("Alquiler mensual", fmt_money(apt.get("monto_alquiler") or 0)),
                        ("Garantía", _md(apt.get("garantia"))), ("Amoblado", _md(apt.get("amoblado"))),
                        ("Detalle", _md(apt.get("detalle")))])
            with st.container(border=True):
                st.markdown("**📄 Contrato**")
                _ficha([("Tipo", _md(apt.get("tipo_contrato"))), ("Estado", _md(apt.get("estado_contrato"))),
                        ("Fecha inicio", _f(apt.get("contrato_fecha_inicio"))),
                        ("Fecha fin", _f(apt.get("contrato_fecha_fin"))),
                        ("Observaciones", _md(apt.get("contrato_observaciones")))])

elif pagina == "🤝 Compromisos de pago":
    st.title("🤝 Compromisos de pago")
    st.caption(
        "Historial de los motivos de retraso que informa el inquilino y de los acuerdos de pago (compromiso, "
        "fecha plazo y monto). Todos los usuarios pueden registrar y editar; solo el Administrador puede eliminar."
    )
    mensaje_flash = st.session_state.pop("compromiso_msg", None)
    if mensaje_flash:
        st.success(mensaje_flash)

    hoy_c = recibo.hoy_bolivia()
    nombre_c = usuario_actual.get("nombre") or usuario_actual.get("username")
    apartamentos = cargar_apartamentos()
    try:
        todos_comp = cargar_compromisos()
    except Exception as e:
        st.error("No se pudo leer el historial de compromisos. Si es la primera vez que usas esta sección, "
                 "ejecuta el archivo `migracion_compromisos_pago.sql` en el SQL Editor de Supabase.")
        st.caption(f"Detalle técnico: {e}")
        st.stop()

    ocupados = [a for a in apartamentos if a.get("estado") == "Ocupado"]
    codigo_por_id = {a["id"]: a.get("codigo") for a in apartamentos}

    def _fmt_f(valor):
        f = parse_fecha(valor)
        return f.strftime("%d/%m/%Y") if f else "—"

    def _codigo_de(c):
        return (c.get("apartamentos") or {}).get("codigo") or codigo_por_id.get(c["apartamento_id"]) or "—"

    n_form = st.session_state.get("comp_form_n", 0)   # cambia al guardar: así el formulario se limpia solo si salió bien
    tab_nuevo_c, tab_hist_c = st.tabs(["➕ Nuevo compromiso", "📋 Historial y edición"])

    # ---------------- Nuevo compromiso ----------------
    with tab_nuevo_c:
        if not ocupados:
            st.info("No hay apartamentos ocupados.")
        else:
            etiquetas_c = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "sin nombre"}' for a in ocupados]
            i_c = st.selectbox("Apartamento", range(len(ocupados)), format_func=lambda i: etiquetas_c[i],
                               key="comp_apto")
            apt_c = ocupados[i_c]

            # Contexto: deuda actual, con la misma regla del Dashboard y del estado de cuenta
            alq_c = [p for p in cargar_periodos_abiertos("alquiler") if p["apartamento_id"] == apt_c["id"]]
            elec_c = [p for p in cargar_periodos_abiertos("electricidad") if p["apartamento_id"] == apt_c["id"]]
            d_c = moras.deuda_real_inquilino(apt_c, alq_c, elec_c, hoy_c)
            if d_c["aplica"]:
                m_atr = d_c["alquiler"]["meses_atrasados"]
                st.info(
                    f'Deuda actual — alquiler: {fmt_money(d_c["alquiler"]["deuda"])} '
                    f'({m_atr} mes{"es" if m_atr != 1 else ""} atrasado{"s" if m_atr != 1 else ""}) · '
                    f'electricidad: {fmt_money(d_c["electricidad"]["deuda"])} · '
                    f'**total: {fmt_money(d_c["deuda_total"])}**')
            else:
                st.caption(d_c["motivo"])
            abiertos = [c for c in todos_comp if c["apartamento_id"] == apt_c["id"]
                        and compromisos.estado_efectivo(c, hoy_c) in ("Pendiente", "Vencido")]
            if abiertos:
                st.warning(f'Este apartamento ya tiene {len(abiertos)} compromiso(s) pendiente(s) o vencido(s). '
                           'Revisa el historial antes de registrar otro.')

            with st.form(f"form_nuevo_compromiso_{n_form}"):
                fecha_reg = st.date_input("Fecha del registro", value=hoy_c, format="DD/MM/YYYY",
                                          key=f"cn_fecha_{n_form}")
                motivo = st.text_area("Motivo del retraso (lo que informó el inquilino)", max_chars=2000,
                                      key=f"cn_motivo_{n_form}")
                compromiso_txt = st.text_area(
                    "Compromiso asumido (opcional)", max_chars=2000, key=f"cn_comp_{n_form}",
                    placeholder='Ej. "Pagará la mitad esta semana y el resto el 30"')
                cp1, cp2 = st.columns(2)
                with cp1:
                    plazo = st.date_input("Fecha plazo (opcional)", value=None, format="DD/MM/YYYY",
                                          key=f"cn_plazo_{n_form}")
                with cp2:
                    monto = st.number_input("Monto acordado a pagar (Bs)", min_value=0.0, step=10.0,
                                            format="%.2f", value=0.0, key=f"cn_monto_{n_form}")
                st.caption(f"Se guardará como registrado por: **{nombre_c}**")
                guardar_c = st.form_submit_button("💾 Guardar compromiso")

            if guardar_c:
                errores = compromisos.validar_compromiso(motivo, compromiso_txt, fecha_reg, plazo, monto)
                for err in errores:
                    st.error(err)
                if not errores:
                    try:
                        db.crear_compromiso(compromisos.armar_registro(
                            motivo, compromiso_txt, fecha_reg, plazo, monto, "Pendiente", nombre_c, apartamento=apt_c))
                        limpiar_cache()
                        st.session_state["comp_form_n"] = n_form + 1
                        st.session_state["compromiso_msg"] = f'Compromiso registrado para {apt_c["codigo"]}.'
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo guardar: {e}")

    # ---------------- Historial y edición ----------------
    with tab_hist_c:
        ids_con_datos = {c["apartamento_id"] for c in todos_comp}
        apts_filtro = [a for a in apartamentos if a.get("estado") == "Ocupado" or a["id"] in ids_con_datos]
        nombres_apt = {a["id"]: f'{a["codigo"]} — {a.get("inquilino_nombre") or "sin inquilino"}' for a in apts_filtro}
        f1, f2 = st.columns(2)
        with f1:
            filtro_id = st.selectbox("Apartamento", [None] + [a["id"] for a in apts_filtro],
                                     format_func=lambda i: "Todos los apartamentos" if i is None else nombres_apt[i],
                                     key="comp_filtro_apto")
        with f2:
            filtro_estado = st.selectbox("Estado", ["Todos", "Pendiente", "Vencido", "Cumplido", "Incumplido"],
                                         key="comp_filtro_estado")

        base_c = [c for c in todos_comp if filtro_id is None or c["apartamento_id"] == filtro_id]
        pend_c = [c for c in base_c if compromisos.estado_efectivo(c, hoy_c) in ("Pendiente", "Vencido")]
        venc_c = [c for c in base_c if compromisos.estado_efectivo(c, hoy_c) == compromisos.ESTADO_VENCIDO]
        k1, k2, k3 = st.columns(3)
        k1.metric("Pendientes", len(pend_c))
        k2.metric("Vencidos", len(venc_c))
        k3.metric("Monto acordado por cobrar", fmt_money(sum(float(c.get("monto_comprometido") or 0) for c in pend_c)))

        filtrados = [c for c in base_c if filtro_estado == "Todos"
                     or compromisos.estado_efectivo(c, hoy_c) == filtro_estado]
        filtrados = (compromisos.ordenar_por_plazo(filtrados) if filtro_estado in ("Pendiente", "Vencido")
                     else compromisos.ordenar_historial(filtrados))

        if not filtrados:
            st.info("No hay compromisos registrados con ese filtro.")
        else:
            iconos = {"Pendiente": "🟡 Pendiente", "Vencido": "🔴 Vencido",
                      "Cumplido": "🟢 Cumplido", "Incumplido": "⚫ Incumplido"}
            st.dataframe(pd.DataFrame([{
                "Registro": _fmt_f(c.get("fecha_registro")),
                "Apartamento": _codigo_de(c),
                "Inquilino": c.get("inquilino_nombre") or "—",
                "Motivo del retraso": c.get("motivo_retraso") or "—",
                "Compromiso": c.get("compromiso") or "—",
                "Fecha plazo": _fmt_f(c.get("fecha_plazo")),
                "Monto acordado": float(c["monto_comprometido"]) if c.get("monto_comprometido") is not None else None,
                "Estado": iconos[compromisos.estado_efectivo(c, hoy_c)],
                "Registrado por": c.get("registrado_por") or "—",
                "Editado por": c.get("editado_por") or "—",
            } for c in filtrados]), use_container_width=True, hide_index=True,
                column_config={
                    "Motivo del retraso": st.column_config.TextColumn(width="large"),
                    "Compromiso": st.column_config.TextColumn(width="large"),
                    "Monto acordado": st.column_config.NumberColumn(format="Bs %.2f"),
                })

            st.divider()
            st.markdown("### ✏️ Editar un compromiso")
            por_id = {c["id"]: c for c in filtrados}

            def _etiqueta_comp(cid):
                c = por_id[cid]
                motivo_corto = (c.get("motivo_retraso") or "").replace("\n", " ")
                if len(motivo_corto) > 45:
                    motivo_corto = motivo_corto[:45] + "…"
                return f'{_fmt_f(c.get("fecha_registro"))} · {_codigo_de(c)} · {motivo_corto}'

            cid = st.selectbox("Compromiso", list(por_id.keys()), format_func=_etiqueta_comp, key="comp_editar_sel")
            c_sel = por_id[cid]
            with st.form(f"form_edit_compromiso_{cid}"):
                e_fecha = st.date_input("Fecha del registro", value=parse_fecha(c_sel.get("fecha_registro")) or hoy_c,
                                        format="DD/MM/YYYY", key=f"ce_fecha_{cid}")
                e_motivo = st.text_area("Motivo del retraso", value=c_sel.get("motivo_retraso") or "",
                                        max_chars=2000, key=f"ce_motivo_{cid}")
                e_comp = st.text_area("Compromiso asumido", value=c_sel.get("compromiso") or "",
                                      max_chars=2000, key=f"ce_comp_{cid}")
                ce1, ce2 = st.columns(2)
                with ce1:
                    e_plazo = st.date_input("Fecha plazo (opcional)", value=parse_fecha(c_sel.get("fecha_plazo")),
                                            format="DD/MM/YYYY", key=f"ce_plazo_{cid}")
                    quitar_plazo = (st.checkbox("Quitar la fecha plazo", key=f"ce_quitar_{cid}")
                                    if c_sel.get("fecha_plazo") else False)
                with ce2:
                    e_monto = st.number_input("Monto acordado a pagar (Bs)", min_value=0.0, step=10.0, format="%.2f",
                                              value=float(c_sel.get("monto_comprometido") or 0), key=f"ce_monto_{cid}")
                estado_actual = c_sel.get("estado") if c_sel.get("estado") in compromisos.ESTADOS else "Pendiente"
                e_estado = st.selectbox("Estado", compromisos.ESTADOS, index=compromisos.ESTADOS.index(estado_actual),
                                        key=f"ce_estado_{cid}")
                st.caption(f'Registrado por **{c_sel.get("registrado_por") or "—"}** · '
                           f'última edición por **{c_sel.get("editado_por") or "—"}**')
                if es_admin:
                    confirmar_borrar = st.checkbox("Confirmo que quiero eliminar este compromiso",
                                                   key=f"ce_confirmar_{cid}")
                    cg, cd = st.columns(2)
                    guardar_e = cg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                    eliminar_e = cd.form_submit_button("🗑️ Eliminar", use_container_width=True)
                else:
                    confirmar_borrar, eliminar_e = False, False
                    guardar_e = st.form_submit_button("💾 Guardar cambios", use_container_width=True)

            if guardar_e:
                plazo_final = None if quitar_plazo else e_plazo
                errores = compromisos.validar_compromiso(e_motivo, e_comp, e_fecha, plazo_final, e_monto)
                for err in errores:
                    st.error(err)
                if not errores:
                    try:
                        db.actualizar_compromiso(cid, compromisos.armar_registro(
                            e_motivo, e_comp, e_fecha, plazo_final, e_monto, e_estado, nombre_c))
                        limpiar_cache()
                        st.session_state["compromiso_msg"] = "Compromiso actualizado."
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo actualizar: {e}")

            if eliminar_e and es_admin:
                if not confirmar_borrar:
                    st.warning("Marca la casilla de confirmación para poder eliminar.")
                else:
                    try:
                        db.eliminar_compromiso(cid)
                        limpiar_cache()
                        st.session_state["compromiso_msg"] = "Compromiso eliminado."
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo eliminar: {e}")

elif pagina == "✅ Pendientes":
    st.title("✅ Pendientes")
    st.caption("Tareas y actividades del edificio: cualquier colaborador puede crearlas, "
               "asignarlas y actualizar su estado.")

    usuarios_activos = cargar_usuarios_activos()
    usuarios_todos = cargar_todos_los_usuarios()
    usuarios_por_id = {u["id"]: u for u in usuarios_todos}
    apartamentos_pend = cargar_apartamentos()
    nombre_usuario_actual = usuario_actual.get("nombre") or usuario_actual.get("username")

    def nombre_de(u):
        return u.get("nombre") or u.get("username") or "—"

    tab_nuevo, tab_tablero = st.tabs(["➕ Nuevo pendiente", "📋 Tablero"])

    # ---------------- Nuevo pendiente ----------------
    with tab_nuevo:
        with st.form("form_nuevo_pendiente", clear_on_submit=True):
            titulo = st.text_input("Título", placeholder='Ej. "Cambiar foco del pasillo piso 2"')
            descripcion = st.text_area("Descripción (opcional)")
            que_falta = st.text_input(
                "¿Qué falta para realizarlo? (opcional)",
                placeholder='Ej. "Comprar lampas", "Contratar personal", "Terminar tumbado antes"')
            observacion = st.text_area("Observación (opcional)")

            col1, col2, col3 = st.columns(3)
            with col1:
                prioridad = st.selectbox("Prioridad", PRIORIDADES_PENDIENTE, index=2)
            with col2:
                opciones_asignado = ["Sin asignar"] + [nombre_de(u) for u in usuarios_activos]
                asignado_sel = st.selectbox("Asignar a (opcional)", opciones_asignado)
            with col3:
                fecha_limite = st.date_input("Fecha límite (opcional)", value=None, format="DD/MM/YYYY")

            opciones_apto = ["(General, sin apartamento)"] + [f'{a["codigo"]} — {a.get("inquilino_nombre") or ""}'
                                                                for a in apartamentos_pend]
            apto_sel = st.selectbox("Apartamento relacionado (opcional)", opciones_apto)

            st.caption(f"Creado por: **{nombre_usuario_actual}**")
            guardar = st.form_submit_button("💾 Crear pendiente")

            if guardar:
                if not titulo.strip():
                    st.error("El título es obligatorio.")
                else:
                    try:
                        asignado_a_id = None
                        if asignado_sel != "Sin asignar":
                            idx = opciones_asignado.index(asignado_sel) - 1
                            asignado_a_id = usuarios_activos[idx]["id"]
                        apartamento_id_sel = None
                        if apto_sel != "(General, sin apartamento)":
                            idx_a = opciones_apto.index(apto_sel) - 1
                            apartamento_id_sel = apartamentos_pend[idx_a]["id"]

                        db.crear_pendiente({
                            "titulo": titulo.strip(),
                            "descripcion": descripcion or None,
                            "que_falta": que_falta or None,
                            "observacion": observacion or None,
                            "prioridad": prioridad,
                            "estado": "Pendiente",
                            "asignado_a": asignado_a_id,
                            "creado_por": usuario_actual.get("id"),
                            "apartamento_id": apartamento_id_sel,
                            "fecha_limite": str(fecha_limite) if fecha_limite else None,
                        })
                        limpiar_cache()
                        st.success("Pendiente creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    # ---------------- Tablero / listado ----------------
    with tab_tablero:
        colf1, colf2, colf3 = st.columns(3)
        with colf1:
            filtro_estado = st.selectbox("Estado", ["Todos"] + ESTADOS_PENDIENTE, key="pend_filtro_estado")
        with colf2:
            filtro_prioridad = st.selectbox("Prioridad", ["Todas"] + PRIORIDADES_PENDIENTE, key="pend_filtro_prioridad")
        with colf3:
            opciones_filtro_asig = ["Todos"] + [nombre_de(u) for u in usuarios_activos]
            filtro_asignado = st.selectbox("Asignado a", opciones_filtro_asig, key="pend_filtro_asignado")

        asignado_a_filtro_id = None
        if filtro_asignado != "Todos":
            idx_f = opciones_filtro_asig.index(filtro_asignado) - 1
            asignado_a_filtro_id = usuarios_activos[idx_f]["id"]

        pendientes = cargar_pendientes(
            estado=None if filtro_estado == "Todos" else filtro_estado,
            prioridad=None if filtro_prioridad == "Todas" else filtro_prioridad,
            asignado_a=asignado_a_filtro_id,
        )

        if not pendientes:
            st.info("No hay pendientes que coincidan con el filtro.")
        else:
            orden_prioridad = {"Urgente": 0, "Alta": 1, "Media": 2, "Baja": 3}
            pendientes = sorted(pendientes, key=lambda p: orden_prioridad.get(p["prioridad"], 9))

            colm1, colm2, colm3 = st.columns(3)
            colm1.metric("⏳ Pendientes", sum(1 for p in pendientes if p["estado"] == "Pendiente"))
            colm2.metric("🔧 En Proceso", sum(1 for p in pendientes if p["estado"] == "En Proceso"))
            colm3.metric("✅ Terminados", sum(1 for p in pendientes if p["estado"] == "Terminado"))

            st.divider()

            for p in pendientes:
                asignado_info = usuarios_por_id.get(p.get("asignado_a"))
                creador_info = usuarios_por_id.get(p.get("creado_por"))
                apto_info = p.get("apartamentos")
                asignado_txt = nombre_de(asignado_info) if asignado_info else "Sin asignar"
                apto_txt = f' · 🏠 {apto_info["codigo"]}' if apto_info else ""
                vencida = False
                if p.get("fecha_limite") and p["estado"] != "Terminado":
                    fl = parse_fecha(p["fecha_limite"])
                    vencida = bool(fl and fl < date.today())

                titulo_linea = (f'{COLOR_PRIORIDAD.get(p["prioridad"], "")} **{p["titulo"]}**  '
                                 f'{ICONO_ESTADO.get(p["estado"], "")} _{p["estado"]}_'
                                 + (" ⚠️ Vencido" if vencida else ""))

                with st.expander(titulo_linea):
                    if p.get("descripcion"):
                        st.write(p["descripcion"])
                    st.caption(f'Prioridad: **{p["prioridad"]}** · Asignado a: **{asignado_txt}**{apto_txt}'
                               + (f' · Vence: {p["fecha_limite"]}' if p.get("fecha_limite") else ""))
                    if p.get("que_falta"):
                        st.markdown(f'🧰 **¿Qué falta?:** {p["que_falta"]}')
                    if p.get("observacion"):
                        st.markdown(f'📝 **Observación:** {p["observacion"]}')
                    if p.get("creado_por"):
                        st.caption(f'Creado por {nombre_de(creador_info)} el {str(p["created_at"])[:10]}')

                    with st.form(f'form_pendiente_{p["id"]}'):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            nuevo_estado = st.selectbox("Estado", ESTADOS_PENDIENTE,
                                                         index=ESTADOS_PENDIENTE.index(p["estado"]),
                                                         key=f'pend_estado_{p["id"]}')
                        with col2:
                            nueva_prioridad = st.selectbox("Prioridad", PRIORIDADES_PENDIENTE,
                                                            index=PRIORIDADES_PENDIENTE.index(p["prioridad"]),
                                                            key=f'pend_prioridad_{p["id"]}')
                        with col3:
                            opciones_asig_edit = ["Sin asignar"] + [nombre_de(u) for u in usuarios_activos]
                            idx_actual = 0
                            if asignado_info:
                                for i, u in enumerate(usuarios_activos):
                                    if u["id"] == asignado_info["id"]:
                                        idx_actual = i + 1
                                        break
                            nuevo_asignado = st.selectbox("Asignado a (opcional)", opciones_asig_edit,
                                                           index=idx_actual, key=f'pend_asignado_{p["id"]}')

                        nuevo_titulo = st.text_input("Título", value=p["titulo"], key=f'pend_titulo_{p["id"]}')
                        nueva_desc = st.text_area("Descripción", value=p.get("descripcion") or "",
                                                   key=f'pend_desc_{p["id"]}')
                        nuevo_que_falta = st.text_input("¿Qué falta para realizarlo?",
                                                         value=p.get("que_falta") or "",
                                                         key=f'pend_quefalta_{p["id"]}')
                        nueva_observacion = st.text_area("Observación", value=p.get("observacion") or "",
                                                          key=f'pend_obs_{p["id"]}')
                        nueva_fecha_limite = st.date_input(
                            "Fecha límite", value=parse_fecha(p.get("fecha_limite")), format="DD/MM/YYYY",
                            key=f'pend_fecha_{p["id"]}')

                        colg, cold = st.columns(2)
                        guardar_p = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        eliminar_p = cold.form_submit_button("🗑️ Eliminar", use_container_width=True)

                        if guardar_p:
                            try:
                                nuevo_asignado_id = None
                                if nuevo_asignado != "Sin asignar":
                                    idx_na = opciones_asig_edit.index(nuevo_asignado) - 1
                                    nuevo_asignado_id = usuarios_activos[idx_na]["id"]

                                payload = {
                                    "titulo": nuevo_titulo.strip() or p["titulo"],
                                    "descripcion": nueva_desc or None,
                                    "que_falta": nuevo_que_falta or None,
                                    "observacion": nueva_observacion or None,
                                    "prioridad": nueva_prioridad,
                                    "asignado_a": nuevo_asignado_id,
                                    "fecha_limite": str(nueva_fecha_limite) if nueva_fecha_limite else None,
                                }
                                if nuevo_estado != p["estado"]:
                                    db.cambiar_estado_pendiente(p["id"], nuevo_estado)
                                db.actualizar_pendiente(p["id"], payload)
                                limpiar_cache()
                                st.success("Pendiente actualizado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar: {e}")

                        if eliminar_p:
                            try:
                                db.eliminar_pendiente(p["id"])
                                limpiar_cache()
                                st.success("Pendiente eliminado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: REUNIONES (área administrativa)
# Solo el Administrador puede crear/editar; el resto solo visualiza.
# ==================================================================
elif pagina == "🗒️ Reuniones":
    st.title("🗒️ Reuniones con el Área Administrativa")

    usuarios_todos_reu = cargar_todos_los_usuarios()
    usuarios_activos_reu = cargar_usuarios_activos()
    usuarios_por_id_reu = {u["id"]: u for u in usuarios_todos_reu}

    # Mapa reunion_id -> [usuario_id, ...], armado en Python en vez de con un
    # embed anidado (reuniones -> reuniones_participantes -> usuarios), que
    # resultó frágil en la librería de Supabase.
    participantes_ids_por_reunion = {}
    for fila in cargar_participantes_reuniones():
        participantes_ids_por_reunion.setdefault(fila["reunion_id"], []).append(fila["usuario_id"])

    def _nombre_usuario_reu(u):
        return u.get("nombre") or u.get("username") or "—"

    def _participantes_de(r):
        """Nombres de los usuarios del sistema que participaron en la reunión r."""
        ids = participantes_ids_por_reunion.get(r["id"], [])
        return [_nombre_usuario_reu(usuarios_por_id_reu[uid]) for uid in ids if uid in usuarios_por_id_reu]

    def _mostrar_reunion(r):
        """Vista de solo lectura de una reunión (usada tanto por Administrador como Cobrador)."""
        st.markdown(f'📅 **{r["fecha"]}**')
        st.markdown("**Puntos tratados:**")
        st.write(r["puntos_tratados"])
        if r.get("descripcion_acuerdos"):
            st.markdown("**Lo acordado:**")
            st.write(r["descripcion_acuerdos"])
        nombres_participantes = _participantes_de(r)
        partes = []
        if nombres_participantes:
            partes.append("👤 " + ", ".join(nombres_participantes))
        if r.get("invitados"):
            partes.append("🙋 Invitados: " + r["invitados"])
        if partes:
            st.caption(" · ".join(partes))
        if r.get("creado_por"):
            creador = usuarios_por_id_reu.get(r["creado_por"])
            if creador:
                st.caption(f'Registrado por {_nombre_usuario_reu(creador)}')

    if not es_admin:
        st.caption("Solo el Administrador puede crear o editar reuniones. Aquí puedes consultarlas.")
        reuniones = cargar_reuniones()
        if not reuniones:
            st.info("Todavía no hay reuniones registradas.")
        else:
            for r in reuniones:
                with st.expander(f'{r["fecha"]} — {(r["puntos_tratados"] or "")[:60]}'):
                    _mostrar_reunion(r)

    else:
        tab_nueva, tab_historial = st.tabs(["➕ Nueva reunión", "📋 Historial"])

        with tab_nueva:
            with st.form("form_nueva_reunion", clear_on_submit=True):
                fecha_reunion = st.date_input("Fecha de la reunión", value=date.today(), format="DD/MM/YYYY")
                puntos_tratados = st.text_area(
                    "Puntos tratados", height=120,
                    placeholder="Ej.\n- Estado de cobranza del mes\n- Mantenimiento del ascensor\n- Otros temas")
                descripcion_acuerdos = st.text_area(
                    "Descripción de lo acordado", height=100,
                    placeholder="Ej. Se acuerda solicitar 3 cotizaciones para el mantenimiento del ascensor...")

                opciones_participantes = [_nombre_usuario_reu(u) for u in usuarios_activos_reu]
                participantes_sel = st.multiselect("Participantes (usuarios del sistema)", opciones_participantes)
                invitados = st.text_input(
                    "Invitados (personas externas, opcional)",
                    placeholder="Ej. Juan Pérez (propietario PB-01), representante de la empresa X")

                st.caption(f'Registrado por: **{usuario_actual.get("nombre") or usuario_actual.get("username")}**')
                guardar = st.form_submit_button("💾 Guardar reunión")

                if guardar:
                    if not puntos_tratados.strip():
                        st.error("Los puntos tratados son obligatorios.")
                    else:
                        try:
                            ids_participantes = [
                                usuarios_activos_reu[opciones_participantes.index(nombre)]["id"]
                                for nombre in participantes_sel
                            ]
                            db.crear_reunion({
                                "fecha": str(fecha_reunion),
                                "puntos_tratados": puntos_tratados.strip(),
                                "descripcion_acuerdos": descripcion_acuerdos or None,
                                "invitados": invitados or None,
                                "creado_por": usuario_actual.get("id"),
                            }, ids_participantes)
                            limpiar_cache()
                            st.success("Reunión registrada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

        with tab_historial:
            reuniones = cargar_reuniones()
            if not reuniones:
                st.info("Todavía no hay reuniones registradas.")
            else:
                for r in reuniones:
                    with st.expander(f'{r["fecha"]} — {(r["puntos_tratados"] or "")[:60]}'):
                        _mostrar_reunion(r)
                        st.divider()

                        ids_actuales = participantes_ids_por_reunion.get(r["id"], [])
                        nombres_actuales = [
                            _nombre_usuario_reu(usuarios_por_id_reu[uid])
                            for uid in ids_actuales if uid in usuarios_por_id_reu
                        ]

                        with st.form(f'form_editar_reunion_{r["id"]}'):
                            e_fecha = st.date_input("Fecha", value=date.fromisoformat(str(r["fecha"])[:10]),
                                                     format="DD/MM/YYYY", key=f'reu_fecha_{r["id"]}')
                            e_puntos = st.text_area("Puntos tratados", value=r["puntos_tratados"],
                                                     height=120, key=f'reu_puntos_{r["id"]}')
                            e_acuerdos = st.text_area("Descripción de lo acordado",
                                                       value=r.get("descripcion_acuerdos") or "",
                                                       height=100, key=f'reu_acuerdos_{r["id"]}')
                            opciones_part_edit = [_nombre_usuario_reu(u) for u in usuarios_activos_reu]
                            e_participantes_sel = st.multiselect(
                                "Participantes (usuarios del sistema)", opciones_part_edit,
                                default=[n for n in nombres_actuales if n in opciones_part_edit],
                                key=f'reu_participantes_{r["id"]}')
                            e_invitados = st.text_input("Invitados (personas externas, opcional)",
                                                         value=r.get("invitados") or "",
                                                         key=f'reu_invitados_{r["id"]}')

                            colg, cold = st.columns(2)
                            guardar_e = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                            eliminar_e = cold.form_submit_button("🗑️ Eliminar reunión", use_container_width=True)

                            if guardar_e:
                                if not e_puntos.strip():
                                    st.error("Los puntos tratados son obligatorios.")
                                else:
                                    try:
                                        ids_nuevos = [
                                            usuarios_activos_reu[opciones_part_edit.index(nombre)]["id"]
                                            for nombre in e_participantes_sel
                                        ]
                                        db.actualizar_reunion(r["id"], {
                                            "fecha": str(e_fecha),
                                            "puntos_tratados": e_puntos.strip(),
                                            "descripcion_acuerdos": e_acuerdos or None,
                                            "invitados": e_invitados or None,
                                        }, ids_nuevos)
                                        limpiar_cache()
                                        st.success("Reunión actualizada.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al actualizar: {e}")

                            if eliminar_e:
                                try:
                                    db.eliminar_reunion(r["id"])
                                    limpiar_cache()
                                    st.success("Reunión eliminada.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: USUARIOS (solo Administrador)
# ==================================================================
elif pagina == "👥 Usuarios":
    if not es_admin:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("👥 Usuarios")
    st.caption("Administra quién puede entrar al sistema y con qué rol.")

    tab_lista, tab_nuevo = st.tabs(["📋 Lista y edición", "➕ Nuevo usuario"])

    with tab_lista:
        usuarios = db.listar_usuarios()
        if not usuarios:
            st.info("No hay usuarios registrados.")
        else:
            etiquetas = [f'{u["username"]} — {u.get("nombre") or ""} ({u["rol"]})' for u in usuarios]
            idx = st.selectbox("Selecciona un usuario", range(len(usuarios)), format_func=lambda i: etiquetas[i])
            u = usuarios[idx]

            with st.form("form_editar_usuario"):
                nombre = st.text_input("Nombre completo", value=u.get("nombre") or "")
                rol = st.selectbox("Rol", ROLES, index=ROLES.index(u["rol"]) if u["rol"] in ROLES else 0)
                activo = st.checkbox("Usuario activo", value=u.get("activo", True))
                st.caption("Deja la contraseña en blanco si no quieres cambiarla.")
                nueva_pwd = st.text_input("Nueva contraseña (opcional)", type="password")

                col_a, col_b = st.columns(2)
                guardar = col_a.form_submit_button("💾 Guardar cambios", use_container_width=True)
                eliminar = col_b.form_submit_button("🗑️ Eliminar usuario", use_container_width=True)

                if guardar:
                    if u["username"] == usuario_actual.get("username") and (not activo or rol != "Administrador"):
                        st.error("No puedes quitarte a ti mismo el acceso de Administrador o desactivarte.")
                    else:
                        payload = {"nombre": nombre or None, "rol": rol, "activo": activo}
                        if nueva_pwd:
                            payload["password_hash"] = hash_password(nueva_pwd)
                        try:
                            db.actualizar_usuario(u["id"], payload)
                            st.success("Usuario actualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")

                if eliminar:
                    if u["username"] == usuario_actual.get("username"):
                        st.error("No puedes eliminar tu propio usuario.")
                    else:
                        try:
                            db.eliminar_usuario(u["id"])
                            st.success("Usuario eliminado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")

    with tab_nuevo:
        with st.form("form_nuevo_usuario", clear_on_submit=True):
            username = st.text_input("Usuario (para iniciar sesión)")
            nombre = st.text_input("Nombre completo")
            rol = st.selectbox("Rol", ROLES, index=1)
            pwd1 = st.text_input("Contraseña", type="password")
            pwd2 = st.text_input("Repetir contraseña", type="password")

            crear = st.form_submit_button("➕ Crear usuario")
            if crear:
                if not username or not pwd1:
                    st.error("Usuario y contraseña son obligatorios.")
                elif pwd1 != pwd2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    try:
                        db.crear_usuario({
                            "username": username.strip().lower(),
                            "nombre": nombre or None,
                            "password_hash": hash_password(pwd1),
                            "rol": rol,
                            "activo": True,
                        })
                        st.success(f"Usuario {username} creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear (¿usuario repetido?): {e}")


# ==================================================================
# PÁGINA: COMPRAS (Gastos / Egresos)
# ==================================================================
elif pagina == "🧾 Compras":
    st.title("🧾 Compras (Gastos)")
    st.caption("Registro de salidas de dinero del edificio: reparaciones, artículos de limpieza, servicios, etc.")
    compras_con_estado = estado_disponible("compras", "estado_devolucion")
    if not compras_con_estado:
        st.warning(AVISO_MIGRACION_ESTADOS)

    nombre_encargado = usuario_actual.get("nombre") or usuario_actual.get("username")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar compra", "📜 Historial"])

    with tab_registrar:
        with st.form("form_nueva_compra", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha_compra = st.date_input("Fecha de compra", value=date.today(), format="DD/MM/YYYY")
                categoria_sel = st.selectbox("Categoría / Rubro", CATEGORIAS_GASTO)
                categoria_otro = st.text_input("Especificar categoría") if categoria_sel == "Otro" else ""
                monto_total = st.number_input("Monto total (Bs)", min_value=0.0, step=10.0)
                metodo_pago_sel = st.selectbox("Método de pago", METODOS_PAGO_MOVIMIENTOS)
                metodo_pago_otro = st.text_input("Especificar método de pago") if metodo_pago_sel == "Otro" else ""
            with col2:
                proveedor = st.text_input("Proveedor (tienda o técnico)")
                numero_comprobante = st.text_input("Número de comprobante (factura/recibo)")
                if compras_con_estado:
                    estado_compra = st.selectbox("Estado", estados.ESTADOS_DEVOLUCION, key="compra_estado")
            descripcion = st.text_area("Descripción detallada",
                                        placeholder='Ej. "Compra de 4 focos LED para el pasillo del piso 3"')

            st.caption(f"Registrado por: **{nombre_encargado}**")

            guardar = st.form_submit_button("💾 Registrar compra")
            if guardar:
                if monto_total <= 0:
                    st.error("El monto total debe ser mayor a 0.")
                else:
                    try:
                        nueva_compra = {
                            "fecha_compra": str(fecha_compra),
                            "categoria": categoria_otro if categoria_sel == "Otro" and categoria_otro else categoria_sel,
                            "descripcion": descripcion or None,
                            "monto_total": monto_total,
                            "metodo_pago": metodo_pago_otro if metodo_pago_sel == "Otro" and metodo_pago_otro else metodo_pago_sel,
                            "proveedor": proveedor or None,
                            "numero_comprobante": numero_comprobante or None,
                            "encargado": nombre_encargado,
                        }
                        if compras_con_estado:
                            nueva_compra["estado_devolucion"] = estado_compra
                        db.crear_compra(nueva_compra)
                        st.success("Compra registrada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    with tab_historial:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filtro_desde = st.date_input("Desde", value=date.today().replace(day=1), format="DD/MM/YYYY",
                                          key="compras_desde")
        with col2:
            filtro_hasta = st.date_input("Hasta", value=date.today(), format="DD/MM/YYYY", key="compras_hasta")
        with col3:
            filtro_categoria = st.selectbox("Categoría", ["Todas"] + CATEGORIAS_GASTO, key="compras_cat")
        with col4:
            filtro_estado = (st.selectbox("Estado", ["Todos"] + estados.ESTADOS_DEVOLUCION, key="compras_estado_filtro")
                             if compras_con_estado else "Todos")

        compras = db.listar_compras(
            fecha_desde=str(filtro_desde), fecha_hasta=str(filtro_hasta),
            categoria=None if filtro_categoria == "Todas" else filtro_categoria,
        )
        compras = estados.filtrar_por_estado(compras, "estado_devolucion", filtro_estado, estados.ESTADOS_DEVOLUCION)

        if not compras:
            st.info("No hay compras que coincidan con el filtro.")
        else:
            total = sum(float(c["monto_total"]) for c in compras)
            mc1, mc2 = st.columns(2)
            mc1.metric("Total gastado en el periodo", fmt_money(total))
            if compras_con_estado:
                mc2.metric("Pendiente de devolución", fmt_money(estados.monto_pendiente(
                    compras, "estado_devolucion", "monto_total", estados.PENDIENTE_DEVOLUCION)))
            st.dataframe(
                pd.DataFrame([{
                    "Fecha": c["fecha_compra"], "Categoría": c["categoria"],
                    "Descripción": c.get("descripcion") or "", "Monto": c["monto_total"],
                    "Proveedor": c.get("proveedor") or "", "Comprobante N°": c.get("numero_comprobante") or "",
                    "Encargado": c.get("encargado") or "",
                    **({"Estado": estados.normalizar(c.get("estado_devolucion"), estados.ESTADOS_DEVOLUCION)}
                       if compras_con_estado else {}),
                } for c in compras]),
                use_container_width=True, hide_index=True,
            )

            with st.expander("✏️ Editar o eliminar una compra"):
                opciones = [f'{c["fecha_compra"]} — {c["categoria"]} — {fmt_money(c["monto_total"])}'
                            for c in compras]
                sel = st.selectbox("Compra", range(len(opciones)), format_func=lambda i: opciones[i])
                c = compras[sel]
                if c.get("archivo_url"):
                    st.markdown(f'📎 [Ver comprobante adjunto]({c["archivo_url"]})')
                with st.form(f'form_editar_compra_{c["id"]}'):
                    e_fecha = st.date_input("Fecha", value=date.fromisoformat(str(c["fecha_compra"])[:10]),
                                             format="DD/MM/YYYY")
                    e_categoria = st.text_input("Categoría", value=c["categoria"])
                    e_descripcion = st.text_area("Descripción", value=c.get("descripcion") or "")
                    e_monto = st.number_input("Monto total (Bs)", min_value=0.0, step=10.0,
                                               value=float(c["monto_total"]))
                    e_metodo = st.text_input("Método de pago", value=c.get("metodo_pago") or "")
                    e_proveedor = st.text_input("Proveedor", value=c.get("proveedor") or "")
                    e_comprobante = st.text_input("N° de comprobante", value=c.get("numero_comprobante") or "")
                    if compras_con_estado:
                        e_estado = st.selectbox(
                            "Estado", estados.ESTADOS_DEVOLUCION,
                            index=estados.indice(c.get("estado_devolucion"), estados.ESTADOS_DEVOLUCION),
                            key=f'compra_estado_edit_{c["id"]}')

                    if es_admin:
                        colg, cold = st.columns(2)
                        g = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = cold.form_submit_button("🗑️ Eliminar compra", use_container_width=True)
                    else:
                        g = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = False

                    if g:
                        try:
                            cambios_compra = {
                                "fecha_compra": str(e_fecha), "categoria": e_categoria,
                                "descripcion": e_descripcion or None, "monto_total": e_monto,
                                "metodo_pago": e_metodo or None, "proveedor": e_proveedor or None,
                                "numero_comprobante": e_comprobante or None,
                            }
                            if compras_con_estado:
                                cambios_compra["estado_devolucion"] = e_estado
                            db.actualizar_compra(c["id"], cambios_compra)
                            st.success("Compra actualizada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
                    if d:
                        try:
                            db.eliminar_compra(c["id"])
                            st.success("Compra eliminada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: PAGOS (pagos generales, sin comprobante adjunto)
# ==================================================================
elif pagina == "💳 Pagos":
    st.title("💳 Pagos")
    st.caption("Pagos generales del edificio que no requieren comprobante adjunto: "
               "sueldos, servicios, pagos a proveedores, etc.")
    pagos_con_estado = estado_disponible("pagos_generales", "estado_devolucion")
    if not pagos_con_estado:
        st.warning(AVISO_MIGRACION_ESTADOS)

    nombre_encargado = usuario_actual.get("nombre") or usuario_actual.get("username")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar pago", "📜 Historial"])

    with tab_registrar:
        with st.form("form_nuevo_pago_general", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha_pago = st.date_input("Fecha de pago", value=date.today(), format="DD/MM/YYYY")
                categoria_sel = st.selectbox("Categoría / Concepto", CATEGORIAS_PAGO)
                categoria_otro = st.text_input("Especificar categoría") if categoria_sel == "Otro" else ""
                monto = st.number_input("Monto pagado (Bs)", min_value=0.0, step=10.0)
            with col2:
                metodo_pago_sel = st.selectbox("Método de pago", METODOS_PAGO_MOVIMIENTOS)
                metodo_pago_otro = st.text_input("Especificar método de pago") if metodo_pago_sel == "Otro" else ""
                beneficiario = st.text_input("Beneficiario (a quién se le pagó)")
                if pagos_con_estado:
                    estado_pago = st.selectbox("Estado", estados.ESTADOS_DEVOLUCION, key="pago_estado")
            descripcion = st.text_area("Descripción",
                                        placeholder='Ej. "Pago de factura de luz de áreas comunes, septiembre"')

            st.caption(f"Registrado por: **{nombre_encargado}**")

            guardar = st.form_submit_button("💾 Registrar pago")
            if guardar:
                if monto <= 0:
                    st.error("El monto pagado debe ser mayor a 0.")
                else:
                    try:
                        nuevo_pago = {
                            "fecha_pago": str(fecha_pago),
                            "categoria": categoria_otro if categoria_sel == "Otro" and categoria_otro else categoria_sel,
                            "descripcion": descripcion or None,
                            "monto": monto,
                            "metodo_pago": metodo_pago_otro if metodo_pago_sel == "Otro" and metodo_pago_otro else metodo_pago_sel,
                            "beneficiario": beneficiario or None,
                            "encargado": nombre_encargado,
                        }
                        if pagos_con_estado:
                            nuevo_pago["estado_devolucion"] = estado_pago
                        db.crear_pago_general(nuevo_pago)
                        st.success("Pago registrado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    with tab_historial:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filtro_desde = st.date_input("Desde", value=date.today().replace(day=1), format="DD/MM/YYYY",
                                          key="pagos_gen_desde")
        with col2:
            filtro_hasta = st.date_input("Hasta", value=date.today(), format="DD/MM/YYYY", key="pagos_gen_hasta")
        with col3:
            filtro_categoria = st.selectbox("Categoría", ["Todas"] + CATEGORIAS_PAGO, key="pagos_gen_cat")
        with col4:
            filtro_estado = (st.selectbox("Estado", ["Todos"] + estados.ESTADOS_DEVOLUCION, key="pagos_gen_estado_filtro")
                             if pagos_con_estado else "Todos")

        pagos_generales = db.listar_pagos_generales(
            fecha_desde=str(filtro_desde), fecha_hasta=str(filtro_hasta),
            categoria=None if filtro_categoria == "Todas" else filtro_categoria,
        )
        pagos_generales = estados.filtrar_por_estado(
            pagos_generales, "estado_devolucion", filtro_estado, estados.ESTADOS_DEVOLUCION)

        if not pagos_generales:
            st.info("No hay pagos que coincidan con el filtro.")
        else:
            total = sum(float(pg["monto"]) for pg in pagos_generales)
            mp1, mp2 = st.columns(2)
            mp1.metric("Total pagado en el periodo", fmt_money(total))
            if pagos_con_estado:
                mp2.metric("Pendiente de devolución", fmt_money(estados.monto_pendiente(
                    pagos_generales, "estado_devolucion", "monto", estados.PENDIENTE_DEVOLUCION)))
            st.dataframe(
                pd.DataFrame([{
                    "Fecha": pg["fecha_pago"], "Categoría": pg["categoria"],
                    "Descripción": pg.get("descripcion") or "", "Monto": pg["monto"],
                    "Método de pago": pg.get("metodo_pago") or "", "Beneficiario": pg.get("beneficiario") or "",
                    "Encargado": pg.get("encargado") or "",
                    **({"Estado": estados.normalizar(pg.get("estado_devolucion"), estados.ESTADOS_DEVOLUCION)}
                       if pagos_con_estado else {}),
                } for pg in pagos_generales]),
                use_container_width=True, hide_index=True,
            )

            with st.expander("✏️ Editar o eliminar un pago"):
                opciones = [f'{pg["fecha_pago"]} — {pg["categoria"]} — {fmt_money(pg["monto"])}'
                            for pg in pagos_generales]
                sel = st.selectbox("Pago", range(len(opciones)), format_func=lambda i: opciones[i])
                pg = pagos_generales[sel]
                with st.form(f'form_editar_pago_general_{pg["id"]}'):
                    e_fecha = st.date_input("Fecha", value=date.fromisoformat(str(pg["fecha_pago"])[:10]),
                                             format="DD/MM/YYYY")
                    e_categoria = st.text_input("Categoría", value=pg["categoria"])
                    e_descripcion = st.text_area("Descripción", value=pg.get("descripcion") or "")
                    e_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0, value=float(pg["monto"]))
                    e_metodo = st.text_input("Método de pago", value=pg.get("metodo_pago") or "")
                    e_beneficiario = st.text_input("Beneficiario", value=pg.get("beneficiario") or "")
                    if pagos_con_estado:
                        e_estado = st.selectbox(
                            "Estado", estados.ESTADOS_DEVOLUCION,
                            index=estados.indice(pg.get("estado_devolucion"), estados.ESTADOS_DEVOLUCION),
                            key=f'pago_estado_edit_{pg["id"]}')

                    if es_admin:
                        colg, cold = st.columns(2)
                        g = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = cold.form_submit_button("🗑️ Eliminar pago", use_container_width=True)
                    else:
                        g = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = False

                    if g:
                        try:
                            cambios_pago = {
                                "fecha_pago": str(e_fecha), "categoria": e_categoria,
                                "descripcion": e_descripcion or None, "monto": e_monto,
                                "metodo_pago": e_metodo or None, "beneficiario": e_beneficiario or None,
                            }
                            if pagos_con_estado:
                                cambios_pago["estado_devolucion"] = e_estado
                            db.actualizar_pago_general(pg["id"], cambios_pago)
                            st.success("Pago actualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
                    if d:
                        try:
                            db.eliminar_pago_general(pg["id"])
                            st.success("Pago eliminado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: VENTAS (Ingresos extraordinarios)
# ==================================================================
elif pagina == "💸 Ventas":
    st.title("💸 Ventas (Ingresos extraordinarios)")
    st.caption("Venta de activos, cobro por uso de áreas comunes, parqueos de visita, copias de llaves, etc.")
    ventas_con_estado = estado_disponible("ventas", "estado_entrega")
    if not ventas_con_estado:
        st.warning(AVISO_MIGRACION_ESTADOS)

    nombre_encargado = usuario_actual.get("nombre") or usuario_actual.get("username")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar venta", "📜 Historial"])

    with tab_registrar:
        with st.form("form_nueva_venta", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha_venta = st.date_input("Fecha de venta", value=date.today(), format="DD/MM/YYYY")
                concepto_sel = st.selectbox("Concepto de ingreso", CONCEPTOS_VENTA)
                concepto_otro = st.text_input("Especificar concepto") if concepto_sel == "Otro" else ""
                monto = st.number_input("Monto recibido (Bs)", min_value=0.0, step=10.0)
            with col2:
                forma_cobro_sel = st.selectbox("Forma de cobro", METODOS_PAGO_MOVIMIENTOS)
                forma_cobro_otro = st.text_input("Especificar forma de cobro") if forma_cobro_sel == "Otro" else ""
                comprador = st.text_input("Comprador (residente, depto. o tercero)")
                recibo_emitido = st.text_input("N° de recibo emitido")
                if ventas_con_estado:
                    estado_venta = st.selectbox("Estado", estados.ESTADOS_ENTREGA, key="venta_estado")
            descripcion = st.text_area("Descripción",
                                        placeholder='Ej. "Alquiler del salón de eventos al departamento 402"')

            st.caption(f"Registrado por: **{nombre_encargado}**")

            guardar = st.form_submit_button("💾 Registrar venta")
            if guardar:
                if monto <= 0:
                    st.error("El monto recibido debe ser mayor a 0.")
                else:
                    try:
                        nueva_venta = {
                            "fecha_venta": str(fecha_venta),
                            "concepto": concepto_otro if concepto_sel == "Otro" and concepto_otro else concepto_sel,
                            "descripcion": descripcion or None,
                            "monto": monto,
                            "forma_cobro": forma_cobro_otro if forma_cobro_sel == "Otro" and forma_cobro_otro else forma_cobro_sel,
                            "comprador": comprador or None,
                            "recibo_emitido": recibo_emitido or None,
                            "encargado": nombre_encargado,
                        }
                        if ventas_con_estado:
                            nueva_venta["estado_entrega"] = estado_venta
                        db.crear_venta(nueva_venta)
                        st.success("Venta registrada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    with tab_historial:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filtro_desde = st.date_input("Desde", value=date.today().replace(day=1), format="DD/MM/YYYY",
                                          key="ventas_desde")
        with col2:
            filtro_hasta = st.date_input("Hasta", value=date.today(), format="DD/MM/YYYY", key="ventas_hasta")
        with col3:
            filtro_concepto = st.selectbox("Concepto", ["Todos"] + CONCEPTOS_VENTA, key="ventas_concepto")
        with col4:
            filtro_estado = (st.selectbox("Estado", ["Todos"] + estados.ESTADOS_ENTREGA, key="ventas_estado_filtro")
                             if ventas_con_estado else "Todos")

        ventas = db.listar_ventas(
            fecha_desde=str(filtro_desde), fecha_hasta=str(filtro_hasta),
            concepto=None if filtro_concepto == "Todos" else filtro_concepto,
        )
        ventas = estados.filtrar_por_estado(ventas, "estado_entrega", filtro_estado, estados.ESTADOS_ENTREGA)

        if not ventas:
            st.info("No hay ventas que coincidan con el filtro.")
        else:
            total = sum(float(v["monto"]) for v in ventas)
            mv1, mv2 = st.columns(2)
            mv1.metric("Total recibido en el periodo", fmt_money(total))
            if ventas_con_estado:
                mv2.metric("Pendiente de entrega", fmt_money(estados.monto_pendiente(
                    ventas, "estado_entrega", "monto", estados.PENDIENTE_ENTREGA)))
            st.dataframe(
                pd.DataFrame([{
                    "Fecha": v["fecha_venta"], "Concepto": v["concepto"],
                    "Descripción": v.get("descripcion") or "", "Monto": v["monto"],
                    "Comprador": v.get("comprador") or "", "Recibo N°": v.get("recibo_emitido") or "",
                    "Encargado": v.get("encargado") or "",
                    **({"Estado": estados.normalizar(v.get("estado_entrega"), estados.ESTADOS_ENTREGA)}
                       if ventas_con_estado else {}),
                } for v in ventas]),
                use_container_width=True, hide_index=True,
            )

            with st.expander("✏️ Editar o eliminar una venta"):
                opciones = [f'{v["fecha_venta"]} — {v["concepto"]} — {fmt_money(v["monto"])}' for v in ventas]
                sel = st.selectbox("Venta", range(len(opciones)), format_func=lambda i: opciones[i])
                v = ventas[sel]
                with st.form(f'form_editar_venta_{v["id"]}'):
                    e_fecha = st.date_input("Fecha", value=date.fromisoformat(str(v["fecha_venta"])[:10]),
                                             format="DD/MM/YYYY")
                    e_concepto = st.text_input("Concepto", value=v["concepto"])
                    e_descripcion = st.text_area("Descripción", value=v.get("descripcion") or "")
                    e_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0, value=float(v["monto"]))
                    e_forma_cobro = st.text_input("Forma de cobro", value=v.get("forma_cobro") or "")
                    e_comprador = st.text_input("Comprador", value=v.get("comprador") or "")
                    e_recibo = st.text_input("N° de recibo", value=v.get("recibo_emitido") or "")
                    if ventas_con_estado:
                        e_estado = st.selectbox(
                            "Estado", estados.ESTADOS_ENTREGA,
                            index=estados.indice(v.get("estado_entrega"), estados.ESTADOS_ENTREGA),
                            key=f'venta_estado_edit_{v["id"]}')

                    if es_admin:
                        colg, cold = st.columns(2)
                        g = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = cold.form_submit_button("🗑️ Eliminar venta", use_container_width=True)
                    else:
                        g = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = False

                    if g:
                        try:
                            cambios_venta = {
                                "fecha_venta": str(e_fecha), "concepto": e_concepto,
                                "descripcion": e_descripcion or None, "monto": e_monto,
                                "forma_cobro": e_forma_cobro or None, "comprador": e_comprador or None,
                                "recibo_emitido": e_recibo or None,
                            }
                            if ventas_con_estado:
                                cambios_venta["estado_entrega"] = e_estado
                            db.actualizar_venta(v["id"], cambios_venta)
                            st.success("Venta actualizada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
                    if d:
                        try:
                            db.eliminar_venta(v["id"])
                            st.success("Venta eliminada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")
