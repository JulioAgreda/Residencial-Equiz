"""
Generación de recibos de pago de alquiler, en PDF y PNG, con el logo
de la residencial. Usa reportlab (PDF) y Pillow (PNG) — ambas livianas
y compatibles con Streamlit Cloud (Pillow ya viene con streamlit;
reportlab hay que agregarlo a requirements.txt).

Para que el logo aparezca, sube la carpeta "assets/" (incluida junto
a este archivo) a tu repositorio, en la misma carpeta que app.py.
"""
import io
import os
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import consumo as _consumo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, Flowable
from PIL import Image, ImageDraw, ImageFont

# El servidor (Streamlit Cloud) corre en UTC, no en la hora de Bolivia (UTC-4).
# Sin esto, la hora de emisión del recibo saldría adelantada.
_ZONA_BOLIVIA = timezone(timedelta(hours=-4))

_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(_DIR, "assets", "logo_equise_horizontal.png")
LOGO_FALLBACK_PATH = os.path.join(_DIR, "assets", "logo_equise.png")
_AZUL = "#102F50"
_DORADO = "#C99A3B"
_AZUL_CLARO = "#EDF3F8"
_GRIS = "#D6E0E8"
NOMBRE_RESIDENCIAL = "Residencial Equise"

_COLOR_ACENTO = (46, 125, 50)      # verde, para PNG (RGB)
_COLOR_ACENTO_PDF = "#2E7D32"      # mismo verde, para PDF

# PB=Planta Baja, PP=Primer Piso, SP=Segundo Piso, TP=Tercer Piso
_MAPA_PISO_ABREV = {"PB": "Planta Baja", "PP": "Primer Piso", "SP": "Segundo Piso", "TP": "Tercer Piso"}


def _fmt_bs(monto):
    try:
        return f"Bs {float(monto):,.1f}"
    except (TypeError, ValueError):
        return "Bs 0.0"


def formatear_apartamento(apartamento):
    """Arma un texto legible tipo 'Apartamento 4 - Segundo Piso' a partir del código y el
    piso guardados, sin importar si el código se escribió como 'PB-01', '4' o
    'SP - Apartamento 4'. Usa el campo "piso" del apartamento cuando existe (ya viene
    con el nombre completo); si no, lo deduce de las letras iniciales del código."""
    apartamento = apartamento or {}
    codigo = str(apartamento.get("codigo") or "").strip()
    piso = str(apartamento.get("piso") or "").strip()

    m_num = re.search(r"(\d+)\s*$", codigo)
    numero = str(int(m_num.group(1))) if m_num else None

    if not piso:
        m_abrev = re.match(r"^\s*([A-Za-zÁÉÍÓÚáéíóú]+)", codigo)
        abrev = (m_abrev.group(1) if m_abrev else "").upper()
        piso = _MAPA_PISO_ABREV.get(abrev, "")

    if numero and piso:
        return f"Apartamento {numero} - {piso}"
    return codigo or "—"


def _fuente(tamano, negrita=False, cursiva=False):
    """Carga una fuente TrueType legible desde assets/fonts/. Si por algún
    motivo no está disponible, usa la fuente por defecto de Pillow (más
    simple, pero nunca falla)."""
    if negrita:
        nombre = "DejaVuSans-Bold.ttf"
    elif cursiva:
        nombre = "DejaVuSans-Oblique.ttf"
    else:
        nombre = "DejaVuSans.ttf"
    ruta = os.path.join(_DIR, "assets", "fonts", nombre)
    try:
        return ImageFont.truetype(ruta, tamano)
    except Exception:
        return ImageFont.load_default()


def construir_datos_recibo(pago, periodo, apartamento, total_pagado_periodo, recibido_por):
    """Arma el diccionario de datos que necesitan generar_recibo_pdf/png,
    a partir de los registros que ya existen en la app (el abono, su
    periodo y el apartamento)."""
    monto_esperado = float((periodo or {}).get("monto_esperado") or 0)
    saldo = monto_esperado - float(total_pagado_periodo or 0)
    return {
        "numero_recibo": f'REC-{int(pago["id"]):06d}',
        "fecha_emision": datetime.now(_ZONA_BOLIVIA).strftime("%d/%m/%Y %H:%M"),
        # Este constructor corresponde exclusivamente a recibos de alquiler.
        # Los recibos de electricidad/agua y CXC asignan su propio título.
        "titulo": "Recibo de Pago de Alquiler",
        "apartamento_texto": formatear_apartamento(apartamento),
        "inquilino_nombre": (periodo or {}).get("inquilino_nombre") or (apartamento or {}).get("inquilino_nombre") or "—",
        "periodo": f'{(periodo or {}).get("mes", "")} {(periodo or {}).get("anio", "")}'.strip(),
        "fecha_pago": pago.get("fecha", ""),
        "monto_pagado": float(pago.get("monto") or 0),
        "metodo_pago": pago.get("metodo_pago") or "—",
        "observacion": pago.get("observacion") or "",
        "monto_esperado": monto_esperado,
        "total_pagado_periodo": float(total_pagado_periodo or 0),
        "saldo_pendiente": saldo,
        "recibido_por": recibido_por or "—",
    }


# ============================================================
# Recibos de LUZ y AGUA: mismo formato que el de alquiler + lecturas del medidor
# ============================================================

SERVICIOS = {
    "electricidad": {"titulo": "Recibo de Pago de Electricidad", "prefijo": "REC-L", "unidad": "Kwh",
                     "campo_anterior": "kwh_anterior", "campo_actual": "kwh_actual", "campo_tarifa": "tarifa_kwh"},
    "agua": {"titulo": "Recibo de Pago de Agua", "prefijo": "REC-A", "unidad": "m³",
             "campo_anterior": "lectura_anterior", "campo_actual": "lectura_actual", "campo_tarifa": "tarifa_agua"},
}


def _fmt_num(valor):
    """6509 -> '6,509'; 1200.1 -> '1,200.1'; 12.50 -> '12.5'."""
    texto = f"{float(valor):,.2f}"
    return texto.rstrip("0").rstrip(".")


def _fmt_tarifa(valor):
    """1.3 -> '1.30'; 1.2345 -> '1.2345' (mínimo 2 decimales, máximo 4)."""
    texto = f"{float(valor or 0):.4f}"
    while texto.endswith("0") and len(texto.split(".")[1]) > 2:
        texto = texto[:-1]
    return texto


def _detalle_lecturas(cfg, periodo, servicio=None):
    """Filas (etiqueta, valor) con las lecturas del medidor. El consumo y la tarifa solo se imprimen si
    el monto guardado de ese periodo corresponde a esa cuenta: los periodos guardados antes de redondear
    el cobro a boliviano entero tienen otro monto, y un recibo no debe mostrar números que no cuadran.
    Si el periodo tiene dos medidores de luz, se imprimen las lecturas de cada uno y el consumo total."""
    periodo = periodo or {}
    if servicio is None:
        servicio = next(k for k, v in SERVICIOS.items() if v is cfg)
    anterior, actual = periodo.get(cfg["campo_anterior"]), periodo.get(cfg["campo_actual"])
    if anterior is None or actual is None:
        return []
    unidad = cfg["unidad"]
    pares = _consumo.pares_lecturas(periodo, servicio)
    if len(pares) == 1:
        filas = [("Lectura anterior:", f"{_fmt_num(anterior)} {unidad}"),
                 ("Lectura actual:", f"{_fmt_num(actual)} {unidad}")]
    else:
        filas = []
        for n, (ant, act) in enumerate(pares, start=1):
            filas += [(f"Medidor {n} - anterior:", f"{_fmt_num(ant or 0)} {unidad}"),
                      (f"Medidor {n} - actual:", f"{_fmt_num(act or 0)} {unidad}")]
    tarifa = float(periodo.get(cfg["campo_tarifa"]) or 0)
    consumo_entero = _consumo.consumo_total(periodo, servicio)
    if abs(_consumo.calcular_monto(consumo_entero, tarifa) - float(periodo.get("monto_esperado") or 0)) < 0.005:
        filas += [("Consumo total:" if len(pares) > 1 else "Consumo:", f"{consumo_entero} {unidad}"),
                  ("Tarifa:", f"Bs {_fmt_tarifa(tarifa)} por {unidad}")]
    return filas


@lru_cache(maxsize=1)
def _fuente_pdf_unicode():
    """Nombre de una fuente incrustada que sí dibuja caracteres como '³' (la Helvetica estándar de los PDF no
    lo dibuja de forma fiable: 'm³' se vería 'm'). Si no se puede cargar, se usa Helvetica."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont("DejaVuSans-Recibo", os.path.join(_DIR, "assets", "fonts", "DejaVuSans.ttf")))
        return "DejaVuSans-Recibo"
    except Exception:
        return "Helvetica"


def _identificador_recibo_cxc(movimiento):
    """Identificador legible y estable para un cobro de cuenta por cobrar."""
    bruto = str((movimiento or {}).get("id") or "SIN-ID").strip()
    if bruto.isdigit():
        return f"{int(bruto):06d}"
    limpio = re.sub(r"[^A-Za-z0-9]", "", bruto).upper()
    return (limpio[:10] or "SIN-ID")


def construir_datos_recibo_cuenta_cobrar(cuenta, movimiento, movimientos_cuenta=None):
    """Prepara los datos del recibo de un cobro de una cuenta por cobrar (CXC).

    No consulta ni modifica la base de datos: utiliza la cuenta y los movimientos
    que la aplicación ya cargó. El saldo se calcula sobre saldo_apertura menos
    los cobros registrados, evitando sumar movimientos de otras cuentas.
    """
    cuenta = cuenta or {}
    movimiento = movimiento or {}
    movimientos_cuenta = list(movimientos_cuenta or [])

    if movimiento.get("tipo") != "cobro":
        raise ValueError("El movimiento seleccionado no corresponde a un cobro.")
    cuenta_id = cuenta.get("id")
    if movimiento.get("cuenta_id") is not None and cuenta_id is not None:
        if str(movimiento.get("cuenta_id")) != str(cuenta_id):
            raise ValueError("El cobro seleccionado no pertenece a la cuenta indicada.")

    cobros = [m for m in movimientos_cuenta if m.get("tipo") == "cobro"]
    # Asegura incluir el cobro seleccionado aunque el listado recibido esté incompleto.
    if not any(str(m.get("id")) == str(movimiento.get("id")) for m in cobros):
        cobros.append(movimiento)
    total_cobrado = sum(float(m.get("monto") or 0) for m in cobros)

    saldo_apertura_raw = cuenta.get("saldo_apertura")
    if saldo_apertura_raw is None:
        saldo_apertura_raw = cuenta.get("monto_original") or 0
    saldo_apertura = float(saldo_apertura_raw or 0)
    saldo_pendiente = max(0.0, saldo_apertura - total_cobrado)

    codigo = str(cuenta.get("codigo") or cuenta_id or "—")
    categoria = str(cuenta.get("categoria") or "Cuenta por cobrar")
    concepto = str(cuenta.get("descripcion") or categoria)
    referencia = str(movimiento.get("referencia") or "").strip()
    observacion = str(movimiento.get("observacion") or "").strip()
    notas = []
    if referencia:
        notas.append(f"Referencia: {referencia}")
    if observacion:
        notas.append(observacion)

    return {
        "numero_recibo": f"REC-CXC-{_identificador_recibo_cxc(movimiento)}",
        "fecha_emision": datetime.now(_ZONA_BOLIVIA).strftime("%d/%m/%Y %H:%M"),
        "titulo": "Recibo de cobro de cuenta por cobrar",
        "apartamento_texto": codigo,
        "inquilino_nombre": cuenta.get("deudor") or "—",
        "periodo": concepto,
        "fecha_pago": movimiento.get("fecha") or "—",
        "monto_pagado": float(movimiento.get("monto") or 0),
        "metodo_pago": movimiento.get("metodo") or "—",
        "observacion": " | ".join(notas),
        "monto_esperado": saldo_apertura,
        "total_pagado_periodo": total_cobrado,
        "saldo_pendiente": saldo_pendiente,
        "recibido_por": movimiento.get("registrado_por") or cuenta.get("creado_por") or "—",
        # Etiquetas específicas para que el recibo no muestre términos de alquiler.
        "etiqueta_apartamento": "Cuenta por cobrar:",
        "etiqueta_inquilino": "Deudor:",
        "etiqueta_periodo": "Concepto:",
        "etiqueta_fecha_pago": "Fecha de cobro:",
        "etiqueta_metodo_pago": "Medio de cobro:",
        "etiqueta_monto_esperado": "Saldo inicial de cuenta:",
        "etiqueta_total_pagado": "Total cobrado desde registro:",
        "etiqueta_monto_abono": "MONTO COBRADO",
    }


def construir_datos_recibo_servicio(servicio, pago, periodo, apartamento, total_pagado_periodo, recibido_por):
    """Como construir_datos_recibo, para un abono de 'electricidad' o 'agua'. El número lleva prefijo propio
    (REC-L / REC-A) porque cada servicio tiene su propia tabla de abonos y los ids se repetirían entre ellas."""
    cfg = SERVICIOS[servicio]
    datos = construir_datos_recibo(pago, periodo, apartamento, total_pagado_periodo, recibido_por)
    datos["numero_recibo"] = f'{cfg["prefijo"]}-{int(pago["id"]):06d}'
    datos["titulo"] = cfg["titulo"]
    datos["detalle"] = _detalle_lecturas(cfg, periodo, servicio)
    return datos



def _lineas_titulo_encabezado(datos):
    """Devuelve un título corto y legible para el panel azul del recibo."""
    titulo = str((datos or {}).get("titulo") or "PAGO").strip()
    normalizado = titulo.lower()
    if "cuenta por cobrar" in normalizado or "cobro de cuenta" in normalizado:
        return ["COBRO DE", "CUENTA"]
    titulo = titulo.replace("Recibo de Pago de ", "").replace("Recibo de pago de ", "")
    titulo = titulo.replace("Recibo de cobro de ", "").replace("Recibo de Cobro de ", "")
    if titulo.strip().lower() == "alquiler":
        titulo = "ALQUILER"
    titulo = titulo.strip().upper() or "PAGO"
    palabras = titulo.split()
    lineas, actual = [], ""
    for palabra in palabras:
        candidato = f"{actual} {palabra}".strip()
        if len(candidato) <= 14 or not actual:
            actual = candidato
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    if len(lineas) > 2:
        # En paneles pequeños prioriza el nombre del concepto y evita desbordes.
        lineas = [lineas[0], " ".join(lineas[1:])]
    return lineas[:2]


# ============================================================
# PDF — formato compacto, tipo comprobante
# ============================================================

def generar_recibo_pdf(datos: dict) -> bytes:
    """Genera recibos con el diseño institucional aprobado: logo horizontal,
    panel azul marino con diagonal dorada, ficha celeste y resumen de pago."""
    buffer = io.BytesIO()
    ancho, alto = A5
    c = pdfcanvas.Canvas(buffer, pagesize=A5)
    margen = 8 * mm
    azul = colors.HexColor("#123456")
    dorado = colors.HexColor("#C99A3B")
    azul_claro = colors.HexColor("#EDF3F8")
    gris = colors.HexColor("#D5E0E9")
    gris_texto = colors.HexColor("#647991")
    verde = colors.HexColor("#2E7D32")

    # Encabezado: sin marco exterior; logo a la izquierda y panel azul a la derecha.
    x0, y_top = margen, alto - margen
    header_h = 32 * mm
    header_bottom = y_top - header_h
    panel_x = x0 + (ancho - 2*margen) * 0.66
    # Diagonal dorada y panel azul.
    p = c.beginPath()
    p.moveTo(panel_x + 5*mm, y_top)
    p.lineTo(ancho-margen, y_top)
    p.lineTo(ancho-margen, header_bottom)
    p.lineTo(panel_x - 5*mm, header_bottom)
    p.close()
    c.setFillColor(azul); c.drawPath(p, fill=1, stroke=0)
    p2 = c.beginPath()
    p2.moveTo(panel_x, y_top); p2.lineTo(panel_x+2.2*mm, y_top)
    p2.lineTo(panel_x-7.8*mm, header_bottom); p2.lineTo(panel_x-10*mm, header_bottom)
    p2.close()
    c.setFillColor(dorado); c.drawPath(p2, fill=1, stroke=0)

    logo_path = LOGO_PATH if os.path.exists(LOGO_PATH) else LOGO_FALLBACK_PATH
    if os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, x0+2*mm, header_bottom+3*mm,
                        width=(panel_x-x0-12*mm), height=header_h-6*mm,
                        preserveAspectRatio=True, anchor="c", mask="auto")
        except Exception:
            pass

    lineas_titulo = _lineas_titulo_encabezado(datos)
    centro_panel = (panel_x+ancho-margen)/2 + 1*mm
    ancho_panel_pt = (ancho-margen) - (panel_x-2*mm)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 7.2)
    c.drawCentredString(centro_panel, y_top-10*mm, "RECIBO DE PAGO")
    tam_titulo = 10.2 if len(lineas_titulo) > 1 else 11.2
    while tam_titulo > 8 and any(c.stringWidth(linea, "Helvetica-Bold", tam_titulo) > ancho_panel_pt for linea in lineas_titulo):
        tam_titulo -= 0.4
    c.setFont("Helvetica-Bold", tam_titulo)
    if len(lineas_titulo) == 1:
        c.drawCentredString(centro_panel, y_top-18*mm, lineas_titulo[0])
    else:
        c.drawCentredString(centro_panel, y_top-17*mm, lineas_titulo[0])
        c.drawCentredString(centro_panel, y_top-22*mm, lineas_titulo[1])
    c.setStrokeColor(dorado); c.setLineWidth(1.4)
    c.line(x0, header_bottom, ancho-margen, header_bottom)

    y = header_bottom - 5*mm
    c.setFillColor(gris_texto); c.setFont("Helvetica", 7)
    c.drawString(x0, y, "RECIBO N.º")
    c.setFillColor(azul); c.setFont("Helvetica-Bold", 7.4)
    c.drawString(x0+19*mm, y, str(datos.get("numero_recibo", "—")))
    c.setFillColor(gris_texto); c.setFont("Helvetica", 7)
    c.drawRightString(ancho-margen-23*mm, y, "Emisión:")
    c.setFillColor(azul); c.setFont("Helvetica", 7)
    c.drawRightString(ancho-margen, y, str(datos.get("fecha_emision", "—")))

    # Tarjeta de identificación.
    y -= 5*mm
    card_h = 25*mm
    c.setFillColor(azul_claro); c.roundRect(x0, y-card_h+2*mm, ancho-2*margen, card_h, 3*mm, fill=1, stroke=0)
    xx_label, xx_val = x0+4*mm, x0+39*mm
    cy = y-4.5*mm
    for label, value in [
        ("APARTAMENTO", datos.get("apartamento_texto","—")),
        ("INQUILINO", datos.get("inquilino_nombre","—")),
        ("PERIODO / CONCEPTO", datos.get("periodo","—")),
    ]:
        c.setFillColor(azul); c.setFont("Helvetica-Bold", 6.6); c.drawString(xx_label, cy, label)
        c.setFillColor(azul); c.setFont("Helvetica", 8.1); c.drawString(xx_val, cy-0.2*mm, str(value)[:48])
        cy -= 7*mm

    y -= card_h + 4*mm
    # Datos y lecturas, en filas compactas.
    c.setStrokeColor(gris); c.setLineWidth(0.6); c.line(x0, y, ancho-margen, y)
    y -= 5.5*mm
    def fila(label, value, bold=False, small=False):
        nonlocal y
        c.setFillColor(gris_texto if small else azul)
        c.setFont("Helvetica-Bold", 6.8 if small else 7.8)
        c.drawString(x0+3*mm, y, str(label).upper() if small else str(label))
        c.setFillColor(azul); c.setFont("Helvetica-Bold" if bold else "Helvetica", 8 if not small else 7.8)
        c.drawString(x0+58*mm, y, str(value)[:45])
        y -= 6.2*mm if not small else 5.4*mm

    fila(datos.get("etiqueta_fecha_pago","FECHA DE PAGO"), datos.get("fecha_pago","—"), small=True)
    fila(datos.get("etiqueta_metodo_pago","MÉTODO DE PAGO"), datos.get("metodo_pago","—"), small=True)
    fila("RECIBIDO POR", datos.get("recibido_por","—"), small=True)
    if datos.get("detalle"):
        for label, value in datos["detalle"]:
            fila(label, value, small=True)
    c.setStrokeColor(gris); c.line(x0, y+1.5*mm, ancho-margen, y+1.5*mm)
    y -= 4*mm

    # Resumen del periodo.
    fila(datos.get("etiqueta_monto_esperado","Monto esperado:"), _fmt_bs(datos.get("monto_esperado",0)))
    fila(datos.get("etiqueta_total_pagado","Total pagado a la fecha:"), _fmt_bs(datos.get("total_pagado_periodo",0)))
    saldo = float(datos.get("saldo_pendiente",0) or 0)
    fila("Estado:", "PAGADO COMPLETO" if saldo <= 0.009 else f"Saldo pendiente: {_fmt_bs(saldo)}", bold=True)

    # Monto del abono en tarjeta azul claro, sin exagerar el color de alerta.
    y -= 1.5*mm
    caja_h = 18*mm
    c.setFillColor(azul_claro); c.setStrokeColor(azul); c.setLineWidth(1)
    c.roundRect(x0, y-caja_h, ancho-2*margen, caja_h, 3*mm, fill=1, stroke=1)
    c.setFillColor(azul); c.circle(x0+10*mm, y-caja_h/2, 6.5*mm, fill=1, stroke=0)
    c.setFillColor(dorado); c.setFont("Helvetica-Bold", 8); c.drawCentredString(x0+10*mm, y-caja_h/2-1*mm, "Bs")
    c.setFillColor(azul); c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x0+22*mm, y-6.5*mm, datos.get("etiqueta_monto_abono","MONTO RECIBIDO").upper())
    c.setFont("Helvetica-Bold", 17)
    c.drawString(x0+22*mm, y-14*mm, _fmt_bs(datos.get("monto_pagado",0)))
    y -= caja_h + 4*mm

    # Estado resumido en panel claro.
    c.setFillColor(azul_claro); c.roundRect(x0, y-14*mm, ancho-2*margen, 14*mm, 2.5*mm, fill=1, stroke=0)
    c.setFillColor(azul); c.setFont("Helvetica", 7)
    c.drawString(x0+3*mm, y-4.5*mm, "Monto esperado:")
    c.drawRightString(ancho-margen-3*mm, y-4.5*mm, _fmt_bs(datos.get("monto_esperado",0)))
    c.setStrokeColor(gris); c.line(x0+3*mm, y-7*mm, ancho-margen-3*mm, y-7*mm)
    c.drawString(x0+3*mm, y-11.5*mm, "Estado:")
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(ancho-margen-3*mm, y-11.5*mm, "PAGADO COMPLETO" if saldo <= 0.009 else f"SALDO: {_fmt_bs(saldo)}")
    y -= 20*mm

    if datos.get("observacion"):
        c.setFillColor(gris_texto); c.setFont("Helvetica-Oblique", 7)
        c.drawString(x0+3*mm, y, f'Observación: {str(datos["observacion"])[:90]}')
        y -= 5*mm
    c.setStrokeColor(dorado); c.setLineWidth(1); c.line(x0, y, ancho-margen, y)
    y -= 5*mm
    c.setFillColor(azul); c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(ancho/2, y, f'REGISTRADO POR: {datos.get("recibido_por","—")}')
    y -= 4*mm
    c.setFont("Helvetica-Oblique", 8); c.drawCentredString(ancho/2, y, "¡Gracias por su pago!")

    c.showPage(); c.save(); buffer.seek(0)
    return buffer.getvalue()


def generar_recibo_png(datos: dict) -> bytes:
    """PNG con la misma identidad gráfica que el PDF: logo horizontal y panel azul/dorado."""
    ancho, alto = 820, 1160
    img = Image.new("RGB", (ancho, alto), "white")
    d = ImageDraw.Draw(img)
    azul="#123456"; dorado="#C99A3B"; claro="#EDF3F8"; gris="#D5E0E9"; gris_texto="#647991"
    margen=46; top=24; header_h=170; bottom=top+header_h
    panel_x=margen+(ancho-2*margen)*0.66
    d.polygon([(panel_x+28,top),(ancho-margen,top),(ancho-margen,bottom),(panel_x-28,bottom)],fill=azul)
    d.polygon([(panel_x,top),(panel_x+12,top),(panel_x-44,bottom),(panel_x-56,bottom)],fill=dorado)
    logo_path=LOGO_PATH if os.path.exists(LOGO_PATH) else LOGO_FALLBACK_PATH
    if os.path.exists(logo_path):
        try:
            logo=Image.open(logo_path).convert("RGBA")
            logo.thumbnail((int(panel_x-margen-80),header_h-42),Image.Resampling.LANCZOS)
            img.paste(logo,(margen+10,top+(header_h-logo.height)//2),logo)
        except Exception:
            pass
    f_small=_fuente(14); f_head=_fuente(22,negrita=True); f_label=_fuente(13,negrita=True)
    f_val=_fuente(15); f_bold=_fuente(16,negrita=True); f_amount=_fuente(31,negrita=True)
    cx=(panel_x+ancho-margen)/2+5
    d.text((cx,top+52),"RECIBO DE PAGO",font=f_small,fill="white",anchor="mm")
    lineas_titulo = _lineas_titulo_encabezado(datos)
    tam_titulo = 20 if len(lineas_titulo) == 1 else 18
    f_titulo = _fuente(tam_titulo, negrita=True)
    ancho_panel_px = (ancho-margen) - (panel_x-8)
    while tam_titulo > 14 and any(d.textbbox((0,0), linea, font=f_titulo)[2] > ancho_panel_px for linea in lineas_titulo):
        tam_titulo -= 1
        f_titulo = _fuente(tam_titulo, negrita=True)
    if len(lineas_titulo) == 1:
        d.text((cx,top+94),lineas_titulo[0],font=f_titulo,fill="white",anchor="mm")
    else:
        d.text((cx,top+82),lineas_titulo[0],font=f_titulo,fill="white",anchor="mm")
        d.text((cx,top+108),lineas_titulo[1],font=f_titulo,fill="white",anchor="mm")
    d.line((margen,bottom,ancho-margen,bottom),fill=dorado,width=4)
    y=bottom+22
    d.text((margen,y),"RECIBO N.º",font=f_small,fill=gris_texto)
    d.text((margen+100,y),str(datos.get("numero_recibo","—")),font=f_label,fill=azul)
    d.text((ancho-margen,y),"Emisión: "+str(datos.get("fecha_emision","—")),font=f_small,fill=azul,anchor="ra")
    y+=40
    # Tarjeta de apartamento, inquilino y periodo.
    card=(margen,y,ancho-margen,y+144)
    d.rounded_rectangle(card,radius=18,fill=claro)
    yy=y+20
    for lab,val in [("APARTAMENTO",datos.get("apartamento_texto","—")),("INQUILINO",datos.get("inquilino_nombre","—")),("PERIODO / CONCEPTO",datos.get("periodo","—"))]:
        d.text((margen+24,yy),lab,font=f_label,fill=azul)
        d.text((margen+245,yy),str(val)[:45],font=f_val,fill=azul)
        yy+=42
    y+=174
    d.line((margen,y,ancho-margen,y),fill=gris,width=2); y+=24
    def fila(lab,val,small=False):
        nonlocal y
        d.text((margen+18,y),str(lab).upper() if small else str(lab),font=f_label if not small else f_small,fill=gris_texto if small else azul)
        d.text((margen+300,y),str(val)[:55],font=f_val,fill=azul)
        y+=34 if not small else 29
    fila(datos.get("etiqueta_fecha_pago","FECHA DE PAGO"),datos.get("fecha_pago","—"),True)
    fila(datos.get("etiqueta_metodo_pago","MÉTODO DE PAGO"),datos.get("metodo_pago","—"),True)
    fila("RECIBIDO POR",datos.get("recibido_por","—"),True)
    if datos.get("detalle"):
        for lab,val in datos["detalle"]:
            fila(lab,val,True)
    d.line((margen,y,ancho-margen,y),fill=gris,width=2); y+=24
    fila(datos.get("etiqueta_monto_esperado","Monto esperado:"),_fmt_bs(datos.get("monto_esperado",0)))
    fila(datos.get("etiqueta_total_pagado","Total pagado a la fecha:"),_fmt_bs(datos.get("total_pagado_periodo",0)))
    saldo=float(datos.get("saldo_pendiente",0) or 0)
    fila("Estado:","PAGADO COMPLETO" if saldo<=0.009 else f"Saldo pendiente: {_fmt_bs(saldo)}")
    y+=8
    # Tarjeta monto recibido.
    h=104
    d.rounded_rectangle((margen,y,ancho-margen,y+h),radius=18,fill=claro,outline=azul,width=3)
    d.ellipse((margen+18,y+17,margen+88,y+87),fill=azul)
    d.text((margen+53,y+52),"Bs",font=f_label,fill=dorado,anchor="mm")
    d.text((margen+112,y+22),str(datos.get("etiqueta_monto_abono","MONTO RECIBIDO")).upper(),font=f_label,fill=azul)
    d.text((margen+112,y+52),_fmt_bs(datos.get("monto_pagado",0)),font=f_amount,fill=azul)
    y+=h+20
    d.rounded_rectangle((margen,y,ancho-margen,y+82),radius=14,fill=claro)
    d.text((margen+18,y+16),"Monto esperado:",font=f_small,fill=azul)
    d.text((ancho-margen-18,y+16),_fmt_bs(datos.get("monto_esperado",0)),font=f_label,fill=azul,anchor="ra")
    d.line((margen+18,y+42,ancho-margen-18,y+42),fill=gris,width=1)
    d.text((margen+18,y+53),"Estado:",font=f_small,fill=azul)
    d.text((ancho-margen-18,y+53),"PAGADO COMPLETO" if saldo<=0.009 else f"SALDO: {_fmt_bs(saldo)}",font=f_label,fill=azul,anchor="ra")
    y+=110
    if datos.get("observacion"):
        d.text((margen+18,y),f'Observación: {str(datos["observacion"])[:100]}',font=f_small,fill=gris_texto); y+=30
    d.line((margen,y,ancho-margen,y),fill=dorado,width=3); y+=18
    d.text((ancho//2,y),f'REGISTRADO POR: {datos.get("recibido_por","—")}',font=f_label,fill=azul,anchor="mt"); y+=28
    d.text((ancho//2,y),"¡Gracias por su pago!",font=_fuente(16,cursiva=True),fill=azul,anchor="mt"); y+=40
    buffer=io.BytesIO()
    img.crop((0,0,ancho,min(y,alto))).save(buffer,format="PNG",optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


def _logo_liviano_bytes():
    """Carga el logo horizontal institucional y lo reduce para incrustarlo en PDF."""
    ruta = LOGO_PATH if os.path.exists(LOGO_PATH) else LOGO_FALLBACK_PATH
    logo = Image.open(ruta).convert("RGBA")
    logo.thumbnail((900, 300), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    return buf.getvalue()


_COLOR_DEUDA = (183, 28, 28)          # rojo (RGB, PNG)
_COLOR_DEUDA_PDF = "#B71C1C"
_COLOR_ESTADO_REP = {
    "Pagado": "#2E7D32", "Parcial": "#E65100", "Pendiente": "#B71C1C",
    "Sin pago": "#B71C1C", "Por vencer": "#1565C0",
}


def _fmt_bs2(monto):
    """Dos decimales: en una deuda no se debe ocultar ningún centavo."""
    try:
        return f"Bs {float(monto):,.2f}"
    except (TypeError, ValueError):
        return "Bs 0.00"


def _fmt_fecha(f):
    return f.strftime("%d/%m/%Y") if f else "—"


MAX_FILAS_REPORTE = 12  # filas por tabla; las deudas siempre se muestran completas


def _recortar_filas(filas, maximo=MAX_FILAS_REPORTE):
    """Siempre muestra TODAS las filas con saldo (el inquilino debe ver de dónde sale su deuda)
    y completa con los meses pagados más recientes hasta 'maximo'. Devuelve (filas, omitidas)."""
    con_saldo = [i for i, f in enumerate(filas) if f["saldo"] > 0.009]
    pagadas = [i for i, f in enumerate(filas) if f["saldo"] <= 0.009]
    cupo = max(0, maximo - len(con_saldo))
    visibles = set(con_saldo) | set(pagadas[max(0, len(pagadas) - cupo):] if cupo else [])
    return [f for i, f in enumerate(filas) if i in visibles], len(filas) - len(visibles)


def _resumen_ultimo_pago(bloque):
    up = bloque.get("ultimo_pago")
    if not up:
        return "Sin pagos registrados"
    dias = bloque.get("dias_desde_ultimo_pago")
    hace = "hoy" if dias == 0 else (f"hace {dias} día" + ("s" if dias != 1 else ""))
    return f'{_fmt_fecha(up["fecha"])} ({hace}) - {_fmt_bs2(up["monto"])}'


def construir_datos_reporte_inquilino(apartamento, deuda, emitido_por=None):
    """'deuda' es el resultado de moras.deuda_real_inquilino() (con aplica=True)."""
    alq, elec = deuda["alquiler"], deuda["electricidad"]
    filas_alq, omit_alq = _recortar_filas(alq["filas"])
    filas_elec, omit_elec = _recortar_filas(elec["filas"])
    notas = []
    if alq["desde_ingreso_sin_registros"]:
        notas.append("No hay pagos de alquiler registrados: la deuda se calcula desde la fecha de ingreso.")
    if alq["por_vencer"] > 0.009:
        notas.append(f'Alquiler por vencer (aún no incluido en la deuda): {_fmt_bs2(alq["por_vencer"])}.')
    if omit_alq or omit_elec:
        notas.append("Se omiten meses anteriores ya pagados para abreviar el reporte.")
    return {
        "apartamento_texto": formatear_apartamento(apartamento),
        "inquilino_nombre": (apartamento or {}).get("inquilino_nombre") or "—",
        "fecha_emision": datetime.now(_ZONA_BOLIVIA).strftime("%d/%m/%Y %H:%M"),
        "fecha_corte": _fmt_fecha(deuda["fecha_corte"]),
        "ultimo_pago_alquiler": _resumen_ultimo_pago(alq),
        "ultimo_pago_electricidad": _resumen_ultimo_pago(elec),
        "filas_alquiler": filas_alq, "filas_electricidad": filas_elec,
        "meses_atrasados": alq["meses_atrasados"],
        "deuda_alquiler": alq["deuda"], "deuda_electricidad": elec["deuda"],
        "deuda_total": deuda["deuda_total"],
        "notas": notas,
        "emitido_por": emitido_por or "—",
    }


class _EncabezadoEstadoCuenta(Flowable):
    """Encabezado institucional con marco azul, logo blanco y banda azul/dorada diagonal."""
    def __init__(self, logo_bytes, height=30 * mm):
        super().__init__()
        self.logo_bytes = logo_bytes
        self.height = height
        self.width = 0

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return self.width, self.height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        navy = colors.HexColor(_AZUL)
        gold = colors.HexColor(_DORADO)
        # Panel blanco completo y marco institucional exterior.
        c.saveState()
        c.setFillColor(colors.white)
        c.rect(0, 0, w, h, stroke=0, fill=1)

        # Corte diagonal dorado y panel azul marino, como el diseño aprobado.
        split = w * 0.575
        band = 2.3 * mm
        slant = 7.0 * mm
        p = c.beginPath()
        p.moveTo(split - slant, 0)
        p.lineTo(split - slant + band, 0)
        p.lineTo(split + slant + band, h)
        p.lineTo(split + slant, h)
        p.close()
        c.setFillColor(gold)
        c.drawPath(p, stroke=0, fill=1)

        p = c.beginPath()
        p.moveTo(split - slant + band, 0)
        p.lineTo(w, 0)
        p.lineTo(w, h)
        p.lineTo(split + slant + band, h)
        p.close()
        c.setFillColor(navy)
        c.drawPath(p, stroke=0, fill=1)

        # Logo horizontal centrado en su panel blanco y ajustado sin deformación.
        if self.logo_bytes:
            try:
                from PIL import Image as PILImage
                logo_img = PILImage.open(io.BytesIO(self.logo_bytes))
                iw, ih = logo_img.size
                max_w, max_h = split - 16 * mm, h - 5 * mm
                scale = min(max_w / iw, max_h / ih)
                dw, dh = iw * scale, ih * scale
                x = (split - dw) / 2
                y = (h - dh) / 2
                c.drawImage(ImageReader(io.BytesIO(self.logo_bytes)), x, y,
                            width=dw, height=dh, mask='auto')
            except Exception:
                pass

        # Texto blanco centrado dentro de la zona azul, sin invadir el logo.
        right_center = (split + w) / 2 + 1.5 * mm
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 12.5)
        c.drawCentredString(right_center, h * 0.59, 'ESTADO DE CUENTA')
        c.setFont('Helvetica', 6.7)
        c.drawCentredString(right_center, h * 0.35, 'RESUMEN DE CUENTA DEL INQUILINO')

        # Filete dorado inferior y marco azul exterior.
        c.setFillColor(gold)
        c.rect(0, 0, w, 1.5 * mm, stroke=0, fill=1)
        c.setStrokeColor(navy)
        c.setLineWidth(1.25)
        c.rect(0.6, 0.6, w - 1.2, h - 1.2, stroke=1, fill=0)
        c.restoreState()


def generar_reporte_inquilino_pdf(datos: dict) -> bytes:
    from reportlab.platypus import HRFlowable, KeepTogether
    from reportlab.lib.styles import ParagraphStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=14 * mm, bottomMargin=14 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm,
                             title=f'Estado de cuenta - {datos["apartamento_texto"]}')
    ancho_util = letter[0] - 36 * mm
    # Con muchas filas se compacta el espaciado para que el reporte siga cabiendo en una hoja
    n_total = len(datos["filas_alquiler"]) + len(datos["filas_electricidad"])
    pad_fila, tam_fila = (3, 8.5) if n_total <= 14 else ((1.8, 8) if n_total <= 19 else (1.0, 7.5))
    base = getSampleStyleSheet()["Normal"]
    st_titulo = ParagraphStyle("t", parent=base, fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=colors.white)
    st_sub = ParagraphStyle("s", parent=base, fontSize=8.5, leading=11, textColor=colors.white)
    st_chico = ParagraphStyle("c", parent=base, fontSize=8, leading=10)
    st_nota = ParagraphStyle("n", parent=base, fontName="Helvetica-Oblique", fontSize=7.5, leading=10,
                              textColor=colors.Color(.33, .33, .33))
    st_seccion = ParagraphStyle("sec", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14,
                                 spaceBefore=8 if n_total <= 19 else 3, spaceAfter=4 if n_total <= 19 else 2)
    story = []

    # ---------- Encabezado institucional aprobado: marco azul + logo + corte diagonal dorado ----------
    logo_bytes = _logo_liviano_bytes() if os.path.exists(LOGO_PATH) or os.path.exists(LOGO_FALLBACK_PATH) else None
    story += [_EncabezadoEstadoCuenta(logo_bytes, height=30 * mm), Spacer(1, 7)]

    fechas = Table([[Paragraph(f'Fecha de corte: {datos["fecha_corte"]}', st_chico),
                     Paragraph(f'<para align="right">Emitido: {datos["fecha_emision"]}</para>', st_chico)]],
                   colWidths=[ancho_util / 2, ancho_util / 2])
    fechas.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [fechas, Spacer(1, 6)]

    # ---------- Datos generales: etiqueta a la izquierda, valor a la derecha ----------
    def tabla_datos(pares):
        t = Table([[Paragraph(f"<b>{k}</b>", st_chico), Paragraph(f'<para align="right">{v}</para>', st_chico)]
                   for k, v in pares], colWidths=[ancho_util * 0.38, ancho_util * 0.62])
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
        return t

    story.append(tabla_datos([
        ("Apartamento:", datos["apartamento_texto"]),
        ("Inquilino:", datos["inquilino_nombre"]),
        ("Último pago de alquiler:", datos["ultimo_pago_alquiler"]),
        ("Último pago de electricidad:", datos["ultimo_pago_electricidad"]),
    ]))
    story += [Spacer(1, 4), HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc"))]

    # ---------- Tablas por categoría ----------
    def tabla_categoria(titulo, filas, subtotal_txt):
        story.append(Paragraph(titulo, st_seccion))
        if not filas:
            story.append(Paragraph("Sin periodos registrados.", st_chico))
            return
        datos_t = [["Periodo", "Esperado", "Pagado", "Saldo", "Estado"]] + [
            [f["periodo"], _fmt_bs2(f["esperado"]), _fmt_bs2(f["pagado"]), _fmt_bs2(f["saldo"]), f["estado"]]
            for f in filas]
        t = Table(datos_t, repeatRows=1, hAlign="LEFT",
                  colWidths=[ancho_util * w for w in (0.27, 0.19, 0.19, 0.19, 0.16)])
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_AZUL)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), tam_fila),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
            ("ALIGN", (1, 0), (3, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), pad_fila), ("BOTTOMPADDING", (0, 0), (-1, -1), pad_fila),
        ]
        for i, f in enumerate(filas, start=1):
            estilo += [("TEXTCOLOR", (4, i), (4, i), colors.HexColor(_COLOR_ESTADO_REP.get(f["estado"], "#000000"))),
                       ("FONTNAME", (4, i), (4, i), "Helvetica-Bold")]
        t.setStyle(TableStyle(estilo))
        story.append(t)
        story.append(Paragraph(f'<para align="right"><b>{subtotal_txt}</b></para>', st_chico))

    n = datos["meses_atrasados"]
    tabla_categoria("Alquiler", datos["filas_alquiler"],
                    f'{n} mes{"es" if n != 1 else ""} atrasado{"s" if n != 1 else ""}  |  '
                    f'Deuda de alquiler: {_fmt_bs2(datos["deuda_alquiler"])}')
    tabla_categoria("Electricidad", datos["filas_electricidad"],
                    f'Deuda de electricidad: {_fmt_bs2(datos["deuda_electricidad"])}')
    story.append(Spacer(1, 10))

    # ---------- Caja resaltada con la deuda total (roja con deuda, verde si está al día) ----------
    debe = datos["deuda_total"] > 0.009
    caja = Table([["DEUDA TOTAL" if debe else "ESTADO: AL DÍA", _fmt_bs2(datos["deuda_total"])]],
                 colWidths=[ancho_util * 0.6, ancho_util * 0.4], rowHeights=[13 * mm])
    caja.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_COLOR_DEUDA_PDF if debe else _COLOR_ACENTO_PDF)),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (0, 0), 11), ("FONTSIZE", (1, 0), (1, 0), 16),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    pie = [Spacer(1, 6)]
    for nota in datos["notas"]:
        pie.append(Paragraph(nota, st_nota))
    pie += [Spacer(1, 6), HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc")),
            Spacer(1, 3), Paragraph(f'Emitido por: {datos["emitido_por"]}', st_chico)]
    story.append(KeepTogether([caja] + pie))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generar_reporte_inquilino_png(datos: dict) -> bytes:
    ancho = 820
    n_filas = len(datos["filas_alquiler"]) + len(datos["filas_electricidad"])
    alto_max = 760 + n_filas * 34 + len(datos["notas"]) * 26
    img = Image.new("RGB", (ancho, alto_max), "white")
    draw = ImageDraw.Draw(img)

    f_titulo = _fuente(26, negrita=True)
    f_sub = _fuente(14)
    f_label = _fuente(14, negrita=True)
    f_valor = _fuente(14)
    f_chico = _fuente(12)
    f_chico_b = _fuente(12, negrita=True)
    f_chico_i = _fuente(12, cursiva=True)
    f_seccion = _fuente(16, negrita=True)
    f_caja_label = _fuente(16, negrita=True)
    f_caja_monto = _fuente(28, negrita=True)

    margen = 48
    y = 28

    def ancho_texto(t, fuente):
        b = draw.textbbox((0, 0), t, font=fuente)
        return b[2] - b[0]

    def derecha(texto, fuente, x_der, yy, color="black"):
        draw.text((x_der - ancho_texto(texto, fuente), yy), texto, font=fuente, fill=color)

    # ---------- Encabezado institucional aprobado: marco, logo y panel azul diagonal ----------
    header_top = y
    header_h = 142
    x0, x1 = margen, ancho - margen
    header_w = x1 - x0
    split = x0 + int(header_w * 0.575)
    slant = 18
    band = 8
    # Fondo blanco y panel azul a la derecha.
    draw.rectangle((x0, header_top, x1, header_top + header_h), fill="white")
    draw.polygon([(split - slant + band, header_top + header_h),
                  (x1, header_top + header_h), (x1, header_top),
                  (split + slant + band, header_top)], fill=_AZUL)
    # Banda diagonal dorada entre ambos paneles.
    draw.polygon([(split - slant, header_top + header_h),
                  (split - slant + band, header_top + header_h),
                  (split + slant + band, header_top),
                  (split + slant, header_top)], fill=_DORADO)
    # Logo horizontal con proporción original, centrado en el panel blanco.
    ruta_logo = LOGO_PATH if os.path.exists(LOGO_PATH) else LOGO_FALLBACK_PATH
    if os.path.exists(ruta_logo):
        try:
            logo = Image.open(ruta_logo).convert("RGBA")
            max_w, max_h = split - x0 - 22, header_h - 14
            logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            lx = x0 + (split - x0 - logo.width) // 2
            ly = header_top + (header_h - logo.height) // 2
            img.paste(logo, (lx, ly), logo)
        except Exception:
            draw.text((x0 + 18, header_top + 45), "EQUISE", font=f_titulo, fill=_DORADO)
    # Título y subtítulo blancos, centrados dentro de la zona azul.
    cx = int((split + x1) / 2) + 8
    draw.text((cx, header_top + 48), "ESTADO DE CUENTA", font=_fuente(19, negrita=True),
              fill="white", anchor="mm")
    draw.text((cx, header_top + 82), "RESUMEN DE CUENTA DEL INQUILINO", font=_fuente(9),
              fill="white", anchor="mm")
    # Línea dorada inferior y marco azul marino completo.
    draw.rectangle((x0, header_top + header_h - 4, x1, header_top + header_h), fill=_DORADO)
    draw.rectangle((x0, header_top, x1, header_top + header_h), outline=_AZUL, width=4)
    y += header_h + 23

    draw.text((margen, y), f'Fecha de corte: {datos["fecha_corte"]}', font=f_chico, fill="black")
    derecha(f'Emitido: {datos["fecha_emision"]}', f_chico, ancho - margen, y)
    y += 32

    def fila(etiqueta, valor, yy):
        draw.text((margen, yy), etiqueta, font=f_label, fill="black")
        derecha(str(valor), f_valor, ancho - margen, yy)
        return yy + 31

    y = fila("Apartamento:", datos["apartamento_texto"], y)
    y = fila("Inquilino:", datos["inquilino_nombre"], y)
    y = fila("Último pago de alquiler:", datos["ultimo_pago_alquiler"], y)
    y = fila("Último pago de electricidad:", datos["ultimo_pago_electricidad"], y)
    y += 6
    draw.line([(margen, y), (ancho - margen, y)], fill="#cccccc", width=2)
    y += 20

    # ---------- Tablas ----------
    ancho_tabla = ancho - 2 * margen
    xs = [margen + 10]                                    # Periodo (izquierda)
    cols_der = [margen + 215, margen + 355, margen + 495]  # Esperado, Pagado, Saldo (alineados a la derecha)
    x_estado = margen + 525
    alto_fila = 32

    def tabla(titulo, filas, subtotal):
        nonlocal y
        draw.text((margen, y), titulo, font=f_seccion, fill="black")
        y += 30
        if not filas:
            draw.text((margen, y), "Sin periodos registrados.", font=f_chico_i, fill="#555555")
            y += 34
            return
        draw.rectangle([(margen, y), (ancho - margen, y + alto_fila)], fill="#2E4057")
        draw.text((xs[0], y + 8), "Periodo", font=f_chico_b, fill="white")
        for x, t in zip(cols_der, ("Esperado", "Pagado", "Saldo")):
            derecha(t, f_chico_b, x, y + 8, "white")
        draw.text((x_estado, y + 8), "Estado", font=f_chico_b, fill="white")
        y += alto_fila
        for f in filas:
            draw.text((xs[0], y + 8), f["periodo"], font=f_chico, fill="black")
            derecha(_fmt_bs2(f["esperado"]), f_chico, cols_der[0], y + 8)
            derecha(_fmt_bs2(f["pagado"]), f_chico, cols_der[1], y + 8)
            derecha(_fmt_bs2(f["saldo"]), f_chico_b if f["saldo"] > 0.009 else f_chico, cols_der[2], y + 8)
            draw.text((x_estado, y + 8), f["estado"], font=f_chico_b,
                      fill=_COLOR_ESTADO_REP.get(f["estado"], "#000000"))
            y += alto_fila
            draw.line([(margen, y), (ancho - margen, y)], fill="#e0e0e0", width=1)
        y += 8
        derecha(subtotal, f_chico_b, ancho - margen, y)
        y += 34

    n = datos["meses_atrasados"]
    tabla("Alquiler", datos["filas_alquiler"],
          f'{n} mes{"es" if n != 1 else ""} atrasado{"s" if n != 1 else ""}   |   '
          f'Deuda de alquiler: {_fmt_bs2(datos["deuda_alquiler"])}')
    tabla("Electricidad", datos["filas_electricidad"],
          f'Deuda de electricidad: {_fmt_bs2(datos["deuda_electricidad"])}')
    y += 4

    # ---------- Caja resaltada con la deuda total ----------
    debe = datos["deuda_total"] > 0.009
    caja_alto = 74
    draw.rounded_rectangle([(margen, y), (ancho - margen, y + caja_alto)], radius=10,
                           fill=_COLOR_DEUDA if debe else _COLOR_ACENTO)
    draw.text((margen + 20, y + caja_alto / 2 - 11), "DEUDA TOTAL" if debe else "ESTADO: AL DÍA",
              font=f_caja_label, fill="white")
    derecha(_fmt_bs2(datos["deuda_total"]), f_caja_monto, ancho - margen - 20, y + caja_alto / 2 - 18, "white")
    y += caja_alto + 22

    for nota in datos["notas"]:
        draw.text((margen, y), nota, font=f_chico_i, fill="#555555")
        y += 26
    y += 8
    draw.line([(margen, y), (ancho - margen, y)], fill="#cccccc", width=2)
    y += 18
    draw.text((margen, y), f'Emitido por: {datos["emitido_por"]}', font=f_chico, fill="black")
    y += 34

    buffer = io.BytesIO()
    img.crop((0, 0, ancho, min(y + 10, alto_max))).save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def hoy_bolivia():
    """Fecha de hoy en Bolivia (UTC-4). En Streamlit Cloud el servidor suele estar en UTC, y entre
    las 20:00 y las 24:00 de Bolivia date.today() ya marcaría el día siguiente, lo que adelantaría
    un día los vencimientos de alquiler."""
    return datetime.now(_ZONA_BOLIVIA).date()
