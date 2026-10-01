-- ============================================================
-- MIGRACIÓN: Día de pago del alquiler, por apartamento
-- Ejecuta esto en el SQL Editor de Supabase. Es aditiva: solo
-- agrega una columna nueva, no borra nada. Los campos
-- "Referencia - Parentesco" y "Notas" se quitaron solo del
-- formulario (la app ya no los muestra ni los edita), pero sus
-- columnas y datos existentes se conservan en la base de datos
-- por si los necesitas más adelante.
-- ============================================================

alter table apartamentos add column if not exists dia_pago int;

alter table apartamentos drop constraint if exists dia_pago_valido;
alter table apartamentos add constraint dia_pago_valido
    check (dia_pago is null or (dia_pago between 1 and 31));
