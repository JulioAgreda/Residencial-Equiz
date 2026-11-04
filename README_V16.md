# EQUISE V16 – Garantías de alquiler y tesorería

## Objetivo
Registrar las garantías de alquiler como depósitos reembolsables, separados de ingresos por alquiler y gastos operativos. La recepción y devolución del dinero generan movimientos de tesorería vinculados a la operación original.

## Qué incorpora
- Mantiene la interfaz de garantías de V15.
- Al recibir una garantía, crea en una sola transacción SQL:
  1. El registro de garantía.
  2. Una entrada en `movimientos_tesoreria` con categoría `GARANTIA_ALQUILER`.
- Al devolver una parte o la totalidad, crea en una sola transacción SQL:
  1. El registro de devolución.
  2. Una salida en `movimientos_tesoreria` con categoría `DEVOLUCION_GARANTIA_ALQUILER`.
- Los RPC validan que la devolución no supere el capital menos descuentos aprobados y devoluciones previas.
- La tabla de tesorería evita duplicar el origen mediante una restricción única (`origen_tipo`, `origen_id`).
- Muestra dentro de Garantías las entradas y salidas vinculadas a estos depósitos.
- Mantiene las garantías, daños, cotizaciones y devoluciones por cada registro de ocupación.
- Permite cerrar una garantía sin devolución cuando el monto completo se retiene por daños aprobados documentados.
- Al registrar salida de inquilino, después de guardar correctamente la salida, la garantía vigente pasa a liquidación pendiente.

## Archivos
- `app.py`: interfaz.
- `db.py`: consultas y llamadas RPC.
- `schema_garantias_v16.sql`: migración SQL.
- `README_V16.md`: instrucciones.

## Orden de instalación
1. Hacer respaldo de la aplicación y la base de datos.
2. Confirmar que V15 ya está aplicada (tablas `garantias_alquiler`, `danos_garantia_alquiler`, `devoluciones_garantia_alquiler`).
3. Ejecutar `schema_garantias_v16.sql` en Supabase SQL Editor.
4. Actualizar `app.py` y `db.py` en el repositorio Streamlit.
5. Reiniciar la aplicación.
6. Validar con una garantía de prueba y una devolución parcial en entorno de prueba antes de usar datos reales.

## Alcance de la integración de tesorería
- `movimientos_tesoreria` es un libro auxiliar de movimientos de efectivo/banco para las operaciones de garantía.
- La recepción se registra como ENTRADA y la devolución como SALIDA.
- Ninguna de las dos se clasifica como ingreso operativo o gasto operativo.
- Los descuentos por daños no generan una entrada o salida de efectivo por sí mismos; son una aplicación/retención del depósito. El gasto de reparación, si se realiza, debe registrarse por separado con su comprobante.
- Esta versión NO integra todavía los movimientos de garantía en los reportes existentes de conciliación bancaria ni en los módulos históricos de caja/bancos. Es un auxiliar separado, preparado para una posterior consolidación con el libro único de tesorería.
- No se registran aquí depósitos bancarios ni cuentas bancarias específicas; se guarda el medio de recepción/devolución informado.

## Seguridad
- Las funciones RPC se ejecutan con `SECURITY DEFINER`, `search_path` fijo y permisos de ejecución concedidos a `anon` y `authenticated`, necesarios por el cliente actual de la aplicación.
- Se revocan permisos directos de `anon` y `authenticated` sobre `movimientos_tesoreria`; la consulta se realiza mediante una función RPC de lectura limitada a garantías.
- Revisar el modelo de autenticación y RLS global de Supabase antes de producción. La aplicación actual usa la clave anon, por lo que las políticas y permisos de todo el esquema deben revisarse integralmente.

## Validaciones realizadas
- Análisis sintáctico de `app.py` y `db.py`: correcto.
- ZIP verificado.
- No se ejecutó el SQL en Supabase.
- No se probó contra la base real ni en navegador.
- No se modificó producción.

## Importante
La migración V16 debe ejecutarse después de V15. No ejecutar V16 en una base donde V15 no esté aplicada. La migración agrega objetos y restricciones; no borra registros existentes.
