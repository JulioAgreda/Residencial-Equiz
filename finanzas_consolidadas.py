"""
Consolidación financiera de Residencial Equise.

Une cobros de alquiler/agua/electricidad (rendicion.py) con ventas,
pagos generales y compras (cuadre.py), sin volver a consultar la base.

Regla: cada registro se incorpora desde una sola fuente:
- rendicion["movimientos"]: pagos de alquiler, luz y agua (inquilinos actuales y exinquilinos).
- movimientos_cuadre: ventas, pagos generales y compras.

No incorpora deuda pendiente como ingreso ni montos esperados como dinero recibido.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import unicodedata


def _d(valor):
    try:
        return Decimal(str(valor if valor not in (None, "") else 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def _fecha(valor):
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10]) if valor else None
    except (ValueError, TypeError):
        return None


def _metodo(valor):
    texto = unicodedata.normalize("NFD", str(valor or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn").casefold().strip()
    if not texto or texto in ("—", "-"):
        return "Sin método"
    if "efectivo" in texto:
        return "Efectivo"
    if texto == "qr" or " qr " in f" {texto} ":
        return "QR"
    if "transfer" in texto or "deposito" in texto:
        return "Transferencia"
    if "tarjeta" in texto or "debito" in texto or "credito" in texto:
        return "Tarjeta"
    return "Otro"


def construir_movimientos_consolidados(movimientos_cuadre, movimientos_rendicion):
    """Devuelve un libro único, ordenado por fecha y con origen trazable."""
    salida = []

    for m in movimientos_cuadre or []:
        fecha = _fecha(m.get("fecha"))
        monto = _d(m.get("monto"))
        if not fecha or monto <= 0:
            continue
        origen = m.get("origen") or "Otro"
        tipo = m.get("tipo")
        if tipo not in ("Ingreso", "Egreso"):
            continue
        salida.append({
            "fecha": fecha, "tipo": tipo, "origen": origen,
            "concepto": m.get("categoria") or origen,
            "detalle": m.get("detalle") or "",
            "persona": m.get("persona") or "",
            "apartamento": "", "inquilino": "",
            "metodo": _metodo(m.get("metodo_original") or m.get("metodo")),
            "comprobante": m.get("comprobante") or "",
            "estado": m.get("estado") or "",
            "devolucion_a": m.get("devolucion_a") or "",
            "monto": monto,
            "fuente": "cuadre",
            "id_origen": m.get("id"),
        })

    mapa_concepto = {"Alquiler": "Alquiler", "Luz": "Electricidad", "Agua": "Agua"}
    for m in movimientos_rendicion or []:
        fecha = _fecha(m.get("fecha"))
        monto = _d(m.get("monto"))
        if not fecha or monto <= 0:
            continue
        concepto = m.get("concepto") or "Cobro de inquilino"
        salida.append({
            "fecha": fecha, "tipo": "Ingreso", "origen": "Cobro de inquilino",
            "concepto": mapa_concepto.get(concepto, concepto),
            "detalle": m.get("observacion") or "",
            "persona": m.get("inquilino") or "",
            "apartamento": m.get("apartamento") or "",
            "inquilino": m.get("inquilino") or "",
            "metodo": _metodo(m.get("metodo")),
            "comprobante": "",
            "estado": "",
            "devolucion_a": "",
            "monto": monto,
            "fuente": "rendicion",
            "id_origen": None,
        })

    salida.sort(key=lambda x: (x["fecha"], x["tipo"], x["origen"], str(x.get("apartamento") or "")))
    return salida


def construir_resumen(movimientos, desde=None, hasta=None, saldo_inicial=0):
    """Resumen por fecha, tipo, origen y método. Saldo = inicial + ingresos - egresos."""
    desde, hasta = _fecha(desde), _fecha(hasta)
    movs = [
        m for m in (movimientos or [])
        if (desde is None or m["fecha"] >= desde)
        and (hasta is None or m["fecha"] <= hasta)
    ]
    ingresos = sum((_d(m["monto"]) for m in movs if m["tipo"] == "Ingreso"), Decimal("0"))
    egresos = sum((_d(m["monto"]) for m in movs if m["tipo"] == "Egreso"), Decimal("0"))
    inicial = _d(saldo_inicial)

    por_origen = {}
    por_metodo = {}
    por_dia = {}
    for m in movs:
        origen = m["origen"]
        metodo = m["metodo"]
        po = por_origen.setdefault(origen, {"origen": origen, "ingresos": Decimal(0), "egresos": Decimal(0), "cantidad": 0})
        po["ingresos" if m["tipo"] == "Ingreso" else "egresos"] += _d(m["monto"])
        po["cantidad"] += 1
        pm = por_metodo.setdefault(metodo, {"metodo": metodo, "ingresos": Decimal(0), "egresos": Decimal(0), "cantidad": 0})
        pm["ingresos" if m["tipo"] == "Ingreso" else "egresos"] += _d(m["monto"])
        pm["cantidad"] += 1
        pd = por_dia.setdefault(m["fecha"], {"fecha": m["fecha"], "ingresos": Decimal(0), "egresos": Decimal(0)})
        pd["ingresos" if m["tipo"] == "Ingreso" else "egresos"] += _d(m["monto"])

    def serializar(filas, clave):
        resultado = []
        for f in filas:
            fila = dict(f)
            for k in ("ingresos", "egresos"):
                if k in fila:
                    fila[k] = float(fila[k].quantize(Decimal("0.01")))
            if clave == "dia":
                fila["neto"] = round(fila["ingresos"] - fila["egresos"], 2)
            else:
                fila["neto"] = round(fila.get("ingresos", 0) - fila.get("egresos", 0), 2)
            resultado.append(fila)
        return resultado

    # No se registra hora para todos los movimientos. Por ello no se debe
    # presentar un saldo secuencial ficticio entre operaciones del mismo día.
    # Se calcula el saldo acumulado al cierre de cada fecha y se repite en las
    # filas de esa fecha para dejar clara la limitación temporal del origen.
    libro = []
    saldo = inicial
    por_fecha = {}
    for m in movs:
        por_fecha.setdefault(m["fecha"], []).append(m)
    for fecha in sorted(por_fecha):
        movimientos_dia = por_fecha[fecha]
        neto_dia = sum(
            (_d(m["monto"]) if m["tipo"] == "Ingreso" else -_d(m["monto"])
             for m in movimientos_dia),
            Decimal("0")
        )
        saldo += neto_dia
        saldo_cierre = float(saldo.quantize(Decimal("0.01")))
        for m in movimientos_dia:
            monto = _d(m["monto"])
            libro.append({
                **m, "monto": float(monto),
                "saldo_acumulado": saldo_cierre
            })

    return {
        "desde": desde, "hasta": hasta, "cantidad_movimientos": len(movs),
        "ingresos": float(ingresos), "egresos": float(egresos),
        "resultado_periodo": float((ingresos-egresos).quantize(Decimal("0.01"))),
        "saldo_inicial": float(inicial),
        "saldo_final_teorico": float((inicial+ingresos-egresos).quantize(Decimal("0.01"))),
        "por_origen": serializar(sorted(por_origen.values(), key=lambda x:x["origen"]), "origen"),
        "por_metodo": serializar(sorted(por_metodo.values(), key=lambda x:x["metodo"]), "metodo"),
        "por_dia": serializar([por_dia[k] for k in sorted(por_dia)], "dia"),
        "libro": libro,
        "advertencia": "Saldo teórico de los movimientos incluidos; no equivale al saldo bancario conciliado ni al efectivo físico contado."
    }


def puede_ver_rendicion_financiera(usuario):
    """El reporte consolidado contiene información global; solo lo ve Administrador."""
    return isinstance(usuario, dict) and str(usuario.get("rol", "")).strip().casefold() == "administrador"


def exportar_excel(resumen):
    """Genera un libro XLSX con detalle y resúmenes de la rendición consolidada."""
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)
    hojas = [
        ("Libro", ["Fecha", "Tipo", "Origen", "Concepto", "Detalle", "Persona / Inquilino",
                   "Apartamento", "Método", "Estado", "Devuelto a", "Monto (Bs)", "Saldo al cierre del día (Bs)"],
         [[m["fecha"], m["tipo"], m["origen"], m["concepto"], m["detalle"], m["persona"],
           m["apartamento"], m["metodo"], m.get("estado", ""), m.get("devolucion_a", ""),
           float(m["monto"]), float(m["saldo_acumulado"])]
          for m in resumen.get("libro", [])]),
        ("Por origen", ["Origen", "Movimientos", "Ingresos (Bs)", "Egresos (Bs)", "Neto (Bs)"],
         [[x["origen"], x["cantidad"], float(x["ingresos"]), float(x["egresos"]), float(x["neto"])]
          for x in resumen.get("por_origen", [])]),
        ("Por metodo", ["Método", "Movimientos", "Ingresos (Bs)", "Egresos (Bs)", "Neto (Bs)"],
         [[x["metodo"], x["cantidad"], float(x["ingresos"]), float(x["egresos"]), float(x["neto"])]
          for x in resumen.get("por_metodo", [])]),
        ("Por dia", ["Fecha", "Ingresos (Bs)", "Egresos (Bs)", "Neto (Bs)"],
         [[x["fecha"], float(x["ingresos"]), float(x["egresos"]), float(x["neto"])]
          for x in resumen.get("por_dia", [])]),
    ]
    for nombre, encabezados, filas in hojas:
        ws = wb.create_sheet(nombre)
        ws.append(encabezados)
        for fila in filas:
            ws.append(fila)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for celda in ws[1]:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor="244062")
        for columna in ws.columns:
            ancho = min(max(max(len(str(c.value or "")) for c in columna) + 2, 12), 42)
            ws.column_dimensions[get_column_letter(columna[0].column)].width = ancho
        for fila in ws.iter_rows(min_row=2):
            for celda in fila:
                if celda.is_date:
                    celda.number_format = "dd/mm/yyyy"
                elif isinstance(celda.value, (int, float)) and ("Bs)" in encabezados[celda.column-1]):
                    celda.number_format = '"Bs" #,##0.00'
    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()
