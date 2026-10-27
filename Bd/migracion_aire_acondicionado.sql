-- ============================================================
-- Aire acondicionado en Apartamentos — Residencial EQUIZ
--   apartamentos.aire_acondicionado           : verdadero = cuenta con aire acondicionado
--   apartamentos.aire_acondicionado_propiedad : 'Del edificio' (activo propio) o 'Del inquilino'
--                                               (lo compró por su cuenta y se lo lleva al retirarse);
--                                               vacío si no tiene aire o aún no se definió.
--
-- Ejecutar completo en el SQL Editor de Supabase. Es SEGURO y REPETIBLE: si ya ejecutaste una versión anterior
-- de este archivo, vuelve a ejecutarlo completo (solo agrega lo que falte). Solo AGREGA columnas
-- ("if not exists"); no borra ni modifica datos. Los apartamentos que ya existen quedan en "No" y sin propiedad.
-- En PostgreSQL 11 o superior agregar una columna con valor por defecto constante es instantáneo.
-- ============================================================

alter table apartamentos add column if not exists aire_acondicionado boolean not null default false;
alter table apartamentos add column if not exists aire_acondicionado_propiedad varchar(20);

-- Solo se aceptan valores válidos, y la propiedad solo puede existir si el apartamento tiene aire
-- (se crean una sola vez aunque el script se ejecute de nuevo)
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'ck_apartamentos_aire_propiedad_valor') then
        alter table apartamentos add constraint ck_apartamentos_aire_propiedad_valor
            check (aire_acondicionado_propiedad is null or aire_acondicionado_propiedad in ('Del edificio', 'Del inquilino'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'ck_apartamentos_aire_propiedad_con_aire') then
        alter table apartamentos add constraint ck_apartamentos_aire_propiedad_con_aire
            check (aire_acondicionado_propiedad is null or aire_acondicionado);
    end if;
end $$;

-- Verificación: deben aparecer las dos columnas
select column_name, data_type, is_nullable, column_default
from information_schema.columns
where table_schema = 'public' and table_name = 'apartamentos'
  and column_name in ('aire_acondicionado', 'aire_acondicionado_propiedad')
order by column_name;
