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
import textwrap
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from PIL import Image, ImageDraw, ImageFont

_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(_DIR, "assets", "logo_equise.png")
LOGO_HORIZONTAL_PATH = os.path.join(_DIR, "assets", "logo_equise_horizontal.png")
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


def _colores_recibo(datos):
    """Paleta por tipo de recibo, siguiendo el diseño aprobado por el usuario."""
    from reportlab.lib import colors
    servicio = str(datos.get("servicio") or "alquiler").lower()
    if servicio == "electricidad":
        principal = "#075B35"
        claro = "#EAF5EE"
        acento = "#C9A24D"
    elif servicio == "agua":
        principal = "#0876C9"
        claro = "#EAF4FC"
        acento = "#83C8F4"
    else:
        principal = "#0D2D4C"
        claro = "#EEF3F8"
        acento = "#C49A45"
    return {
        "principal": colors.HexColor(principal),
        "claro": colors.HexColor(claro),
        "acento": colors.HexColor(acento),
        "texto": colors.HexColor("#14243A"),
        "gris": colors.HexColor("#657080"),
        "borde": colors.HexColor("#D5DDE5"),
        "verde": colors.HexColor("#247A3B"),
        "rojo": colors.HexColor("#B3261E"),
        "blanco": colors.white,
    }


def _tabla_consumo_desde_periodo(servicio, periodo, dos_medidores=False):
    """Construye filas de lectura para mostrar en el recibo, sin recalcular cargos."""
    periodo = periodo or {}
    if servicio == "electricidad":
        medidores = [("Medidor 1", periodo.get("kwh_anterior"), periodo.get("kwh_actual"))]
        if dos_medidores and periodo.get("kwh_anterior_2") is not None and periodo.get("kwh_actual_2") is not None:
            medidores.append(("Medidor 2", periodo.get("kwh_anterior_2"), periodo.get("kwh_actual_2")))
        tarifa = periodo.get("tarifa_kwh")
        filas = []
        total = 0.0
        for nombre, anterior, actual in medidores:
            a = float(anterior or 0)
            b = float(actual or 0)
            consumo = max(b-a, 0)
            total += consumo
            filas.append({"medidor": nombre, "anterior": f"{a:g}", "actual": f"{b:g}", "consumo": f"{consumo:g} kWh", "tarifa": f"Bs {float(tarifa):.2f}" if tarifa is not None else "—"})
        return {"headers": ["Medidor", "Lectura anterior", "Lectura actual", "Consumo (kWh)", "Tarifa (Bs/kWh)"], "filas": filas, "total": f"{total:g} kWh", "unidad": "kWh"}
    anterior = float(periodo.get("lectura_anterior") or 0)
    actual = float(periodo.get("lectura_actual") or 0)
    consumo = max(actual-anterior, 0)
    tarifa = periodo.get("tarifa_agua")
    return {
        "headers": ["Medidor", "Lectura anterior", "Lectura actual", "Consumo (m³)", "Tarifa (Bs/m³)"],
        "filas": [{"medidor": "Medidor 1", "anterior": f"{anterior:g}", "actual": f"{actual:g}", "consumo": f"{consumo:g} m³", "tarifa": f"Bs {float(tarifa):.2f}" if tarifa is not None else "—"}],
        "total": f"{consumo:g} m³", "unidad": "m³"
    }


def _fuentes_pdf():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    regular, bold, italic = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"
    try:
        paths = {
            "EquiseDV": os.path.join(_DIR, "assets", "fonts", "DejaVuSans.ttf"),
            "EquiseDV-Bold": os.path.join(_DIR, "assets", "fonts", "DejaVuSans-Bold.ttf"),
            "EquiseDV-Oblique": os.path.join(_DIR, "assets", "fonts", "DejaVuSans-Oblique.ttf"),
        }
        for name, path in paths.items():
            if os.path.exists(path) and name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, path))
        if "EquiseDV" in pdfmetrics.getRegisteredFontNames():
            regular = "EquiseDV"
            bold = "EquiseDV-Bold" if "EquiseDV-Bold" in pdfmetrics.getRegisteredFontNames() else regular
            italic = "EquiseDV-Oblique" if "EquiseDV-Oblique" in pdfmetrics.getRegisteredFontNames() else regular
    except Exception:
        pass
    return regular, bold, italic


def generar_recibo_pdf(datos: dict) -> bytes:
    """Genera recibos A5 con el diseño Equise aprobado: cabecera por servicio, tablas y monto destacado."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    buffer = io.BytesIO()
    ancho, alto = A5
    c = pdfcanvas.Canvas(buffer, pagesize=A5)
    pal = _colores_recibo(datos)
    font, font_b, font_i = _fuentes_pdf()
    margen = 10 * mm
    util = ancho - 2*margen
    titulo, concepto = _texto_recibo(datos)
    servicio = str(datos.get("servicio") or "alquiler").lower()
    y = alto - 8*mm

    # Cabecera blanca con marca transparente y banda de color del tipo de recibo.
    header_h = 28*mm
    c.setFillColor(pal["principal"])
    c.rect(ancho-59*mm, y-header_h, 49*mm, header_h, fill=1, stroke=0)
    c.setFillColor(pal["blanco"])
    c.setFont(font, 7)
    c.drawCentredString(ancho-34.5*mm, y-9*mm, "RECIBO DE PAGO")
    c.setFont(font_b, 10)
    c.drawCentredString(ancho-34.5*mm, y-16*mm, concepto)
    c.setStrokeColor(pal["acento"])
    c.setLineWidth(2)
    c.line(ancho-47*mm, y-21*mm, ancho-22*mm, y-21*mm)
    if os.path.exists(LOGO_HORIZONTAL_PATH):
        try:
            c.drawImage(LOGO_HORIZONTAL_PATH, margen+2*mm, y-header_h+5*mm, width=61*mm, height=17*mm, preserveAspectRatio=True, anchor="c", mask="auto")
        except Exception:
            pass
    y -= header_h + 3*mm
    c.setStrokeColor(pal["acento"]); c.setLineWidth(.8); c.line(margen,y,ancho-margen,y)
    y -= 5*mm
    c.setFillColor(pal["texto"]); c.setFont(font_b, 8)
    c.drawString(margen, y, f'Recibo N°: {datos.get("numero_recibo", "—")}')
    c.setFont(font, 7)
    c.drawRightString(ancho-margen, y, f'Fecha de emisión: {datos.get("fecha_emision", "—")}')
    y -= 7*mm

    # Tarjeta de datos del inquilino.
    c.setFillColor(pal["claro"]); c.roundRect(margen,y-27*mm,util,27*mm,5,fill=1,stroke=0)
    c.setFillColor(pal["texto"]); c.setFont(font_b, 7.5)
    info = [
        ("Apartamento:", f'{datos.get("apartamento_codigo", "—")} - {datos.get("apartamento_piso", "—")}'),
        ("Inquilino:", datos.get("inquilino_nombre", "—")),
        ("Periodo:", datos.get("periodo", "—")),
    ]
    yy = y-6*mm
    for lab,val in info:
        c.setFont(font_b,7.2); c.drawString(margen+3*mm,yy,lab)
        c.setFont(font,7.2); c.drawString(margen+24*mm,yy,str(val or "—")[:58])
        yy -= 6.2*mm
    y -= 31*mm

    # Datos de pago en dos columnas.
    c.setFillColor(pal["texto"]); c.setFont(font,7.4)
    c.drawString(margen+2*mm,y,f'Fecha de pago: {datos.get("fecha_pago", "—")}')
    c.drawRightString(ancho-margen-2*mm,y,f'Método: {datos.get("metodo_pago", "—")}')
    y -= 6*mm

    # Tabla de consumo para agua/electricidad.
    tabla = datos.get("tabla_consumo")
    if servicio in ("agua", "electricidad") and tabla and tabla.get("filas"):
        c.setFillColor(pal["principal"]); c.setFont(font_b,8)
        c.drawString(margen,y,"DETALLE DE CONSUMO")
        y -= 4*mm
        headers = tabla.get("headers") or []
        rows = tabla.get("filas") or []
        col_widths = [util*.19, util*.19, util*.19, util*.20, util*.23]
        row_h = 7*mm
        c.setFillColor(pal["principal"]); c.roundRect(margen,y-row_h,util,row_h,2,fill=1,stroke=0)
        c.setFillColor(pal["blanco"]); c.setFont(font_b,5.7)
        xx=margen
        for i,h in enumerate(headers):
            c.drawCentredString(xx+col_widths[i]/2,y-4.6*mm,str(h)[:22]); xx += col_widths[i]
        y -= row_h
        c.setFont(font,6.5)
        for ridx,row in enumerate(rows):
            if ridx%2==0:
                c.setFillColor(pal["claro"]); c.rect(margen,y-row_h,util,row_h,fill=1,stroke=0)
            vals=[row.get("medidor","—"),row.get("anterior","—"),row.get("actual","—"),row.get("consumo","—"),row.get("tarifa","—")]
            xx=margen
            for i,val in enumerate(vals):
                c.setFillColor(pal["texto"]); c.drawCentredString(xx+col_widths[i]/2,y-4.6*mm,str(val)[:18]); xx+=col_widths[i]
            c.setStrokeColor(pal["borde"]); c.setLineWidth(.3); c.line(margen,y-row_h,ancho-margen,y-row_h)
            y -= row_h
        c.setFillColor(pal["texto"]); c.setFont(font_b,6.8)
        c.drawRightString(ancho-margen-2*mm,y-4.5*mm,f'Total consumo: {tabla.get("total", "—")}')
        y -= 8*mm

    # Resumen de pago, conservando montos registrados en el sistema.
    c.setStrokeColor(pal["borde"]); c.line(margen,y,ancho-margen,y); y -= 6*mm
    esperado = _fmt_bs(datos.get("monto_esperado",0))
    pagado = _fmt_bs(datos.get("total_pagado_periodo",0))
    saldo = float(datos.get("saldo_pendiente") or 0)
    for label,val in [("Monto esperado del periodo:",esperado),("Total pagado a la fecha:",pagado),("Saldo pendiente:",_fmt_bs(saldo))]:
        c.setFillColor(pal["texto"]); c.setFont(font,7.5); c.drawString(margen+2*mm,y,label)
        c.setFont(font_b if label.startswith("Saldo") else font,7.5); c.drawRightString(ancho-margen-2*mm,y,val)
        y -= 5.5*mm
    # Estado destacado.
    estado = "PAGADO COMPLETO" if saldo <= 0.009 else "SALDO PENDIENTE"
    estado_color = pal["verde"] if saldo <= 0.009 else pal["rojo"]
    c.setFillColor(colors.HexColor("#E7F3E8" if saldo <= 0.009 else "#FBEAEA"))
    c.roundRect(margen,y-8*mm,util,8*mm,3,fill=1,stroke=0)
    c.setFillColor(estado_color); c.setFont(font_b,8)
    c.drawCentredString(ancho/2,y-5.2*mm,estado)
    y -= 12*mm

    # Monto de este abono, en una franja de marca.
    c.setFillColor(pal["principal"]); c.roundRect(margen,y-15*mm,util,15*mm,5,fill=1,stroke=0)
    c.setFillColor(pal["blanco"]); c.setFont(font_b,7.5); c.drawString(margen+4*mm,y-9*mm,"MONTO DE ESTE ABONO")
    c.setFont(font_b,13); c.drawRightString(ancho-margen-4*mm,y-9.5*mm,_fmt_bs(datos.get("monto_pagado",0)))
    y -= 19*mm

    obs=str(datos.get("observacion") or "").strip()
    if obs:
        c.setFillColor(pal["gris"]); c.setFont(font_i,6.5)
        c.drawString(margen,y, "Observación: " + obs[:100]); y -= 5*mm

    # Pie coherente en todos los tipos: nombre del usuario que emitió/registró.
    footer_y=9*mm
    c.setStrokeColor(pal["acento"]); c.setLineWidth(.7); c.line(margen,footer_y+5*mm,ancho-margen,footer_y+5*mm)
    c.setFillColor(pal["gris"]); c.setFont(font,6.5)
    emisor=str(datos.get("recibido_por") or datos.get("emitido_por") or "—")
    c.drawString(margen,footer_y,"Emitido por: " + emisor[:42])
    c.setFillColor(pal["gris"]); c.drawRightString(ancho-margen,footer_y,str(datos.get("fecha_emision") or "")[:24])
    c.showPage(); c.save(); buffer.seek(0)
    return buffer.getvalue()


def generar_recibo_png(datos: dict) -> bytes:
    """PNG equivalente al PDF: cabecera por servicio, consumo tabulado y resumen claro."""
    ancho=900; margen=28; util=ancho-2*margen
    servicio=str(datos.get("servicio") or "alquiler").lower()
    if servicio == "electricidad": principal="#075B35"; claro="#EAF5EE"; acento="#C9A24D"
    elif servicio == "agua": principal="#0876C9"; claro="#EAF4FC"; acento="#83C8F4"
    else: principal="#0D2D4C"; claro="#EEF3F8"; acento="#C49A45"
    texto="#14243A"; gris="#657080"; borde="#D5DDE5"; verde="#247A3B"; rojo="#B3261E"
    f_title=_fuente(28,negrita=True); f_sub=_fuente(13); f_label=_fuente(14,negrita=True); f_value=_fuente(14); f_small=_fuente(11); f_small_b=_fuente(11,negrita=True); f_amount=_fuente(25,negrita=True)
    titulo, concepto=_texto_recibo(datos); tabla=datos.get("tabla_consumo") or {}; filas=tabla.get("filas") or []
    obs=str(datos.get("observacion") or "").strip()
    alto=890 + (len(filas)*42 + 100 if servicio in ("agua","electricidad") and filas else 0) + (35 if obs else 0)
    img=Image.new("RGB",(ancho,alto),"white"); draw=ImageDraw.Draw(img); y=20

    # Header split: logo sobre blanco, panel de servicio coloreado.
    draw.rectangle((ancho-315,y,ancho-margen,y+105),fill=principal)
    draw.rectangle((margen,y,ancho-315,y+105),fill="white")
    if os.path.exists(LOGO_HORIZONTAL_PATH):
        try:
            logo=Image.open(LOGO_HORIZONTAL_PATH).convert("RGBA"); logo.thumbnail((250,88))
            img.paste(logo,(margen+12,y+8),logo)
        except Exception: pass
    draw.text((ancho-300,y+20),"RECIBO DE PAGO",font=f_small,fill="white")
    draw.text((ancho-300,y+48),concepto,font=_fuente(19,negrita=True),fill="white")
    draw.rectangle((margen,y+103,ancho-margen,y+106),fill=acento); y+=125

    draw.text((margen,y),f'Recibo N°: {datos.get("numero_recibo","—")}',font=f_small_b,fill=texto)
    emitido=f'Fecha de emisión: {datos.get("fecha_emision","—")}'
    eb=draw.textbbox((0,0),emitido,font=f_small)
    draw.text((ancho-margen-(eb[2]-eb[0]),y),emitido,font=f_small,fill=gris); y+=34

    # Identificación del apartamento e inquilino.
    draw.rounded_rectangle((margen,y,ancho-margen,y+142),radius=12,fill=claro)
    info=[("Apartamento:",f'{datos.get("apartamento_codigo","—")} - {datos.get("apartamento_piso","—")}'),("Inquilino:",datos.get("inquilino_nombre","—")),("Periodo:",datos.get("periodo","—"))]
    yy=y+16
    for lab,val in info:
        draw.text((margen+20,yy),lab,font=f_label,fill=texto); yy+=2
        draw.text((margen+190,yy),str(val or "—")[:64],font=f_value,fill=texto); yy+=38
    y+=158
    draw.text((margen+4,y),f'Fecha de pago: {datos.get("fecha_pago","—")}',font=f_small,fill=texto)
    metodo=f'Método de pago: {datos.get("metodo_pago","—")}'; mb=draw.textbbox((0,0),metodo,font=f_small)
    draw.text((ancho-margen-(mb[2]-mb[0]),y),metodo,font=f_small,fill=texto); y+=32

    if servicio in ("agua","electricidad") and filas:
        draw.text((margen,y),"DETALLE DE CONSUMO",font=f_label,fill=principal); y+=29
        headers=tabla.get("headers") or ["Medidor","Anterior","Actual","Consumo","Tarifa"]
        colw=[util*.18,util*.20,util*.20,util*.21,util*.21]
        draw.rounded_rectangle((margen,y,ancho-margen,y+38),radius=6,fill=principal)
        xx=margen
        for i,h in enumerate(headers):
            txt=str(h).replace("Lectura ","")
            draw.text((xx+3,y+11),txt[:18],font=_fuente(9,negrita=True),fill="white")
            xx+=colw[i]
        y+=38
        for ridx,row in enumerate(filas):
            if ridx%2==0: draw.rectangle((margen,y,ancho-margen,y+37),fill=claro)
            vals=[row.get("medidor","—"),row.get("anterior","—"),row.get("actual","—"),row.get("consumo","—"),row.get("tarifa","—")]
            xx=margen
            for i,val in enumerate(vals):
                value=str(val)
                font=_fuente(10)
                bb=draw.textbbox((0,0),value,font=font)
                maxw=colw[i]-8
                if bb[2]-bb[0]>maxw: font=_fuente(8)
                draw.text((xx+4,y+11),value[:18],font=font,fill=texto); xx+=colw[i]
            draw.line((margen,y+37,ancho-margen,y+37),fill=borde,width=1); y+=37
        total=f'Total consumo: {tabla.get("total","—")}'
        draw.text((ancho-margen-240,y+5),total,font=f_small_b,fill=texto); y+=35

    draw.line((margen,y,ancho-margen,y),fill=borde,width=2); y+=18
    saldo=float(datos.get("saldo_pendiente") or 0)
    for lab,val in [("Monto esperado del periodo:",_fmt_bs(datos.get("monto_esperado",0))),("Total pagado a la fecha:",_fmt_bs(datos.get("total_pagado_periodo",0))),("Saldo pendiente:",_fmt_bs(saldo))]:
        draw.text((margen+12,y),lab,font=f_value,fill=texto)
        vv=str(val); bb=draw.textbbox((0,0),vv,font=f_value)
        draw.text((ancho-margen-12-(bb[2]-bb[0]),y),vv,font=f_value,fill=texto); y+=32
    status="PAGADO COMPLETO" if saldo<=0.009 else "SALDO PENDIENTE"
    status_color=verde if saldo<=0.009 else rojo
    draw.rounded_rectangle((margen,y,ancho-margen,y+42),radius=9,fill="#E7F3E8" if saldo<=0.009 else "#FBEAEA")
    bb=draw.textbbox((0,0),status,font=f_label)
    draw.text(((ancho-(bb[2]-bb[0]))/2,y+11),status,font=f_label,fill=status_color); y+=56

    draw.rounded_rectangle((margen,y,ancho-margen,y+76),radius=12,fill=principal)
    draw.text((margen+20,y+27),"MONTO DE ESTE ABONO",font=f_small_b,fill="white")
    amount=_fmt_bs(datos.get("monto_pagado",0)); ab=draw.textbbox((0,0),amount,font=f_amount)
    draw.text((ancho-margen-20-(ab[2]-ab[0]),y+19),amount,font=f_amount,fill="white"); y+=94
    if obs:
        draw.text((margen,y),"Observación: "+obs[:100],font=f_small,fill=gris); y+=30
    draw.line((margen,y,ancho-margen,y),fill=acento,width=2); y+=15
    emisor=str(datos.get("recibido_por") or datos.get("emitido_por") or "—")
    draw.text((margen,y),"Emitido por: "+emisor[:45],font=f_small,fill=gris)
    fecha=str(datos.get("fecha_emision") or "")
    fb=draw.textbbox((0,0),fecha,font=f_small)
    draw.text((ancho-margen-(fb[2]-fb[0]),y),fecha,font=f_small,fill=gris); y+=30
    out=io.BytesIO(); img.crop((0,0,ancho,y+15)).save(out,format="PNG"); out.seek(0); return out.getvalue()


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
    if servicio in ("agua", "electricidad"):
        datos["tabla_consumo"] = _tabla_consumo_desde_periodo(servicio, periodo, dos_medidores=permitir_segundo)
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
