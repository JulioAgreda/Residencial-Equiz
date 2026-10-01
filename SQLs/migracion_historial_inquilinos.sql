-- ============================================================
-- MIGRACIÓN: Historial de inquilinos (salida de un inquilino / ingreso de otro)
-- Ejecuta esto UNA vez en el SQL Editor de Supabase. Es aditiva y segura:
-- no borra pagos ni apartamentos. Se puede volver a ejecutar sin problema.
--
-- Qué hace:
--  1) Crea la tabla inquilinos_historial (ficha archivada de cada inquilino que salió,
--     con la deuda que dejó al salir).
--  2) Cada periodo (alquiler, electricidad, agua) guarda el nombre del inquilino de ese
--     momento y, cuando el inquilino sale, queda "cerrado" a nombre de su ficha.
--     Así la deuda del que se fue NO pasa al nuevo inquilino.
--  3) Crea la función registrar_salida_inquilino(), que hace todo el proceso de salida
--     de una sola vez (si algo falla, no se guarda nada a medias).
-- ============================================================

-- Por si todavía no corriste migracion_dia_pago.sql
alter table apartamentos add column if not exists dia_pago int;

-- ---------- 1) Ficha archivada de inquilinos que salieron ----------
create table if not exists inquilinos_historial (
    id bigserial primary key,
    apartamento_id bigint not null references apartamentos(id) on delete cascade,
    inquilino_nombre text,
    celular text,
    cedula_identidad text,
    nacionalidad text,
    fecha_nacimiento date,
    referencia_nombre text,
    referencia_parentesco text,
    referencia_celular text,
    fecha_ingreso date,
    fecha_salida date not null,
    garantia text,
    monto_alquiler numeric(10,2),
    dia_pago int,
    tipo_contrato text,
    estado_contrato text,
    contrato_fecha_inicio date,
    contrato_fecha_fin date,
    contrato_observaciones text,
    observacion_salida text,
    deuda_alquiler numeric(10,2) not null default 0,      -- deuda al momento de salir
    deuda_electricidad numeric(10,2) not null default 0,
    deuda_agua numeric(10,2) not null default 0,
    registrado_por text,
    created_at timestamptz default now()
);
create index if not exists idx_inq_hist_apartamento on inquilinos_historial (apartamento_id);
alter table inquilinos_historial disable row level security;

-- ---------- 2) Periodos: inquilino de ese momento + cierre al salir ----------
alter table periodos_alquiler add column if not exists inquilino_nombre text;
alter table periodos_alquiler add column if not exists inquilino_historial_id bigint
    references inquilinos_historial(id) on delete set null;

alter table periodos_electricidad add column if not exists inquilino_nombre text;
alter table periodos_electricidad add column if not exists inquilino_historial_id bigint
    references inquilinos_historial(id) on delete set null;

alter table periodos_agua add column if not exists inquilino_nombre text;
alter table periodos_agua add column if not exists inquilino_historial_id bigint
    references inquilinos_historial(id) on delete set null;

-- Los periodos que ya existen pasan a llevar el nombre del inquilino actual del apartamento
update periodos_alquiler p set inquilino_nombre = a.inquilino_nombre
    from apartamentos a where a.id = p.apartamento_id and p.inquilino_nombre is null;
update periodos_electricidad p set inquilino_nombre = a.inquilino_nombre
    from apartamentos a where a.id = p.apartamento_id and p.inquilino_nombre is null;
update periodos_agua p set inquilino_nombre = a.inquilino_nombre
    from apartamentos a where a.id = p.apartamento_id and p.inquilino_nombre is null;

-- Antes: solo podía existir UN periodo por apartamento/mes/año. Ahora puede haber uno del
-- inquilino que salió (cerrado) y otro del nuevo inquilino en el mismo mes.
do $$
declare r record;
begin
    for r in
        select c.conname, c.conrelid::regclass::text as tbl
        from pg_constraint c
        where c.contype = 'u'
          and c.conrelid::regclass::text in ('periodos_alquiler', 'periodos_electricidad', 'periodos_agua')
    loop
        execute format('alter table %s drop constraint %I', r.tbl, r.conname);
    end loop;
end $$;

create unique index if not exists uq_periodos_alquiler_activo
    on periodos_alquiler (apartamento_id, mes, anio, coalesce(inquilino_historial_id, 0));
create unique index if not exists uq_periodos_electricidad_activo
    on periodos_electricidad (apartamento_id, mes, anio, coalesce(inquilino_historial_id, 0));
create unique index if not exists uq_periodos_agua_activo
    on periodos_agua (apartamento_id, mes, anio, coalesce(inquilino_historial_id, 0));

create index if not exists idx_periodos_alq_hist on periodos_alquiler (inquilino_historial_id);
create index if not exists idx_periodos_elec_hist on periodos_electricidad (inquilino_historial_id);
create index if not exists idx_periodos_agua_hist on periodos_agua (inquilino_historial_id);

-- ---------- 3) Registrar la salida de un inquilino (todo o nada) ----------
create or replace function registrar_salida_inquilino(
    p_apartamento_id bigint,
    p_fecha_salida date,
    p_observacion text,
    p_registrado_por text
) returns bigint
language plpgsql
as $$
declare
    a apartamentos%rowtype;
    v_hist_id bigint;
    d_alq numeric := 0;
    d_elec numeric := 0;
    d_agua numeric := 0;
begin
    select * into a from apartamentos where id = p_apartamento_id for update;
    if not found then
        raise exception 'Apartamento no encontrado';
    end if;

    -- Deuda pendiente del inquilino actual (solo periodos todavía abiertos)
    select coalesce(sum(greatest(0, pe.monto_esperado
               - coalesce((select sum(g.monto) from pagos g where g.periodo_id = pe.id), 0))), 0)
      into d_alq
      from periodos_alquiler pe
     where pe.apartamento_id = a.id and pe.inquilino_historial_id is null;

    select coalesce(sum(greatest(0, pe.monto_esperado
               - coalesce((select sum(g.monto) from pagos_electricidad g where g.periodo_id = pe.id), 0))), 0)
      into d_elec
      from periodos_electricidad pe
     where pe.apartamento_id = a.id and pe.inquilino_historial_id is null;

    select coalesce(sum(greatest(0, pe.monto_esperado
               - coalesce((select sum(g.monto) from pagos_agua g where g.periodo_id = pe.id), 0))), 0)
      into d_agua
      from periodos_agua pe
     where pe.apartamento_id = a.id and pe.inquilino_historial_id is null;

    -- Archivar la ficha del inquilino
    insert into inquilinos_historial (
        apartamento_id, inquilino_nombre, celular, cedula_identidad, nacionalidad, fecha_nacimiento,
        referencia_nombre, referencia_parentesco, referencia_celular, fecha_ingreso, fecha_salida,
        garantia, monto_alquiler, dia_pago, tipo_contrato, estado_contrato,
        contrato_fecha_inicio, contrato_fecha_fin, contrato_observaciones, observacion_salida,
        deuda_alquiler, deuda_electricidad, deuda_agua, registrado_por
    ) values (
        a.id, a.inquilino_nombre, a.celular, a.cedula_identidad, a.nacionalidad, a.fecha_nacimiento,
        a.referencia_nombre, a.referencia_parentesco, a.referencia_celular, a.fecha_ingreso, p_fecha_salida,
        a.garantia, a.monto_alquiler, a.dia_pago, a.tipo_contrato, a.estado_contrato,
        a.contrato_fecha_inicio, a.contrato_fecha_fin, a.contrato_observaciones, p_observacion,
        d_alq, d_elec, d_agua, p_registrado_por
    ) returning id into v_hist_id;

    -- Cerrar los periodos del inquilino: quedan a su nombre y ya no cuentan para el nuevo
    update periodos_alquiler
       set inquilino_historial_id = v_hist_id,
           inquilino_nombre = coalesce(inquilino_nombre, a.inquilino_nombre)
     where apartamento_id = a.id and inquilino_historial_id is null;
    update periodos_electricidad
       set inquilino_historial_id = v_hist_id,
           inquilino_nombre = coalesce(inquilino_nombre, a.inquilino_nombre)
     where apartamento_id = a.id and inquilino_historial_id is null;
    update periodos_agua
       set inquilino_historial_id = v_hist_id,
           inquilino_nombre = coalesce(inquilino_nombre, a.inquilino_nombre)
     where apartamento_id = a.id and inquilino_historial_id is null;

    -- Dejar el apartamento libre (se conservan: código, piso, monto de alquiler, amoblado y detalle)
    update apartamentos
       set estado = 'Desocupado',
           inquilino_nombre = null, celular = null, cedula_identidad = null, nacionalidad = null,
           fecha_nacimiento = null, referencia_nombre = null, referencia_parentesco = null,
           referencia_celular = null, fecha_ingreso = null, garantia = null, dia_pago = null,
           tipo_contrato = null, estado_contrato = 'Sin Contrato',
           contrato_fecha_inicio = null, contrato_fecha_fin = null, contrato_observaciones = null
     where id = a.id;

    return v_hist_id;
end;
$$;

-- Le avisa a Supabase que hay una función nueva
notify pgrst, 'reload schema';
