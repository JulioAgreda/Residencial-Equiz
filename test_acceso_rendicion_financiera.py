import finanzas_consolidadas as fc

assert fc.puede_ver_rendicion_financiera({"rol": "Administrador"})
assert not fc.puede_ver_rendicion_financiera({"rol": "Cobrador"})
assert not fc.puede_ver_rendicion_financiera({})
assert not fc.puede_ver_rendicion_financiera(None)
print("PRUEBAS DE ACCESO A RENDICION FINANCIERA OK")
