# Actualización del generador de documentos Equise

Incluye `recibo.py` y los recursos gráficos utilizados.

## Cambios
- Diseño de recibos coherente con la maqueta aprobada: alquiler (azul marino/dorado), electricidad (verde) y agua (azul).
- PDF y PNG comparten la misma composición visual.
- Logo horizontal de alta resolución en la cabecera y del Estado de Cuenta.
- El apartamento se muestra sin prefijos internos como `TP-` ni la palabra `APARTAMENTO` (por ejemplo: `5 - Tercer Piso`).
- El apartamento 2 puede mostrar dos medidores eléctricos; los demás muestran uno.
- El pie de recibos muestra el nombre de la persona emisora.
- Estado de cuenta compacto, con detalle mensual de alquiler/electricidad, saldos y nombre de quien lo emite; se omite la sección redundante de últimos pagos.
- Fechas de emisión con zona horaria de Bolivia.

Reemplaza el archivo `recibo.py` y sube la carpeta `assets/` incluida. No requiere migración SQL. Prueba primero con datos reales revisando importes y lecturas antes de darlo por aprobado.
