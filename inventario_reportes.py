"""
Reportes de inventario en Excel y PDF: existencias (stock actual valorizado), Kardex de un artículo y movimientos de un
periodo. Reutilizan el estilo de los demás reportes (cuadre.py).

Todos reciben los datos ya calculados por inventario.py; aquí solo se les da formato.
"""
import io
from datetime import date

import openpyxl
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, Paragraph, Spacer

import cuadre as cd
import inventario as inv
import reportes as rp


def _n(valor, decimales=2):
    return "" if valor is None else f"{valor:,.{decimales}f}"


def _cant(valor):
    return "" if valor is None else inv.formato_cantidad(valor)


def _costo(valor):
    """Costo unitario con 1 decimal (3.5). El costo promedio se muestra redondeado; los valores en Bs usan el promedio exacto."""
    return "" if valor is None else f"{inv.a_un_decimal(valor):,.1f}"


def _libro(nombre_hoja, titulo, subtitulo, columnas, filas, totales=None):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    cd._hoja(wb, nombre_hoja, titulo, subtitulo, columnas, filas, totales)
    return wb


def _a_bytes(wb):
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ============================================================
# EXISTENCIAS (stock actual)
# ============================================================

COLUMNAS_EXISTENCIAS = [("codigo", "Código", "txt"), ("nombre", "Artículo", "txt"), ("categoria", "Categoría", "txt"),
                        ("unidad", "Unidad", "txt"), ("ubicacion", "Ubicación", "txt"), ("cantidad", "Stock", "num"),
                        ("stock_minimo", "Mínimo", "num"), ("costo_promedio", "Costo promedio (Bs)", "bs1"),
                        ("valor", "Valor (Bs)", "bs"), ("estado", "Estado", "txt")]


def generar_excel_existencias(filas, valor_total, hoy=None, emitido_por=None):
    hoy = hoy or date.today()
    sub = f"Al {rp._fmt_fecha(hoy)}  ·  Costo promedio ponderado" + (f"  ·  Emitido por: {emitido_por}" if emitido_por else "")
    return _a_bytes(_libro("Existencias", "Existencias de inventario", sub, COLUMNAS_EXISTENCIAS, filas, {"valor": valor_total}))


def generar_pdf_existencias(filas, resumen, hoy=None, emitido_por=None):
    """resumen: {'valor_total', 'n_activos', 'n_bajo', 'n_sin_stock'} (lo que devuelve inventario.existencias)."""
    hoy = hoy or date.today()
    buffer = io.BytesIO()
    doc, ancho = cd.documento_pdf(buffer, "Existencias de inventario")
    est = cd.estilos_pdf()
    story = cd.cabecera_pdf("Existencias de inventario", hoy, hoy, emitido_por, ancho, est, texto_periodo=f"Al {rp._fmt_fecha(hoy)}")
    story.append(Paragraph(f"<b>Artículos:</b> {resumen['n_activos']} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Valor del inventario:</b> "
                           f"Bs {_n(resumen['valor_total'])} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Stock bajo:</b> {resumen['n_bajo']} "
                           f"&nbsp;&nbsp;|&nbsp;&nbsp; <b>Sin stock:</b> {resumen['n_sin_stock']}", est.chico))
    story.append(Spacer(1, 4))
    if filas:
        story.append(cd.tabla_pdf(
            ["Código", "Artículo", "Categoría", "Unidad", "Ubicación", "Stock", "Mínimo", "Costo prom.", "Valor (Bs)", "Estado"],
            [[f["codigo"], f["nombre"], f["categoria"], f["unidad"], f["ubicacion"], _cant(f["cantidad"]), _cant(f["stock_minimo"]),
              _costo(f["costo_promedio"]), _n(f["valor"]), f["estado"]] for f in filas],
            [1.1, 3.2, 1.7, 1.0, 1.6, 1.0, 1.0, 1.2, 1.3, 1.2], (5, 6, 7, 8),
            ["TOTAL", "", "", "", "", "", "", "", _n(sum(f["valor"] for f in filas if f["activo"])), ""], ancho=ancho, est=est))
        story.append(Paragraph("Valorizado a costo promedio ponderado. «Stock bajo»: el stock llegó al mínimo definido para el artículo.", est.nota))
    else:
        story.append(Paragraph("No hay artículos para mostrar.", est.nota))
    story += cd.firmas_pdf(ancho, "Elaborado por", "Revisado por (Administración)")
    doc.build(story)
    return buffer.getvalue()


# ============================================================
# KARDEX de un artículo
# ============================================================

COLUMNAS_KARDEX = [("fecha_txt", "Fecha", "txt"), ("detalle", "Detalle", "txt"),
                   ("entrada_cantidad", "Entrada: cantidad", "num"), ("entrada_costo", "Entrada: costo unit.", "bs1"),
                   ("entrada_valor", "Entrada: valor", "bs"), ("salida_cantidad", "Salida: cantidad", "num"),
                   ("salida_costo", "Salida: costo unit.", "bs1"), ("salida_valor", "Salida: valor", "bs"),
                   ("saldo_cantidad", "Saldo: cantidad", "num"), ("saldo_costo", "Saldo: costo prom.", "bs1"),
                   ("saldo_valor", "Saldo: valor", "bs")]


def _detalle(fila):
    partes = [fila["motivo"]]
    if fila.get("destino"):
        partes.append(fila["destino"])
    if fila.get("documento"):
        partes.append(f"Doc. {fila['documento']}")
    return " · ".join(partes)


def filas_kardex(kp, con_saldo_inicial=True):
    """Filas listas para mostrar: (saldo inicial del periodo, si lo hay) + los movimientos."""
    filas = []
    si = kp["saldo_inicial"]
    if con_saldo_inicial and (si["cantidad"] or si["valor"]):
        filas.append({"fecha_txt": "", "detalle": "SALDO INICIAL DEL PERIODO", "saldo_cantidad": si["cantidad"],
                      "saldo_costo": si["costo"], "saldo_valor": si["valor"]})
    filas += [{**f, "detalle": _detalle(f)} for f in kp["filas"]]
    return filas


def _titulo_kardex(articulo):
    return f"Kardex — {articulo.get('codigo', '')} {articulo.get('nombre', '')} ({articulo.get('unidad', '')})"


def _periodo_kardex(desde, hasta):
    return "Todo el historial" if not desde and not hasta else f"Del {rp._fmt_fecha(desde) if desde else 'inicio'} al {rp._fmt_fecha(hasta) if hasta else 'hoy'}"


def generar_excel_kardex(articulo, kp, desde=None, hasta=None, emitido_por=None):
    sub = f"{_periodo_kardex(desde, hasta)}  ·  Costo promedio ponderado" + (f"  ·  Emitido por: {emitido_por}" if emitido_por else "")
    totales = {"entrada_cantidad": kp["entradas"]["cantidad"], "entrada_valor": kp["entradas"]["valor"],
               "salida_cantidad": kp["salidas"]["cantidad"], "salida_valor": kp["salidas"]["valor"]}
    return _a_bytes(_libro("Kardex", _titulo_kardex(articulo), sub, COLUMNAS_KARDEX, filas_kardex(kp), totales))


def generar_pdf_kardex(articulo, kp, desde=None, hasta=None, emitido_por=None):
    buffer = io.BytesIO()
    doc, ancho = cd.documento_pdf(buffer, "Kardex de inventario")
    est = cd.estilos_pdf()
    story = cd.cabecera_pdf(_titulo_kardex(articulo), desde or date.today(), hasta or date.today(), emitido_por, ancho, est,
                            texto_periodo=_periodo_kardex(desde, hasta))
    sf = kp["saldo_final"]
    story.append(Paragraph(f"<b>Saldo final:</b> {_cant(sf['cantidad'])} {rp._pdf_texto(articulo.get('unidad', ''))} &nbsp;&nbsp;|&nbsp;&nbsp; "
                           f"<b>Costo promedio:</b> Bs {_costo(sf['costo'])} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Valor:</b> Bs {_n(sf['valor'])}", est.chico))
    story.append(Spacer(1, 4))
    filas = filas_kardex(kp)
    if filas:
        story.append(cd.tabla_pdf(
            ["Fecha", "Detalle", "Entrada cant.", "Entrada costo", "Entrada valor", "Salida cant.", "Salida costo", "Salida valor",
             "Saldo cant.", "Saldo costo", "Saldo valor"],
            [[f["fecha_txt"], f["detalle"], _cant(f.get("entrada_cantidad")), _costo(f.get("entrada_costo")), _n(f.get("entrada_valor")),
              _cant(f.get("salida_cantidad")), _costo(f.get("salida_costo")), _n(f.get("salida_valor")),
              _cant(f.get("saldo_cantidad")), _costo(f.get("saldo_costo")), _n(f.get("saldo_valor"))] for f in filas],
            [1.1, 3.6, 1.1, 1.1, 1.2, 1.1, 1.1, 1.2, 1.1, 1.1, 1.3], tuple(range(2, 11)),
            ["TOTAL", "", _cant(kp["entradas"]["cantidad"]), "", _n(kp["entradas"]["valor"]), _cant(kp["salidas"]["cantidad"]), "",
             _n(kp["salidas"]["valor"]), "", "", ""], ancho=ancho, est=est))
        story.append(Paragraph("Costo promedio ponderado: cada salida se valora al costo promedio que tenía el artículo ese día. El costo se muestra con 1 decimal; el valor se calcula con el promedio exacto.", est.nota))
    else:
        story.append(Paragraph("Este artículo no tiene movimientos en el periodo.", est.nota))
    story += cd.firmas_pdf(ancho, "Elaborado por", "Revisado por (Administración)")
    doc.build(story)
    return buffer.getvalue()


# ============================================================
# MOVIMIENTOS de un periodo
# ============================================================

COLUMNAS_MOVIMIENTOS = [("fecha_txt", "Fecha", "txt"), ("codigo", "Código", "txt"), ("articulo", "Artículo", "txt"),
                        ("tipo", "Tipo", "txt"), ("motivo", "Motivo", "txt"), ("destino", "Destino", "txt"),
                        ("documento", "Documento", "txt"), ("cantidad", "Cantidad", "num"), ("unidad", "Unidad", "txt"),
                        ("costo_unitario", "Costo unitario (Bs)", "bs1"), ("valor", "Valor (Bs)", "bs"),
                        ("registrado_por", "Registrado por", "txt")]
COLUMNAS_POR_MOTIVO = [("tipo", "Tipo", "txt"), ("motivo", "Motivo", "txt"), ("n", "Movimientos", "num"), ("valor", "Valor (Bs)", "bs")]


def _periodo_mov(desde, hasta):
    return f"Del {rp._fmt_fecha(desde) if desde else 'inicio'} al {rp._fmt_fecha(hasta) if hasta else 'hoy'}"


def generar_excel_movimientos(mv, desde=None, hasta=None, emitido_por=None):
    """mv: lo que devuelve inventario.movimientos_valorizados."""
    sub = _periodo_mov(desde, hasta) + (f"  ·  Emitido por: {emitido_por}" if emitido_por else "")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    cd._hoja(wb, "Movimientos", "Movimientos de inventario", sub, COLUMNAS_MOVIMIENTOS, mv["filas"])
    resumen = [{"tipo": "Entradas", "motivo": "Todas", "n": mv["n_entradas"], "valor": mv["entradas_valor"]},
               {"tipo": "Salidas", "motivo": "Todas", "n": mv["n_salidas"], "valor": mv["salidas_valor"]}] + mv["por_motivo"]
    cd._hoja(wb, "Resumen", "Resumen de movimientos por motivo", sub, COLUMNAS_POR_MOTIVO, resumen)
    return _a_bytes(wb)


def generar_pdf_movimientos(mv, desde=None, hasta=None, emitido_por=None):
    buffer = io.BytesIO()
    doc, ancho = cd.documento_pdf(buffer, "Movimientos de inventario")
    est = cd.estilos_pdf()
    story = cd.cabecera_pdf("Movimientos de inventario", desde or date.today(), hasta or date.today(), emitido_por, ancho, est,
                            texto_periodo=_periodo_mov(desde, hasta))
    story.append(Paragraph(f"<b>Entradas:</b> {mv['n_entradas']} (Bs {_n(mv['entradas_valor'])}) &nbsp;&nbsp;|&nbsp;&nbsp; "
                           f"<b>Salidas:</b> {mv['n_salidas']} (Bs {_n(mv['salidas_valor'])})", est.chico))
    story.append(Spacer(1, 4))
    if mv["filas"]:
        story.append(cd.tabla_pdf(
            ["Fecha", "Artículo", "Tipo", "Motivo", "Destino", "Documento", "Cantidad", "Costo unit.", "Valor (Bs)"],
            [[f["fecha_txt"], f"{f['codigo']} {f['articulo']}", f["tipo"], f["motivo"], f["destino"], f["documento"],
              f"{_cant(f['cantidad'])} {f['unidad']}", _costo(f["costo_unitario"]), _n(f["valor"])] for f in mv["filas"]],
            [1.1, 3.3, 1.0, 2.4, 1.9, 1.3, 1.4, 1.1, 1.2], (6, 7, 8), ancho=ancho, est=est))
        story.append(CondPageBreak(30 * mm))
        story.append(Paragraph("Por motivo", est.sec))
        story.append(cd.tabla_pdf(["Tipo", "Motivo", "Movimientos", "Valor (Bs)"],
                                  [[x["tipo"], x["motivo"], str(x["n"]), _n(x["valor"])] for x in mv["por_motivo"]],
                                  [1.2, 4, 1.4, 1.6], (2, 3), ancho=ancho, est=est, ancho_tabla=ancho * 0.5))
        story.append(Paragraph("Las salidas se valoran al costo promedio ponderado que tenía el artículo ese día.", est.nota))
    else:
        story.append(Paragraph("No hay movimientos en este periodo.", est.nota))
    story += cd.firmas_pdf(ancho, "Elaborado por", "Revisado por (Administración)")
    doc.build(story)
    return buffer.getvalue()
