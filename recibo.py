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
    for etiqueta, valor in datos.get("detalle", []):
        fila(etiqueta, valor, tam=8.5)

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
    for etiqueta, valor in datos.get("detalle", []):
        y = fila(etiqueta, valor, y)

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


def _detalle_lecturas(config, periodo, servicio=None):
    """Devuelve las lecturas/tarifa imprimibles sin inventar consumos incoherentes."""
    servicio = servicio or ("agua" if config is SERVICIOS["agua"] else "electricidad")
    unidad = config["unidad"]
    if servicio == "electricidad":
        ant1, act1 = periodo.get("kwh_anterior"), periodo.get("kwh_actual")
        ant2, act2 = periodo.get("kwh_anterior_2"), periodo.get("kwh_actual_2")
        dos = ant2 is not None and act2 is not None
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


def construir_datos_recibo_servicio(servicio, pago, periodo, apartamento, total_pagado_periodo, recibido_por):
    if servicio not in SERVICIOS:
        raise ValueError(f"Servicio no válido: {servicio}")
    datos = construir_datos_recibo(pago, periodo, apartamento, total_pagado_periodo, recibido_por)
    config = SERVICIOS[servicio]
    datos["titulo"] = f"Recibo de Pago de {config['nombre']}"
    datos["servicio"] = servicio
    datos["detalle"] = _detalle_lecturas(config, periodo, servicio)
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
