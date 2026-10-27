"""
Conciliación bancaria: compara el extracto del banco con lo registrado en el sistema y dice qué coincide y qué no.

  * Un CRÉDITO del banco (entra dinero) se compara con los INGRESOS del sistema (pagos de alquiler, luz y agua, y ventas).
    Un DÉBITO (sale dinero) se compara con los EGRESOS (pagos y compras).
  * Por defecto solo se comparan los registros que NO son en efectivo (QR, transferencia, tarjeta, sin método), porque el
    efectivo no pasa por el banco. Opcionalmente se incluye el efectivo (por si se depositó).
  * Coinciden cuando el monto es exacto y la fecha está dentro de unos días de diferencia (3 por defecto). Se aceptan también
    los pagos DIVIDIDOS en cualquiera de los dos sentidos:
        - un movimiento del banco = varios registros del sistema («Alquiler y energía» pagado de una vez);
        - varios movimientos del banco = un registro del sistema (una compra pagada en dos partes).
    Para elegir entre varias posibilidades se usan pistas del texto: el apartamento («PB-04», «PP - APARTAMENTO 3»),
    el concepto (alquiler, energía/luz, agua) y las palabras que se repiten.
  * Lo que no coincide se explica: del lado del banco («está en el banco pero no en el sistema»: probablemente falta
    registrarlo, o está registrado con otro monto, otra fecha o en efectivo) y del lado del sistema («está registrado pero no
    aparece en el banco»).

Módulo sin dependencias de Streamlit ni de la base: recibe los movimientos ya leídos (extracto.py) y los del sistema.
"""
import re
import unicodedata
from datetime import date
from itertools import combinations

import cuadre as cd

INGRESO, EGRESO = "Ingreso", "Egreso"
DIAS_POR_DEFECTO = 3
VENTANA_AGRUPADA = 10            # días de margen para unir varios movimientos del banco con un solo registro
MARGEN_CANDIDATOS = 45           # hasta cuántos días se busca un registro «parecido» para explicar una diferencia
MAX_CANDIDATOS = 14              # candidatos que se combinan entre sí (limita el tiempo de cálculo)
MAX_PIEZAS = 5
METODOS_BANCARIOS = ("QR", "Transferencia", "Tarjeta", "Otro", "Sin método")

ALTA, MEDIA, REVISAR = "Alta", "Media", "Revisar"
UNO_A_UNO, BANCO_VARIOS, VARIOS_BANCO = "1 a 1", "1 banco = varios registros", "Varios banco = 1 registro"

_STOP = {"pago", "pagos", "compra", "compras", "para", "desde", "hasta", "mes", "meses", "inquilino", "banco", "como", "cuenta",
         "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre", "octubre", "noviembre",
         "diciembre", "alquiler", "alquile", "energia", "electricidad", "agua", "luz", "sabe", "este", "esta", "pero"}
_RE_APTO = re.compile(r"(?<![a-z0-9])(pb|pp|sp|tp)\s*(?:apartamento\s*|apto\s*|depto\s*|dpto\s*)?0*(\d{1,2})(?!\d)")


def _norm(texto):
    t = unicodedata.normalize("NFD", str(texto if texto is not None else ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def centavos(monto):
    return int(round(abs(float(monto or 0)) * 100))


def clave_apartamento(texto):
    """'PB-04', 'Pb04' y 'PB - APARTAMENTO 4' -> 'PB-04'. None si el texto no menciona un apartamento."""
    m = _RE_APTO.search(_norm(texto))
    return f"{m.group(1).upper()}-{int(m.group(2)):02d}" if m else None


def conceptos(texto):
    """Conceptos que menciona un texto: {'Alquiler', 'Luz', 'Agua'}."""
    n = _norm(texto)
    encontrados = set()
    if "alquil" in n:
        encontrados.add("Alquiler")
    if "energia" in n or "electric" in n or re.search(r"\bluz\b", n):
        encontrados.add("Luz")
    if re.search(r"\bagua\b", n):
        encontrados.add("Agua")
    return encontrados


def _palabras(texto, minimo=4):
    return {p for p in _norm(texto).split() if len(p) >= minimo and not p.isdigit() and p not in _STOP}


def _fmt_fecha(f):
    return f.strftime("%d/%m/%Y") if f else "—"


def _fmt_monto(centavos_):
    return f"{centavos_ / 100:,.2f}"


# ============================================================
# Preparación de los dos lados
# ============================================================

def unificar_sistema(movs_inquilinos, movs_cuadre):
    """Movimientos del sistema en una sola lista.
    movs_inquilinos: pagos de alquiler/luz/agua (los 'movimientos' de rendicion.construir_rendicion, incluyen a los ex inquilinos).
    movs_cuadre: ventas, pagos y compras (los de cuadre.construir_movimientos)."""
    sis = []
    for m in movs_inquilinos or []:
        metodo_original = m.get("metodo") or ""
        sis.append({"origen": m["concepto"], "tipo": INGRESO, "fecha": m["fecha"], "monto": m["monto"], "apartamento": m.get("apartamento") or "",
                    "persona": m.get("inquilino") or "", "categoria": "", "periodo": m.get("periodo") or "",
                    "detalle": " ".join(x for x in (f"{m['concepto']} {m.get('periodo') or ''}".strip(), m.get("observacion") or "") if x),
                    "metodo": cd.grupo_metodo("" if metodo_original == "—" else metodo_original), "metodo_original": metodo_original})
    for m in movs_cuadre or []:
        sis.append({"origen": m["origen"], "tipo": m["tipo"], "fecha": m["fecha"], "monto": m["monto"], "apartamento": "",
                    "persona": m.get("persona") or "", "categoria": m.get("categoria") or "", "periodo": "",
                    "detalle": m.get("detalle") or "", "metodo": m.get("metodo") or "Sin método",
                    "metodo_original": m.get("metodo_original") or ""})
    return sis


def _preparar_banco(lineas, palabras_excluir):
    claves = [k for k in (_norm(p) for p in palabras_excluir or ()) if k]
    salida = []
    for i, l in enumerate(lineas):
        completo = _norm(f"{l.get('contraparte', '')} {l.get('detalle', '')} {l.get('transaccion', '')}")
        palabra = next((k for k in claves if k in completo), None)
        cents = centavos(l["monto"])
        b = dict(l)
        b.update({"idx": i, "cents": cents, "dir": INGRESO if l["monto"] > 0 else EGRESO,
                  "apt": clave_apartamento(l.get("detalle", "")) or clave_apartamento(l.get("contraparte", "")),
                  "conceptos": conceptos(l.get("detalle", "")), "palabras": _palabras(f"{l.get('contraparte', '')} {l.get('detalle', '')}"),
                  "contraparte_norm": _norm(l.get("contraparte", "")),
                  "excluido": cents == 0 or palabra is not None,
                  "motivo_exclusion": "monto cero" if cents == 0 else (f"contiene «{palabra}»" if palabra else "")})
        salida.append(b)
    return salida


def _preparar_sistema(movs):
    salida = []
    for i, m in enumerate(movs):
        s = dict(m)
        s.update({"idx": i, "cents": centavos(m["monto"]), "dir": m["tipo"], "apt": clave_apartamento(m.get("apartamento", "")),
                  "palabras": _palabras(f"{m.get('persona', '')} {m.get('detalle', '')} {m.get('categoria', '')}", 3)})
        salida.append(s)
    return salida


# ============================================================
# Puntaje de parecido
# ============================================================

def _afinidad(b, s):
    """(puntos, razones): cuánto se parecen los textos del movimiento del banco y del registro del sistema."""
    pts, razones = 0, []
    if b["apt"] and s["apt"]:
        if b["apt"] == s["apt"]:
            pts += 40
            razones.append(f"mismo apartamento ({b['apt']})")
        else:
            pts -= 40
    if b["conceptos"] and s["origen"] in b["conceptos"]:
        pts += 15
        razones.append(f"mismo concepto ({s['origen'].lower()})")
    comunes = b["palabras"] & s["palabras"]
    if comunes:
        pts += min(10 * len(comunes), 30)
        razones.append("coincide: " + ", ".join(sorted(comunes)))
    return pts, razones


def _dias(b, s):
    return abs((b["fecha"] - s["fecha"]).days)


# ============================================================
# Combinaciones de pagos divididos
# ============================================================

def _combinaciones(candidatos, objetivo, minimo=2, maximo=MAX_PIEZAS):
    """Todas las combinaciones de 2 a 5 candidatos cuya suma es exactamente `objetivo` (en centavos)."""
    candidatos = candidatos[:MAX_CANDIDATOS]
    for n in range(minimo, min(maximo, len(candidatos)) + 1):
        for combo in combinations(candidatos, n):
            if sum(c["cents"] for c in combo) == objetivo:
                yield combo


def _evaluar_banco_varios(b, combo):
    """Corroboración de 'un movimiento del banco = varios registros': (nivel, puntaje, razones)."""
    apts = {s["apt"] for s in combo}
    apto_coincide = b["apt"] is not None and apts == {b["apt"]}
    mismo_apto = None not in apts and len(apts) == 1
    mismo_dia = all(s["fecha"] == b["fecha"] for s in combo)
    texto = bool(b["palabras"] & set().union(*(s["palabras"] for s in combo))) or bool(b["conceptos"] & {s["origen"] for s in combo})
    razones = []
    if apto_coincide:
        razones.append(f"todos son del apartamento {b['apt']}")
    elif mismo_apto:
        razones.append("todos son del mismo apartamento")
    if texto:
        razones.append("el texto coincide (concepto o palabras)")
    if mismo_dia:
        razones.append("misma fecha")
    if apto_coincide:
        nivel = ALTA
    elif mismo_apto or texto:
        nivel = MEDIA
    elif mismo_dia and len(combo) == 2:
        nivel = REVISAR
    else:
        return None
    puntaje = (apto_coincide * 8 + mismo_apto * 4 + texto * 2 + mismo_dia, -len(combo), -sum(_dias(b, s) for s in combo))
    return nivel, puntaje, razones


def _evaluar_sistema_varios(s, combo):
    """Corroboración de 'varios movimientos del banco = un registro': (nivel, puntaje, razones)."""
    mismas_contrapartes = len({b["contraparte_norm"] for b in combo}) == 1 and combo[0]["contraparte_norm"] != ""
    texto = bool(s["palabras"] & set().union(*(b["palabras"] for b in combo))) or any(
        b["apt"] and b["apt"] == s["apt"] for b in combo) or bool(s["origen"] in set().union(*(b["conceptos"] for b in combo)))
    razones = []
    if mismas_contrapartes:
        razones.append("todos los pagos son de la misma persona o empresa")
    if texto:
        razones.append("el texto coincide")
    if mismas_contrapartes and texto:
        nivel = ALTA
    elif mismas_contrapartes or texto:
        nivel = MEDIA
    else:
        return None
    return nivel, (mismas_contrapartes * 4 + texto * 2, -len(combo), -sum(_dias(b, s) for b in combo)), razones


# ============================================================
# Conciliación
# ============================================================

def conciliar(lineas_banco, movs_sistema, dias=DIAS_POR_DEFECTO, incluir_efectivo=False, palabras_excluir=(), desde=None, hasta=None):
    """Concilia el extracto con el sistema. Devuelve un diccionario con:
      'pares'              coincidencias: {'banco': [movimientos], 'sistema': [registros], 'union', 'confianza', 'dias', 'razones'}
      'banco_sin_registro' movimientos del banco sin registro: {'linea', 'causas', 'sugerencia'}
      'sistema_sin_banco'  registros del sistema sin movimiento en el banco: {'mov', 'causas'}
      'excluidos'          movimientos del banco que se dejaron fuera a propósito (palabras clave)
      'efectivo'           registros en efectivo que no se compararon
      'resumen'            totales para mostrar y exportar
    desde / hasta: periodo que cubre el extracto (por defecto, de la primera a la última fecha del banco)."""
    if not lineas_banco:
        raise ValueError("El extracto no tiene movimientos.")
    banco = _preparar_banco(lineas_banco, palabras_excluir)
    sistema_todo = _preparar_sistema(movs_sistema or [])
    desde = desde or min(b["fecha"] for b in banco)
    hasta = hasta or max(b["fecha"] for b in banco)
    efectivo = [s for s in sistema_todo if s["metodo"] == "Efectivo"] if not incluir_efectivo else []
    sistema = [s for s in sistema_todo if incluir_efectivo or s["metodo"] != "Efectivo"]
    for s in sistema_todo:
        s["en_periodo"] = desde <= s["fecha"] <= hasta

    libres_b = {b["idx"]: b for b in banco if not b["excluido"]}
    libres_s = {s["idx"]: s for s in sistema}
    pares = []

    def registrar(bancos, sistemas, union, confianza, razones):
        for b in bancos:
            libres_b.pop(b["idx"], None)
        for s in sistemas:
            libres_s.pop(s["idx"], None)
        dmax = max(_dias(b, s) for b in bancos for s in sistemas)
        pares.append({"banco": sorted(bancos, key=lambda x: x["idx"]), "sistema": sorted(sistemas, key=lambda x: x["idx"]), "union": union,
                      "confianza": confianza, "dias": dmax, "razones": razones})

    # Las coincidencias se asignan por FASES, de la más a la menos respaldada: primero las que el texto confirma (apartamento, concepto,
    # palabras), y solo después las que coinciden únicamente por monto y fecha. Así un depósito sin anotación que casualmente tiene el
    # mismo monto no le quita su registro a un pago que sí está identificado.
    candidatos = []
    cand_b, cand_s = {}, {}
    for b in libres_b.values():
        for s in libres_s.values():
            if s["dir"] == b["dir"] and s["cents"] == b["cents"] and _dias(b, s) <= dias:
                pts, razones = _afinidad(b, s)
                candidatos.append((100 - 12 * _dias(b, s) + pts, -_dias(b, s), b["idx"], s["idx"], pts, razones))
                cand_b.setdefault(b["idx"], []).append(s["idx"])
                cand_s.setdefault(s["idx"], []).append(b["idx"])

    def fase_uno_a_uno(acepta_pts):
        """Mismo monto y fecha cercana, uno a uno."""
        for puntaje, _nd, ib, is_, pts, razones in sorted(candidatos, key=lambda c_: (-c_[0], -c_[1], c_[2], c_[3])):
            if not acepta_pts(pts) or ib not in libres_b or is_ not in libres_s:
                continue
            b, s = libres_b[ib], libres_s[is_]
            ambigua = len(cand_b[ib]) > 1 or len(cand_s[is_]) > 1
            if pts < 0:
                confianza = REVISAR
            elif pts > 0 or (_dias(b, s) == 0 and not ambigua):
                confianza = ALTA
            else:
                confianza = MEDIA
            if ambigua and pts <= 0:
                razones = razones + ["hay varios registros con el mismo monto: verifica que sea el correcto"]
            registrar([b], [s], UNO_A_UNO, confianza, razones or (["mismo monto y misma fecha"] if _dias(b, s) == 0 else ["mismo monto, fecha cercana"]))

    def fase_banco_varios(acepta_nivel):
        """Un movimiento del banco = varios registros del sistema (pagos juntos, como «alquiler y energía»)."""
        for b in sorted(libres_b.values(), key=lambda x: (-x["cents"], x["idx"])):
            if b["idx"] not in libres_b:
                continue
            cand = [s for s in libres_s.values() if s["dir"] == b["dir"] and s["cents"] < b["cents"] and _dias(b, s) <= dias]
            cand.sort(key=lambda s: (0 if b["apt"] and s["apt"] == b["apt"] else 1, _dias(b, s), -s["cents"]))
            mejor = None
            for combo in _combinaciones(cand, b["cents"]):
                ev = _evaluar_banco_varios(b, combo)
                if ev and acepta_nivel(ev[0]) and (mejor is None or ev[1] > mejor[1][1]):
                    mejor = (combo, ev)
            if mejor:
                combo, (nivel, _p, razones) = mejor
                registrar([b], list(combo), BANCO_VARIOS, nivel, razones)

    def fase_sistema_varios(acepta_nivel):
        """Varios movimientos del banco = un registro del sistema (un pago hecho en partes)."""
        for s in sorted(libres_s.values(), key=lambda x: (-x["cents"], x["idx"])):
            if s["idx"] not in libres_s:
                continue
            cand = [b for b in libres_b.values() if b["dir"] == s["dir"] and b["cents"] < s["cents"] and _dias(b, s) <= max(dias, VENTANA_AGRUPADA)]
            cand.sort(key=lambda b: (_dias(b, s), -b["cents"]))
            mejor = None
            for combo in _combinaciones(cand, s["cents"], maximo=4):
                ev = _evaluar_sistema_varios(s, combo)
                if ev and acepta_nivel(ev[0]) and (len({b["contraparte_norm"] for b in combo}) == 1 or all(_dias(b, s) <= dias for b in combo)):
                    if mejor is None or ev[1] > mejor[1][1]:
                        mejor = (combo, ev)
            if mejor:
                combo, (nivel, _p, razones) = mejor
                registrar(list(combo), [s], VARIOS_BANCO, nivel, razones)

    fase_uno_a_uno(lambda pts: pts > 0)                 # 1) uno a uno confirmado por el texto
    fase_banco_varios(lambda nivel: nivel == ALTA)      # 2) pagos juntos confirmados (todos del mismo apartamento)
    fase_sistema_varios(lambda nivel: nivel == ALTA)    # 3) pagos en partes confirmados (misma persona y texto)
    fase_uno_a_uno(lambda pts: pts <= 0)                # 4) uno a uno solo por monto y fecha
    fase_banco_varios(lambda nivel: nivel != ALTA)      # 5) combinaciones con menos respaldo
    fase_sistema_varios(lambda nivel: nivel != ALTA)

    # ---- diagnóstico de lo que no coincidió ----
    asignado_s = {s["idx"]: p for p in pares for s in p["sistema"]}
    sin_banco = []
    for b in sorted(libres_b.values(), key=lambda x: (x["fecha"], x["idx"])):
        causas = _causas_banco(b, list(libres_s.values()), efectivo, asignado_s, dias)
        sin_banco.append({"linea": b, "causas": causas, "sugerencia": _sugerencia(b)})
    sin_sistema = []
    for s in sorted(libres_s.values(), key=lambda x: (x["fecha"], x["idx"])):
        if s["en_periodo"]:
            sin_sistema.append({"mov": s, "causas": _causas_sistema(s, list(libres_b.values()), dias)})
    excluidos = [b for b in banco if b["excluido"]]
    pares.sort(key=lambda p: (p["banco"][0]["fecha"], p["banco"][0]["idx"]))
    return {"desde": desde, "hasta": hasta, "dias": dias, "incluir_efectivo": incluir_efectivo, "pares": pares, "banco_sin_registro": sin_banco,
            "sistema_sin_banco": sin_sistema, "excluidos": excluidos, "efectivo": [s for s in efectivo if s["en_periodo"]],
            "banco": banco, "resumen": _resumen(banco, pares, sin_banco, sin_sistema, excluidos, sistema, efectivo)}


# ============================================================
# Explicaciones
# ============================================================

def _etiqueta_sistema(s):
    quien = s.get("apartamento") or s.get("persona") or ""
    return f"{s['origen']}{' ' + quien if quien else ''} ({_fmt_fecha(s['fecha'])})"


def _sugerencia(b):
    if b["dir"] == INGRESO:
        if b["apt"] or b["conceptos"]:
            que = " y ".join(sorted(b["conceptos"])) or "pago"
            return f"Registrar {que.lower()}" + (f" del {b['apt']}" if b["apt"] else "") + f" por Bs {_fmt_monto(b['cents'])}"
        return "Registrar el ingreso (alquiler, luz, agua o venta)"
    return "Registrar el egreso (compra o pago)"


def _causas_banco(b, libres_s, efectivo, asignado_s, dias):
    causas = []
    mismos = [s for s in libres_s if s["dir"] == b["dir"] and s["cents"] == b["cents"]]
    lejos = sorted((s for s in mismos if dias < _dias(b, s) <= MARGEN_CANDIDATOS), key=lambda s: _dias(b, s))
    for s in lejos[:2]:
        causas.append(f"Hay un registro de {_etiqueta_sistema(s)} por Bs {_fmt_monto(s['cents'])}, a {_dias(b, s)} días del movimiento del banco: "
                      "revisa la fecha con que se registró.")
    parecidos = sorted((s for s in libres_s if s["dir"] == b["dir"] and s["cents"] != b["cents"] and _dias(b, s) <= dias
                        and abs(s["cents"] - b["cents"]) <= max(1000, b["cents"] * 0.03)), key=lambda s: abs(s["cents"] - b["cents"]))
    for s in parecidos[:2]:
        pts, _r = _afinidad(b, s)
        if pts >= 0:
            causas.append(f"Hay un registro de {_etiqueta_sistema(s)} por Bs {_fmt_monto(s['cents'])} (diferencia de Bs "
                          f"{_fmt_monto(abs(s['cents'] - b['cents']))}): revisa el monto.")
    cerca_efectivo = [s for s in efectivo if s["dir"] == b["dir"] and s["cents"] == b["cents"] and _dias(b, s) <= max(dias, VENTANA_AGRUPADA)]
    for s in cerca_efectivo[:1]:
        causas.append(f"Existe un registro de {_etiqueta_sistema(s)} por ese monto pagado en efectivo: si se depositó en el banco, "
                      "activa «Comparar también los pagos en efectivo».")
    if not cerca_efectivo and efectivo:
        cand = sorted((s for s in efectivo if s["dir"] == b["dir"] and s["cents"] < b["cents"] and _dias(b, s) <= max(dias, VENTANA_AGRUPADA)),
                      key=lambda s: (_dias(b, s), -s["cents"]))
        combo = next(_combinaciones(cand, b["cents"]), None)
        if combo:
            causas.append(f"Los {len(combo)} pagos en efectivo registrados por {', '.join(_etiqueta_sistema(s) for s in combo)} suman exactamente este "
                          "monto: parece un depósito de efectivo. Activa «Comparar también los pagos en efectivo» para conciliarlo.")
    if not causas:
        usados = _ya_asignados(asignado_s, b)
        if usados:
            s, par = usados[0]
            otros = " + ".join(f"Bs {_fmt_monto(x['cents'])} del {_fmt_fecha(x['fecha'])}" for x in par["banco"])
            causas.append(f"El registro de {_etiqueta_sistema(s)} por ese monto ya se usó para conciliar otro movimiento del banco ({otros}): "
                          "este movimiento puede ser un pago repetido en el banco, o falta registrarlo una segunda vez.")
    if (b["apt"] or b["conceptos"]) and not causas:
        que = " y ".join(sorted(b["conceptos"])).lower() or "un pago"
        causas.append(f"Por tu anotación corresponde a {que}" + (f" del {b['apt']}" if b["apt"] else "") +
                      ": en el sistema no hay un pago así sin conciliar. Probablemente falta registrarlo.")
    if not causas:
        causas.append("No hay ningún registro en el sistema con ese monto: probablemente no se registró.")
    return causas


def _ya_asignados(asignado_s, b):
    """[(registro, coincidencia)] de los registros con el mismo monto y sentido que `b` que ya se usaron para conciliar otro movimiento."""
    vistos = []
    for _idx, par in asignado_s.items():
        for s in par["sistema"]:
            if s["cents"] == b["cents"] and s["dir"] == b["dir"] and _dias(b, s) <= MARGEN_CANDIDATOS and all(s is not v[0] for v in vistos):
                vistos.append((s, par))
    return vistos


def _causas_sistema(s, libres_b, dias):
    causas = []
    mismos = sorted((b for b in libres_b if b["dir"] == s["dir"] and b["cents"] == s["cents"] and dias < _dias(b, s) <= MARGEN_CANDIDATOS),
                    key=lambda b: _dias(b, s))
    for b in mismos[:2]:
        causas.append(f"En el banco hay un movimiento por ese monto el {_fmt_fecha(b['fecha'])} ({b['contraparte'] or b['transaccion']}), a "
                      f"{_dias(b, s)} días: revisa la fecha del registro.")
    parecidos = sorted((b for b in libres_b if b["dir"] == s["dir"] and b["cents"] != s["cents"] and _dias(b, s) <= dias
                        and abs(b["cents"] - s["cents"]) <= max(1000, s["cents"] * 0.03)), key=lambda b: abs(b["cents"] - s["cents"]))
    for b in parecidos[:2]:
        pts, _r = _afinidad(b, s)
        if pts >= 0:
            causas.append(f"En el banco hay un movimiento de Bs {_fmt_monto(b['cents'])} el {_fmt_fecha(b['fecha'])} (diferencia de Bs "
                          f"{_fmt_monto(abs(s['cents'] - b['cents']))}): revisa el monto.")
    if s["metodo"] in ("QR", "Transferencia", "Tarjeta"):
        causas.append(f"Se registró como {s['metodo']} pero no aparece en el extracto: verifica que el pago se hizo, o que el monto y la fecha estén bien.")
    elif s["metodo"] in ("Otro", "Sin método"):
        causas.append("El método de pago no está definido (o es «Otro»): si fue en efectivo es normal que no aparezca en el banco.")
    else:
        causas.append("Está registrado como efectivo: si no se depositó en el banco, es normal que no aparezca.")
    return causas


# ============================================================
# Resumen
# ============================================================

def _suma(items, clave="monto", filtro=lambda x: True):
    return round(sum(abs(x[clave]) for x in items if filtro(x)), 2)


def _resumen(banco, pares, sin_banco, sin_sistema, excluidos, sistema, efectivo):
    bancos_conciliados = [b for p in pares for b in p["banco"]]
    sin_registro = [x["linea"] for x in sin_banco]
    cred = lambda b: b["monto"] > 0
    deb = lambda b: b["monto"] < 0
    sist_conciliados = [s for p in pares for s in p["sistema"]]
    sist_periodo = [s for s in sistema if s["en_periodo"]]
    ing = lambda s: s["dir"] == INGRESO
    egr = lambda s: s["dir"] == EGRESO
    return {
        "banco": {"n": len(banco), "creditos": _suma(banco, filtro=cred), "debitos": _suma(banco, filtro=deb),
                  "n_creditos": sum(1 for b in banco if cred(b)), "n_debitos": sum(1 for b in banco if deb(b))},
        "conciliado": {"n": len(bancos_conciliados), "creditos": _suma(bancos_conciliados, filtro=cred), "debitos": _suma(bancos_conciliados, filtro=deb),
                       "n_pares": len(pares)},
        "sin_registro": {"n": len(sin_registro), "creditos": _suma(sin_registro, filtro=cred), "debitos": _suma(sin_registro, filtro=deb),
                         "n_creditos": sum(1 for b in sin_registro if cred(b)), "n_debitos": sum(1 for b in sin_registro if deb(b))},
        "excluidos": {"n": len(excluidos), "creditos": _suma(excluidos, filtro=cred), "debitos": _suma(excluidos, filtro=deb)},
        "sistema": {"n": len(sist_periodo), "ingresos": _suma(sist_periodo, filtro=ing), "egresos": _suma(sist_periodo, filtro=egr)},
        "sistema_sin_banco": {"n": len(sin_sistema), "ingresos": _suma([x["mov"] for x in sin_sistema], filtro=ing),
                              "egresos": _suma([x["mov"] for x in sin_sistema], filtro=egr)},
        "efectivo_no_comparado": {"n": sum(1 for s in efectivo if s["en_periodo"]), "ingresos": _suma([s for s in efectivo if s["en_periodo"]], filtro=ing),
                                  "egresos": _suma([s for s in efectivo if s["en_periodo"]], filtro=egr)},
        "por_confianza": {n: sum(1 for p in pares if p["confianza"] == n) for n in (ALTA, MEDIA, REVISAR)},
    }
