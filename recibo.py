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

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from PIL import Image, ImageDraw, ImageFont

# El servidor (Streamlit Cloud) corre en UTC, no en la hora de Bolivia (UTC-4).
# Sin esto, la hora de emisión del recibo saldría adelantada.
_ZONA_BOLIVIA = timezone(timedelta(hours=-4))

_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(_DIR, "assets", "logo_equise.png")
NOMBRE_RESIDENCIAL = "Residencial Equise"

_COLOR_ACENTO = (46, 125, 50)      # verde, para PNG (RGB)
_COLOR_ACENTO_PDF = "#2E7D32"      # mismo verde, para PDF

# PB=Planta Baja, PP=Primer Piso, SP=Segundo Piso, TP=Tercer Piso
_MAPA_PISO_ABREV = {"PB": "Planta Baja", "PP": "Primer Piso", "SP": "Segundo Piso", "TP": "Tercer Piso"}

_MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
          "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


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
# PDF — formato compacto, tipo comprobante
# ============================================================

def generar_recibo_pdf(datos: dict) -> bytes:
    buffer = io.BytesIO()
    ancho, alto_pagina = A5
    c = pdfcanvas.Canvas(buffer, pagesize=A5)

    margen = 11 * mm
    y = alto_pagina - margen

    # ---------- Encabezado: logo y título lado a lado (más compacto que apilados) ----------
    logo_w = logo_h = 16 * mm
    texto_x = margen
    if os.path.exists(LOGO_PATH):
        try:
            c.drawImage(LOGO_PATH, margen, y - logo_h, width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask="auto")
            texto_x = margen + logo_w + 4 * mm
        except Exception:
            pass

    c.setFont("Helvetica-Bold", 14)
    c.drawString(texto_x, y - 6 * mm, NOMBRE_RESIDENCIAL)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.Color(0.33, 0.33, 0.33))
    c.drawString(texto_x, y - 11.5 * mm, "Recibo de Pago de Alquiler")
    c.setFillColor(colors.black)
    y -= logo_h + 3 * mm

    c.setLineWidth(0.6)
    c.line(margen, y, ancho - margen, y)
    y -= 5.5 * mm

    c.setFont("Helvetica", 8)
    c.drawString(margen, y, f'Recibo N°: {datos["numero_recibo"]}')
    c.drawRightString(ancho - margen, y, f'Emitido: {datos["fecha_emision"]}')
    y -= 7 * mm

    def fila(etiqueta, valor, negrita_valor=False, tam=9.5):
        nonlocal y
        c.setFont("Helvetica-Bold", tam)
        c.drawString(margen, y, etiqueta)
        c.setFont("Helvetica-Bold" if negrita_valor else "Helvetica", tam)
        c.drawRightString(ancho - margen, y, str(valor))
        y -= 6 * mm

    fila("Apartamento:", datos["apartamento_texto"])
    fila("Inquilino:", datos["inquilino_nombre"])
    fila("Periodo:", datos["periodo"])
    fila("Fecha de pago:", datos["fecha_pago"])
    fila("Método de pago:", datos["metodo_pago"])

    y -= 1 * mm
    c.line(margen, y, ancho - margen, y)
    y -= 6 * mm

    fila("Monto esperado del mes:", _fmt_bs(datos["monto_esperado"]))
    fila("Total pagado a la fecha:", _fmt_bs(datos["total_pagado_periodo"]))
    saldo = datos["saldo_pendiente"]
    fila("Saldo pendiente:" if saldo > 0.009 else "Estado:",
         _fmt_bs(saldo) if saldo > 0.009 else "PAGADO COMPLETO", negrita_valor=True)
    y -= 2 * mm

    # ---------- Caja resaltada con el monto de este abono ----------
    caja_alto = 13 * mm
    y -= caja_alto
    c.setFillColor(colors.HexColor(_COLOR_ACENTO_PDF))
    c.roundRect(margen, y, ancho - 2 * margen, caja_alto, 2 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margen + 4 * mm, y + caja_alto / 2 - 1.5 * mm, "MONTO DE ESTE ABONO")
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(ancho - margen - 4 * mm, y + caja_alto / 2 - 2.2 * mm, _fmt_bs(datos["monto_pagado"]))
    c.setFillColor(colors.black)
    y -= 6 * mm

    if datos.get("observacion"):
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(margen, y, f'Observación: {datos["observacion"]}')
        y -= 6 * mm

    y -= 3 * mm
    c.line(margen, y, ancho - margen, y)
    y -= 4.5 * mm
    c.setFont("Helvetica", 7.5)
    c.drawString(margen, y, f'Recibido por: {datos["recibido_por"]}')

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# PNG — mismo diseño compacto, recortado a su contenido real
# ============================================================

def generar_recibo_png(datos: dict) -> bytes:
    ancho, alto_max = 820, 1100
    img = Image.new("RGB", (ancho, alto_max), "white")
    draw = ImageDraw.Draw(img)

    f_titulo = _fuente(26, negrita=True)
    f_sub = _fuente(14)
    f_label = _fuente(14, negrita=True)
    f_valor = _fuente(14)
    f_chico = _fuente(12)
    f_chico_i = _fuente(12, cursiva=True)
    f_caja_label = _fuente(14, negrita=True)
    f_caja_monto = _fuente(24, negrita=True)

    margen = 48
    y = 28

    # ---------- Encabezado: logo y título lado a lado ----------
    texto_x = margen
    logo_alto = 0
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo.thumbnail((92, 92))
            img.paste(logo, (margen, y), logo)
            texto_x = margen + logo.width + 18
            logo_alto = logo.height
        except Exception:
            pass

    draw.text((texto_x, y + 6), NOMBRE_RESIDENCIAL, font=f_titulo, fill="black")
    draw.text((texto_x, y + 42), "Recibo de Pago de Alquiler", font=f_sub, fill="#555555")
    y += max(logo_alto, 70) + 14

    draw.line([(margen, y), (ancho - margen, y)], fill="#cccccc", width=2)
    y += 20

    draw.text((margen, y), f'Recibo N°: {datos["numero_recibo"]}', font=f_chico, fill="black")
    texto_emitido = f'Emitido: {datos["fecha_emision"]}'
    bbox = draw.textbbox((0, 0), texto_emitido, font=f_chico)
    draw.text((ancho - margen - (bbox[2] - bbox[0]), y), texto_emitido, font=f_chico, fill="black")
    y += 32

    def fila(etiqueta, valor, yy, negrita_valor=False):
        draw.text((margen, yy), etiqueta, font=f_label, fill="black")
        fuente_valor = f_label if negrita_valor else f_valor
        texto = str(valor)
        bbox = draw.textbbox((0, 0), texto, font=fuente_valor)
        draw.text((ancho - margen - (bbox[2] - bbox[0]), yy), texto, font=fuente_valor, fill="black")
        return yy + 31

    y = fila("Apartamento:", datos["apartamento_texto"], y)
    y = fila("Inquilino:", datos["inquilino_nombre"], y)
    y = fila("Periodo:", datos["periodo"], y)
    y = fila("Fecha de pago:", datos["fecha_pago"], y)
    y = fila("Método de pago:", datos["metodo_pago"], y)

    y += 6
    draw.line([(margen, y), (ancho - margen, y)], fill="#cccccc", width=2)
    y += 20

    y = fila("Monto esperado del mes:", _fmt_bs(datos["monto_esperado"]), y)
    y = fila("Total pagado a la fecha:", _fmt_bs(datos["total_pagado_periodo"]), y)
    saldo = datos["saldo_pendiente"]
    y = fila("Saldo pendiente:" if saldo > 0.009 else "Estado:",
             _fmt_bs(saldo) if saldo > 0.009 else "PAGADO COMPLETO", y, negrita_valor=True)
    y += 10

    # ---------- Caja resaltada con el monto de este abono ----------
    caja_alto = 64
    draw.rounded_rectangle([(margen, y), (ancho - margen, y + caja_alto)], radius=10, fill=_COLOR_ACENTO)
    draw.text((margen + 18, y + caja_alto / 2 - 10), "MONTO DE ESTE ABONO", font=f_caja_label, fill="white")
    texto_monto = _fmt_bs(datos["monto_pagado"])
    bbox = draw.textbbox((0, 0), texto_monto, font=f_caja_monto)
    draw.text((ancho - margen - 18 - (bbox[2] - bbox[0]), y + caja_alto / 2 - 16), texto_monto,
              font=f_caja_monto, fill="white")
    y += caja_alto + 22

    if datos.get("observacion"):
        draw.text((margen, y), f'Observación: {datos["observacion"]}', font=f_chico_i, fill="#555555")
        y += 30

    y += 10
    draw.line([(margen, y), (ancho - margen, y)], fill="#cccccc", width=2)
    y += 18
    draw.text((margen, y), f'Recibido por: {datos["recibido_por"]}', font=f_chico, fill="black")
    y += 34

    buffer = io.BytesIO()
    img.crop((0, 0, ancho, min(y + 20, alto_max))).save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# ESTADO DE CUENTA POR APARTAMENTO (para entregar al inquilino)
# ============================================================

def _detalle_periodos(periodos, campo_pagos):
    """A partir de una lista de periodos (de un solo apartamento, con sus pagos embebidos),
    arma una fila por mes ya ordenada cronológicamente, con su estado (Pagado/Parcial/
    Pendiente), y devuelve también la deuda total de esa categoría."""
    def _clave_orden(p):
        idx = _MESES.index(p["mes"]) if p.get("mes") in _MESES else 0
        return (int(p.get("anio") or 0), idx)

    filas = []
    deuda_total = 0.0
    for p in sorted(periodos or [], key=_clave_orden):
        pagado = sum(float(pg.get("monto") or 0) for pg in (p.get(campo_pagos) or []))
        esperado = float(p.get("monto_esperado") or 0)
        saldo = round(esperado - pagado, 2)
        if saldo > 0.009:
            estado = "Pendiente" if pagado <= 0.009 else "Parcial"
        else:
            estado = "Pagado"
            saldo = 0.0
        filas.append({
            "periodo": f'{p.get("mes", "")} {p.get("anio", "")}'.strip(),
            "esperado": esperado, "pagado": round(pagado, 2), "saldo": saldo, "estado": estado,
        })
        deuda_total += saldo
    return filas, round(deuda_total, 2)


def construir_datos_estado_cuenta(apartamento, periodos_alquiler, periodos_electricidad):
    """periodos_alquiler / periodos_electricidad: listas de periodos YA FILTRADAS para un
    solo apartamento (con sus pagos embebidos), como las devuelve db.listar_periodos /
    db.listar_periodos_electricidad."""
    filas_alq, deuda_alq = _detalle_periodos(periodos_alquiler, "pagos")
    filas_elec, deuda_elec = _detalle_periodos(periodos_electricidad, "pagos_electricidad")
    return {
        "apartamento_texto": formatear_apartamento(apartamento),
        "inquilino_nombre": (apartamento or {}).get("inquilino_nombre") or "—",
        "fecha_emision": datetime.now(_ZONA_BOLIVIA).strftime("%d/%m/%Y %H:%M"),
        "filas_alquiler": filas_alq, "deuda_alquiler": deuda_alq,
        "filas_electricidad": filas_elec, "deuda_electricidad": deuda_elec,
        "deuda_total": round(deuda_alq + deuda_elec, 2),
    }


_COLOR_ESTADO = {"Pagado": "#2E7D32", "Parcial": "#E65100", "Pendiente": "#B71C1C"}


def generar_estado_cuenta_pdf(datos: dict) -> bytes:
    """A diferencia del recibo (tamaño fijo A5), el estado de cuenta puede tener muchos
    meses, así que usa reportlab Platypus (tablas con paginación automática) sobre una
    hoja carta, manteniendo el mismo estilo visual que el recibo."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=14 * mm, bottomMargin=14 * mm,
                             leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    story = []

    if os.path.exists(LOGO_PATH):
        try:
            story.append(RLImage(LOGO_PATH, width=20 * mm, height=20 * mm))
            story.append(Spacer(1, 4))
        except Exception:
            pass

    story.append(Paragraph(NOMBRE_RESIDENCIAL, styles["Title"]))
    story.append(Paragraph("Estado de Cuenta del Apartamento", styles["Normal"]))
    story.append(Paragraph(f'Emitido: {datos["fecha_emision"]}', styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f'<b>Apartamento:</b> {datos["apartamento_texto"]}', styles["Normal"]))
    story.append(Paragraph(f'<b>Inquilino:</b> {datos["inquilino_nombre"]}', styles["Normal"]))
    story.append(Spacer(1, 14))

    def tabla_categoria(titulo, filas, deuda):
        story.append(Paragraph(titulo, styles["Heading3"]))
        if not filas:
            story.append(Paragraph("Sin periodos registrados.", styles["Normal"]))
            story.append(Spacer(1, 10))
            return
        encabezado = ["Periodo", "Esperado", "Pagado", "Saldo", "Estado"]
        datos_tabla = [encabezado]
        for f in filas:
            datos_tabla.append([f["periodo"], _fmt_bs(f["esperado"]), _fmt_bs(f["pagado"]),
                                 _fmt_bs(f["saldo"]), f["estado"]])
        t = Table(datos_tabla, repeatRows=1, hAlign="LEFT",
                   colWidths=[32 * mm, 28 * mm, 28 * mm, 28 * mm, 24 * mm])
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E4057")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i, f in enumerate(filas, start=1):
            estilo.append(("TEXTCOLOR", (4, i), (4, i), colors.HexColor(_COLOR_ESTADO.get(f["estado"], "#000000"))))
            estilo.append(("FONTNAME", (4, i), (4, i), "Helvetica-Bold"))
        t.setStyle(TableStyle(estilo))
        story.append(t)
        story.append(Paragraph(f'<b>Subtotal deuda: {_fmt_bs(deuda)}</b>', styles["Normal"]))
        story.append(Spacer(1, 14))

    tabla_categoria("Alquiler", datos["filas_alquiler"], datos["deuda_alquiler"])
    tabla_categoria("Electricidad", datos["filas_electricidad"], datos["deuda_electricidad"])

    t_total = Table([["DEUDA TOTAL", _fmt_bs(datos["deuda_total"])]], colWidths=[100 * mm, 40 * mm], hAlign="LEFT")
    t_total.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_COLOR_ACENTO_PDF)),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 13),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_total)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generar_estado_cuenta_png(datos: dict) -> bytes:
    ancho = 820
    n_filas = len(datos["filas_alquiler"]) + len(datos["filas_electricidad"])
    alto_max = 420 + n_filas * 30 + 160
    img = Image.new("RGB", (ancho, alto_max), "white")
    draw = ImageDraw.Draw(img)

    f_titulo = _fuente(26, negrita=True)
    f_sub = _fuente(14)
    f_label = _fuente(14, negrita=True)
    f_seccion = _fuente(16, negrita=True)
    f_fila = _fuente(12)
    f_fila_b = _fuente(12, negrita=True)
    f_total_label = _fuente(16, negrita=True)
    f_total_monto = _fuente(22, negrita=True)

    margen = 48
    y = 28
    texto_x = margen
    logo_alto = 0
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo.thumbnail((92, 92))
            img.paste(logo, (margen, y), logo)
            texto_x = margen + logo.width + 18
            logo_alto = logo.height
        except Exception:
            pass

    draw.text((texto_x, y + 6), NOMBRE_RESIDENCIAL, font=f_titulo, fill="black")
    draw.text((texto_x, y + 42), "Estado de Cuenta del Apartamento", font=f_sub, fill="#555555")
    y += max(logo_alto, 70) + 14
    draw.line([(margen, y), (ancho - margen, y)], fill="#cccccc", width=2)
    y += 20

    draw.text((margen, y), f'Emitido: {datos["fecha_emision"]}', font=f_fila, fill="black")
    y += 28
    draw.text((margen, y), "Apartamento:", font=f_label, fill="black")
    draw.text((margen + 150, y), datos["apartamento_texto"], font=f_fila, fill="black")
    y += 26
    draw.text((margen, y), "Inquilino:", font=f_label, fill="black")
    draw.text((margen + 150, y), datos["inquilino_nombre"], font=f_fila, fill="black")
    y += 36

    col_x = [margen, margen + 170, margen + 330, margen + 480, margen + 620]

    def encabezado_tabla(yy):
        draw.rectangle([(margen, yy), (ancho - margen, yy + 28)], fill="#2E4057")
        etiquetas = ["Periodo", "Esperado", "Pagado", "Saldo", "Estado"]
        for x, et in zip(col_x, etiquetas):
            draw.text((x + 6, yy + 6), et, font=f_fila_b, fill="white")
        return yy + 32

    def fila_tabla(f, yy):
        valores = [f["periodo"], _fmt_bs(f["esperado"]), _fmt_bs(f["pagado"]), _fmt_bs(f["saldo"])]
        for x, val in zip(col_x, valores):
            draw.text((x + 6, yy), val, font=f_fila, fill="black")
        color_estado = _ESTADO_PNG.get(f["estado"], "black")
        draw.text((col_x[4] + 6, yy), f["estado"], font=f_fila_b, fill=color_estado)
        return yy + 28

    def seccion(titulo, filas, deuda, yy):
        draw.text((margen, yy), titulo, font=f_seccion, fill="black")
        yy += 30
        if not filas:
            draw.text((margen, yy), "Sin periodos registrados.", font=f_fila, fill="#777777")
            return yy + 34
        yy = encabezado_tabla(yy)
        for f in filas:
            yy = fila_tabla(f, yy)
        yy += 4
        texto_sub = f'Subtotal deuda: {_fmt_bs(deuda)}'
        draw.text((margen, yy), texto_sub, font=f_fila_b, fill="black")
        return yy + 38

    y = seccion("Alquiler", datos["filas_alquiler"], datos["deuda_alquiler"], y)
    y = seccion("Electricidad", datos["filas_electricidad"], datos["deuda_electricidad"], y)

    caja_alto = 66
    draw.rounded_rectangle([(margen, y), (ancho - margen, y + caja_alto)], radius=10, fill=_COLOR_ACENTO)
    draw.text((margen + 18, y + caja_alto / 2 - 12), "DEUDA TOTAL", font=f_total_label, fill="white")
    texto_total = _fmt_bs(datos["deuda_total"])
    bbox = draw.textbbox((0, 0), texto_total, font=f_total_monto)
    draw.text((ancho - margen - 18 - (bbox[2] - bbox[0]), y + caja_alto / 2 - 15), texto_total,
              font=f_total_monto, fill="white")
    y += caja_alto + 20

    buffer = io.BytesIO()
    img.crop((0, 0, ancho, min(y, alto_max))).save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


_ESTADO_PNG = {"Pagado": "#2E7D32", "Parcial": "#E65100", "Pendiente": "#B71C1C"}
