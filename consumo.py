"""
Consumo y monto de los servicios de electricidad (Kwh) y agua (m³).

Regla: el CONSUMO (lectura actual - lectura anterior) se redondea a un número ENTERO, y el MONTO A COBRAR
(consumo entero x tarifa) también se redondea a un número ENTERO de bolivianos (76,70 -> 77).

  * Redondeo normal ("half up"): 34,5 -> 35 y 34,49 -> 34. No se usa round() de Python, que redondea
    2,5 a 2 ("redondeo del banquero") y daría cobros distintos de los esperados.
  * La resta se hace en aritmética decimal exacta sobre lecturas de 2 decimales (como se guardan en la
    base). Con floats, 758.56 - 461.06 da 297.49999999999994 y se redondearía a 297 en vez de 298.
  * Un consumo negativo (lectura actual menor que la anterior) se toma como 0, igual que antes.
  * El monto entero se redondea desde el producto EXACTO, no desde un valor ya redondeado a centavos
    (76,495 -> 76; si se redondeara dos veces daría 76,50 -> 77).
"""
from decimal import Decimal, ROUND_HALF_UP

_UNO = Decimal(1)
_CENTAVO = Decimal("0.01")


def _producto(consumo, tarifa):
    """consumo x tarifa en Decimal exacto (la tarifa se guarda con hasta 4 decimales)."""
    return Decimal(int(consumo or 0)) * Decimal(str(round(float(tarifa or 0), 4)))


def _lectura(valor):
    """Lectura como Decimal de 2 decimales (el formato en que se guarda). None o vacío = 0."""
    if valor is None or valor == "":
        return Decimal(0)
    return Decimal(str(round(float(valor), 2)))


def diferencia_lecturas(anterior, actual):
    """Diferencia exacta entre dos lecturas (puede ser negativa o con decimales)."""
    return _lectura(actual) - _lectura(anterior)


def calcular_consumo(anterior, actual):
    """Consumo entero (int, nunca negativo): la diferencia de lecturas redondeada al entero más cercano."""
    diferencia = diferencia_lecturas(anterior, actual)
    if diferencia <= 0:
        return 0
    return int(diferencia.quantize(_UNO, rounding=ROUND_HALF_UP))


def monto_exacto(consumo, tarifa):
    """consumo × tarifa con 2 decimales, SIN redondear a entero (solo para mostrar el paso intermedio)."""
    return float(_producto(consumo, tarifa).quantize(_CENTAVO, rounding=ROUND_HALF_UP))


def calcular_monto(consumo, tarifa):
    """Monto a cobrar: consumo × tarifa redondeado al boliviano entero (float, listo para guardar)."""
    return float(_producto(consumo, tarifa).quantize(_UNO, rounding=ROUND_HALF_UP))


def nota_redondeo(anterior, actual):
    """Texto que explica el redondeo cuando la diferencia de lecturas no es entera (None si es entera o <= 0)."""
    diferencia = diferencia_lecturas(anterior, actual)
    if diferencia <= 0 or diferencia == diferencia.to_integral_value():
        return None
    return f"diferencia de lecturas {diferencia:,.2f}, redondeada a {calcular_consumo(anterior, actual)}"
