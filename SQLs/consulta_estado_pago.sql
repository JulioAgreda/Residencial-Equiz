-- Estado de pago por apartamento para un mes/año específico
-- (cámbialos abajo en el where si quieres ver otro periodo)

select
    a.codigo as apartamento,
    a.piso,
    a.inquilino_nombre as inquilino,
    p.monto_esperado,
    coalesce(sum(pg.monto), 0) as pagado,
    p.monto_esperado - coalesce(sum(pg.monto), 0) as deuda,
    case
        when p.id is null then 'Sin registrar'
        when p.monto_esperado - coalesce(sum(pg.monto), 0) <= 0 then 'Pagado'
        when coalesce(sum(pg.monto), 0) > 0 then 'Parcial'
        else 'Pendiente'
    end as estado
from apartamentos a
left join periodos_alquiler p
    on p.apartamento_id = a.id
    and p.mes = 'Septiembre'      -- <- cambia el mes aquí
    and p.anio = 2026             -- <- cambia el año aquí
left join pagos pg
    on pg.periodo_id = p.id
group by a.codigo, a.piso, a.inquilino_nombre, p.id, p.monto_esperado
order by a.codigo;
