-- ============================================================
-- Aire acondicionado en Apartamentos — Residencial EQUIZ
--   apartamentos.aire_acondicionado : verdadero = cuenta con aire acondicionado
--
-- Ejecutar completo en el SQL Editor de Supabase. Es SEGURO y repetible: solo AGREGA una columna
-- ("if not exists"); no borra ni modifica datos. Todos los apartamentos que ya existen quedan en
-- "No" (falso) hasta que se edite cada uno. En PostgreSQL 11 o superior agregar una columna con valor
-- por defecto constante es instantáneo (no reescribe la tabla).
-- ============================================================

alter table apartamentos add column if not exists aire_acondicionado boolean not null default false;

-- Verificación: debe aparecer la columna
select column_name, data_type, is_nullable, column_default
from information_schema.columns
where table_schema = 'public' and table_name = 'apartamentos' and column_name = 'aire_acondicionado';
