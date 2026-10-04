# Dashboard de moras + Módulo de Reportes + Inquilinos (solo lectura)

Basado en TUS archivos originales. Reemplaza `app.py`, `db.py`, `recibo.py` y `reportes.py`, y agrega
`moras.py` (nuevo). No hay que ejecutar SQL ni cambiar `requirements.txt`.

## Qué incluye
- **Dashboard**: moras de alquiler, electricidad y agua en 3 cuadros (Departamento, Inquilino, Meses
  atrasados, Deuda total).
- **📑 Módulo de Reportes** (menú propio, como Pendientes y Reuniones, para ambos roles):
  - *Estado de cuenta*: reporte PDF/PNG por apartamento para entregar al inquilino (deuda real).
  - *Actividad por usuario*: pagos, compras y ventas registrados por un usuario o el reporte general de
    todos, por rango de fechas, en Excel y PDF.
- **🏠 Inquilinos** (solo cobradores): consulta de solo lectura de los datos de cada apartamento. Los
  administradores siguen usando "🏠 Apartamentos" para editar.

## Archivos
- `db.py` y `recibo.py`: solo se AÑADEN funciones; ninguna existente se modificó.
- `reportes.py`: reescrito (ver abajo). Antes no estaba conectado a la app.
- `app.py`: cambios en menú, Dashboard y 3 páginas nuevas.

## Reglas y límites del reporte de actividad por usuario
- Solo se pueden atribuir a un usuario **Pagos, Compras y Ventas** (guardan el campo "Encargado").
  Los abonos de alquiler, electricidad y agua NO guardan quién los cobró, por eso no están.
- Egresos = pagos + compras; Ingresos = ventas. Se muestran por separado (antes se sumaban juntos).
- El usuario se identifica por el texto de "Encargado" con que se guardó cada registro. Si alguien
  cambia su nombre, sus registros viejos quedan bajo el nombre anterior. Los registros de usuarios
  que ya no existen aparecen con su nombre antiguo, y los que no tienen encargado en "(Sin encargado)",
  para que los totales siempre cuadren.
- Los textos que empiezan con = + - @ se guardan en el Excel como texto (no como fórmula).

## Reglas del estado de cuenta (deuda real)
Solo inquilino actual de apartamentos "Ocupado", sin contratos de "Anticrético". Alquiler: meses con saldo
cuyo día de pago ya pasó + meses sin ningún registro desde el primer mes registrado (o la fecha de
ingreso) hasta hoy. Electricidad: toda factura registrada con saldo. Hora de Bolivia (UTC-4).

## Pruebas (carpeta pruebas/)
`python test_moras.py` · `python test_deuda_real.py` · `python test_recorte.py` · `python test_reportes.py`
(las dos últimas necesitan `recibo.py` con su logo y fuentes al lado).
