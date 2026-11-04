"""Pruebas de quién puede modificar el estado  ->  python test_permiso_estado.py"""
import estados as e

assert e.puede_modificar({"username": "viovip", "rol": "Cobrador"}, False)          # Viovip (aunque sea Cobrador)
assert e.puede_modificar({"username": "Viovip"}, False)                              # sin distinguir mayúsculas
assert e.puede_modificar({"username": " VIOVIP "}, False)                            # ni espacios
assert e.puede_modificar({"username": "maria", "rol": "Administrador"}, True)        # el Administrador siempre
assert e.puede_modificar({"username": "admin"}, True)                                # clave general (también es admin)
assert not e.puede_modificar({"username": "juan", "rol": "Cobrador"}, False)         # cobrador común
assert not e.puede_modificar({"username": "viovip2"}, False)                         # no basta que se parezca
assert not e.puede_modificar({"username": "xviovip"}, False)
assert not e.puede_modificar({}, False) and not e.puede_modificar(None, False)       # sin dato: sin permiso
assert not e.puede_modificar({"username": None}, False)
print("PRUEBAS DE PERMISO DE ESTADO OK")
