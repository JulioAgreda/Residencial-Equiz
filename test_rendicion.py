"""Pruebas de rendicion.py  ->  python test_rendicion.py   (necesita recibo.py con su logo y fuentes al lado)"""
import io
from datetime import date
import openpyxl
import rendicion as r

HOY = date(2026, 10, 20)
def apt(i, codigo, nombre, alquiler=0, estado="Ocupado", **extra):
    return {"id": i, "codigo": codigo, "piso": "Planta Baja", "estado": estado, "inquilino_nombre": nombre, "celular": f"7000000{i}",
            "monto_alquiler": alquiler, "dia_pago": 5, "fecha_ingreso": "2026-01-10", "tipo_contrato": "Alquiler",
            "estado_contrato": "Vigente", "aire_acondicionado": False, **extra}
def per(i, apt_id, mes, anio, esperado, pagos=(), campo="pagos"):
    return {"id": i, "apartamento_id": apt_id, "mes": mes, "anio": anio, "monto_esperado": esperado,
            campo: [{"id": k, "monto": m, "fecha": f, "metodo_pago": met, "observacion": obs} for k, (m, f, met, obs) in enumerate(pagos, 1)]}

# Como el boceto: julio no pagó el alquiler; viv no pagó nada; badi pagó todo
apartamentos = [apt(1, "PB - APARTAMENTO 1", "julio", 600), apt(2, "PB - APARTAMENTO 2", "viv", 800),
                apt(3, "PB - APARTAMENTO 3", "badi", 500, aire_acondicionado=True, aire_acondicionado_propiedad="Del edificio"),
                apt(4, "PP - APARTAMENTO 4", None, 0, estado="Desocupado"),
                apt(5, "PP - APARTAMENTO 5", "ana", 900, tipo_contrato="Anticrético")]
alq = [per(1, 1, "Octubre", 2026, 600), per(2, 2, "Octubre", 2026, 800, [(300, "2026-10-06", "Efectivo", "abono")]),
       per(3, 3, "Octubre", 2026, 500, [(500, "2026-10-03", "QR", None)]),
       per(4, 3, "Septiembre", 2026, 500, [(500, "2026-09-04", "Efectivo", None)]),
       per(5, 1, "Septiembre", 2026, 600, [(600, "2026-09-05", "Efectivo", None)]),
       per(6, 2, "Septiembre", 2026, 800, [(800, "2026-09-05", "Transferencia", None)])]
luz = [per(10, 1, "Octubre", 2026, 33, [(33, "2026-10-07", "Efectivo", None)], "pagos_electricidad"),
       per(11, 3, "Octubre", 2026, 67, [(80, "2026-10-08", "Efectivo", "pagó de más")], "pagos_electricidad"),     # pago de más
       per(12, 2, "Octubre", 2026, 45, [], "pagos_electricidad")]
agua = [per(20, 1, "Octubre", 2026, 34, [(10, "2026-10-07", "Efectivo", None)], "pagos_agua"),
        per(21, 3, "Octubre", 2026, 78, [(78, "2026-10-08", "Efectivo", None)], "pagos_agua"),
        per(22, 2, "Octubre", 2026, 56, [], "pagos_agua")]

oct_ = r.construir_rendicion(apartamentos, alq, luz, agua, date(2026, 10, 1), date(2026, 10, 31), HOY)
f = {x["apartamento"]: x for x in oct_["filas"]}
assert oct_["meses"] == [(2026, 10)] and oct_["n_apartamentos"] == 4                      # el desocupado sin movimientos no sale
a, b, c, d = f["PB - APARTAMENTO 1"], f["PB - APARTAMENTO 2"], f["PB - APARTAMENTO 3"], f["PP - APARTAMENTO 5"]
assert (a["alquiler"], a["luz"], a["agua"], a["total"], a["pagado"], a["deuda"]) == (600, 33, 34, 667, 43, 624)    # no pagó alquiler; luz pagada; agua parcial
assert (a["alquiler_pagado"], a["alquiler_deuda"], a["luz_deuda"], a["agua_pagado"], a["agua_deuda"]) == (0, 600, 0, 10, 24)
assert (b["alquiler"], b["pagado"], b["deuda"]) == (800, 300, 800 - 300 + 45 + 56)                                # pago parcial + luz y agua sin pagar
assert (c["total"], c["pagado"], c["deuda"]) == (645, 658, 0)                                                      # pagó todo (de más en la luz): deuda 0, no negativa
assert c["aire"] == "Sí · edificio" and c["contrato"] == "Alquiler · Vigente" and a["aire"] == "No"
assert d["alquiler"] == 0 and d["deuda"] == 0 and d["contrato"] == "Anticrético · Vigente"                         # anticrético: sin alquiler mensual
assert a["inquilino"] == "julio" and a["celular"] == "70000001" and a["piso"] == "Planta Baja" and a["estado"] == "Ocupado"
t = oct_["totales"]
assert t["alquiler"] == 1900 and t["luz"] == 145 and t["agua"] == 168                                              # los totales del boceto
assert t["total"] == 2213 and round(sum(x["deuda"] for x in oct_["filas"]), 2) == t["deuda"] == 624 + 601 + 0
assert oct_["con_deuda"] == 2 and oct_["porcentaje_cobrado"] == round(100 * t["pagado"] / t["total"], 1)

# movimientos: cada pago, ordenados por fecha, con método y observación
m = oct_["movimientos"]
assert len(m) == 6 and [x["fecha"] for x in m] == sorted(x["fecha"] for x in m)
assert {"concepto": "Luz", "monto": 80, "metodo": "Efectivo", "observacion": "pagó de más"}.items() <= [x for x in m if x["observacion"] == "pagó de más"][0].items()
assert sum(x["monto"] for x in m) == 33 + 10 + 300 + 500 + 80 + 78 == t["pagado"] == 1001      # los pagos listados suman lo pagado del resumen
assert [(p["concepto"], p["total"]) for p in oct_["pagos_por_concepto"]] == [("Alquiler", 800), ("Luz", 113), ("Agua", 88)]
assert all(x["periodo"] == "Octubre 2026" for x in m)

# mes sin ningún registro: se cobra con el alquiler de la ficha (como el estado de cuenta)
sin = r.construir_rendicion(apartamentos, [p for p in alq if p["id"] != 1], luz, agua, date(2026, 10, 1), date(2026, 10, 31), HOY)
assert {x["apartamento"]: x for x in sin["filas"]}["PB - APARTAMENTO 1"]["alquiler"] == 600       # sin registro de octubre pero con septiembre -> se completa
assert {x["apartamento"]: x for x in sin["filas"]}["PB - APARTAMENTO 1"]["alquiler_deuda"] == 600
futuro = r.construir_rendicion(apartamentos, alq, luz, agua, date(2026, 12, 1), date(2026, 12, 31), HOY)
assert all(x["alquiler"] == 0 for x in futuro["filas"])                                           # meses futuros no se inventan

# rango: meses que toca (sep. 15 a oct. 5 = septiembre y octubre)
rango = r.construir_rendicion(apartamentos, alq, luz, agua, date(2026, 9, 15), date(2026, 10, 5), HOY)
assert rango["meses"] == [(2026, 9), (2026, 10)] and r.texto_meses(rango) == "Septiembre 2026 a Octubre 2026"
fr = {x["apartamento"]: x for x in rango["filas"]}
assert fr["PB - APARTAMENTO 1"]["alquiler"] == 1200 and fr["PB - APARTAMENTO 1"]["alquiler_pagado"] == 600     # sep. pagado + oct. no
assert fr["PB - APARTAMENTO 3"]["alquiler"] == 1000 and fr["PB - APARTAMENTO 3"]["alquiler_deuda"] == 0
assert r.texto_meses(oct_) == "Octubre 2026" and r.meses_en_rango(date(2025, 11, 30), date(2026, 2, 1)) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]

# solo con deuda / sin datos
sd = r.construir_rendicion(apartamentos, alq, luz, agua, date(2026, 10, 1), date(2026, 10, 31), HOY, solo_con_deuda=True)
assert [x["apartamento"] for x in sd["filas"]] == ["PB - APARTAMENTO 1", "PB - APARTAMENTO 2"]
vacio = r.construir_rendicion([], [], [], [], date(2026, 10, 1), date(2026, 10, 31), HOY)
assert vacio["filas"] == [] and vacio["totales"]["total"] == 0 and vacio["porcentaje_cobrado"] is None and vacio["movimientos"] == []
# periodos con mes ilegible no rompen el reporte
raros = r.construir_rendicion(apartamentos, alq + [{"id": 99, "apartamento_id": 1, "mes": "???", "anio": 2026, "monto_esperado": 5, "pagos": []}], luz, agua,
                              date(2026, 10, 1), date(2026, 10, 31), HOY)
assert raros["totales"] == oct_["totales"]

# ---- Excel ----
wb = openpyxl.load_workbook(io.BytesIO(r.generar_excel_rendicion(oct_, "Vio")))
assert wb.sheetnames == ["Rendición", "Detalle por servicio", "Pagos recibidos"]
ws = wb["Rendición"]
assert [ws.cell(4, i).value for i in range(1, 14)] == [e for _c, e, _t in r.COLUMNAS_RESUMEN]
assert [ws.cell(5, i).value for i in (1, 4, 6, 7, 8, 11)] == ["PB - APARTAMENTO 1", "julio", 600, 33, 34, 624]
assert [ws.cell(9, i).value for i in (1, 6, 7, 8, 9, 10, 11)] == ["TOTAL", 1900, 145, 168, 2213, 1001, 1225]
assert wb["Pagos recibidos"].max_row == 4 + 6 + 1                                               # encabezado + 6 pagos + total
openpyxl.load_workbook(io.BytesIO(r.generar_excel_rendicion(vacio)))
# ---- PDF ----
assert r.generar_pdf_rendicion(oct_, "Vio")[:4] == b"%PDF" and r.generar_pdf_rendicion(vacio)[:4] == b"%PDF"
print("PRUEBAS DE RENDICIÓN OK")
