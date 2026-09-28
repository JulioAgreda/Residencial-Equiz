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

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from PIL import Image, ImageDraw, ImageFont

_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(_DIR, "assets", "logo_equise.png")
NOMBRE_RESIDENCIAL = "Residencial Equise"

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
# PDF
# ============================================================

def generar_recibo_pdf(datos: dict) -> bytes:
    buffer = io.BytesIO()
    ancho, alto = A5
    c = pdfcanvas.Canvas(buffer, pagesize=A5)

    margen = 12 * mm
    y = alto - margen

    if os.path.exists(LOGO_PATH):
        try:
            logo_w = logo_h = 22 * mm
            c.drawImage(LOGO_PATH, (ancho - logo_w) / 2, y - logo_h, width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask="auto")
            y -= logo_h + 4 * mm
        except Exception:
            pass

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(ancho / 2, y, NOMBRE_RESIDENCIAL)
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawCentredString(ancho / 2, y, "Recibo de Pago de Alquiler")
    y -= 8 * mm

    c.setLineWidth(0.6)
    c.line(margen, y, ancho - margen, y)
    y -= 7 * mm

    c.setFont("Helvetica", 9)
    c.drawString(margen, y, f'Recibo N°: {datos["numero_recibo"]}')
    c.drawRightString(ancho - margen, y, f'Emitido: {datos["fecha_emision"]}')
    y -= 8 * mm

    def fila(etiqueta, valor, negrita_valor=False, tam=9.5):
        nonlocal y
        c.setFont("Helvetica-Bold", tam)
        c.drawString(margen, y, etiqueta)
        c.setFont("Helvetica-Bold" if negrita_valor else "Helvetica", tam)
        c.drawRightString(ancho - margen, y, str(valor))
        y -= 6.8 * mm

    fila("Apartamento:", f'{datos["apartamento_codigo"]} ({datos["apartamento_piso"]})')
    fila("Inquilino:", datos["inquilino_nombre"])
    fila("Periodo:", datos["periodo"])
    fila("Fecha de pago:", datos["fecha_pago"])
    fila("Método de pago:", datos["metodo_pago"])

    y -= 2 * mm
    c.line(margen, y, ancho - margen, y)
    y -= 7 * mm

    fila("Monto esperado del mes:", _fmt_bs(datos["monto_esperado"]))
    fila("Total pagado a la fecha:", _fmt_bs(datos["total_pagado_periodo"]))
    saldo = datos["saldo_pendiente"]
    fila("Saldo pendiente:" if saldo > 0.009 else "Estado:",
         _fmt_bs(saldo) if saldo > 0.009 else "PAGADO COMPLETO", negrita_valor=True)

    y -= 3 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margen, y, "Monto de este abono:")
    c.drawRightString(ancho - margen, y, _fmt_bs(datos["monto_pagado"]))
    y -= 10 * mm

    if datos.get("observacion"):
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(margen, y, f'Observación: {datos["observacion"]}')
        y -= 8 * mm

    y -= 6 * mm
    c.line(margen, y, ancho - margen, y)
    y -= 5 * mm
    c.setFont("Helvetica", 8)
    c.drawString(margen, y, f'Recibido por: {datos["recibido_por"]}')

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# PNG
# ============================================================

def generar_recibo_png(datos: dict) -> bytes:
    ancho, alto = 900, 1200
    img = Image.new("RGB", (ancho, alto), "white")
    draw = ImageDraw.Draw(img)

    f_titulo = _fuente(30, negrita=True)
    f_sub = _fuente(17)
    f_label = _fuente(16, negrita=True)
    f_valor = _fuente(16)
    f_chico = _fuente(13)
    f_chico_i = _fuente(13, cursiva=True)

    margen = 55
    y = 30

    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo.thumbnail((150, 150))
            img.paste(logo, ((ancho - logo.width) // 2, y), logo)
            y += logo.height + 15
        except Exception:
            pass

    def centrado(texto, fuente, yy, color="black"):
        bbox = draw.textbbox((0, 0), texto, font=fuente)
        w = bbox[2] - bbox[0]
        draw.text(((ancho - w) / 2, yy), texto, font=fuente, fill=color)

    centrado(NOMBRE_RESIDENCIAL, f_titulo, y)
    y += 42
    centrado("Recibo de Pago de Alquiler", f_sub, y, color="#555555")
    y += 38

    draw.line([(margen, y), (ancho - margen, y)], fill="#cccccc", width=2)
    y += 24

    draw.text((margen, y), f'Recibo N°: {datos["numero_recibo"]}', font=f_chico, fill="black")
    texto_emitido = f'Emitido: {datos["fecha_emision"]}'
    bbox = draw.textbbox((0, 0), texto_emitido, font=f_chico)
    draw.text((ancho - margen - (bbox[2] - bbox[0]), y), texto_emitido, font=f_chico, fill="black")
    y += 38

    def fila(etiqueta, valor, yy, negrita_valor=False):
        draw.text((margen, yy), etiqueta, font=f_label, fill="black")
        fuente_valor = f_label if negrita_valor else f_valor
        texto = str(valor)
        bbox = draw.textbbox((0, 0), texto, font=fuente_valor)
        draw.text((ancho - margen - (bbox[2] - bbox[0]), yy), texto, font=fuente_valor, fill="black")
        return yy + 36

    y = fila("Apartamento:", f'{datos["apartamento_codigo"]} ({datos["apartamento_piso"]})', y)
    y = fila("Inquilino:", datos["inquilino_nombre"], y)
    y = fila("Periodo:", datos["periodo"], y)
    y = fila("Fecha de pago:", datos["fecha_pago"], y)
    y = fila("Método de pago:", datos["metodo_pago"], y)

    y += 8
    draw.line([(margen, y), (ancho - margen, y)], fill="#cccccc", width=2)
    y += 24

    y = fila("Monto esperado del mes:", _fmt_bs(datos["monto_esperado"]), y)
    y = fila("Total pagado a la fecha:", _fmt_bs(datos["total_pagado_periodo"]), y)
    saldo = datos["saldo_pendiente"]
    y = fila("Saldo pendiente:" if saldo > 0.009 else "Estado:",
             _fmt_bs(saldo) if saldo > 0.009 else "PAGADO COMPLETO", y, negrita_valor=True)

    y += 14
    y = fila("Monto de este abono:", _fmt_bs(datos["monto_pagado"]), y, negrita_valor=True)
    y += 20

    if datos.get("observacion"):
        draw.text((margen, y), f'Observación: {datos["observacion"]}', font=f_chico_i, fill="#555555")
        y += 34

    y += 16
    draw.line([(margen, y), (ancho - margen, y)], fill="#cccccc", width=2)
    y += 20
    draw.text((margen, y), f'Recibido por: {datos["recibido_por"]}', font=f_chico, fill="black")
    y += 40

    buffer = io.BytesIO()
    img.crop((0, 0, ancho, min(y + 40, alto))).save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()
