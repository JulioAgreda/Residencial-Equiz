"""Controles centrales de sesión y autorización para Residencial Equise.

Este módulo no sustituye la autorización en cada operación de base de datos.
Debe invocarse desde el backend antes de ejecutar lecturas o escrituras.
"""
from __future__ import annotations

from typing import Any, Iterable


class AccesoDenegado(PermissionError):
    """La sesión o el permiso solicitado no son válidos."""


def validar_usuario_sesion(usuario: dict | None) -> dict:
    if not isinstance(usuario, dict):
        raise AccesoDenegado("Se requiere una sesión individual válida.")
    if not usuario.get("id") or not usuario.get("username"):
        raise AccesoDenegado("La sesión no contiene una identidad válida.")
    if not usuario.get("activo", False):
        raise AccesoDenegado("La cuenta está desactivada.")
    if "password_hash" in usuario:
        raise AccesoDenegado("La sesión contiene datos de autenticación que no deben conservarse.")
    return usuario


def exigir_rol(usuario: dict | None, roles: str | Iterable[str]) -> dict:
    u = validar_usuario_sesion(usuario)
    permitidos = {roles} if isinstance(roles, str) else set(roles)
    if u.get("rol") not in permitidos:
        raise AccesoDenegado("No tiene autorización para realizar esta operación.")
    return u


def exigir_administrador(usuario: dict | None) -> dict:
    return exigir_rol(usuario, "Administrador")


def apartamento_autorizado(usuario: dict | None, apartamento_id: Any,
                            acceso_todos: bool, ids_asignados: Iterable[Any]) -> bool:
    u = validar_usuario_sesion(usuario)
    if u.get("rol") == "Administrador" or acceso_todos:
        return True
    return apartamento_id in set(ids_asignados or [])


def exigir_apartamento(usuario: dict | None, apartamento_id: Any,
                       acceso_todos: bool, ids_asignados: Iterable[Any]) -> None:
    if not apartamento_autorizado(usuario, apartamento_id, acceso_todos, ids_asignados):
        raise AccesoDenegado("No tiene acceso al apartamento solicitado.")
