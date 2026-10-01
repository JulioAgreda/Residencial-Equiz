-- ============================================================
-- MIGRACIÓN: Módulo de Pendientes (tareas / to-dos)
-- Ejecuta esto en el SQL Editor de Supabase. Es aditiva/segura de
-- volver a correr: si la tabla ya existe (de una versión anterior
-- de esta migración), solo le agrega las columnas nuevas.
-- Requiere que ya exista la función set_updated_at() (viene en
-- schema.sql / migracion_completa.sql).
-- ============================================================

create table if not exists pendientes (
    id bigserial primary key,
    titulo varchar(200) not null,
    descripcion text,
    que_falta text,                                                        -- ej. "Comprar lampas", "Contratar personal", "Terminar tumbado antes"
    observacion text,                                                      -- notas libres adicionales
    prioridad varchar(20) not null default 'Media'
        check (prioridad in ('Urgente', 'Alta', 'Media', 'Baja')),
    estado varchar(20) not null default 'Pendiente'
        check (estado in ('Pendiente', 'En Proceso', 'Terminado')),
    apartamento_id bigint references apartamentos(id) on delete set null,  -- opcional: si el pendiente es de una unidad específica
    asignado_a bigint references usuarios(id) on delete set null,          -- colaborador responsable (opcional)
    creado_por bigint references usuarios(id) on delete set null,
    fecha_limite date,
    fecha_completado timestamptz,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Por si la tabla ya existía de una corrida anterior de este mismo script:
alter table pendientes add column if not exists que_falta text;
alter table pendientes add column if not exists observacion text;

create index if not exists idx_pendientes_estado on pendientes (estado);
create index if not exists idx_pendientes_prioridad on pendientes (prioridad);
create index if not exists idx_pendientes_asignado on pendientes (asignado_a);
create index if not exists idx_pendientes_apartamento on pendientes (apartamento_id);

drop trigger if exists trg_pendientes_updated on pendientes;
create trigger trg_pendientes_updated
before update on pendientes
for each row execute function set_updated_at();

alter table pendientes disable row level security;

