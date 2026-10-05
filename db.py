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

_ORDEN_PISO_CODIGO = {"PB": 0, "PP": 1, "SP": 2, "TP": 3}
_MESES_ORDEN = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
                "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def clave_orden_apartamento(codigo):
    """Orden natural de códigos: PB (planta baja), PP (primer piso), SP (segundo piso),
    TP (tercer piso), y dentro de cada uno por número (PB-1, PB-2, ... PB-10)."""
    import re
    texto = (codigo or "").strip().upper()
    m = re.match(r"^([A-Z]+)[\s\-_]*(\d+)", texto)
    if m:
        return (_ORDEN_PISO_CODIGO.get(m.group(1), 99), m.group(1), int(m.group(2)), texto)
    return (99, texto, 0, texto)


def _ordenar_periodos(periodos):
    """Más reciente primero (año, mes) y, dentro de cada mes, apartamentos en orden PB, PP, SP, TP."""
    def clave(p):
        mes_idx = _MESES_ORDEN.index(p["mes"]) if p.get("mes") in _MESES_ORDEN else 0
        codigo = (p.get("apartamentos") or {}).get("codigo")
        return (-int(p.get("anio") or 0), -mes_idx, clave_orden_apartamento(codigo))
    return sorted(periodos, key=clave)


def listar_apartamentos():
    sb = get_client()
    res = sb.table("apartamentos").select("*").execute()
    return sorted(res.data or [], key=lambda a: clave_orden_apartamento(a.get("codigo")))


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


# ---------- Historial de inquilinos (salida de un inquilino / ingreso de otro) ----------

def deuda_activa_apartamento(apartamento_id):
    """Deuda pendiente del inquilino actual (solo periodos abiertos): alquiler, electricidad y agua."""
    sb = get_client()
    deudas = {}
    for clave, tabla, tabla_pagos in [
        ("alquiler", "periodos_alquiler", "pagos"),
        ("electricidad", "periodos_electricidad", "pagos_electricidad"),
        ("agua", "periodos_agua", "pagos_agua"),
    ]:
        res = (
            sb.table(tabla)
            .select(f"monto_esperado, {tabla_pagos}(monto)")
            .eq("apartamento_id", apartamento_id)
            .is_("inquilino_historial_id", "null")
            .execute()
        )
        total = 0.0
        for p in res.data or []:
            pagado = sum(float(x["monto"]) for x in (p.get(tabla_pagos) or []))
            total += max(0.0, float(p.get("monto_esperado") or 0) - pagado)
        deudas[clave] = round(total, 2)
    return deudas


def registrar_salida_inquilino(apartamento_id, fecha_salida, observacion, registrado_por):
    """Archiva la ficha del inquilino, cierra sus periodos (su deuda queda a su nombre) y deja
    el apartamento libre. Todo se hace en una sola operación en la base de datos (todo o nada)."""
    sb = get_client()
    res = sb.rpc("registrar_salida_inquilino", {
        "p_apartamento_id": apartamento_id,
        "p_fecha_salida": str(fecha_salida),
        "p_observacion": observacion or None,
        "p_registrado_por": registrado_por,
    }).execute()
    return res.data


def listar_inquilinos_historial(apartamento_id=None):
    sb = get_client()
    q = sb.table("inquilinos_historial").select("*")
    if apartamento_id:
        q = q.eq("apartamento_id", apartamento_id)
    res = q.order("fecha_salida", desc=True).order("id", desc=True).execute()
    return res.data or []


def deuda_actual_por_inquilino_historial():
    """Deuda que todavía tiene cada inquilino que salió (según sus periodos cerrados):
    {historial_id: {"alquiler": x, "electricidad": y, "agua": z}}"""
    sb = get_client()
    resultado = {}
    for clave, tabla, tabla_pagos in [
        ("alquiler", "periodos_alquiler", "pagos"),
        ("electricidad", "periodos_electricidad", "pagos_electricidad"),
        ("agua", "periodos_agua", "pagos_agua"),
    ]:
        res = (
            sb.table(tabla)
            .select(f"inquilino_historial_id, monto_esperado, {tabla_pagos}(monto)")
            .gt("inquilino_historial_id", 0)
            .execute()
        )
        for p in res.data or []:
            hid = p["inquilino_historial_id"]
            pagado = sum(float(x["monto"]) for x in (p.get(tabla_pagos) or []))
            deuda = max(0.0, float(p.get("monto_esperado") or 0) - pagado)
            d = resultado.setdefault(hid, {"alquiler": 0.0, "electricidad": 0.0, "agua": 0.0})
            d[clave] = round(d[clave] + deuda, 2)
    return resultado


# ---------- Periodos de alquiler (un registro por apartamento + mes/año) ----------

def listar_periodos(apartamento_id=None, anio=None, mes=None, solo_activos=False):
    """Trae los periodos junto con el apartamento y todos sus pagos (abonos) asociados.
    solo_activos=True excluye los periodos cerrados de inquilinos que ya salieron."""
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
    if solo_activos:
        q = q.is_("inquilino_historial_id", "null")
    res = q.order("anio", desc=True).execute()
    return _ordenar_periodos(res.data or [])


def obtener_periodo(apartamento_id, mes, anio):
    sb = get_client()
    res = (
        sb.table("periodos_alquiler")
        .select("*, pagos(id, fecha, monto, metodo_pago, observacion)")
        .eq("apartamento_id", apartamento_id)
        .eq("mes", mes)
        .eq("anio", anio)
        .is_("inquilino_historial_id", "null")
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


def obtener_o_crear_periodo(apartamento_id, mes, anio, monto_esperado, inquilino_nombre=None):
    """Devuelve el periodo (abierto) existente para ese apartamento/mes/año, o lo crea si no existe.
    El periodo guarda el nombre del inquilino de ese momento."""
    periodo = obtener_periodo(apartamento_id, mes, anio)
    if periodo:
        return periodo
    nuevo = crear_periodo({
        "apartamento_id": apartamento_id,
        "mes": mes,
        "anio": anio,
        "monto_esperado": monto_esperado,
        "inquilino_nombre": inquilino_nombre,
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

def listar_periodos_electricidad(apartamento_id=None, anio=None, mes=None, solo_activos=False):
    """solo_activos=True excluye los periodos cerrados de inquilinos que ya salieron."""
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
    if solo_activos:
        q = q.is_("inquilino_historial_id", "null")
    res = q.order("anio", desc=True).execute()
    return _ordenar_periodos(res.data or [])


def obtener_periodo_electricidad(apartamento_id, mes, anio):
    sb = get_client()
    res = (
        sb.table("periodos_electricidad")
        .select("*, pagos_electricidad(id, fecha, monto, metodo_pago, observacion)")
        .eq("apartamento_id", apartamento_id)
        .eq("mes", mes)
        .eq("anio", anio)
        .is_("inquilino_historial_id", "null")
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
    return _ordenar_periodos(res.data or [])


def obtener_periodo_agua(apartamento_id, mes, anio):
    sb = get_client()
    res = (
        sb.table("periodos_agua")
        .select("*, pagos_agua(id, fecha, monto, metodo_pago, observacion)")
        .eq("apartamento_id", apartamento_id)
        .eq("mes", mes)
        .eq("anio", anio)
        .is_("inquilino_historial_id", "null")
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


# ---------- Reportes por usuario (cobrador) ----------

def listar_pagos_alquiler_rango(fecha_desde, fecha_hasta):
    """Abonos de alquiler en un rango de fechas (tabla plana, sin embeds anidados;
    el periodo/apartamento se cruza en la app con listar_todos_periodos_alquiler_basico)."""
    sb = get_client()
    res = (
        sb.table("pagos").select("*")
        .gte("fecha", str(fecha_desde)).lte("fecha", str(fecha_hasta))
        .order("fecha").execute()
    )
    return res.data or []


def listar_pagos_electricidad_rango(fecha_desde, fecha_hasta):
    sb = get_client()
    res = (
        sb.table("pagos_electricidad").select("*")
        .gte("fecha", str(fecha_desde)).lte("fecha", str(fecha_hasta))
        .order("fecha").execute()
    )
    return res.data or []


def listar_todos_periodos_alquiler_basico():
    """Solo id/apartamento/mes/año de cada periodo de alquiler (tabla chica), para cruzar
    en la app con los pagos y armar los reportes sin usar embeds anidados."""
    sb = get_client()
    res = sb.table("periodos_alquiler").select("id, apartamento_id, mes, anio").execute()
    return res.data or []


def listar_todos_periodos_electricidad_basico():
    sb = get_client()
    res = sb.table("periodos_electricidad").select("id, apartamento_id, mes, anio").execute()
    return res.data or []


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


# ---------- Pagos generales (tercera opción de Movimientos, sin comprobante) ----------

def listar_pagos_generales(fecha_desde=None, fecha_hasta=None, categoria=None):
    sb = get_client()
    q = sb.table("pagos_generales").select("*")
    if fecha_desde:
        q = q.gte("fecha_pago", fecha_desde)
    if fecha_hasta:
        q = q.lte("fecha_pago", fecha_hasta)
    if categoria:
        q = q.eq("categoria", categoria)
    res = q.order("fecha_pago", desc=True).execute()
    return res.data or []


def crear_pago_general(payload: dict):
    sb = get_client()
    return sb.table("pagos_generales").insert(payload).execute()


def actualizar_pago_general(pago_id, payload: dict):
    sb = get_client()
    return sb.table("pagos_generales").update(payload).eq("id", pago_id).execute()


def eliminar_pago_general(pago_id):
    sb = get_client()
    return sb.table("pagos_generales").delete().eq("id", pago_id).execute()


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


# ---------- Servicios Básicos (dentro del módulo de Pendientes) ----------

def listar_servicios_basicos():
    sb = get_client()
    res = sb.table("servicios_basicos").select("*").order("nombre_servicio").execute()
    return res.data or []


def crear_servicio_basico(payload: dict):
    sb = get_client()
    return sb.table("servicios_basicos").insert(payload).execute()


def actualizar_servicio_basico(servicio_id, payload: dict):
    sb = get_client()
    return sb.table("servicios_basicos").update(payload).eq("id", servicio_id).execute()


def eliminar_servicio_basico(servicio_id):
    sb = get_client()
    return sb.table("servicios_basicos").delete().eq("id", servicio_id).execute()


# ---------- Reuniones (área administrativa) ----------

def listar_reuniones(fecha_desde=None, fecha_hasta=None):
    """Trae las reuniones (sin embeds anidados, que son frágiles en Postgrest).
    Los participantes se resuelven aparte con listar_participantes_reuniones()."""
    sb = get_client()
    q = sb.table("reuniones").select("*")
    if fecha_desde:
        q = q.gte("fecha", fecha_desde)
    if fecha_hasta:
        q = q.lte("fecha", fecha_hasta)
    res = q.order("fecha", desc=True).execute()
    return res.data or []


def listar_participantes_reuniones():
    """Trae todas las filas de reuniones_participantes (tabla chica) para mapear
    en la app qué usuarios participaron en cada reunión."""
    sb = get_client()
    res = sb.table("reuniones_participantes").select("reunion_id, usuario_id").execute()
    return res.data or []


def crear_reunion(payload: dict, participantes_ids=None):
    """Crea la reunión y, si se pasan ids de usuarios, los vincula como participantes."""
    sb = get_client()
    res = sb.table("reuniones").insert(payload).execute()
    reunion = res.data[0]
    if participantes_ids:
        filas = [{"reunion_id": reunion["id"], "usuario_id": uid} for uid in participantes_ids]
        sb.table("reuniones_participantes").insert(filas).execute()
    return reunion


def actualizar_reunion(reunion_id, payload: dict, participantes_ids=None):
    """Actualiza los datos de la reunión y sincroniza la lista de participantes
    (borra los anteriores y registra los nuevos)."""
    sb = get_client()
    sb.table("reuniones").update(payload).eq("id", reunion_id).execute()
    sb.table("reuniones_participantes").delete().eq("reunion_id", reunion_id).execute()
    if participantes_ids:
        filas = [{"reunion_id": reunion_id, "usuario_id": uid} for uid in participantes_ids]
        sb.table("reuniones_participantes").insert(filas).execute()
    return True


def eliminar_reunion(reunion_id):
    sb = get_client()
    return sb.table("reuniones").delete().eq("id", reunion_id).execute()


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


# ---------- Moras (Dashboard): periodos abiertos con sus abonos ----------

_TABLAS_MORA = {
    "alquiler": ("periodos_alquiler", "pagos"),
    "electricidad": ("periodos_electricidad", "pagos_electricidad"),
    "agua": ("periodos_agua", "pagos_agua"),
}


def listar_periodos_abiertos(tipo):
    """Todos los periodos del inquilino ACTUAL (sin los cerrados de inquilinos que ya salieron),
    con solo las columnas necesarias para calcular deuda. tipo: 'alquiler' | 'electricidad' | 'agua'.
    PostgREST corta en 1000 filas por consulta sin avisar; aquí se pide por páginas hasta traer
    todo, para que ninguna deuda quede fuera del cálculo."""
    tabla, tabla_pagos = _TABLAS_MORA[tipo]
    sb = get_client()
    filas, inicio, tam = [], 0, 1000
    while True:
        res = (
            sb.table(tabla)
            .select(f"id, apartamento_id, mes, anio, monto_esperado, {tabla_pagos}(monto, fecha)")
            .is_("inquilino_historial_id", "null")
            .order("id")
            .range(inicio, inicio + tam - 1)
            .execute()
        )
        datos = res.data or []
        filas.extend(datos)
        if len(datos) < tam:
            return filas
        inicio += tam


# ---------- Reporte de actividad por usuario ----------

_TABLAS_ACTIVIDAD = {
    "pagos_generales": "fecha_pago",
    "compras": "fecha_compra",
    "ventas": "fecha_venta",
}


def listar_actividad_rango(tabla, fecha_desde, fecha_hasta):
    """Todos los registros de 'pagos_generales', 'compras' o 'ventas' entre dos fechas (ambas
    inclusive). PostgREST corta en 1000 filas por consulta sin avisar; aquí se pide por páginas
    hasta traer todo, para que un reporte de varios meses nunca quede incompleto."""
    campo_fecha = _TABLAS_ACTIVIDAD[tabla]
    sb = get_client()
    filas, inicio, tam = [], 0, 1000
    while True:
        res = (
            sb.table(tabla).select("*")
            .gte(campo_fecha, str(fecha_desde)).lte(campo_fecha, str(fecha_hasta))
            .order(campo_fecha).order("id")
            .range(inicio, inicio + tam - 1)
            .execute()
        )
        datos = res.data or []
        filas.extend(datos)
        if len(datos) < tam:
            return filas
        inicio += tam


# ---------- Compromisos de pago ----------

def listar_compromisos(apartamento_id=None, estado=None):
    """Historial de compromisos (más recientes primero) con el apartamento embebido.
    Se pide por páginas: PostgREST corta en 1000 filas por consulta sin avisar."""
    sb = get_client()
    filas, inicio, tam = [], 0, 1000
    while True:
        q = sb.table("compromisos_pago").select("*, apartamentos(codigo, piso)")
        if apartamento_id is not None:
            q = q.eq("apartamento_id", apartamento_id)
        if estado:
            q = q.eq("estado", estado)
        res = (q.order("fecha_registro", desc=True).order("id", desc=True)
                .range(inicio, inicio + tam - 1).execute())
        datos = res.data or []
        filas.extend(datos)
        if len(datos) < tam:
            return filas
        inicio += tam


def crear_compromiso(payload: dict):
    sb = get_client()
    res = sb.table("compromisos_pago").insert(payload).execute()
    return res.data[0]


def actualizar_compromiso(compromiso_id, payload: dict):
    sb = get_client()
    return sb.table("compromisos_pago").update(payload).eq("id", compromiso_id).execute()


def eliminar_compromiso(compromiso_id):
    sb = get_client()
    return sb.table("compromisos_pago").delete().eq("id", compromiso_id).execute()


# ---------- Estados de Compras / Pagos / Ventas ----------

def columna_disponible(tabla, columna):
    """True si la columna existe en la tabla. Sirve para que la app siga funcionando si todavía no se
    ejecutó la migración SQL que la crea. Solo un error de 'columna inexistente' da False: un fallo de
    red u otro error se vuelve a lanzar (no se debe ocultar un problema real como si faltara la migración)."""
    sb = get_client()
    try:
        sb.table(tabla).select(columna).limit(1).execute()
        return True
    except Exception as e:
        texto = str(e).lower()
        if "42703" in texto or "pgrst204" in texto or "does not exist" in texto or "could not find" in texto:
            return False
        raise
