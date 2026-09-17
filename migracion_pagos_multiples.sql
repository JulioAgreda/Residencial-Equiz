-- ============================================================
-- MIGRACIÓN: permitir varios pagos (abonos) por apartamento y mes
-- Ejecuta esto en el SQL Editor de Supabase.
-- Es seguro de correr aunque ya tengas apartamentos creados: solo
-- reemplaza la tabla pagos_alquiler (que hasta ahora no tenía
-- datos utilizables por el error de RLS).
-- ============================================================

drop table if exists pagos_alquiler cascade;

-- Un registro por apartamento + mes/año: cuánto se espera cobrar ese mes
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

-- Varios pagos/abonos pueden pertenecer a un mismo periodo
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

drop trigger if exists trg_periodos_updated on periodos_alquiler;
create trigger trg_periodos_updated
before update on periodos_alquiler
for each row execute function set_updated_at();

alter table periodos_alquiler disable row level security;
alter table pagos disable row level security;
