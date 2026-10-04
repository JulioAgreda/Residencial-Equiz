# Revisión y optimización — Residencial EQUIZ

Fecha: 03/10/2026. Alcance: `app.py`, `db.py`, `recibo.py`, `reportes.py`, `schema.sql`,
`backup-diario.yml`, `requirements.txt`, README.

> **Qué NO pude hacer:** ejecutar la app contra Supabase ni abrirla en Streamlit (el entorno de
> revisión no tiene red ni Streamlit instalado). Verifiqué: compilación, que no falten funciones ni
> nombres (análisis AST), `db.py` con stubs (orden, paginación), los 4 generadores de PDF/PNG con el
> logo real, y la lógica de retención de backups. **Prueba la app en un entorno de staging o
> con una copia de la base antes de publicar.**

---

## 1. Cambios aplicados

### Rendimiento
| # | Problema encontrado | Cambio | Efecto |
|---|---|---|---|
| 1 | El gráfico "últimos 12 meses" del Dashboard hacía **12 consultas** a Supabase (una por mes), en cada carga. | `db.listar_cobros_por_anios()` + `cargar_cobros_12_meses()`: **1 consulta**, cacheada 2 min. | 12 viajes de red → 1 (y 0 si está en caché). |
| 2 | Streamlit vuelve a ejecutar todo el script en **cada clic** de un selector. Las pantallas de Pagos/Electricidad/Agua llamaban a la base directamente en cada ejecución (periodo, último periodo, tarifa, historiales). | Cargadores con `@st.cache_data` (TTL 20–120 s). Todas las escrituras ya llamaban a `limpiar_cache()`; agregué ese llamado al guardar tarifas (antes no hacía falta). | Cambiar mes/apartamento ya no consulta la base cada vez. |
| 3 | Los botones de recibo generaban **PDF + PNG de cada abono en cada ejecución**, aunque el expander estuviera cerrado. | `_recibo_pdf_cache` / `_recibo_png_cache` (10 min). | Con 5 abonos en pantalla: ~360 ms de CPU por interacción → ~0 (tras la 1.ª vez). |
| 4 | `reportlab` releía y decodificaba el logo de 190 KB en cada PDF. | Logo reducido (200 px) y cacheado; fuentes y logo PNG cacheados con `lru_cache`. | Par PDF+PNG: **73 ms → 48 ms** medido; PDF de ~160 KB a ~74 KB. |
| 5 | Supabase corta **silenciosamente en 1000 filas** por consulta. Con ~20 aptos × 12 meses, el historial "Todos" se cortaría en ~4 años. | `_traer_todo()` pagina automáticamente (periodos de alquiler/luz/agua, compras, pagos generales, ventas). Se añade orden por `id` para que la paginación sea estable. | Sin pérdida silenciosa de datos. |
| 6 | El login bajaba **toda la tabla `usuarios` (con hashes)** en cada dibujo de la pantalla, solo para saber si hay usuarios. | `db.hay_usuarios()` (1 columna, 1 fila). | Menos datos y menos exposición. |
| 7 | `import re`/`uuid`/`mimetypes` dentro de funciones llamadas por fila; `.index()` en lista para ordenar. | Imports arriba, regex compilada, diccionario de meses. | Mejora menor. |
| 8 | `schema`/consultas sin índices para filtros por fecha y por periodo activo. | `migracion_indices_rendimiento.sql` (solo crea índices; condicional según tablas existentes). | Mejora a medida que crezcan los datos. |

### Seguridad y robustez
- **Hash de contraseña fuera de la sesión**: `st.session_state["usuario"]` ya no guarda `password_hash`.
- **Freno a fuerza bruta**: 5 intentos fallidos → bloqueo de 60 s (login y clave general). *Es por sesión del navegador: frena lo casual, no reemplaza protección de servidor.*
- Clave general comparada con `hmac.compare_digest` (tiempo constante, soporta tildes/ñ).
- **Backup (`backup-diario.yml`)** — corregí fallos reales:
  - La limpieza `find -mtime +30` **nunca borraba nada** (tras `checkout` todos los archivos tienen fecha de hoy). Ahora borra por la fecha del nombre (probado).
  - Instala `pg_dump` 17 (el de Ubuntu suele fallar con "server version mismatch").
  - Exige la cadena **Session pooler** (la "Direct connection" de Supabase es solo IPv6 y GitHub Actions no tiene IPv6).
  - Respaldo comprimido `.sql.gz`, validación de tamaño mínimo, `pipefail`, `permissions: contents: write`, `concurrency` y `timeout`.
  - README actualizado (incluye cómo restaurar un `.gz`).
- `requirements.txt`: se declaran `Pillow` (lo usa `recibo.py`) y versiones mínimas.

### ⚠️ Un cambio de comportamiento (revísalo)
**La mora ahora respeta el campo "Día de Pago"** de la ficha del apartamento. Antes la ficha lo pedía pero el cálculo de mora lo ignoraba y usaba el día de `fecha_ingreso`. Si no hay "Día de Pago", se usa la fecha de ingreso como antes. Si prefieres el comportamiento anterior, borra el bloque `dia_fijo` en `calcular_mora_alquiler`.

---

## 2. Hallazgos que NO cambié (necesitan tu decisión)

1. **Seguridad de base de datos (el más importante).** Todas las tablas tienen RLS desactivado y la app usa la clave `anon`; el bucket `comprobantes` es público con políticas de insertar/borrar abiertas. Los roles Administrador/Cobrador **solo se aplican en la interfaz**: quien obtenga la URL y la clave `anon` puede leer y borrar todo (datos personales de inquilinos incluidos). Recomendación: usar la clave `service_role` solo en `st.secrets` (servidor), **activar RLS sin políticas** y hacer el bucket privado con URLs firmadas. Es un cambio de configuración + 2 líneas en `db.py`; puedo prepararlo.
2. **`schema.sql` está desactualizado respecto al código.** El código usa tablas/columnas que no están ahí: `pagos_generales`, `pendientes`, `servicios_basicos`, `reuniones`, `reuniones_participantes`, `inquilinos_historial`, la función RPC `registrar_salida_inquilino`, y columnas `dia_pago`, `inquilino_historial_id` y `inquilino_nombre` en periodos. Tampoco están en lo subido los `migracion_*.sql` ni `.streamlit/secrets.toml.example` que cita el README. Si tuvieras que reconstruir el proyecto, no podrías. Solución: `pg_dump --schema-only` y reemplazar `schema.sql`.
3. **Posible conflicto de unicidad.** `unique (apartamento_id, mes, anio)` en los periodos podría chocar cuando sale un inquilino y entra otro en el mismo mes (el periodo cerrado conserva ese mes). Verifica en tu base real cómo quedó la restricción.
4. **"Lectura anterior" puede precargarse mal.** `ultimo_periodo_electricidad/agua` ordena por año y fecha de *creación*, no por mes. Si cargas lecturas fuera de orden, el valor sugerido será el último *cargado*, no el último *mes*. Solución: guardar un `mes_num` numérico.
5. **Código muerto:** `reportes.py` (reportes por usuario) y las funciones de *estado de cuenta* de `recibo.py` no se usan en este `app.py`. ¿Es una versión anterior del app, o falta conectarlas?
6. **Mantenibilidad:** `app.py` tiene 2.470 líneas en un solo script; Electricidad y Agua son ~290 líneas casi idénticas cada una, y el formulario de edición de abonos está copiado en dos sitios. Conviene pasar a `st.navigation` (páginas en archivos separados; además elimina el truco de 4 radios con callbacks) y una función genérica de "consumo". No lo hice sin poder probar la interfaz.
7. Importar CSV inserta fila por fila (un viaje por apartamento); se puede hacer en un solo `insert`.
8. Cachés de 20–120 s: si dos cobradores trabajan a la vez, uno puede ver datos de hasta ese tiempo de atraso (las escrituras siempre consultan la base). Se puede bajar el TTL.
9. La sesión se pierde al recargar el navegador (hay que volver a entrar).
10. El archivo `_gitignore` debe llamarse `.gitignore` en el repositorio.

---

## 3. Archivos entregados
`app.py`, `db.py`, `recibo.py`, `requirements.txt`, `backup-diario.yml`, `README.md`,
`migracion_indices_rendimiento.sql` (nuevo), `REVISION.md`. El resto (`reportes.py`, `schema.sql`,
fuentes, logo) queda igual.
