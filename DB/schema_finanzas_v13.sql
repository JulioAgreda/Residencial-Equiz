-- Residencial Equise | Migración V13: cuentas por pagar y por cobrar
-- PREPARACIÓN ÚNICAMENTE. NO EJECUTAR EN PRODUCCIÓN SIN REVISIÓN Y AUTORIZACIÓN.
-- No modifica tablas existentes ni altera RLS. La app actual usa acceso propio
-- con clave anon; revisar la estrategia de seguridad antes de habilitar estas tablas.

create table if not exists obligaciones_financieras (
    id bigserial primary key,
    codigo varchar(40) unique not null,
    categoria varchar(40) not null check (categoria in (
        'Prestamo de colaborador','Prestamo de persona externa'
    )),
    acreedor varchar(200) not null,
    identificacion_acreedor varchar(80),
    descripcion text,
    fecha_origen date not null,
    fecha_corte date not null,
    monto_original numeric(14,2) not null check (monto_original > 0),
    saldo_apertura numeric(14,2) not null check (saldo_apertura >= 0),
    fecha_vencimiento date,
    documento_referencia varchar(150),
    observaciones text,
    estado varchar(20) not null default 'Vigente'
        check (estado in ('Vigente','Vencida','Cancelada','Reestructurada')),
    creado_por varchar(150),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (fecha_vencimiento is null or fecha_vencimiento >= fecha_origen),
    check (saldo_apertura <= monto_original)
);

create table if not exists movimientos_obligaciones (
    id bigserial primary key,
    obligacion_id bigint not null references obligaciones_financieras(id),
    fecha date not null,
    tipo varchar(30) not null check (tipo in (
        'desembolso_adicional','pago_capital','ajuste_incremento','ajuste_reduccion'
    )),
    monto numeric(14,2) not null check (monto > 0),
    metodo varchar(40),
    referencia varchar(150),
    observacion text,
    registrado_por varchar(150),
    created_at timestamptz not null default now()
);

create table if not exists cuentas_por_cobrar (
    id bigserial primary key,
    codigo varchar(40) unique not null,
    categoria varchar(40) not null check (categoria in (
        'Prestamo a colaborador','Prestamo a persona externa'
    )),
    deudor varchar(200) not null,
    identificacion_deudor varchar(80),
    descripcion text,
    fecha_origen date not null,
    fecha_corte date not null,
    monto_original numeric(14,2) not null check (monto_original > 0),
    saldo_apertura numeric(14,2) not null check (saldo_apertura >= 0),
    fecha_vencimiento date,
    documento_referencia varchar(150),
    observaciones text,
    estado varchar(20) not null default 'Vigente'
        check (estado in ('Vigente','Vencida','Cancelada','Incobrable')),
    creado_por varchar(150),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (fecha_vencimiento is null or fecha_vencimiento >= fecha_origen),
    check (saldo_apertura <= monto_original)
);

create table if not exists movimientos_cuentas_cobrar (
    id bigserial primary key,
    cuenta_id bigint not null references cuentas_por_cobrar(id),
    fecha date not null,
    tipo varchar(30) not null check (tipo in (
        'nuevo_desembolso','cargo_adicional','cobro','ajuste_incremento','ajuste_reduccion'
    )),
    monto numeric(14,2) not null check (monto > 0),
    metodo varchar(40),
    referencia varchar(150),
    observacion text,
    registrado_por varchar(150),
    created_at timestamptz not null default now()
);

create index if not exists idx_obligaciones_estado on obligaciones_financieras(estado);
create index if not exists idx_obligaciones_vencimiento on obligaciones_financieras(fecha_vencimiento);
create index if not exists idx_mov_obligacion_fecha on movimientos_obligaciones(obligacion_id, fecha);
create index if not exists idx_cxc_estado on cuentas_por_cobrar(estado);
create index if not exists idx_cxc_vencimiento on cuentas_por_cobrar(fecha_vencimiento);
create index if not exists idx_mov_cxc_fecha on movimientos_cuentas_cobrar(cuenta_id, fecha);

-- No se agregan intereses en esta primera versión, según alcance definido.
-- Los pagos/cobros deben enlazarse en la siguiente fase a caja/bancos para evitar
-- registrar dos veces el mismo movimiento de efectivo.

-- Alinear restricciones de categoria si las tablas fueron creadas previamente con V12.
ALTER TABLE public.obligaciones_financieras
  DROP CONSTRAINT IF EXISTS obligaciones_financieras_categoria_check;
ALTER TABLE public.obligaciones_financieras
  ADD CONSTRAINT obligaciones_financieras_categoria_check
  CHECK (categoria IN ('Prestamo de colaborador','Prestamo de persona externa'));

ALTER TABLE public.cuentas_por_cobrar
  DROP CONSTRAINT IF EXISTS cuentas_por_cobrar_categoria_check;
ALTER TABLE public.cuentas_por_cobrar
  ADD CONSTRAINT cuentas_por_cobrar_categoria_check
  CHECK (categoria IN ('Prestamo a colaborador','Prestamo a persona externa'));

NOTIFY pgrst, 'reload schema';
