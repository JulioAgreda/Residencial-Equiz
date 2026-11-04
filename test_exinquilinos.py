"""Pruebas de exinquilinos.py  ->  python test_exinquilinos.py"""
from datetime import date, timedelta
import exinquilinos as x

def per(i, hid, mes, anio, esperado, pagos=(), campo="pagos"):
    return {"id": i, "inquilino_historial_id": hid, "mes": mes, "anio": anio, "monto_esperado": esperado,
            campo: [{"id": k, "monto": m, "fecha": f} for k, (m, f) in enumerate(pagos, 1)]}

# ---- saldo y deuda: cada periodo por separado, nunca negativa ----
assert x.saldo(per(1, 1, "Julio", 2026, 600), "pagos") == 600
assert x.saldo(per(1, 1, "Julio", 2026, 600, [(200, "2026-10-04")]), "pagos") == 400
assert x.saldo(per(1, 1, "Julio", 2026, 600, [(700, "2026-10-04")]), "pagos") == 0            # pagó de más: saldo 0, no -100
assert x.saldo({"monto_esperado": 10.1, "pagos": [{"monto": 0.1}]}, "pagos") == 10            # sin errores de coma flotante
cerrados = {"alquiler": [per(1, 1, "Julio", 2026, 600), per(2, 1, "Agosto", 2026, 600, [(700, "2026-10-04")]),   # agosto pagado de más
                         per(3, 2, "Septiembre", 2026, 800, [(800, "2026-09-20")])],
            "electricidad": [per(4, 1, "Agosto", 2026, 40, [], "pagos_electricidad")],
            "agua": [per(5, 1, "Agosto", 2026, 30, [(30, "2026-10-05")], "pagos_agua")], }
g = x.agrupar_por_historial(cerrados)
assert sorted(g) == [1, 2] and [p["id"] for p in g[1]["alquiler"]] == [1, 2] and g[2]["electricidad"] == []
assert x.deuda_ex_inquilino(g[1]) == {"alquiler": 600, "luz": 40, "agua": 0, "total": 640}      # el pago de más de agosto NO resta la deuda de julio
assert x.deuda_ex_inquilino(g[2])["total"] == 0 and x.deuda_ex_inquilino({}) == {"alquiler": 0, "luz": 0, "agua": 0, "total": 0}
assert x.agrupar_por_historial({"alquiler": [{"id": 9, "mes": "Enero", "anio": 2026, "monto_esperado": 1}]}) == {}   # un periodo abierto (sin historial) no entra
assert x.agrupar_por_historial(None) == {}

# ---- nombre y etiqueta ----
assert x.nombre_ex_inquilino({"inquilino_nombre": "Carlos"}) == "Carlos" and x.nombre_ex_inquilino({"nombre": "Ana"}) == "Ana" and x.nombre_ex_inquilino({}) == "—"
assert x.etiqueta_periodo(per(1, 1, " octubre ", 2026, 1)) == "Octubre 2026" and x.etiqueta_periodo(per(1, 1, "???", 2026, 1)) == "—"

# ---- abonos de un ex inquilino ----
assert x.validar_abono(0, 100) and x.validar_abono(-5, 100) and x.validar_abono(None, 100)
assert x.validar_abono(100, 100) is None and x.validar_abono(99.99, 100) is None and x.validar_abono(100.005, 100) is None   # el saldo exacto sí
assert "saldo pendiente" in x.validar_abono(100.5, 100) and "100.00" in x.validar_abono(150, 100)
mezcla = [per(1, 1, "Septiembre", 2026, 600), per(2, 1, "Julio", 2026, 600, [(600, "2026-07-05")]), per(3, 1, "???", 2026, 50),
          per(4, 1, "Agosto", 2026, 600, [(100, "2026-08-05")])]
assert [p["id"] for p in x.periodos_con_saldo(mezcla, "pagos")] == [4, 1, 3]                    # julio ya está pagado; el más antiguo primero; ilegible al final

# ---- salida: meses sin registro y deuda con la que sale ----
apt = {"id": 1, "estado": "Ocupado", "inquilino_nombre": "Carlos", "monto_alquiler": 600, "dia_pago": 5, "fecha_ingreso": "2026-06-10",
       "tipo_contrato": "Alquiler"}
junio = {"id": 1, "mes": "Junio", "anio": 2026, "monto_esperado": 600, "pagos": [{"monto": 500, "fecha": "2026-06-11"}]}      # debe 100
sin = x.meses_sin_registro(apt, [junio], date(2026, 8, 20))
assert [(m["etiqueta"], m["monto"], m["mes"], m["anio"]) for m in sin] == [("Julio 2026", 600, "Julio", 2026), ("Agosto 2026", 600, "Agosto", 2026)]
assert [m["etiqueta"] for m in x.meses_sin_registro(apt, [junio], date(2026, 8, 3))] == ["Julio 2026"]    # agosto aún no vence: no es deuda
assert x.meses_sin_registro({**apt, "tipo_contrato": "Anticrético"}, [junio], date(2026, 8, 20)) == []
assert x.meses_sin_registro({**apt, "estado": "Desocupado"}, [junio], date(2026, 8, 20)) == []
luz = [{"id": 2, "mes": "Julio", "anio": 2026, "monto_esperado": 33, "pagos_electricidad": []}]
agua = [{"id": 3, "mes": "Julio", "anio": 2026, "monto_esperado": 20, "pagos_agua": [{"monto": 20, "fecha": "2026-07-09"}]}]
r1 = x.resumen_salida(apt, [junio], luz, agua, date(2026, 8, 20))
assert (r1["alquiler"], r1["luz"], r1["agua"], r1["total"]) == (100 + 1200, 33, 0, 1333) and len(r1["meses_sin_registro"]) == 2
r2 = x.resumen_salida(apt, [junio], luz, agua, date(2026, 8, 20), incluir_meses_sin_registro=False)
assert (r2["alquiler"], r2["total"]) == (100, 133) and len(r2["meses_sin_registro"]) == 2          # sin registrarlos, la deuda solo incluye lo ya registrado
assert x.resumen_salida({**apt, "estado": "Desocupado"}, [], [], [], date(2026, 8, 20))["total"] == 0

# ---- validar la salida ----
hoy = date.today()
assert x.validar_salida(apt, hoy, True) == []
assert any("confirmación" in e for e in x.validar_salida(apt, hoy, False))
assert any("fecha de salida" in e for e in x.validar_salida(apt, None, True))
assert any("no tiene un inquilino" in e for e in x.validar_salida({**apt, "estado": "Desocupado"}, hoy, True))
assert any("no tiene un inquilino" in e for e in x.validar_salida({**apt, "inquilino_nombre": "  "}, hoy, True))
assert x.validar_salida(apt, hoy - timedelta(days=400), True) == []                              # una salida pasada se puede registrar tarde
assert any("futuro" in e for e in x.validar_salida(apt, hoy + timedelta(days=90), True)) and x.validar_salida(apt, hoy + timedelta(days=10), True) == []
print("PRUEBAS DE EX INQUILINOS OK")
