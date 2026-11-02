# Residencial Equise — V13.1 Control financiero simplificado

## Navegación corregida
- El menú lateral conserva un único acceso: **Finanzas**.
- Se eliminó el bloque lateral duplicado **Operaciones financieras** y su radio independiente de Egresos/Ventas.
- Al entrar en Finanzas, la navegación de contenido ofrece tres opciones: **Préstamos**, **Egresos** e **Ingresos**.
- Las opciones internas reutilizan las pantallas existentes: Préstamos abre el módulo financiero, Egresos abre el formulario unificado y Ingresos abre Ventas.

## Estructura funcional
1. **Ingresos por ventas**: muebles, equipos, copias de llave y otros ingresos.
2. **Egresos**: un solo formulario con tipo Compra (artículos de limpieza, repuestos, herramientas, dispositivos) o Gasto/Pago (electricidad, agua, internet, honorarios, impuestos).
3. **Préstamos**: préstamos recibidos y realizados, sin intereses; admite devoluciones/cobros parciales vinculados al préstamo.

## Archivos
- `app.py`: interfaz Streamlit con navegación financiera integrada.
- `db.py`: acceso Supabase heredado de V12; conserva tablas y funciones actuales.
- `deudas.py`, `deudores.py`: validación y cálculo de saldos.
- `schema_finanzas_v13.sql`: migración para las tablas auxiliares de préstamos. No hubo cambios SQL en esta corrección de interfaz.

## Conservación de datos
- No se eliminan tablas `compras`, `pagos_generales` ni `ventas`.
- Se conserva el código de compatibilidad y los reportes históricos; únicamente se retira la navegación duplicada.
- No se elimina información ni se ejecuta SQL.
- No se modifica producción ni Supabase.

## Validación realizada
- `app.py`, `db.py`, `deudas.py` y `deudores.py` compilan con `py_compile`.
- Se verificó estáticamente que ya no existe el radio lateral `nav_movimientos` ni la leyenda lateral `📒 Operaciones financieras`.
- No se ha realizado una prueba de ejecución real en Streamlit ni conexión a Supabase.

## Limitaciones pendientes
- El formulario de egresos registra operaciones pagadas al momento; no gestiona compras a crédito ni cuentas por pagar de proveedores.
- Los préstamos todavía no crean automáticamente movimientos en caja/bancos.
- Antes de desplegar: probar en copia/staging, confirmar el esquema real de `pagos_generales`, revisar RLS y validar reportes/cuadres.

## Instalación
Reemplazar archivos únicamente en una copia del proyecto y probar. No subir a producción hasta aprobar la validación integral y la migración correspondiente.
