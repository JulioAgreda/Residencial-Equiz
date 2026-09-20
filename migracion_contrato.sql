-- ============================================================
-- MIGRACIÓN: Datos de contrato por apartamento
-- Ejecuta esto en el SQL Editor de Supabase. Es aditivo: solo
-- agrega columnas nuevas a la tabla apartamentos, no borra nada.
-- ============================================================

alter table apartamentos add column if not exists tipo_contrato varchar(20);
alter table apartamentos add column if not exists estado_contrato varchar(20) not null default 'Sin Contrato';
alter table apartamentos add column if not exists contrato_fecha_inicio date;
alter table apartamentos add column if not exists contrato_fecha_fin date;
alter table apartamentos add column if not exists contrato_observaciones text;
