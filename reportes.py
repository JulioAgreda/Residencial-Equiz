"""
Reportes de actividad por usuario (cobrador), por rango de fechas, en Excel y PDF.

app.py arma, para cada usuario, un diccionario {clave_categoria: [filas...]} donde cada
fila ya viene con sus columnas en español y valores listos para mostrar (strings/números).
Este módulo solo se encarga de maquetar esos datos en un .xlsx o un .pdf.
"""
import io

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak

# (clave_interna, título visible, color de acento)
CATEGORIAS = [
    ("pagos_generales", "💳 Pagos realizados", "#2E7D32"),
    ("compras", "🧾 Compras realizadas", "#B71C1C"),
    ("ventas", "💸 Ventas realizadas", "#1565C0"),
    ("pagos_alquiler", "💵 Pagos de Alquiler", "#6A1B9A"),
    ("pagos_electricidad", "⚡ Pagos de Electricidad", "#E65100"),
]

_COLOR_HEADER = "2E4057"  # sin "#": así lo espera openpyxl (PatternFill); para reportlab se le agrega "#"


def _fmt_bs(v):
    try:
        return f"Bs {float(v):,.2f}"
    except (TypeError, ValueError):
        return "Bs 0.00"


def construir_reporte_usuario(nombre_usuario, datos_por_categoria):
    """datos_por_categoria: {clave: [fila_dict, ...]}, ya filtradas por usuario y rango.
    Cada fila debe tener una clave "Monto" (número) para poder sumar el subtotal.
    Devuelve {"usuario", "categorias": {clave: {"titulo","filas","total"}}, "total_general"}."""
    categorias = {}
    total_general = 0.0
    for clave, titulo, _color in CATEGORIAS:
        filas = datos_por_categoria.get(clave, [])
        total = sum(float(f.get("Monto") or 0) for f in filas)
        categorias[clave] = {"titulo": titulo, "filas": filas, "total": round(total, 2)}
        total_general += total
    return {"usuario": nombre_usuario, "categorias": categorias, "total_general": round(total_general, 2)}


def _nombre_hoja_valido(nombre, usados):
    """Los nombres de hoja de Excel no pueden tener: \\ / * ? : [ ] y deben ser únicos y de máx 31 chars."""
    limpio = "".join(c for c in nombre if c not in r"\/*?:[]") or "Usuario"
    limpio = limpio[:28]
    candidato = limpio
    i = 2
    while candidato in usados:
        candidato = f"{limpio[:25]} {i}"
        i += 1
    usados.add(candidato)
    return candidato


# ============================================================
# EXCEL
# ============================================================

def generar_excel_reporte(reportes, fecha_desde, fecha_hasta):
    """reportes: lista de resultados de construir_reporte_usuario (uno o varios)."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    fuente_titulo = Font(name="Calibri", bold=True, size=14)
    fuente_header = Font(name="Calibri", bold=True, color="FFFFFF")
    relleno_header = PatternFill("solid", fgColor=_COLOR_HEADER)
    fuente_normal = Font(name="Calibri", size=10)
    fuente_subtotal = Font(name="Calibri", bold=True, size=10)
    fuente_total = Font(name="Calibri", bold=True, size=12)

    # ---------- Hoja Resumen ----------
    ws = wb.create_sheet("Resumen")
    ws["A1"] = "Reporte de actividad por usuario"
    ws["A1"].font = fuente_titulo
    ws["A2"] = f"Periodo: {fecha_desde} al {fecha_hasta}"
    ws["A2"].font = fuente_normal

    fila = 4
    encabezados = ["Usuario"] + [t for _, t, _ in CATEGORIAS] + ["Total"]
    for col, texto in enumerate(encabezados, start=1):
        c = ws.cell(fila, col, texto)
        c.font = fuente_header
        c.fill = relleno_header
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    fila += 1
    for r in reportes:
        ws.cell(fila, 1, r["usuario"]).font = fuente_normal
        for col, (clave, _t, _c) in enumerate(CATEGORIAS, start=2):
            ws.cell(fila, col, r["categorias"][clave]["total"]).number_format = '"Bs" #,##0.00'
        ws.cell(fila, len(encabezados), r["total_general"]).number_format = '"Bs" #,##0.00'
        ws.cell(fila, len(encabezados)).font = fuente_subtotal
        fila += 1
    if len(reportes) > 1:
        fila_tg = fila + 1
        ws.cell(fila_tg, 1, "TOTAL GENERAL").font = fuente_total
        for col, (clave, _t, _c) in enumerate(CATEGORIAS, start=2):
            total_cat = sum(r["categorias"][clave]["total"] for r in reportes)
            cc = ws.cell(fila_tg, col, total_cat)
            cc.number_format = '"Bs" #,##0.00'
            cc.font = fuente_subtotal
        total_todo = sum(r["total_general"] for r in reportes)
        cc = ws.cell(fila_tg, len(encabezados), total_todo)
        cc.number_format = '"Bs" #,##0.00'
        cc.font = fuente_total
    ws.column_dimensions["A"].width = 26
    for col in range(2, len(encabezados) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 20

    # ---------- Una hoja por usuario, con el detalle de cada categoría ----------
    nombres_usados = {"Resumen"}
    for r in reportes:
        ws = wb.create_sheet(_nombre_hoja_valido(r["usuario"] or "Usuario", nombres_usados))
        fila = 1
        ws.cell(fila, 1, f'Detalle de {r["usuario"]}').font = fuente_titulo
        fila += 1
        ws.cell(fila, 1, f"Periodo: {fecha_desde} al {fecha_hasta}").font = fuente_normal
        fila += 2

        for clave, titulo, _color in CATEGORIAS:
            datos = r["categorias"][clave]
            ws.cell(fila, 1, titulo).font = Font(name="Calibri", bold=True, size=12)
            fila += 1
            filas_datos = datos["filas"]
            if not filas_datos:
                ws.cell(fila, 1, "Sin registros en este periodo.").font = fuente_normal
                fila += 2
                continue

            columnas = list(filas_datos[0].keys())
            for col, nombre_col in enumerate(columnas, start=1):
                c = ws.cell(fila, col, nombre_col)
                c.font = fuente_header
                c.fill = relleno_header
            fila += 1
            for fd in filas_datos:
                for col, nombre_col in enumerate(columnas, start=1):
                    valor = fd[nombre_col]
                    c = ws.cell(fila, col, valor)
                    c.font = fuente_normal
                    if nombre_col == "Monto" and isinstance(valor, (int, float)):
                        c.number_format = '"Bs" #,##0.00'
                fila += 1
            ws.cell(fila, 1, "Subtotal:").font = fuente_subtotal
            c = ws.cell(fila, 2, datos["total"])
            c.font = fuente_subtotal
            c.number_format = '"Bs" #,##0.00'
            fila += 2

        ws.cell(fila, 1, "TOTAL GENERAL:").font = fuente_total
        c = ws.cell(fila, 2, r["total_general"])
        c.font = fuente_total
        c.number_format = '"Bs" #,##0.00'

        ws.column_dimensions["A"].width = 16
        for col in range(2, 9):
            ws.column_dimensions[get_column_letter(col)].width = 18

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# PDF
# ============================================================

def generar_pdf_reporte(reportes, fecha_desde, fecha_hasta):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=14 * mm, bottomMargin=14 * mm,
                             leftMargin=14 * mm, rightMargin=14 * mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Reporte de actividad por usuario", styles["Title"]),
        Paragraph(f"Periodo: {fecha_desde} al {fecha_hasta}", styles["Normal"]),
        Spacer(1, 10),
    ]

    # ---------- Tabla resumen ----------
    encabezado = ["Usuario"] + [t for _, t, _ in CATEGORIAS] + ["Total"]
    filas_resumen = [encabezado]
    for r in reportes:
        filas_resumen.append(
            [r["usuario"]] + [_fmt_bs(r["categorias"][c]["total"]) for c, _t, _col in CATEGORIAS]
            + [_fmt_bs(r["total_general"])]
        )
    if len(reportes) > 1:
        fila_tot = ["TOTAL GENERAL"]
        for clave, _t, _c in CATEGORIAS:
            fila_tot.append(_fmt_bs(sum(r["categorias"][clave]["total"] for r in reportes)))
        fila_tot.append(_fmt_bs(sum(r["total_general"] for r in reportes)))
        filas_resumen.append(fila_tot)

    t = Table(filas_resumen, repeatRows=1, hAlign="LEFT")
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + _COLOR_HEADER)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if len(reportes) > 1:
        estilo.append(("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"))
        estilo.append(("LINEABOVE", (0, -1), (-1, -1), 1, colors.black))
    t.setStyle(TableStyle(estilo))
    story.append(t)
    story.append(Spacer(1, 16))

    # ---------- Detalle por usuario ----------
    for idx, r in enumerate(reportes):
        story.append(Paragraph(f'Detalle: {r["usuario"]}', styles["Heading2"]))
        for clave, titulo, _color in CATEGORIAS:
            datos = r["categorias"][clave]
            story.append(Paragraph(titulo, styles["Heading4"]))
            filas_datos = datos["filas"]
            if not filas_datos:
                story.append(Paragraph("Sin registros en este periodo.", styles["Normal"]))
            else:
                columnas = list(filas_datos[0].keys())
                tabla_datos = [columnas] + [
                    [_fmt_bs(f[c]) if c == "Monto" else str(f[c]) for c in columnas] for f in filas_datos
                ]
                tt = Table(tabla_datos, repeatRows=1, hAlign="LEFT")
                tt.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dddddd")),
                    ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]))
                story.append(tt)
                story.append(Paragraph(f'<b>Subtotal: {_fmt_bs(datos["total"])}</b>', styles["Normal"]))
            story.append(Spacer(1, 8))
        story.append(Paragraph(f'<b>Total general de {r["usuario"]}: {_fmt_bs(r["total_general"])}</b>',
                                styles["Normal"]))
        if idx < len(reportes) - 1:
            story.append(PageBreak())
        else:
            story.append(Spacer(1, 10))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
