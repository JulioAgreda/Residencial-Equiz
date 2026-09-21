-- ============================================================
-- MIGRACIÓN: Compras (gastos) y Ventas (ingresos extraordinarios)
-- Ejecuta esto en el SQL Editor de Supabase. Es aditivo.
-- ============================================================

-- ---------- Compras / Gastos ----------
create table if not exists compras (
    id bigserial primary key,
    fecha_compra date not null,
    categoria varchar(100) not null,
    descripcion text,
    monto_total numeric(10,2) not null default 0,
    metodo_pago varchar(50),
    proveedor varchar(200),
    numero_comprobante varchar(100),
    archivo_url text,               -- link al comprobante subido (foto/PDF)
    archivo_nombre text,
    encargado varchar(150),         -- quién realizó la compra
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

-- ---------- Ventas / Ingresos extraordinarios ----------
create table if not exists ventas (
    id bigserial primary key,
    fecha_venta date not null,
    concepto varchar(100) not null,
    descripcion text,
    monto numeric(10,2) not null default 0,
    forma_cobro varchar(50),
    comprador varchar(200),
    recibo_emitido varchar(100),
    encargado varchar(150),         -- quién recibió el dinero
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

-- ---------- Almacenamiento de comprobantes (fotos/PDF de facturas) ----------
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
