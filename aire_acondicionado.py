"""Normalización y presentación del dato de aire acondicionado del apartamento."""

OPCIONES_PROPIEDAD = ["Del edificio", "Del inquilino"]


def a_bool(valor):
    """Convierte valores de formularios/CSV a booleano de forma tolerante."""
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return False
    if isinstance(valor, (int, float)):
        return valor != 0
    return str(valor).strip().casefold() in {"sí", "si", "s", "true", "1", "yes", "y", "verdadero"}


def indice_propiedad(valor):
    try:
        return OPCIONES_PROPIEDAD.index(valor)
    except ValueError:
        return 0


def etiqueta_propiedad(valor):
    return valor if valor in OPCIONES_PROPIEDAD else OPCIONES_PROPIEDAD[0]


def propiedad_a_guardar(tiene_aire, propiedad):
    if not a_bool(tiene_aire):
        return None
    return propiedad if propiedad in OPCIONES_PROPIEDAD else None


def validar(tiene_aire, propiedad):
    if a_bool(tiene_aire) and propiedad not in OPCIONES_PROPIEDAD:
        return "Selecciona quién es propietario del aire acondicionado."
    if not a_bool(tiene_aire) and propiedad:
        return "No se puede indicar propiedad si el apartamento no tiene aire acondicionado."
    return None


def resumen(tiene_aire, propiedad=None, con_propiedad=True):
    if not a_bool(tiene_aire):
        return "No"
    if con_propiedad and propiedad in OPCIONES_PROPIEDAD:
        return "Sí · edificio" if propiedad == "Del edificio" else "Sí · inquilino"
    return "Sí"


def descripcion(tiene_aire, propiedad=None, con_propiedad=True):
    if not a_bool(tiene_aire):
        return "No cuenta con aire acondicionado"
    if con_propiedad and propiedad in OPCIONES_PROPIEDAD:
        return f"Cuenta con aire acondicionado; propiedad: {propiedad.lower()}"
    return "Cuenta con aire acondicionado"
