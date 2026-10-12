"""
Rendición de alquileres: el DINERO QUE INGRESÓ en un periodo (un mes o un rango de fechas), para rendir cuentas.

Reglas:
  * Lo cobrado es lo que se recibió ENTRE las dos fechas: cada pago (abono) cuenta según su FECHA DE PAGO, sin importar a
    qué mes corresponda. Un pago hecho en julio por el alquiler de octubre aparece en el reporte de julio, no en el de octubre.
    El detalle de pagos y el resumen por apartamento salen de los mismos pagos, así que siempre suman lo mismo.
  * Alquiler, luz y agua se muestran por separado. Cada pago indica además el «mes que paga».
  * «Deuda pendiente» es lo que todavía falta pagar de los MESES que toca el periodo (alquiler, luz y agua), a la fecha de
    hoy: pago parcial o ningún pago; si se pagó de más, la deuda es 0, no negativa. No depende de cuándo se pagó.
  * Solo cuenta el inquilino ACTUAL de cada apartamento (periodos abiertos), igual que el Dashboard y el Estado de cuenta.
  * Alquiler: la deuda se calcula como en el estado de cuenta (moras.deuda_real_inquilino): un mes sin ningún registro se
    cobra con el alquiler de la ficha. Luz y agua: solo los meses con lectura registrada.
  * Contratos de anticrético y apartamentos desocupados no generan alquiler mensual.

Módulo sin dependencias de Streamlit ni de la base: recibe listas de diccionarios y devuelve datos listos para
mostrar o exportar a Excel y PDF.
"""
import io
from datetime import date
from decimal import Decimal

import openpyxl
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, Paragraph, Spacer

import aire_acondicionado
import cuadre as cd
import moras
import reportes as rp

MAX_MESES = 24
_TOL = 0.009


def meses_en_rango(desde, hasta):
    """[(año, mes)] desde el mes de «desde» hasta el mes de «hasta», ambos incluidos."""
    return list(moras._meses_entre((desde.year, desde.month), (hasta.year, hasta.month)))


def _etiqueta_a_clave(etiqueta):
    """'Octubre 2026' -> (2026, 10). Las filas de moras.deuda_real_inquilino traen el periodo como texto."""
    mes, _, anio = str(etiqueta).rpartition(" ")
    return int(anio), moras._mes_num(mes)


def _agrupar(periodos):
    por_apt = {}
    for p in periodos or []:
        por_apt.setdefault(p.get("apartamento_id"), []).append(p)
    return por_apt


def _montos_registrados(periodos, campo_pagos, meses):
    """(a cobrar, pagado, deuda) de los periodos registrados que caen en los meses indicados. La deuda de cada
    periodo no baja de 0 (un pago de más no resta deuda de otro mes)."""
    esperado = pagado = deuda = Decimal(0)
    for p in periodos:
        if moras._clave_periodo(p) not in meses:
            continue
        e, g = cd._d(p.get("monto_esperado")), sum((cd._d(a.get("monto")) for a in (p.get(campo_pagos) or [])), Decimal(0))
        esperado, pagado, deuda = esperado + e, pagado + g, deuda + max(e - g, Decimal(0))
    return esperado, pagado, deuda


def _montos_alquiler(apt, periodos, meses, hoy):
    """Igual que el estado de cuenta: incluye los meses sin registro (con el alquiler de la ficha). Si el apartamento no
    genera alquiler mensual (desocupado, anticrético), solo lo que haya registrado."""
    d = moras.deuda_real_inquilino(apt, periodos, [], hoy)
    if not d["aplica"]:
        return _montos_registrados(periodos, "pagos", meses)
    esperado = pagado = deuda = Decimal(0)
    for fila in d["alquiler"]["filas"]:
        if _etiqueta_a_clave(fila["periodo"]) in meses:
            esperado += cd._d(fila["esperado"])
            pagado += cd._d(fila["pagado"])
            deuda += cd._d(fila["saldo"])
    return esperado, pagado, deuda


CONCEPTOS = ("Alquiler", "Luz", "Agua")


def construir_rendicion(apartamentos, periodos_alquiler, periodos_electricidad, periodos_agua, desde, hasta,
                        hoy=None, solo_con_deuda=False, solo_con_cobros=False):
    """Todo lo que muestra y exporta el reporte. Los periodos son los ABIERTOS (inquilino actual) con sus abonos
    embebidos ('pagos' / 'pagos_electricidad' / 'pagos_agua', cada uno con monto, fecha, metodo_pago y observacion).
    desde / hasta: fechas (ambas incluidas) entre las que se recibió el dinero."""
    hoy = hoy or date.today()
    meses = set(meses_en_rango(desde, hasta))                     # solo para la deuda pendiente
    alq, luz, agua = _agrupar(periodos_alquiler), _agrupar(periodos_electricidad), _agrupar(periodos_agua)

    filas, movimientos = [], []
    for apt in apartamentos:
        id_apt = apt["id"]
        # ---- dinero recibido entre las dos fechas (por fecha de pago) ----
        cobrado, movs_apt = {}, []
        for concepto, clave_c, periodos, campo in (("Alquiler", "alquiler", alq.get(id_apt, []), "pagos"),
                                                   ("Luz", "luz", luz.get(id_apt, []), "pagos_electricidad"),
                                                   ("Agua", "agua", agua.get(id_apt, []), "pagos_agua")):
            cobrado[clave_c] = Decimal(0)
            for p in periodos:
                clave = moras._clave_periodo(p)
                for a in p.get(campo) or []:
                    f = cd._fecha(a.get("fecha"))
                    if not f or not (desde <= f <= hasta):
                        continue
                    cobrado[clave_c] += cd._d(a.get("monto"))
                    movs_apt.append({
                        "fecha": f, "fecha_txt": rp._fmt_fecha(f), "apartamento": apt.get("codigo") or "—",
                        "inquilino": (apt.get("inquilino_nombre") or "—") if apt.get("estado") == "Ocupado" else "—",
                        "concepto": concepto, "periodo": f"{moras.MESES[clave[1] - 1]} {clave[0]}" if clave else "—",
                        "metodo": rp._txt(a.get("metodo_pago")) or "—", "observacion": rp._txt(a.get("observacion")),
                        "monto": cd._f(cd._d(a.get("monto")))})
        total_cobrado = sum(cobrado.values(), Decimal(0))

        # ---- deuda pendiente de los meses del periodo (a hoy) ----
        por_concepto = {
            "alquiler": _montos_alquiler(apt, alq.get(id_apt, []), meses, hoy),
            "luz": _montos_registrados(luz.get(id_apt, []), "pagos_electricidad", meses),
            "agua": _montos_registrados(agua.get(id_apt, []), "pagos_agua", meses),
        }
        a_cobrar = sum((v[0] for v in por_concepto.values()), Decimal(0))
        deuda = sum((v[2] for v in por_concepto.values()), Decimal(0))

        ocupado = apt.get("estado") == "Ocupado"
        if not ocupado and a_cobrar <= _TOL and total_cobrado <= _TOL:
            continue                                     # desocupado y sin movimientos
        if solo_con_deuda and deuda <= _TOL:
            continue
        if solo_con_cobros and total_cobrado <= _TOL:
            continue
        fila = {
            "apartamento_id": id_apt, "apartamento": apt.get("codigo") or "—", "piso": apt.get("piso") or "—",
            "estado": apt.get("estado") or "—", "inquilino": (apt.get("inquilino_nombre") or "—") if ocupado else "—",
            "celular": (apt.get("celular") or "—") if ocupado else "—",
            "alquiler": cd._f(cobrado["alquiler"]), "luz": cd._f(cobrado["luz"]), "agua": cd._f(cobrado["agua"]),
            "total": cd._f(total_cobrado), "deuda": cd._f(deuda),
            "aire": aire_acondicionado.resumen(apt.get("aire_acondicionado"), apt.get("aire_acondicionado_propiedad"),
                                               "aire_acondicionado_propiedad" in apt),
            "contrato": " · ".join(x for x in (apt.get("tipo_contrato"), apt.get("estado_contrato")) if x) or "—",
        }
        for clave, (e, g, dd) in por_concepto.items():     # detalle de la deuda: a cobrar / pagado (a hoy) / deuda de esos meses
            fila[f"{clave}_acobrar"], fila[f"{clave}_pagado"], fila[f"{clave}_deuda"] = cd._f(e), cd._f(g), cd._f(dd)
        filas.append(fila)
        movimientos.extend(movs_apt)
    movimientos.sort(key=lambda m: (m["fecha"], m["apartamento"], m["concepto"]))

    def suma(clave):
        return cd._f(sum((cd._d(f[clave]) for f in filas), Decimal(0)))

    totales = {k: suma(k) for k in ("alquiler", "luz", "agua", "total", "deuda")}
    por_concepto_mov = []
    for concepto in CONCEPTOS:
        sel = [m for m in movimientos if m["concepto"] == concepto]
        por_concepto_mov.append({"concepto": concepto, "n": len(sel),
                                 "total": cd._f(sum((cd._d(m["monto"]) for m in sel), Decimal(0)))})
    return {"desde": desde, "hasta": hasta, "meses": sorted(meses), "n_apartamentos": len(filas), "filas": filas,
            "totales": totales, "movimientos": movimientos, "n_pagos": len(movimientos),
            "pagos_por_concepto": por_concepto_mov, "con_deuda": sum(1 for f in filas if f["deuda"] > _TOL)}


def texto_meses(rendicion):
    """'Octubre 2026' o 'Septiembre 2026 a Noviembre 2026'."""
    etiquetas = [f"{moras.MESES[m - 1]} {a}" for a, m in rendicion["meses"]]
    return etiquetas[0] if len(etiquetas) == 1 else f"{etiquetas[0]} a {etiquetas[-1]}"


# ============================================================
# EXCEL
# ============================================================

COLUMNAS_RESUMEN = [("apartamento", "Apartamento", "txt"), ("piso", "Piso", "txt"), ("estado", "Estado", "txt"),
                    ("inquilino", "Inquilino", "txt"), ("celular", "Celular", "txt"), ("alquiler", "Alquiler cobrado", "bs"),
                    ("luz", "Luz cobrada", "bs"), ("agua", "Agua cobrada", "bs"), ("total", "Total cobrado", "bs"),
                    ("deuda", "Deuda pendiente", "bs"), ("aire", "Aire acondicionado", "txt"), ("contrato", "Contrato", "txt")]
COLUMNAS_DETALLE = [("apartamento", "Apartamento", "txt"), ("inquilino", "Inquilino", "txt"),
                    ("alquiler_acobrar", "Alquiler a cobrar", "bs"), ("alquiler_pagado", "Alquiler pagado", "bs"), ("alquiler_deuda", "Alquiler deuda", "bs"),
                    ("luz_acobrar", "Luz a cobrar", "bs"), ("luz_pagado", "Luz pagado", "bs"), ("luz_deuda", "Luz deuda", "bs"),
                    ("agua_acobrar", "Agua a cobrar", "bs"), ("agua_pagado", "Agua pagado", "bs"), ("agua_deuda", "Agua deuda", "bs"),
                    ("deuda", "Deuda total", "bs")]
COLUMNAS_MOVIMIENTOS = [("fecha_txt", "Fecha de pago", "txt"), ("apartamento", "Apartamento", "txt"), ("inquilino", "Inquilino", "txt"),
                        ("concepto", "Concepto", "txt"), ("periodo", "Mes que paga", "txt"), ("metodo", "Método", "txt"),
                        ("observacion", "Observación", "txt"), ("monto", "Monto", "bs")]


def _totales_detalle(r):
    claves = [c for c, _e, t in COLUMNAS_DETALLE if t == "bs"]
    return {c: cd._f(sum((cd._d(f[c]) for f in r["filas"]), Decimal(0))) for c in claves}


def generar_excel_rendicion(r, emitido_por=None):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    periodo = f"Dinero recibido del {rp._fmt_fecha(r['desde'])} al {rp._fmt_fecha(r['hasta'])}  ·  Deuda de: {texto_meses(r)}"
    if emitido_por:
        periodo += f"  ·  Emitido por: {emitido_por}"
    cd._hoja(wb, "Rendición", "Rendición de alquileres: dinero recibido en el periodo", periodo, COLUMNAS_RESUMEN, r["filas"], r["totales"])
    cd._hoja(wb, "Deuda por servicio", "Deuda pendiente por servicio (meses que toca el periodo, a hoy)", periodo,
             COLUMNAS_DETALLE, r["filas"], _totales_detalle(r))
    cd._hoja(wb, "Pagos recibidos", "Pagos recibidos en el periodo (por fecha de pago)", periodo, COLUMNAS_MOVIMIENTOS, r["movimientos"],
             {"monto": cd._f(sum((cd._d(m["monto"]) for m in r["movimientos"]), Decimal(0)))})
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ============================================================
# PDF
# ============================================================

def generar_pdf_rendicion(r, emitido_por=None):
    bs, pdf = rp._fmt_bs, rp._pdf_texto
    buffer = io.BytesIO()
    doc, ancho = cd.documento_pdf(buffer, "Rendición de alquileres")
    est = cd.estilos_pdf()

    def tabla(*args, **kwargs):
        return cd.tabla_pdf(*args, ancho=ancho, est=est, **kwargs)

    t = r["totales"]
    story = cd.cabecera_pdf("Rendición de alquileres: dinero recibido en el periodo", r["desde"], r["hasta"], emitido_por, ancho, est)
    story.append(Paragraph(f"<b>Pagos recibidos:</b> {r['n_pagos']} &nbsp;&nbsp;|&nbsp;&nbsp; "
                           f"<b>Total cobrado:</b> {bs(t['total'])} &nbsp;&nbsp;|&nbsp;&nbsp; "
                           f"<b>Apartamentos:</b> {r['n_apartamentos']} &nbsp;&nbsp;|&nbsp;&nbsp; "
                           f"<b>Con deuda:</b> {r['con_deuda']}", est.chico))
    story.append(Spacer(1, 4))
    if r["filas"]:
        filas = [[f["apartamento"], f["piso"], f["estado"], f["inquilino"], f["celular"], bs(f["alquiler"]), bs(f["luz"]),
                  bs(f["agua"]), bs(f["total"]), bs(f["deuda"]), f["aire"], f["contrato"]] for f in r["filas"]]
        story.append(tabla(["Apartamento", "Piso", "Estado", "Inquilino", "Celular", "Alquiler cobrado", "Luz cobrada",
                            "Agua cobrada", "Total cobrado", "Deuda pendiente", "Aire", "Contrato"], filas,
                           [2.3, 1.2, 1.0, 2.0, 1.2, 1.3, 1.2, 1.2, 1.3, 1.4, 1.2, 1.7], tuple(range(5, 10)),
                           ["TOTAL", "", "", "", "", bs(t["alquiler"]), bs(t["luz"]), bs(t["agua"]), bs(t["total"]),
                            bs(t["deuda"]), "", ""]))
    else:
        story.append(Paragraph("No hay apartamentos para mostrar en este periodo.", est.nota))
    story.append(Paragraph("«Cobrado» es el dinero recibido entre las dos fechas (por fecha de pago), sin importar a qué mes corresponda. "
                           f"«Deuda pendiente» es lo que aún falta pagar de {pdf(texto_meses(r))}, a la fecha de emisión.", est.nota))

    story.append(CondPageBreak(40 * mm))
    story.append(Paragraph("Pagos recibidos en el periodo", est.sec))
    if r["movimientos"]:
        story.append(tabla(["Fecha de pago", "Apartamento", "Inquilino", "Concepto", "Mes que paga", "Método", "Observación", "Monto"],
                           [[m["fecha_txt"], m["apartamento"], m["inquilino"], m["concepto"], m["periodo"], m["metodo"],
                             m["observacion"], bs(m["monto"])] for m in r["movimientos"]],
                           [1.2, 2.2, 2.0, 1.1, 1.5, 1.5, 2.6, 1.3], (7,),
                           ["TOTAL", "", "", "", "", "", "", bs(sum(m["monto"] for m in r["movimientos"]))]))
        story.append(Paragraph("Por concepto: " + " · ".join(f"{c['concepto']} {bs(c['total'])}" for c in r["pagos_por_concepto"]) + ".",
                               est.nota))
    else:
        story.append(Paragraph("No se recibió ningún pago en este periodo.", est.nota))
    story += cd.firmas_pdf(ancho, "Elaborado por", "Revisado por (Administración)")
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
