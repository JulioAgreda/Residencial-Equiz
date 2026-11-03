-- EQUISE V16: integración de garantías con tesorería (entradas y salidas reales).
-- Ejecutar después de schema_garantias_v15.sql. No elimina datos históricos.
-- Los depósitos de garantía NO se clasifican como ingresos operativos.
-- Los reembolsos NO se clasifican como gastos operativos.

CREATE TABLE IF NOT EXISTS public.movimientos_tesoreria (
    id bigserial PRIMARY KEY,
    fecha date NOT NULL,
    direccion varchar(10) NOT NULL CHECK (direccion IN ('ENTRADA', 'SALIDA')),
    categoria varchar(50) NOT NULL,
    concepto varchar(200) NOT NULL,
    monto numeric(14,2) NOT NULL CHECK (monto > 0),
    moneda varchar(3) NOT NULL DEFAULT 'BOB' CHECK (moneda = 'BOB'),
    medio varchar(50),
    comprobante varchar(120),
    origen_tipo varchar(60) NOT NULL,
    origen_id bigint NOT NULL,
    apartamento_id bigint REFERENCES public.apartamentos(id) ON DELETE RESTRICT,
    persona varchar(200),
    registrado_por varchar(160),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT movimientos_tesoreria_origen_unico UNIQUE (origen_tipo, origen_id)
);

CREATE INDEX IF NOT EXISTS idx_movimientos_tesoreria_fecha
    ON public.movimientos_tesoreria(fecha DESC);
CREATE INDEX IF NOT EXISTS idx_movimientos_tesoreria_apartamento
    ON public.movimientos_tesoreria(apartamento_id, fecha DESC);

-- Impide dos garantías vigentes simultáneas para el mismo apartamento.
CREATE UNIQUE INDEX IF NOT EXISTS uq_garantia_alquiler_vigente_apartamento
    ON public.garantias_alquiler(apartamento_id)
    WHERE estado = 'Vigente';

-- Permite cerrar una garantía cuando el importe retenido por daños cubre todo el depósito.
ALTER TABLE public.garantias_alquiler
    DROP CONSTRAINT IF EXISTS garantias_alquiler_estado_check;
ALTER TABLE public.garantias_alquiler
    ADD CONSTRAINT garantias_alquiler_estado_check
    CHECK (estado IN (
        'Vigente', 'Pendiente de liquidación', 'Devolución parcial',
        'Devuelta', 'Liquidada sin devolución', 'Liquidada'
    ));

CREATE OR REPLACE FUNCTION public.registrar_garantia_y_movimiento(p_payload jsonb)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_id bigint;
    v_apartamento_id bigint;
    v_monto numeric(14,2);
BEGIN
    v_apartamento_id := (p_payload->>'apartamento_id')::bigint;
    v_monto := (p_payload->>'monto_recibido')::numeric;

    IF v_monto IS NULL OR v_monto <= 0 THEN
        RAISE EXCEPTION 'El monto de garantía debe ser mayor a cero';
    END IF;

    INSERT INTO public.garantias_alquiler (
        apartamento_id, inquilino_nombre, fecha_recepcion, monto_recibido,
        moneda, monto_alquiler_referencia, medio_recepcion,
        comprobante_recepcion, observacion, estado, registrado_por
    ) VALUES (
        v_apartamento_id,
        p_payload->>'inquilino_nombre',
        (p_payload->>'fecha_recepcion')::date,
        v_monto,
        COALESCE(p_payload->>'moneda', 'BOB'),
        COALESCE((p_payload->>'monto_alquiler_referencia')::numeric, 0),
        p_payload->>'medio_recepcion',
        p_payload->>'comprobante_recepcion',
        p_payload->>'observacion',
        'Vigente',
        p_payload->>'registrado_por'
    )
    RETURNING id INTO v_id;

    INSERT INTO public.movimientos_tesoreria (
        fecha, direccion, categoria, concepto, monto, moneda, medio,
        comprobante, origen_tipo, origen_id, apartamento_id, persona, registrado_por
    ) VALUES (
        (p_payload->>'fecha_recepcion')::date,
        'ENTRADA',
        'GARANTIA_ALQUILER',
        'Recepción de garantía de alquiler',
        v_monto,
        COALESCE(p_payload->>'moneda', 'BOB'),
        p_payload->>'medio_recepcion',
        p_payload->>'comprobante_recepcion',
        'GARANTIA_ALQUILER',
        v_id,
        v_apartamento_id,
        p_payload->>'inquilino_nombre',
        p_payload->>'registrado_por'
    );

    RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.registrar_devolucion_garantia_y_movimiento(p_payload jsonb)
RETURNS bigint
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_devolucion_id bigint;
    v_garantia_id bigint;
    v_apartamento_id bigint;
    v_persona text;
    v_capital numeric(14,2);
    v_danos numeric(14,2);
    v_devuelto numeric(14,2);
    v_monto numeric(14,2);
BEGIN
    v_garantia_id := (p_payload->>'garantia_id')::bigint;
    v_monto := (p_payload->>'monto')::numeric;

    SELECT apartamento_id, inquilino_nombre, monto_recibido
      INTO v_apartamento_id, v_persona, v_capital
      FROM public.garantias_alquiler
     WHERE id = v_garantia_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe la garantía indicada';
    END IF;

    SELECT COALESCE(SUM(monto_aprobado), 0)
      INTO v_danos
      FROM public.danos_garantia_alquiler
     WHERE garantia_id = v_garantia_id;

    SELECT COALESCE(SUM(monto), 0)
      INTO v_devuelto
      FROM public.devoluciones_garantia_alquiler
     WHERE garantia_id = v_garantia_id;

    IF v_monto IS NULL OR v_monto <= 0 OR v_monto > (v_capital - v_danos - v_devuelto) THEN
        RAISE EXCEPTION 'La devolución supera el saldo disponible de la garantía';
    END IF;

    INSERT INTO public.devoluciones_garantia_alquiler (
        garantia_id, fecha, monto, medio, comprobante, observacion, registrado_por
    ) VALUES (
        v_garantia_id,
        (p_payload->>'fecha')::date,
        v_monto,
        p_payload->>'medio',
        p_payload->>'comprobante',
        p_payload->>'observacion',
        p_payload->>'registrado_por'
    )
    RETURNING id INTO v_devolucion_id;

    INSERT INTO public.movimientos_tesoreria (
        fecha, direccion, categoria, concepto, monto, moneda, medio,
        comprobante, origen_tipo, origen_id, apartamento_id, persona, registrado_por
    ) VALUES (
        (p_payload->>'fecha')::date,
        'SALIDA',
        'DEVOLUCION_GARANTIA_ALQUILER',
        'Devolución de garantía de alquiler',
        v_monto,
        'BOB',
        p_payload->>'medio',
        p_payload->>'comprobante',
        'DEVOLUCION_GARANTIA_ALQUILER',
        v_devolucion_id,
        v_apartamento_id,
        v_persona,
        p_payload->>'registrado_por'
    );

    -- Actualiza el estado dentro de la misma transacción del reembolso.
    SELECT COALESCE(SUM(monto), 0)
      INTO v_devuelto
      FROM public.devoluciones_garantia_alquiler
     WHERE garantia_id = v_garantia_id;

    IF v_devuelto + v_danos >= v_capital - 0.001 THEN
        UPDATE public.garantias_alquiler
           SET estado = 'Liquidada'
         WHERE id = v_garantia_id;
    ELSE
        UPDATE public.garantias_alquiler
           SET estado = 'Devolución parcial'
         WHERE id = v_garantia_id;
    END IF;

    RETURN v_devolucion_id;
END;
$$;

-- El cliente de la aplicación usa la clave anon. Los RPC solo exponen estas dos operaciones
-- validadas; no se conceden permisos directos nuevos sobre la tabla de tesorería.
REVOKE ALL ON FUNCTION public.registrar_garantia_y_movimiento(jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.registrar_devolucion_garantia_y_movimiento(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.registrar_garantia_y_movimiento(jsonb) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.registrar_devolucion_garantia_y_movimiento(jsonb) TO anon, authenticated;


CREATE OR REPLACE FUNCTION public.listar_movimientos_garantias_tesoreria()
RETURNS TABLE (
    id bigint, fecha date, direccion varchar, categoria varchar, concepto varchar,
    monto numeric, moneda varchar, medio varchar, comprobante varchar,
    apartamento_id bigint, persona varchar, registrado_por varchar
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT m.id, m.fecha, m.direccion, m.categoria, m.concepto,
           m.monto, m.moneda, m.medio, m.comprobante,
           m.apartamento_id, m.persona, m.registrado_por
      FROM public.movimientos_tesoreria m
     WHERE m.categoria IN ('GARANTIA_ALQUILER', 'DEVOLUCION_GARANTIA_ALQUILER')
     ORDER BY m.fecha DESC, m.id DESC;
$$;

REVOKE ALL ON FUNCTION public.listar_movimientos_garantias_tesoreria() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.listar_movimientos_garantias_tesoreria() TO anon, authenticated;
REVOKE ALL ON TABLE public.movimientos_tesoreria FROM anon, authenticated;

NOTIFY pgrst, 'reload schema';
