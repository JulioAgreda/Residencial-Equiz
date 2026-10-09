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


# ============================================================
# ¿De quién es el aire acondicionado?  (columna `aire_acondicionado_propiedad`)
#   "Del edificio"  -> activo propio del edificio
#   "Del inquilino" -> lo compró el inquilino por su cuenta y se lo lleva al retirarse
#   None            -> sin definir (o el apartamento no tiene aire)
# ============================================================
DEL_EDIFICIO = "Del edificio"
DEL_INQUILINO = "Del inquilino"
OPCIONES_PROPIEDAD = [None, DEL_EDIFICIO, DEL_INQUILINO]          # None = "(sin definir)" en los formularios

_ETIQUETAS = {None: "(sin definir)", DEL_EDIFICIO: "Del edificio (activo propio)",
              DEL_INQUILINO: "Del inquilino (se lo lleva al retirarse)"}


def etiqueta_propiedad(valor):
    """Texto de cada opción en el formulario."""
    return _ETIQUETAS.get(valor, _ETIQUETAS[None])


def indice_propiedad(valor):
    """Posición de la opción guardada (para preseleccionarla al editar); desconocido -> '(sin definir)'."""
    return OPCIONES_PROPIEDAD.index(valor) if valor in OPCIONES_PROPIEDAD else 0


def normalizar_propiedad(valor):
    """Convierte lo que venga (p. ej. de un CSV: 'edificio', 'del inquilino', 'propio') a la opción guardada o None."""
    if valor is None:
        return None
    try:
        if valor != valor:                    # NaN
            return None
    except Exception:
        pass
    t = str(valor).strip().casefold()
    if t in ("", "none", "nan"):
        return None
    if "inquilin" in t or "arrendatari" in t or "cliente" in t:
        return DEL_INQUILINO
    if "edific" in t or "propio" in t or "residencial" in t or "administraci" in t:
        return DEL_EDIFICIO
    return None


def propiedad_a_guardar(tiene_aire, propiedad):
    """Lo que se guarda: la propiedad solo tiene sentido si el apartamento tiene aire; si no, queda vacía."""
    return normalizar_propiedad(propiedad) if a_bool(tiene_aire) else None


def validar(tiene_aire, propiedad):
    """Error en español si se marca que tiene aire pero no se indica de quién es; None si todo está bien."""
    if a_bool(tiene_aire) and normalizar_propiedad(propiedad) is None:
        return "Indica de quién es el aire acondicionado (del edificio o del inquilino)."
    return None


def descripcion(valor, propiedad, con_propiedad=True):
    """Texto completo para la ficha de solo lectura. con_propiedad=False cuando la columna aún no existe en la base."""
    if valor is None:
        return "—"
    if not a_bool(valor):
        return "No"
    if not con_propiedad:
        return "Sí"
    p = normalizar_propiedad(propiedad)
    if p == DEL_EDIFICIO:
        return "Sí — del edificio (activo propio)"
    if p == DEL_INQUILINO:
        return "Sí — del inquilino (se lo lleva al retirarse)"
    return "Sí — falta indicar de quién es"


def resumen(valor, propiedad, con_propiedad=True):
    """Texto corto para columnas de tablas."""
    if valor is None:
        return "—"
    if not a_bool(valor):
        return "No"
    if not con_propiedad:
        return "Sí"
    return {DEL_EDIFICIO: "Sí · edificio", DEL_INQUILINO: "Sí · inquilino"}.get(normalizar_propiedad(propiedad), "Sí · sin definir")
