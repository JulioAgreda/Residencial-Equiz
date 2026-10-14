-- ============================================================
-- INVENTARIO: artículos (materiales, repuestos, suministros) y sus movimientos de entrada y salida
-- Ejecutar UNA vez en el SQL Editor de Supabase. Es repetible y no toca ningún dato existente: solo crea
-- dos tablas nuevas (y sus índices) si no existen.
--
-- El Kardex NO se guarda: la app lo calcula siempre desde los movimientos (costo promedio ponderado).
-- ============================================================

-- Función genérica para mantener updated_at (ya existe en el proyecto; se vuelve a crear igual por si falta)
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

-- ---------- Artículos ----------
create table if not exists inventario_articulos (
    id bigserial primary key,
    codigo varchar(30) not null,                                  -- ej. INV-001
    nombre varchar(150) not null,
    categoria varchar(60),
    unidad varchar(30) not null default 'Unidad',                 -- Pieza, Metro, Litro, Caja, ...
    stock_minimo numeric(12,3) not null default 0 check (stock_minimo >= 0),   -- alerta de stock bajo
    ubicacion varchar(100),                                       -- ej. Bodega, Cuarto de máquinas
    notas text,
    activo boolean not null default true,
    creado_por varchar(150),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
-- el código no se repite (sin distinguir mayúsculas)
create unique index if not exists uq_inventario_articulos_codigo on inventario_articulos (lower(codigo));
create index if not exists idx_inventario_articulos_nombre on inventario_articulos (nombre);

-- ---------- Movimientos ----------
create table if not exists inventario_movimientos (
    id bigserial primary key,
    articulo_id bigint not null references inventario_articulos(id) on delete restrict,   -- no se borra un artículo con movimientos
    fecha date not null,
    tipo varchar(10) not null check (tipo in ('Entrada', 'Salida')),
    motivo varchar(60) not null,                                  -- Compra, Saldo inicial, Uso en apartamento, ...
    cantidad numeric(12,3) not null check (cantidad > 0),
    costo_unitario numeric(12,4) check (costo_unitario is null or costo_unitario >= 0),   -- solo en entradas
    apartamento_id bigint references apartamentos(id) on delete set null,                -- salidas de uso en un apartamento
    destino varchar(150),                                         -- apartamento, áreas comunes o edificio en general
    documento varchar(100),                                       -- N° de factura, vale o recibo
    observacion text,
    registrado_por varchar(150),
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    constraint ck_inventario_entrada_con_costo check (tipo <> 'Entrada' or costo_unitario is not null)
);
create index if not exists idx_inventario_mov_articulo_fecha on inventario_movimientos (articulo_id, fecha);
create index if not exists idx_inventario_mov_fecha on inventario_movimientos (fecha);

drop trigger if exists trg_inventario_articulos_updated on inventario_articulos;
create trigger trg_inventario_articulos_updated
before update on inventario_articulos
for each row execute function set_updated_at();

drop trigger if exists trg_inventario_mov_updated on inventario_movimientos;
create trigger trg_inventario_mov_updated
before update on inventario_movimientos
for each row execute function set_updated_at();

-- Igual que el resto de las tablas de la app: se accede con la clave "anon" desde la app, que ya tiene su propio login
alter table inventario_articulos disable row level security;
alter table inventario_movimientos disable row level security;
