-- ============================================================
-- MIGRACIÓN: Soporte para reportes por usuario (cobrador)
-- Ejecuta esto en el SQL Editor de Supabase. Es aditiva: solo agrega
-- columnas nuevas, no borra ni modifica datos existentes.
--
-- Por qué: compras, ventas y pagos_generales ya guardan quién los
-- registró (columna "encargado"). Los pagos de alquiler, electricidad
-- y agua NO guardaban esa información, así que no era posible saber
-- qué cobrador registró cada abono. Esta migración agrega esa columna.
--
-- IMPORTANTE: los abonos registrados ANTES de correr esta migración
-- quedarán con registrado_por = NULL (no hay forma de reconstruir ese
-- dato retroactivamente). Los reportes por usuario solo podrán
-- incluir abonos de alquiler/electricidad/agua hechos de aquí en
-- adelante.
-- ============================================================

alter table pagos add column if not exists registrado_por text;
alter table pagos_electricidad add column if not exists registrado_por text;
alter table pagos_agua add column if not exists registrado_por text;
