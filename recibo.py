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
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from PIL import Image, ImageDraw, ImageFont

_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(_DIR, "assets", "logo_equise.png")
NOMBRE_RESIDENCIAL = "Residencial Equise"
_ZONA_BOLIVIA = ZoneInfo("America/La_Paz")

_METODOS_ESTANDAR = ["Efectivo", "Transferencia", "QR", "Otro"]


def _fmt_bs(monto):
    try:
        return f"Bs {float(monto):,.2f}"
    except (TypeError, ValueError):
        return "Bs 0.00"


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
        "fecha_emision": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "apartamento_codigo": (apartamento or {}).get("codigo", ""),
        "apartamento_piso": (apartamento or {}).get("piso", ""),
        "inquilino_nombre": (apartamento or {}).get("inquilino_nombre") or "—",
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
# PDF
# ============================================================


def _texto_recibo(datos):
    """Texto y etiquetas comunes para recibos de alquiler y servicios."""
    titulo = datos.get("titulo") or "Recibo de Pago de Alquiler"
    servicio = (datos.get("servicio") or "").lower()
    if servicio == "agua":
        concepto = "AGUA"
    elif servicio == "electricidad":
        concepto = "ELECTRICIDAD"
    else:
        concepto = "ALQUILER"
    return titulo, concepto


def generar_recibo_pdf(datos: dict) -> bytes:
    """Genera un recibo A5 con diseño compacto, coherente con la marca Equise."""
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas as pdfcanvas
    from reportlab.lib.utils import ImageReader

    # Usar DejaVu también en PDF para conservar tildes, símbolos y consistencia.
    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    font_italic = "Helvetica-Oblique"
    try:
        regular_path = os.path.join(_DIR, "assets", "fonts", "DejaVuSans.ttf")
        bold_path = os.path.join(_DIR, "assets", "fonts", "DejaVuSans-Bold.ttf")
        italic_path = os.path.join(_DIR, "assets", "fonts", "DejaVuSans-Oblique.ttf")
        if os.path.exists(regular_path) and "EquiseDV" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("EquiseDV", regular_path))
            if os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont("EquiseDV-Bold", bold_path))
            if os.path.exists(italic_path):
                pdfmetrics.registerFont(TTFont("EquiseDV-Oblique", italic_path))
        if "EquiseDV" in pdfmetrics.getRegisteredFontNames():
            font_regular = "EquiseDV"
            font_bold = "EquiseDV-Bold" if "EquiseDV-Bold" in pdfmetrics.getRegisteredFontNames() else font_regular
            font_italic = "EquiseDV-Oblique" if "EquiseDV-Oblique" in pdfmetrics.getRegisteredFontNames() else font_regular
    except Exception:
        pass

    buffer = io.BytesIO()
    ancho, alto = A5
    c = pdfcanvas.Canvas(buffer, pagesize=A5)
    navy = colors.HexColor("#26384F")
    gold = colors.HexColor("#B99755")
    muted = colors.HexColor("#657080")
    light = colors.HexColor("#F3F5F7")
    green = colors.HexColor("#287D3C")
    red = colors.HexColor("#B3261E")
    margen = 12 * mm
    util = ancho - 2 * margen
    y = alto - 11 * mm

    # Cabecera horizontal: logo a la izquierda, identificación a la derecha.
    logo_size = 22 * mm
    if os.path.exists(LOGO_PATH):
        try:
            c.drawImage(LOGO_PATH, margen, y-logo_size, width=logo_size, height=logo_size,
                        preserveAspectRatio=True, anchor="c", mask="auto")
        except Exception:
            pass
    text_x = margen + logo_size + 5 * mm
    c.setFillColor(navy)
    c.setFont(font_bold, 15)
    c.drawString(text_x, y-7*mm, NOMBRE_RESIDENCIAL)
    titulo, concepto = _texto_recibo(datos)
    c.setFillColor(muted)
    c.setFont(font_regular, 8.5)
    c.drawString(text_x, y-13*mm, titulo)
    c.setFillColor(gold)
    c.setFont(font_bold, 7)
    c.drawString(text_x, y-18*mm, "EDIFICIO RESIDENCIAL")
    y -= logo_size + 5 * mm

    c.setStrokeColor(gold)
    c.setLineWidth(1.2)
    c.line(margen, y, ancho-margen, y)
    y -= 6 * mm

    c.setFillColor(navy)
    c.setFont(font_bold, 8.5)
    c.drawString(margen, y, f'Recibo N°: {datos.get("numero_recibo", "—")}')
    c.setFillColor(muted)
    c.setFont(font_regular, 7.5)
    c.drawRightString(ancho-margen, y, f'Emitido: {datos.get("fecha_emision", "—")}')
    y -= 7 * mm

    # Ficha de identificación.
    c.setFillColor(light)
    c.roundRect(margen, y-27*mm, util, 27*mm, 5, fill=1, stroke=0)
    y -= 5 * mm

    def fila_pdf(etiqueta, valor, value_bold=False, label_color=navy, max_font=8.3):
        nonlocal y
        valor = str(valor if valor not in (None, "") else "—")
        c.setFont(font_bold, 7.8)
        c.setFillColor(label_color)
        c.drawString(margen+4*mm, y, etiqueta)
        # Reducir tipografía para valores largos, sin salirse del margen.
        size = max_font
        available = util - 48*mm
        while size > 6 and pdfmetrics.stringWidth(valor, font_bold if value_bold else font_regular, size) > available:
            size -= .3
        c.setFont(font_bold if value_bold else font_regular, size)
        c.setFillColor(colors.HexColor("#171B21"))
        c.drawRightString(ancho-margen-4*mm, y, valor)
        y -= 5.4 * mm

    fila_pdf("Apartamento:", f'{datos.get("apartamento_codigo", "—")} ({datos.get("apartamento_piso", "—")})', max_font=8)
    fila_pdf("Inquilino:", datos.get("inquilino_nombre", "—"), max_font=8)
    fila_pdf("Periodo:", datos.get("periodo", "—"), max_font=8)
    fila_pdf("Fecha de pago:", datos.get("fecha_pago", "—"), max_font=8)
    fila_pdf("Método de pago:", datos.get("metodo_pago", "—"), max_font=8)
    y -= 3 * mm

    detalle = datos.get("detalle") or []
    if detalle:
        c.setFillColor(navy)
        c.setFont(font_bold, 8)
        c.drawString(margen, y, "DETALLE DEL SERVICIO" if datos.get("servicio") else "DETALLE")
        y -= 5 * mm
        for etiqueta, valor in detalle:
            fila_pdf(str(etiqueta), str(valor), max_font=7.8)
        y -= 1 * mm

    c.setStrokeColor(colors.HexColor("#D5D9DE"))
    c.setLineWidth(.6)
    c.line(margen, y, ancho-margen, y)
    y -= 6 * mm

    # Resumen económico.
    fila_pdf("Monto esperado del periodo:", _fmt_bs(datos.get("monto_esperado", 0)), max_font=8.5)
    fila_pdf("Total pagado a la fecha:", _fmt_bs(datos.get("total_pagado_periodo", 0)), max_font=8.5)
    saldo = float(datos.get("saldo_pendiente") or 0)
    if saldo > 0.009:
        fila_pdf("Saldo pendiente:", _fmt_bs(saldo), value_bold=True, label_color=red, max_font=8.5)
    else:
        fila_pdf("Estado:", "PAGADO COMPLETO", value_bold=True, label_color=green, max_font=8.5)

    # Monto del abono destacado.
    y -= 2 * mm
    monto_h = 15 * mm
    c.setFillColor(navy)
    c.roundRect(margen, y-monto_h, util, monto_h, 5, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(font_bold, 8)
    c.drawString(margen+4*mm, y-9*mm, "MONTO DE ESTE ABONO")
    c.setFont(font_bold, 14)
    c.drawRightString(ancho-margen-4*mm, y-9.5*mm, _fmt_bs(datos.get("monto_pagado", 0)))
    y -= monto_h + 5 * mm

    observacion = str(datos.get("observacion") or "").strip()
    if observacion:
        c.setFillColor(muted)
        c.setFont(font_italic, 7)
        # Wrap básico de observación para no cortarla en el borde.
        max_chars = 82
        lineas = textwrap.wrap("Observación: " + observacion, width=max_chars)[:2]
        for linea in lineas:
            c.drawString(margen, y, linea)
            y -= 4 * mm
        y -= 1 * mm

    # Pie fijo, separado del contenido.
    footer_y = 12 * mm
    c.setStrokeColor(colors.HexColor("#D5D9DE"))
    c.line(margen, footer_y+8*mm, ancho-margen, footer_y+8*mm)
    c.setFillColor(muted)
    c.setFont(font_regular, 7.2)
    c.drawString(margen, footer_y+3*mm, f'Recibido por: {datos.get("recibido_por") or "—"}')
    c.setFillColor(gold)
    c.setFont(font_bold, 6.5)
    c.drawRightString(ancho-margen, footer_y+3*mm, f'Emitido por: {datos.get("recibido_por") or "—"}')
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def generar_recibo_png(datos: dict) -> bytes:
    """PNG del recibo con estructura y jerarquía visual equivalentes al PDF."""
    ancho = 900
    margen = 52
    util = ancho - 2*margen
    navy = "#26384F"
    gold = "#B99755"
    muted = "#657080"
    light = "#F3F5F7"
    green = "#287D3C"
    red = "#B3261E"

    f_title = _fuente(29, negrita=True)
    f_sub = _fuente(17)
    f_brand = _fuente(12, negrita=True)
    f_label = _fuente(16, negrita=True)
    f_value = _fuente(16)
    f_small = _fuente(13)
    f_small_b = _fuente(13, negrita=True)
    f_amount = _fuente(25, negrita=True)
    titulo, concepto = _texto_recibo(datos)
    detalle = datos.get("detalle") or []
    observacion = str(datos.get("observacion") or "").strip()

    # Altura dinámica según los detalles y observaciones.
    alto = 850 + len(detalle)*36 + (42 if observacion else 0)
    img = Image.new("RGB", (ancho, alto), "white")
    draw = ImageDraw.Draw(img)
    y = 32

    # Cabecera horizontal.
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo.thumbnail((112, 112))
            img.paste(logo, (margen, y), logo)
        except Exception:
            pass
    tx = margen + 132
    draw.text((tx, y+8), NOMBRE_RESIDENCIAL, font=f_title, fill=navy)
    draw.text((tx, y+51), titulo, font=f_sub, fill=muted)
    draw.text((tx, y+82), "EDIFICIO RESIDENCIAL", font=f_brand, fill=gold)
    y += 130
    draw.rounded_rectangle((margen, y, ancho-margen, y+4), radius=2, fill=gold)
    y += 22

    # Número y fecha de emisión.
    draw.text((margen, y), f'Recibo N°: {datos.get("numero_recibo", "—")}', font=f_small_b, fill=navy)
    emitted = f'Emitido: {datos.get("fecha_emision", "—")}'
    eb = draw.textbbox((0,0), emitted, font=f_small)
    draw.text((ancho-margen-(eb[2]-eb[0]), y), emitted, font=f_small, fill=muted)
    y += 42

    # Tarjeta de identificación.
    draw.rounded_rectangle((margen, y, ancho-margen, y+220), radius=12, fill=light)
    y += 16

    def fila_png(etiqueta, valor, negrita=False, color=navy):
        nonlocal y
        valor = str(valor if valor not in (None, "") else "—")
        draw.text((margen+18, y), etiqueta, font=f_label, fill=color)
        font = f_label if negrita else f_value
        box = draw.textbbox((0,0), valor, font=font)
        maxw = ancho - margen - 18 - (margen+210)
        # Ajusta el tamaño si el dato es largo.
        if box[2]-box[0] > maxw:
            font = _fuente(14, negrita=negrita)
            box = draw.textbbox((0,0), valor, font=font)
        draw.text((ancho-margen-18-(box[2]-box[0]), y), valor, font=font, fill="#171B21")
        y += 37

    fila_png("Apartamento:", f'{datos.get("apartamento_codigo", "—")} ({datos.get("apartamento_piso", "—")})')
    fila_png("Inquilino:", datos.get("inquilino_nombre", "—"))
    fila_png("Periodo:", datos.get("periodo", "—"))
    fila_png("Fecha de pago:", datos.get("fecha_pago", "—"))
    fila_png("Método de pago:", datos.get("metodo_pago", "—"))
    y += 12

    if detalle:
        draw.text((margen, y), "DETALLE DEL SERVICIO" if datos.get("servicio") else "DETALLE", font=f_small_b, fill=navy)
        y += 30
        for etiqueta, valor in detalle:
            fila_png(str(etiqueta), str(valor))
        y += 6

    draw.line((margen, y, ancho-margen, y), fill="#D5D9DE", width=2)
    y += 22
    fila_png("Monto esperado del periodo:", _fmt_bs(datos.get("monto_esperado", 0)))
    fila_png("Total pagado a la fecha:", _fmt_bs(datos.get("total_pagado_periodo", 0)))
    saldo = float(datos.get("saldo_pendiente") or 0)
    if saldo > 0.009:
        fila_png("Saldo pendiente:", _fmt_bs(saldo), negrita=True, color=red)
    else:
        fila_png("Estado:", "PAGADO COMPLETO", negrita=True, color=green)
    y += 8

    # Franja de monto abonado.
    draw.rounded_rectangle((margen, y, ancho-margen, y+76), radius=12, fill=navy)
    draw.text((margen+20, y+25), "MONTO DE ESTE ABONO", font=f_small_b, fill="white")
    amount = _fmt_bs(datos.get("monto_pagado", 0))
    ab = draw.textbbox((0,0), amount, font=f_amount)
    draw.text((ancho-margen-20-(ab[2]-ab[0]), y+18), amount, font=f_amount, fill="white")
    y += 96

    if observacion:
        obs = "Observación: " + observacion
        draw.text((margen, y), obs[:105], font=f_small, fill=muted)
        y += 30

    # Pie.
    draw.line((margen, y, ancho-margen, y), fill="#D5D9DE", width=2)
    y += 17
    draw.text((margen, y), f'Recibido por: {datos.get("recibido_por") or "—"}', font=f_small, fill=muted)
    brand = f'Emitido por: {datos.get("recibido_por") or "—"}'
    bb = draw.textbbox((0,0), brand, font=f_small_b)
    draw.text((ancho-margen-(bb[2]-bb[0]), y), brand, font=f_small_b, fill=gold)
    y += 40

    out = io.BytesIO()
    img.crop((0, 0, ancho, y)).save(out, format="PNG")
    out.seek(0)
    return out.getvalue()


# ============================================================
# Funciones compartidas por la versión actual de app.py
# ============================================================

SERVICIOS = {
    "electricidad": {
        "nombre": "Electricidad", "unidad": "Kwh", "lectura_anterior": "kwh_anterior",
        "lectura_actual": "kwh_actual", "lectura_anterior_2": "kwh_anterior_2",
        "lectura_actual_2": "kwh_actual_2", "tarifa": "tarifa_kwh",
    },
    "agua": {
        "nombre": "Agua", "unidad": "m³", "lectura_anterior": "lectura_anterior",
        "lectura_actual": "lectura_actual", "tarifa": "tarifa_agua",
    },
}


def hoy_bolivia():
    """Fecha local de Bolivia, independiente de la zona del servidor."""
    return datetime.now(_ZONA_BOLIVIA).date()


def _detalle_lecturas(config, periodo, servicio=None, permitir_segundo_medidor=True):
    """Devuelve lecturas/tarifa imprimibles sin inventar consumos incoherentes.

    El segundo medidor solo se muestra cuando la unidad permite expresamente
    dos medidores; la aplicación determina esa condición por el código del apartamento.
    """
    servicio = servicio or ("agua" if config is SERVICIOS["agua"] else "electricidad")
    unidad = config["unidad"]
    if servicio == "electricidad":
        ant1, act1 = periodo.get("kwh_anterior"), periodo.get("kwh_actual")
        ant2, act2 = periodo.get("kwh_anterior_2"), periodo.get("kwh_actual_2")
        dos = permitir_segundo_medidor and ant2 is not None and act2 is not None
        if dos:
            filas = [("Medidor 1 - anterior:", f"{float(ant1 or 0):g} {unidad}"),
                     ("Medidor 1 - actual:", f"{float(act1 or 0):g} {unidad}"),
                     ("Medidor 2 - anterior:", f"{float(ant2):g} {unidad}"),
                     ("Medidor 2 - actual:", f"{float(act2):g} {unidad}")]
            consumo = max(float(act1 or 0)-float(ant1 or 0), 0) + max(float(act2)-float(ant2), 0)
        else:
            filas = [("Lectura anterior:", f"{float(ant1 or 0):g} {unidad}"),
                     ("Lectura actual:", f"{float(act1 or 0):g} {unidad}")]
            consumo = max(float(act1 or 0)-float(ant1 or 0), 0)
        tarifa = float(periodo.get("tarifa_kwh") or 0)
        esperado = float(periodo.get("monto_esperado") or 0)
        if abs(consumo * tarifa - esperado) < 0.011 or abs(__import__("math").floor(consumo * tarifa + 0.5) - esperado) < 0.011:
            filas.append(("Consumo total:" if dos else "Consumo:", f"{consumo:g} {unidad}"))
            filas.append(("Tarifa:", f"Bs {tarifa:.2f} por {unidad}"))
        return filas
    anterior = float(periodo.get("lectura_anterior") or 0)
    actual = float(periodo.get("lectura_actual") or 0)
    consumo = max(actual-anterior, 0)
    tarifa = float(periodo.get("tarifa_agua") or 0)
    esperado = float(periodo.get("monto_esperado") or 0)
    filas = [("Lectura anterior:", f"{anterior:g} {unidad}"), ("Lectura actual:", f"{actual:g} {unidad}")]
    if abs(consumo * tarifa - esperado) < 0.011 or abs(__import__("math").floor(consumo * tarifa + 0.5) - esperado) < 0.011:
        filas.extend([("Consumo:", f"{consumo:g} {unidad}"), ("Tarifa:", f"Bs {tarifa:.2f} por {unidad}")])
    return filas


def _es_apartamento_dos(apartamento):
    """Identifica el apartamento 2 por su código visible, no por el ID de BD.

    Los IDs internos pueden cambiar y no necesariamente coinciden con el número
    del apartamento. Se aceptan códigos como 'TP- APARTAMENTO 2' o 'APTO 2'.
    """
    import re
    codigo = str((apartamento or {}).get("codigo") or "").upper().strip()
    return bool(re.search(r"\b(?:APARTAMENTO|APTO\.?|DEPTO\.?|DPTO\.?)\s*0*2\b", codigo))


def construir_datos_recibo_servicio(servicio, pago, periodo, apartamento, total_pagado_periodo, recibido_por):
    if servicio not in SERVICIOS:
        raise ValueError(f"Servicio no válido: {servicio}")
    datos = construir_datos_recibo(pago, periodo, apartamento, total_pagado_periodo, recibido_por)
    config = SERVICIOS[servicio]
    datos["titulo"] = f"Recibo de Pago de {config['nombre']}"
    datos["servicio"] = servicio
    permitir_segundo = servicio == "electricidad" and _es_apartamento_dos(apartamento)
    datos["detalle"] = _detalle_lecturas(config, periodo, servicio, permitir_segundo_medidor=permitir_segundo)
    return datos


def construir_datos_reporte_inquilino(apartamento, deuda, emitido_por=None):
    """Normaliza los datos para un estado de cuenta individual."""
    return {
        "apartamento": dict(apartamento or {}),
        "deuda": dict(deuda or {}) if isinstance(deuda, dict) else deuda,
        "fecha_emision": datetime.now(_ZONA_BOLIVIA).strftime("%d/%m/%Y %H:%M"),
        "emitido_por": emitido_por or "—",
        "numero_recibo": f"EC-{int((apartamento or {}).get('id') or 0):06d}",
        "apartamento_codigo": (apartamento or {}).get("codigo") or "—",
        "apartamento_piso": (apartamento or {}).get("piso") or "—",
        "inquilino_nombre": (apartamento or {}).get("inquilino_nombre") or "—",
        "monto_esperado": float((deuda or {}).get("monto_esperado") or 0) if isinstance(deuda, dict) else 0,
        "total_pagado_periodo": float((deuda or {}).get("total_pagado") or 0) if isinstance(deuda, dict) else 0,
        "saldo_pendiente": float((deuda or {}).get("deuda_total") or 0) if isinstance(deuda, dict) else 0,
    }


def generar_reporte_inquilino_pdf(datos):
    """Genera un estado de cuenta individual en PDF."""
    from reportlab.lib.pagesizes import A4
    buffer = io.BytesIO()
    ancho, alto = A4
    c = pdfcanvas.Canvas(buffer, pagesize=A4)
    margen, y = 18 * mm, alto - 20 * mm
    if os.path.exists(LOGO_PATH):
        try:
            c.drawImage(LOGO_PATH, (ancho-25*mm)/2, y-25*mm, width=25*mm, height=25*mm, preserveAspectRatio=True, mask="auto")
            y -= 30*mm
        except Exception:
            pass
    c.setFont("Helvetica-Bold", 16); c.drawCentredString(ancho/2, y, NOMBRE_RESIDENCIAL); y -= 9*mm
    c.setFont("Helvetica-Bold", 12); c.drawCentredString(ancho/2, y, "Estado de cuenta del inquilino"); y -= 12*mm
    c.setFont("Helvetica", 10)
    for label, key in [("Código de apartamento", "apartamento_codigo"), ("Piso", "apartamento_piso"), ("Inquilino", "inquilino_nombre"), ("Fecha de emisión", "fecha_emision"), ("Emitido por", "emitido_por")]:
        c.drawString(margen, y, f"{label}: {datos.get(key, '—')}"); y -= 7*mm
    y -= 3*mm; c.line(margen, y, ancho-margen, y); y -= 9*mm
    deuda = datos.get("deuda") or {}
    if isinstance(deuda, dict):
        for key, value in deuda.items():
            if isinstance(value, (str, int, float)) or value is None:
                label = str(key).replace("_", " ").capitalize()
                c.drawString(margen, y, f"{label}: {value if value is not None else '—'}"); y -= 7*mm
                if y < 25*mm:
                    c.showPage(); y = alto-20*mm; c.setFont("Helvetica", 10)
    c.save(); buffer.seek(0); return buffer.getvalue()


def generar_reporte_inquilino_png(datos):
    """Genera una vista PNG sencilla del estado de cuenta individual."""
    ancho, alto = 1000, 1200
    img = Image.new("RGB", (ancho, alto), "white")
    draw = ImageDraw.Draw(img)
    f_t = _fuente(30, negrita=True); f_l = _fuente(20, negrita=True); f_v = _fuente(18)
    y = 30
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA"); logo.thumbnail((160, 160))
            img.paste(logo, ((ancho-logo.width)//2, y), logo); y += logo.height + 20
        except Exception:
            pass
    title = NOMBRE_RESIDENCIAL
    draw.text(((ancho-draw.textbbox((0,0),title,font=f_t)[2])//2,y), title, fill="black", font=f_t); y += 55
    draw.text((60,y), "Estado de cuenta del inquilino", fill="black", font=f_l); y += 45
    for label,key in [("Apartamento", "apartamento_codigo"), ("Piso", "apartamento_piso"), ("Inquilino", "inquilino_nombre"), ("Fecha de emisión", "fecha_emision"), ("Emitido por", "emitido_por")]:
        draw.text((60,y), f"{label}: {datos.get(key,'—')}", fill="black", font=f_v); y += 34
    draw.line((60,y,940,y), fill="#999999", width=2); y += 20
    deuda = datos.get("deuda") or {}
    if isinstance(deuda, dict):
        for key,value in deuda.items():
            if isinstance(value,(str,int,float)) or value is None:
                draw.text((60,y), f"{str(key).replace('_',' ').capitalize()}: {value if value is not None else '—'}", fill="black", font=f_v); y += 32
                if y > alto-40: break
    buf=io.BytesIO(); img.crop((0,0,ancho,min(y+30,alto))).save(buf,format="PNG"); buf.seek(0); return buf.getvalue()


# ---------------------------------------------------------------------------
# Estado de cuenta detallado del inquilino (versión corregida)
# Conserva el detalle de alquiler y electricidad que calcula moras.py.
# ---------------------------------------------------------------------------
def construir_datos_reporte_inquilino(apartamento, deuda, emitido_por=None):
    deuda = dict(deuda or {}) if isinstance(deuda, dict) else {}
    ultimo_alq = deuda.get("alquiler", {}).get("ultimo_pago") or {}
    ultimo_elec = deuda.get("electricidad", {}).get("ultimo_pago") or {}
    def fecha_txt(valor):
        return valor.strftime("%d/%m/%Y") if hasattr(valor, "strftime") else (str(valor)[:10] if valor else "Sin pagos")
    ahora = datetime.now(_ZONA_BOLIVIA)
    corte = deuda.get("fecha_corte")
    return {
        "apartamento": dict(apartamento or {}), "deuda": deuda,
        "fecha_emision": ahora.strftime("%d/%m/%Y %H:%M"),
        "fecha_corte": fecha_txt(corte), "emitido_por": emitido_por or "—",
        "numero_recibo": f"EC-{int((apartamento or {}).get('id') or 0):06d}",
        "apartamento_codigo": (apartamento or {}).get("codigo") or "—",
        "apartamento_piso": (apartamento or {}).get("piso") or "—",
        "inquilino_nombre": (apartamento or {}).get("inquilino_nombre") or "—",
        "ultimo_pago_alquiler": ultimo_alq,
        "ultimo_pago_electricidad": ultimo_elec,
        "deuda_alquiler": float(deuda.get("alquiler", {}).get("deuda") or 0),
        "deuda_electricidad": float(deuda.get("electricidad", {}).get("deuda") or 0),
        "deuda_total": float(deuda.get("deuda_total") or 0),
        "aplica": bool(deuda.get("aplica", True)), "motivo": deuda.get("motivo") or "",
    }


def _fecha_y_monto_ultimo(ultimo):
    if not ultimo:
        return "Sin pagos registrados"
    fecha = ultimo.get("fecha")
    if hasattr(fecha, "strftime"):
        fecha = fecha.strftime("%d/%m/%Y")
    elif fecha:
        fecha = str(fecha)[:10]
    else:
        fecha = "Fecha no disponible"
    return f"{fecha} - {_fmt_bs(ultimo.get('monto') or 0)}"


def generar_reporte_inquilino_pdf(datos):
    """PDF con tablas detalladas de alquiler y electricidad y resumen de deuda."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, HRFlowable
    from reportlab.lib.utils import ImageReader

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=14*mm, leftMargin=14*mm,
                            topMargin=12*mm, bottomMargin=12*mm, title="Estado de cuenta del inquilino")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ECHeader", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=18, leading=22, alignment=TA_LEFT, textColor=colors.HexColor("#111111"), spaceAfter=2))
    styles.add(ParagraphStyle(name="ECSub", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#555555"), leading=13))
    styles.add(ParagraphStyle(name="ECTableHead", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white))
    styles.add(ParagraphStyle(name="ECTable", parent=styles["Normal"], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="ECTableRight", parent=styles["ECTable"], alignment=TA_RIGHT))
    story=[]
    header_cells=[]
    if os.path.exists(LOGO_PATH):
        try:
            logo=RLImage(LOGO_PATH, width=23*mm, height=23*mm, kind="proportional")
            header_cells.append(logo)
        except Exception:
            header_cells.append(Paragraph("", styles["Normal"]))
    else:
        header_cells.append(Paragraph("", styles["Normal"]))
    header_cells.append([Paragraph("Residencial Equise", styles["ECHeader"]), Paragraph("Estado de Cuenta del Inquilino", styles["ECSub"])])
    ht=Table([header_cells], colWidths=[27*mm, 150*mm])
    ht.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [ht, Spacer(1,4*mm), HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#BBBBBB")), Spacer(1,3*mm)]
    d=datos.get("deuda") or {}
    corte=datos.get("fecha_corte") or "—"
    story.append(Paragraph(f"Fecha de corte: {corte} <font color='#777777'>|</font> Emitido: {datos.get('fecha_emision','—')}", styles["ECTable"]))
    story.append(Spacer(1,2*mm))
    apto=f"{datos.get('apartamento_codigo','—')} - {datos.get('apartamento_piso','—')}"
    for label,value in [("Apartamento:",apto),("Inquilino:",datos.get("inquilino_nombre","—")),
                        ("Último pago de alquiler:",_fecha_y_monto_ultimo(datos.get("ultimo_pago_alquiler"))),
                        ("Último pago de electricidad:",_fecha_y_monto_ultimo(datos.get("ultimo_pago_electricidad")))]:
        story.append(Paragraph(f"<b>{label}</b> {value}", styles["ECTable"]))
        story.append(Spacer(1,1.2*mm))
    story += [Spacer(1,2*mm), HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#BBBBBB")), Spacer(1,3*mm)]

    def tabla_servicio(titulo, bloque):
        story.append(Paragraph(f"<b>{titulo}</b>", styles["Heading3"]))
        filas=[[Paragraph(x,styles["ECTableHead"]) for x in ("Periodo","Esperado","Pagado","Saldo","Estado")]]
        for f in (bloque or {}).get("filas",[]):
            estado=str(f.get("estado") or "—")
            filas.append([Paragraph(str(f.get("periodo") or "—"),styles["ECTable"]),
                          Paragraph(_fmt_bs(f.get("esperado")),styles["ECTableRight"]),
                          Paragraph(_fmt_bs(f.get("pagado")),styles["ECTableRight"]),
                          Paragraph(_fmt_bs(f.get("saldo")),styles["ECTableRight"]),
                          Paragraph(estado,styles["ECTable"])])
        if len(filas)==1:
            filas.append([Paragraph("Sin periodos registrados",styles["ECTable"]),"","","",""])
        t=Table(filas, colWidths=[43*mm,32*mm,32*mm,25*mm,35*mm], repeatRows=1, hAlign="LEFT")
        cmds=[("BACKGROUND",(0,0),(-1,0),colors.HexColor("#30425B")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
              ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
              ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
              ("LINEBELOW",(0,1),(-1,-1),0.35,colors.HexColor("#D7D7D7"))]
        for ri,row in enumerate(filas[1:],1):
            if len(row)>4 and isinstance(row[4],Paragraph) and "Pagado" in str((bloque or {}).get("filas",[])[ri-1].get("estado","")):
                cmds.append(("TEXTCOLOR",(4,ri),(4,ri),colors.HexColor("#27823B")))
        t.setStyle(TableStyle(cmds)); story.append(t); story.append(Spacer(1,2*mm))
        deuda_serv=float((bloque or {}).get("deuda") or 0)
        story.append(Paragraph(f"<b>Deuda de {titulo.lower()}: {_fmt_bs(deuda_serv)}</b>", ParagraphStyle("right_"+titulo,parent=styles["ECTable"],alignment=TA_RIGHT)))
        story.append(Spacer(1,3*mm))

    tabla_servicio("Alquiler",d.get("alquiler",{}))
    tabla_servicio("Electricidad",d.get("electricidad",{}))
    total=float(d.get("deuda_total") or 0)
    al_dia=total <= 0.009
    estado_txt="ESTADO: AL DÍA" if al_dia else "ESTADO: DEUDA PENDIENTE"
    final=Table([[Paragraph(f"<b>{estado_txt}</b>",styles["Heading3"]),Paragraph(f"<b>{_fmt_bs(total)}</b>",ParagraphStyle("total",parent=styles["Heading2"],alignment=TA_RIGHT,textColor=colors.white))]],colWidths=[100*mm,67*mm])
    final.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#2E7D32" if al_dia else "#B3261E")),("TEXTCOLOR",(0,0),(-1,-1),colors.white),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story += [final,Spacer(1,6*mm),HRFlowable(width="100%",thickness=0.7,color=colors.HexColor("#BBBBBB")),Spacer(1,3*mm),Paragraph(f"Emitido por: {datos.get('emitido_por') or '—'}",styles["ECTable"])]
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generar_reporte_inquilino_png(datos):
    """PNG detallado con tablas de alquiler/electricidad y resumen visual de deuda."""
    from PIL import ImageColor
    ancho=1000; margen=58; ancho_util=ancho-2*margen
    d=datos.get("deuda") or {}
    alquiler=(d.get("alquiler") or {}); electricidad=(d.get("electricidad") or {})
    filas_alq=alquiler.get("filas") or []; filas_elec=electricidad.get("filas") or []
    alto=310 + 56*(len(filas_alq)+len(filas_elec)) + 170
    img=Image.new("RGB",(ancho,alto),"white"); draw=ImageDraw.Draw(img)
    ft=_fuente(31,negrita=True); fs=_fuente(17); fb=_fuente(17,negrita=True); fc=_fuente(14); fcb=_fuente(14,negrita=True)
    y=30
    if os.path.exists(LOGO_PATH):
        try:
            logo=Image.open(LOGO_PATH).convert("RGB"); logo.thumbnail((112,112))
            img.paste(logo,(margen,y)); x_text=margen+132
        except Exception: x_text=margen
    else: x_text=margen
    draw.text((x_text,y+8),"Residencial Equise",font=ft,fill="#111111")
    draw.text((x_text,y+52),"Estado de Cuenta del Inquilino",font=fs,fill="#555555")
    y+=128; draw.line((margen,y,ancho-margen,y),fill="#BBBBBB",width=2); y+=20
    def line(label,value):
        nonlocal y
        draw.text((margen,y),label,font=fb,fill="#111111")
        text=str(value or "—"); bbox=draw.textbbox((0,0),text,font=fs)
        draw.text((ancho-margen-(bbox[2]-bbox[0]),y),text,font=fs,fill="#111111")
        y+=35
    line("Fecha de corte:",datos.get("fecha_corte","—"))
    line("Emitido:",datos.get("fecha_emision","—"))
    line("Apartamento:",f"{datos.get('apartamento_codigo','—')} - {datos.get('apartamento_piso','—')}")
    line("Inquilino:",datos.get("inquilino_nombre","—"))
    line("Último pago de alquiler:",_fecha_y_monto_ultimo(datos.get("ultimo_pago_alquiler")))
    line("Último pago de electricidad:",_fecha_y_monto_ultimo(datos.get("ultimo_pago_electricidad")))
    y+=5; draw.line((margen,y,ancho-margen,y),fill="#BBBBBB",width=2); y+=18
    cols=[margen,margen+190,margen+380,margen+560,margen+690,ancho-margen]
    def tabla(titulo,bloque,filas):
        nonlocal y
        draw.text((margen,y),titulo,font=fb,fill="#111111"); y+=25
        draw.rectangle((margen,y,ancho-margen,y+38),fill="#30425B")
        heads=["Periodo","Esperado","Pagado","Saldo","Estado"]
        for i,h in enumerate(heads): draw.text((cols[i]+8,y+10),h,font=fcb,fill="white")
        y+=38
        if not filas:
            draw.text((cols[0]+8,y+9),"Sin periodos registrados",font=fc,fill="#222222"); y+=34
        for f in filas:
            vals=[f.get("periodo","—"),_fmt_bs(f.get("esperado")),_fmt_bs(f.get("pagado")),_fmt_bs(f.get("saldo")),f.get("estado","—")]
            for i,val in enumerate(vals):
                font=fcb if i==4 and str(val).lower().startswith("pagado") else fc
                color="#27823B" if i==4 and str(val).lower().startswith("pagado") else "#111111"
                draw.text((cols[i]+8,y+9),str(val),font=font,fill=color)
            y+=34; draw.line((margen,y,ancho-margen,y),fill="#DDDDDD",width=1)
        y+=5
        draw.text((margen,y),f"Deuda de {titulo.lower()}: {_fmt_bs(bloque.get('deuda') or 0)}",font=fcb,fill="#111111")
        y+=36
    tabla("Alquiler",alquiler,filas_alq)
    tabla("Electricidad",electricidad,filas_elec)
    total=float(d.get("deuda_total") or 0); al_dia=total<=0.009
    color="#2E7D32" if al_dia else "#B3261E"
    draw.rounded_rectangle((margen,y,ancho-margen,y+76),radius=12,fill=color)
    estado="ESTADO: AL DÍA" if al_dia else "ESTADO: DEUDA PENDIENTE"
    draw.text((margen+20,y+22),estado,font=fb,fill="white")
    monto=_fmt_bs(total); bbox=draw.textbbox((0,0),monto,font=ft)
    draw.text((ancho-margen-20-(bbox[2]-bbox[0]),y+18),monto,font=ft,fill="white")
    y+=100; draw.line((margen,y,ancho-margen,y),fill="#BBBBBB",width=2); y+=18
    draw.text((margen,y),f"Emitido por: {datos.get('emitido_por') or '—'}",font=fc,fill="#111111")
    out=io.BytesIO(); img.crop((0,0,ancho,y+35)).save(out,format="PNG"); out.seek(0); return out.getvalue()
