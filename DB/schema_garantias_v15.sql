-- EQUISE V15: Garantías de alquiler.
-- Migración aditiva: crea tablas de garantías, daños/cotizaciones y devoluciones.
-- No elimina ni altera los datos históricos de apartamentos, alquileres o anticréticos.

CREATE TABLE IF NOT EXISTS public.garantias_alquiler (
    id bigserial PRIMARY KEY,
    apartamento_id bigint NOT NULL REFERENCES public.apartamentos(id) ON DELETE RESTRICT,
    inquilino_nombre varchar(200) NOT NULL,
    fecha_recepcion date NOT NULL,
    monto_recibido numeric(14,2) NOT NULL CHECK (monto_recibido > 0),
    moneda varchar(3) NOT NULL DEFAULT 'BOB' CHECK (moneda IN ('BOB')),
    monto_alquiler_referencia numeric(14,2) NOT NULL DEFAULT 0 CHECK (monto_alquiler_referencia >= 0),
    medio_recepcion varchar(50),
    comprobante_recepcion varchar(120),
    observacion text,
    estado varchar(40) NOT NULL DEFAULT 'Vigente'
        CHECK (estado IN ('Vigente', 'Pendiente de liquidación', 'Devolución parcial', 'Devuelta')),
    fecha_salida date,
    observacion_salida text,
    registrado_por varchar(160),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_garantias_alquiler_apartamento
    ON public.garantias_alquiler(apartamento_id, fecha_recepcion DESC);
CREATE INDEX IF NOT EXISTS idx_garantias_alquiler_estado
    ON public.garantias_alquiler(estado);

CREATE TABLE IF NOT EXISTS public.danos_garantia_alquiler (
    id bigserial PRIMARY KEY,
    garantia_id bigint NOT NULL REFERENCES public.garantias_alquiler(id) ON DELETE RESTRICT,
    fecha date NOT NULL,
    descripcion text NOT NULL,
    proveedor_cotizacion varchar(200),
    monto_cotizado numeric(14,2) NOT NULL DEFAULT 0 CHECK (monto_cotizado >= 0),
    monto_aprobado numeric(14,2) NOT NULL DEFAULT 0 CHECK (monto_aprobado >= 0),
    comprobante varchar(200),
    observacion text,
    registrado_por varchar(160),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT danos_garantia_aprobado_no_supera_cotizado CHECK (monto_aprobado <= monto_cotizado)
);

CREATE INDEX IF NOT EXISTS idx_danos_garantia_id
    ON public.danos_garantia_alquiler(garantia_id);

CREATE TABLE IF NOT EXISTS public.devoluciones_garantia_alquiler (
    id bigserial PRIMARY KEY,
    garantia_id bigint NOT NULL REFERENCES public.garantias_alquiler(id) ON DELETE RESTRICT,
    fecha date NOT NULL,
    monto numeric(14,2) NOT NULL CHECK (monto > 0),
    medio varchar(50),
    comprobante varchar(120),
    observacion text,
    registrado_por varchar(160),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_devoluciones_garantia_id
    ON public.devoluciones_garantia_alquiler(garantia_id, fecha DESC);

NOTIFY pgrst, 'reload schema';
