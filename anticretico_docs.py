# Generadores PDF exclusivos para entregas de capital anticrético.
# Este módulo no modifica ni reutiliza los diseños de recibos ordinarios.
import os
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(_DIR, "assets", "logo_equise_horizontal.png")
LOGO_FALLBACK = os.path.join(_DIR, "assets", "logo_equise.png")

def _font_setup():
    fonts = os.path.join(_DIR, "assets", "fonts")
    try:
        if "EquiseSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("EquiseSans", os.path.join(fonts, "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont("EquiseSans-Bold", os.path.join(fonts, "DejaVuSans-Bold.ttf")))
    except Exception:
        pass
    return ("EquiseSans" if "EquiseSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica",
            "EquiseSans-Bold" if "EquiseSans-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold")

def _money(v, currency="BOB"):
    try: n=float(v or 0)
    except Exception: n=0
    prefix = "USD" if str(currency).upper()=="USD" else "Bs"
    return f"{prefix} {n:,.2f}"

def _date(v):
    if not v: return "—"
    try:
        return str(v)[:10]
    except Exception:
        return str(v)

def _styles():
    regular,bold=_font_setup()
    ss=getSampleStyleSheet()
    ss.add(ParagraphStyle(name="EquiseBody", parent=ss["Normal"], fontName=regular, fontSize=9, leading=13, textColor=colors.HexColor("#222222")))
    ss.add(ParagraphStyle(name="EquiseSmall", parent=ss["Normal"], fontName=regular, fontSize=8, leading=11, textColor=colors.HexColor("#555555")))
    ss.add(ParagraphStyle(name="EquiseTitle", parent=ss["Normal"], fontName=bold, fontSize=16, leading=20, textColor=colors.HexColor("#17365D")))
    ss.add(ParagraphStyle(name="EquiseSub", parent=ss["Normal"], fontName=bold, fontSize=10, leading=14, textColor=colors.HexColor("#17365D")))
    ss.add(ParagraphStyle(name="EquiseRight", parent=ss["Normal"], fontName=regular, fontSize=9, leading=12, alignment=TA_RIGHT))
    return ss, regular, bold

def _header(title, subtitle="Documento de control de capital anticrético"):
    ss,regular,bold=_styles()
    logo_file=LOGO_PATH if os.path.exists(LOGO_PATH) else LOGO_FALLBACK
    logo_cell=""
    if os.path.exists(logo_file):
        try:
            from reportlab.platypus import Image
            img=Image(logo_file, width=52*mm, height=19*mm, kind="proportional")
            logo_cell=img
        except Exception:
            logo_cell=Paragraph("<b>RESIDENCIAL EQUISE</b>",ss["EquiseSub"])
    else:
        logo_cell=Paragraph("<b>RESIDENCIAL EQUISE</b>",ss["EquiseSub"])
    right=Paragraph(f"<b>{title}</b><br/><font size='8'>{subtitle}</font>",ss["EquiseRight"])
    tbl=Table([[logo_cell,right]], colWidths=[85*mm,95*mm], rowHeights=[24*mm])
    tbl.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ALIGN",(1,0),(1,0),"RIGHT"),
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F1F4F8")),
        ("LINEBELOW",(0,0),(-1,-1),1.5,colors.HexColor("#17365D")),
        ("LEFTPADDING",(0,0),(-1,-1),5*mm),("RIGHTPADDING",(0,0),(-1,-1),5*mm),
        ("TOPPADDING",(0,0),(-1,-1),2*mm),("BOTTOMPADDING",(0,0),(-1,-1),2*mm),
    ]))
    return tbl,ss

def _doc(story):
    buff=io.BytesIO()
    doc=SimpleDocTemplate(buff,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=16*mm,bottomMargin=17*mm,title="Residencial EQUISE - Capital anticrético")
    doc.build(story)
    return buff.getvalue()

def generar_recibo_anticretico_pdf(datos):
    header,ss=_header("RECIBO DE ENTREGA","Capital anticrético")
    story=[header,Spacer(1,7*mm),Paragraph("RECIBO",ss["EquiseTitle"]),Spacer(1,2*mm)]
    num=datos.get("numero_recibo","—")
    status=str(datos.get("estado_recibo","vigente")).upper()
    meta=Table([[Paragraph(f"<b>N.º:</b> {num}",ss["EquiseBody"]),Paragraph(f"<b>Estado:</b> {status}",ss["EquiseRight"])]],colWidths=[90*mm,90*mm])
    meta.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#EAF0F7")),("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#AAB7C4")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("PADDING",(0,0),(-1,-1),5)]))
    story += [meta,Spacer(1,5*mm)]
    fields=[
        ("Apartamento / inmueble",datos.get("apartamento","—")),
        ("Fecha de recepción",_date(datos.get("fecha_entrega"))),
        ("Entregante",datos.get("entregante","—")),
        ("Recibido / registrado por",datos.get("recibido_por","—")),
        ("Monto recibido",datos.get("monto_texto","—")),
        ("Momento de entrega",datos.get("etapa_texto","—")),
        ("Medio de pago",datos.get("medio_pago","—")),
        ("Referencia",datos.get("referencia") or "—"),
        ("Saldo de capital posterior",datos.get("saldo_posterior","—")),
        ("Concepto",datos.get("concepto") or "Entrega a cuenta del capital anticrético"),
        ("Observaciones",datos.get("observacion") or "—"),
    ]
    t=Table([[Paragraph(f"<b>{a}</b>",ss["EquiseBody"]),Paragraph(str(b).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"),ss["EquiseBody"])] for a,b in fields],colWidths=[55*mm,125*mm])
    t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#B8C1CA")),("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F1F4F8")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story += [t,Spacer(1,13*mm)]
    story += [Paragraph("Documento generado por el sistema administrativo de Residencial EQUISE. Conserve este recibo como constancia de la entrega registrada.",ss["EquiseSmall"]),Spacer(1,15*mm)]
    sig=Table([["____________________________","____________________________"],["ENTREGANTE","RESPONSABLE DE RECEPCIÓN"]],colWidths=[90*mm,90*mm])
    sig.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER"),("FONTNAME",(0,0),(-1,-1),ss["EquiseBody"].fontName),("FONTSIZE",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),4)]))
    story.append(sig)
    return _doc(story)

def generar_estado_cuenta_anticretico_pdf(datos):
    header,ss=_header("ESTADO DE CUENTA","Capital anticrético")
    story=[header,Spacer(1,7*mm),Paragraph("ESTADO DE CUENTA DE CAPITAL ANTICRÉTICO",ss["EquiseTitle"]),Spacer(1,4*mm)]
    apt=datos.get("apartamento","—")
    fields=[["Apartamento / inmueble",apt],["Titular registrado",datos.get("titular","—")],["Fecha de emisión",datetime.now().strftime("%d/%m/%Y")]]
    info=Table([[Paragraph(f"<b>{a}</b>",ss["EquiseBody"]),Paragraph(str(b),ss["EquiseBody"])] for a,b in fields],colWidths=[55*mm,125*mm])
    info.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#B8C1CA")),("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F1F4F8")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("PADDING",(0,0),(-1,-1),5)]))
    story += [info,Spacer(1,5*mm)]
    moneda=datos.get("moneda","BOB")
    summary=[[ "Capital acordado",_money(datos.get("capital"),moneda)],["Total recibido",_money(datos.get("recibido"),moneda)],["Saldo por recibir",_money(datos.get("saldo"),moneda)]]
    st=Table([[Paragraph(f"<b>{a}</b>",ss["EquiseBody"]),Paragraph(b,ss["EquiseBody"])] for a,b in summary],colWidths=[55*mm,125*mm])
    st.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#17365D")),("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#EAF0F7")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("PADDING",(0,0),(-1,-1),7)]))
    story += [st,Spacer(1,6*mm),Paragraph("Historial de entregas",ss["EquiseSub"]),Spacer(1,2*mm)]
    rows=[["Recibo","Fecha","Etapa","Entregante","Monto","Medio","Estado"]]
    for x in sorted(datos.get("entregas",[]) or [],key=lambda r:(r.get("fecha_entrega") or "",r.get("created_at") or "")):
        etapa="Antes de firma" if x.get("etapa")=="antes_firma" else "Después de firma"
        rows.append([str(x.get("numero_recibo") or "—"),_date(x.get("fecha_entrega")),etapa,str(x.get("entregante") or "—"),_money(x.get("monto"),x.get("moneda") or moneda),str(x.get("medio_pago") or "—"),str(x.get("estado") or "vigente").upper()])
    data=[]
    for row in rows:
        data.append([Paragraph(str(cell).replace("&","&amp;"),ss["EquiseSmall"]) for cell in row])
    tab=Table(data,colWidths=[24*mm,23*mm,29*mm,34*mm,28*mm,22*mm,20*mm],repeatRows=1)
    tab.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17365D")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#B8C1CA")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [tab,Spacer(1,7*mm),Paragraph("Documento informativo generado por el sistema administrativo de Residencial EQUISE. El estado refleja los registros vigentes de entregas de capital anticrético.",ss["EquiseSmall"])]
    return _doc(story)
