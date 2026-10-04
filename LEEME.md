# Dashboard de moras + Reportes de estado de cuenta

Basado en TUS archivos originales. Copia estos 4 archivos junto a tu `app.py` actual (reemplazando
`app.py`, `db.py` y `recibo.py`; `moras.py` es nuevo). No hay que ejecutar ningún SQL ni cambiar
`requirements.txt`. Todo lo demás (otras páginas, `reportes.py`, `schema.sql`, fuentes, logo) queda igual.

## Qué cambia
- `app.py`: Dashboard con sección de moras (3 cuadros); nuevo módulo "📑 Reportes" para ambos roles.
  Se reemplaza el bloque "⚠️ Alertas": las alertas de contrato se conservan, la mora de alquiler
  vieja se sustituye por la nueva.
- `db.py`: solo se AÑADE `listar_periodos_abiertos()`. Ninguna función existente se modificó.
- `recibo.py`: solo se AÑADEN las funciones del reporte. Ninguna función existente se modificó.
- `moras.py` (nuevo): todo el cálculo de deuda, sin depender de Streamlit ni de la base.

## Reglas de cálculo
- Solo inquilino actual de apartamentos "Ocupado". El reporte excluye contratos de "Anticrético"
  (un tipo de contrato vacío se trata como alquiler).
- Alquiler (deuda real): meses con saldo cuyo día de pago ya pasó + meses SIN ningún registro entre el
  primer mes registrado (o la fecha de ingreso, si nunca hubo pagos) y hoy, valorados con el alquiler
  mensual de la ficha. Día de pago: campo "Día de Pago"; si no hay, el día de la fecha de ingreso; si
  tampoco, el 1. El mes en curso no es deuda hasta que pasa su día de pago (se muestra "Por vencer").
- Electricidad y agua: toda factura registrada con saldo pendiente.
- La fecha de "hoy" usa hora de Bolivia (UTC-4).

## Pruebas (carpeta pruebas/)
`python test_moras.py` · `python test_deuda_real.py` · `python test_recorte.py` (esta última necesita
`recibo.py` con su logo y fuentes al lado).
