"""
Inventario del edificio: materiales, repuestos y suministros, con sus movimientos de ENTRADA y SALIDA y el KARDEX.

Reglas:
  * Cada artículo tiene movimientos. Una entrada suma stock y lleva su costo unitario; una salida resta stock.
  * El Kardex se calcula con COSTO PROMEDIO PONDERADO: cada entrada recalcula el costo promedio y cada salida se valora
    a ese costo promedio del momento. El saldo final siempre es igual a entradas - salidas.
  * CANTIDADES y COSTOS UNITARIOS se registran con 1 SOLO DECIMAL (2.5 piezas, Bs 3.5 por unidad). Los cálculos internos
    conservan toda su precisión: el costo promedio se muestra redondeado a 1 decimal, pero los valores en Bs (que se
    muestran con 2 decimales) se calculan con el promedio exacto, así que entradas - salidas = saldo sin diferencias.
  * El Kardex no se guarda: se calcula siempre desde los movimientos (así nunca queda desactualizado).
  * El stock nunca puede quedar negativo: no se puede sacar más de lo que hay, ni registrar con fecha pasada una salida
    que dejaría un saldo negativo en una fecha posterior, ni eliminar una entrada de la que dependen salidas posteriores.
  * Orden de los movimientos: por fecha; en el mismo día las entradas van antes que las salidas; luego por orden de registro.
  * Un movimiento registrado no se modifica en cantidad, fecha ni costo (eso altera el Kardex): para corregirlo se
    elimina (solo el Administrador, si el Kardex lo permite) y se registra de nuevo. Sí se pueden editar el documento,
    el destino y la observación.

Módulo sin dependencias de Streamlit ni de la base: recibe listas de diccionarios y devuelve datos listos para mostrar.
"""
import re
import unicodedata
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

ENTRADA, SALIDA = "Entrada", "Salida"
TIPOS = [ENTRADA, SALIDA]
MOTIVO_SALDO_INICIAL = "Saldo inicial"
MOTIVOS = {
    ENTRADA: ["Compra", MOTIVO_SALDO_INICIAL, "Donación", "Devolución a bodega", "Ajuste de inventario (sobrante)"],
    SALIDA: ["Uso en apartamento", "Uso en áreas comunes", "Mantenimiento / reparación", "Pérdida o daño",
             "Ajuste de inventario (faltante)"],
}
MOTIVO_USO_APARTAMENTO = "Uso en apartamento"
DESTINO_APARTAMENTO, DESTINO_AREAS, DESTINO_EDIFICIO = "Apartamento", "Áreas comunes", "Edificio en general"
DESTINOS = [DESTINO_EDIFICIO, DESTINO_AREAS, DESTINO_APARTAMENTO]

CATEGORIAS = ["Electricidad", "Plomería y agua", "Limpieza", "Pintura", "Ferretería", "Cerrajería y seguridad",
              "Jardinería", "Repuestos", "Papelería y oficina", "Otros"]
UNIDADES = ["Unidad", "Pieza", "Par", "Juego", "Metro", "Litro", "Galón", "Kilo", "Caja", "Paquete", "Rollo", "Bolsa", "Balde"]

ESTADO_OK, ESTADO_BAJO, ESTADO_SIN_STOCK = "OK", "Stock bajo", "Sin stock"

MAX_CANTIDAD = Decimal("999999999.999")
DECIMALES = 1                                 # decimales permitidos al REGISTRAR cantidades y costos unitarios
_D1, _D2, _D3, _D4 = Decimal("0.1"), Decimal("0.01"), Decimal("0.001"), Decimal("0.0001")


# ============================================================
# Utilidades
# ============================================================

def _dec(valor):
    if valor is None or valor == "":
        return Decimal(0)
    try:
        return Decimal(str(valor))
    except Exception:
        return Decimal(0)


def _cant(valor):
    return _dec(valor).quantize(_D3, rounding=ROUND_HALF_UP)


def _un_decimal(valor):
    """True si el número tiene a lo sumo 1 decimal (2, 2.5, 0.3). Tolera el ruido de coma flotante (0.30000000000000004)."""
    try:
        d = Decimal(str(round(float(valor), 9)))
    except (TypeError, ValueError):
        return False
    return d == d.quantize(_D1)


def a_un_decimal(valor):
    """El número redondeado a 1 decimal (float), con redondeo normal (0.25 -> 0.3)."""
    try:
        return float(Decimal(str(round(float(valor or 0), 9))).quantize(_D1, rounding=ROUND_HALF_UP))
    except (TypeError, ValueError):
        return 0.0


def _fecha(valor):
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10]) if valor else None
    except ValueError:
        return None


def _fmt_fecha(valor):
    f = _fecha(valor)
    return f.strftime("%d/%m/%Y") if f else "—"


def _sin_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if unicodedata.category(c) != "Mn").casefold()


def _limpio(texto):
    texto = (texto or "").strip()
    return texto or None


def _clave_orden(m):
    return (_fecha(m.get("fecha")) or date.min, 0 if m.get("tipo") == ENTRADA else 1, m.get("id") or 0)


def formato_cantidad(valor):
    """12 -> '12'; 2.5 -> '2.5'; 1234.5 -> '1,234.5' (1 decimal, sin ceros de más)."""
    d = _dec(valor).quantize(_D1, rounding=ROUND_HALF_UP)
    if d == 0:
        return "0"
    texto = f"{d:,.1f}"
    return texto[:-2] if texto.endswith(".0") else texto


# ============================================================
# KARDEX (costo promedio ponderado)
# ============================================================

def kardex(movimientos):
    """Filas del Kardex de UN artículo, en orden, con el saldo después de cada movimiento.
    Cada fila: id, fecha, tipo, motivo, documento, destino, observacion, registrado_por,
      entrada_cantidad / entrada_costo / entrada_valor, salida_cantidad / salida_costo / salida_valor (None si no aplica),
      saldo_cantidad / saldo_costo / saldo_valor, y 'negativo' (True si el saldo quedó por debajo de 0)."""
    cantidad, valor, filas = Decimal(0), Decimal(0), []
    for m in sorted(movimientos, key=_clave_orden):
        q = _cant(m.get("cantidad"))
        fila = {"id": m.get("id"), "fecha": _fecha(m.get("fecha")), "fecha_txt": _fmt_fecha(m.get("fecha")), "tipo": m.get("tipo"),
                "motivo": m.get("motivo") or "", "documento": m.get("documento") or "", "destino": m.get("destino") or "",
                "observacion": m.get("observacion") or "", "registrado_por": m.get("registrado_por") or "",
                "entrada_cantidad": None, "entrada_costo": None, "entrada_valor": None,
                "salida_cantidad": None, "salida_costo": None, "salida_valor": None}
        if m.get("tipo") == ENTRADA:
            costo = _dec(m.get("costo_unitario")).quantize(_D4, rounding=ROUND_HALF_UP)
            v = (q * costo).quantize(_D4, rounding=ROUND_HALF_UP)
            cantidad, valor = cantidad + q, valor + v
            fila.update(entrada_cantidad=float(q), entrada_costo=float(costo), entrada_valor=float(v.quantize(_D2, rounding=ROUND_HALF_UP)))
        else:
            if cantidad <= 0:
                v = Decimal(0)
            elif q >= cantidad:
                v = valor                                    # sale todo lo que hay: sale todo su valor (sin residuos)
            else:
                v = (valor * q / cantidad).quantize(_D4, rounding=ROUND_HALF_UP)
            costo = (v / q).quantize(_D4, rounding=ROUND_HALF_UP) if q > 0 else Decimal(0)
            cantidad, valor = cantidad - q, valor - v
            fila.update(salida_cantidad=float(q), salida_costo=float(costo), salida_valor=float(v.quantize(_D2, rounding=ROUND_HALF_UP)))
        if cantidad == 0:
            valor = Decimal(0)
        fila.update(saldo_cantidad=float(cantidad),
                    saldo_costo=float((valor / cantidad).quantize(_D4, rounding=ROUND_HALF_UP)) if cantidad > 0 else 0.0,
                    saldo_valor=float(valor.quantize(_D2, rounding=ROUND_HALF_UP)), negativo=cantidad < 0)
        filas.append(fila)
    return filas


_SALDO_CERO = {"cantidad": 0.0, "costo": 0.0, "valor": 0.0}


def _saldo(fila):
    return {"cantidad": fila["saldo_cantidad"], "costo": fila["saldo_costo"], "valor": fila["saldo_valor"]}


def kardex_periodo(movimientos, desde=None, hasta=None):
    """Kardex de un artículo entre dos fechas (ambas incluidas; None = sin límite). Los saldos se calculan con TODO el
    historial, así que el saldo inicial del periodo es el que realmente había. Devuelve
    {'saldo_inicial', 'filas', 'saldo_final', 'entradas': {cantidad, valor}, 'salidas': {cantidad, valor}}."""
    todas = kardex(movimientos)
    antes = [f for f in todas if desde and f["fecha"] and f["fecha"] < desde]
    dentro = [f for f in todas if not (desde and f["fecha"] and f["fecha"] < desde) and not (hasta and f["fecha"] and f["fecha"] > hasta)]
    ultimo_antes = _saldo(antes[-1]) if antes else dict(_SALDO_CERO)
    entradas_c = sum(Decimal(str(f["entrada_cantidad"] or 0)) for f in dentro)
    salidas_c = sum(Decimal(str(f["salida_cantidad"] or 0)) for f in dentro)
    return {"saldo_inicial": ultimo_antes, "filas": dentro, "saldo_final": _saldo(dentro[-1]) if dentro else ultimo_antes,
            "entradas": {"cantidad": float(entradas_c), "valor": round(sum(f["entrada_valor"] or 0 for f in dentro), 2)},
            "salidas": {"cantidad": float(salidas_c), "valor": round(sum(f["salida_valor"] or 0 for f in dentro), 2)}}


def _agrupar(movimientos):
    por_articulo = {}
    for m in movimientos or []:
        por_articulo.setdefault(m.get("articulo_id"), []).append(m)
    return por_articulo


# ============================================================
# Existencias (stock actual)
# ============================================================

def estado_stock(cantidad, stock_minimo):
    if cantidad <= 0:
        return ESTADO_SIN_STOCK
    if _dec(stock_minimo) > 0 and Decimal(str(cantidad)) <= _dec(stock_minimo):
        return ESTADO_BAJO
    return ESTADO_OK


def existencias(articulos, movimientos):
    """Stock actual de cada artículo: lista de filas más los totales. Fila: id, codigo, nombre, categoria, unidad,
    ubicacion, activo, stock_minimo, cantidad, costo_promedio, valor, estado."""
    por_articulo = _agrupar(movimientos)
    filas = []
    for a in articulos or []:
        ks = kardex(por_articulo.get(a["id"], []))
        saldo = _saldo(ks[-1]) if ks else dict(_SALDO_CERO)
        filas.append({"id": a["id"], "codigo": a.get("codigo") or "", "nombre": a.get("nombre") or "", "categoria": a.get("categoria") or "",
                      "unidad": a.get("unidad") or "", "ubicacion": a.get("ubicacion") or "", "activo": a.get("activo", True) is not False,
                      "stock_minimo": float(_dec(a.get("stock_minimo"))), "cantidad": saldo["cantidad"],
                      "costo_promedio": saldo["costo"], "valor": saldo["valor"],
                      "estado": estado_stock(saldo["cantidad"], a.get("stock_minimo")), "n_movimientos": len(ks)})
    filas.sort(key=lambda f: (_sin_acentos(f["nombre"]), f["id"]))
    activas = [f for f in filas if f["activo"]]
    return {"filas": filas,
            "valor_total": round(sum(f["valor"] for f in activas), 2),
            "n_activos": len(activas),
            "n_bajo": sum(1 for f in activas if f["estado"] == ESTADO_BAJO),
            "n_sin_stock": sum(1 for f in activas if f["estado"] == ESTADO_SIN_STOCK)}


def filtrar_existencias(filas, texto="", categoria="Todas", solo_alertas=False, incluir_inactivos=False):
    buscado = _sin_acentos(texto).strip()
    salida = []
    for f in filas:
        if not incluir_inactivos and not f["activo"]:
            continue
        if categoria != "Todas" and f["categoria"] != categoria:
            continue
        if solo_alertas and f["estado"] == ESTADO_OK:
            continue
        if buscado and not any(buscado in _sin_acentos(f[c]) for c in ("codigo", "nombre", "categoria", "ubicacion")):
            continue
        salida.append(f)
    return salida


# ============================================================
# Movimientos del periodo (valorizados)
# ============================================================

def movimientos_valorizados(articulos, movimientos, desde=None, hasta=None, articulo_id=None, tipo=None, motivo=None):
    """Todos los movimientos entre dos fechas, con su valor (las salidas valoradas a su costo promedio del momento).
    Devuelve {'filas', 'entradas_valor', 'salidas_valor', 'n_entradas', 'n_salidas', 'por_motivo'}."""
    info = {a["id"]: a for a in articulos or []}
    filas = []
    for art_id, movs in _agrupar(movimientos).items():
        a = info.get(art_id)
        if a is None or (articulo_id is not None and art_id != articulo_id):
            continue
        for f in kardex(movs):
            if (desde and f["fecha"] and f["fecha"] < desde) or (hasta and f["fecha"] and f["fecha"] > hasta):
                continue
            if tipo and tipo != "Todos" and f["tipo"] != tipo:
                continue
            if motivo and motivo != "Todos" and f["motivo"] != motivo:
                continue
            es_entrada = f["tipo"] == ENTRADA
            filas.append({"id": f["id"], "fecha": f["fecha"], "fecha_txt": f["fecha_txt"], "codigo": a.get("codigo") or "",
                          "articulo": a.get("nombre") or "", "categoria": a.get("categoria") or "", "unidad": a.get("unidad") or "",
                          "tipo": f["tipo"], "motivo": f["motivo"], "destino": f["destino"], "documento": f["documento"],
                          "cantidad": f["entrada_cantidad"] if es_entrada else f["salida_cantidad"],
                          "costo_unitario": f["entrada_costo"] if es_entrada else f["salida_costo"],
                          "valor": f["entrada_valor"] if es_entrada else f["salida_valor"],
                          "observacion": f["observacion"], "registrado_por": f["registrado_por"], "articulo_id": art_id})
    filas.sort(key=lambda r: (r["fecha"] or date.min, 0 if r["tipo"] == ENTRADA else 1, r["id"] or 0))
    por_motivo = {}
    for r in filas:
        clave = (r["tipo"], r["motivo"])
        n, total = por_motivo.get(clave, (0, 0.0))
        por_motivo[clave] = (n + 1, round(total + (r["valor"] or 0), 2))
    return {"filas": filas,
            "entradas_valor": round(sum(r["valor"] or 0 for r in filas if r["tipo"] == ENTRADA), 2),
            "salidas_valor": round(sum(r["valor"] or 0 for r in filas if r["tipo"] == SALIDA), 2),
            "n_entradas": sum(1 for r in filas if r["tipo"] == ENTRADA), "n_salidas": sum(1 for r in filas if r["tipo"] == SALIDA),
            "por_motivo": [{"tipo": t, "motivo": m, "n": n, "valor": v} for (t, m), (n, v) in sorted(por_motivo.items())]}


# ============================================================
# Validaciones de movimientos
# ============================================================

def validar_movimiento(tipo, cantidad, costo_unitario, fecha, motivo, destino=None, apartamento_id=None, hoy=None):
    """Lista de errores en español (vacía si todo está bien)."""
    errores = []
    hoy = hoy or date.today()
    if tipo not in TIPOS:
        errores.append("Elige si es una entrada o una salida.")
        return errores
    q = _dec(cantidad)
    if q <= 0:
        errores.append("La cantidad debe ser mayor a 0.")
    elif q > MAX_CANTIDAD:
        errores.append("La cantidad es demasiado grande.")
    elif not _un_decimal(cantidad):
        errores.append("La cantidad admite solo 1 decimal (por ejemplo 2.5).")
    if tipo == ENTRADA:
        if costo_unitario is None or costo_unitario == "":
            errores.append("Indica el costo unitario (puede ser 0 si fue una donación).")
        elif _dec(costo_unitario) < 0:
            errores.append("El costo unitario no puede ser negativo.")
        elif _dec(costo_unitario) > Decimal("99999999.9"):
            errores.append("El costo unitario es demasiado grande.")
        elif not _un_decimal(costo_unitario):
            errores.append("El costo unitario admite solo 1 decimal (por ejemplo 3.5).")
    f = _fecha(fecha)
    if not f:
        errores.append("La fecha es obligatoria.")
    elif f > hoy:
        errores.append("La fecha del movimiento no puede ser futura.")
    if motivo not in MOTIVOS[tipo]:
        errores.append("Elige el motivo del movimiento.")
    if tipo == SALIDA:
        if not _limpio(destino):
            errores.append("Indica el destino de la salida (apartamento, áreas comunes o edificio en general).")
        if motivo == MOTIVO_USO_APARTAMENTO and apartamento_id is None:
            errores.append("El motivo «Uso en apartamento» requiere elegir el apartamento.")
    return errores


def armar_movimiento(articulo_id, tipo, fecha, cantidad, costo_unitario, motivo, destino, apartamento_id, documento, observacion, usuario):
    """Registro listo para guardar. En las salidas no se guarda el costo: se calcula en el Kardex."""
    return {"articulo_id": articulo_id, "fecha": str(_fecha(fecha)), "tipo": tipo, "motivo": motivo,
            "cantidad": a_un_decimal(cantidad),
            "costo_unitario": a_un_decimal(costo_unitario) if tipo == ENTRADA else None,
            "apartamento_id": apartamento_id if tipo == SALIDA else None, "destino": _limpio(destino) if tipo == SALIDA else None,
            "documento": _limpio(documento), "observacion": _limpio(observacion), "registrado_por": usuario}


def armar_edicion(destino, apartamento_id, documento, observacion, tipo):
    """Lo único que se puede editar de un movimiento ya registrado."""
    cambios = {"documento": _limpio(documento), "observacion": _limpio(observacion)}
    if tipo == SALIDA:
        cambios.update({"destino": _limpio(destino), "apartamento_id": apartamento_id})
    return cambios


def _primer_saldo_negativo(filas):
    return next((f for f in filas if f["negativo"]), None)


def validar_en_kardex(movimientos_articulo, nuevo=None, excluir_id=None, unidad=""):
    """Error en español si, al agregar `nuevo` (y/o quitar el movimiento `excluir_id`), el saldo del artículo quedaría
    negativo en alguna fecha; None si el Kardex sigue siendo válido."""
    lista = [m for m in movimientos_articulo if m.get("id") != excluir_id]
    if nuevo is not None:
        lista.append({**nuevo, "id": 10 ** 12})            # el nuevo se registra después de todos los demás
    malo = _primer_saldo_negativo(kardex(lista))
    if malo is None:
        return None
    unidad = f" {unidad}" if unidad else ""
    disponible = malo["saldo_cantidad"] + (malo["salida_cantidad"] or 0)
    if nuevo is not None and malo["id"] == 10 ** 12:
        return f"No hay stock suficiente: al {malo['fecha_txt']} solo hay {formato_cantidad(max(disponible, 0))}{unidad} disponibles."
    return (f"No se puede hacer: dejaría el stock en negativo ({formato_cantidad(malo['saldo_cantidad'])}{unidad}) "
            f"el {malo['fecha_txt']} por una salida posterior.")


# ============================================================
# Artículos
# ============================================================

def siguiente_codigo(articulos, prefijo="INV-", ancho=3):
    """INV-001, INV-002… el siguiente libre según los códigos que ya siguen ese formato."""
    patron = re.compile(rf"^{re.escape(prefijo)}(\d+)$", re.IGNORECASE)
    mayor = max((int(m.group(1)) for a in articulos or [] if (m := patron.match((a.get("codigo") or "").strip()))), default=0)
    return f"{prefijo}{mayor + 1:0{ancho}d}"


def validar_articulo(codigo, nombre, unidad, stock_minimo, articulos, articulo_id=None):
    """Lista de errores en español (vacía si todo está bien)."""
    errores = []
    cod = (codigo or "").strip()
    if not cod:
        errores.append("El código es obligatorio.")
    elif len(cod) > 30:
        errores.append("El código no puede pasar de 30 caracteres.")
    elif any(a.get("id") != articulo_id and (a.get("codigo") or "").strip().casefold() == cod.casefold() for a in articulos or []):
        errores.append(f"Ya existe un artículo con el código {cod}.")
    if not (nombre or "").strip():
        errores.append("El nombre es obligatorio.")
    elif len(nombre.strip()) > 150:
        errores.append("El nombre no puede pasar de 150 caracteres.")
    if not (unidad or "").strip():
        errores.append("La unidad es obligatoria.")
    if _dec(stock_minimo) < 0:
        errores.append("El stock mínimo no puede ser negativo.")
    elif not _un_decimal(stock_minimo):
        errores.append("El stock mínimo admite solo 1 decimal (por ejemplo 2.5).")
    return errores


def armar_articulo(codigo, nombre, categoria, unidad, stock_minimo, ubicacion, notas, activo=True, creado_por=None):
    registro = {"codigo": (codigo or "").strip(), "nombre": (nombre or "").strip(), "categoria": _limpio(categoria),
                "unidad": (unidad or "").strip(), "stock_minimo": a_un_decimal(stock_minimo), "ubicacion": _limpio(ubicacion),
                "notas": _limpio(notas), "activo": bool(activo)}
    if creado_por is not None:
        registro["creado_por"] = creado_por
    return registro
