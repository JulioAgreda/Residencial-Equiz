# Residencial Equise — V16.1: Garantía condicional por tipo de contrato

## Cambio incluido
- En edición de apartamentos, el campo **Garantía** se muestra únicamente cuando el tipo de contrato seleccionado es **Alquiler**.
- En creación de apartamentos, se aplica la misma condición.
- Al guardar un apartamento con tipo de contrato **Anticrético** (o sin tipo de contrato Alquiler), el campo `garantia` se envía como `NULL`.
- El selector de tipo de contrato permanece fuera del formulario para que Streamlit actualice la interfaz al cambiar la selección.

## Archivos
- `app.py`: aplicación actualizada.
- `db.py`: capa de base de datos de V16, sin cambios en esta corrección.
- `schema_garantias_v16.sql`: migración V16, sin cambios en esta corrección.
- `README_V16.md`: instrucciones originales de V16.

## Aplicación
Reemplazar el `app.py` de la versión V16 por el `app.py` incluido en este paquete. No es necesario ejecutar nuevamente el SQL de V16 por este ajuste de interfaz.

## Verificación realizada
- Compilación sintáctica de `app.py` con `py_compile`: correcta.
- Integridad del ZIP: verificada.
- No se ejecutó contra Supabase ni se desplegó a producción.
