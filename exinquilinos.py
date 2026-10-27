"""
Ex inquilinos: cuando un inquilino se va, su ficha queda archivada en el historial (tabla `inquilinos_historial`) y sus
periodos de alquiler, luz y agua quedan CERRADOS a su nombre (columna `inquilino_historial_id`), con la deuda que tenía.
Si más adelante paga, se le registra el abono en uno de esos periodos y la deuda se actualiza.

Este módulo reúne las reglas, sin depender de Streamlit ni de la base, para poder probarlas aisladas:
  * resumen de la deuda al momento de la salida (incluye los meses sin ningún registro, que de otro modo se perderían);
  * agrupar los periodos cerrados por ex inquilino y calcular lo que cada uno debe;
  * validar un abono de un ex inquilino.

Los periodos llegan como los devuelve la base, con sus abonos embebidos: 'pagos' (alquiler), 'pagos_electricidad' y
'pagos_agua', cada abono con 'monto' y 'fecha'.
"""
from datetime import date
from decimal import Decimal

import moras

TOLERANCIA = 0.009

# (nombre que se muestra, tipo de servicio en la base, campo con los abonos embebidos, clave corta)
CONCEPTOS = (("Alquiler", "alquiler", "pagos", "alquiler"),
             ("Luz", "electricidad", "pagos_electricidad", "luz"),
             ("Agua", "agua", "pagos_agua", "agua"))


def _d(valor):
    try:
        return Decimal(str(round(float(valor or 0), 2)))
    except (TypeError, ValueError):
        return Decimal(0)


def _f(decimal):
    return float(round(decimal, 2))


def pagado(periodo, campo_pagos):
    """Suma de los abonos de un periodo (Decimal)."""
    return sum((_d(a.get("monto")) for a in (periodo.get(campo_pagos) or [])), Decimal(0))


def saldo(periodo, campo_pagos):
    """Lo que falta pagar de un periodo, nunca negativo (float)."""
    return _f(max(_d(periodo.get("monto_esperado")) - pagado(periodo, campo_pagos), Decimal(0)))


def nombre_ex_inquilino(historial):
    return (historial.get("inquilino_nombre") or historial.get("nombre") or "—")


def etiqueta_periodo(periodo):
    """'Octubre 2026' (o '—' si el mes del periodo no se puede leer)."""
    clave = moras._clave_periodo(periodo)
    return f"{moras.MESES[clave[1] - 1]} {clave[0]}" if clave else "—"


# ============================================================
# Periodos cerrados de los ex inquilinos
# ============================================================

def agrupar_por_historial(cerrados):
    """cerrados: {'alquiler': [periodos], 'electricidad': [...], 'agua': [...]} (periodos cerrados, cada uno con
    'inquilino_historial_id') -> {historial_id: {'alquiler': [...], 'electricidad': [...], 'agua': [...]}}"""
    salida = {}
    for _nombre, tipo, _campo, _clave in CONCEPTOS:
        for p in (cerrados or {}).get(tipo) or []:
            hid = p.get("inquilino_historial_id")
            if hid:
                salida.setdefault(hid, {"alquiler": [], "electricidad": [], "agua": []})[tipo].append(p)
    return salida


def deuda_ex_inquilino(periodos_por_tipo):
    """Lo que todavía debe un ex inquilino, por concepto: {'alquiler': x, 'luz': y, 'agua': z, 'total': t}.
    Cada periodo cuenta por separado (un pago de más en un mes no baja la deuda de otro)."""
    d = {clave: Decimal(0) for _n, _t, _c, clave in CONCEPTOS}
    for _nombre, tipo, campo, clave in CONCEPTOS:
        for p in (periodos_por_tipo or {}).get(tipo) or []:
            d[clave] += _d(saldo(p, campo))
    total = sum(d.values(), Decimal(0))
    return {**{k: _f(v) for k, v in d.items()}, "total": _f(total)}


# ============================================================
# Salida de un inquilino
# ============================================================

def meses_sin_registro(apt, periodos_alquiler, fecha_salida):
    """Meses de alquiler vencidos a la fecha de salida que NO tienen ningún registro de pago (el mismo cálculo del estado
    de cuenta: se completan con el alquiler de la ficha). Al archivar al inquilino se registran como deuda a su nombre;
    si no, esa deuda desaparecería. Lista de {'mes', 'anio', 'etiqueta', 'monto'}."""
    d = moras.deuda_real_inquilino(apt, periodos_alquiler, [], fecha_salida)
    if not d["aplica"]:
        return []
    meses = []
    for fila in d["alquiler"]["filas"]:
        if fila["estado"] == moras.ESTADO_SIN_PAGO:
            nombre_mes, _, anio = fila["periodo"].rpartition(" ")
            meses.append({"mes": nombre_mes, "anio": int(anio), "etiqueta": fila["periodo"], "monto": fila["esperado"]})
    return meses


def resumen_salida(apt, periodos_alquiler, periodos_electricidad, periodos_agua, fecha_salida, incluir_meses_sin_registro=True):
    """Deuda con la que el inquilino sale (a la fecha de salida), para mostrarla antes de confirmar.
    Devuelve {'alquiler', 'luz', 'agua', 'total', 'meses_sin_registro': [...]}. La deuda de alquiler incluye los meses
    sin registro solo si se van a registrar (incluir_meses_sin_registro)."""
    deuda = deuda_ex_inquilino({"alquiler": periodos_alquiler, "electricidad": periodos_electricidad, "agua": periodos_agua})
    sin_registro = meses_sin_registro(apt, periodos_alquiler, fecha_salida)
    if incluir_meses_sin_registro:
        extra = sum((_d(m["monto"]) for m in sin_registro), Decimal(0))
        deuda["alquiler"] = _f(_d(deuda["alquiler"]) + extra)
        deuda["total"] = _f(_d(deuda["total"]) + extra)
    return {**deuda, "meses_sin_registro": sin_registro}


def validar_salida(apt, fecha_salida, confirmado):
    """Lista de errores en español para registrar la salida (vacía si todo está bien)."""
    errores = []
    if apt.get("estado") != "Ocupado" or not (apt.get("inquilino_nombre") or "").strip():
        errores.append("Este apartamento no tiene un inquilino registrado.")
    if not fecha_salida:
        errores.append("La fecha de salida es obligatoria.")
    elif fecha_salida > date.today() and (fecha_salida - date.today()).days > 31:
        errores.append("La fecha de salida no puede ser más de un mes en el futuro.")
    if not confirmado:
        errores.append("Marca la casilla de confirmación para registrar la salida.")
    return errores


# ============================================================
# Abonos de un ex inquilino
# ============================================================

def validar_abono(monto, saldo_pendiente):
    """Error en español para un abono de un ex inquilino; None si está bien. No puede ser cero ni mayor al saldo."""
    monto = _d(monto)
    if monto <= 0:
        return "El monto abonado debe ser mayor a 0."
    if monto > _d(saldo_pendiente) + Decimal("0.009"):
        return f"El monto no puede ser mayor al saldo pendiente de ese mes (Bs {float(_d(saldo_pendiente)):,.2f})."
    return None


def periodos_con_saldo(periodos, campo_pagos):
    """Periodos que todavía tienen saldo, del más antiguo al más reciente (los de mes ilegible, al final)."""
    con_saldo = [p for p in periodos if saldo(p, campo_pagos) > TOLERANCIA]
    return sorted(con_saldo, key=lambda p: (moras._clave_periodo(p) is None, moras._clave_periodo(p) or (0, 0), p.get("id") or 0))
