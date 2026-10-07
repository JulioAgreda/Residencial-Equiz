"""
Servicios Básicos: datos de contacto de los proveedores de servicios básicos del edificio
(electricidad, agua, internet, gas, etc.). Tabla `servicios_basicos`.

Columnas: nombre_servicio, empresa_proveedor, telefono, codigo, titular, observacion, creado_por
(más id, created_at y updated_at, que maneja la base).

Módulo sin dependencias de Streamlit ni de la base: valida, arma el registro y filtra.
"""
import unicodedata

# Largos conservadores: no conozco los límites exactos de los varchar de la tabla.
LIMITES = {"nombre_servicio": 100, "empresa_proveedor": 150, "telefono": 50, "codigo": 80,
           "titular": 150, "observacion": 2000}
CAMPOS_TEXTO = ["nombre_servicio", "empresa_proveedor", "telefono", "codigo", "titular", "observacion"]


def _limpio(texto):
    texto = (texto or "").strip()
    return texto or None


def validar_servicio(nombre_servicio, empresa_proveedor="", telefono="", codigo="", titular="", observacion=""):
    """Lista de errores en español (vacía si todo está bien). Solo el nombre del servicio es obligatorio."""
    errores = []
    if not _limpio(nombre_servicio):
        errores.append("El nombre del servicio es obligatorio.")
    valores = {"nombre_servicio": nombre_servicio, "empresa_proveedor": empresa_proveedor, "telefono": telefono,
               "codigo": codigo, "titular": titular, "observacion": observacion}
    etiquetas = {"nombre_servicio": "El nombre del servicio", "empresa_proveedor": "La empresa proveedora",
                 "telefono": "El teléfono", "codigo": "El código", "titular": "El titular", "observacion": "La observación"}
    for campo, valor in valores.items():
        if len((valor or "").strip()) > LIMITES[campo]:
            errores.append(f"{etiquetas[campo]} no puede pasar de {LIMITES[campo]} caracteres.")
    return errores


def armar_registro(nombre_servicio, empresa_proveedor, telefono, codigo, titular, observacion, creado_por=None):
    """Diccionario con los nombres EXACTOS de las columnas de la tabla. Vacío -> None (NULL).
    'creado_por' solo se incluye al crear (al editar no se cambia quién lo creó)."""
    registro = {
        "nombre_servicio": _limpio(nombre_servicio), "empresa_proveedor": _limpio(empresa_proveedor),
        "telefono": _limpio(telefono), "codigo": _limpio(codigo), "titular": _limpio(titular),
        "observacion": _limpio(observacion),
    }
    if creado_por is not None:
        registro["creado_por"] = creado_por
    return registro


def _sin_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if unicodedata.category(c) != "Mn").casefold()


def filtrar(servicios, texto):
    """Búsqueda sin distinguir mayúsculas ni acentos, en todos los campos de texto. Texto vacío = todos."""
    buscado = _sin_acentos(texto).strip()
    if not buscado:
        return list(servicios)
    return [s for s in servicios if any(buscado in _sin_acentos(s.get(c)) for c in CAMPOS_TEXTO)]


def ordenar(servicios):
    """Por nombre del servicio (sin distinguir mayúsculas ni acentos)."""
    return sorted(servicios, key=lambda s: (_sin_acentos(s.get("nombre_servicio")), s.get("id") or 0))
