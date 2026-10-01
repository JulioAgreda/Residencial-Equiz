-- ============================================================
-- LIMPIEZA: borrar TODOS los pagos (abonos) de prueba
-- Alquiler (pagos), Electricidad (pagos_electricidad) y Agua (pagos_agua).
-- Ejecuta esto en el SQL Editor de Supabase.
--
-- ⚠️ ESTA ACCIÓN NO SE PUEDE DESHACER. Si tienes dudas, primero
-- revisa un respaldo (tu backup diario de GitHub Actions).
--
-- NO borra: apartamentos, usuarios, ni los periodos (meses con su
-- monto esperado y lecturas de medidor). Solo los pagos/abonos.
-- ============================================================

-- 1) Antes de borrar: cuántos registros hay en cada tabla
select 'pagos (alquiler)' as tabla, count(*) as registros from pagos
union all
select 'pagos_electricidad', count(*) from pagos_electricidad
union all
select 'pagos_agua', count(*) from pagos_agua;

-- 2) Borrado de los pagos
delete from pagos;
delete from pagos_electricidad;
delete from pagos_agua;

-- 3) Verificación: las tres filas deben mostrar 0
select 'pagos (alquiler)' as tabla, count(*) as registros from pagos
union all
select 'pagos_electricidad', count(*) from pagos_electricidad
union all
select 'pagos_agua', count(*) from pagos_agua;


-- ============================================================
-- OPCIONAL (descomenta solo si también quieres borrar los periodos
-- de prueba: meses registrados con monto esperado y lecturas de
-- medidor de luz/agua). Al borrar un periodo se borran sus pagos
-- automáticamente. Si lo haces, la app volverá a pedir la lectura
-- anterior del medidor desde cero.
-- ============================================================
-- delete from periodos_alquiler;
-- delete from periodos_electricidad;
-- delete from periodos_agua;
