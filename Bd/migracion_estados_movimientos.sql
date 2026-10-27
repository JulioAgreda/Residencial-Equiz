-- ============================================================
-- Estados en Compras, Pagos y Ventas — Residencial EQUIZ
--   compras.estado_devolucion        : No aplica / Pendiente de devolución / Se realizó devolución
--   pagos_generales.estado_devolucion: No aplica / Pendiente de devolución / Se realizó devolución
--   ventas.estado_entrega            : No aplica / Pendiente de entrega / Se realizó entrega
--
-- Ejecutar completo en el SQL Editor de Supabase. Es SEGURO y repetible: solo AGREGA columnas
-- ("if not exists"); no borra ni modifica datos. Todos los registros que ya existen quedan en
-- 'No aplica'. En PostgreSQL 11 o superior, agregar una columna con valor por defecto constante
-- es instantáneo (no reescribe la tabla).
-- ============================================================

alter table compras         add column if not exists estado_devolucion varchar(40) not null default 'No aplica';
alter table pagos_generales add column if not exists estado_devolucion varchar(40) not null default 'No aplica';
alter table ventas          add column if not exists estado_entrega    varchar(40) not null default 'No aplica';

-- Solo se aceptan los valores válidos (se crea una sola vez aunque el script se ejecute de nuevo)
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'ck_compras_estado_devolucion') then
        alter table compras add constraint ck_compras_estado_devolucion
            check (estado_devolucion in ('No aplica', 'Pendiente de devolución', 'Se realizó devolución'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'ck_pagos_generales_estado_devolucion') then
        alter table pagos_generales add constraint ck_pagos_generales_estado_devolucion
            check (estado_devolucion in ('No aplica', 'Pendiente de devolución', 'Se realizó devolución'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'ck_ventas_estado_entrega') then
        alter table ventas add constraint ck_ventas_estado_entrega
            check (estado_entrega in ('No aplica', 'Pendiente de entrega', 'Se realizó entrega'));
    end if;
end $$;

-- Verificación: deben aparecer las 3 columnas
select table_name, column_name, data_type, column_default
from information_schema.columns
where table_schema = 'public'
  and ((table_name in ('compras', 'pagos_generales') and column_name = 'estado_devolucion')
    or (table_name = 'ventas' and column_name = 'estado_entrega'))
order by table_name;
