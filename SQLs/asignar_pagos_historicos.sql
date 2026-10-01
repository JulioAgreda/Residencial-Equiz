-- ============================================================
-- Asignar retroactivamente "quién lo registró" a pagos viejos
-- (de antes de la migración migracion_reportes_usuarios.sql).
-- Ejecuta esto en el SQL Editor de Supabase.
--
-- La app no guardaba esta información antes, así que no hay forma
-- de reconstruirla automáticamente: tienes que decir TÚ quién cobró
-- esos pagos. Edita el nombre entre comillas antes de ejecutar.
-- ============================================================

-- 0) Diagnóstico: cuántos pagos viejos faltan por asignar
select 'pagos (alquiler)' as tabla, count(*) as sin_asignar from pagos where registrado_por is null
union all
select 'pagos_electricidad', count(*) from pagos_electricidad where registrado_por is null
union all
select 'pagos_agua', count(*) from pagos_agua where registrado_por is null;


-- ============================================================
-- OPCIÓN A: Asignar TODOS los pagos sin dueño a una sola persona
-- (lo más común si, antes de tener varios cobradores, una sola
-- persona --tú-- registraba todo). Cambia el nombre y descomenta.
-- ============================================================
-- update pagos              set registrado_por = 'Julio Agreda' where registrado_por is null;
-- update pagos_electricidad set registrado_por = 'Julio Agreda' where registrado_por is null;
-- update pagos_agua         set registrado_por = 'Julio Agreda' where registrado_por is null;


-- ============================================================
-- OPCIÓN B: Asignar por rango de fechas, si distintas personas
-- cobraron en distintas épocas. Repite el bloque con cada rango
-- y nombre que corresponda, y descomenta las líneas que uses.
-- ============================================================
-- update pagos
--    set registrado_por = 'Erick Zelada'
--  where registrado_por is null
--    and fecha between '2025-01-01' and '2025-06-30';

-- update pagos_electricidad
--    set registrado_por = 'Erick Zelada'
--  where registrado_por is null
--    and fecha between '2025-01-01' and '2025-06-30';


-- ============================================================
-- OPCIÓN C: Asignar por apartamento, si un cobrador atendía
-- siempre los mismos apartamentos (requiere cruzar con el periodo).
-- ============================================================
-- update pagos p
--    set registrado_por = 'Yerlin Cuellar'
--   from periodos_alquiler per, apartamentos a
--  where p.periodo_id = per.id
--    and per.apartamento_id = a.id
--    and p.registrado_por is null
--    and a.codigo in ('PB-01', 'PB-02');


-- 3) Verificación final: debe dar 0 en las tres filas (o lo que decidas dejar sin asignar)
select 'pagos (alquiler)' as tabla, count(*) as sin_asignar from pagos where registrado_por is null
union all
select 'pagos_electricidad', count(*) from pagos_electricidad where registrado_por is null
union all
select 'pagos_agua', count(*) from pagos_agua where registrado_por is null;
