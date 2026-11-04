import pytest
import seguridad


def usuario(rol='Cobrador', activo=True):
    return {'id': 7, 'username': 'prueba', 'rol': rol, 'activo': activo}


def test_rechaza_sesion_ausente():
    with pytest.raises(seguridad.AccesoDenegado):
        seguridad.validar_usuario_sesion(None)


def test_rechaza_usuario_inactivo():
    with pytest.raises(seguridad.AccesoDenegado):
        seguridad.validar_usuario_sesion(usuario(activo=False))


def test_rechaza_hash_en_sesion():
    u = usuario()
    u['password_hash'] = 'no-debe-estar-en-sesion'
    with pytest.raises(seguridad.AccesoDenegado):
        seguridad.validar_usuario_sesion(u)


def test_administrador_puede_exigir_rol():
    assert seguridad.exigir_administrador(usuario('Administrador'))['rol'] == 'Administrador'


def test_cobrador_no_es_administrador():
    with pytest.raises(seguridad.AccesoDenegado):
        seguridad.exigir_administrador(usuario('Cobrador'))


def test_apartamento_asignado_autorizado():
    assert seguridad.apartamento_autorizado(usuario(), 12, False, [12, 13])


def test_apartamento_no_asignado_rechazado():
    assert not seguridad.apartamento_autorizado(usuario(), 14, False, [12, 13])


def test_acceso_general_autorizado():
    assert seguridad.apartamento_autorizado(usuario(), 99, True, [])
