# Sistema de Control — Residencial "EQUIZ"

Aplicación web (Streamlit) con base de datos en la nube (Supabase) para gestionar
los apartamentos del residencial: datos de inquilinos, control de pagos de
alquiler y un dashboard general del edificio.

## 1. Crear el proyecto en Supabase (base de datos en la nube)

1. Entra a https://supabase.com y crea una cuenta (gratis) o inicia sesión.
2. Clic en **New Project**. Ponle un nombre, ej. `residencial-equiz`, elige una
   contraseña para la base de datos (guárdala) y la región más cercana.
3. Espera 1-2 minutos a que se cree el proyecto.
4. Ve a **SQL Editor** (menú lateral) → **New query**, pega todo el contenido
   del archivo `schema.sql` de este proyecto y ejecútalo (botón *Run*). Esto
   crea las tablas `apartamentos` y `pagos_alquiler`.
5. Ve a **Project Settings → API**. Copia:
   - **Project URL** → lo usarás como `SUPABASE_URL`
   - **anon public key** → lo usarás como `SUPABASE_KEY`

## 2. Configurar la aplicación

1. Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml`.
2. Completa `SUPABASE_URL`, `SUPABASE_KEY` y elige un `APP_PASSWORD` (la clave
   que usarán tú y tu personal para entrar a la app).

## 3. Ejecutar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Se abrirá en tu navegador (normalmente `http://localhost:8501`).

## 4. Publicar en internet (opcional, gratis)

1. Sube esta carpeta a un repositorio de GitHub.
2. Entra a https://share.streamlit.io con tu cuenta de GitHub.
3. Clic en **New app**, elige el repositorio y el archivo `app.py`.
4. En **Advanced settings → Secrets**, pega el contenido de tu
   `secrets.toml` (con tus datos reales).
5. Deploy. Obtendrás un link para acceder desde cualquier celular o
   computadora.

## 5. Importar los datos de tu Excel

Se incluye `apartamentos_plantilla.csv`, generado a partir de tu archivo
`Control_de_Edificio_30-12-2023.xlsx`, con los 20 apartamentos y los datos que
se pudieron extraer automáticamente (inquilino, alquiler mensual, garantía,
etc.).

**Importante:** el Excel original tiene datos escritos de forma poco uniforme
(fechas en texto, celdas combinadas, campos vacíos), así que **revisa y
corrige el CSV antes de importarlo** — ábrelo en Excel o Google Sheets y
verifica sobre todo: nombre del inquilino, monto de alquiler y estado
(Ocupado/Desocupado).

Para importar:
1. Abre la app → **Apartamentos** → pestaña **📥 Importar CSV**.
2. Sube el archivo `apartamentos_plantilla.csv` (ya corregido).
3. Revisa la vista previa y presiona **Importar estos apartamentos**.

## 6. Funcionalidades incluidas

- **Dashboard**: resumen general del edificio — unidades ocupadas/desocupadas,
  total esperado, total recaudado y deuda del mes seleccionado, estado de
  pago por apartamento, una sección de **⚠️ Alertas** con contratos
  vencidos o por vencer en los próximos 30 días y apartamentos en mora de
  alquiler (según el día del mes en que ingresó cada inquilino), una
  **gráfica de líneas del cobro de alquiler de los últimos 12 meses**, y un
  **ranking de los 5 apartamentos con mayor consumo de electricidad y agua**
  del mes seleccionado.
- **Apartamentos**: ver, editar, crear y eliminar apartamentos e inquilinos,
  incluyendo los datos del contrato (tipo, estado, fecha inicio/fin y
  observaciones).
- **Pagos de Alquiler**: para cada apartamento y mes puedes registrar varios
  abonos (pagos parciales) por separado — ej. Bs 200 el día 5 y Bs 300 el
  día 20 — y el sistema suma automáticamente cuánto se pagó y cuánto queda
  de deuda. Tú decides cuándo agregar cada mes, no es automático. Incluye
  historial filtrable por apartamento, año y mes, con el detalle de cada
  abono.
- **Electricidad**: registras la lectura del medidor (Kwh anterior y
  actual) y la tarifa por Kwh; el sistema calcula automáticamente el monto
  a pagar del mes. El Kwh anterior se precarga solo con el Kwh actual del
  último mes registrado. Igual que en alquiler, permite varios abonos
  parciales por mes y tiene su propio historial.
- **Agua**: funciona igual que Electricidad, pero con lectura del medidor
  de agua (m³) y su propia tarifa por m³.
- **Roles y permisos**: dos roles — **Administrador** (acceso total) y
  **Cobrador/Conserje** (puede registrar pagos/lecturas, ver el
  Dashboard, ver el Historial completo de todos los módulos y **editar**
  cualquier registro; solo el Administrador puede **eliminar** registros,
  editar apartamentos, o cambiar tarifas y montos esperados). El primer
  Administrador se crea desde la propia app la primera vez que entras.
  Desde **👥 Usuarios** (solo visible para Administradores) puedes crear más
  cuentas, cambiar roles, desactivar o eliminar usuarios.
- **📒 Módulo de Movimientos (Compras y Ventas)**: visualmente separado en
  el menú lateral (bajo su propio encabezado), pero dentro del mismo
  sistema y login.
  - **🧾 Compras (Gastos)**: fecha, categoría/rubro, descripción, monto,
    método de pago, proveedor, número de comprobante y un adjunto (foto o
    PDF de la factura, guardado en Supabase Storage). El campo "Encargado"
    se llena solo con el usuario que inició sesión, no se escribe a mano.
  - **💸 Ventas (Ingresos extraordinarios)**: fecha, concepto, descripción,
    monto, forma de cobro, comprador y número de recibo emitido. También
    registra automáticamente al usuario que la creó.
  - Ambos roles pueden registrar, ver el Historial completo y editar
    registros (incluido el adjunto del comprobante en compras); solo
    Administrador puede eliminarlos.

### Si ya habías creado las tablas antes (actualizaciones)

**Opción rápida:** si ya tienes el proyecto de Supabase funcionando con al
menos la tabla `apartamentos`, ejecuta un único script,
**`migracion_completa.sql`**, en el SQL Editor — incluye todo lo de abajo
en el orden correcto (pagos múltiples, electricidad, agua, contrato,
usuarios/roles, Compras y Ventas) y no borra tus apartamentos. Al final te
muestra una tabla de verificación de seguridad (RLS) que debe mostrar
`false` en todas las filas.

**Opción paso a paso** (si prefieres ir aplicando cada mejora por
separado, o ya corriste algunas de estas):

- Si tu base de datos ya tenía la tabla `pagos_alquiler` de una versión
  anterior de esta app, ejecuta `migracion_pagos_multiples.sql` en el SQL
  Editor de Supabase — reemplaza esa tabla por `periodos_alquiler` + `pagos`,
  que es lo que permite registrar varios abonos por mes. No afecta los datos
  de `apartamentos`.
- Para agregar el control de Electricidad a una base de datos que ya tienes
  funcionando, ejecuta `migracion_electricidad.sql` en el SQL Editor. Es
  aditivo: solo crea tablas nuevas, no toca nada de lo que ya existe.
- Para agregar el control de Agua, ejecuta `migracion_agua.sql` en el SQL
  Editor. También es aditivo (agrega una columna de tarifa a
  `configuracion` y crea las tablas `periodos_agua` y `pagos_agua`).
- Para agregar los datos de contrato a `apartamentos`, ejecuta
  `migracion_contrato.sql` en el SQL Editor. Solo agrega columnas nuevas.
- Para agregar roles y permisos, ejecuta `migracion_usuarios.sql` en el
  SQL Editor. Crea la tabla `usuarios`; no borra nada existente.
- Para agregar el módulo de Compras y Ventas, ejecuta
  `migracion_movimientos.sql` en el SQL Editor. Crea las tablas `compras`
  y `ventas`, y configura el bucket de almacenamiento `comprobantes` para
  los adjuntos.

Nota: `schema.sql` es distinto — solo se usa si algún día empiezas un
proyecto de Supabase **completamente nuevo** desde cero (incluye también
la creación de `apartamentos`). Para tu proyecto actual, usa
`migracion_completa.sql` o los pasos individuales de arriba, no `schema.sql`.

## 7. Backups diarios automáticos

Como Supabase en el plan gratuito no incluye backups automáticos, se
incluye un workflow de GitHub Actions (`.github/workflows/backup-diario.yml`)
que genera un respaldo completo de la base todos los días.

**Importante:** los backups contienen datos personales de tus inquilinos
(nombres, celular, cédula). Por eso deben guardarse en un repositorio
**privado**, nunca en el mismo repo público que uses para desplegar la app
en Streamlit Cloud. Pasos:

1. Crea un repositorio nuevo en GitHub, **privado**, solo para esto (ej.
   `residencial-equiz-backups`).
2. Sube ahí únicamente la carpeta `.github/workflows/backup-diario.yml`
   (no hace falta subir el resto del código).
3. En Supabase, ve a Project Settings → Database → Connection string →
   copia la URI y reemplaza `[YOUR-PASSWORD]` por la contraseña real de tu
   base de datos (la que pusiste al crear el proyecto; si no la recuerdas,
   puedes resetearla ahí mismo).
4. En ese repositorio de backups → Settings → Secrets and variables →
   Actions → New repository secret. Nombre: `SUPABASE_DB_URL`. Valor: la
   URI completa del paso anterior.
5. Ve a la pestaña "Actions" del repositorio, entra al workflow "Backup
   diario de la base de datos" y usa "Run workflow" para probarlo una vez
   manualmente. Si corre sin errores, revisa la carpeta `backups/` — debe
   aparecer un archivo `backup-AAAA-MM-DD.sql`.
6. A partir de ahí corre solo, todos los días, y borra automáticamente los
   respaldos de más de 30 días para no acumular espacio.

Para restaurar un backup en caso de emergencia, se usa `psql` con ese
mismo archivo `.sql` contra tu base de datos — avísame si llegas a
necesitarlo y te guío en el momento.
