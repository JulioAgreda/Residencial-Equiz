"""Pruebas de accesos.py  ->  python test_accesos.py"""
import accesos as a

usuarios = [{"id": 1, "acceso_todos_apartamentos": True}, {"id": 2, "acceso_todos_apartamentos": False},
            {"id": 3, "acceso_todos_apartamentos": False}, {"id": 4}, {"id": 5, "acceso_todos_apartamentos": None}]
asign = [{"usuario_id": 2, "apartamento_id": 10}, {"usuario_id": 2, "apartamento_id": 11}, {"usuario_id": 2, "apartamento_id": 10},   # duplicado
         {"usuario_id": 1, "apartamento_id": 12}, {"usuario_id": 99, "apartamento_id": 13}]                                          # de un usuario que ya no existe
acc = a.construir_accesos(usuarios, asign)
assert acc[1] == {"todos": True, "ids": {12}}                          # "todos" ignora sus asignaciones (se conservan por si vuelve a restringirse)
assert acc[2] == {"todos": False, "ids": {10, 11}}                     # duplicados no cuentan dos veces
assert acc[3] == {"todos": False, "ids": set()}                        # restringido sin asignaciones
assert acc[4]["todos"] is True and acc[5]["todos"] is True             # sin dato = por defecto "todos" (nadie pierde acceso)
assert 99 not in acc and a.construir_accesos(None, None) == {}

# resolver
assert a.resolver(True, 2, acc) is None                                # el administrador ve todo, aunque tenga una restricción guardada
assert a.resolver(False, 1, acc) is None and a.resolver(False, 4, acc) is None
assert a.resolver(False, 2, acc) == {10, 11}
assert a.resolver(False, 3, acc) == set()                              # restringido sin asignaciones: NO ve ninguno (set vacío, no None)
assert a.resolver(False, 3, acc) is not None
assert a.resolver(False, None, acc) is None                            # sesión sin id (clave general): sin restricción
assert a.resolver(False, 2, acc, funcion_disponible=False) is None     # migración sin ejecutar: funciona como antes
assert a.resolver(False, 777, acc) is None and a.resolver(False, 2, {}) is None    # usuario desconocido / sin datos: sin restricción
copia = a.resolver(False, 2, acc); copia.add(999); assert acc[2]["ids"] == {10, 11}      # el resultado no permite alterar los datos guardados

# filtrar
filas = [{"id": 1, "apartamento_id": 10}, {"id": 2, "apartamento_id": 11}, {"id": 3, "apartamento_id": 12}, {"id": 4, "apartamento_id": None}]
assert [f["id"] for f in a.filtrar(filas, None)] == [1, 2, 3, 4]                       # sin restricción: todo (incluye sin apartamento)
assert [f["id"] for f in a.filtrar(filas, {10, 11})] == [1, 2]                          # sin apartamento NO pasa por defecto
assert [f["id"] for f in a.filtrar(filas, {10, 11}, permitir_vacio=True)] == [1, 2, 4]   # pendientes «Generales» sí
assert a.filtrar(filas, set()) == [] and [f["id"] for f in a.filtrar(filas, set(), permitir_vacio=True)] == [4]
assert [x["id"] for x in a.filtrar([{"id": 10}, {"id": 12}], {10}, campo="id")] == [10]
assert a.filtrar([], {1}) == [] and a.filtrar([{"otro": 1}], {1}) == []                 # registro sin el campo no pasa
assert a.filtrar(filas, None) is not filas                                              # devuelve una copia

# resumen
assert a.resumen(acc[1], 20) == "Todos" and a.resumen(acc[2], 20) == "2 de 20" and a.resumen(acc[3], 20) == "Ninguno"
assert a.resumen(None, 20) == "Todos" and a.resumen(acc[3], 20, es_admin=True) == "Todos (administrador)"
# ---- los nombres de tabla y columnas del SQL deben coincidir con los que usa el código ----
import os, re
base = os.path.dirname(os.path.abspath(__file__))
def leer(nombre):
    for carpeta in (base, os.path.join(base, "..")):
        if os.path.exists(os.path.join(carpeta, nombre)):
            return open(os.path.join(carpeta, nombre), encoding="utf-8").read()
sql, codigo_db = leer("migracion_acceso_apartamentos.sql"), leer("db.py")
if sql and codigo_db:
    for nombre in ("usuarios_apartamentos", "usuario_id", "apartamento_id", "acceso_todos_apartamentos"):
        assert nombre in sql and nombre in codigo_db, nombre
    assert "primary key (usuario_id, apartamento_id)" in sql                                    # evita asignaciones duplicadas
    assert "acceso_todos_apartamentos boolean not null default true" in sql                      # los usuarios existentes NO pierden acceso
    assert sql.count("on delete cascade") == 2                                                  # al borrar un usuario o apartamento se limpian las asignaciones
    sin_comentarios = re.sub(r"--.*", "", sql)
    assert not re.search(r"\b(drop|delete|truncate)\b", sin_comentarios.replace("on delete cascade", ""), re.I)   # la migración no borra nada
print("PRUEBAS DE ACCESOS OK (incluye coincidencia con el SQL)")
