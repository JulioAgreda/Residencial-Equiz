-- =====================================================================
-- RESIDENCIAL EQUISE - ROLES RESTRINGIDOS PARA COBROS (DEV/STAGING)
-- Version: 1.0
-- PRECONDICION: ejecutar SOLO en una base de DESARROLLO que ya tenga
--              las tablas operaciones_cobro / aplicaciones_cobro (V1).
-- NO ejecutar en producción. No contiene contraseñas.
-- Ejecutar conectado como administrador de la base (por ejemplo postgres).
-- =====================================================================

begin;

-- 1) Rol propietario de las funciones SECURITY DEFINER.
--    NO puede iniciar sesión. No se concede a la aplicación como membresía.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'equise_cobros_owner') then
    create role equise_cobros_owner nologin noinherit;
  end if;
end
$$;

-- 2) Rol de conexión usado exclusivamente por el backend Streamlit.
--    Se crea sin contraseña; establecerla por un canal seguro después.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'equise_cobros_app') then
    create role equise_cobros_app login noinherit;
  end if;
end
$$;

alter role equise_cobros_app noinherit;

-- 3) Crear un esquema privado para las funciones de cobros.
--    No se expone por PostgREST salvo que se configure expresamente.
create schema if not exists cobros_private authorization equise_cobros_owner;
alter schema cobros_private owner to equise_cobros_owner;
revoke all on schema cobros_private from public;
grant usage on schema cobros_private to equise_cobros_app;
grant create on schema cobros_private to equise_cobros_owner;

-- La conexión app puede conectarse, pero no crear objetos ni acceder a public.
grant connect on database postgres to equise_cobros_app;
revoke all on schema public from equise_cobros_app;

-- La aplicación no recibe privilegios de tabla ni de secuencia.
revoke all privileges on
  public.usuarios,
  public.usuarios_apartamentos,
  public.apartamentos,
  public.inquilinos_historial,
  public.periodos_alquiler,
  public.periodos_electricidad,
  public.periodos_agua,
  public.pagos,
  public.pagos_electricidad,
  public.pagos_agua,
  public.operaciones_cobro,
  public.aplicaciones_cobro
from equise_cobros_app;

-- 4) Privilegios mínimos del propietario de las funciones.
--    La función SECURITY DEFINER correrá con este rol.
grant usage on schema public to equise_cobros_owner;

grant select on
  public.usuarios,
  public.usuarios_apartamentos,
  public.apartamentos,
  public.inquilinos_historial,
  public.periodos_alquiler,
  public.periodos_electricidad,
  public.periodos_agua,
  public.pagos,
  public.pagos_electricidad,
  public.pagos_agua,
  public.operaciones_cobro,
  public.aplicaciones_cobro
to equise_cobros_owner;

grant insert on
  public.operaciones_cobro,
  public.aplicaciones_cobro,
  public.pagos,
  public.pagos_electricidad,
  public.pagos_agua
to equise_cobros_owner;

-- Secuencias identity/serial necesarias para insertar.
-- Ajustar únicamente si los nombres reales de secuencia difieren.
grant usage, select on sequence
  public.operaciones_cobro_id_seq,
  public.aplicaciones_cobro_id_seq,
  public.pagos_id_seq,
  public.pagos_electricidad_id_seq,
  public.pagos_agua_id_seq
to equise_cobros_owner;

-- No otorgar membresía owner a app: evita que la conexión herede sus permisos.
revoke equise_cobros_owner from equise_cobros_app;

commit;

-- =====================================================================
-- CONTRASEÑA: NO escribirla en este archivo ni en Git.
-- Configurarla separadamente mediante un canal seguro de administración.
-- Ejemplo conceptual (reemplazar el marcador fuera de este archivo):
-- ALTER ROLE equise_cobros_app PASSWORD '<CONTRASEÑA_LARGA_ALEATORIA>';
-- =====================================================================

-- VERIFICACIÓN 1: roles y atributos.
select rolname, rolcanlogin, rolinherit, rolsuper, rolbypassrls
from pg_roles
where rolname in ('equise_cobros_owner', 'equise_cobros_app')
order by rolname;

-- VERIFICACIÓN 2: la conexión de aplicación no debe tener DML directo.
select
  has_table_privilege('equise_cobros_app', 'public.operaciones_cobro', 'SELECT') as app_select_operaciones,
  has_table_privilege('equise_cobros_app', 'public.operaciones_cobro', 'INSERT') as app_insert_operaciones,
  has_table_privilege('equise_cobros_app', 'public.pagos', 'INSERT') as app_insert_pagos,
  has_schema_privilege('equise_cobros_app', 'public', 'USAGE') as app_public_usage,
  has_schema_privilege('equise_cobros_app', 'cobros_private', 'USAGE') as app_cobros_schema_usage;

-- Esperado: SELECT/INSERT/INSERT = false; app_public_usage = false;
-- app_cobros_schema_usage = true.

-- VERIFICACIÓN 3: permisos del propietario de funciones.
select
  has_table_privilege('equise_cobros_owner', 'public.usuarios', 'SELECT') as owner_select_usuarios,
  has_table_privilege('equise_cobros_owner', 'public.pagos', 'INSERT') as owner_insert_pagos,
  has_table_privilege('equise_cobros_owner', 'public.operaciones_cobro', 'INSERT') as owner_insert_operaciones;

-- NOTAS IMPORTANTES:
-- A) No se concede EXECUTE todavía: la firma de la función transaccional
--    debe definirse y revisarse antes de otorgarlo.
-- B) No se modifica RLS ni se revocan permisos de anon/authenticated.
-- C) No se cambia ningún dato de negocio ni se migran pagos históricos.
-- D) No conceder equise_cobros_app a anon/authenticated ni viceversa.
-- E) Crear la función en cobros_private, con SECURITY DEFINER y
--    SET search_path = pg_catalog; usar nombres public.tabla totalmente
--    calificados. Luego ALTER FUNCTION ... OWNER TO equise_cobros_owner
--    y GRANT EXECUTE únicamente a equise_cobros_app.
