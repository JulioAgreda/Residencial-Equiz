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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
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
        return f"Bs {float(monto):,.2f}"
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


def construir_datos_recibo_garantia(garantia, apartamento, recibido_por):
    """Prepara un recibo independiente por la recepción de una garantía reembolsable."""
    garantia = garantia or {}
    monto = round(float(garantia.get("monto_recibido") or 0), 2)
    fecha = garantia.get("fecha_recepcion") or ""
    return {
        "numero_recibo": f'REC-G-{int(garantia["id"]):06d}',
        "fecha_emision": datetime.now(_ZONA_BOLIVIA).strftime("%d/%m/%Y %H:%M"),
        "titulo": "Recibo de Recepción de Garantía de Alquiler",
        "apartamento_texto": formatear_apartamento(apartamento),
        "inquilino_nombre": garantia.get("inquilino_nombre") or "—",
        "periodo": "Depósito de garantía de alquiler",
        "fecha_pago": fecha,
        "metodo_pago": garantia.get("medio_recepcion") or "—",
        "observacion": garantia.get("observacion") or "",
        "detalle": [
            ("Concepto:", "Depósito de garantía reembolsable"),
            ("Estado de garantía:", garantia.get("estado") or "Vigente"),
            ("Comprobante de respaldo:", garantia.get("comprobante_recepcion") or "—"),
        ],
        "monto_esperado": monto,
        "total_pagado_periodo": monto,
        "saldo_pendiente": 0.0,
        "monto_pagado": monto,
        "label_monto_esperado": "Monto de garantía acordado:",
        "label_total_pagado": "Monto recibido:",
        "label_monto_abono": "MONTO DE GARANTÍA RECIBIDO",
        "recibido_por": recibido_por or garantia.get("registrado_por") or "—",
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


# ============================================================
# PDF — formato compacto, tipo comprobante
# ============================================================

def _logo_horizontal():
    """Carga el logo horizontal de alta resolución; usa el vertical solo como respaldo."""
    ruta = LOGO_PATH if os.path.exists(LOGO_PATH) else LOGO_FALLBACK_PATH
    if not os.path.exists(ruta):
        return None
    try:
        return Image.open(ruta).convert("RGBA")
    except Exception:
        return None


def _texto_envuelto(draw, texto, fuente, ancho):
    palabras = str(texto or "—").split()
    lineas, actual = [], ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if draw.textbbox((0, 0), prueba, font=fuente)[2] <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas or ["—"]


def generar_recibo_png(datos: dict) -> bytes:
    """Recibo EQUISE renovado: formato vertical, logo horizontal y paleta azul/dorado."""
    W = 1100
    detalle_extra = max(0, len(datos.get("detalle") or []) - 2)
    H = 1556 + detalle_extra * 72 + (55 if datos.get("observacion") else 0)  # página dinámica, sin cortar detalle
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    navy, gold, pale, ink, muted = _AZUL, _DORADO, _AZUL_CLARO, "#142A43", "#607286"
    f_brand = _fuente(42, negrita=True)
    f_kicker = _fuente(23)
    f_title = _fuente(37, negrita=True)
    f_label = _fuente(22, negrita=True)
    f_value = _fuente(27)
    f_small = _fuente(19)
    f_small_b = _fuente(20, negrita=True)
    f_amount = _fuente(57, negrita=True)
    f_amount_label = _fuente(23, negrita=True)
    margin = 58

    # Cabecera institucional con corte diagonal azul y filete dorado.
    d.rectangle((0, 0, W, 300), fill="white")
    d.polygon([(650, 0), (W, 0), (W, 300), (430, 300)], fill=navy)
    d.polygon([(650, 0), (668, 0), (448, 300), (430, 300)], fill=gold)
    logo = _logo_horizontal()
    if logo:
        logo.thumbnail((535, 205), Image.Resampling.LANCZOS)
        img.paste(logo, (margin, 46), logo if logo.mode == "RGBA" else None)
    else:
        d.text((margin, 95), "EQUISE", font=f_brand, fill=gold)
        d.text((margin, 150), "EDIFICIO RESIDENCIAL", font=f_small_b, fill=navy)
    titulo_raw = str(datos.get("titulo") or "Recibo de Pago de Alquiler").upper()
    if "GARANT" in titulo_raw:
        titulo = "GARANTÍA"
    elif "ELECTRIC" in titulo_raw or "LUZ" in titulo_raw:
        titulo = "ELECTRICIDAD"
    elif "AGUA" in titulo_raw:
        titulo = "AGUA"
    else:
        titulo = "ALQUILER"
    # Título blanco en bloque derecho, centrado.
    d.text((760, 86), "RECIBO DE PAGO", font=f_kicker, fill="white", anchor="mm")
    title_lines = _texto_envuelto(d, titulo, f_title, 365)
    yy = 142
    for line in title_lines[:2]:
        d.text((815, yy), line, font=f_title, fill="white", anchor="mm")
        yy += 49
    d.line((margin, 299, W-margin, 299), fill=gold, width=4)

    # Número y fecha de emisión.
    y = 330
    d.text((margin, y), "RECIBO N.º", font=f_small, fill=muted)
    d.text((margin+155, y-4), str(datos.get("numero_recibo", "—")), font=f_small_b, fill=navy)
    d.text((W-margin, y), f'Emisión: {datos.get("fecha_emision", "—")}', font=f_small, fill=ink, anchor="ra")

    # Panel de identificación.
    top, bottom = 385, 650
    d.rounded_rectangle((margin, top, W-margin, bottom), radius=22, fill=pale)
    campos = [
        ("APARTAMENTO", datos.get("apartamento_texto", "—")),
        ("INQUILINO", datos.get("inquilino_nombre", "—")),
        ("PERIODO / CONCEPTO", datos.get("periodo", "—")),
    ]
    yy = top + 30
    for label, value in campos:
        d.text((margin+34, yy), label, font=f_small_b, fill=navy)
        d.text((margin+34, yy+34), str(value), font=f_value, fill=ink)
        yy += 78

    # Datos del pago.
    y = 700
    d.line((margin, y, W-margin, y), fill=_GRIS, width=3)
    y += 34
    pagos = [("FECHA DE PAGO", datos.get("fecha_pago", "—")),
             ("MÉTODO DE PAGO", datos.get("metodo_pago", "—")),
             ("RECIBIDO POR", datos.get("recibido_por", "—"))]
    if datos.get("detalle"):
        pagos.extend((str(k).upper(), str(v)) for k, v in datos["detalle"])
    for label, value in pagos:
        d.text((margin+22, y), label, font=f_small_b, fill=muted)
        lines = _texto_envuelto(d, value, f_value, 590)
        for j, line in enumerate(lines[:2]):
            d.text((margin+440, y+j*31), line, font=f_value, fill=ink)
        y += max(68, len(lines[:2])*34+24)
    d.line((margin, y, W-margin, y), fill=_GRIS, width=3)
    y += 30

    # Monto de este abono: bloque protagonista.
    box_h = 155
    d.rounded_rectangle((margin, y, W-margin, y+box_h), radius=22, fill=pale, outline=navy, width=4)
    d.ellipse((margin+26, y+25, margin+132, y+131), fill=navy)
    d.text((margin+79, y+79), "Bs", font=f_amount_label, fill=gold, anchor="mm")
    d.text((margin+160, y+39), str(datos.get("label_monto_abono", "MONTO RECIBIDO")).upper(), font=f_amount_label, fill=navy)
    d.text((margin+160, y+82), _fmt_bs(datos.get("monto_pagado", 0)), font=f_amount, fill=navy)
    y += box_h + 26

    # Resumen del periodo / garantía.
    resumen = [
        (datos.get("label_monto_esperado", "Monto esperado:"), _fmt_bs(datos.get("monto_esperado", 0))),
        (datos.get("label_total_pagado", "Total pagado a la fecha:"), _fmt_bs(datos.get("total_pagado_periodo", 0))),
        ("Saldo pendiente:" if float(datos.get("saldo_pendiente", 0) or 0) > .009 else "Estado:",
         _fmt_bs(datos.get("saldo_pendiente", 0)) if float(datos.get("saldo_pendiente", 0) or 0) > .009 else "PAGADO COMPLETO"),
    ]
    panel_h = 174
    d.rounded_rectangle((margin, y, W-margin, y+panel_h), radius=20, fill=pale)
    yy = y+23
    for idx, (label, value) in enumerate(resumen):
        d.text((margin+28, yy), str(label), font=f_small, fill=ink)
        d.text((W-margin-28, yy), str(value), font=f_small_b, fill=navy, anchor="ra")
        if idx < 2:
            d.line((margin+24, yy+37, W-margin-24, yy+37), fill=_GRIS, width=2)
        yy += 52
    y += panel_h + 28

    if datos.get("observacion"):
        d.text((margin+4, y), "OBSERVACIÓN", font=f_small_b, fill=navy)
        y += 32
        for line in _texto_envuelto(d, datos["observacion"], f_small, W-2*margin-10)[:2]:
            d.text((margin+4, y), line, font=f_small, fill=muted)
            y += 27

    # Pie de página institucional.
    footer_y = H-105
    d.line((margin, footer_y, W-margin, footer_y), fill=gold, width=3)
    d.text((margin+12, footer_y+25), str(datos.get("recibido_por", "Administración")), font=f_small, fill=ink)
    d.text((W//2, footer_y+25), "ADMINISTRACIÓN", font=f_small_b, fill=navy, anchor="mm")
    d.text((W-margin-10, footer_y+25), str(datos.get("fecha_emision", "")), font=f_small, fill=ink, anchor="ra")
    d.text((W//2, H-42), "¡Gracias por su pago!", font=_fuente(25, cursiva=True), fill=navy, anchor="mm")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


def generar_recibo_pdf(datos: dict) -> bytes:
    """PDF A5 de alta calidad generado desde el mismo arte que el PNG."""
    png = generar_recibo_png(datos)
    buffer = io.BytesIO()
    ancho = A5[0]
    alto = ancho * Image.open(io.BytesIO(png)).height / Image.open(io.BytesIO(png)).width
    c = pdfcanvas.Canvas(buffer, pagesize=(ancho, alto))
    c.drawImage(ImageReader(io.BytesIO(png)), 0, 0, width=ancho, height=alto, preserveAspectRatio=False)
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================


def _cabecera_estado_cuenta_png(ancho=1100, alto=300):
    """Cabecera institucional: logo completo a la izquierda y panel azul separado por diagonal dorada."""
    escala = ancho / 1100
    alto_real = int(alto * escala)
    cab = Image.new("RGB", (ancho, alto_real), "white")
    d = ImageDraw.Draw(cab)
    sx = lambda v: int(v * escala)
    navy, gold = _AZUL, _DORADO

    # La diagonal comienza más a la derecha y es menos inclinada para no invadir
    # visualmente el nombre del residencial ni dejar un corte abrupto junto al logo.
    d.polygon([(sx(790), 0), (ancho, 0), (ancho, alto_real), (sx(650), alto_real)], fill=navy)
    d.polygon([(sx(772), 0), (sx(790), 0), (sx(668), alto_real), (sx(650), alto_real)], fill=gold)

    ruta = LOGO_PATH if os.path.exists(LOGO_PATH) else LOGO_FALLBACK_PATH
    if os.path.exists(ruta):
        try:
            logo = Image.open(ruta).convert("RGBA")
            logo.thumbnail((sx(535), sx(205)), Image.Resampling.LANCZOS)
            cab.paste(logo, (sx(58), sx(46)), logo)
        except Exception:
            pass

    try:
        fuente_titulo = ImageFont.truetype(os.path.join(_DIR, "assets", "fonts", "DejaVuSans-Bold.ttf"), sx(22))
        fuente_sub = ImageFont.truetype(os.path.join(_DIR, "assets", "fonts", "DejaVuSans.ttf"), sx(11))
    except Exception:
        fuente_titulo = ImageFont.load_default()
        fuente_sub = ImageFont.load_default()
    d.text((sx(930), sx(105)), "ESTADO DE CUENTA", font=fuente_titulo, fill="white", anchor="mm")
    d.text((sx(930), sx(160)), "RESUMEN DE CUENTA DEL INQUILINO", font=fuente_sub, fill="white", anchor="mm")
    d.line((sx(58), alto_real-2, ancho-sx(58), alto_real-2), fill=gold, width=max(2, sx(4)))
    return cab

# REPORTE DE DEUDA REAL PARA EL INQUILINO (PDF y PNG, mismo diseño que el recibo)
# ============================================================
# El cálculo está en moras.deuda_real_inquilino(); aquí solo se maqueta.

MAX_FILAS_REPORTE = 12   # filas por tabla; las deudas siempre se muestran completas


@lru_cache(maxsize=1)
def _logo_liviano_bytes():
    """Logo reducido a 200 px (el original pesa ~190 KB y se incrustaría completo en cada PDF).
    Se guardan los bytes y no un ImageReader: reportlab (Platypus) solo acepta ruta o archivo."""
    logo = Image.open(LOGO_PATH).convert("RGBA")
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

    # ---------- Encabezado institucional: mismo arte diagonal del recibo ----------
    cabecera_img = _cabecera_estado_cuenta_png(1600, 224)
    cabecera_buffer = io.BytesIO()
    cabecera_img.save(cabecera_buffer, format="PNG", optimize=True)
    cabecera_buffer.seek(0)
    cabecera = RLImage(cabecera_buffer, width=ancho_util, height=ancho_util * 224 / 1100)
    story += [cabecera, Spacer(1, 7)]

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

    # ---------- Encabezado con el mismo diseño diagonal del recibo ----------
    ancho_cabecera = ancho - 2 * margen
    cabecera = _cabecera_estado_cuenta_png(ancho_cabecera, 224)
    img.paste(cabecera, (margen, y))
    y += cabecera.height + 24

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
        draw.rectangle([(margen, y), (ancho - margen, y + alto_fila)], fill=_AZUL)
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
