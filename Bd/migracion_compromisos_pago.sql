-- ============================================================
-- Compromisos de pago — Residencial EQUIZ
-- Historial del motivo de retraso que informa el inquilino y del acuerdo de pago
-- (compromiso, fecha plazo y monto acordado). Un apartamento puede tener varios.
--
-- Ejecutar completo en el SQL Editor de Supabase. Es SEGURO y repetible: solo crea
-- una tabla nueva ("if not exists"); no toca ninguna tabla ni dato existente.
-- ============================================================

-- Función para mantener updated_at (si tu base ya la tiene, esto la deja igual).
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create table if not exists compromisos_pago (
    id bigserial primary key,
    apartamento_id bigint not null references apartamentos(id) on delete cascade,
    inquilino_nombre varchar(200),                 -- inquilino al momento del registro (puede cambiar después)
    fecha_registro date not null default current_date,
    motivo_retraso text not null,                  -- lo que informó el inquilino
    compromiso text,                               -- a qué se comprometió
    fecha_plazo date,                              -- fecha límite acordada
    monto_comprometido numeric(10,2),              -- monto que se comprometió a pagar
    estado varchar(20) not null default 'Pendiente',
    registrado_por varchar(150),
    editado_por varchar(150),
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    constraint ck_compromiso_estado check (estado in ('Pendiente', 'Cumplido', 'Incumplido')),
    constraint ck_compromiso_monto check (monto_comprometido is null or monto_comprometido >= 0),
    constraint ck_compromiso_plazo check (fecha_plazo is null or fecha_plazo >= fecha_registro)
);

create index if not exists idx_compromisos_apto on compromisos_pago (apartamento_id, fecha_registro desc);
create index if not exists idx_compromisos_estado_plazo on compromisos_pago (estado, fecha_plazo);

drop trigger if exists trg_compromisos_updated on compromisos_pago;
create trigger trg_compromisos_updated
before update on compromisos_pago
for each row execute function set_updated_at();

-- Igual que el resto de las tablas de la app (acceso con la clave "anon" detrás del login de la app).
alter table compromisos_pago disable row level security;

-- Verificación: debe mostrar la tabla y rowsecurity = false
select tablename, rowsecurity from pg_tables where schemaname = 'public' and tablename = 'compromisos_pago';
