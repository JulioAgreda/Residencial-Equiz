# EQUISE — V10: Rendición financiera consolidada (preparación de publicación)

## Base de aplicación utilizada
`app.py` se preparó tomando como base exacta `app(5).py`, que es la versión identificada en el historial del proyecto como última versión confirmada en Streamlit Cloud.
SHA-256 de la base: `05c23677872eba872775540d126dee8f8a22130f21c71e6e88d01b03b2b5267c`

Esto corrige un desajuste de versiones detectado en las entregas anteriores: la V9 se había construido desde otro `app.py` disponible, no desde la copia `app(5).py` identificada como desplegada. La V10 re-aplica solo las adiciones de rendición financiera sobre la base confirmada, sin incorporar otros cambios de interfaz o caché.

## Archivos del paquete
- `app.py` — reemplazo preparado, derivado de `app(5).py`; añade import del módulo financiero, acceso de Administrador al menú y página de rendición consolidada.
- `finanzas_consolidadas.py` — módulo nuevo de consolidación, resúmenes y exportación Excel.
- `rendicion.py` — añade `id_pago` e `id_periodo` para rastrear cobros a su pago y periodo original.
- `README_V10.md` — esta guía.
- `test_finanzas_consolidadas.py` y `test_acceso_rendicion_financiera.py` — pruebas de regresión.

`aire_acondicionado.py` no se incluye como reemplazo porque es un módulo existente del proyecto; el archivo original se usó en las pruebas. No reemplazarlo.

## Validación de la V10
En un directorio temporal que replica los módulos Python disponibles, se aplicó la V10 sobre la base `app(5).py` y se ejecutaron 13 scripts:
- `test_acceso_rendicion_financiera.py`
- `test_accesos.py`
- `test_conciliacion.py`
- `test_conciliacion_reportes.py`
- `test_cuadre.py`
- `test_devolucion.py`
- `test_dos_medidores.py`
- `test_exinquilinos.py`
- `test_extracto.py`
- `test_finanzas_consolidadas.py`
- `test_historial_solo_actual.py`
- `test_permiso_estado.py`
- `test_rendicion.py`

Resultado: 13/13 con código de salida 0. Los archivos Python de la copia pasaron la compilación sintáctica.

## Límite pendiente
No se pudo iniciar Streamlit ni validar una conexión en vivo a Supabase porque el entorno de trabajo no tiene instalados `streamlit`, `supabase` ni `bcrypt`, aunque están declarados en `requirements.txt`. El archivo `requirements.txt` del proyecto no se modifica.

## Publicación segura — no ejecutar sin autorización
Esta es una preparación, no una publicación. No se ha cambiado Streamlit Cloud ni Supabase.

Cuando el usuario autorice:
1. Descargar respaldo de `app.py` y `rendicion.py` actualmente desplegados.
2. Reemplazar `app.py` con el de este paquete.
3. Añadir `finanzas_consolidadas.py`.
4. Reemplazar `rendicion.py` con el incluido.
5. Mantener sin cambios `db.py`, `accesos.py`, `aire_acondicionado.py`, `requirements.txt`, los demás módulos y la base de datos.
6. Publicar y comprobar la vista desde la sesión de Administrador.
7. Si hay error, restaurar los dos archivos respaldados y retirar `finanzas_consolidadas.py`.

No ejecutar SQL ni modificar políticas, roles o datos de Supabase para esta mejora.
