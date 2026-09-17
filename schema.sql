-- ============================================================
-- ESQUEMA: Sistema de Control - Residencial "EQUIZ"
-- Ejecutar este script completo en el SQL Editor de Supabase
-- (Proyecto nuevo y separado del sistema de ingresos y egresos)
-- ============================================================

-- Tabla de apartamentos (información base de cada unidad e inquilino)
create table if not exists apartamentos (
    id bigserial primary key,
    codigo varchar(20) unique not null,          -- Ej: PB-01, PP-03, SP-05, TP-02
    piso varchar(50) not null,                    -- Planta Baja / Primer Piso / Segundo Piso / Tercer Piso
    estado varchar(20) not null default 'Ocupado',-- Ocupado / Desocupado
    inquilino_nombre varchar(200),
    celular varchar(50),
    cedula_identidad varchar(50),
    nacionalidad varchar(80),
    fecha_nacimiento date,
    referencia_nombre varchar(200),
    referencia_parentesco varchar(80),
    referencia_celular varchar(50),
    fecha_ingreso date,
    garantia varchar(80),                         -- texto libre: monto o "Sin Garantía"
    amoblado text,
    detalle text,                                 -- ej: "Incluye agua e internet"
    monto_alquiler numeric(10,2) not null default 0,
    notas text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Un registro por apartamento + mes/año: cuánto se espera cobrar ese mes
create table if not exists periodos_alquiler (
    id bigserial primary key,
    apartamento_id bigint not null references apartamentos(id) on delete cascade,
    mes varchar(20) not null,                     -- Enero, Febrero, ...
    anio int not null,
    monto_esperado numeric(10,2) not null default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique (apartamento_id, mes, anio)
);

-- Pagos/abonos individuales: varios pueden pertenecer a un mismo periodo
-- (ej. abonó 200 el día 5 y 300 el día 20 del mismo mes)
create table if not exists pagos (
    id bigserial primary key,
    periodo_id bigint not null references periodos_alquiler(id) on delete cascade,
    fecha date not null,
    monto numeric(10,2) not null default 0,
    metodo_pago varchar(50),                      -- Efectivo, Transferencia, QR, etc.
    observacion text,
    created_at timestamptz default now()
);

-- Configuración general (tarifa por Kwh y por m³ de agua vigentes)
create table if not exists configuracion (
    id int primary key default 1,
    tarifa_kwh numeric(10,4) not null default 0,
    tarifa_agua numeric(10,4) not null default 0,
    updated_at timestamptz default now(),
    constraint solo_una_fila check (id = 1)
);
insert into configuracion (id, tarifa_kwh, tarifa_agua)
    values (1, 0, 0)
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

-- Índices útiles
create index if not exists idx_periodos_apartamento on periodos_alquiler (apartamento_id);
create index if not exists idx_periodos_periodo on periodos_alquiler (anio, mes);
create index if not exists idx_pagos_periodo on pagos (periodo_id);
create index if not exists idx_periodos_elec_apartamento on periodos_electricidad (apartamento_id);
create index if not exists idx_periodos_elec_periodo on periodos_electricidad (anio, mes);
create index if not exists idx_pagos_elec_periodo on pagos_electricidad (periodo_id);
create index if not exists idx_periodos_agua_apartamento on periodos_agua (apartamento_id);
create index if not exists idx_periodos_agua_periodo on periodos_agua (anio, mes);
create index if not exists idx_pagos_agua_periodo on pagos_agua (periodo_id);

-- Trigger genérico para actualizar updated_at automáticamente
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_apartamentos_updated on apartamentos;
create trigger trg_apartamentos_updated
before update on apartamentos
for each row execute function set_updated_at();

drop trigger if exists trg_periodos_updated on periodos_alquiler;
create trigger trg_periodos_updated
before update on periodos_alquiler
for each row execute function set_updated_at();

drop trigger if exists trg_periodos_elec_updated on periodos_electricidad;
create trigger trg_periodos_elec_updated
before update on periodos_electricidad
for each row execute function set_updated_at();

drop trigger if exists trg_periodos_agua_updated on periodos_agua;
create trigger trg_periodos_agua_updated
before update on periodos_agua
for each row execute function set_updated_at();

-- ============================================================
-- Seguridad: estas tablas se acceden con la clave "anon" desde
-- la app de Streamlit, que ya está protegida con una clave de
-- acceso compartida (APP_PASSWORD). Por eso desactivamos RLS
-- explícitamente: los proyectos nuevos de Supabase a veces lo
-- activan por defecto sin políticas, lo que bloquearía todo
-- acceso ("row-level security policy" error). Si más adelante
-- quieres activar RLS y definir políticas, se puede ajustar.
-- ============================================================
alter table apartamentos disable row level security;
alter table periodos_alquiler disable row level security;
alter table pagos disable row level security;
alter table configuracion disable row level security;
alter table periodos_electricidad disable row level security;
alter table pagos_electricidad disable row level security;
alter table periodos_agua disable row level security;
alter table pagos_agua disable row level security;
