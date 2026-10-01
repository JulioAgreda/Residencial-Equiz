-- ============================================================
-- MIGRACIÓN: Control de Agua
-- Ejecuta esto en el SQL Editor de Supabase. Es aditivo: solo
-- agrega tablas/columnas nuevas, no toca lo que ya existe.
-- ============================================================

-- Agrega la tarifa de agua a la tabla de configuración ya existente
alter table configuracion add column if not exists tarifa_agua numeric(10,4) not null default 0;

-- Un registro por apartamento + mes/año: lectura del medidor de agua y monto calculado
create table if not exists periodos_agua (
    id bigserial primary key,
    apartamento_id bigint not null references apartamentos(id) on delete cascade,
    mes varchar(20) not null,
    anio int not null,
    lectura_anterior numeric(10,2) not null default 0,
    lectura_actual numeric(10,2) not null default 0,
    tarifa_agua numeric(10,4) not null default 0,
    monto_esperado numeric(10,2) not null default 0,  -- (lectura_actual - lectura_anterior) * tarifa_agua
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique (apartamento_id, mes, anio)
);

-- Pagos/abonos individuales de agua (varios por periodo, igual que electricidad/alquiler)
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

alter table periodos_agua disable row level security;
alter table pagos_agua disable row level security;
