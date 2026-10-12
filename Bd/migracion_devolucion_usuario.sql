-- ============================================================
-- Estado de devolución más claro + a qué usuario se le devolvió el dinero
-- (Compras y Pagos)
--
-- Ejecutar UNA vez en el SQL Editor de Supabase, DESPUÉS de migracion_estados_movimientos.sql.
-- Es repetible y NO borra datos. Hace tres cosas, en cada una de las tablas `compras` y `pagos_generales`:
--   1. Cambia el texto del estado «Se realizó devolución» por
--      «Se realizó la devolución a la persona que realizó el pago» (también en los registros que ya existen).
--   2. Actualiza la validación (CHECK) de la columna estado_devolucion para aceptar el texto nuevo, y amplía la
--      columna a `text` para que el texto más largo quepa.
--   3. Agrega la columna `devolucion_a`: nombre del usuario al que se le devolvió el dinero.
--      Los registros que ya estaban en «Se realizó devolución» quedan con `devolucion_a` vacío; la app los muestra
--      como «(sin indicar)» hasta que se edite cada uno.
--
-- Los textos de abajo DEBEN coincidir con estados.py (hay una prueba que lo comprueba).
-- ============================================================
do $$
declare
    t text;
    r record;
begin
    foreach t in array array['compras', 'pagos_generales'] loop
        if not exists (select 1 from information_schema.columns
                       where table_schema = 'public' and table_name = t and column_name = 'estado_devolucion') then
            raise notice 'La tabla % no tiene estado_devolucion: ejecuta primero migracion_estados_movimientos.sql', t;
            continue;
        end if;

        -- 2a. quitar la validación anterior (no se conoce su nombre: se busca por lo que valida)
        for r in select c.conname from pg_constraint c
                 where c.conrelid = ('public.' || t)::regclass and c.contype = 'c'
                   and pg_get_constraintdef(c.oid) ilike '%estado_devolucion%'
        loop
            execute format('alter table public.%I drop constraint %I', t, r.conname);
        end loop;

        -- 2b. el texto nuevo es más largo
        execute format('alter table public.%I alter column estado_devolucion type text', t);

        -- 1. migrar el texto anterior de los registros existentes
        execute format('update public.%I set estado_devolucion = %L where estado_devolucion = %L',
                       t, 'Se realizó la devolución a la persona que realizó el pago', 'Se realizó devolución');

        -- 2c. nueva validación (NOT VALID: se aplica a lo que se guarde de ahora en adelante)
        execute format('alter table public.%I add constraint %I check (estado_devolucion in (%L, %L, %L)) not valid',
                       t, t || '_estado_devolucion_check',
                       'No aplica', 'Pendiente de devolución', 'Se realizó la devolución a la persona que realizó el pago');

        -- 3. a qué usuario se le devolvió el dinero
        execute format('alter table public.%I add column if not exists devolucion_a varchar(150)', t);
    end loop;
end $$;
