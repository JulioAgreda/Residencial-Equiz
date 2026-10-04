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
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
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


def _fmt_bs(monto):
    try:
        return f"Bs {float(monto):,.2f}"
    except (TypeError, ValueError):
        return "Bs 0.00"


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
