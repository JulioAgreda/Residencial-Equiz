import sys
import types
import pytest

# Stubs mínimos: las pruebas de autorización no necesitan conectarse a Streamlit ni Supabase.
st = types.ModuleType("streamlit")
st.cache_resource = lambda fn=None, **kwargs: (lambda f: f) if fn is None else fn
st.secrets = {}
sys.modules.setdefault("streamlit", st)
supabase = types.ModuleType("supabase")
supabase.Client = object
supabase.create_client = lambda *args, **kwargs: None
sys.modules.setdefault("supabase", supabase)

import seguridad
import db

def admin():
    return {"id": 1, "username": "admin", "rol": "Administrador", "activo": True}

def cobrador():
    return {"id": 2, "username": "cobrador", "rol": "Cobrador", "activo": True}

def test_crear_usuario_rechaza_cobrador():
    with pytest.raises(seguridad.AccesoDenegado):
        db.crear_usuario({"username": "nuevo", "password_hash": "hash", "rol": "Cobrador"}, cobrador())

def test_actualizar_usuario_rechaza_cobrador():
    with pytest.raises(seguridad.AccesoDenegado):
        db.actualizar_usuario(3, {"activo": False}, cobrador())

def test_desactivar_usuario_rechaza_autodesactivacion():
    with pytest.raises(seguridad.AccesoDenegado):
        db.eliminar_usuario(1, admin())

def test_guardar_acceso_rechaza_cobrador():
    with pytest.raises(seguridad.AccesoDenegado):
        db.guardar_acceso_apartamentos(3, True, (), usuario_solicitante=cobrador())

def test_actualizar_usuario_rechaza_campos_no_permitidos():
    with pytest.raises(ValueError):
        db.actualizar_usuario(3, {"username": "otro"}, admin())
