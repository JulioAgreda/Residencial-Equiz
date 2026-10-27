"""Pruebas de conciliacion.py  ->  python test_conciliacion.py   (necesita test_extracto.py, extracto.py, cuadre.py y recibo.py al lado)"""
import io
from datetime import date
import conciliacion as c
import extracto as x
import test_extracto as te

D = date
L = x.leer_extracto(te.libro_xlsx(), "e.xlsx")["lineas"]          # el extracto (anonimizado) de 27 movimientos
def sis(origen, tipo, dia, monto, apto="", persona="", detalle="", metodo="QR", categoria="", periodo=""):
    return {"origen": origen, "tipo": tipo, "fecha": D(2026, 10, dia), "monto": monto, "apartamento": apto, "persona": persona, "detalle": detalle or origen,
            "categoria": categoria, "metodo": metodo, "metodo_original": metodo, "periodo": periodo}
I, E = c.INGRESO, c.EGRESO
def sistema_base():
    return [
        sis("Alquiler", I, 5, 1100, "PP - APARTAMENTO 3", "Inquilino A", "Alquiler Octubre 2026"),                                  # A  <- banco 2
        sis("Luz", I, 5, 77, "PP - APARTAMENTO 3", "Inquilino A", "Luz Octubre 2026"),                                              # B  <- banco 3
        sis("Alquiler", I, 7, 1600, "PB - APARTAMENTO 4", "Inquilino B", "Alquiler Octubre 2026"),                                  # C  <- banco 7
        sis("Alquiler", I, 7, 1700, "PB - APARTAMENTO 4", "Inquilino C", "Alquiler Octubre 2026"),                                  # D \ banco 9 (1976 pagado de una vez)
        sis("Luz", I, 7, 276, "PB - APARTAMENTO 4", "Inquilino C", "Luz Octubre 2026"),                                             # E /
        sis("Alquiler", I, 8, 1100, "SP - APARTAMENTO 5", "Inquilino D", "Alquiler Octubre 2026", "Transferencia"),                 # F  <- banco 10
        sis("Luz", I, 9, 29, "SP - APARTAMENTO 5", "Inquilino D", "Luz Octubre 2026"),                                              # G  <- banco 11 (1 día después)
        sis("Alquiler", I, 14, 1400, "SP - APARTAMENTO 3", "Inquilino F", "Alquiler Octubre 2026"),                                 # H \ banco 20 (1506)
        sis("Luz", I, 14, 106, "SP - APARTAMENTO 3", "Inquilino F", "Luz Octubre 2026"),                                            # I /
        sis("Alquiler", I, 14, 1100, "TP - APARTAMENTO 5", "Inquilino G", "Alquiler Junio 2026", periodo="Junio 2026"),                                   # J \ banco 22 (2200: dos meses)
        sis("Alquiler", I, 14, 1100, "TP - APARTAMENTO 5", "Inquilino G", "Alquiler Julio 2026", periodo="Julio 2026"),                                   # K /
        sis("Luz", I, 14, 270, "PB - APARTAMENTO 4", "Inquilino B", "Luz Octubre 2026"),                                            # L  monto distinto del banco 23 (278)
        sis("Alquiler", I, 6, 1500, "PP - APARTAMENTO 1", "x", metodo="Efectivo"), sis("Alquiler", I, 6, 1800, "PP - APARTAMENTO 2", "y", metodo="Efectivo"),
        sis("Luz", I, 6, 139, "PP - APARTAMENTO 1", "x", metodo="Efectivo"), sis("Alquiler", I, 6, 2500, "PB - APARTAMENTO 3", "z", metodo="Efectivo"),   # 5939 en efectivo
        sis("Venta", I, 6, 1543, persona="Comprador", detalle="Venta de materiales", metodo="Efectivo", categoria="Otros"),                      # = banco 5, en efectivo
        sis("Alquiler", I, 10, 1300, "PP - APARTAMENTO 4", "Inquilino H", "Alquiler Octubre 2026"),                                  # W  registrado como QR pero NO está en el banco
        sis("Compra", E, 7, 150, persona="Ferreteria", detalle="Sellador de pintura", categoria="Pintura"),                          # X1 <- banco 8
        sis("Compra", E, 9, 110, persona="Tienda", detalle="Esponja y palo", categoria="Limpieza"),                                  # X2 <- banco 12
        sis("Pago", E, 9, 3500, persona="Oficina", detalle="Pago de tramite", categoria="Servicios"),                                # X3 <- banco 13
        sis("Compra", E, 7, 5200, persona="Proveedor persianas", detalle="Persianas", metodo="Transferencia", categoria="Mantenimiento"),   # X4 <- banco 6 + 21
        sis("Compra", E, 15, 450, persona="Ferreteria", detalle="Pintura e interruptor", categoria="Pintura"),                        # X5 <- banco 24
        sis("Compra", E, 10, 20, persona="Electricista", detalle="Foco"),                                                            # X6 <- banco 15
        sis("Compra", E, 15, 100, persona="Tienda", detalle="Varios", metodo="Efectivo"),                                            # X7 = banco 26, en efectivo
        sis("Compra", E, 12, 800, persona="Ferreteria", detalle="Materiales", categoria="Mantenimiento"),                            # X8 registrado como QR pero NO está en el banco
    ]
def por_banco(r):
    """{n del movimiento del banco: par}"""
    return {b["n"]: p for p in r["pares"] for b in p["banco"]}
def sin_registro(r): return {x_["linea"]["n"]: x_ for x_ in r["banco_sin_registro"]}
def sin_banco(r): return [(x_["mov"]["origen"], x_["mov"]["monto"]) for x_ in r["sistema_sin_banco"]]

r = c.conciliar(L, sistema_base())
pb = por_banco(r)
# ---------- coincidencias 1 a 1 ----------
for n, monto in ((2, 1100), (3, 77), (7, 1600), (10, 1100), (8, -150), (12, -110), (13, -3500), (24, -450), (15, -20)):
    assert n in pb and pb[n]["union"] == c.UNO_A_UNO and len(pb[n]["sistema"]) == 1, n
assert pb[2]["confianza"] == c.ALTA and any("mismo apartamento (PP-03)" in z for z in pb[2]["razones"]) and pb[2]["dias"] == 0
assert pb[3]["confianza"] == c.ALTA and any("concepto (luz)" in z for z in pb[3]["razones"])
assert pb[11]["union"] == c.UNO_A_UNO and pb[11]["dias"] == 1 and pb[11]["sistema"][0]["origen"] == "Luz"              # la fecha del registro es 1 día después: se acepta
assert pb[8]["confianza"] == c.ALTA and any("coincide" in z for z in pb[8]["razones"])
# ---------- un movimiento del banco = varios registros ----------
assert pb[9]["union"] == c.BANCO_VARIOS and sorted(s["monto"] for s in pb[9]["sistema"]) == [276, 1700] and pb[9]["confianza"] == c.ALTA
assert any("PB-04" in z for z in pb[9]["razones"])                                                                  # «Alquiler y Energia Pb-04»: 1700 + 276 = 1976
assert pb[20]["union"] == c.BANCO_VARIOS and sorted(s["monto"] for s in pb[20]["sistema"]) == [106, 1400] and pb[20]["confianza"] == c.ALTA and pb[20]["dias"] == 1
assert pb[22]["union"] == c.BANCO_VARIOS and [s["monto"] for s in pb[22]["sistema"]] == [1100, 1100] and {s["periodo"] for s in pb[22]["sistema"]} == {"Junio 2026", "Julio 2026"}   # «2 meses»
# ---------- varios movimientos del banco = un registro ----------
assert pb[6]["union"] == c.VARIOS_BANCO and pb[6] is pb[21] and [b["monto"] for b in pb[6]["banco"]] == [-2000, -3200] and pb[6]["sistema"][0]["monto"] == 5200
assert pb[6]["confianza"] == c.ALTA and any("misma persona o empresa" in z for z in pb[6]["razones"]) and pb[6]["dias"] == 6      # las dos partes tienen la misma contraparte
assert len(r["pares"]) == 14 and r["resumen"]["conciliado"] == {"n": 15, "creditos": round(1100 + 77 + 1600 + 1100 + 29 + 1976 + 1506 + 2200, 2), "debitos": round(150 + 110 + 3500 + 20 + 450 + 2000 + 3200, 2), "n_pares": 14}
# ---------- lo que está en el banco y NO en el sistema ----------
sr = sin_registro(r)
assert sorted(sr) == [1, 4, 5, 14, 16, 17, 18, 19, 23, 25, 26, 27]
assert any("Probablemente falta registrarlo" in z and "PP-05" in z and "alquiler" in z for z in sr[17]["causas"])             # «Alquiler PP-05 (...)»: no hay pago de ese apartamento
assert sr[17]["sugerencia"] == "Registrar alquiler del PP-05 por Bs 1,200.00"
assert sr[14]["causas"] == ["No hay ningún registro en el sistema con ese monto: probablemente no se registró."] and sr[14]["sugerencia"] == "Registrar el ingreso (alquiler, luz, agua o venta)"
assert sr[16]["sugerencia"] == "Registrar el egreso (compra o pago)" and sr[1]["linea"]["monto"] == -0.12
assert any("diferencia de Bs 8.00" in z and "revisa el monto" in z for z in sr[23]["causas"])                              # 278 en el banco, 270 en el sistema
assert any("pagado en efectivo" in z and "Comparar también" in z for z in sr[5]["causas"])                                 # 1543 existe, pero como venta en efectivo
assert any("5939" not in z and "suman exactamente" in z and "depósito de efectivo" in z for z in sr[4]["causas"])           # 1500 + 1800 + 139 + 2500 en efectivo = 5939
assert any("pagado en efectivo" in z for z in sr[26]["causas"])
assert any("ya se usó para conciliar otro movimiento del banco" in z and "Bs 1,506.00 del 13/10/2026" in z and "Alquiler PB" not in z for z in sr[19]["causas"]) \
    and any("SP - APARTAMENTO 3" in z for z in sr[19]["causas"])                                                          # el 1400 sin anotación: ese registro ya se usó en el pago de 1506
# ---------- lo que está en el sistema y NO en el banco ----------
assert sorted(sin_banco(r)) == [("Alquiler", 1300), ("Compra", 800), ("Luz", 270)]
causas = {(x_["mov"]["origen"], x_["mov"]["monto"]): x_["causas"] for x_ in r["sistema_sin_banco"]}
assert any("Se registró como QR pero no aparece en el extracto" in z for z in causas[("Alquiler", 1300)])
assert any("diferencia de Bs 8.00" in z for z in causas[("Luz", 270)])
assert r["resumen"]["efectivo_no_comparado"] == {"n": 6, "ingresos": 5939 + 1543, "egresos": 100} and len(r["efectivo"]) == 6
# ---------- identidades: nada se pierde ----------
rs = r["resumen"]
assert rs["banco"]["n"] == 27 == rs["conciliado"]["n"] + rs["sin_registro"]["n"] + rs["excluidos"]["n"]
assert round(rs["banco"]["creditos"], 2) == round(rs["conciliado"]["creditos"] + rs["sin_registro"]["creditos"] + rs["excluidos"]["creditos"], 2) == 23510.53
assert round(rs["banco"]["debitos"], 2) == round(rs["conciliado"]["debitos"] + rs["sin_registro"]["debitos"] + rs["excluidos"]["debitos"], 2) == 23461.32
assert len(sistema_base()) == 26 and rs["sistema"]["n"] == 26 - 6 and rs["sistema_sin_banco"] == {"n": 3, "ingresos": 1570.0, "egresos": 800.0}            # los 6 en efectivo no se comparan
assert round(sum(m for p in r["pares"] for m in [sum(b["cents"] for b in p["banco"])]), 2) == round(sum(sum(s["cents"] for s in p["sistema"]) for p in r["pares"]), 2)   # cada par suma lo mismo de los dos lados
assert rs["por_confianza"] == {"Alta": 14, "Media": 0, "Revisar": 0}
# ---------- incluir el efectivo: se concilia el depósito ----------
re_ = c.conciliar(L, sistema_base(), incluir_efectivo=True)
pe = por_banco(re_)
assert pe[4]["union"] == c.BANCO_VARIOS and sorted(s["monto"] for s in pe[4]["sistema"]) == [139, 1500, 1800, 2500] and pe[4]["confianza"] == c.MEDIA   # el depósito de efectivo
assert pe[5]["union"] == c.UNO_A_UNO and pe[5]["sistema"][0]["origen"] == "Venta" and pe[26]["sistema"][0]["monto"] == 100
assert sorted(sin_registro(re_)) == [1, 14, 16, 17, 18, 19, 23, 25, 27] and re_["efectivo"] == [] and re_["resumen"]["sistema"]["n"] == 26
assert sorted(sin_banco(re_)) == [("Alquiler", 1300), ("Compra", 800), ("Luz", 270)]
# ---------- tolerancia de días ----------
r0 = c.conciliar(L, sistema_base(), dias=0)
assert 11 not in por_banco(r0) and 20 not in por_banco(r0) and 2 in por_banco(r0)                                          # con 0 días, solo el mismo día
assert any("a 1 días" in z and "revisa la fecha" in z for z in sin_registro(r0)[11]["causas"]) and ("Luz", 29) in sin_banco(r0)
r15 = c.conciliar(L, sistema_base(), dias=15)
assert len(r15["pares"]) == 14 and sorted(sin_registro(r15)) == sorted(sin_registro(r))
# ---------- palabras que se dejan fuera (movimientos que no son del negocio) ----------
rx = c.conciliar(L, sistema_base(), palabras_excluir=["pago de banco", " TITULAR cuenta "])
assert sorted(b["n"] for b in rx["excluidos"]) == [1, 16, 18] and rx["resumen"]["excluidos"] == {"n": 3, "creditos": 462.53, "debitos": round(0.12 + 10684, 2)}
assert all(n not in sin_registro(rx) for n in (1, 16, 18)) and rx["excluidos"][0]["motivo_exclusion"].startswith("contiene")
assert rx["resumen"]["banco"]["n"] == 27 == rx["resumen"]["conciliado"]["n"] + rx["resumen"]["sin_registro"]["n"] + rx["resumen"]["excluidos"]["n"]

# ---------- fecha lejana: «está registrado, pero con otra fecha» ----------
lejos = sistema_base() + [{**sis("Alquiler", I, 1, 1200, "PP - APARTAMENTO 5", "Inquilino E", "Alquiler Octubre 2026"), "fecha": D(2026, 9, 30)}]
rl = c.conciliar(L, lejos)
assert 17 not in por_banco(rl) and any("a 12 días" in z and "revisa la fecha" in z and "PP - APARTAMENTO 5" in z for z in sin_registro(rl)[17]["causas"])
assert ("Alquiler", 1200) not in sin_banco(rl)                                                                           # el de fuera del periodo no se marca como «sin banco»
# ---------- apartamentos distintos con el mismo monto el mismo día ----------
b2 = [{"n": 1, "fila": 2, "fecha": D(2026, 10, 5), "hora": None, "nro": "", "transaccion": "", "contraparte": "P1", "detalle": "Alquiler PB-04", "monto": 1100.0, "saldo": None},
      {"n": 2, "fila": 3, "fecha": D(2026, 10, 5), "hora": None, "nro": "", "transaccion": "", "contraparte": "P2", "detalle": "Alquiler PP-03", "monto": 1100.0, "saldo": None}]
s2 = [sis("Alquiler", I, 5, 1100, "PP - APARTAMENTO 3", "Q"), sis("Alquiler", I, 5, 1100, "PB - APARTAMENTO 4", "R")]
r2 = c.conciliar(b2, s2)
assert {p["banco"][0]["n"]: p["sistema"][0]["apartamento"] for p in r2["pares"]} == {1: "PB - APARTAMENTO 4", 2: "PP - APARTAMENTO 3"}   # se cruzan por apartamento, no por orden
s3 = [sis("Alquiler", I, 5, 1100, "SP - APARTAMENTO 1", "Q")]
r3 = c.conciliar(b2[:1], s3)                                                                                              # mismo monto pero otro apartamento: se avisa
assert r3["pares"][0]["confianza"] == c.REVISAR
# ---------- un solo registro y dos pagos iguales en el banco ----------
b4 = [{**b2[0], "detalle": "", "contraparte": "A"}, {**b2[1], "detalle": "", "contraparte": "B"}]
r4 = c.conciliar(b4, [sis("Venta", I, 5, 1100, persona="Z")])
assert len(r4["pares"]) == 1 and len(r4["banco_sin_registro"]) == 1 and any("ya se usó para conciliar otro movimiento del banco" in z and "Bs 1,100.00" in z for z in r4["banco_sin_registro"][0]["causas"])
assert r4["pares"][0]["confianza"] == c.MEDIA                                                                             # había dos candidatos con el mismo monto
# ---------- el sentido importa: un débito no se concilia con un ingreso ----------
r5 = c.conciliar([{**b2[0], "monto": -100.0, "detalle": ""}], [sis("Venta", I, 5, 100, persona="Z")])
assert r5["pares"] == [] and len(r5["banco_sin_registro"]) == 1 and len(r5["sistema_sin_banco"]) == 1
# ---------- combinaciones dudosas ----------
b6 = [{**b2[0], "detalle": "", "contraparte": "X", "monto": 1000.0}]
r6 = c.conciliar(b6, [sis("Venta", I, 5, 400, persona="a"), sis("Venta", I, 5, 600, persona="b")])
assert len(r6["pares"]) == 1 and r6["pares"][0]["confianza"] == c.REVISAR and r6["pares"][0]["union"] == c.BANCO_VARIOS      # dos ventas el mismo día que suman lo mismo: se propone, pero a revisar
r7 = c.conciliar(b6, [sis("Venta", I, 5, 300, persona="a"), sis("Venta", I, 5, 300, persona="b"), sis("Venta", I, 5, 400, persona="c")])
assert r7["pares"] == [] and len(r7["sistema_sin_banco"]) == 3                                                              # tres sin ninguna pista: no se inventa la coincidencia
r8 = c.conciliar(b6, [sis("Venta", I, 5, 400, persona="a"), sis("Venta", I, 9, 600, persona="b")], dias=3)
assert r8["pares"] == []                                                                                                    # una de las partes está fuera de los días: no se une
# ---------- casos borde ----------
try: c.conciliar([], [])
except ValueError as e_: assert "no tiene movimientos" in str(e_)
vacio = c.conciliar(L, [])
assert vacio["pares"] == [] and len(vacio["banco_sin_registro"]) == 27 and vacio["resumen"]["sistema"]["n"] == 0 and vacio["resumen"]["conciliado"]["n"] == 0
cero = c.conciliar([{**b2[0], "monto": 0.0}], [])
assert cero["excluidos"] and cero["excluidos"][0]["motivo_exclusion"] == "monto cero" and cero["banco_sin_registro"] == []
# ---------- ayudas de texto ----------
k = c.clave_apartamento
assert k("PB-04") == k("Pb04") == k("PB - APARTAMENTO 4") == k("alquiler pb 4 ana") == "PB-04" and k("Alquiler PP-03 (Inquilino A)") == "PP-03" and k("SP-5") == "SP-05"
assert k("") is None and k("hola 123") is None and k("TP-05 (Vania 2 meses)") == "TP-05" and k("PB-123") is None and k("OPP-03") is None
assert c.conceptos("Alquiler y Energia ?") == {"Alquiler", "Luz"} and c.conceptos("Pago de agua y luz") == {"Agua", "Luz"} and c.conceptos("Compra de pintura") == set()
assert c.conceptos("Alquile y Energia SP-03") == {"Alquiler", "Luz"} and c.conceptos("Esponja") == set()
assert c.centavos(-1847.2) == 184720 and c.centavos(0.1 + 0.2) == 30 and c.centavos(None) == 0
# ---------- unificar los dos orígenes del sistema ----------
u = c.unificar_sistema(
    [{"concepto": "Luz", "fecha": D(2026, 10, 5), "monto": 77.0, "apartamento": "PP - APARTAMENTO 3", "inquilino": "Inquilino A", "periodo": "Octubre 2026", "metodo": "QR", "observacion": "x"},
     {"concepto": "Alquiler", "fecha": D(2026, 10, 5), "monto": 5.0, "apartamento": "A", "inquilino": "B", "periodo": "—", "metodo": "—", "observacion": ""}],
    [{"origen": "Compra", "tipo": "Egreso", "fecha": D(2026, 10, 7), "monto": 150.0, "persona": "Ferreteria", "categoria": "Pintura", "detalle": "Sellador", "metodo": "QR", "metodo_original": "Qr"}])
assert [(m["origen"], m["tipo"], m["metodo"]) for m in u] == [("Luz", "Ingreso", "QR"), ("Alquiler", "Ingreso", "Sin método"), ("Compra", "Egreso", "QR")]
assert u[0]["detalle"] == "Luz Octubre 2026 x" and u[0]["apartamento"] == "PP - APARTAMENTO 3" and u[2]["persona"] == "Ferreteria"
print("PRUEBAS DE CONCILIACIÓN OK")
