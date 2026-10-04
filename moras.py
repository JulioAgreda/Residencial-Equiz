"""
Cálculo de moras (deudas) por apartamento: alquiler, electricidad y agua.

Módulo sin dependencias de Streamlit ni de la base: recibe listas de diccionarios y devuelve
filas listas para mostrar. Así se puede probar de forma aislada.

Reglas:
  * Solo cuenta la deuda del inquilino ACTUAL (periodos abiertos) de apartamentos "Ocupado".
  * Alquiler: se usa la "deuda real" (ver deuda_real_inquilino): meses con saldo pendiente cuyo
    día de pago ya pasó, MÁS los meses sin ningún registro entre el primer mes registrado (o la
    fecha de ingreso) y hoy. No aplica a contratos de anticrético.
    Día de pago: campo «Día de Pago» de la ficha; si no hay, el día de la fecha de ingreso; si
    tampoco, el 1.
  * Electricidad y agua: toda factura registrada con saldo pendiente es deuda (la lectura ya se
    cobró al registrarla). No se inventan meses sin lectura.
"""
import calendar
from datetime import date

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
_MES_NUM = {m: i + 1 for i, m in enumerate(MESES)}

_TOLERANCIA = 0.009  # evita contar como deuda diferencias de centavos por redondeo


def _a_fecha(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _dia_de_pago(apt):
    """Día del mes en que vence el alquiler de este apartamento."""
    dia = apt.get("dia_pago")
    if dia:
        try:
            return int(dia)
        except (TypeError, ValueError):
            pass
    ingreso = _a_fecha(apt.get("fecha_ingreso"))
    return ingreso.day if ingreso else 1


def _vencimiento(apt, anio, mes_num):
    ultimo = calendar.monthrange(anio, mes_num)[1]
    return date(anio, mes_num, min(_dia_de_pago(apt), ultimo))


def _pagado(periodo, campo_pagos):
    return sum(float(p.get("monto") or 0) for p in (periodo.get(campo_pagos) or []))


def _agrupar(deudas_por_apt, apartamentos_por_id):
    """deudas_por_apt: {apt_id: [deuda_de_cada_mes_atrasado]} -> filas ordenadas por deuda desc."""
    filas = []
    for apt_id, deudas in deudas_por_apt.items():
        apt = apartamentos_por_id[apt_id]
        filas.append({
            "Departamento": apt.get("codigo") or "—",
            "Inquilino": apt.get("inquilino_nombre") or "—",
            "Meses atrasados": len(deudas),
            "Deuda total": round(sum(deudas), 2),
        })
    filas.sort(key=lambda f: (-f["Deuda total"], f["Departamento"]))
    return filas


def calcular_mora_alquiler(apartamentos, periodos, hoy=None):
    """Filas de mora de alquiler con el MISMO criterio que el estado de cuenta del inquilino."""
    hoy = hoy or date.today()
    por_apt = {}
    for p in periodos:
        por_apt.setdefault(p.get("apartamento_id"), []).append(p)
    filas = []
    for apt in apartamentos:
        d = deuda_real_inquilino(apt, por_apt.get(apt["id"], []), [], hoy)
        if d["aplica"] and d["alquiler"]["deuda"] > _TOLERANCIA:
            filas.append({
                "Departamento": apt.get("codigo") or "—",
                "Inquilino": apt.get("inquilino_nombre") or "—",
                "Meses atrasados": d["alquiler"]["meses_atrasados"],
                "Deuda total": d["alquiler"]["deuda"],
            })
    filas.sort(key=lambda f: (-f["Deuda total"], f["Departamento"]))
    return filas


def calcular_mora_consumo(apartamentos, periodos, campo_pagos, hoy=None):
    """Para electricidad ('pagos_electricidad') y agua ('pagos_agua'): toda factura con saldo pendiente."""
    hoy = hoy or date.today()
    por_id = {a["id"]: a for a in apartamentos if a.get("estado") == "Ocupado"}
    deudas = {}
    for p in periodos:
        apt = por_id.get(p.get("apartamento_id"))
        mes_num = _MES_NUM.get(p.get("mes"))
        if not apt or not mes_num:
            continue
        saldo = float(p.get("monto_esperado") or 0) - _pagado(p, campo_pagos)
        if saldo > _TOLERANCIA:
            deudas.setdefault(apt["id"], []).append(saldo)
    return _agrupar(deudas, por_id)


# ============================================================
# DEUDA REAL POR INQUILINO (estado de cuenta que se entrega al inquilino)
# ============================================================
#
# A diferencia de la mora del Dashboard (que solo mira los meses que ya tienen registro),
# la "deuda real" también cuenta los meses SIN registro: en esta app los periodos de alquiler
# se crean al registrar un pago, así que un inquilino que dejó de pagar no tiene registros de
# los meses siguientes y su deuda quedaría invisible. Aquí esos meses se completan, con el
# alquiler mensual de la ficha, desde el primer mes registrado (o la fecha de ingreso, si
# nunca hubo registros) hasta el mes actual, respetando el día de pago de cada mes.

ESTADO_PAGADO = "Pagado"
ESTADO_PARCIAL = "Parcial"
ESTADO_PENDIENTE = "Pendiente"
ESTADO_SIN_PAGO = "Sin pago"        # mes sin ningún registro (completado por el sistema)
ESTADO_POR_VENCER = "Por vencer"    # aún no llega el día de pago de ese mes


def _meses_entre(desde, hasta):
    """Genera (anio, mes_num) desde 'desde' hasta 'hasta', ambos inclusive."""
    anio, mes = desde
    while (anio, mes) <= hasta:
        yield anio, mes
        mes += 1
        if mes == 13:
            anio, mes = anio + 1, 1


def _ultimo_pago(periodos, campo_pagos):
    mejor = None
    for p in periodos:
        for pg in (p.get(campo_pagos) or []):
            f = _a_fecha(pg.get("fecha"))
            if f and float(pg.get("monto") or 0) > 0 and (mejor is None or f > mejor[0]):
                mejor = (f, float(pg.get("monto") or 0))
    return {"fecha": mejor[0], "monto": mejor[1]} if mejor else None


def _estado_por_saldo(esperado, pagado):
    if esperado - pagado > _TOLERANCIA:
        return ESTADO_PENDIENTE if pagado <= _TOLERANCIA else ESTADO_PARCIAL
    return ESTADO_PAGADO


def _clave_periodo(p):
    mes_num = _MES_NUM.get(p.get("mes"))
    if not mes_num:
        return None
    try:
        return int(p["anio"]), mes_num
    except (KeyError, TypeError, ValueError):
        return None


def deuda_real_inquilino(apt, periodos_alquiler, periodos_electricidad, hoy=None):
    """Estado de cuenta del inquilino actual de UN apartamento.

    periodos_*: periodos abiertos de ese apartamento, cada uno con sus abonos embebidos
    ('pagos' / 'pagos_electricidad', con 'monto' y 'fecha').

    Solo aplica a apartamentos Ocupados cuyo contrato no sea Anticrético (el anticrético no
    paga alquiler mensual); un tipo de contrato vacío se trata como alquiler.
    """
    hoy = hoy or date.today()
    resultado = {"aplica": True, "motivo": None, "fecha_corte": hoy, "deuda_total": 0.0}

    if apt.get("estado") != "Ocupado":
        return {**resultado, "aplica": False, "motivo": "El apartamento está desocupado."}
    if (apt.get("tipo_contrato") or "").strip().lower() in ("anticrético", "anticretico"):
        return {**resultado, "aplica": False,
                "motivo": "Contrato de anticrético: no genera alquiler mensual."}

    # ---------------- Alquiler ----------------
    registrados = {}
    for p in periodos_alquiler or []:
        k = _clave_periodo(p)
        if k:
            registrados.setdefault(k, []).append(p)

    mes_actual = (hoy.year, hoy.month)
    if registrados:
        inicio, completa_desde_ingreso = min(registrados), False
    else:
        ingreso = _a_fecha(apt.get("fecha_ingreso"))
        inicio = (ingreso.year, ingreso.month) if ingreso else mes_actual
        completa_desde_ingreso = ingreso is not None

    monto_ficha = float(apt.get("monto_alquiler") or 0)
    filas_alq, deuda_alq, atrasados, por_vencer = [], 0.0, 0, 0.0

    for clave in _meses_entre(inicio, max(mes_actual, max(registrados) if registrados else mes_actual)):
        anio, mes_num = clave
        etiqueta = f"{MESES[mes_num - 1]} {anio}"
        vencido = hoy > _vencimiento(apt, anio, mes_num)
        if clave in registrados:
            esperado = sum(float(p.get("monto_esperado") or 0) for p in registrados[clave])
            pagado = sum(_pagado(p, "pagos") for p in registrados[clave])
            saldo = round(esperado - pagado, 2)
            estado = _estado_por_saldo(esperado, pagado)
            if saldo > _TOLERANCIA and not vencido:
                estado = ESTADO_POR_VENCER
        else:
            if monto_ficha <= _TOLERANCIA:
                continue
            esperado, pagado, saldo = monto_ficha, 0.0, monto_ficha
            estado = ESTADO_SIN_PAGO if vencido else ESTADO_POR_VENCER
        if saldo <= _TOLERANCIA:
            saldo = 0.0
        elif vencido:
            deuda_alq += saldo
            atrasados += 1
        else:
            por_vencer += saldo
        filas_alq.append({"periodo": etiqueta, "esperado": round(esperado, 2),
                          "pagado": round(pagado, 2), "saldo": round(saldo, 2), "estado": estado})

    ultimo_alq = _ultimo_pago([p for ps in registrados.values() for p in ps], "pagos")
    resultado["alquiler"] = {
        "filas": filas_alq,
        "deuda": round(deuda_alq, 2),
        "meses_atrasados": atrasados,
        "por_vencer": round(por_vencer, 2),
        "pagado_total": round(sum(f["pagado"] for f in filas_alq), 2),
        "ultimo_pago": ultimo_alq,
        "dias_desde_ultimo_pago": (hoy - ultimo_alq["fecha"]).days if ultimo_alq else None,
        "desde_ingreso_sin_registros": completa_desde_ingreso,
    }

    # ---------------- Electricidad ----------------
    # La factura existe desde que se registra la lectura, así que todo saldo pendiente es deuda.
    # No se pueden inventar meses sin lectura (no hay consumo que cobrar).
    elec_validos = [(k, p) for p in (periodos_electricidad or []) if (k := _clave_periodo(p))]
    filas_elec, deuda_elec = [], 0.0
    for clave, p in sorted(elec_validos, key=lambda t: t[0]):
        esperado = float(p.get("monto_esperado") or 0)
        pagado = _pagado(p, "pagos_electricidad")
        saldo = round(esperado - pagado, 2)
        estado = _estado_por_saldo(esperado, pagado)
        if saldo <= _TOLERANCIA:
            saldo = 0.0
        else:
            deuda_elec += saldo
        filas_elec.append({"periodo": f"{MESES[clave[1] - 1]} {clave[0]}", "esperado": round(esperado, 2),
                           "pagado": round(pagado, 2), "saldo": round(saldo, 2), "estado": estado})

    ultimo_elec = _ultimo_pago([p for _k, p in elec_validos], "pagos_electricidad")
    resultado["electricidad"] = {
        "filas": filas_elec,
        "deuda": round(deuda_elec, 2),
        "pagado_total": round(sum(f["pagado"] for f in filas_elec), 2),
        "ultimo_pago": ultimo_elec,
        "dias_desde_ultimo_pago": (hoy - ultimo_elec["fecha"]).days if ultimo_elec else None,
    }

    resultado["deuda_total"] = round(resultado["alquiler"]["deuda"] + resultado["electricidad"]["deuda"], 2)
    return resultado
