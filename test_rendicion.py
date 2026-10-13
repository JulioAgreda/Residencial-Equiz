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

D = date
oct_ = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY)
f = {x["apartamento"]: x for x in oct_["filas"]}
assert oct_["meses"] == [(2026, 10)] and oct_["n_apartamentos"] == 4                      # el desocupado sin movimientos no sale
a, b, c, d = f["PB - APARTAMENTO 1"], f["PB - APARTAMENTO 2"], f["PB - APARTAMENTO 3"], f["PP - APARTAMENTO 5"]

# --- lo COBRADO es lo recibido entre las fechas (por fecha de pago), por servicio ---
assert (a["alquiler"], a["luz"], a["agua"], a["total"]) == (0, 33, 10, 43)                  # julio no pagó alquiler en octubre; pagó luz y parte del agua
assert (b["alquiler"], b["luz"], b["agua"], b["total"]) == (300, 0, 0, 300)
assert (c["alquiler"], c["luz"], c["agua"], c["total"]) == (500, 80, 78, 658)               # incluye lo pagado de más en la luz
assert d["total"] == 0 and d["alquiler"] == 0 and d["contrato"] == "Anticrético · Vigente"
t = oct_["totales"]
assert (t["alquiler"], t["luz"], t["agua"], t["total"]) == (800, 113, 88, 1001)
assert a["aire"] == "No" and c["aire"] == "Sí · edificio" and c["contrato"] == "Alquiler · Vigente"
assert a["inquilino"] == "julio" and a["celular"] == "70000001" and a["piso"] == "Planta Baja" and a["estado"] == "Ocupado"

# --- la DEUDA pendiente es de los meses del periodo y no depende de cuándo se pagó ---
assert (a["deuda"], b["deuda"], c["deuda"]) == (624, 601, 0) and t["deuda"] == 1225 == round(sum(x["deuda"] for x in oct_["filas"]), 2)
assert (a["alquiler_acobrar"], a["alquiler_pagado"], a["alquiler_deuda"], a["agua_acobrar"], a["agua_pagado"], a["agua_deuda"]) == (600, 0, 600, 34, 10, 24)
assert oct_["con_deuda"] == 2

# --- movimientos: solo los pagos de esas fechas; suman lo mismo que el resumen ---
m = oct_["movimientos"]
assert len(m) == oct_["n_pagos"] == 6 and [x["fecha"] for x in m] == sorted(x["fecha"] for x in m)
assert sum(x["monto"] for x in m) == 33 + 10 + 300 + 500 + 80 + 78 == t["total"] == 1001
assert {"concepto": "Luz", "monto": 80, "metodo": "Efectivo", "observacion": "pagó de más"}.items() <= [x for x in m if x["observacion"] == "pagó de más"][0].items()
assert [(p["concepto"], p["total"]) for p in oct_["pagos_por_concepto"]] == [("Alquiler", 800), ("Luz", 113), ("Agua", 88)]
assert all(x["fecha"].month == 10 for x in m)                                                # nada de septiembre aunque sea un pago del mismo inquilino
assert all(x["periodo"] == "Octubre 2026" for x in m)

# --- el caso de la captura: un pago hecho en julio por el alquiler de octubre NO es de octubre ---
adelantos = alq + [per(30, 5, "Octubre", 2026, 900, [(1200, "2026-07-27", "Efectivo", None)]),      # apt. 5 (anticrético en los datos de prueba)
                   per(31, 2, "Noviembre", 2026, 800, [(800, "2026-10-12", "QR", "adelanto")])]    # pago de octubre por el alquiler de NOVIEMBRE
ad_oct = r.construir_rendicion(apartamentos, adelantos, luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY)
assert all(x["fecha"] != D(2026, 7, 27) for x in ad_oct["movimientos"])                            # el de julio no aparece en octubre
nov = [x for x in ad_oct["movimientos"] if x["observacion"] == "adelanto"][0]
assert nov["periodo"] == "Noviembre 2026" and nov["fecha"] == D(2026, 10, 12)                      # sí entra en octubre: el dinero ingresó en octubre
assert {x["apartamento"]: x for x in ad_oct["filas"]}["PB - APARTAMENTO 2"]["alquiler"] == 1100   # 300 + 800
jul = r.construir_rendicion(apartamentos, adelantos, luz, agua, D(2026, 7, 1), D(2026, 7, 31), HOY)
assert [(x["fecha"], x["periodo"], x["monto"]) for x in jul["movimientos"]] == [(D(2026, 7, 27), "Octubre 2026", 1200)]   # aparece en julio
assert jul["totales"]["total"] == 1200 and {x["apartamento"]: x for x in jul["filas"]}["PP - APARTAMENTO 5"]["alquiler"] == 1200
sep = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 9, 1), D(2026, 9, 30), HOY)
assert sep["totales"]["alquiler"] == 600 + 800 + 500 and sep["n_pagos"] == 3 and sep["totales"]["deuda"] == 0   # septiembre: lo que ingresó en septiembre

# --- fechas exactas: los extremos están incluidos ---
assert r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 6), D(2026, 10, 6), HOY)["totales"]["total"] == 300
assert r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 7), D(2026, 10, 7), HOY)["totales"]["total"] == 43
assert r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 5), D(2026, 10, 7), HOY)["totales"]["total"] == 343
assert r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 9), D(2026, 10, 31), HOY)["totales"]["total"] == 0     # sin pagos esos días
rango = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 9, 15), D(2026, 10, 5), HOY)
assert rango["n_pagos"] == 1 and rango["totales"]["total"] == 500 and rango["meses"] == [(2026, 9), (2026, 10)]    # solo el pago del 3/10
assert r.texto_meses(rango) == "Septiembre 2026 a Octubre 2026" and r.texto_meses(oct_) == "Octubre 2026"
assert r.meses_en_rango(D(2025, 11, 30), D(2026, 2, 1)) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]
sin_pagos = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 9), D(2026, 10, 31), HOY)
assert sin_pagos["movimientos"] == [] and sin_pagos["totales"]["deuda"] == 1225                     # sin pagos, pero la deuda sigue ahí

# --- deuda: mes sin registro se cobra con la ficha; meses futuros no se inventan ---
sinreg = r.construir_rendicion(apartamentos, [p for p in alq if p["id"] != 1], luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY)
assert {x["apartamento"]: x for x in sinreg["filas"]}["PB - APARTAMENTO 1"]["alquiler_deuda"] == 600
futuro = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 12, 1), D(2026, 12, 31), HOY)
assert all(x["alquiler_acobrar"] == 0 for x in futuro["filas"]) and futuro["totales"]["total"] == 0

# --- filtros de apartamentos ---
sd = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY, solo_con_deuda=True)
assert [x["apartamento"] for x in sd["filas"]] == ["PB - APARTAMENTO 1", "PB - APARTAMENTO 2"]
sc = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY, solo_con_cobros=True)
assert [x["apartamento"] for x in sc["filas"]] == ["PB - APARTAMENTO 1", "PB - APARTAMENTO 2", "PB - APARTAMENTO 3"] and sc["totales"]["total"] == 1001
vacio = r.construir_rendicion([], [], [], [], D(2026, 10, 1), D(2026, 10, 31), HOY)
assert vacio["filas"] == [] and vacio["totales"]["total"] == 0 and vacio["movimientos"] == [] and vacio["n_pagos"] == 0

# --- periodo con mes ilegible: su dinero SÍ cuenta como cobrado (mes «—»); su deuda no entra ---
raro = {"id": 99, "apartamento_id": 1, "mes": "???", "anio": 2026, "monto_esperado": 5,
        "pagos": [{"id": 1, "monto": 7, "fecha": "2026-10-10", "metodo_pago": "Efectivo", "observacion": None}]}
raros = r.construir_rendicion(apartamentos, alq + [raro], luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY)
assert raros["totales"]["total"] == 1008 and raros["totales"]["deuda"] == oct_["totales"]["deuda"]
assert [x["periodo"] for x in raros["movimientos"] if x["monto"] == 7] == ["—"]

# ================= EX INQUILINOS: si pagan después, ese cobro suma y se ve que es de un ex inquilino =================
def cer(i, hid, mes, anio, esperado, pagos=(), campo="pagos"):
    return {"id": i, "apartamento_id": 1 if hid == 1 else 2, "inquilino_historial_id": hid, "mes": mes, "anio": anio, "monto_esperado": esperado,
            campo: [{"id": k, "monto": m, "fecha": fe, "metodo_pago": me, "observacion": ob} for k, (m, fe, me, ob) in enumerate(pagos, 1)]}
cerrados = {"alquiler": [cer(1, 1, "Julio", 2026, 600), cer(2, 1, "Agosto", 2026, 600, [(200, "2026-10-04", "Efectivo", "pago de ex inquilino")]),
                         cer(3, 2, "Septiembre", 2026, 800, [(800, "2026-09-20", "QR", None)])],
            "electricidad": [cer(4, 1, "Agosto", 2026, 40, [], "pagos_electricidad")],
            "agua": [cer(5, 1, "Agosto", 2026, 30, [(30, "2026-10-05", "QR", None)], "pagos_agua")]}
historial = [{"id": 1, "apartamento_id": 1, "inquilino_nombre": "carlos", "celular": "7111", "fecha_salida": "2026-08-31"},
             {"id": 2, "apartamento_id": 2, "inquilino_nombre": "lucia", "celular": "7222", "fecha_salida": "2026-09-30"},
             {"id": 3, "apartamento_id": 3, "inquilino_nombre": "sin periodos", "fecha_salida": "2026-05-31"}]
con = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY, cerrados=cerrados, historial=historial)
exf = [x for x in con["filas"] if x.get("ex_inquilino")]
assert len(exf) == 1 and con["n_ex_inquilinos"] == 1 and con["n_apartamentos"] == 4                       # lucía no aporta (sin pagos en octubre y sin deuda); el 3.º no tiene periodos
e1 = exf[0]
assert e1["estado"] == "Ex inquilino" and e1["inquilino"] == "carlos (ex inquilino)" and e1["apartamento"] == "PB - APARTAMENTO 1"
assert e1["celular"] == "7111" and e1["contrato"] == "Salió 31/08/2026" and e1["aire"] == "—"
assert (e1["alquiler"], e1["luz"], e1["agua"], e1["total"]) == (200, 0, 30, 230)                           # lo que pagó en octubre
assert e1["deuda"] == 1040 == 1000 + 40 + 0                                                                # TODO lo que aún debe, no solo de octubre
assert (e1["alquiler_acobrar"], e1["alquiler_pagado"], e1["alquiler_deuda"], e1["luz_deuda"], e1["agua_deuda"]) == (1200, 200, 1000, 40, 0)
assert con["filas"][-1] is e1 and [x["apartamento"] for x in con["filas"][:4]] == [x["apartamento"] for x in oct_["filas"]]   # los ex inquilinos van al final
tc = con["totales"]
assert (tc["alquiler"], tc["luz"], tc["agua"], tc["total"], tc["deuda"]) == (1000, 113, 118, 1231, 2265)    # 1001 + 230 ; 1225 + 1040
assert con["cobrado_ex"] == 230 and con["deuda_ex"] == 1040 and con["con_deuda"] == 3
mx = [m for m in con["movimientos"] if "ex inquilino" in m["inquilino"]]
assert len(con["movimientos"]) == 8 and con["n_pagos"] == 8 and len(mx) == 2
assert {(m["concepto"], m["periodo"], m["monto"]) for m in mx} == {("Alquiler", "Agosto 2026", 200), ("Agua", "Agosto 2026", 30)}
assert sum(m["monto"] for m in con["movimientos"]) == tc["total"] == 1231                                   # los pagos listados suman el total del resumen
assert [(p["concepto"], p["total"]) for p in con["pagos_por_concepto"]] == [("Alquiler", 1000), ("Luz", 113), ("Agua", 118)]
# la rendición SIN ex inquilinos no cambia (y los datos de ex inquilinos son opcionales)
assert r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY, cerrados=cerrados)["n_ex_inquilinos"] == 0
assert r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY)["totales"] == oct_["totales"]
# lo que pagó un ex inquilino en OTRO periodo no aparece en este (cada pago, en su fecha)
sep2 = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 9, 1), D(2026, 9, 30), HOY, cerrados=cerrados, historial=historial)
lucia = [x for x in sep2["filas"] if x.get("ex_inquilino") and "lucia" in x["inquilino"]][0]
assert (lucia["alquiler"], lucia["total"], lucia["deuda"]) == (800, 800, 0) and sep2["cobrado_ex"] == 800 + 0   # en septiembre solo pagó lucía; carlos debe pero no pagó
carlos_sep = [x for x in sep2["filas"] if x.get("ex_inquilino") and "carlos" in x["inquilino"]][0]
assert carlos_sep["total"] == 0 and carlos_sep["deuda"] == 1040                                              # aparece por su deuda pendiente
# filtros
assert [x["inquilino"] for x in r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 11, 1), D(2026, 11, 30), HOY, cerrados=cerrados, historial=historial)["filas"] if x.get("ex_inquilino")] == ["carlos (ex inquilino)"]   # sin pagos, pero su deuda sigue
noviembre_cobros = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 11, 1), D(2026, 11, 30), HOY, solo_con_cobros=True, cerrados=cerrados, historial=historial)
assert noviembre_cobros["n_ex_inquilinos"] == 0 and noviembre_cobros["filas"] == []
solo_deuda = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY, solo_con_deuda=True, cerrados=cerrados, historial=historial)
assert [x["inquilino"] for x in solo_deuda["filas"]][-1] == "carlos (ex inquilino)" and solo_deuda["n_ex_inquilinos"] == 1
solo_cobros = r.construir_rendicion(apartamentos, alq, luz, agua, D(2026, 10, 1), D(2026, 10, 31), HOY, solo_con_cobros=True, cerrados=cerrados, historial=historial)
assert solo_cobros["n_ex_inquilinos"] == 1 and solo_cobros["totales"]["total"] == 1231
# un ex inquilino cuyo apartamento ya no está en la lista (p. ej. acceso restringido) no rompe el reporte
sin_apt = r.construir_rendicion([], [], [], [], D(2026, 10, 1), D(2026, 10, 31), HOY, cerrados=cerrados, historial=historial)
assert sin_apt["n_apartamentos"] == 0 and [x["apartamento"] for x in sin_apt["filas"]] == ["—", ] * len(sin_apt["filas"])
# Excel y PDF con ex inquilinos
wbx = openpyxl.load_workbook(io.BytesIO(r.generar_excel_rendicion(con, "Vio")))
wsx = wbx["Rendición"]
assert [wsx.cell(9, i).value for i in (1, 3, 4, 6, 8, 9, 10, 12)] == ["PB - APARTAMENTO 1", "Ex inquilino", "carlos (ex inquilino)", 200, 30, 230, 1040, "Salió 31/08/2026"]
assert [wsx.cell(10, i).value for i in (1, 6, 7, 8, 9, 10)] == ["TOTAL", 1000, 113, 118, 1231, 2265]
assert wbx["Pagos recibidos"].max_row == 4 + 8 + 1
assert r.generar_pdf_rendicion(con, "Vio")[:4] == b"%PDF"

# ---- Excel ----
wb = openpyxl.load_workbook(io.BytesIO(r.generar_excel_rendicion(oct_, "Vio")))
assert wb.sheetnames == ["Rendición", "Deuda por servicio", "Pagos recibidos"]
ws = wb["Rendición"]
assert [ws.cell(4, i).value for i in range(1, 13)] == [e for _c, e, _t in r.COLUMNAS_RESUMEN]
assert [ws.cell(5, i).value for i in (1, 4, 6, 7, 8, 9, 10)] == ["PB - APARTAMENTO 1", "julio", 0, 33, 10, 43, 624]
assert [ws.cell(9, i).value for i in (1, 6, 7, 8, 9, 10)] == ["TOTAL", 800, 113, 88, 1001, 1225]
assert wb["Pagos recibidos"].max_row == 4 + 6 + 1                                              # encabezado + 6 pagos + total
assert wb["Pagos recibidos"].cell(11, 8).value == 1001
openpyxl.load_workbook(io.BytesIO(r.generar_excel_rendicion(vacio)))
# ---- PDF ----
assert r.generar_pdf_rendicion(oct_, "Vio")[:4] == b"%PDF" and r.generar_pdf_rendicion(vacio)[:4] == b"%PDF"
assert r.generar_pdf_rendicion(sin_pagos)[:4] == b"%PDF"
print("PRUEBAS DE RENDICIÓN OK")
