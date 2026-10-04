# Cambios sobre tu proyecto original

## Instalación
1. Reemplaza `app.py`, `db.py`, `recibo.py` y `reportes.py`; agrega `moras.py` y `compromisos.py` (nuevos).
2. **Ejecuta una vez `migracion_compromisos_pago.sql`** en el SQL Editor de Supabase (solo crea una tabla
   nueva; no toca nada existente). Sin esto, la sección "Compromisos de pago" muestra un aviso y el resto
   de la app funciona normal. No hace falta cambiar `requirements.txt`.

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

## Qué NO se tocó
Las páginas Apartamentos, Pagos de Alquiler, Electricidad, Agua, Usuarios, Compras, Pagos, Ventas, Pendientes
y Reuniones son idénticas a tu original (comparado bloque por bloque). En `db.py` y `recibo.py` solo se
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
`python test_moras.py` · `test_deuda_real.py` · `test_compromisos.py` · `test_recorte.py` · `test_reportes.py`
(las dos últimas necesitan `recibo.py` con su logo y fuentes al lado).
