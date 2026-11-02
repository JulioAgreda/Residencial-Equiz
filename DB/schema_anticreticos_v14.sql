-- EQUISE V14: datos específicos para contratos de anticrético.
-- Ejecutar una sola vez en Supabase SQL Editor antes de desplegar los archivos Python.
-- Esta migración agrega columnas; no elimina ni modifica registros históricos.

ALTER TABLE public.apartamentos
    ADD COLUMN IF NOT EXISTS monto_anticretico numeric(14,2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS anticretico_moneda varchar(3) NOT NULL DEFAULT 'BOB',
    ADD COLUMN IF NOT EXISTS anticretico_fecha_entrega date,
    ADD COLUMN IF NOT EXISTS anticretico_fecha_devolucion date,
    ADD COLUMN IF NOT EXISTS anticretico_condiciones text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'apartamentos_anticretico_moneda_check'
    ) THEN
        ALTER TABLE public.apartamentos
        ADD CONSTRAINT apartamentos_anticretico_moneda_check
        CHECK (anticretico_moneda IN ('BOB', 'USD'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.devoluciones_anticretico (
    id bigserial PRIMARY KEY,
    apartamento_id bigint NOT NULL
        REFERENCES public.apartamentos(id) ON DELETE RESTRICT,
    fecha date NOT NULL,
    monto numeric(14,2) NOT NULL CHECK (monto > 0),
    medio_devolucion varchar(50),
    comprobante varchar(120),
    observacion text,
    registrado_por varchar(160),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_devoluciones_anticretico_apartamento_fecha
    ON public.devoluciones_anticretico(apartamento_id, fecha DESC);

-- Recarga del esquema REST de Supabase después de crear las columnas y tabla.
NOTIFY pgrst, 'reload schema';
