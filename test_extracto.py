"""Pruebas de extracto.py  ->  python test_extracto.py"""
import csv, io
from datetime import date, datetime
import openpyxl
import extracto as x

# ============ conversión de valores ============
f = x.parsear_fecha
assert f("01/Oct/2026") == date(2026, 10, 1) and f("15/oct/2026") == date(2026, 10, 15) and f("9/Sep/2026") == date(2026, 9, 9)
assert f("05/Set/2026") == date(2026, 9, 5) and f("02/Dic/26") == date(2026, 12, 2) and f("03-Ene-2027") == date(2027, 1, 3)
assert f("01/10/2026") == date(2026, 10, 1) and f("1-10-2026") == date(2026, 10, 1) and f("2026-10-01") == date(2026, 10, 1) and f("01.10.2026") == date(2026, 10, 1)
assert f(datetime(2026, 10, 1, 14, 17)) == date(2026, 10, 1) and f(date(2026, 10, 1)) == date(2026, 10, 1) and f(46296) == date(2026, 10, 1)   # serie de Excel
assert f("31/02/2026") is None and f("") is None and f(None) is None and f("hola") is None and f("TOTAL") is None and f(5) is None and f("32/Oct/2026") is None
m = x.parsear_monto
assert m(-0.12) == -0.12 and m(1100) == 1100.0 and m("1,100.00") == 1100.0 and m("1.100,00") == -(-1100.0) and m("-1,847.20") == -1847.2
assert m("(150.00)") == -150.0 and m("150.00-") == -150.0 and m("Bs 150") == 150.0 and m("Bs. -2,000.50") == -2000.5 and m("1.234.567") == 1234567.0
assert m("150,5") == 150.5 and m("1,500") == 1500.0 and m("+25") == 25.0 and m("-10684.0") == -10684.0
assert m("") is None and m(None) is None and m("abc") is None and m("--") is None and m(True) is None and m("1,2,3x") is None
assert x.parsear_hora(datetime(2026, 1, 1, 7, 44, 26)) == "07:44:26" and x.parsear_hora("14:17:58") == "14:17:58" and x.parsear_hora(None) is None and x.parsear_hora("") is None

# ============ el extracto del banco (transcrito de la captura) ============
ENCAB = ["Fecha", "Hora", "Nro Trn./Cheque", "Transacción", "Nota", None, "Monto", "Saldo"]
D, C, T = "DEBITO ACH QR", "CREDITO ACH QR", "TRASPASO CA/CC CON QR (MOVIL)"
FILAS = [
 ("01/Oct/2026", "14:17:58", 100000001, D, "TITULAR CUENTA UNO", "", -0.12, 0.0),
 ("05/Oct/2026", "12:52:30", 100000002, C, "PAGADOR UNO", "Alquiler PP-03 (Inquilino A - Octubre)", 1100.0, 1100.0),
 ("05/Oct/2026", "13:30:15", 100000003, C, "PAGADOR UNO", "Energia  PP-03 (Inquilino A - Octubre)", 77.0, 1177.0),
 ("06/Oct/2026", "13:00:02", 100000004, C, "DEPOSITANTE UNO", "Alquiler y Energia ?", 5939.0, 7116.0),
 ("06/Oct/2026", "18:44:12", 100000005, C, "DEPOSITANTE UNO", "No se Sabe", 1543.0, 8659.0),
 ("07/Oct/2026", "07:44:26", 100000006, D, "PROVEEDOR PERSIANAS (B.", "Primer Pago Persianas", -2000.0, 6659.0),
 ("07/Oct/2026", "12:18:55", 100000007, C, "PAGADOR UNO", "Alquiler PB-04 (Inquilino B-)", 1600.0, 8259.0),
 ("07/Oct/2026", "17:23:51", 100000008, D, "DEPOSITANTE DOS", "Compra de Sellador de Pintura", -150.0, 8109.0),
 ("07/Oct/2026", "17:38:40", 45316816, T, "TRASP.CTAS.TERCEROS", "Alquiler y Energia Pb-04 (Inquilino C - Octubre)", 1976.0, 10085.0),
 ("08/Oct/2026", "18:41:54", 100000009, C, "DEPOSITANTE UNO", "Alquiler SP-05 (Inquilino D - Octubre)", 1100.0, 11185.0),
 ("08/Oct/2026", "18:50:27", 100000010, C, "PAGADOR DOS", "Energia SP-05 (Inquilino D - Octubre)", 29.0, 11214.0),
 ("09/Oct/2026", "07:21:28", 100000011, D, "ENCARGADO UNO", "Esponja 40 y el palo 70", -110.0, 11104.0),
 ("09/Oct/2026", "15:12:37", 100000012, D, "ENCARGADO UNO", "Pago de tramite", -3500.0, 7604.0),
 ("09/Oct/2026", "19:08:20", 100000013, C, "DEPOSITANTE UNO", "No se Sabe", 3100.0, 10704.0),
 ("10/Oct/2026", "12:43:03", 100000014, D, "ENCARGADO UNO", "Pago de Anulacion de Foco", -20.0, 10684.0),
 ("12/Oct/2026", "13:10:04", 100000015, D, "TITULAR CUENTA UNO", "Pago de Banco - Mes", -10684.0, 0.0),
 ("12/Oct/2026", "19:37:54", 100000016, C, "DEPOSITANTE UNO", "Alquiler PP-05 (Inquilino E - )", 1200.0, 1200.0),
 ("12/Oct/2026", "19:39:24", 100000017, C, "TITULAR CUENTA UNO", "", 462.53, 1662.53),
 ("13/Oct/2026", "07:45:12", 100000018, C, "DEPOSITANTE DOS", "", 1400.0, 3062.53),
 ("13/Oct/2026", "12:17:36", 100000019, C, "PAGADOR TRES", "Alquile y Energia SP-03 (Inquilino F-Octubre)", 1506.0, 4568.53),
 ("13/Oct/2026", "20:46:23", 100000020, D, "PROVEEDOR PERSIANAS (B.", "Segundo pago de Persianas", -3200.0, 1368.53),
 ("14/Oct/2026", "11:31:45", 100000021, C, "PAGADOR CUATRO", "Alquiler TP-05 (Inquilino G 2 meses (Junio - Julio)", 2200.0, 3568.53),
 ("14/Oct/2026", "18:21:53", 45794833, T, "TRASP.CTAS.TERCEROS", "Energia PB04 (Inquilino B - )", 278.0, 3846.53),
 ("15/Oct/2026", "15:10:53", 100000022, D, "FERRETERIA UNO", "Compra de pintura +  Interruptor", -450.0, 3396.53),
 ("15/Oct/2026", "22:55:28", 100000023, D, "DEPOSITANTE DOS", "", -1400.0, 1996.53),
 ("15/Oct/2026", "23:03:58", 100000024, D, "DEPOSITANTE DOS", "", -100.0, 1896.53),
 ("16/Oct/2026", "11:07:04", 100000025, D, "SERVICIOS S.R.L. (B.", "", -1847.2, 49.33),
]
def libro_xlsx(filas=FILAS, encab=ENCAB, antes=(), despues=(), fechas_reales=False, montos_texto=False):
    wb = openpyxl.Workbook(); ws = wb.active
    for fila in antes: ws.append(list(fila))
    ws.append(list(encab))
    for f in filas:
        f = list(f)
        if fechas_reales: f[0] = x.parsear_fecha(f[0])
        if montos_texto: f[6], f[7] = f"{f[6]:,.2f}", f"{f[7]:,.2f}"
        ws.append(f)
    for fila in despues: ws.append(list(fila))
    b = io.BytesIO(); wb.save(b); return b.getvalue()

r = x.leer_extracto(libro_xlsx(), "extracto.xlsx")
L = r["lineas"]
assert len(L) == 27 and r["faltan"] == [] and r["fila_encabezado"] == 1 and r["avisos"] == []
assert {k: r["encabezados"][v] for k, v in r["columnas"].items()} == {"fecha": "Fecha", "hora": "Hora", "saldo": "Saldo", "monto": "Monto", "transaccion": "Transacción",
        "nro": "Nro Trn./Cheque", "contraparte": "Nota", "detalle": ""}                                  # la columna SIN título entre la nota y el monto es el detalle
assert (r["desde"], r["hasta"]) == (date(2026, 10, 1), date(2026, 10, 16))
assert r["total_creditos"] == 23510.53 and r["total_debitos"] == 23461.32 and r["saldo_inicial"] == 0.12 and r["saldo_final"] == 49.33
assert round(r["saldo_inicial"] + r["total_creditos"] - r["total_debitos"], 2) == r["saldo_final"] and r["problemas_saldo"] == []   # el saldo del extracto cuadra
l2, l9, l13 = L[1], L[8], L[12]
assert (l2["fecha"], l2["hora"], l2["nro"], l2["transaccion"], l2["contraparte"], l2["detalle"], l2["monto"], l2["saldo"]) == (
    date(2026, 10, 5), "12:52:30", "100000002", C, "PAGADOR UNO", "Alquiler PP-03 (Inquilino A - Octubre)", 1100.0, 1100.0)
assert l9["transaccion"].startswith("TRASPASO") and l13["monto"] == -3500.0 and L[0]["monto"] == -0.12 and L[0]["detalle"] == "" and [l["n"] for l in L] == list(range(1, 28))
assert L[0]["fila"] == 2 and L[1]["fila"] == 3                                                              # número de fila del archivo (para ubicar errores)

# ============ variantes de formato ============
# títulos antes de la tabla, fechas de Excel, montos como texto con comas, filas de total al pie, fila vacía
r2 = x.leer_extracto(libro_xlsx(antes=[["BANCO EJEMPLO"], ["Extracto de cuenta 123"], []], despues=[[], ["TOTAL", None, None, None, None, None, 99999, None]],
                                fechas_reales=True, montos_texto=True), "e.xlsx")
assert len(r2["lineas"]) == 27 and r2["fila_encabezado"] == 3 and r2["total_creditos"] == 23510.53 and r2["saldo_final"] == 49.33 and r2["problemas_saldo"] == []
assert any("Se ignoraron 1 fila" in a for a in r2["avisos"])                                                  # el total al pie no se cuenta como movimiento
# CSV con ; y columnas Débito / Crédito separadas
filas_csv = [["Fecha", "Descripción", "Débito", "Crédito", "Saldo"], ["05/10/2026", "ALQUILER", "", "1.100,00", "1.100,00"], ["06/10/2026", "COMPRA", "150,50", "", "949,50"]]
buf = io.StringIO(); csv.writer(buf, delimiter=";").writerows(filas_csv)
r3 = x.leer_extracto(buf.getvalue().encode("utf-8"), "e.csv")
assert [(l["fecha"], l["monto"], l["saldo"], l["contraparte"]) for l in r3["lineas"]] == [(date(2026, 10, 5), 1100.0, 1100.0, "ALQUILER"), (date(2026, 10, 6), -150.5, 949.5, "COMPRA")]
assert r3["problemas_saldo"] == [] and r3["saldo_inicial"] == 0.0
# CSV en latin-1 (acentos) con coma
buf = io.StringIO(); csv.writer(buf).writerows([["Fecha", "Transacción", "Nota", "Monto"], ["2026-10-05", "CRÉDITO", "Ñandú", "100"]])
assert x.leer_extracto(buf.getvalue().encode("latin-1"), "e.csv")["lineas"][0]["contraparte"] == "Ñandú"
# montos SIN signo: la transacción dice si es débito o crédito
sin_signo = [("05/Oct/2026", "1", 1, C, "A", "", 100.0, 100.0), ("06/Oct/2026", "1", 2, D, "B", "", 30.0, 70.0)]
r4 = x.leer_extracto(libro_xlsx(sin_signo), "e.xlsx")
assert [l["monto"] for l in r4["lineas"]] == [100.0, -30.0] and r4["problemas_saldo"] == [] and any("sin signo" in a for a in r4["avisos"])
# extracto exportado del más nuevo al más antiguo: el control de saldo sigue funcionando
r5 = x.leer_extracto(libro_xlsx(list(reversed(FILAS))), "e.xlsx")
assert r5["problemas_saldo"] == [] and r5["saldo_inicial"] == 0.12 and r5["saldo_final"] == 49.33 and len(r5["lineas"]) == 27
# sin columna de saldo y sin detalle
r6 = x.leer_extracto(libro_xlsx([("05/Oct/2026", 1100.0), ("06/Oct/2026", -50.0)], encab=["Fecha", "Importe"]), "e.xlsx")
assert [l["monto"] for l in r6["lineas"]] == [1100.0, -50.0] and r6["saldo_final"] is None and r6["problemas_saldo"] == [] and r6["lineas"][0]["detalle"] == ""

# ============ control del saldo: líneas que faltan o sobran ============
faltante = [f for i, f in enumerate(FILAS) if i != 13]                       # se pierde la línea de 3100 del 09/Oct
r7 = x.leer_extracto(libro_xlsx(faltante), "e.xlsx")
assert len(r7["problemas_saldo"]) == 1 and r7["problemas_saldo"][0]["diferencia"] == 3100.0 and r7["problemas_saldo"][0]["fecha"] == date(2026, 10, 10)
repetida = FILAS[:5] + [FILAS[4]] + FILAS[5:]                                 # una línea duplicada
r8 = x.leer_extracto(libro_xlsx(repetida), "e.xlsx")
assert len(r8["problemas_saldo"]) == 1 and r8["problemas_saldo"][0]["diferencia"] == -1543.0 and r8["problemas_saldo"][0]["saldo_esperado"] == 10202.0   # el saldo no sube con la línea repetida

# ============ columnas que no se reconocen: se pueden elegir a mano ============
raro = [("05/Oct/2026", 1100.0, "x"), ("06/Oct/2026", -50.0, "y")]
r9 = x.leer_extracto(libro_xlsx(raro, encab=["Fecha", "Valor", "Quien"]), "e.xlsx")
assert r9["lineas"] == [] and r9["faltan"] == ["monto"] and r9["encabezados"] == ["Fecha", "Valor", "Quien"]
r10 = x.leer_extracto(libro_xlsx(raro, encab=["Fecha", "Valor", "Quien"]), "e.xlsx", mapeo={"fecha": 0, "monto": 1, "contraparte": 2})
assert [l["monto"] for l in r10["lineas"]] == [1100.0, -50.0] and r10["lineas"][0]["contraparte"] == "x" and r10["faltan"] == []

# ============ errores claros ============
def error(contenido, nombre):
    try: x.leer_extracto(contenido, nombre)
    except x.ErrorExtracto as e: return str(e)
assert ".xls" in error(b"x", "extracto.xls") and "vacío" in error(b"", "e.csv")
sin_encabezado = io.BytesIO(); wb = openpyxl.Workbook(); wb.active.append(["hola", "mundo"]); wb.save(sin_encabezado)
assert "encabezados" in error(sin_encabezado.getvalue(), "e.xlsx") and "No se pudo abrir" in error(b"no es un excel", "e.xlsx")
assert "movimientos" in error(libro_xlsx([("nada", "nada")], encab=["Fecha", "Monto"]), "e.xlsx")
print("PRUEBAS DE EXTRACTO OK")
