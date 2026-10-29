# Residencial Equise — paquete depurado para pruebas

Esta carpeta es una copia de trabajo. No cambia el repositorio de GitHub ni Supabase.

## Contenido
- `app.py`: aplicación Streamlit principal seleccionada entre los dos archivos recibidos. `app(1).py` se excluyó como copia alternativa para evitar dos puntos de entrada.
- Módulos `.py`: dependencias locales importadas por la aplicación y sus reportes.
- `assets/`: logo y fuentes usadas por la generación de recibos.
- `test_*.py`: pruebas automatizadas recibidas.
- `migracion_*.sql`: migraciones incrementales de funciones existentes.
- `schema.sql`: esquema de referencia para una base nueva; **no ejecutarlo sobre la base de producción existente**.
- `verificar_historial_inquilinos.sql`: consulta de verificación, no modifica datos.

## Configuración local
1. Instalar dependencias: `pip install -r requirements.txt`.
2. Crear `.streamlit/secrets.toml` con `SUPABASE_URL`, `SUPABASE_KEY` y `APP_PASSWORD`. No subir ese archivo a GitHub ni compartir claves reales.
3. Ejecutar `streamlit run app.py`.
4. Ejecutar pruebas sin conectar a producción: `pytest -q`.

## Importante
El archivo `aire_acondicionado.py` se reconstruyó porque `app.py` y `rendicion.py` lo importan, pero no estaba entre los archivos recibidos. Validar su comportamiento antes de usar ese campo en producción. También se agregó a `recibo.py` la zona horaria de Bolivia que los reportes ya esperaban.

Antes de publicar esta copia, revisar todos los resultados de `pytest`, probar el inicio de sesión y validar reportes con datos de prueba. No ejecutar migraciones SQL sin confirmar primero el estado de la base de datos.
