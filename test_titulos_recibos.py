import importlib.util
from pathlib import Path

mod_path = Path(__file__).with_name("recibo.py")
spec = importlib.util.spec_from_file_location("recibo", mod_path)
recibo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recibo)

assert recibo._lineas_titulo_encabezado({
    "titulo": "Recibo de cobro de cuenta por cobrar"
}) == ["COBRO DE", "CUENTA"]

assert recibo._lineas_titulo_encabezado({
    "titulo": "Recibo de Pago de Electricidad"
}) == ["ELECTRICIDAD"]

assert recibo._lineas_titulo_encabezado({
    "titulo": "Recibo de Pago de Agua"
}) == ["AGUA"]

print("Pruebas de títulos de encabezado: OK")
