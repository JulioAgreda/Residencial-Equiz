# Registro de depuración inicial — Residencial Equise

## Alcance de esta copia
Esta es una copia de trabajo creada a partir de los archivos recibidos. No se ha conectado a Supabase ni se han modificado datos de producción.

## Archivos organizados
- Se conserva `app.py` como punto de entrada principal porque contiene los módulos y funciones de la versión más amplia recibida.
- Se excluye `app(1).py` de esta copia para evitar dos posibles puntos de entrada. El archivo original no se elimina de la carpeta de origen.
- Se excluye `migracion_inventario(1).sql` por ser una copia duplicada por nombre; se conserva `migracion_inventario.sql`.
- Se agrupan los recursos visuales bajo `assets/` y `assets/fonts/`, tal como espera `recibo.py`.
- Se conservan las migraciones SQL y los scripts de pruebas recibidos.

## Ajustes para permitir la validación
- Se incorporó `aire_acondicionado.py`, ausente en los archivos recibidos pero importado por `app.py` y `rendicion.py`. Sus funciones son una implementación de compatibilidad y requieren validación funcional antes de producción.
- Se amplió `recibo.py` para incluir las funciones que el `app.py` principal invoca para recibos de electricidad/agua y estados de cuenta. Los formatos deben revisarse visualmente y contrastarse con datos reales anonimizados.
- Se agregó zona horaria `America/La_Paz` para la fecha local de Bolivia.

## Pruebas ejecutadas
Los 11 scripts `test_*.py` recibidos se ejecutaron individualmente y finalizaron correctamente en esta copia:
- accesos
- conciliación
- reportes de conciliación
- cuadre
- devoluciones
- dos medidores
- exinquilinos
- extracto
- historial de inquilinos
- permisos de estado
- rendición

Estas pruebas son pruebas locales basadas en sus propios datos; **no demuestran** que las credenciales, políticas de Supabase, estructura de producción, migraciones instaladas ni interfaz completa estén correctas.

## Antes de desplegar
1. Instalar dependencias con `pip install -r requirements.txt`.
2. Crear `.streamlit/secrets.toml` localmente con los valores correctos; nunca subirlo al repositorio.
3. Ejecutar `python run_tests.py`.
4. Probar la aplicación en un entorno de prueba, no contra producción al principio.
5. Confirmar las migraciones instaladas en Supabase antes de ejecutar cualquier SQL.
6. Verificar permisos/RLS en Supabase; el control de acceso en Streamlit no reemplaza políticas de base de datos.
7. Revisar visualmente PDF y PNG de recibos y estados de cuenta, especialmente el saldo mostrado en recibos antiguos.
