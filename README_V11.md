# Residencial Equise – Preparación V11: Cuentas por pagar y por cobrar

## Alcance
Se preparan las reglas de cálculo y el modelo de datos para:
- Obligaciones: préstamos bancarios y particulares recibidos, proveedores,
  obligaciones con propietarios/socios y servicios pendientes.
- Cuentas por cobrar: préstamos a particulares, anticipos a empleados,
  préstamos a propietarios/socios y ventas/servicios a crédito.
- Sin intereses en esta primera versión, según definición del usuario.

## Archivos
- `deudas.py`: validaciones y cálculo puro de obligaciones.
- `deudores.py`: validaciones y cálculo puro de cuentas por cobrar.
- `schema_finanzas_v11.sql`: propuesta de tablas nueva; no ejecutada.
- `test_finanzas_v11.py`: pruebas unitarias locales.
- `README_V11.md`: estas instrucciones.

## Criterio de saldo inicial
Para migrar saldos existentes, cada ficha conserva `monto_original`, `fecha_corte`
y `saldo_apertura`. El saldo inicial es el pendiente real a la fecha de corte.
No se deben recrear desembolsos históricos como entradas del período actual.

## Criterios contables
- Préstamo recibido: aumenta caja/banco y pasivo; no es ingreso operativo.
- Capital pagado: disminuye caja/banco y pasivo; no es gasto operativo.
- Préstamo otorgado: aumenta cuenta por cobrar y disminuye caja/banco; no es gasto.
- Cobro de capital: aumenta caja/banco y disminuye cuenta por cobrar; no es ingreso
  operativo nuevo si el derecho ya estaba reconocido.
- Aportes de socios sin obligación de devolución no se registran como deuda.
- Intereses no están habilitados en V11 inicial.
- Un pago/cobro debe originar un solo movimiento de caja/banco. La integración
  transaccional con caja/bancos se debe implementar antes de usar en producción.

## Seguridad y publicación
Este paquete es preparación local. No ejecutar el SQL ni subir estos módulos
a producción todavía. Antes de publicar falta:
1. Revisar y aprobar el esquema SQL y estrategia de permisos.
2. Integrar funciones CRUD en `db.py`.
3. Integrar formularios y reportes en `app.py`.
4. Enlazar cada pago/cobro a caja/bancos sin duplicidad.
5. Añadir auditoría y pruebas de permisos.
6. Probar con copia de datos y validar saldos contra documentos fuente.

No se modificó Supabase, producción, `db.py`, `app.py` ni tablas existentes.
