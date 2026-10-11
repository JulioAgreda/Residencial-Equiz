"""Pruebas del apartamento con 2 medidores de luz  ->  python test_dos_medidores.py
(necesita recibo.py con su logo y fuentes al lado; la parte del SQL necesita migracion_dos_medidores.sql en la misma carpeta o una arriba)"""
import os, re
import consumo as c
import recibo

# ---- qué apartamento tiene 2 medidores ----
for codigo in ("PB - APARTAMENTO 2", "pb - apartamento 2", "PB  -  APARTAMENTO  2", "PB-02", "pb-02"):
    assert c.cantidad_medidores_luz({"codigo": codigo}) == 2, codigo
for codigo in ("PB - APARTAMENTO 1", "PB - APARTAMENTO 20", "PP - APARTAMENTO 2", "SP - APARTAMENTO 2", "", None):
    assert c.cantidad_medidores_luz({"codigo": codigo}) == 1, codigo
assert c.cantidad_medidores_luz(None) == 1 and c.cantidad_medidores_luz({}) == 1

# ---- consumo total ----
p1 = {"kwh_anterior": 100, "kwh_actual": 159, "kwh_anterior_2": 10, "kwh_actual_2": 25}
assert c.pares_lecturas(p1, "electricidad") == [(100, 159), (10, 25)] and c.consumo_total(p1, "electricidad") == 74
assert c.consumo_total({"kwh_anterior": 100, "kwh_actual": 159}, "electricidad") == 59                 # sin medidor 2 (columna ausente)
assert c.consumo_total({"kwh_anterior": 100, "kwh_actual": 159, "kwh_anterior_2": None, "kwh_actual_2": None}, "electricidad") == 59
assert c.consumo_total({"kwh_anterior": 0, "kwh_actual": 0, "kwh_anterior_2": 0, "kwh_actual_2": 0}, "electricidad") == 0   # 2.º medidor en 0 cuenta como dato (0)
assert c.consumo_total({"kwh_anterior": 100, "kwh_actual": 159.4, "kwh_anterior_2": 10, "kwh_actual_2": 25.5}, "electricidad") == 75   # 59 + 16: cada medidor se redondea
assert c.consumo_total({"kwh_anterior": 100, "kwh_actual": 90, "kwh_anterior_2": 10, "kwh_actual_2": 25}, "electricidad") == 15     # un medidor negativo cuenta 0
assert c.consumo_total({"lectura_anterior": 1, "lectura_actual": 5, "kwh_actual_2": 99}, "agua") == 4                                # el agua nunca usa medidor 2
monto = c.calcular_monto(74, 1.5); assert monto == 111.0

# ---- recibo: apartamentos de 1 medidor NO cambian; con 2 medidores muestra ambos ----
cfg = recibo.SERVICIOS["electricidad"]
uno = {"kwh_anterior": 100, "kwh_actual": 159, "tarifa_kwh": 1.5, "monto_esperado": c.calcular_monto(59, 1.5)}
assert recibo._detalle_lecturas(cfg, uno) == [("Lectura anterior:", "100 Kwh"), ("Lectura actual:", "159 Kwh"),
                                              ("Consumo:", "59 Kwh"), ("Tarifa:", "Bs 1.50 por Kwh")]
dos = {**p1, "tarifa_kwh": 1.5, "monto_esperado": monto}
assert recibo._detalle_lecturas(cfg, dos, "electricidad") == [
    ("Medidor 1 - anterior:", "100 Kwh"), ("Medidor 1 - actual:", "159 Kwh"),
    ("Medidor 2 - anterior:", "10 Kwh"), ("Medidor 2 - actual:", "25 Kwh"),
    ("Consumo total:", "74 Kwh"), ("Tarifa:", "Bs 1.50 por Kwh")]
viejo = {**dos, "monto_esperado": 99.0}                                       # monto que no cuadra: solo lecturas, sin consumo ni tarifa
assert [f[0] for f in recibo._detalle_lecturas(cfg, viejo)] == ["Medidor 1 - anterior:", "Medidor 1 - actual:", "Medidor 2 - anterior:", "Medidor 2 - actual:"]
agua = recibo.SERVICIOS["agua"]
assert [f[0] for f in recibo._detalle_lecturas(agua, {"lectura_anterior": 1, "lectura_actual": 5, "kwh_actual_2": 9, "tarifa_agua": 2, "monto_esperado": 8})] == \
       ["Lectura anterior:", "Lectura actual:", "Consumo:", "Tarifa:"]
apt = {"codigo": "PB - APARTAMENTO 2", "inquilino_nombre": "Dueri", "piso": "Planta Baja"}
datos = recibo.construir_datos_recibo_servicio("electricidad", {"id": 3, "fecha": "2026-10-11", "monto": 50, "metodo_pago": "Efectivo"},
                                               {**dos, "mes": "Octubre", "anio": 2026}, apt, 50, "Vio")
assert len(datos["detalle"]) == 6
assert recibo.generar_recibo_pdf(datos)[:4] == b"%PDF" and recibo.generar_recibo_png(datos)[:4] == b"\x89PNG"

# ---- el SQL coincide con lo que usa el código ----
base = os.path.dirname(os.path.abspath(__file__))
def leer(nombre):
    for carpeta in (base, os.path.join(base, "..")):
        if os.path.exists(os.path.join(carpeta, nombre)):
            return open(os.path.join(carpeta, nombre), encoding="utf-8").read()
sql = leer("migracion_dos_medidores.sql")
if sql:
    sin_comentarios = re.sub(r"--.*", "", sql)
    for col in c.PARES_LECTURAS["electricidad"][1]:                                           # columnas del 2.º medidor
        assert f"add column if not exists {col} numeric(10,2)" in sin_comentarios, col
    assert "not null" not in sin_comentarios.lower()                                         # NULL = un solo medidor
    assert not re.search(r"\b(drop|delete|truncate|update)\b", sin_comentarios, re.I)        # no borra ni modifica datos
print("PRUEBAS DE DOS MEDIDORES OK")
