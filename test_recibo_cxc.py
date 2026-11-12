import recibo

cuenta = {
    "id": 7, "codigo": "CXC-000001", "categoria": "Préstamo realizado",
    "deudor": "Martha Rosario Cespedes Vaca", "descripcion": "Préstamo personal",
    "monto_original": 1200, "saldo_apertura": 1200, "creado_por": "Julio Agreda",
}
movimientos = [
    {"id": 11, "cuenta_id": 7, "tipo": "cobro", "fecha": "2026-11-06", "monto": 1000,
     "metodo": "Transferencia Bancaria", "referencia": "256837157", "registrado_por": "Julio Agreda"},
    {"id": 12, "cuenta_id": 7, "tipo": "cobro", "fecha": "2026-11-10", "monto": 100,
     "metodo": "Efectivo", "registrado_por": "Julio Agreda"},
]
datos = recibo.construir_datos_recibo_cuenta_cobrar(cuenta, movimientos[0], movimientos)
assert datos["numero_recibo"] == "REC-CXC-000011"
assert datos["monto_pagado"] == 1000
assert datos["total_pagado_periodo"] == 1100
assert datos["saldo_pendiente"] == 100
assert datos["etiqueta_apartamento"] == "Cuenta por cobrar:"
assert recibo.generar_recibo_pdf(datos).startswith(b"%PDF")
assert recibo.generar_recibo_png(datos).startswith(b"\x89PNG")

# IDs UUID también producen números de recibo válidos y estables.
mov_uuid = {"id": "a1b2-c3d4-5678", "cuenta_id": 7, "tipo": "cobro", "fecha": "2026-11-11", "monto": 25}
datos_uuid = recibo.construir_datos_recibo_cuenta_cobrar(cuenta, mov_uuid, [mov_uuid])
assert datos_uuid["numero_recibo"] == "REC-CXC-A1B2C3D456"

# Rechaza cobros que pertenecen a otra cuenta o movimientos que no son cobros.
try:
    recibo.construir_datos_recibo_cuenta_cobrar(cuenta, {**movimientos[0], "cuenta_id": 99}, movimientos)
    raise AssertionError("Debió rechazar cuenta distinta")
except ValueError:
    pass
try:
    recibo.construir_datos_recibo_cuenta_cobrar(cuenta, {**movimientos[0], "tipo": "ajuste"}, movimientos)
    raise AssertionError("Debió rechazar movimiento que no es cobro")
except ValueError:
    pass
print("PRUEBAS DE RECIBO CXC OK")
