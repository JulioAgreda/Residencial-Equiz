-- ============================================================
-- MIGRACIÓN: Módulo de Reuniones (área administrativa)
-- Ejecuta esto en el SQL Editor de Supabase. Es aditivo: solo
-- agrega tablas nuevas, no toca nada existente.
-- Requiere que ya exista la función set_updated_at() (viene en
-- schema.sql / migracion_completa.sql).
-- ============================================================

-- Una fila por reunión
create table if not exists reuniones (
    id bigserial primary key,
    fecha date not null,
    puntos_tratados text not null,
    descripcion_acuerdos text,          -- descripción de lo acordado
    invitados text,                     -- personas externas, en texto libre (no son usuarios del sistema)
    creado_por bigint references usuarios(id) on delete set null,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Participantes internos (usuarios del sistema) de cada reunión: relación varios a varios
create table if not exists reuniones_participantes (
    id bigserial primary key,
    reunion_id bigint not null references reuniones(id) on delete cascade,
    usuario_id bigint not null references usuarios(id) on delete cascade,
    unique (reunion_id, usuario_id)
);

create index if not exists idx_reuniones_fecha on reuniones (fecha);
create index if not exists idx_reuniones_part_reunion on reuniones_participantes (reunion_id);
create index if not exists idx_reuniones_part_usuario on reuniones_participantes (usuario_id);

drop trigger if exists trg_reuniones_updated on reuniones;
create trigger trg_reuniones_updated
before update on reuniones
for each row execute function set_updated_at();

alter table reuniones disable row level security;
alter table reuniones_participantes disable row level security;

-- ============================================================
-- NOTA sobre permisos: "solo el Administrador puede crear/editar,
-- el resto solo visualiza" se controla en la app (Streamlit ya
-- filtra por rol, igual que en Usuarios), no con RLS en la base
-- de datos — mismo criterio de seguridad que usa el resto del
-- sistema (ver comentario de seguridad en schema.sql).
-- ============================================================
