# EQUISE V14 – Control de contratos de anticrético

## Qué incorpora
- Campo de capital anticrético entregado, independiente del alquiler mensual.
- Moneda del capital: BOB o USD.
- Fecha de entrega del capital.
- Fecha pactada para la devolución, según el contrato firmado.
- Condiciones pactadas de devolución.
- Historial de devoluciones parciales o totales, con fecha, monto, medio, comprobante y usuario.
- Cálculo del capital devuelto y saldo pendiente.
- Aviso cuando la fecha pactada está próxima o vencida.
- En la ficha del apartamento, los datos de anticrético se muestran en lugar de los datos de alquiler.
- El formulario oculta los campos de alquiler cuando se selecciona Anticrético.

## Archivos
- `app.py`: interfaz de alta, edición, consulta y registro de devoluciones.
- `db.py`: consultas y registro del historial de devoluciones.
- `schema_anticreticos_v14.sql`: migración aditiva para Supabase.
- `README_V14.md`: estas instrucciones.

## Orden de instalación
1. Respaldar los archivos actuales de la aplicación.
2. En Supabase SQL Editor, ejecutar únicamente `schema_anticreticos_v14.sql`.
3. Confirmar que se agregaron las columnas y la tabla `devoluciones_anticretico`.
4. Reemplazar `app.py` y `db.py` en el repositorio de Streamlit.
5. Reiniciar y probar primero en un entorno de validación.

## Consideraciones
- La migración agrega columnas y una tabla; no elimina tablas ni registros históricos.
- El importe del anticrético se conserva en la moneda indicada. No se convierte entre BOB y USD.
- Las devoluciones se registran como historial de capital devuelto y nunca se mezclan con cobros de alquiler.
- El sistema calcula el saldo como capital original menos devoluciones registradas.
- El aviso de vencimiento utiliza la fecha pactada registrada. Debe coincidir con el contrato y sus modificaciones firmadas.
- El sistema no sustituye ni modifica el contrato jurídico, no interpreta cláusulas ambiguas y no determina por sí mismo la exigibilidad. Se debe registrar fielmente lo acordado en el documento firmado.
- Este módulo registra las devoluciones en su historial, pero todavía no genera automáticamente el movimiento correspondiente en Caja y Bancos. Esa integración debe realizarse en una fase posterior para evitar duplicaciones.
- No se ejecutó la migración en Supabase ni se modificó producción.
- Validación realizada: análisis sintáctico de Python. No se probó contra la base real ni en el navegador.
