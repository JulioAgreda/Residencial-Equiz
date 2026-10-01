-- ============================================================
-- MIGRACIÓN: Pagos generales (tercera opción del Módulo de Movimientos,
-- junto a Compras y Ventas). Se usa para pagos que no necesitan
-- comprobante adjunto (sueldos, servicios, pagos a proveedores, etc.)
-- Ejecuta esto en el SQL Editor de Supabase. Es aditivo.
-- NOTA: se llama "pagos_generales" (no "pagos") porque la tabla
-- "pagos" ya existe y se usa para los abonos de alquiler.
-- ============================================================

create table if not exists pagos_generales (
    id bigserial primary key,
    fecha_pago date not null,
    categoria varchar(100) not null,
    descripcion text,
    monto numeric(10,2) not null default 0,
    metodo_pago varchar(50),
    beneficiario varchar(200),      -- a quién se le pagó
    encargado varchar(150),         -- quién realizó el pago
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists idx_pagos_generales_fecha on pagos_generales (fecha_pago);
create index if not exists idx_pagos_generales_categoria on pagos_generales (categoria);

drop trigger if exists trg_pagos_generales_updated on pagos_generales;
create trigger trg_pagos_generales_updated
before update on pagos_generales
for each row execute function set_updated_at();

alter table pagos_generales disable row level security;
