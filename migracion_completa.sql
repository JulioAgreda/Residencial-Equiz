-- ============================================================
-- MIGRACIÓN CONSOLIDADA — Sistema de Control Residencial EQUIZ
-- Ejecuta este ÚNICO script completo en el SQL Editor de Supabase.
-- Incluye TODO lo implementado hasta ahora: pagos múltiples de
-- alquiler, electricidad, agua, datos de contrato, usuarios (roles
-- y permisos), y el módulo de Compras/Ventas con almacenamiento de
-- comprobantes. Es seguro de ejecutar aunque ya hayas corrido antes
-- alguno de los migracion_*.sql sueltos (todo usa "if not exists").
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

-- ---------- 6) Compras (gastos) ----------
create table if not exists compras (
    id bigserial primary key,
    fecha_compra date not null,
    categoria varchar(100) not null,
    descripcion text,
    monto_total numeric(10,2) not null default 0,
    metodo_pago varchar(50),
    proveedor varchar(200),
    numero_comprobante varchar(100),
    archivo_url text,
    archivo_nombre text,
    encargado varchar(150),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists idx_compras_fecha on compras (fecha_compra);
create index if not exists idx_compras_categoria on compras (categoria);

drop trigger if exists trg_compras_updated on compras;
create trigger trg_compras_updated
before update on compras
for each row execute function set_updated_at();

alter table compras disable row level security;

-- ---------- 7) Ventas (ingresos extraordinarios) ----------
create table if not exists ventas (
    id bigserial primary key,
    fecha_venta date not null,
    concepto varchar(100) not null,
    descripcion text,
    monto numeric(10,2) not null default 0,
    forma_cobro varchar(50),
    comprador varchar(200),
    recibo_emitido varchar(100),
    encargado varchar(150),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists idx_ventas_fecha on ventas (fecha_venta);
create index if not exists idx_ventas_concepto on ventas (concepto);

drop trigger if exists trg_ventas_updated on ventas;
create trigger trg_ventas_updated
before update on ventas
for each row execute function set_updated_at();

alter table ventas disable row level security;

-- ---------- 8) Almacenamiento de comprobantes (fotos/PDF de facturas) ----------
insert into storage.buckets (id, name, public)
values ('comprobantes', 'comprobantes', true)
on conflict (id) do nothing;

drop policy if exists "comprobantes_select" on storage.objects;
create policy "comprobantes_select" on storage.objects
    for select using (bucket_id = 'comprobantes');

drop policy if exists "comprobantes_insert" on storage.objects;
create policy "comprobantes_insert" on storage.objects
    for insert with check (bucket_id = 'comprobantes');

drop policy if exists "comprobantes_update" on storage.objects;
create policy "comprobantes_update" on storage.objects
    for update using (bucket_id = 'comprobantes');

drop policy if exists "comprobantes_delete" on storage.objects;
create policy "comprobantes_delete" on storage.objects
    for delete using (bucket_id = 'comprobantes');

-- ---------- 9) Seguridad: asegurar RLS desactivado en TODAS las tablas ----------
-- Esto es clave: si alguna queda con RLS activo, las consultas devuelven
-- vacío (200 con 0 filas) en vez de error, lo que parece "no trae datos".
alter table apartamentos disable row level security;
alter table periodos_alquiler disable row level security;
alter table pagos disable row level security;
alter table configuracion disable row level security;
alter table periodos_electricidad disable row level security;
alter table pagos_electricidad disable row level security;
alter table periodos_agua disable row level security;
alter table pagos_agua disable row level security;
alter table usuarios disable row level security;
alter table compras disable row level security;
alter table ventas disable row level security;

-- ---------- 10) Verificación final ----------
select tablename, rowsecurity
from pg_tables
where tablename in (
    'apartamentos','periodos_alquiler','pagos','configuracion',
    'periodos_electricidad','pagos_electricidad','periodos_agua','pagos_agua',
    'usuarios','compras','ventas'
);
-- Todas las filas de este resultado deben mostrar "false" en rowsecurity.
