-- ============================================================
-- MIGRACIÓN: Usuarios, roles y permisos
-- Ejecuta esto en el SQL Editor de Supabase. Es aditivo.
-- ============================================================

create table if not exists usuarios (
    id bigserial primary key,
    username varchar(50) unique not null,
    nombre varchar(150),
    password_hash text not null,
    rol varchar(20) not null default 'Cobrador',  -- 'Administrador' | 'Cobrador'
    activo boolean not null default true,
    created_at timestamptz default now()
);

alter table usuarios disable row level security;

-- No insertamos ningún usuario aquí: la app te guiará para crear
-- el primer Administrador la primera vez que entres, de forma segura
-- (la contraseña se cifra en la app antes de guardarse, nunca en SQL).
