-- ============================================================
-- MIGRACIÓN: Servicios Básicos (dentro del módulo de Pendientes)
-- Ejecuta esto en el SQL Editor de Supabase. Es aditiva: solo
-- agrega la tabla nueva, no toca nada existente.
-- ============================================================

create table if not exists servicios_basicos (
    id bigserial primary key,
    nombre_servicio varchar(150) not null,   -- ej. "Electricidad", "Agua", "Internet"
    empresa_proveedor varchar(200),
    telefono varchar(50),
    codigo varchar(100),                      -- código de cliente / NIS / cuenta
    titular varchar(200),
    observacion text,
    creado_por bigint references usuarios(id) on delete set null,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists idx_servicios_basicos_nombre on servicios_basicos (nombre_servicio);

drop trigger if exists trg_servicios_basicos_updated on servicios_basicos;
create trigger trg_servicios_basicos_updated
before update on servicios_basicos
for each row execute function set_updated_at();

alter table servicios_basicos disable row level security;
