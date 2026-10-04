"""
Compromisos de pago: historial del motivo de retraso que informa el inquilino y del acuerdo al que
se llegó (compromiso, fecha plazo y monto acordado).

Módulo sin dependencias de Streamlit ni de la base: valida, arma el registro a guardar y calcula el
estado visible. Así se puede probar de forma aislada.
"""
from datetime import date

ESTADOS = ["Pendiente", "Cumplido", "Incumplido"]
ESTADO_VENCIDO = "Vencido"            # solo visual: Pendiente cuyo plazo ya pasó
MONTO_MAXIMO = 99_999_999.99          # límite de numeric(10,2)
MAX_TEXTO = 2000


def _fecha(valor):
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10]) if valor else None
    except ValueError:
        return None


def _limpio(texto):
    texto = (texto or "").strip()
    return texto or None


def estado_efectivo(compromiso, hoy=None):
    """Estado que se muestra: un compromiso 'Pendiente' con el plazo vencido se ve como 'Vencido'.
    No se guarda en la base: si el plazo se edita, el estado se corrige solo."""
    hoy = hoy or date.today()
    estado = compromiso.get("estado") or "Pendiente"
    plazo = _fecha(compromiso.get("fecha_plazo"))
    if estado == "Pendiente" and plazo and plazo < hoy:
        return ESTADO_VENCIDO
    return estado


def dias_para_plazo(compromiso, hoy=None):
    """Días que faltan para el plazo (negativo si ya pasó); None si no tiene plazo."""
    hoy = hoy or date.today()
    plazo = _fecha(compromiso.get("fecha_plazo"))
    return (plazo - hoy).days if plazo else None


def validar_compromiso(motivo, compromiso, fecha_registro, fecha_plazo, monto):
    """Devuelve la lista de errores en español (vacía si todo está bien).
    Reglas: el motivo es obligatorio; si hay monto debe haber plazo; el plazo no puede ser anterior
    a la fecha del registro; el monto no puede ser negativo ni exceder el límite de la base."""
    errores = []
    if not _limpio(motivo):
        errores.append("El motivo del retraso es obligatorio.")
    if len(motivo or "") > MAX_TEXTO or len(compromiso or "") > MAX_TEXTO:
        errores.append(f"Los textos no pueden pasar de {MAX_TEXTO} caracteres.")
    registro, plazo = _fecha(fecha_registro), _fecha(fecha_plazo)
    if not registro:
        errores.append("La fecha del registro es obligatoria.")
    monto = float(monto or 0)
    if monto < 0:
        errores.append("El monto no puede ser negativo.")
    elif monto > MONTO_MAXIMO:
        errores.append("El monto es demasiado grande.")
    if monto > 0 and not plazo:
        errores.append("Si indicas un monto acordado, indica también la fecha plazo.")
    if registro and plazo and plazo < registro:
        errores.append("La fecha plazo no puede ser anterior a la fecha del registro.")
    return errores


def armar_registro(motivo, compromiso, fecha_registro, fecha_plazo, monto, estado, usuario,
                   apartamento=None):
    """Diccionario listo para guardar. Con 'apartamento' es un registro NUEVO (guarda quién lo
    registró y el nombre del inquilino de ese momento, porque el inquilino puede cambiar después);
    sin él es una EDICIÓN (guarda quién la hizo). Un monto de 0 se guarda como 'sin monto'."""
    monto = round(float(monto or 0), 2)
    registro = {
        "fecha_registro": str(_fecha(fecha_registro)),
        "motivo_retraso": _limpio(motivo),
        "compromiso": _limpio(compromiso),
        "fecha_plazo": str(_fecha(fecha_plazo)) if _fecha(fecha_plazo) else None,
        "monto_comprometido": monto if monto > 0 else None,
        "estado": estado if estado in ESTADOS else "Pendiente",
    }
    if apartamento is not None:
        registro["apartamento_id"] = apartamento["id"]
        registro["inquilino_nombre"] = apartamento.get("inquilino_nombre")
        registro["registrado_por"] = usuario
    else:
        registro["editado_por"] = usuario
    return registro


def ordenar_historial(compromisos):
    """Más reciente primero (por fecha del registro y, a igual fecha, por id)."""
    return sorted(compromisos, key=lambda c: (str(c.get("fecha_registro") or ""), c.get("id") or 0), reverse=True)


def ordenar_por_plazo(compromisos):
    """Para seguimiento: primero los de plazo más cercano o ya vencido; los sin plazo al final."""
    return sorted(compromisos, key=lambda c: (c.get("fecha_plazo") is None, str(c.get("fecha_plazo") or ""),
                                              -(c.get("id") or 0)))
