"""Lógica pura para cuentas por cobrar de Residencial Equise.

No realiza conexiones ni escrituras en Supabase. Se registran desembolsos,
cargos y cobros por separado para conservar trazabilidad.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

CATEGORIAS_COBRO = (
    "Prestamo a colaborador",
    "Prestamo a persona externa",
)


def _dinero(valor, campo="monto"):
    try:
        n = Decimal(str(valor if valor is not None else 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{campo} debe ser un importe numérico.")
    if not n.is_finite() or n < 0:
        raise ValueError(f"{campo} no puede ser negativo ni inválido.")
    return n


def validar_cuenta(datos):
    d = dict(datos or {})
    if not str(d.get("deudor") or "").strip():
        raise ValueError("Debes indicar el deudor.")
    if d.get("categoria") not in CATEGORIAS_COBRO:
        raise ValueError("La categoría de cuenta por cobrar no es válida.")
    if not d.get("fecha_origen"):
        raise ValueError("Debes indicar la fecha de origen.")
    monto = _dinero(d.get("monto_original"), "monto_original")
    if monto <= 0:
        raise ValueError("El monto original debe ser mayor a cero.")
    if d.get("fecha_vencimiento") and str(d["fecha_vencimiento"]) < str(d["fecha_origen"]):
        raise ValueError("El vencimiento no puede ser anterior al origen.")
    return d


def calcular_saldo(cuenta, movimientos):
    """Saldo = saldo de apertura + nuevos cargos/desembolsos - cobros."""
    apertura = _dinero(cuenta.get("saldo_apertura", cuenta.get("monto_original", 0)), "saldo_apertura")
    cargos = Decimal("0.00")
    cobros = Decimal("0.00")
    for m in movimientos or []:
        tipo = m.get("tipo")
        monto = _dinero(m.get("monto"), "monto movimiento")
        if tipo in ("nuevo_desembolso", "cargo_adicional", "ajuste_incremento"):
            cargos += monto
        elif tipo in ("cobro", "ajuste_reduccion"):
            cobros += monto
        else:
            raise ValueError(f"Tipo de movimiento no válido para cuenta por cobrar: {tipo}")
    saldo = apertura + cargos - cobros
    if saldo < 0:
        raise ValueError("Los cobros o reducciones superan el saldo por cobrar.")
    return saldo.quantize(Decimal("0.01"))


def estado_cuenta(saldo, fecha_vencimiento=None, hoy=None):
    saldo = _dinero(saldo)
    if saldo == 0:
        return "Cancelada"
    hoy = hoy or date.today()
    if fecha_vencimiento and date.fromisoformat(str(fecha_vencimiento)[:10]) < hoy:
        return "Vencida"
    return "Vigente"


def resumir_cuentas(cuentas, movimientos_por_cuenta=None):
    movimientos_por_cuenta = movimientos_por_cuenta or {}
    filas = []
    total = Decimal("0.00")
    for c in cuentas or []:
        cid = c.get("id")
        saldo = calcular_saldo(c, movimientos_por_cuenta.get(cid, []))
        total += saldo
        filas.append({**c, "saldo_por_cobrar": saldo,
                      "estado_calculado": estado_cuenta(saldo, c.get("fecha_vencimiento"))})
    return {"cuentas": filas, "total_por_cobrar": total.quantize(Decimal("0.01"))}
