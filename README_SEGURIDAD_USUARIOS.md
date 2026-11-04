# Residencial Equise — Etapa 2: protección de usuarios y asignaciones

## Cambios incluidos en esta copia de desarrollo

- Las operaciones de creación, modificación y desactivación de usuarios exigen un objeto de sesión individual con rol `Administrador`.
- La actualización limita los campos editables a `nombre`, `rol`, `activo` y `password_hash`.
- Se impide que el administrador actual se desactive o se retire su propio rol.
- Se impide desactivar o degradar al último administrador activo.
- La operación que antes eliminaba usuarios ahora desactiva la cuenta (`activo = false`) y conserva el registro histórico.
- La asignación de apartamentos exige administrador, valida que el usuario destino exista y no permite restringir administradores.
- La interfaz muestra “Desactivar usuario” en lugar de “Eliminar usuario”.
- Se conserva la consulta de perfiles sin `password_hash`; el hash se obtiene solamente en el flujo de autenticación.

## Archivos principales

- `app.py`: interfaz y llamadas actualizadas con `usuario_solicitante=usuario_actual`.
- `db.py`: controles en la capa de acceso a datos.
- `seguridad.py`: validación de sesión y rol.
- `test_seguridad_usuarios.py`: pruebas de rechazo de operaciones no autorizadas.

## Pruebas ejecutadas

Comando:

```bash
pytest -q test_seguridad.py test_seguridad_usuarios.py test_accesos.py
```

Resultado: **13 pruebas aprobadas**. También se compiló `app.py`, `db.py` y `seguridad.py` con `py_compile`.

Las pruebas de esta etapa validan autorización y reglas locales; no se conectan a Supabase ni prueban la aplicación completa.

## Límites y precauciones

- Esta es una copia de desarrollo; no se modificó Supabase ni producción.
- El cliente Supabase sigue usando la configuración actual. No se cambió `SUPABASE_KEY` ni se introdujo `service_role`.
- Esta etapa protege las funciones de gestión de usuarios y asignaciones llamadas por la aplicación, pero no resuelve por sí sola los permisos directos de Data API ni RLS.
- Antes de producción se debe auditar y proteger el resto de las operaciones de lectura/escritura y validar con una cuenta de pruebas en un entorno separado.
- La desactivación conserva el registro en `usuarios`; no es una eliminación física.
