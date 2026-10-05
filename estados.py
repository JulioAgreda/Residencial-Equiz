"""
Estados de Compras, Pagos y Ventas.

  Compras y Pagos -> estado de devolución:  No aplica / Pendiente de devolución / Se realizó devolución
  Ventas          -> estado de entrega:     No aplica / Pendiente de entrega / Se realizó entrega

"No aplica" es el valor neutro (por defecto): la mayoría de los registros, y todos los que ya existían
antes de agregar este campo, no tienen devolución ni entrega pendiente.

Los textos de abajo DEBEN coincidir con los de migracion_estados_movimientos.sql (hay una prueba que lo
comprueba).
"""
ESTADO_NEUTRO = "No aplica"
ESTADOS_DEVOLUCION = [ESTADO_NEUTRO, "Pendiente de devolución", "Se realizó devolución"]
ESTADOS_ENTREGA = [ESTADO_NEUTRO, "Pendiente de entrega", "Se realizó entrega"]
PENDIENTE_DEVOLUCION = ESTADOS_DEVOLUCION[1]
PENDIENTE_ENTREGA = ESTADOS_ENTREGA[1]


def normalizar(valor, opciones):
    """Un estado vacío, ausente o desconocido (p. ej. registros anteriores al campo) cuenta como 'No aplica'."""
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
