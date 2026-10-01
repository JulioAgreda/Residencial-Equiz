-- ============================================================
-- MIGRACIÓN: Control de Electricidad
-- Ejecuta esto en el SQL Editor de Supabase. Es aditivo: solo
-- agrega tablas nuevas, no toca apartamentos, periodos_alquiler
-- ni pagos existentes.
-- ============================================================

-- Configuración general (por ahora solo guarda la tarifa por Kwh vigente)
create table if not exists configuracion (
    id int primary key default 1,
    tarifa_kwh numeric(10,4) not null default 0,
    updated_at timestamptz default now(),
    constraint solo_una_fila check (id = 1)
);
insert into configuracion (id, tarifa_kwh)
    values (1, 0)
    on conflict (id) do nothing;

-- Un registro por apartamento + mes/año: lectura del medidor y monto calculado
create table if not exists periodos_electricidad (
    id bigserial primary key,
    apartamento_id bigint not null references apartamentos(id) on delete cascade,
    mes varchar(20) not null,
    anio int not null,
    kwh_anterior numeric(10,2) not null default 0,
    kwh_actual numeric(10,2) not null default 0,
    tarifa_kwh numeric(10,4) not null default 0,
    monto_esperado numeric(10,2) not null default 0,  -- (kwh_actual - kwh_anterior) * tarifa_kwh
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique (apartamento_id, mes, anio)
);

-- Pagos/abonos individuales de electricidad (varios por periodo, igual que alquiler)
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

alter table configuracion disable row level security;
alter table periodos_electricidad disable row level security;
alter table pagos_electricidad disable row level security;
