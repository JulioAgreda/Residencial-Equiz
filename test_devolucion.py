"""Pruebas del estado de devolución y «Devolución a»  ->  python test_devolucion.py
(la parte del SQL necesita migracion_devolucion_usuario.sql en la misma carpeta o una arriba)"""
import os, re
import estados as e
import reportes as rp

NUEVO = "Se realizó la devolución a la persona que realizó el pago"
ANTERIOR = "Se realizó devolución"

# ---- textos ----
assert e.ESTADOS_DEVOLUCION == ["No aplica", "Pendiente de devolución", NUEVO] and e.REALIZADA_DEVOLUCION == NUEVO
assert e.ESTADOS_ENTREGA == ["No aplica", "Pendiente de entrega", "Se realizó entrega"]          # Ventas no cambia
# un registro viejo (texto anterior) sigue viéndose como «realizada», no como «No aplica»
assert e.normalizar(ANTERIOR, e.ESTADOS_DEVOLUCION) == NUEVO and e.indice(ANTERIOR, e.ESTADOS_DEVOLUCION) == 2
assert e.normalizar(ANTERIOR, e.ESTADOS_ENTREGA) == "No aplica"                                   # y no se cuela en Ventas
assert e.normalizar(None, e.ESTADOS_DEVOLUCION) == e.normalizar("", e.ESTADOS_DEVOLUCION) == e.normalizar("otro", e.ESTADOS_DEVOLUCION) == "No aplica"
reg = [{"estado_devolucion": ANTERIOR}, {"estado_devolucion": NUEVO}, {"estado_devolucion": e.PENDIENTE_DEVOLUCION}, {}]
assert len(e.filtrar_por_estado(reg, "estado_devolucion", NUEVO, e.ESTADOS_DEVOLUCION)) == 2        # el filtro agrupa texto anterior y nuevo
assert len(e.filtrar_por_estado(reg, "estado_devolucion", "No aplica", e.ESTADOS_DEVOLUCION)) == 1

# ---- a quién se devolvió ----
assert e.validar_devolucion(NUEVO, "") and e.validar_devolucion(NUEVO, None) and e.validar_devolucion(NUEVO, "   ")
assert e.validar_devolucion(ANTERIOR, None)                                                         # el texto anterior también exige el nombre
assert e.validar_devolucion(NUEVO, "Ana") is None
assert e.validar_devolucion("Pendiente de devolución", None) is None and e.validar_devolucion("No aplica", "") is None
assert e.devolucion_a_a_guardar(NUEVO, "  Ana ") == "Ana" and e.devolucion_a_a_guardar(NUEVO, "") is None
assert e.devolucion_a_a_guardar("Pendiente de devolución", "Ana") is None                           # si cambia a otro estado, se limpia
assert e.devolucion_a_a_guardar("No aplica", "Ana") is None
assert e.texto_devolucion_a(NUEVO, "Ana") == "Ana" and e.texto_devolucion_a(NUEVO, None) == "(sin indicar)"
assert e.texto_devolucion_a(ANTERIOR, None) == "(sin indicar)" and e.texto_devolucion_a("Pendiente de devolución", "Ana") == ""

# ---- devolución a un TERCERO (persona externa que no es usuario del sistema) ----
T = e.OPCION_TERCERO
assert e.componer_devolucion_a(T, "  Juan Gómez ") == "Tercero: Juan Gómez" and e.componer_devolucion_a("Ana", "ignorado") == "Ana"
assert e.componer_devolucion_a(None, "Juan") is None and e.componer_devolucion_a("", "") is None
assert e.componer_devolucion_a(T, "") == "Tercero:" and e.componer_devolucion_a(T, None) == "Tercero:"           # eligió Tercero y no escribió el nombre
assert e.validar_devolucion(NUEVO, "Tercero:") and e.validar_devolucion(NUEVO, "Tercero:   ")                      # -> se rechaza, con mensaje propio
assert "nombre del tercero" in e.validar_devolucion(NUEVO, "Tercero:") and "quién" in e.validar_devolucion(NUEVO, "")
assert e.validar_devolucion(NUEVO, "Tercero: Juan Gómez") is None and e.validar_devolucion(NUEVO, "Ana") is None
assert e.validar_devolucion(e.PENDIENTE_DEVOLUCION, "Tercero:") is None                                           # en otro estado no se exige
assert e.validar_devolucion(NUEVO, "Tercero: " + "x" * 200) and e.validar_devolucion(NUEVO, "Tercero: " + "x" * 100) is None   # cabe en varchar(150)
assert e.devolucion_a_a_guardar(NUEVO, "Tercero: Juan Gómez") == "Tercero: Juan Gómez"
assert e.devolucion_a_a_guardar(e.PENDIENTE_DEVOLUCION, "Tercero: Juan") is None                                   # si deja de estar realizada, se limpia
assert e.texto_devolucion_a(NUEVO, "Tercero: Juan Gómez") == "Tercero: Juan Gómez"                               # se lee claro en tablas y reportes
assert e.separar_devolucion_a("Tercero: Juan Gómez") == (T, "Juan Gómez") and e.separar_devolucion_a("Ana") == ("Ana", "")
assert e.separar_devolucion_a(None) == (None, "") and e.separar_devolucion_a("tercero: x")[0] != T                  # solo el formato exacto cuenta
for nombre in ("Juan Gómez", "María del Carmen", "Empresa X & Cía."):                                              # ida y vuelta sin pérdida
    assert e.separar_devolucion_a(e.componer_devolucion_a(T, nombre)) == (T, nombre)
assert e.es_tercero("Tercero: A") and not e.es_tercero("Ana") and not e.es_tercero(None) and not e.es_tercero("Terceros SA")

# ---- reporte «Actividad por usuario» ----
pago = {"fecha_pago": "2026-10-02", "monto": 10, "estado_devolucion": NUEVO, "devolucion_a": "Ana"}
compra = {"fecha_compra": "2026-10-02", "monto_total": 10, "estado_devolucion": ANTERIOR}
venta = {"fecha_venta": "2026-10-02", "monto": 10, "estado_entrega": "Pendiente de entrega"}
assert rp.fila_pago_general(pago)["Devolución a"] == "Ana" and rp.fila_pago_general(pago)["Estado"] == NUEVO
assert rp.fila_compra(compra)["Devolución a"] == "(sin indicar)" and rp.fila_compra(compra)["Estado"] == NUEVO   # texto anterior -> texto actual
assert "Devolución a" not in rp.fila_venta(venta) and rp.fila_venta(venta)["Estado"] == "Pendiente de entrega"
assert rp.fila_pago_general({"fecha_pago": "2026-10-02", "monto": 1})["Devolución a"] == ""
assert rp.fila_pago_general({**pago, "devolucion_a": "Tercero: Juan Gómez"})["Devolución a"] == "Tercero: Juan Gómez"

# ---- el SQL coincide con lo que usa el código ----
base = os.path.dirname(os.path.abspath(__file__))
def leer(nombre):
    for carpeta in (base, os.path.join(base, "..")):
        if os.path.exists(os.path.join(carpeta, nombre)):
            return open(os.path.join(carpeta, nombre), encoding="utf-8").read()
sql = leer("migracion_devolucion_usuario.sql")
if sql:
    codigo = re.sub(r"--.*", "", sql)
    for texto in e.ESTADOS_DEVOLUCION:
        assert f"'{texto}'" in codigo, texto                                                          # los 3 textos de la validación
    assert f"'{ANTERIOR}'" in codigo                                                                  # migra el texto anterior
    assert "'compras', 'pagos_generales'" in codigo and "devolucion_a varchar(150)" in codigo
    assert "add column if not exists" in codigo and "not valid" in codigo
    assert not re.search(r"\b(delete|truncate|drop\s+table|drop\s+column)\b", codigo, re.I)         # no borra datos
    assert len(NUEVO) < 150                                                                           # cabe en la columna
print("PRUEBAS DE DEVOLUCIÓN OK")
