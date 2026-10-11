"""
Estados de Compras, Pagos y Ventas.

  Compras y Pagos -> estado de devolución:  No aplica / Pendiente de devolución / Se realizó la devolución a la persona que realizó el pago
  Ventas          -> estado de entrega:     No aplica / Pendiente de entrega / Se realizó entrega

"No aplica" es el valor neutro (por defecto): la mayoría de los registros, y todos los que ya existían
antes de agregar este campo, no tienen devolución ni entrega pendiente.

Cuando la devolución ya se realizó, se guarda además A QUIÉN se le devolvió (columna `devolucion_a` de Compras y
Pagos). Los textos de abajo DEBEN coincidir con los de migracion_devolucion_usuario.sql (hay una prueba que lo
comprueba).
"""
ESTADO_NEUTRO = "No aplica"
REALIZADA_DEVOLUCION = "Se realizó la devolución a la persona que realizó el pago"
ESTADOS_DEVOLUCION = [ESTADO_NEUTRO, "Pendiente de devolución", REALIZADA_DEVOLUCION]
ESTADOS_ENTREGA = [ESTADO_NEUTRO, "Pendiente de entrega", "Se realizó entrega"]
PENDIENTE_DEVOLUCION = ESTADOS_DEVOLUCION[1]
PENDIENTE_ENTREGA = ESTADOS_ENTREGA[1]

# Textos que se usaron antes y que pueden seguir guardados en registros viejos (si todavía no se ejecutó la migración
# SQL): se tratan como su texto actual para que esos registros no pasen a verse como "No aplica".
TEXTOS_ANTERIORES = {"Se realizó devolución": REALIZADA_DEVOLUCION}


def normalizar(valor, opciones):
    """Un estado vacío, ausente o desconocido (p. ej. registros anteriores al campo) cuenta como 'No aplica'.
    Un texto anterior (TEXTOS_ANTERIORES) se convierte al texto actual."""
    valor = TEXTOS_ANTERIORES.get(valor, valor)
    return valor if valor in opciones else ESTADO_NEUTRO


def indice(valor, opciones):
    """Posición del estado en la lista de opciones (para preseleccionarlo al editar)."""
    return opciones.index(normalizar(valor, opciones))


def filtrar_por_estado(registros, campo_estado, filtro, opciones):
    """filtro 'Todos' deja pasar todo; si no, solo los de ese estado."""
    if filtro == "Todos":
        return list(registros)
    return [r for r in registros if normalizar(r.get(campo_estado), opciones) == filtro]


def monto_pendiente(registros, campo_estado, campo_monto, estado_pendiente):
    """Suma de los montos de los registros en el estado pendiente indicado."""
    return round(sum(float(r.get(campo_monto) or 0) for r in registros
                     if r.get(campo_estado) == estado_pendiente), 2)


# ------------------------------------------------------------------
# Quién puede MODIFICAR el estado (registrarlo distinto de "No aplica" o cambiarlo al editar).
# Los demás usuarios siguen viendo el estado, filtrando por él y registrando/editando el resto de los datos.
# ------------------------------------------------------------------
USUARIOS_CON_PERMISO_ESTADO = ("viovip",)     # nombres de usuario (sin distinguir mayúsculas)
AYUDA_SIN_PERMISO = "Solo el usuario Viovip y el Administrador pueden modificar el estado."


def puede_modificar(usuario, es_admin):
    """True para el Administrador y para los usuarios de USUARIOS_CON_PERMISO_ESTADO."""
    if es_admin:
        return True
    nombre = str((usuario or {}).get("username") or "").strip().casefold()
    return nombre in USUARIOS_CON_PERMISO_ESTADO


# ------------------------------------------------------------------
# A quién se le devolvió el dinero (solo cuando el estado es "Se realizó la devolución…")
# ------------------------------------------------------------------
SIN_INDICAR = "(sin indicar)"


def devolucion_realizada(estado):
    return normalizar(estado, ESTADOS_DEVOLUCION) == REALIZADA_DEVOLUCION


def validar_devolucion(estado, devuelto_a):
    """Error en español si el estado dice que la devolución ya se realizó pero no se indicó a quién; None si está bien."""
    if devolucion_realizada(estado) and not (devuelto_a or "").strip():
        return "Indica a qué usuario se realizó la devolución."
    return None


def devolucion_a_a_guardar(estado, devuelto_a):
    """Lo que se guarda en `devolucion_a`: el nombre solo si la devolución ya se realizó; en cualquier otro estado, vacío."""
    return (devuelto_a or "").strip() or None if devolucion_realizada(estado) else None


def texto_devolucion_a(estado, devuelto_a):
    """Texto para tablas y reportes: el nombre; '(sin indicar)' si ya se devolvió pero no se anotó a quién
    (registros anteriores a esta columna); vacío si la devolución no se ha realizado."""
    if not devolucion_realizada(estado):
        return ""
    return (devuelto_a or "").strip() or SIN_INDICAR
