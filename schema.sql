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
    tipo_contrato varchar(20),                     -- Alquiler / Anticrético
    estado_contrato varchar(20) not null default 'Sin Contrato',  -- Vigente / Caducado / Sin Contrato
    contrato_fecha_inicio date,
    contrato_fecha_fin date,
    contrato_observaciones text,
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

-- Usuarios (roles y permisos: Administrador / Cobrador)
create table if not exists usuarios (
    id bigserial primary key,
    username varchar(50) unique not null,
    nombre varchar(150),
    password_hash text not null,
    rol varchar(20) not null default 'Cobrador',
    activo boolean not null default true,
    created_at timestamptz default now()
);

-- Compras (gastos / egresos)
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

-- Ventas (ingresos extraordinarios)
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

-- Almacenamiento de comprobantes (fotos/PDF de facturas de compras)
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

-- ============================================================
-- Seguridad: estas tablas se acceden con la clave "anon" desde
-- la app de Streamlit, que ya está protegida con login propio
-- (usuarios/roles). Por eso desactivamos RLS explícitamente: los
-- proyectos nuevos de Supabase a veces lo activan por defecto sin
-- políticas, lo que bloquearía todo acceso ("row-level security
-- policy" error). Si más adelante quieres activar RLS y definir
-- políticas, se puede ajustar.
-- ============================================================
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
