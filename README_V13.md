# Residencial Equise — V13 Control financiero simplificado

## Estructura funcional
1. **Ingresos por ventas**: muebles, equipos, copias de llave y otros ingresos.
2. **Egresos**: un solo formulario con tipo Compra (artículos de limpieza, repuestos, herramientas, dispositivos) o Gasto/Pago (electricidad, agua, internet, honorarios, impuestos).
3. **Préstamos**: préstamos recibidos y realizados, sin intereses; admite devoluciones/cobros parciales vinculados al préstamo.

## Archivos
- `app.py`: interfaz Streamlit con Egresos unificados y Préstamos.
- `db.py`: acceso Supabase heredado de V12; conserva tablas y funciones actuales.
- `deudas.py`, `deudores.py`: validación y cálculo de saldos.
- `schema_finanzas_v13.sql`: migración para las tablas auxiliares de préstamos con categorías limitadas. Verificar antes de ejecutar.

## Decisiones de seguridad y conservación
- No se eliminan tablas `compras`, `pagos_generales` ni `ventas`. El formulario único de Egresos escribe en la tabla histórica correspondiente para no romper reportes existentes.
- Los módulos antiguos Compras y Pagos dejan de estar en la navegación, pero su código y registros históricos se conservan para reversión y compatibilidad.
- No se ejecuta SQL ni se modifica producción con este paquete.
- El módulo de préstamos requiere las cuatro tablas de la migración V13. Si ya existen, no volver a ejecutar el SQL.

## Limitaciones que deben resolverse en la siguiente fase
- El formulario V13 registra egresos pagados al momento. No gestiona compras a crédito ni cuentas por pagar de proveedores.
- Los préstamos se registran en tablas auxiliares, pero V13 todavía no crea automáticamente movimientos en caja/bancos. Por tanto, no se debe considerar el saldo bancario como integrado ni duplicar manualmente los pagos/cobros en otro módulo sin una conciliación definida.
- El historial unificado de egresos consulta las tablas históricas `compras` y `pagos_generales`; no migra ni duplica datos.
- Antes de desplegar: probar en copia/staging con datos anonimizados, confirmar esquema real de `pagos_generales`, permisos RLS y reportes/cuadre.

## Instalación local
Reemplazar los archivos Python correspondientes en una copia del proyecto. No subir a producción hasta aprobar la validación y la migración correspondiente.
