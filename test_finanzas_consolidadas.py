import sys
from datetime import date
sys.path.insert(0, ".")
import finanzas_consolidadas as fc

def test_unifica_sin_confundir_deuda():
    cuadre = [
        {"id": 1, "fecha": "2026-10-01", "tipo": "Ingreso", "origen": "Venta", "categoria": "Venta extra",
         "monto": 100, "metodo_original": "QR"},
        {"id": 2, "fecha": "2026-10-02", "tipo": "Egreso", "origen": "Compra", "categoria": "Limpieza",
         "monto": 30, "metodo_original": "Efectivo", "estado": "Devuelto",
         "devolucion_a": "Tercero: Juan"},
    ]
    rendicion = [
        {"fecha": date(2026,10,3), "concepto": "Alquiler", "monto": 500, "metodo": "Transferencia",
         "apartamento": "PB-1", "inquilino": "Inquilino A"},
        {"fecha": date(2026,10,4), "concepto": "Luz", "monto": 50, "metodo": "QR",
         "apartamento": "PB-1", "inquilino": "Inquilino A"},
    ]
    movs = fc.construir_movimientos_consolidados(cuadre, rendicion)
    assert len(movs) == 4
    compra = next(x for x in movs if x["origen"] == "Compra")
    assert compra["estado"] == "Devuelto"
    assert compra["devolucion_a"] == "Tercero: Juan"
    r = fc.construir_resumen(movs, "2026-10-01", "2026-10-31", saldo_inicial=1000)
    assert r["ingresos"] == 650
    assert r["egresos"] == 30
    assert r["resultado_periodo"] == 620
    assert r["saldo_final_teorico"] == 1620
    assert r["cantidad_movimientos"] == 4
    assert {x["origen"] for x in r["por_origen"]} == {"Venta", "Compra", "Cobro de inquilino"}


def test_saldo_es_cierre_diario_no_secuencia_ficticia():
    movs = fc.construir_movimientos_consolidados(
        [{"fecha":"2026-10-01","tipo":"Ingreso","origen":"Venta","monto":100},
         {"fecha":"2026-10-01","tipo":"Egreso","origen":"Compra","monto":30}],
        [])
    r = fc.construir_resumen(movs, "2026-10-01", "2026-10-01", saldo_inicial=50)
    assert len(r["libro"]) == 2
    assert {x["saldo_acumulado"] for x in r["libro"]} == {120.0}

def test_excluye_montos_no_validos_y_fechas_fuera_rango():
    movs = fc.construir_movimientos_consolidados(
        [{"fecha":"2026-09-30","tipo":"Ingreso","origen":"Venta","monto":25,"metodo":"Efectivo"},
         {"fecha":"2026-10-02","tipo":"Egreso","origen":"Compra","monto":0,"metodo":"Efectivo"}],
        [{"fecha":"2026-10-01","concepto":"Agua","monto":75,"metodo":"QR"}])
    r=fc.construir_resumen(movs,"2026-10-01","2026-10-31")
    assert r["ingresos"] == 75
    assert r["egresos"] == 0
    assert r["cantidad_movimientos"] == 1

def test_permiso_solo_administrador():
    assert fc.puede_ver_rendicion_financiera({"rol": "Administrador"}) is True
    assert fc.puede_ver_rendicion_financiera({"rol": "Cobrador"}) is False
    assert fc.puede_ver_rendicion_financiera({}) is False
    assert fc.puede_ver_rendicion_financiera(None) is False

def test_exporta_excel_con_cuatro_hojas():
    from openpyxl import load_workbook
    from io import BytesIO
    movs = fc.construir_movimientos_consolidados(
        [{"fecha":"2026-10-01","tipo":"Ingreso","origen":"Venta","concepto":"Venta","monto":100,"metodo":"QR"}],
        [{"fecha":"2026-10-02","concepto":"Agua","monto":50,"metodo":"Efectivo"}])
    resumen = fc.construir_resumen(movs, "2026-10-01", "2026-10-31")
    contenido = fc.exportar_excel(resumen)
    wb = load_workbook(BytesIO(contenido), read_only=True)
    assert wb.sheetnames == ["Libro", "Por origen", "Por metodo", "Por dia"]
    assert wb["Libro"].max_row == 3
    wb.close()

if __name__=="__main__":
    test_unifica_sin_confundir_deuda()
    test_saldo_es_cierre_diario_no_secuencia_ficticia()
    test_excluye_montos_no_validos_y_fechas_fuera_rango()
    test_permiso_solo_administrador()
    test_exporta_excel_con_cuatro_hojas()
    print("PRUEBAS FINANZAS CONSOLIDADAS OK")
