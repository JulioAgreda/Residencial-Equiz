-- ============================================================
-- Índices de rendimiento — Residencial EQUIZ
-- Ejecutar completo en el SQL Editor de Supabase. Es SEGURO y repetible:
--   * solo crea índices ("if not exists"), no modifica ni borra datos;
--   * los que dependen de columnas/tablas que quizá tu base no tenga
--     se crean solo si existen.
-- ============================================================

-- Reportes y filtros por rango de fechas sobre los abonos (consultas "fecha >= x and fecha <= y")
create index if not exists idx_pagos_fecha on pagos (fecha);
create index if not exists idx_pagos_elec_fecha on pagos_electricidad (fecha);
create index if not exists idx_pagos_agua_fecha on pagos_agua (fecha);

-- Índices condicionales (según las tablas/columnas que existan en tu base)
do $$
begin
    -- Periodos "activos" vs "cerrados" (inquilino que ya salió): la app filtra por esta columna
    -- en cada pantalla de pagos, junto con apartamento/mes/año.
    if exists (select 1 from information_schema.columns
               where table_name = 'periodos_alquiler' and column_name = 'inquilino_historial_id') then
        create index if not exists idx_periodos_alq_hist on periodos_alquiler (inquilino_historial_id);
        create index if not exists idx_periodos_alq_busqueda
            on periodos_alquiler (apartamento_id, anio, mes) where inquilino_historial_id is null;
    end if;
    if exists (select 1 from information_schema.columns
               where table_name = 'periodos_electricidad' and column_name = 'inquilino_historial_id') then
        create index if not exists idx_periodos_elec_hist on periodos_electricidad (inquilino_historial_id);
        create index if not exists idx_periodos_elec_busqueda
            on periodos_electricidad (apartamento_id, anio, mes) where inquilino_historial_id is null;
    end if;
    if exists (select 1 from information_schema.columns
               where table_name = 'periodos_agua' and column_name = 'inquilino_historial_id') then
        create index if not exists idx_periodos_agua_hist on periodos_agua (inquilino_historial_id);
        create index if not exists idx_periodos_agua_busqueda
            on periodos_agua (apartamento_id, anio, mes) where inquilino_historial_id is null;
    end if;

    if to_regclass('public.pagos_generales') is not null then
        create index if not exists idx_pagos_generales_fecha on pagos_generales (fecha_pago);
    end if;
    if to_regclass('public.pendientes') is not null then
        create index if not exists idx_pendientes_estado on pendientes (estado, created_at desc);
    end if;
    if to_regclass('public.reuniones') is not null then
        create index if not exists idx_reuniones_fecha on reuniones (fecha);
    end if;
    if to_regclass('public.reuniones_participantes') is not null then
        create index if not exists idx_reuniones_part_reunion on reuniones_participantes (reunion_id);
    end if;
end $$;

-- Verificación: lista los índices creados por este script
select tablename, indexname from pg_indexes
where schemaname = 'public'
  and indexname in ('idx_pagos_fecha','idx_pagos_elec_fecha','idx_pagos_agua_fecha',
                    'idx_periodos_alq_hist','idx_periodos_alq_busqueda','idx_periodos_elec_hist',
                    'idx_periodos_elec_busqueda','idx_periodos_agua_hist','idx_periodos_agua_busqueda',
                    'idx_pagos_generales_fecha','idx_pendientes_estado','idx_reuniones_fecha',
                    'idx_reuniones_part_reunion')
order by tablename, indexname;
