-- ============================================================
-- MIGRACIÓN: Módulos de Deudas (lo que el residencial DEBE) y
-- Cobros (lo que le DEBEN al residencial), con pagos parciales.
-- Ejecuta esto en el SQL Editor de Supabase. Es aditiva y segura
-- de volver a correr. Requiere set_updated_at() (ya existe).
-- ============================================================

create table if not exists deudas_cobros (
    id bigserial primary key,
    tipo varchar(10) not null check (tipo in ('Deuda', 'Cobro')),
    persona varchar(200) not null,          -- acreedor (Deuda) o deudor (Cobro)
    telefono varchar(50),
    concepto varchar(100) not null,         -- préstamo, servicio, daños, etc.
    descripcion text,
    monto_total numeric(12,2) not null check (monto_total > 0),
    fecha_origen date not null,
    fecha_vencimiento date,                 -- fecha límite pactada (opcional)
    observacion text,
    creado_por text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists deudas_cobros_pagos (
    id bigserial primary key,
    cuenta_id bigint not null references deudas_cobros(id) on delete cascade,
    fecha date not null,
    monto numeric(12,2) not null check (monto > 0),
    metodo_pago varchar(50),
    observacion text,
    registrado_por text,
    created_at timestamptz default now()
);

create index if not exists idx_deudas_cobros_tipo on deudas_cobros (tipo);
create index if not exists idx_deudas_cobros_venc on deudas_cobros (fecha_vencimiento);
create index if not exists idx_dc_pagos_cuenta on deudas_cobros_pagos (cuenta_id);
create index if not exists idx_dc_pagos_fecha on deudas_cobros_pagos (fecha);

drop trigger if exists trg_deudas_cobros_updated on deudas_cobros;
create trigger trg_deudas_cobros_updated
before update on deudas_cobros
for each row execute function set_updated_at();

alter table deudas_cobros disable row level security;
alter table deudas_cobros_pagos disable row level security;

notify pgrst, 'reload schema';
