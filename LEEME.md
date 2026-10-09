> ⚠️ **Lee `0_LEER_PRIMERO.txt` antes de instalar.** Instala todos los archivos juntos. El `app.py` que recibí era más viejo que tu
> aplicación en línea: la página **Servicios Básicos** la reconstruí (réplica, no tu código original) y tu versión podría
> tener otras pantallas que esta no tiene. Revisa tus menús antes de reemplazar; el cambio se puede revertir desde el
> historial de GitHub.

# Cambios sobre tu proyecto original

## Instalación
1. Reemplaza `app.py`, `db.py`, `recibo.py` y `reportes.py`; agrega `moras.py`, `compromisos.py`, `estados.py`, `consumo.py`, `servicios_basicos.py` y `aire_acondicionado.py` (nuevos).
2. En el SQL Editor de Supabase ejecuta, una vez cada uno (ambos son seguros y repetibles):
   - `migracion_compromisos_pago.sql`: crea la tabla de compromisos de pago.
   - `migracion_estados_movimientos.sql`: agrega las columnas de estado a Compras, Pagos y Ventas.
   - `migracion_aire_acondicionado.sql`: agrega la columna de aire acondicionado a Apartamentos.
   Si se despliega la app ANTES de ejecutarlos, nada se rompe: esas secciones muestran un aviso y funcionan
   sin el campo nuevo hasta que se ejecute el SQL. No hace falta cambiar `requirements.txt`.

## Qué incluye
- **Dashboard**: moras de alquiler, electricidad y agua en 3 cuadros.
- **🤝 Compromisos de pago** (menú principal, ambos roles): historial por apartamento del motivo de retraso
  que informa el inquilino, el compromiso asumido, la fecha plazo y el monto acordado, con estado
  (Pendiente / Cumplido / Incumplido; un Pendiente con plazo pasado se ve como Vencido).
  Todos los usuarios registran y editan; solo el Administrador elimina (con casilla de confirmación).
  Guarda quién registró y quién editó por última vez.
- **🗂️ Módulo Administración**: agrupa Pendientes, **Servicios Básicos** (reconstruido) y Reuniones (antes eran módulos separados).
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

## Recibos de pago de electricidad y agua
- Cada abono de **Electricidad** y de **Agua** tiene ahora botones «Descargar recibo (PDF / PNG)», en el registro y
  en el historial, igual que los de alquiler: mismo diseño, con las lecturas del medidor entre los datos del pago
  (lectura anterior, lectura actual, consumo y tarifa).
- Numeración propia para que no se repita entre servicios: alquiler `REC-000012`, luz `REC-L-000012`, agua `REC-A-000012`.
- Si el monto guardado de un periodo no corresponde a consumo × tarifa (periodos guardados antes de redondear el
  cobro a entero), el recibo imprime solo las lecturas y no el consumo ni la tarifa, para no mostrar números que no
  cuadran. Se corrige volviendo a guardar la lectura.
- El recibo de alquiler no cambió (comparado píxel a píxel con la versión anterior).

## Periodos con mes ilegible
- El mes de un periodo se lee con tolerancia (mayúsculas, espacios, «Setiembre»). Si algún periodo tiene un mes o año
  que no se puede leer, el Dashboard y el Estado de cuenta muestran un aviso: sus pagos y deudas no entran en el
  cálculo hasta que se corrija el dato en Supabase. Antes se omitían sin avisar.

## Aire acondicionado en Apartamentos
- Dato por apartamento: **❄️ Cuenta con aire acondicionado** (Sí/No) y, si lo tiene, **¿de quién es?**:
  *Del edificio (activo propio)* o *Del inquilino (se lo lleva al retirarse)*. Se registra al **crear** y al **editar** un
  apartamento; si marcas que tiene aire, es obligatorio indicar de quién es. Si se desmarca el aire, la propiedad se limpia sola.
- Se ve (solo lectura) en la página «Inquilinos»: «Sí — del edificio (activo propio)», «Sí — del inquilino (se lo lleva al
  retirarse)», «Sí — falta indicar de quién es» o «No». La importación CSV acepta las columnas opcionales
  `aire_acondicionado` (Sí / No) y `aire_acondicionado_propiedad` (Del edificio / Del inquilino).
- **Ejecuta `migracion_aire_acondicionado.sql`** (si ya ejecutaste una versión anterior, vuelve a ejecutarlo completo: es repetible).
- Los apartamentos que ya existen quedan en **No**; los que ya marcaste con aire antes de esta versión aparecerán como
  «falta indicar de quién es» hasta que los edites.
- Si la app se instala antes del SQL, la página muestra un aviso y crear/editar/importar funcionan como antes.

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
`python test_moras.py` · `test_deuda_real.py` · `test_compromisos.py` · `test_estados.py` · `test_consumo.py` · `test_servicios_basicos.py` · `test_recibo_servicios.py` · `test_recorte.py` ·
`test_reportes.py` (`test_estados.py` necesita `migracion_estados_movimientos.sql` en la misma carpeta o una arriba;
`test_recorte.py` y `test_reportes.py` necesitan `recibo.py` con su logo y fuentes al lado).
