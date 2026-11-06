"""
Lógica independiente para el módulo de cobros de Residencial Equise.

Este archivo NO se conecta a Supabase y NO modifica datos.
Los importes se manejan con Decimal para evitar errores de redondeo.

Conceptos admitidos: alquiler, electricidad y agua.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date
from typing import Iterable

CENTAVO = Decimal("0.01")
CONCEPTOS = ("alquiler", "electricidad", "agua")


class ErrorCobro(ValueError):
    """Error de validación de una operación de cobro."""


def dinero(valor) -> Decimal:
    """Convierte un importe a Decimal con dos decimales."""
    try:
        importe = Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise ErrorCobro(f"Importe no válido: {valor!r}")
    if not importe.is_finite():
        raise ErrorCobro("El importe debe ser un número finito.")
    return importe


def validar_concepto(concepto: str) -> str:
    concepto = str(concepto).strip().lower()
    if concepto not in CONCEPTOS:
        raise ErrorCobro(f"Concepto no admitido: {concepto!r}")
    return concepto


def calcular_saldo_periodo(monto_esperado, pagos_existentes=()) -> Decimal:
    """Devuelve saldo pendiente, sin permitir que la deuda calculada sea negativa."""
    esperado = dinero(monto_esperado)
    if esperado < 0:
        raise ErrorCobro("El monto esperado no puede ser negativo.")
    pagado = sum((dinero(p) for p in pagos_existentes), Decimal("0.00"))
    if any(dinero(p) < 0 for p in pagos_existentes):
        raise ErrorCobro("Los pagos existentes no pueden ser negativos.")
    return max(Decimal("0.00"), esperado - pagado).quantize(CENTAVO)


def _normalizar_obligaciones(obligaciones: Iterable[dict]) -> list[dict]:
    """Valida y normaliza obligaciones: id, concepto, periodo, saldo y fecha."""
    resultado = []
    ids = set()
    for item in obligaciones:
        concepto = validar_concepto(item.get("concepto"))
        periodo_id = item.get("periodo_id")
        if periodo_id is None:
            raise ErrorCobro("Cada obligación debe tener periodo_id.")
        clave = (concepto, str(periodo_id))
        if clave in ids:
            raise ErrorCobro(f"Obligación duplicada: {clave}")
        ids.add(clave)
        saldo = dinero(item.get("saldo_pendiente", 0))
        if saldo < 0:
            raise ErrorCobro("El saldo pendiente no puede ser negativo.")
        fecha = item.get("fecha_vencimiento") or item.get("fecha") or ""
        resultado.append({
            "concepto": concepto,
            "periodo_id": periodo_id,
            "saldo_pendiente": saldo,
            "fecha_vencimiento": str(fecha),
        })
    return resultado


def distribuir_cobro(monto_recibido, obligaciones, modo="manual", asignaciones=None):
    """
    Distribuye una recepción de dinero.

    modo='manual': asignaciones es una lista de
      {concepto, periodo_id, monto}
    modo='antiguedad': aplica a las obligaciones ordenadas por fecha ascendente.

    Devuelve total recibido, aplicaciones, total aplicado y saldo a favor.
    No escribe en base de datos.
    """
    recibido = dinero(monto_recibido)
    if recibido <= 0:
        raise ErrorCobro("El monto recibido debe ser mayor que cero.")

    obligaciones = _normalizar_obligaciones(obligaciones)
    indice = {(o["concepto"], str(o["periodo_id"])): o for o in obligaciones}
    aplicaciones = []
    usados = {}

    if modo == "manual":
        if asignaciones is None:
            raise ErrorCobro("Debe indicar las asignaciones para el modo manual.")
        for a in asignaciones:
            concepto = validar_concepto(a.get("concepto"))
            periodo_id = a.get("periodo_id")
            clave = (concepto, str(periodo_id))
            if clave not in indice:
                raise ErrorCobro(f"La obligación seleccionada no existe: {clave}")
            importe = dinero(a.get("monto"))
            if importe <= 0:
                raise ErrorCobro("Cada aplicación debe ser mayor que cero.")
            usados[clave] = usados.get(clave, Decimal("0.00")) + importe
            if usados[clave] > indice[clave]["saldo_pendiente"]:
                raise ErrorCobro(
                    f"La aplicación supera el saldo pendiente de {concepto}, período {periodo_id}."
                )
            aplicaciones.append({
                "concepto": concepto,
                "periodo_id": periodo_id,
                "monto": importe,
            })
    elif modo == "antiguedad":
        if asignaciones:
            raise ErrorCobro("No envíe asignaciones manuales en modo antigüedad.")
        ordenadas = sorted(obligaciones, key=lambda o: (o["fecha_vencimiento"], CONCEPTOS.index(o["concepto"]), str(o["periodo_id"])))
        disponible = recibido
        for o in ordenadas:
            if disponible <= 0:
                break
            aplicar = min(disponible, o["saldo_pendiente"])
            if aplicar > 0:
                aplicaciones.append({
                    "concepto": o["concepto"],
                    "periodo_id": o["periodo_id"],
                    "monto": aplicar,
                })
                disponible -= aplicar
    else:
        raise ErrorCobro("El modo debe ser 'manual' o 'antiguedad'.")

    total_aplicado = sum((a["monto"] for a in aplicaciones), Decimal("0.00"))
    if total_aplicado > recibido:
        raise ErrorCobro("La suma aplicada no puede superar el dinero recibido.")
    credito = (recibido - total_aplicado).quantize(CENTAVO)
    return {
        "monto_recibido": recibido,
        "aplicaciones": aplicaciones,
        "total_aplicado": total_aplicado.quantize(CENTAVO),
        "saldo_a_favor_generado": credito,
    }


def aplicar_saldo_favor(saldo_disponible, concepto_destino, periodo_id,
                        saldo_periodo, monto_solicitado=None, confirmado=False):
    """
    Aplica crédito existente a cualquier concepto (previa confirmación).
    No genera ingreso de caja. Devuelve importe aplicado y crédito restante.
    """
    credito = dinero(saldo_disponible)
    pendiente = dinero(saldo_periodo)
    concepto = validar_concepto(concepto_destino)
    if credito < 0 or pendiente < 0:
        raise ErrorCobro("El crédito y el saldo pendiente no pueden ser negativos.")
    if periodo_id is None:
        raise ErrorCobro("Debe indicar el período de destino.")
    if not confirmado:
        return {
            "requiere_confirmacion": True,
            "concepto": concepto,
            "periodo_id": periodo_id,
            "monto_aplicado": Decimal("0.00"),
            "saldo_favor_restante": credito,
            "saldo_periodo_restante": pendiente,
            "genera_ingreso": False,
        }
    if monto_solicitado is None:
        aplicar = min(credito, pendiente)
    else:
        aplicar = dinero(monto_solicitado)
    if aplicar <= 0:
        raise ErrorCobro("El importe a aplicar debe ser mayor que cero.")
    if aplicar > credito:
        raise ErrorCobro("No existe suficiente saldo a favor.")
    if aplicar > pendiente:
        raise ErrorCobro("La aplicación supera el saldo pendiente del período.")
    return {
        "requiere_confirmacion": False,
        "concepto": concepto,
        "periodo_id": periodo_id,
        "monto_aplicado": aplicar,
        "saldo_favor_restante": (credito - aplicar).quantize(CENTAVO),
        "saldo_periodo_restante": (pendiente - aplicar).quantize(CENTAVO),
        "genera_ingreso": False,
    }


def resumir_operacion(monto_recibido, resultado_distribucion, forma_pago):
    """Construye resumen validado de una operación; una sola forma de pago."""
    recibido = dinero(monto_recibido)
    if recibido <= 0:
        raise ErrorCobro("El monto recibido debe ser mayor que cero.")
    forma = str(forma_pago or "").strip().lower()
    if forma not in {"efectivo", "qr", "transferencia", "deposito", "depósito"}:
        raise ErrorCobro("Forma de pago no reconocida.")
    if dinero(resultado_distribucion["monto_recibido"]) != recibido:
        raise ErrorCobro("El monto recibido no coincide con la distribución.")
    return {
        "monto_recibido": recibido,
        "forma_pago": forma,
        "total_aplicado": dinero(resultado_distribucion["total_aplicado"]),
        "saldo_a_favor_generado": dinero(resultado_distribucion["saldo_a_favor_generado"]),
        "aplicaciones": resultado_distribucion["aplicaciones"],
    }
