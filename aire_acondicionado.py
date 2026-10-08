"""
Aire acondicionado de los apartamentos: columna `aire_acondicionado` (boolean, por defecto falso) de `apartamentos`.

Módulo sin dependencias de Streamlit ni de la base.
"""

_SI = {"si", "sí", "s", "y", "yes", "true", "verdadero", "1", "x", "con", "tiene"}


def a_bool(valor):
    """Convierte lo que venga (un Sí/No escrito en un CSV, un número, True/False, vacío) a True/False.
    Lo vacío, desconocido o 'No' es False: el valor por defecto es 'sin aire acondicionado'."""
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return False
    try:
        if valor != valor:                    # NaN (celda vacía de un CSV leído con pandas)
            return False
    except Exception:
        pass
    texto = str(valor).strip().casefold()
    return texto in _SI


def texto(valor):
    """'Sí' / 'No' para mostrar; '—' si el dato no existe (la columna todavía no se creó en la base)."""
    if valor is None:
        return "—"
    return "Sí" if a_bool(valor) else "No"
