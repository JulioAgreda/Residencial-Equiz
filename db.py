"""
Conexión a Supabase para el Sistema de Control del Residencial.
"""
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


# ---------- Apartamentos ----------

def listar_apartamentos():
    sb = get_client()
    res = sb.table("apartamentos").select("*").order("codigo").execute()
    return res.data or []


def obtener_apartamento(apartamento_id):
    sb = get_client()
    res = sb.table("apartamentos").select("*").eq("id", apartamento_id).single().execute()
    return res.data


def crear_apartamento(payload: dict):
    sb = get_client()
    return sb.table("apartamentos").insert(payload).execute()


def actualizar_apartamento(apartamento_id, payload: dict):
    sb = get_client()
    return sb.table("apartamentos").update(payload).eq("id", apartamento_id).execute()


def eliminar_apartamento(apartamento_id):
    sb = get_client()
    return sb.table("apartamentos").delete().eq("id", apartamento_id).execute()


# ---------- Periodos de alquiler (un registro por apartamento + mes/año) ----------

def listar_periodos(apartamento_id=None, anio=None, mes=None):
    """Trae los periodos junto con el apartamento y todos sus pagos (abonos) asociados."""
    sb = get_client()
    q = sb.table("periodos_alquiler").select(
        "*, apartamentos(codigo, piso, inquilino_nombre), pagos(id, fecha, monto, metodo_pago, observacion)"
    )
    if apartamento_id:
        q = q.eq("apartamento_id", apartamento_id)
    if anio:
        q = q.eq("anio", anio)
    if mes:
        q = q.eq("mes", mes)
    res = q.order("anio", desc=True).execute()
    return res.data or []


def obtener_periodo(apartamento_id, mes, anio):
    sb = get_client()
    res = (
        sb.table("periodos_alquiler")
        .select("*, pagos(id, fecha, monto, metodo_pago, observacion)")
        .eq("apartamento_id", apartamento_id)
        .eq("mes", mes)
        .eq("anio", anio)
        .execute()
    )
    data = res.data or []
    return data[0] if data else None


def crear_periodo(payload: dict):
    sb = get_client()
    res = sb.table("periodos_alquiler").insert(payload).execute()
    return res.data[0]


def actualizar_periodo(periodo_id, payload: dict):
    sb = get_client()
    return sb.table("periodos_alquiler").update(payload).eq("id", periodo_id).execute()


def obtener_o_crear_periodo(apartamento_id, mes, anio, monto_esperado):
    """Devuelve el periodo existente para ese apartamento/mes/año, o lo crea si no existe."""
    periodo = obtener_periodo(apartamento_id, mes, anio)
    if periodo:
        return periodo
    nuevo = crear_periodo({
        "apartamento_id": apartamento_id,
        "mes": mes,
        "anio": anio,
        "monto_esperado": monto_esperado,
    })
    nuevo["pagos"] = []
    return nuevo


# ---------- Pagos (abonos individuales dentro de un periodo) ----------

def crear_pago(payload: dict):
    sb = get_client()
    return sb.table("pagos").insert(payload).execute()


def actualizar_pago(pago_id, payload: dict):
    sb = get_client()
    return sb.table("pagos").update(payload).eq("id", pago_id).execute()


def eliminar_pago(pago_id):
    sb = get_client()
    return sb.table("pagos").delete().eq("id", pago_id).execute()


# ---------- Configuración (tarifa de electricidad y agua) ----------

def obtener_tarifa_kwh():
    sb = get_client()
    res = sb.table("configuracion").select("tarifa_kwh").eq("id", 1).execute()
    data = res.data or []
    return float(data[0]["tarifa_kwh"]) if data else 0.0


def guardar_tarifa_kwh(valor):
    sb = get_client()
    return sb.table("configuracion").upsert({"id": 1, "tarifa_kwh": valor}).execute()


def obtener_tarifa_agua():
    sb = get_client()
    res = sb.table("configuracion").select("tarifa_agua").eq("id", 1).execute()
    data = res.data or []
    return float(data[0]["tarifa_agua"]) if data else 0.0


def guardar_tarifa_agua(valor):
    sb = get_client()
    return sb.table("configuracion").upsert({"id": 1, "tarifa_agua": valor}).execute()


# ---------- Periodos de electricidad (un registro por apartamento + mes/año) ----------

def listar_periodos_electricidad(apartamento_id=None, anio=None, mes=None):
    sb = get_client()
    q = sb.table("periodos_electricidad").select(
        "*, apartamentos(codigo, piso, inquilino_nombre), pagos_electricidad(id, fecha, monto, metodo_pago, observacion)"
    )
    if apartamento_id:
        q = q.eq("apartamento_id", apartamento_id)
    if anio:
        q = q.eq("anio", anio)
    if mes:
        q = q.eq("mes", mes)
    res = q.order("anio", desc=True).execute()
    return res.data or []


def obtener_periodo_electricidad(apartamento_id, mes, anio):
    sb = get_client()
    res = (
        sb.table("periodos_electricidad")
        .select("*, pagos_electricidad(id, fecha, monto, metodo_pago, observacion)")
        .eq("apartamento_id", apartamento_id)
        .eq("mes", mes)
        .eq("anio", anio)
        .execute()
    )
    data = res.data or []
    return data[0] if data else None


def ultimo_periodo_electricidad(apartamento_id):
    """Último periodo registrado (por fecha de creación) para precargar el Kwh anterior."""
    sb = get_client()
    res = (
        sb.table("periodos_electricidad")
        .select("*")
        .eq("apartamento_id", apartamento_id)
        .order("anio", desc=True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    data = res.data or []
    return data[0] if data else None


def crear_periodo_electricidad(payload: dict):
    sb = get_client()
    res = sb.table("periodos_electricidad").insert(payload).execute()
    return res.data[0]


def actualizar_periodo_electricidad(periodo_id, payload: dict):
    sb = get_client()
    return sb.table("periodos_electricidad").update(payload).eq("id", periodo_id).execute()


# ---------- Pagos de electricidad (abonos individuales) ----------

def crear_pago_electricidad(payload: dict):
    sb = get_client()
    return sb.table("pagos_electricidad").insert(payload).execute()


def actualizar_pago_electricidad(pago_id, payload: dict):
    sb = get_client()
    return sb.table("pagos_electricidad").update(payload).eq("id", pago_id).execute()


def eliminar_pago_electricidad(pago_id):
    sb = get_client()
    return sb.table("pagos_electricidad").delete().eq("id", pago_id).execute()


# ---------- Periodos de agua (un registro por apartamento + mes/año) ----------

def listar_periodos_agua(apartamento_id=None, anio=None, mes=None):
    sb = get_client()
    q = sb.table("periodos_agua").select(
        "*, apartamentos(codigo, piso, inquilino_nombre), pagos_agua(id, fecha, monto, metodo_pago, observacion)"
    )
    if apartamento_id:
        q = q.eq("apartamento_id", apartamento_id)
    if anio:
        q = q.eq("anio", anio)
    if mes:
        q = q.eq("mes", mes)
    res = q.order("anio", desc=True).execute()
    return res.data or []


def obtener_periodo_agua(apartamento_id, mes, anio):
    sb = get_client()
    res = (
        sb.table("periodos_agua")
        .select("*, pagos_agua(id, fecha, monto, metodo_pago, observacion)")
        .eq("apartamento_id", apartamento_id)
        .eq("mes", mes)
        .eq("anio", anio)
        .execute()
    )
    data = res.data or []
    return data[0] if data else None


def ultimo_periodo_agua(apartamento_id):
    """Último periodo registrado (por fecha de creación) para precargar la lectura anterior."""
    sb = get_client()
    res = (
        sb.table("periodos_agua")
        .select("*")
        .eq("apartamento_id", apartamento_id)
        .order("anio", desc=True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    data = res.data or []
    return data[0] if data else None


def crear_periodo_agua(payload: dict):
    sb = get_client()
    res = sb.table("periodos_agua").insert(payload).execute()
    return res.data[0]


def actualizar_periodo_agua(periodo_id, payload: dict):
    sb = get_client()
    return sb.table("periodos_agua").update(payload).eq("id", periodo_id).execute()


# ---------- Pagos de agua (abonos individuales) ----------

def crear_pago_agua(payload: dict):
    sb = get_client()
    return sb.table("pagos_agua").insert(payload).execute()


def actualizar_pago_agua(pago_id, payload: dict):
    sb = get_client()
    return sb.table("pagos_agua").update(payload).eq("id", pago_id).execute()


def eliminar_pago_agua(pago_id):
    sb = get_client()
    return sb.table("pagos_agua").delete().eq("id", pago_id).execute()


# ---------- Usuarios (roles y permisos) ----------

def listar_usuarios():
    sb = get_client()
    res = sb.table("usuarios").select("*").order("username").execute()
    return res.data or []


def obtener_usuario_por_username(username):
    sb = get_client()
    res = sb.table("usuarios").select("*").eq("username", username).execute()
    data = res.data or []
    return data[0] if data else None


def crear_usuario(payload: dict):
    sb = get_client()
    return sb.table("usuarios").insert(payload).execute()


def actualizar_usuario(usuario_id, payload: dict):
    sb = get_client()
    return sb.table("usuarios").update(payload).eq("id", usuario_id).execute()


def eliminar_usuario(usuario_id):
    sb = get_client()
    return sb.table("usuarios").delete().eq("id", usuario_id).execute()


# ---------- Compras (gastos) ----------

def listar_compras(fecha_desde=None, fecha_hasta=None, categoria=None):
    sb = get_client()
    q = sb.table("compras").select("*")
    if fecha_desde:
        q = q.gte("fecha_compra", fecha_desde)
    if fecha_hasta:
        q = q.lte("fecha_compra", fecha_hasta)
    if categoria:
        q = q.eq("categoria", categoria)
    res = q.order("fecha_compra", desc=True).execute()
    return res.data or []


def crear_compra(payload: dict):
    sb = get_client()
    return sb.table("compras").insert(payload).execute()


def actualizar_compra(compra_id, payload: dict):
    sb = get_client()
    return sb.table("compras").update(payload).eq("id", compra_id).execute()


def eliminar_compra(compra_id):
    sb = get_client()
    return sb.table("compras").delete().eq("id", compra_id).execute()


# ---------- Ventas (ingresos extraordinarios) ----------

def listar_ventas(fecha_desde=None, fecha_hasta=None, concepto=None):
    sb = get_client()
    q = sb.table("ventas").select("*")
    if fecha_desde:
        q = q.gte("fecha_venta", fecha_desde)
    if fecha_hasta:
        q = q.lte("fecha_venta", fecha_hasta)
    if concepto:
        q = q.eq("concepto", concepto)
    res = q.order("fecha_venta", desc=True).execute()
    return res.data or []


def crear_venta(payload: dict):
    sb = get_client()
    return sb.table("ventas").insert(payload).execute()


def actualizar_venta(venta_id, payload: dict):
    sb = get_client()
    return sb.table("ventas").update(payload).eq("id", venta_id).execute()


def eliminar_venta(venta_id):
    sb = get_client()
    return sb.table("ventas").delete().eq("id", venta_id).execute()


# ---------- Pendientes (tareas / to-dos de colaboradores) ----------

def listar_pendientes(estado=None, prioridad=None, asignado_a=None, apartamento_id=None):
    """Trae los pendientes con el apartamento embebido. Los nombres de 'asignado_a' y
    'creado_por' se resuelven en la app con un diccionario de usuarios (evita usar
    joins ambiguos hacia la misma tabla usuarios, que son frágiles en Postgrest)."""
    sb = get_client()
    q = sb.table("pendientes").select("*, apartamentos(codigo, piso)")
    if estado:
        q = q.eq("estado", estado)
    if prioridad:
        q = q.eq("prioridad", prioridad)
    if asignado_a:
        q = q.eq("asignado_a", asignado_a)
    if apartamento_id:
        q = q.eq("apartamento_id", apartamento_id)
    res = q.order("created_at", desc=True).execute()
    return res.data or []


def obtener_pendiente(pendiente_id):
    sb = get_client()
    res = sb.table("pendientes").select("*").eq("id", pendiente_id).single().execute()
    return res.data


def crear_pendiente(payload: dict):
    sb = get_client()
    res = sb.table("pendientes").insert(payload).execute()
    return res.data[0]


def actualizar_pendiente(pendiente_id, payload: dict):
    sb = get_client()
    return sb.table("pendientes").update(payload).eq("id", pendiente_id).execute()


def cambiar_estado_pendiente(pendiente_id, nuevo_estado: str):
    """Actualiza el estado y, si pasa a 'Terminado', registra la fecha de cierre
    (si sale de 'Terminado' hacia otro estado, limpia la fecha de cierre)."""
    payload = {"estado": nuevo_estado}
    if nuevo_estado == "Terminado":
        from datetime import datetime, timezone
        payload["fecha_completado"] = datetime.now(timezone.utc).isoformat()
    else:
        payload["fecha_completado"] = None
    sb = get_client()
    return sb.table("pendientes").update(payload).eq("id", pendiente_id).execute()


def eliminar_pendiente(pendiente_id):
    sb = get_client()
    return sb.table("pendientes").delete().eq("id", pendiente_id).execute()


# ---------- Almacenamiento de comprobantes ----------

def subir_comprobante(archivo_bytes: bytes, nombre_archivo: str, carpeta: str = "compras") -> str:
    """Sube un archivo al bucket 'comprobantes' y devuelve su URL pública."""
    import uuid
    import mimetypes

    sb = get_client()
    extension = nombre_archivo.split(".")[-1] if "." in nombre_archivo else "bin"
    path = f"{carpeta}/{uuid.uuid4().hex}.{extension}"
    content_type = mimetypes.guess_type(nombre_archivo)[0] or "application/octet-stream"
    sb.storage.from_("comprobantes").upload(path, archivo_bytes, {"content-type": content_type})
    return sb.storage.from_("comprobantes").get_public_url(path)
