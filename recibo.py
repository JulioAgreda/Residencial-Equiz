"""
Generación de recibos de alquiler y servicios en PDF/PNG con diseño Equise consistente. Usa reportlab (PDF) y Pillow (PNG) — ambas livianas
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
        "fecha_emision": datetime.now(_ZONA_BOLIVIA).strftime("%d/%m/%Y %H:%M"),
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


def generar_recibo_png(datos: dict) -> bytes:
    """Genera el recibo PNG siguiendo la maqueta visual aprobada por el usuario."""
    S = 3
    W, H = 375, 667
    ancho, alto = W*S, H*S
    m = 12
    servicio = str(datos.get("servicio") or "alquiler").lower()
    if servicio == "electricidad":
        principal, claro, acento = "#075B35", "#EAF5EE", "#C9A24D"
        titulo = "ELECTRICIDAD"
    elif servicio == "agua":
        principal, claro, acento = "#0876C9", "#EAF4FC", "#83C8F4"
        titulo = "AGUA"
    else:
        principal, claro, acento = "#0D2D4C", "#EEF3F8", "#C49A45"
        titulo = "ALQUILER"
    texto, gris, borde = "#14243A", "#657080", "#D5DDE5"
    verde, rojo = "#247A3B", "#B3261E"
    img = Image.new("RGB", (ancho, alto), "white")
    d = ImageDraw.Draw(img)

    def xy(v):
        return int(round(v*S))
    def rect(box, fill=None, outline=None, width=1):
        d.rectangle(tuple(xy(v) for v in box), fill=fill, outline=outline, width=xy(width))
    def rounded(box, radius=5, fill=None, outline=None, width=1):
        d.rounded_rectangle(tuple(xy(v) for v in box), radius=xy(radius), fill=fill, outline=outline, width=xy(width))
    def line(points, fill, width=1):
        d.line([(xy(x),xy(y)) for x,y in points], fill=fill, width=xy(width))
    def text(x, y, value, size=8, fill=texto, bold=False, italic=False, anchor=None):
        f = _fuente(max(1,xy(size)), negrita=bold, cursiva=italic)
        d.text((xy(x),xy(y)), str(value), font=f, fill=fill, anchor=anchor)
    def centered(cx, y, value, size=8, fill=texto, bold=False, italic=False):
        text(cx, y, value, size, fill, bold, italic, anchor="mt")
    def right(x, y, value, size=8, fill=texto, bold=False):
        text(x, y, value, size, fill, bold, anchor="rt")
    def fit_text(value, max_width, size, bold=False):
        value = str(value or "—")
        f = _fuente(xy(size), negrita=bold)
        while value and d.textbbox((0,0), value, font=f)[2] > xy(max_width):
            value = value[:-1]
        return value

    # Cabecera con logo a la izquierda y banda diagonal de color.
    d.polygon([(xy(0),xy(0)),(xy(W),xy(0)),(xy(W),xy(102)),(xy(184),xy(102)),(xy(266),xy(0))], fill="white")
    d.polygon([(xy(266),xy(0)),(xy(W),xy(0)),(xy(W),xy(102)),(xy(184),xy(102))], fill=principal)
    line([(266,0),(184,102)], acento, 3)
    logo_path = LOGO_HORIZONTAL_PATH if os.path.exists(LOGO_HORIZONTAL_PATH) else LOGO_PATH
    try:
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((xy(178),xy(78)))
        img.paste(logo,(xy(14),xy(12)),logo)
    except Exception:
        text(20,25,"Equise",24,texto,True)
        text(21,57,"EDIFICIO RESIDENCIAL",5,texto)
    text(320,30,"RECIBO DE PAGO",6,"white",anchor="mt")
    centered(320,50,titulo,11,"white",True)
    line([(304,84),(360,84)],acento,1.5)
    line([(m,102),(W-m,102)],acento,1)

    # Número y fecha de emisión.
    text(14,113,"Recibo N°:",7,texto)
    text(78,113,datos.get("numero_recibo","—"),7,"#123C70",True)
    right(361,111,"Fecha de emisión:",6,texto)
    right(361,121,str(datos.get("fecha_emision","—")),6,texto)

    # Datos de apartamento, inquilino y periodo.
    rounded((12,129,363,240),5,claro)
    info = [
        ("Apartamento:", f'{_etiqueta_apartamento(datos.get("apartamento_codigo"), datos.get("apartamento_piso"))}'),
        ("Inquilino:", datos.get("inquilino_nombre","—")),
        ("Periodo:", datos.get("periodo","—")),
    ]
    ys = [145,178,211]
    for i, ((lab,val), yy) in enumerate(zip(info,ys)):
        # Iconos lineales compactos.
        if i == 0:
            rect((29,yy-2,41,yy+11),None,principal,1)
            line([(32,yy-1),(32,yy+10)],principal,1)
            line([(36,yy-1),(36,yy+10)],principal,1)
            line([(29,yy+3),(41,yy+3)],principal,1)
        elif i == 1:
            d.ellipse((xy(30),xy(yy-3),xy(40),xy(yy+7)),fill=principal)
            rounded((28,yy+7,42,yy+16),3,principal)
        else:
            rect((28,yy-3,42,yy+12),None,principal,1)
            line([(28,yy+1),(42,yy+1)],principal,1)
            line([(32,yy-5),(32,yy-1)],principal,1)
            line([(38,yy-5),(38,yy-1)],principal,1)
        text(51,yy-3,lab,7,texto,True)
        text(51,yy+9,fit_text(val,290,8),8,texto)

    es_servicio = servicio in ("agua","electricidad")
    tabla = datos.get("tabla_consumo") or {}
    filas = tabla.get("filas") or []

    # El alquiler muestra fecha y método de pago; los servicios priorizan lecturas.
    if not es_servicio:
        line([(14,250),(361,250)],borde,1)
        text(26,263,"▦",11,"#123C70",True)
        text(51,262,"Fecha de pago:",7,texto)
        text(164,262,str(datos.get("fecha_pago","—"))[:16],7,texto)
        text(51,284,"Método de pago:",7,texto)
        text(164,284,str(datos.get("metodo_pago","—"))[:18],7,texto)
        # La maqueta de alquiler incluye también quién recibió el abono.
        d.ellipse((xy(30),xy(307),xy(40),xy(317)),fill=principal)
        rounded((28,317,42,326),3,principal)
        text(51,307,"Recibido por:",7,texto)
        text(164,307,str(datos.get("recibido_por") or "—")[:24],7,texto)

    # Tabla de consumo. Solo se muestran las filas que la lógica del sistema entrega.
    if es_servicio and filas:
        text(23,250,"⚡" if servicio=="electricidad" else "●",12,principal,True)
        text(51,254,"DETALLE DE CONSUMO",7,principal,True)
        x0, x1 = 13, 362
        top = 277
        head_h, row_h = 42, 23
        widths = [62,72,72,69,74]
        headers = ["Medidor","Lectura\\nanterior","Lectura\\nactual",
                   "Consumo\\n(kWh)" if servicio=="electricidad" else "Consumo\\n(m³)",
                   "Tarifa\\n(Bs/kWh)" if servicio=="electricidad" else "Tarifa\\n(Bs/m³)"]
        rounded((x0,top,x1,top+head_h),2,claro,borde,0.6)
        xx=x0
        for i,h in enumerate(headers):
            parts=h.split("\\n")
            if len(parts)==1:
                centered(xx+widths[i]/2,top+15,parts[0],6,texto,True)
            else:
                centered(xx+widths[i]/2,top+6,parts[0],5.5,texto,True)
                centered(xx+widths[i]/2,top+20,parts[1],5.5,texto,True)
            xx+=widths[i]
        xx=x0
        for w in widths[:-1]:
            xx+=w; line([(xx,top),(xx,top+head_h+row_h*len(filas))],borde,0.6)
        yrow=top+head_h
        for idx,row in enumerate(filas):
            if idx%2==0:
                rect((x0,yrow,x1,yrow+row_h),claro)
            vals=[row.get("medidor","—"),row.get("anterior","—"),row.get("actual","—"),
                  str(row.get("consumo","—")).replace(" kWh","").replace(" m³",""),
                  str(row.get("tarifa","—")).replace("Bs ","")]
            xx=x0
            for i,val in enumerate(vals):
                value=fit_text(val,widths[i]-4,5.5)
                centered(xx+widths[i]/2,yrow+8,value,5.5,texto)
                xx+=widths[i]
            line([(x0,yrow+row_h),(x1,yrow+row_h)],borde,0.6)
            yrow+=row_h
        total_text=f'TOTAL CONSUMO: {tabla.get("total","—")}'
        right(356,yrow+6,total_text,6,texto,True)

    # Separador previo al monto; en alquiler divide los datos del pago del resumen.
    if not es_servicio:
        line([(14,358),(361,358)],borde,1)

    # Área principal del abono. Las coordenadas se mantienen iguales en los tres tipos.
    amount_top = 371 if not es_servicio else 393
    rounded((13,amount_top,362,amount_top+64),6,claro,principal,1.2)
    cx,cy=49,amount_top+32
    d.ellipse((xy(cx-23),xy(cy-23),xy(cx+23),xy(cy+23)),fill=principal)
    if servicio=="electricidad":
        centered(cx,cy-10,"ϟ",24,"white",True)
    elif servicio=="agua":
        # Gota sencilla en blanco.
        d.polygon([(xy(cx),xy(cy-14)),(xy(cx-11),xy(cy+2)),(xy(cx-8),xy(cy+12)),(xy(cx),xy(cy+16)),(xy(cx+8),xy(cy+12)),(xy(cx+11),xy(cy+2))],fill="white")
    else:
        centered(cx,cy-8,"Bs",12,"#E9B54F",True)
    text(80,amount_top+14,"MONTO DE ESTE ABONO",7,principal,True)
    text(80,amount_top+35,_fmt_bs(datos.get("monto_pagado",0)),17,"#10294B",True)

    # Resumen de importes y estado de pago.
    summary_top = amount_top+72
    summary_h=105
    rounded((14,summary_top,361,summary_top+summary_h),5,claro)
    saldo=float(datos.get("saldo_pendiente") or 0)
    resumen=[
        ("Monto esperado del mes:",_fmt_bs(datos.get("monto_esperado",0))),
        ("Total pagado a la fecha:",_fmt_bs(datos.get("total_pagado_periodo",0))),
        ("Saldo pendiente:",_fmt_bs(saldo)),
    ]
    yy=summary_top+16
    for lab,val in resumen:
        text(24,yy,lab,7,texto)
        right(351,yy,val,7,texto)
        line([(22,yy+18),(352,yy+18)],"#DDE5EA",0.5)
        yy+=26
    text(24,summary_top+83,"Estado:",7,texto)
    estado="PAGADO COMPLETO" if saldo<=0.009 else "SALDO PENDIENTE"
    status_color=verde if saldo<=0.009 else rojo
    rounded((205,summary_top+78,352,summary_top+101),5,status_color)
    centered(278.5,summary_top+84,estado,6.5,"white",True)

    # Mensaje y pie de página. El emisor reemplaza a "Residencial Equise".
    thank_y=summary_top+summary_h+10
    centered(187.5,thank_y,"¡Gracias por su pago!",14,"#233A5A",False,True)
    line([(14,thank_y+28),(361,thank_y+28)],acento,1)
    footer_y=thank_y+38
    emisor=str(datos.get("recibido_por") or datos.get("emitido_por") or "—")
    fecha=str(datos.get("fecha_emision") or "")
    text(22,footer_y,fit_text(emisor,90,6),6,texto)
    line([(128,footer_y-2),(128,footer_y+13)],borde,0.7)
    centered(187.5,footer_y,"Administración",6,texto)
    right(359,footer_y,fecha[:16],5.5,texto)

    # Recorte final fijo con el pie siempre visible.
    out=io.BytesIO()
    img.crop((0,0,ancho,alto)).save(out,format="PNG")
    out.seek(0)
    return out.getvalue()


def generar_recibo_pdf(datos: dict) -> bytes:
    """PDF visualmente idéntico al PNG aprobado, en formato vertical de recibo."""
    from reportlab.lib.utils import ImageReader
    buffer = io.BytesIO()
    png = generar_recibo_png(datos)
    page_w, page_h = 105*mm, 187*mm
    c = pdfcanvas.Canvas(buffer, pagesize=(page_w,page_h), pageCompression=1)
    c.drawImage(ImageReader(io.BytesIO(png)), 0, 0, width=page_w, height=page_h, preserveAspectRatio=False, mask="auto")
    c.showPage()
    c.save()
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


def _etiqueta_apartamento(codigo, piso):
    """Normaliza códigos internos para mostrar solo número/nombre y piso."""
    import re
    codigo = str(codigo or "—").strip()
    # Quita prefijos operativos como "TP-" y la palabra descriptiva "APARTAMENTO".
    codigo = re.sub(r"^TP\s*[-–:]\s*", "", codigo, flags=re.IGNORECASE)
    codigo = re.sub(r"\bAPARTAMENTO\b", "", codigo, flags=re.IGNORECASE)
    codigo = re.sub(r"\s+", " ", codigo).strip(" -–:")
    piso = str(piso or "").strip()
    if codigo and piso:
        return f"{codigo} - {piso}"
    return codigo or piso or "—"


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


def _logo_estado_cuenta():
    """Prioriza el logo horizontal nítido y usa el logo principal como respaldo."""
    return LOGO_HORIZONTAL_PATH if os.path.exists(LOGO_HORIZONTAL_PATH) else LOGO_PATH


def generar_reporte_inquilino_pdf(datos):
    """Estado de cuenta compacto, con identidad visual Equise y detalle mensual."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, HRFlowable, KeepTogether

    buffer = io.BytesIO()
    navy = colors.HexColor('#102B49')
    navy_header = colors.HexColor('#30425B')
    gold = colors.HexColor('#B68A36')
    pale = colors.HexColor('#F1F5F8')
    green = colors.HexColor('#2E7D32')
    red = colors.HexColor('#B3261E')
    regular, bold, _ = _fuentes_pdf()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=12*mm, leftMargin=12*mm,
                            topMargin=9*mm, bottomMargin=9*mm, title='Estado de cuenta - Residencial Equise')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='EquiseTitle', parent=styles['Title'], fontName=bold, fontSize=17, leading=19, textColor=navy, alignment=TA_LEFT, spaceAfter=1))
    styles.add(ParagraphStyle(name='EquiseSub', parent=styles['Normal'], fontName=regular, fontSize=9, leading=11, textColor=colors.HexColor('#5B6570')))
    styles.add(ParagraphStyle(name='ECBody', parent=styles['Normal'], fontName=regular, fontSize=8.2, leading=10, textColor=navy))
    styles.add(ParagraphStyle(name='ECBodyBold', parent=styles['ECBody'], fontName=bold))
    styles.add(ParagraphStyle(name='ECTableHead2', parent=styles['Normal'], fontName=bold, fontSize=7.6, leading=8.5, textColor=colors.white))
    styles.add(ParagraphStyle(name='ECTableCell2', parent=styles['Normal'], fontName=regular, fontSize=7.4, leading=8.5, textColor=navy))
    styles.add(ParagraphStyle(name='ECTableRight2', parent=styles['ECTableCell2'], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='ECTotalWhite', parent=styles['Normal'], fontName=bold, fontSize=12, leading=14, textColor=colors.white, alignment=TA_RIGHT))
    story=[]

    # Cabecera horizontal: logo nítido a la izquierda y título a la derecha.
    logo_path = _logo_estado_cuenta()
    logo_cell = Paragraph('', styles['ECBody'])
    if os.path.exists(logo_path):
        try:
            logo_cell = RLImage(logo_path, width=52*mm, height=20*mm, kind='proportional')
        except Exception:
            pass
    title_cell = [Paragraph('Residencial Equise', styles['EquiseTitle']),
                  Paragraph('Estado de Cuenta del Inquilino', styles['EquiseSub'])]
    header = Table([[logo_cell, title_cell]], colWidths=[61*mm, 119*mm])
    header.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),4),
        ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LINEBELOW',(0,0),(-1,-1),1.5,gold),
    ]))
    story += [header, Spacer(1,2.5*mm)]

    d = datos.get('deuda') or {}
    story.append(Paragraph(
        f"<b>Fecha de corte:</b> {datos.get('fecha_corte','—')}"
        f" <font color='#B68A36'>|</font> <b>Emitido:</b> {datos.get('fecha_emision','—')}", styles['ECBody']))
    story.append(Spacer(1,2*mm))
    apto = _etiqueta_apartamento(datos.get('apartamento_codigo'), datos.get('apartamento_piso'))
    info_rows = [
        [Paragraph('<b>Apartamento:</b>',styles['ECBody']), Paragraph(apto,styles['ECBody']),
         Paragraph('<b>Inquilino:</b>',styles['ECBody']), Paragraph(str(datos.get('inquilino_nombre','—')),styles['ECBody'])],
    ]
    info = Table(info_rows, colWidths=[34*mm,56*mm,38*mm,52*mm])
    info.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),pale),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LINEBELOW',(0,0),(-1,-1),0.35,colors.HexColor('#D8E0E7')),
    ]))
    story += [info, Spacer(1,2.5*mm)]

    def tabla_servicio(titulo, bloque):
        filas_datos = (bloque or {}).get('filas', [])
        rows = [[Paragraph(x,styles['ECTableHead2']) for x in ('Periodo','Esperado','Pagado','Saldo','Estado')]]
        for f in filas_datos:
            estado = str(f.get('estado') or '—')
            estado_style = ParagraphStyle('estado_'+str(len(rows)), parent=styles['ECTableCell2'],
                fontName=bold if 'pagado' in estado.lower() else regular,
                textColor=green if 'pagado' in estado.lower() else (red if 'pendiente' in estado.lower() else navy))
            rows.append([
                Paragraph(str(f.get('periodo') or '—'),styles['ECTableCell2']),
                Paragraph(_fmt_bs(f.get('esperado')),styles['ECTableRight2']),
                Paragraph(_fmt_bs(f.get('pagado')),styles['ECTableRight2']),
                Paragraph(_fmt_bs(f.get('saldo')),styles['ECTableRight2']),
                Paragraph(estado,estado_style),
            ])
        if not filas_datos:
            rows.append([Paragraph('Sin periodos registrados',styles['ECTableCell2']), '', '', '', ''])
        t = Table(rows, colWidths=[43*mm,32*mm,32*mm,25*mm,48*mm], repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),navy_header),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
            ('TOPPADDING',(0,0),(-1,0),5),('BOTTOMPADDING',(0,0),(-1,0),5),
            ('TOPPADDING',(0,1),(-1,-1),3),('BOTTOMPADDING',(0,1),(-1,-1),3),
            ('LINEBELOW',(0,1),(-1,-1),0.35,colors.HexColor('#D7DDE3')),
        ]))
        deuda_serv = float((bloque or {}).get('deuda') or 0)
        resumen = Table([[Paragraph(f'<b>Deuda de {titulo.lower()}</b>',styles['ECBody']),
                          Paragraph(f'<b>{_fmt_bs(deuda_serv)}</b>',styles['ECTableRight2'])]], colWidths=[130*mm,50*mm])
        resumen.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),pale),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
            ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ]))
        return [Paragraph(titulo, ParagraphStyle('section_'+titulo,parent=styles['Heading3'],fontName=bold,fontSize=10,leading=12,textColor=navy,spaceBefore=1,spaceAfter=3)), t, resumen, Spacer(1,2*mm)]

    story += tabla_servicio('Alquiler', d.get('alquiler',{}))
    story += tabla_servicio('Electricidad', d.get('electricidad',{}))
    total = float(d.get('deuda_total') or 0)
    al_dia = total <= 0.009
    color_estado = green if al_dia else red
    estado_txt = 'ESTADO: AL DÍA' if al_dia else 'ESTADO: DEUDA PENDIENTE'
    final = Table([[Paragraph(f'<b>{estado_txt}</b>', ParagraphStyle('status',parent=styles['ECBody'],fontName=bold,fontSize=10,textColor=colors.white)),
                    Paragraph(_fmt_bs(total),styles['ECTotalWhite'])]], colWidths=[115*mm,65*mm])
    final.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),color_estado),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
    ]))
    story += [final, Spacer(1,3*mm), HRFlowable(width='100%',thickness=0.7,color=gold), Spacer(1,1.5*mm),
              Paragraph(f"<b>Emitido por:</b> {datos.get('emitido_por') or '—'}",styles['ECBody'])]
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generar_reporte_inquilino_png(datos):
    """PNG compacto y nítido del estado de cuenta, coherente con el diseño Equise."""
    ancho = 1200
    margen = 48
    util = ancho - 2*margen
    d = datos.get('deuda') or {}
    alquiler = d.get('alquiler') or {}
    electricidad = d.get('electricidad') or {}
    filas_alq = alquiler.get('filas') or []
    filas_elec = electricidad.get('filas') or []
    # Altura calculada a partir del número real de periodos, sin espacios vacíos innecesarios.
    alto = 285 + 38*(len(filas_alq)+len(filas_elec)+4) + 160
    img = Image.new('RGB',(ancho,alto),'white')
    draw = ImageDraw.Draw(img)
    navy='#102B49'; header='#30425B'; gold='#B68A36'; pale='#F1F5F8'; grid='#D7DDE3'; green='#2E7D32'; red='#B3261E'; muted='#5B6570'
    ft=_fuente(31,negrita=True); fs=_fuente(17); fb=_fuente(17,negrita=True); fc=_fuente(14); fcb=_fuente(14,negrita=True); fsmall=_fuente(12)
    y=22
    logo_path = _logo_estado_cuenta()
    if os.path.exists(logo_path):
        try:
            logo=Image.open(logo_path).convert('RGBA')
            logo.thumbnail((350,94),Image.Resampling.LANCZOS)
            img.paste(logo,(margen,y),logo)
        except Exception:
            pass
    x_text=margen+350
    draw.text((x_text,y+5),'Residencial Equise',font=ft,fill=navy)
    draw.text((x_text,y+47),'Estado de Cuenta del Inquilino',font=fs,fill=muted)
    y+=112
    draw.line((margen,y,ancho-margen,y),fill=gold,width=3); y+=14
    # Corte/emisión en una sola línea para compactar.
    draw.text((margen,y),f"Fecha de corte: {datos.get('fecha_corte','—')}",font=fc,fill=navy)
    emit=f"Emitido: {datos.get('fecha_emision','—')}"
    eb=draw.textbbox((0,0),emit,font=fc); draw.text((ancho-margen-(eb[2]-eb[0]),y),emit,font=fc,fill=navy); y+=31

    # Tarjeta compacta de datos generales, con columnas para reducir altura.
    draw.rounded_rectangle((margen,y,ancho-margen,y+58),radius=10,fill=pale)
    fields=[('Apartamento',_etiqueta_apartamento(datos.get('apartamento_codigo'), datos.get('apartamento_piso'))),
            ('Inquilino',datos.get('inquilino_nombre','—'))]
    draw.text((margen+14,y+7),fields[0][0]+':',font=fcb,fill=navy)
    draw.text((margen+135,y+7),str(fields[0][1]),font=fc,fill=navy)
    draw.text((margen+14,y+34),fields[1][0]+':',font=fcb,fill=navy)
    draw.text((margen+135,y+34),str(fields[1][1]),font=fc,fill=navy)
    y+=68

    def tabla(titulo,bloque,filas):
        nonlocal y
        draw.text((margen,y),titulo,font=fb,fill=navy); y+=27
        colx=[margen,margen+300,margen+480,margen+660,margen+825,ancho-margen]
        draw.rounded_rectangle((margen,y,ancho-margen,y+34),radius=4,fill=header)
        for i,h in enumerate(['Periodo','Esperado','Pagado','Saldo','Estado']):
            draw.text((colx[i]+8,y+9),h,font=fcb,fill='white')
        y+=34
        if not filas:
            draw.text((margen+10,y+8),'Sin periodos registrados',font=fc,fill=navy); y+=31
        for f in filas:
            draw.rectangle((margen,y,ancho-margen,y+31),fill='white')
            vals=[str(f.get('periodo') or '—'),_fmt_bs(f.get('esperado')),_fmt_bs(f.get('pagado')),_fmt_bs(f.get('saldo')),str(f.get('estado') or '—')]
            for i,val in enumerate(vals):
                font=fcb if i==4 and 'pagado' in val.lower() else fc
                color=green if i==4 and 'pagado' in val.lower() else (red if i==4 and 'pendiente' in val.lower() else navy)
                draw.text((colx[i]+8,y+7),val,font=font,fill=color)
            y+=31; draw.line((margen,y,ancho-margen,y),fill=grid,width=1)
        # Deuda del servicio alineada a la derecha en una franja clara.
        draw.rectangle((margen,y,ancho-margen,y+30),fill=pale)
        lab=f"Deuda de {titulo.lower()}"
        draw.text((margen+10,y+7),lab,font=fcb,fill=navy)
        val=_fmt_bs(bloque.get('deuda') or 0); bb=draw.textbbox((0,0),val,font=fcb)
        draw.text((ancho-margen-10-(bb[2]-bb[0]),y+7),val,font=fcb,fill=navy)
        y+=40
    tabla('Alquiler',alquiler,filas_alq)
    tabla('Electricidad',electricidad,filas_elec)
    total=float(d.get('deuda_total') or 0); al_dia=total<=0.009
    color=green if al_dia else red
    draw.rounded_rectangle((margen,y,ancho-margen,y+68),radius=10,fill=color)
    estado='ESTADO: AL DÍA' if al_dia else 'ESTADO: DEUDA PENDIENTE'
    draw.text((margen+20,y+21),estado,font=fb,fill='white')
    monto=_fmt_bs(total); bb=draw.textbbox((0,0),monto,font=ft)
    draw.text((ancho-margen-20-(bb[2]-bb[0]),y+15),monto,font=ft,fill='white')
    y+=86; draw.line((margen,y,ancho-margen,y),fill=gold,width=2); y+=13
    draw.text((margen,y),f"Emitido por: {datos.get('emitido_por') or '—'}",font=fc,fill=navy)
    out=io.BytesIO(); img.crop((0,0,ancho,min(y+32,alto))).save(out,format='PNG',optimize=True); out.seek(0); return out.getvalue()
