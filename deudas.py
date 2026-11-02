"""Lógica pura para cuentas por pagar de Residencial Equise.

No realiza conexiones ni escrituras en Supabase. Los movimientos deben ser
persistidos por la capa db.py después de validar permisos y datos.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

CATEGORIAS_DEUDA = (
    "Prestamo de colaborador",
    "Prestamo de persona externa",
)
ESTADOS = ("Vigente", "Vencida", "Cancelada", "Reestructurada")


def _dinero(valor, campo="monto"):
    try:
        n = Decimal(str(valor if valor is not None else 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{campo} debe ser un importe numérico.")
    if not n.is_finite() or n < 0:
        raise ValueError(f"{campo} no puede ser negativo ni inválido.")
    return n


def validar_obligacion(datos):
    """Valida cabecera de obligación. monto_original > 0."""
    d = dict(datos or {})
    if not str(d.get("acreedor") or "").strip():
        raise ValueError("Debes indicar el acreedor.")
    if d.get("categoria") not in CATEGORIAS_DEUDA:
        raise ValueError("La categoría de obligación no es válida.")
    if not d.get("fecha_origen"):
        raise ValueError("Debes indicar la fecha de origen.")
    _dinero(d.get("monto_original"), "monto_original")
    if _dinero(d.get("monto_original")) <= 0:
        raise ValueError("El monto original debe ser mayor a cero.")
    if d.get("fecha_vencimiento") and str(d["fecha_vencimiento"]) < str(d["fecha_origen"]):
        raise ValueError("El vencimiento no puede ser anterior al origen.")
    return d


def calcular_saldo(obligacion, movimientos):
    """Saldo = saldo de apertura + cargos posteriores - pagos de capital.

    Para préstamos recibidos, el saldo de apertura es el capital pendiente a
    la fecha de corte. Los movimientos posteriores solo incluyen desembolsos
    adicionales formalizados y pagos de capital; intereses están fuera del
    alcance V11 inicial.
    """
    apertura = _dinero(obligacion.get("saldo_apertura", obligacion.get("monto_original", 0)), "saldo_apertura")
    cargos = Decimal("0.00")
    pagos = Decimal("0.00")
    for m in movimientos or []:
        tipo = m.get("tipo")
        monto = _dinero(m.get("monto"), "monto movimiento")
        if tipo in ("desembolso_adicional", "ajuste_incremento"):
            cargos += monto
        elif tipo in ("pago_capital", "ajuste_reduccion"):
            pagos += monto
        else:
            raise ValueError(f"Tipo de movimiento no válido para obligación: {tipo}")
    saldo = apertura + cargos - pagos
    if saldo < 0:
        raise ValueError("Los pagos o reducciones superan el saldo adeudado.")
    return saldo.quantize(Decimal("0.01"))


def estado_obligacion(saldo, fecha_vencimiento=None, hoy=None):
    saldo = _dinero(saldo)
    if saldo == 0:
        return "Cancelada"
    hoy = hoy or date.today()
    if fecha_vencimiento and date.fromisoformat(str(fecha_vencimiento)[:10]) < hoy:
        return "Vencida"
    return "Vigente"


def resumir_obligaciones(obligaciones, movimientos_por_obligacion=None):
    movimientos_por_obligacion = movimientos_por_obligacion or {}
    filas = []
    total = Decimal("0.00")
    for o in obligaciones or []:
        oid = o.get("id")
        saldo = calcular_saldo(o, movimientos_por_obligacion.get(oid, []))
        total += saldo
        filas.append({**o, "saldo_pendiente": saldo,
                      "estado_calculado": estado_obligacion(saldo, o.get("fecha_vencimiento"))})
    return {"obligaciones": filas, "total_pendiente": total.quantize(Decimal("0.01"))}
