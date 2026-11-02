from datetime import date
from decimal import Decimal
import deudas, deudores

def test_deudas():
    o = {"id": 1, "acreedor": "Banco", "categoria": "Prestamo bancario",
         "fecha_origen": "2025-01-01", "monto_original": "50000",
         "saldo_apertura": "40000", "fecha_vencimiento": "2027-01-01"}
    assert deudas.calcular_saldo(o, [{"tipo":"pago_capital","monto":"5000"}]) == Decimal("35000.00")
    assert deudas.calcular_saldo(o, []) == Decimal("40000.00")
    try:
        deudas.calcular_saldo(o, [{"tipo":"pago_capital","monto":"50000"}])
        raise AssertionError("Debió rechazar saldo negativo")
    except ValueError:
        pass

def test_deudores():
    c = {"id": 2, "deudor": "Persona", "categoria": "Prestamo a particular",
         "fecha_origen": "2025-01-01", "monto_original": "8000",
         "saldo_apertura": "8000", "fecha_vencimiento": "2027-01-01"}
    assert deudores.calcular_saldo(c, [{"tipo":"cobro","monto":"2000"}]) == Decimal("6000.00")
    try:
        deudores.calcular_saldo(c, [{"tipo":"cobro","monto":"9000"}])
        raise AssertionError("Debió rechazar cobro excesivo")
    except ValueError:
        pass

def test_validaciones():
    try:
        deudas.validar_obligacion({"acreedor":"","categoria":"Prestamo bancario",
            "fecha_origen":"2025-01-01","monto_original":100})
        raise AssertionError("Debió exigir acreedor")
    except ValueError:
        pass
    try:
        deudores.validar_cuenta({"deudor":"Persona","categoria":"Prestamo a particular",
            "fecha_origen":"2025-01-01","monto_original":0})
        raise AssertionError("Debió exigir monto positivo")
    except ValueError:
        pass

if __name__ == "__main__":
    test_deudas()
    test_deudores()
    test_validaciones()
    print("PRUEBAS V11 CUENTAS POR PAGAR/COBRAR OK")
