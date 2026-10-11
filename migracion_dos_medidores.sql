-- ============================================================
-- Segundo medidor de energía eléctrica (apartamentos con 2 medidores)
-- Ejecutar UNA vez en el SQL Editor de Supabase. Es seguro y repetible: solo agrega dos columnas
-- y no modifica ni borra ningún dato existente.
--
-- Vacío (NULL) = el apartamento tiene un solo medidor, que sigue usando kwh_anterior / kwh_actual.
-- Los apartamentos con dos medidores guardan el segundo en estas columnas; monto_esperado es el total de ambos.
-- ============================================================
alter table periodos_electricidad add column if not exists kwh_anterior_2 numeric(10,2);
alter table periodos_electricidad add column if not exists kwh_actual_2 numeric(10,2);
