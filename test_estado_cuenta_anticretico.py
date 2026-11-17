import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import moras

def test_anticretico_solo_debe_servicios_basicos():
    apt = {"estado": "Ocupado", "tipo_contrato": "Anticrético", "monto_alquiler": 1500}
    elec = [{"mes": "Octubre", "anio": 2026, "monto_esperado": 120, "pagos_electricidad": [{"monto": 20, "fecha": "2026-10-10"}]}]
    agua = [{"mes": "Octubre", "anio": 2026, "monto_esperado": 45, "pagos_agua": [{"monto": 15, "fecha": "2026-10-11"}]}]
    d = moras.deuda_real_inquilino(apt, [], elec, date(2026, 11, 17), periodos_agua=agua)
    assert d["aplica"] is True
    assert d["alquiler"]["deuda"] == 0
    assert d["electricidad"]["deuda"] == 100
    assert d["agua"]["deuda"] == 30
    assert d["deuda_total"] == 130

def test_apartamento_desocupado_no_aplica():
    d = moras.deuda_real_inquilino({"estado": "Desocupado", "tipo_contrato": "Anticrético"}, [], [], date(2026, 11, 17))
    assert d["aplica"] is False
