# Residencial Equise – Protección de apartamentos (desarrollo)

## Alcance
Esta carpeta contiene copias de desarrollo de `app(9).py` y `db(1).py`, renombradas
como `app.py` y `db.py`. No modifica el despliegue ni la base de datos de Supabase.

## Cambios incluidos
1. Se retiró de la interfaz el botón de eliminación física de apartamentos.
2. `db.eliminar_apartamento()` ahora rechaza cualquier intento de borrado físico.
3. `db.actualizar_apartamento()` impide cambiar el estado de ocupación o sustituir/
   borrar el nombre del inquilino desde la edición general.
4. La edición general muestra el estado y el inquilino como campos de solo lectura.
5. `db.crear_apartamento()` valida coherencia básica entre estado e inquilino:
   - Ocupado requiere nombre de inquilino.
   - Desocupado no admite nombre de inquilino activo.

## Importante
- No se agregó todavía la baja lógica: la tabla `apartamentos` no tiene los campos
  `activo`, `fecha_baja`, `baja_motivo` ni `baja_usuario_id`.
- No se ejecutó SQL ni se modificó Supabase.
- El flujo de salida existente `registrar_salida_inquilino()` se conserva.
- Antes de producción se debe revisar también el formulario de creación/importación
  CSV y las demás rutas que puedan modificar ocupación o inquilinos.
- La protección de Python no reemplaza restricciones/RPC en PostgreSQL. Un acceso
  directo a la API con credenciales privilegiadas podría eludirla.
- No desplegar estos archivos hasta completar las pruebas funcionales y la
  protección de base de datos.

## Pruebas mínimas antes de desplegar
1. Abrir la lista y edición de apartamentos; comprobar que no existe botón Eliminar.
2. Editar teléfono, referencias y datos contractuales; comprobar que guarda.
3. Intentar cambiar estado o nombre mediante llamada directa a
   `actualizar_apartamento()`; debe rechazarlo.
4. Intentar llamar `eliminar_apartamento()`; debe rechazarlo sin enviar DELETE.
5. Registrar una salida desde la pestaña Salida de inquilino; verificar historial,
   deudas y garantías.
6. Crear un apartamento ocupado sin inquilino; debe rechazarse.
7. Crear un apartamento desocupado con inquilino; debe rechazarse.
8. Probar importación CSV y revisar que no permita sobrescribir estados/ocupantes
   sin pasar por un flujo controlado.
