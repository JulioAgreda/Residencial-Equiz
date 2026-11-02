# EQUISE V15 – Garantías de alquiler

## Funcionalidad
- Registra garantías recibidas por inquilino y periodo de ocupación, separadas del alquiler y del anticrético.
- Sugiere como monto inicial un mes de alquiler; el administrador puede modificarlo.
- Guarda fecha, medio de recepción, comprobante y responsable.
- Al registrar la salida del inquilino, la garantía vigente pasa a "Pendiente de liquidación".
- Registra daños, cotización, monto aprobado para descuento, proveedor y referencia documental.
- Registra devoluciones parciales o totales con fecha, medio, comprobante y responsable.
- Calcula el saldo: monto recibido menos descuentos aprobados menos devoluciones efectuadas.
- Mantiene historial por garantía; no sobrescribe la garantía del siguiente inquilino.

## Archivos
- `app.py`
- `db.py`
- `schema_garantias_v15.sql`
- `README_V15.md`

## Instalación
1. Respaldar la aplicación y base de datos.
2. Ejecutar `schema_garantias_v15.sql` en Supabase.
3. Actualizar `app.py` y `db.py` en el repositorio de Streamlit.
4. Probar en entorno de validación antes de producción.

## Limitaciones y controles pendientes
- La interfaz permite registrar la garantía desde la pestaña "Garantías" después de crear el apartamento/registrar al inquilino. El importe sugerido equivale al alquiler mensual actual.
- Para un inquilino ya ocupado, se debe registrar su garantía histórica una sola vez. Verificar el comprobante antes de hacerlo.
- Los descuentos se calculan con el monto aprobado, que no puede superar la cotización ingresada. El usuario administrador debe revisar que la cotización y el daño estén documentados y que el daño no sea desgaste normal.
- La tabla conserva el historial por apartamento e inquilino; no elimina información previa.
- No se genera todavía un movimiento automático en Caja y Bancos. Se debe integrar posteriormente para no duplicar la recepción o devolución.
- La migración no establece políticas RLS nuevas, porque deben alinearse con el esquema de autenticación y permisos ya usado por la aplicación. Revisar permisos antes de exponer tablas mediante la API.
- No se ejecutó SQL ni se modificó producción.
- Validación realizada: análisis sintáctico Python. No se probó contra Supabase ni en navegador.
