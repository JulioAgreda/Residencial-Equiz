# Cambios sobre tu proyecto original

## Instalación
1. Reemplaza `app.py`, `db.py`, `recibo.py` y `reportes.py`; agrega `moras.py`, `compromisos.py`, `estados.py` y `consumo.py` (nuevos).
2. En el SQL Editor de Supabase ejecuta, una vez cada uno (ambos son seguros y repetibles):
   - `migracion_compromisos_pago.sql`: crea la tabla de compromisos de pago.
   - `migracion_estados_movimientos.sql`: agrega las columnas de estado a Compras, Pagos y Ventas.
   Si se despliega la app ANTES de ejecutarlos, nada se rompe: esas secciones muestran un aviso y funcionan
   sin el campo nuevo hasta que se ejecute el SQL. No hace falta cambiar `requirements.txt`.

## Qué incluye
- **Dashboard**: moras de alquiler, electricidad y agua en 3 cuadros.
- **🤝 Compromisos de pago** (menú principal, ambos roles): historial por apartamento del motivo de retraso
  que informa el inquilino, el compromiso asumido, la fecha plazo y el monto acordado, con estado
  (Pendiente / Cumplido / Incumplido; un Pendiente con plazo pasado se ve como Vencido).
  Todos los usuarios registran y editan; solo el Administrador elimina (con casilla de confirmación).
  Guarda quién registró y quién editó por última vez.
- **🗂️ Módulo Administración**: agrupa Pendientes y Reuniones (antes eran dos módulos separados).
- **📑 Módulo de Reportes**: Estado de cuenta (PDF/PNG para el inquilino) y Actividad por usuario (Excel/PDF).
- **🏠 Inquilinos** (cobradores): consulta de solo lectura de los datos de cada apartamento.

## Compras, Pagos y Ventas: sin adjunto + estado
- **Compras**: se quitó "Adjuntar comprobante" (ya no se suben archivos). El "N° de comprobante" (texto) se
  conserva. Los comprobantes ya subidos siguen accesibles con un enlace de solo lectura al editar la compra.
  **Pagos** ya no tenía adjunto.
- **Estado de devolución** (Compras y Pagos): No aplica / Pendiente de devolución / Se realizó devolución.
- **Estado de entrega** (Ventas): No aplica / Pendiente de entrega / Se realizó entrega.
- "No aplica" es el valor por defecto (y el de todos los registros que ya existían).
- En el historial de cada una: columna Estado, filtro por estado y el monto "Pendiente de devolución/entrega".
  El reporte de Actividad por usuario también incluye la columna Estado.
- Los archivos ya subidos siguen ocupando espacio en Supabase Storage (bucket `comprobantes`): quitar la opción
  evita que crezca, pero no libera lo ya subido. Eliminar una compra tampoco borra su archivo.

## Luz y agua: consumo y monto en números enteros
- El **consumo** (lectura actual − lectura anterior) se redondea al entero más cercano (34,5 → 35; 34,49 → 34).
- El **monto a cobrar** (consumo entero × tarifa) se redondea al **boliviano entero**: 59 Kwh × Bs 1,30 = 76,70 → **Bs 77**.
  El formulario muestra el paso: «Consumo: 59 Kwh × Bs 1.3000 = Bs 76.70 → **Bs 77.00** (redondeado al entero)».
- Las lecturas se guardan tal como se escriben; se guarda como deuda (`monto_esperado`) el monto entero.
- Se aplica al registrar o editar una lectura, y el consumo también en los historiales y el Top 5 del Dashboard.
- Redondeo normal (no el «del banquero» de Python, que redondea 2,5 a 2) y cuentas decimales exactas (con floats,
  758,56 − 461,06 da 297,4999… y se cobraría 1 unidad de menos). El monto se redondea desde el producto exacto,
  no en dos pasos (0,495 → 0, no 0,50 → 1).
- **Los periodos ya guardados NO se recalcularon** (conservan su monto, p. ej. 76,70). Para actualizar uno, abre
  ese apartamento/mes en Electricidad o Agua y pulsa «Guardar lectura» de nuevo: pasa a monto entero y los abonos
  ya registrados se conservan.

## Qué NO se tocó
Las páginas Apartamentos, Pagos de Alquiler, Usuarios, Pendientes y Reuniones son idénticas a tu original
(comparado bloque por bloque). Compras, Pagos, Ventas, Electricidad y Agua solo cambian en lo descrito arriba. En `db.py` y `recibo.py` solo se
añadieron funciones; ninguna existente se modificó.

## Reglas
- Compromisos: el motivo es obligatorio; si hay monto debe haber fecha plazo; el plazo no puede ser anterior
  a la fecha del registro. Se guarda el nombre del inquilino de ese momento (el inquilino puede cambiar).
- Actividad por usuario: solo Pagos, Compras y Ventas (los abonos de alquiler/electricidad/agua no guardan
  quién los cobró). Egresos = pagos + compras; Ingresos = ventas.
- Estado de cuenta (deuda real): solo inquilino actual de apartamentos "Ocupado", sin "Anticrético". Alquiler:
  meses con saldo cuyo día de pago ya pasó + meses sin ningún registro desde el primer mes registrado (o la
  fecha de ingreso) hasta hoy. Electricidad: toda factura con saldo. Hora de Bolivia (UTC-4).

## Pruebas (carpeta pruebas/)
`python test_moras.py` · `test_deuda_real.py` · `test_compromisos.py` · `test_estados.py` · `test_consumo.py` · `test_recorte.py` ·
`test_reportes.py` (`test_estados.py` necesita `migracion_estados_movimientos.sql` en la misma carpeta o una arriba;
`test_recorte.py` y `test_reportes.py` necesitan `recibo.py` con su logo y fuentes al lado).
