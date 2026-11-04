"""
Acceso de cada usuario a ciertos apartamentos.

Modelo (explícito, para que nunca haya ambigüedad):
  * usuarios.acceso_todos_apartamentos (boolean, por defecto verdadero): "Todos los apartamentos" o "Solo los asignados".
  * usuarios_apartamentos (usuario_id, apartamento_id): los apartamentos asignados a cada usuario.
  * El Administrador siempre ve todo.
  * Un usuario restringido SIN asignaciones no ve ningún apartamento (acceso cerrado por defecto, a propósito).
  * Si la migración SQL todavía no se ejecutó, no hay restricciones (funciona como antes).

IMPORTANTE: esto filtra lo que MUESTRA la aplicación; no es seguridad a nivel de base de datos (las tablas siguen
accesibles con la clave de Supabase), igual que los roles actuales.

Módulo sin dependencias de Streamlit ni de la base.
"""


def construir_accesos(usuarios, asignaciones):
    """{usuario_id: {"todos": bool, "ids": set(apartamento_id)}} a partir de las filas de `usuarios` y de
    `usuarios_apartamentos`. Un usuario sin el dato (o con valor vacío) cuenta como "todos" (valor por defecto)."""
    ids_por_usuario = {}
    for fila in asignaciones or []:
        ids_por_usuario.setdefault(fila["usuario_id"], set()).add(fila["apartamento_id"])
    accesos = {}
    for u in usuarios or []:
        valor = u.get("acceso_todos_apartamentos")
        accesos[u["id"]] = {"todos": True if valor is None else bool(valor), "ids": ids_por_usuario.get(u["id"], set())}
    return accesos


def resolver(es_admin, usuario_id, accesos, funcion_disponible=True):
    """None = sin restricción (ve todos los apartamentos); si no, el conjunto de ids de apartamentos permitidos."""
    if es_admin or usuario_id is None or not funcion_disponible:
        return None
    cfg = (accesos or {}).get(usuario_id)
    if cfg is None or cfg["todos"]:
        return None
    return set(cfg["ids"])


def filtrar(registros, permitidos, campo="apartamento_id", permitir_vacio=False):
    """Deja solo los registros de los apartamentos permitidos. permitidos=None -> no filtra.
    permitir_vacio=True conserva también los que no tienen apartamento (p. ej. un pendiente «General»)."""
    if permitidos is None:
        return list(registros)
    salida = []
    for r in registros:
        valor = r.get(campo)
        if valor is None:
            if permitir_vacio:
                salida.append(r)
        elif valor in permitidos:
            salida.append(r)
    return salida


def resumen(cfg, total_apartamentos, es_admin=False):
    """Texto corto para tablas: 'Todos', '3 de 20' o 'Ninguno'."""
    if es_admin:
        return "Todos (administrador)"
    if cfg is None or cfg["todos"]:
        return "Todos"
    n = len(cfg["ids"])
    return "Ninguno" if n == 0 else f"{n} de {total_apartamentos}"
