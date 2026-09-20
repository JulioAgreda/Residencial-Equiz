-- ============================================================
-- MIGRACIÓN CONSOLIDADA — Sistema de Control Residencial EQUIZ
-- Ejecuta este ÚNICO script completo en el SQL Editor de Supabase.
-- Incluye, en orden seguro: pagos múltiples de alquiler,
-- electricidad, agua y datos de contrato. Es seguro de ejecutar
-- aunque ya hayas corrido alguno de los migracion_*.sql sueltos
-- antes (todo usa "if not exists" / "if exists").
-- No borra tus apartamentos.
-- ============================================================

-- ---------- 1) Pagos de alquiler múltiples ----------
drop table if exists pagos_alquiler cascade;

create table if not exists periodos_alquiler (
    id bigserial primary key,
    apartamento_id bigint not null references apartamentos(id) on delete cascade,
    mes varchar(20) not null,
    anio int not null,
    monto_esperado numeric(10,2) not null default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique (apartamento_id, mes, anio)
);

create table if not exists pagos (
    id bigserial primary key,
    periodo_id bigint not null references periodos_alquiler(id) on delete cascade,
    fecha date not null,
    monto numeric(10,2) not null default 0,
    metodo_pago varchar(50),
    observacion text,
    created_at timestamptz default now()
);

create index if not exists idx_periodos_apartamento on periodos_alquiler (apartamento_id);
create index if not exists idx_periodos_periodo on periodos_alquiler (anio, mes);
create index if not exists idx_pagos_periodo on pagos (periodo_id);

create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_periodos_updated on periodos_alquiler;
create trigger trg_periodos_updated
before update on periodos_alquiler
for each row execute function set_updated_at();

-- ---------- 2) Electricidad ----------
create table if not exists configuracion (
    id int primary key default 1,
    tarifa_kwh numeric(10,4) not null default 0,
    updated_at timestamptz default now(),
    constraint solo_una_fila check (id = 1)
);
insert into configuracion (id, tarifa_kwh) values (1, 0) on conflict (id) do nothing;

create table if not exists periodos_electricidad (
    id bigserial primary key,
    apartamento_id bigint not null references apartamentos(id) on delete cascade,
    mes varchar(20) not null,
    anio int not null,
    kwh_anterior numeric(10,2) not null default 0,
    kwh_actual numeric(10,2) not null default 0,
    tarifa_kwh numeric(10,4) not null default 0,
    monto_esperado numeric(10,2) not null default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique (apartamento_id, mes, anio)
);

create table if not exists pagos_electricidad (
    id bigserial primary key,
    periodo_id bigint not null references periodos_electricidad(id) on delete cascade,
    fecha date not null,
    monto numeric(10,2) not null default 0,
    metodo_pago varchar(50),
    observacion text,
    created_at timestamptz default now()
);

create index if not exists idx_periodos_elec_apartamento on periodos_electricidad (apartamento_id);
create index if not exists idx_periodos_elec_periodo on periodos_electricidad (anio, mes);
create index if not exists idx_pagos_elec_periodo on pagos_electricidad (periodo_id);

drop trigger if exists trg_periodos_elec_updated on periodos_electricidad;
create trigger trg_periodos_elec_updated
before update on periodos_electricidad
for each row execute function set_updated_at();

-- ---------- 3) Agua ----------
alter table configuracion add column if not exists tarifa_agua numeric(10,4) not null default 0;

create table if not exists periodos_agua (
    id bigserial primary key,
    apartamento_id bigint not null references apartamentos(id) on delete cascade,
    mes varchar(20) not null,
    anio int not null,
    lectura_anterior numeric(10,2) not null default 0,
    lectura_actual numeric(10,2) not null default 0,
    tarifa_agua numeric(10,4) not null default 0,
    monto_esperado numeric(10,2) not null default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique (apartamento_id, mes, anio)
);

create table if not exists pagos_agua (
    id bigserial primary key,
    periodo_id bigint not null references periodos_agua(id) on delete cascade,
    fecha date not null,
    monto numeric(10,2) not null default 0,
    metodo_pago varchar(50),
    observacion text,
    created_at timestamptz default now()
);

create index if not exists idx_periodos_agua_apartamento on periodos_agua (apartamento_id);
create index if not exists idx_periodos_agua_periodo on periodos_agua (anio, mes);
create index if not exists idx_pagos_agua_periodo on pagos_agua (periodo_id);

drop trigger if exists trg_periodos_agua_updated on periodos_agua;
create trigger trg_periodos_agua_updated
before update on periodos_agua
for each row execute function set_updated_at();

-- ---------- 4) Datos de contrato en apartamentos ----------
alter table apartamentos add column if not exists tipo_contrato varchar(20);
alter table apartamentos add column if not exists estado_contrato varchar(20) not null default 'Sin Contrato';
alter table apartamentos add column if not exists contrato_fecha_inicio date;
alter table apartamentos add column if not exists contrato_fecha_fin date;
alter table apartamentos add column if not exists contrato_observaciones text;

-- ---------- 5) Usuarios (roles y permisos) ----------
create table if not exists usuarios (
    id bigserial primary key,
    username varchar(50) unique not null,
    nombre varchar(150),
    password_hash text not null,
    rol varchar(20) not null default 'Cobrador',
    activo boolean not null default true,
    created_at timestamptz default now()
);
alter table usuarios disable row level security;

-- ---------- 6) Seguridad: asegurar RLS desactivado en TODAS las tablas ----------
-- Esto es clave: si alguna quedó con RLS activo, las consultas devuelven
-- vacío (200 con 0 filas) en vez de error, lo que parece "no trae datos".
alter table apartamentos disable row level security;
alter table periodos_alquiler disable row level security;
alter table pagos disable row level security;
alter table configuracion disable row level security;
alter table periodos_electricidad disable row level security;
alter table pagos_electricidad disable row level security;
alter table periodos_agua disable row level security;
alter table pagos_agua disable row level security;

-- ---------- 7) Verificación final ----------
select tablename, rowsecurity
from pg_tables
where tablename in (
    'apartamentos','periodos_alquiler','pagos','configuracion',
    'periodos_electricidad','pagos_electricidad','periodos_agua','pagos_agua','usuarios'
);
-- Todas las filas de este resultado deben mostrar "false" en rowsecurity.
