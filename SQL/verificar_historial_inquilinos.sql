-- ============================================================
-- VERIFICACIÓN (solo lectura) del historial de inquilinos
-- Ejecútalo en el SQL Editor de Supabase. NO modifica nada: solo consulta.
--
-- La app usa estas piezas de la base de datos para archivar a un inquilino que se va y para registrar los pagos
-- de los ex inquilinos. La primera consulta debe mostrar `true` en todas las filas.
-- ============================================================
select elemento, existe from (
    select 1 as orden, 'tabla inquilinos_historial' as elemento,
           to_regclass('public.inquilinos_historial') is not null as existe
    union all select 2, 'columna inquilinos_historial.apartamento_id',
           exists (select 1 from information_schema.columns where table_schema = 'public'
                   and table_name = 'inquilinos_historial' and column_name = 'apartamento_id')
    union all select 3, 'columna inquilinos_historial.fecha_salida',
           exists (select 1 from information_schema.columns where table_schema = 'public'
                   and table_name = 'inquilinos_historial' and column_name = 'fecha_salida')
    union all select 4, 'columna inquilinos_historial.inquilino_nombre',
           exists (select 1 from information_schema.columns where table_schema = 'public'
                   and table_name = 'inquilinos_historial' and column_name = 'inquilino_nombre')
    union all select 5, 'columna periodos_alquiler.inquilino_historial_id',
           exists (select 1 from information_schema.columns where table_schema = 'public'
                   and table_name = 'periodos_alquiler' and column_name = 'inquilino_historial_id')
    union all select 6, 'columna periodos_electricidad.inquilino_historial_id',
           exists (select 1 from information_schema.columns where table_schema = 'public'
                   and table_name = 'periodos_electricidad' and column_name = 'inquilino_historial_id')
    union all select 7, 'columna periodos_agua.inquilino_historial_id',
           exists (select 1 from information_schema.columns where table_schema = 'public'
                   and table_name = 'periodos_agua' and column_name = 'inquilino_historial_id')
    union all select 8, 'función registrar_salida_inquilino(apartamento, fecha, observación, usuario)',
           exists (select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                   where n.nspname = 'public' and p.proname = 'registrar_salida_inquilino')
) comprobacion
order by orden;

-- Qué restricciones de unicidad tienen los periodos (para revisar a ojo).
-- Un nuevo inquilino debe poder registrar un mes que el ex inquilino ya tenía cerrado: la unicidad de
-- (apartamento, mes, año) debería aplicar solo a los periodos ABIERTOS (inquilino_historial_id vacío).
select tablename as tabla, indexname as indice, indexdef as definicion
from pg_indexes
where schemaname = 'public'
  and tablename in ('periodos_alquiler', 'periodos_electricidad', 'periodos_agua')
  and indexdef ilike '%unique%'
order by tablename, indexname;

-- Cuántos ex inquilinos hay y cuántos periodos cerrados tiene cada servicio (si las tablas existen).
select (select count(*) from inquilinos_historial) as ex_inquilinos,
       (select count(*) from periodos_alquiler where inquilino_historial_id is not null) as periodos_alquiler_cerrados,
       (select count(*) from periodos_electricidad where inquilino_historial_id is not null) as periodos_luz_cerrados,
       (select count(*) from periodos_agua where inquilino_historial_id is not null) as periodos_agua_cerrados;
