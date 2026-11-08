-- EQUISE: historial persistente de conciliaciones bancarias
-- Ejecutar una sola vez en Supabase > SQL Editor. No modifica tablas contables existentes.
create table if not exists public.conciliaciones_bancarias (
    id uuid primary key default gen_random_uuid(),
    periodo_desde date not null,
    periodo_hasta date not null,
    cuenta text,
    total_movimientos integer not null default 0,
    conciliados integer not null default 0,
    pendientes integer not null default 0,
    monto_banco numeric(14,2) not null default 0,
    creado_por text,
    detalle jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint conciliaciones_bancarias_periodo_valido check (periodo_hasta >= periodo_desde),
    constraint conciliaciones_bancarias_totales_no_negativos check (total_movimientos >= 0 and conciliados >= 0 and pendientes >= 0 and monto_banco >= 0)
);
create index if not exists idx_conciliaciones_bancarias_periodo on public.conciliaciones_bancarias (periodo_desde desc, periodo_hasta desc);
create index if not exists idx_conciliaciones_bancarias_created_at on public.conciliaciones_bancarias (created_at desc);
alter table public.conciliaciones_bancarias enable row level security;
-- Acceso mediante la clave de servicio que utiliza EQUISE desde el backend. No habilitar acceso público.
