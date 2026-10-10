-- ============================================================
-- Acceso de cada usuario a ciertos apartamentos — Residencial EQUIZ
--   usuarios.acceso_todos_apartamentos : verdadero = ve todos los apartamentos (valor por defecto);
--                                        falso = ve solo los asignados en usuarios_apartamentos.
--   usuarios_apartamentos              : apartamentos asignados a cada usuario.
--
-- Ejecutar completo en el SQL Editor de Supabase. Es SEGURO y repetible: solo AGREGA una columna y una tabla
-- ("if not exists"); no borra ni modifica datos. Todos los usuarios que ya existen quedan con acceso a TODOS los
-- apartamentos, así que nadie pierde acceso al activar esta función. El administrador asigna desde Usuarios.
-- ============================================================

alter table usuarios add column if not exists acceso_todos_apartamentos boolean not null default true;

create table if not exists usuarios_apartamentos (
    usuario_id bigint not null references usuarios(id) on delete cascade,
    apartamento_id bigint not null references apartamentos(id) on delete cascade,
    created_at timestamptz default now(),
    primary key (usuario_id, apartamento_id)
);
create index if not exists idx_usuarios_apartamentos_apto on usuarios_apartamentos (apartamento_id);

-- Igual que el resto de las tablas de la app (acceso con la clave "anon" detrás del login de la app).
alter table usuarios_apartamentos disable row level security;

-- Verificación: deben aparecer la columna y la tabla
select 'columna usuarios.acceso_todos_apartamentos' as elemento, count(*)::text as encontrado
from information_schema.columns
where table_schema = 'public' and table_name = 'usuarios' and column_name = 'acceso_todos_apartamentos'
union all
select 'tabla usuarios_apartamentos', count(*)::text
from information_schema.tables where table_schema = 'public' and table_name = 'usuarios_apartamentos';
