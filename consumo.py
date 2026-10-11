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
import re
import unicodedata
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


# ============================================================
# Apartamentos con DOS medidores de energía eléctrica
# ============================================================
# Un apartamento con dos medidores sigue teniendo UN solo periodo por mes: el segundo medidor se guarda en las
# columnas `kwh_anterior_2` y `kwh_actual_2` (vacías = el apartamento tiene un solo medidor). El consumo es la suma
# de los dos medidores (cada uno redondeado al entero) y el monto es ese total × la tarifa, redondeado al boliviano
# entero. Así la deuda, los abonos y los recibos siguen funcionando igual: todo cuelga de un único periodo.
#
# Para agregar otro apartamento con dos medidores, agrega su código aquí (se compara sin distinguir mayúsculas,
# acentos ni espacios alrededor del guion).
APARTAMENTOS_DOS_MEDIDORES = ("PB - APARTAMENTO 2", "PB-02")

# (lectura anterior, lectura actual) de cada medidor, por servicio. El primero siempre existe; los demás solo si tienen dato.
PARES_LECTURAS = {
    "electricidad": (("kwh_anterior", "kwh_actual"), ("kwh_anterior_2", "kwh_actual_2")),
    "agua": (("lectura_anterior", "lectura_actual"),),
}


def _clave_codigo(texto):
    t = unicodedata.normalize("NFD", str(texto or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").casefold()
    return re.sub(r"\s*-\s*", "-", " ".join(t.split()))


_CODIGOS_DOS_MEDIDORES = {_clave_codigo(c) for c in APARTAMENTOS_DOS_MEDIDORES}


def cantidad_medidores_luz(apartamento):
    """2 para los apartamentos de APARTAMENTOS_DOS_MEDIDORES; 1 para el resto."""
    return 2 if _clave_codigo((apartamento or {}).get("codigo")) in _CODIGOS_DOS_MEDIDORES else 1


def pares_lecturas(periodo, servicio):
    """Lista de (anterior, actual) de los medidores que tiene ese periodo. Un segundo medidor cuenta solo si su lectura
    actual tiene dato (None = no aplica)."""
    periodo = periodo or {}
    pares = []
    for i, (campo_ant, campo_act) in enumerate(PARES_LECTURAS[servicio]):
        if i == 0 or periodo.get(campo_act) is not None:
            pares.append((periodo.get(campo_ant), periodo.get(campo_act)))
    return pares


def consumo_total(periodo, servicio):
    """Consumo entero del periodo: suma del consumo (redondeado) de cada medidor."""
    return sum(calcular_consumo(ant, act) for ant, act in pares_lecturas(periodo, servicio))
