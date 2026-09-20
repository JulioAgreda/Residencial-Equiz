import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
import db

st.set_page_config(page_title="Residencial EQUIZ", page_icon="🏢", layout="wide")

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

PISOS = ["Planta Baja", "Primer Piso", "Segundo Piso", "Tercer Piso"]


# ------------------------------------------------------------------
# Autenticación simple compartida (clave única para el personal)
# ------------------------------------------------------------------
def check_password():
    if st.session_state.get("auth_ok"):
        return True

    st.title("🏢 Residencial EQUIZ")
    st.caption("Sistema de control de apartamentos y alquileres")
    pwd = st.text_input("Clave de acceso", type="password")
    if st.button("Ingresar"):
        if pwd == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Clave incorrecta.")
    return False


if not check_password():
    st.stop()


# ------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------
def fmt_money(v):
    try:
        return f"Bs {float(v):,.2f}"
    except (TypeError, ValueError):
        return "Bs 0.00"


@st.cache_data(ttl=30)
def cargar_apartamentos():
    return db.listar_apartamentos()


@st.cache_data(ttl=30)
def cargar_periodos(apartamento_id=None, anio=None, mes=None):
    return db.listar_periodos(apartamento_id=apartamento_id, anio=anio, mes=mes)


@st.cache_data(ttl=30)
def cargar_periodos_electricidad(anio=None, mes=None):
    return db.listar_periodos_electricidad(anio=anio, mes=mes)


@st.cache_data(ttl=30)
def cargar_periodos_agua(anio=None, mes=None):
    return db.listar_periodos_agua(anio=anio, mes=mes)


def total_pagado(periodo):
    return sum(float(p["monto"]) for p in (periodo.get("pagos") or []))


def limpiar_cache():
    cargar_apartamentos.clear()
    cargar_periodos.clear()
    cargar_periodos_electricidad.clear()
    cargar_periodos_agua.clear()


def parse_fecha(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def fecha_vencimiento_del_mes(fecha_ingreso: date, anio: int, mes_num: int):
    """Día de pago mensual = mismo día del mes que la fecha de ingreso (ajustado si el mes es más corto)."""
    ultimo_dia_mes = calendar.monthrange(anio, mes_num)[1]
    dia = min(fecha_ingreso.day, ultimo_dia_mes)
    return date(anio, mes_num, dia)


def calcular_mora_alquiler(apt, periodos_mes_actual_por_apt):
    """Devuelve (en_mora, dias_atraso, deuda) para un apartamento, según su fecha de pago mensual."""
    if apt["estado"] != "Ocupado":
        return False, 0, 0.0
    fecha_ingreso = parse_fecha(apt.get("fecha_ingreso"))
    hoy = date.today()
    dia_pago = fecha_ingreso if fecha_ingreso else date(hoy.year, hoy.month, 1)
    vencimiento = fecha_vencimiento_del_mes(dia_pago, hoy.year, hoy.month)
    if hoy <= vencimiento:
        return False, 0, 0.0  # todavía no vence el pago de este mes

    periodo = periodos_mes_actual_por_apt.get(apt["id"])
    monto_esperado = float(periodo["monto_esperado"]) if periodo else float(apt.get("monto_alquiler") or 0)
    pagado = total_pagado(periodo) if periodo else 0.0
    deuda = monto_esperado - pagado
    if deuda <= 0:
        return False, 0, 0.0
    dias_atraso = (hoy - vencimiento).days
    return True, dias_atraso, deuda


def estado_contrato_alerta(apt):
    """Devuelve (nivel, texto) para contratos vencidos o por vencer en los próximos 30 días. None si no aplica."""
    hoy = date.today()
    fecha_fin = parse_fecha(apt.get("contrato_fecha_fin"))
    estado = apt.get("estado_contrato") or "Sin Contrato"

    if estado == "Caducado":
        return "🔴 Vencido", None
    if fecha_fin:
        dias = (fecha_fin - hoy).days
        if dias < 0:
            return "🔴 Vencido", abs(dias)
        if dias <= 30:
            return "🟠 Por vencer", dias
    return None, None


def ultimos_n_meses(n=12):
    """Lista de (anio, mes_num) de los últimos n meses, terminando en el mes actual, en orden cronológico."""
    hoy = date.today()
    resultado = []
    for i in range(n - 1, -1, -1):
        offset = hoy.month - 1 - i
        anio = hoy.year + offset // 12
        mes_num = offset % 12 + 1
        resultado.append((anio, mes_num))
    return resultado


# ------------------------------------------------------------------
# Sidebar / navegación
# ------------------------------------------------------------------
st.sidebar.title("🏢 Residencial EQUIZ")
pagina = st.sidebar.radio(
    "Navegación",
    ["📊 Dashboard", "🏠 Apartamentos", "💵 Pagos de Alquiler", "⚡ Electricidad", "💧 Agua"],
)
st.sidebar.divider()
if st.sidebar.button("🔄 Actualizar datos"):
    limpiar_cache()
    st.rerun()
if st.sidebar.button("🚪 Cerrar sesión"):
    st.session_state["auth_ok"] = False
    st.rerun()


# ==================================================================
# PÁGINA: DASHBOARD
# ==================================================================
if pagina == "📊 Dashboard":
    st.title("📊 Dashboard General")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("Aún no hay apartamentos registrados. Ve a la sección **Apartamentos** para agregarlos.")
        st.stop()

    df_apt = pd.DataFrame(apartamentos)

    # ---------------- Alertas: contratos y mora ----------------
    hoy = date.today()
    mes_actual_nombre = MESES[hoy.month - 1]
    periodos_mes_actual = cargar_periodos(anio=hoy.year, mes=mes_actual_nombre)
    periodos_mes_actual_por_apt = {p["apartamento_id"]: p for p in periodos_mes_actual}

    filas_contrato = []
    filas_mora = []
    for apt in apartamentos:
        nivel, dias = estado_contrato_alerta(apt)
        if nivel:
            filas_contrato.append({
                "Apartamento": apt["codigo"],
                "Inquilino": apt.get("inquilino_nombre") or "—",
                "Tipo": apt.get("tipo_contrato") or "—",
                "Fecha fin": apt.get("contrato_fecha_fin") or "—",
                "Estado": nivel,
                "Días": (f"{dias} días vencido" if nivel == "🔴 Vencido" and dias is not None
                         else (f"vence en {dias} días" if dias is not None else "—")),
                "_orden": 0 if nivel == "🔴 Vencido" else 1,
            })

        en_mora, dias_atraso, deuda = calcular_mora_alquiler(apt, periodos_mes_actual_por_apt)
        if en_mora:
            filas_mora.append({
                "Apartamento": apt["codigo"],
                "Inquilino": apt.get("inquilino_nombre") or "—",
                "Días de atraso": dias_atraso,
                "Deuda": fmt_money(deuda),
            })

    if filas_contrato or filas_mora:
        st.subheader("⚠️ Alertas")
        colA, colB = st.columns(2)
        with colA:
            st.markdown("**📄 Contratos vencidos o por vencer (30 días)**")
            if filas_contrato:
                filas_contrato.sort(key=lambda f: f["_orden"])
                df_contrato = pd.DataFrame(filas_contrato).drop(columns=["_orden"])
                st.dataframe(df_contrato, use_container_width=True, hide_index=True)
            else:
                st.success("Sin contratos vencidos ni por vencer en los próximos 30 días.")
        with colB:
            st.markdown(f"**💰 Alquileres en mora (según fecha de pago de {mes_actual_nombre})**")
            if filas_mora:
                filas_mora.sort(key=lambda f: -f["Días de atraso"])
                st.dataframe(pd.DataFrame(filas_mora), use_container_width=True, hide_index=True)
            else:
                st.success("Sin alquileres atrasados por ahora.")
        st.divider()

    col1, col2 = st.columns(2)
    with col1:
        anio_sel = st.selectbox("Año", options=list(range(date.today().year - 2, date.today().year + 2)),
                                 index=2)
    with col2:
        mes_sel = st.selectbox("Mes", options=MESES, index=date.today().month - 1)

    periodos = cargar_periodos(anio=anio_sel, mes=mes_sel)

    total_unidades = len(df_apt)
    ocupados = int((df_apt["estado"] == "Ocupado").sum())
    desocupados = total_unidades - ocupados

    total_esperado = sum(float(p["monto_esperado"]) for p in periodos)
    total_recaudado = sum(total_pagado(p) for p in periodos)
    total_deuda = total_esperado - total_recaudado

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unidades totales", total_unidades)
    c2.metric("Ocupados", ocupados)
    c3.metric("Desocupados", desocupados)
    c4.metric(f"Deuda de {mes_sel} {anio_sel}", fmt_money(total_deuda))

    c5, c6 = st.columns(2)
    c5.metric(f"Esperado en {mes_sel} {anio_sel}", fmt_money(total_esperado))
    c6.metric(f"Recaudado en {mes_sel} {anio_sel}", fmt_money(total_recaudado))

    st.divider()
    st.subheader("📈 Cobro de alquiler — últimos 12 meses")
    meses_grafica = ultimos_n_meses(12)
    valores_grafica = []
    etiquetas_grafica = []
    for (anio_g, mes_num_g) in meses_grafica:
        nombre_mes_g = MESES[mes_num_g - 1]
        periodos_g = cargar_periodos(anio=anio_g, mes=nombre_mes_g)
        total_g = sum(total_pagado(p) for p in periodos_g)
        valores_grafica.append(total_g)
        etiquetas_grafica.append(f"{nombre_mes_g[:3]} {anio_g}")
    df_grafica = pd.DataFrame({"Cobrado": valores_grafica}, index=etiquetas_grafica)
    st.line_chart(df_grafica)

    st.divider()
    st.subheader(f"🔝 Mayor consumo — {mes_sel} {anio_sel}")
    periodos_elec_sel = cargar_periodos_electricidad(anio=anio_sel, mes=mes_sel)
    periodos_agua_sel = cargar_periodos_agua(anio=anio_sel, mes=mes_sel)

    colE, colW = st.columns(2)
    with colE:
        st.markdown("**⚡ Electricidad (Kwh)**")
        filas_elec = []
        for p in periodos_elec_sel:
            apt_info = p.get("apartamentos") or {}
            consumo = float(p["kwh_actual"]) - float(p["kwh_anterior"])
            filas_elec.append({
                "Apartamento": apt_info.get("codigo"),
                "Inquilino": apt_info.get("inquilino_nombre") or "—",
                "Consumo (Kwh)": consumo,
            })
        if filas_elec:
            filas_elec.sort(key=lambda f: -f["Consumo (Kwh)"])
            st.dataframe(pd.DataFrame(filas_elec[:5]), use_container_width=True, hide_index=True)
        else:
            st.info("Sin lecturas de electricidad registradas este periodo.")
    with colW:
        st.markdown("**💧 Agua (m³)**")
        filas_agua = []
        for p in periodos_agua_sel:
            apt_info = p.get("apartamentos") or {}
            consumo = float(p["lectura_actual"]) - float(p["lectura_anterior"])
            filas_agua.append({
                "Apartamento": apt_info.get("codigo"),
                "Inquilino": apt_info.get("inquilino_nombre") or "—",
                "Consumo (m³)": consumo,
            })
        if filas_agua:
            filas_agua.sort(key=lambda f: -f["Consumo (m³)"])
            st.dataframe(pd.DataFrame(filas_agua[:5]), use_container_width=True, hide_index=True)
        else:
            st.info("Sin lecturas de agua registradas este periodo.")

    st.divider()
    st.subheader(f"Estado de pago por apartamento — {mes_sel} {anio_sel}")

    if not periodos:
        st.warning("No hay pagos registrados para este periodo todavía. Regístralos en **Pagos de Alquiler**.")
    else:
        periodos_by_apt = {p["apartamento_id"]: p for p in periodos}
        filas = []
        for _, apt in df_apt.iterrows():
            p = periodos_by_apt.get(apt["id"])
            if p:
                pagado = total_pagado(p)
                deuda = float(p["monto_esperado"]) - pagado
                estado_pago = "✅ Pagado" if deuda <= 0 else ("🟡 Parcial" if pagado else "🔴 Pendiente")
                filas.append({
                    "Apartamento": apt["codigo"],
                    "Piso": apt["piso"],
                    "Inquilino": apt.get("inquilino_nombre") or "—",
                    "Monto esperado": p["monto_esperado"],
                    "Pagado": pagado,
                    "Deuda": deuda,
                    "Estado": estado_pago,
                })
            else:
                filas.append({
                    "Apartamento": apt["codigo"],
                    "Piso": apt["piso"],
                    "Inquilino": apt.get("inquilino_nombre") or "—",
                    "Monto esperado": "—",
                    "Pagado": "—",
                    "Deuda": "—",
                    "Estado": "⚪ Sin registrar",
                })
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Resumen de todos los apartamentos")
    tabla = df_apt[["codigo", "piso", "estado", "inquilino_nombre", "monto_alquiler", "estado_contrato"]].rename(
        columns={"codigo": "Apartamento", "piso": "Piso", "estado": "Estado",
                 "inquilino_nombre": "Inquilino", "monto_alquiler": "Alquiler mensual",
                 "estado_contrato": "Contrato"}
    )
    st.dataframe(tabla, use_container_width=True, hide_index=True)


# ==================================================================
# PÁGINA: APARTAMENTOS
# ==================================================================
elif pagina == "🏠 Apartamentos":
    st.title("🏠 Gestión de Apartamentos")

    tab_lista, tab_nuevo, tab_importar = st.tabs(["📋 Lista y edición", "➕ Nuevo apartamento", "📥 Importar CSV"])

    with tab_lista:
        apartamentos = cargar_apartamentos()
        if not apartamentos:
            st.info("No hay apartamentos registrados todavía.")
        else:
            codigos = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
            idx = st.selectbox("Selecciona un apartamento para ver o editar", range(len(apartamentos)),
                                format_func=lambda i: codigos[i])
            apt = apartamentos[idx]

            with st.form("editar_apartamento"):
                col1, col2 = st.columns(2)
                with col1:
                    codigo = st.text_input("Código", value=apt["codigo"])
                    piso = st.selectbox("Piso", PISOS, index=PISOS.index(apt["piso"]) if apt["piso"] in PISOS else 0)
                    estado = st.selectbox("Estado", ["Ocupado", "Desocupado"],
                                           index=0 if apt["estado"] == "Ocupado" else 1)
                    inquilino_nombre = st.text_input("Nombre del inquilino", value=apt.get("inquilino_nombre") or "")
                    celular = st.text_input("Celular", value=apt.get("celular") or "")
                    cedula_identidad = st.text_input("Cédula de identidad", value=apt.get("cedula_identidad") or "")
                    nacionalidad = st.text_input("Nacionalidad", value=apt.get("nacionalidad") or "")
                    monto_alquiler = st.number_input("Monto de alquiler mensual (Bs)", min_value=0.0,
                                                      value=float(apt.get("monto_alquiler") or 0), step=50.0)
                with col2:
                    referencia_nombre = st.text_input("Referencia - nombre", value=apt.get("referencia_nombre") or "")
                    referencia_parentesco = st.text_input("Referencia - parentesco",
                                                           value=apt.get("referencia_parentesco") or "")
                    referencia_celular = st.text_input("Referencia - celular", value=apt.get("referencia_celular") or "")
                    _raw_fecha = apt.get("fecha_ingreso")
                    try:
                        _fecha_val = date.fromisoformat(str(_raw_fecha)[:10]) if _raw_fecha else None
                    except ValueError:
                        _fecha_val = None
                    fecha_ingreso = st.date_input("Fecha de ingreso", value=_fecha_val, format="DD/MM/YYYY")
                    garantia = st.text_input("Garantía", value=apt.get("garantia") or "")
                    amoblado = st.text_area("Amoblado", value=apt.get("amoblado") or "", height=70)
                    detalle = st.text_area("Detalle (ej. incluye agua/internet)", value=apt.get("detalle") or "",
                                            height=70)

                notas = st.text_area("Notas", value=apt.get("notas") or "")

                st.divider()
                st.markdown("**📄 Datos del contrato**")
                colc1, colc2 = st.columns(2)
                with colc1:
                    _tipos_contrato = ["", "Alquiler", "Anticrético"]
                    tipo_contrato = st.selectbox(
                        "Tipo de contrato", _tipos_contrato,
                        index=_tipos_contrato.index(apt["tipo_contrato"]) if apt.get("tipo_contrato") in _tipos_contrato else 0
                    )
                with colc2:
                    _estados_contrato = ["Sin Contrato", "Vigente", "Caducado"]
                    estado_contrato = st.selectbox(
                        "Estado de contrato", _estados_contrato,
                        index=_estados_contrato.index(apt["estado_contrato"]) if apt.get("estado_contrato") in _estados_contrato else 0
                    )
                colc4, colc5 = st.columns(2)
                with colc4:
                    _raw_ci = apt.get("contrato_fecha_inicio")
                    try:
                        _ci_val = date.fromisoformat(str(_raw_ci)[:10]) if _raw_ci else None
                    except ValueError:
                        _ci_val = None
                    contrato_fecha_inicio = st.date_input("Fecha inicio", value=_ci_val, format="DD/MM/YYYY",
                                                           key="ci_edit")
                with colc5:
                    _raw_cf = apt.get("contrato_fecha_fin")
                    try:
                        _cf_val = date.fromisoformat(str(_raw_cf)[:10]) if _raw_cf else None
                    except ValueError:
                        _cf_val = None
                    contrato_fecha_fin = st.date_input("Fecha fin", value=_cf_val, format="DD/MM/YYYY",
                                                        key="cf_edit")
                contrato_observaciones = st.text_area("Observaciones del contrato",
                                                       value=apt.get("contrato_observaciones") or "")

                col_a, col_b = st.columns([1, 1])
                guardar = col_a.form_submit_button("💾 Guardar cambios", use_container_width=True)
                eliminar = col_b.form_submit_button("🗑️ Eliminar apartamento", use_container_width=True)

                if guardar:
                    payload = {
                        "codigo": codigo.strip().upper(),
                        "piso": piso,
                        "estado": estado,
                        "inquilino_nombre": inquilino_nombre or None,
                        "celular": celular or None,
                        "cedula_identidad": cedula_identidad or None,
                        "nacionalidad": nacionalidad or None,
                        "referencia_nombre": referencia_nombre or None,
                        "referencia_parentesco": referencia_parentesco or None,
                        "referencia_celular": referencia_celular or None,
                        "fecha_ingreso": str(fecha_ingreso) if fecha_ingreso else None,
                        "garantia": garantia or None,
                        "amoblado": amoblado or None,
                        "detalle": detalle or None,
                        "monto_alquiler": monto_alquiler,
                        "notas": notas or None,
                        "tipo_contrato": tipo_contrato or None,
                        "estado_contrato": estado_contrato,
                        "contrato_fecha_inicio": str(contrato_fecha_inicio) if contrato_fecha_inicio else None,
                        "contrato_fecha_fin": str(contrato_fecha_fin) if contrato_fecha_fin else None,
                        "contrato_observaciones": contrato_observaciones or None,
                    }
                    try:
                        db.actualizar_apartamento(apt["id"], payload)
                        limpiar_cache()
                        st.success("Apartamento actualizado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al actualizar: {e}")

                if eliminar:
                    try:
                        db.eliminar_apartamento(apt["id"])
                        limpiar_cache()
                        st.success("Apartamento eliminado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")

    with tab_nuevo:
        with st.form("nuevo_apartamento", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código (ej. PB-01)")
                piso = st.selectbox("Piso", PISOS)
                estado = st.selectbox("Estado", ["Ocupado", "Desocupado"])
                inquilino_nombre = st.text_input("Nombre del inquilino")
                celular = st.text_input("Celular")
                monto_alquiler = st.number_input("Monto de alquiler mensual (Bs)", min_value=0.0, step=50.0)
            with col2:
                cedula_identidad = st.text_input("Cédula de identidad")
                nacionalidad = st.text_input("Nacionalidad")
                fecha_ingreso = st.date_input("Fecha de ingreso", value=None, format="DD/MM/YYYY")
                garantia = st.text_input("Garantía")
                detalle = st.text_input("Detalle (ej. incluye agua/internet)")

            st.divider()
            st.markdown("**📄 Datos del contrato**")
            colc1, colc2 = st.columns(2)
            with colc1:
                tipo_contrato = st.selectbox("Tipo de contrato", ["", "Alquiler", "Anticrético"], key="tipo_nuevo")
            with colc2:
                estado_contrato = st.selectbox("Estado de contrato", ["Sin Contrato", "Vigente", "Caducado"],
                                                key="estado_c_nuevo")
            colc3, colc4 = st.columns(2)
            with colc3:
                contrato_fecha_inicio = st.date_input("Fecha inicio", value=None, format="DD/MM/YYYY", key="ci_nuevo")
            with colc4:
                contrato_fecha_fin = st.date_input("Fecha fin", value=None, format="DD/MM/YYYY", key="cf_nuevo")
            contrato_observaciones = st.text_area("Observaciones del contrato", key="obs_c_nuevo")

            crear = st.form_submit_button("➕ Crear apartamento")
            if crear:
                if not codigo:
                    st.error("El código es obligatorio.")
                else:
                    payload = {
                        "codigo": codigo.strip().upper(),
                        "piso": piso,
                        "estado": estado,
                        "inquilino_nombre": inquilino_nombre or None,
                        "celular": celular or None,
                        "cedula_identidad": cedula_identidad or None,
                        "nacionalidad": nacionalidad or None,
                        "fecha_ingreso": str(fecha_ingreso) if fecha_ingreso else None,
                        "garantia": garantia or None,
                        "detalle": detalle or None,
                        "monto_alquiler": monto_alquiler,
                        "tipo_contrato": tipo_contrato or None,
                        "estado_contrato": estado_contrato,
                        "contrato_fecha_inicio": str(contrato_fecha_inicio) if contrato_fecha_inicio else None,
                        "contrato_fecha_fin": str(contrato_fecha_fin) if contrato_fecha_fin else None,
                        "contrato_observaciones": contrato_observaciones or None,
                    }
                    try:
                        db.crear_apartamento(payload)
                        limpiar_cache()
                        st.success(f"Apartamento {codigo} creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear (¿código repetido?): {e}")

    with tab_importar:
        st.write(
            "Sube un archivo CSV con columnas: `codigo, piso, estado, inquilino_nombre, celular, "
            "cedula_identidad, nacionalidad, fecha_ingreso, garantia, amoblado, detalle, monto_alquiler`. "
            "Se recomienda usar la plantilla generada a partir de tu Excel y revisar/corregir los datos antes de importar."
        )
        archivo = st.file_uploader("Archivo CSV", type=["csv"])
        if archivo is not None:
            df_csv = pd.read_csv(archivo)
            st.dataframe(df_csv, use_container_width=True)
            if st.button("📥 Importar estos apartamentos"):
                errores = []
                creados = 0
                for _, row in df_csv.iterrows():
                    payload = {k: (None if pd.isna(v) or v == "" else v) for k, v in row.to_dict().items()}
                    if "codigo" not in payload or not payload["codigo"]:
                        continue
                    try:
                        db.crear_apartamento(payload)
                        creados += 1
                    except Exception as e:
                        errores.append(f'{payload.get("codigo")}: {e}')
                limpiar_cache()
                st.success(f"{creados} apartamentos importados.")
                if errores:
                    st.warning("Algunos registros no se pudieron importar (puede que ya existan):")
                    for e in errores:
                        st.text(e)


# ==================================================================
# PÁGINA: PAGOS DE ALQUILER
# ==================================================================
elif pagina == "💵 Pagos de Alquiler":
    st.title("💵 Pagos de Alquiler")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("Primero registra apartamentos en la sección **Apartamentos**.")
        st.stop()

    tab_registrar, tab_historial = st.tabs(["➕ Registrar abono", "📜 Historial"])

    with tab_registrar:
        codigos = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
        idx = st.selectbox("Apartamento", range(len(apartamentos)), format_func=lambda i: codigos[i])
        apt = apartamentos[idx]

        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", MESES, index=date.today().month - 1)
        with col2:
            anio = st.number_input("Año", min_value=2000, max_value=2100, value=date.today().year, step=1)

        # obtiene (o prepara) el periodo de este apartamento/mes/año, con sus abonos ya hechos
        periodo = db.obtener_periodo(apt["id"], mes, int(anio))
        monto_esperado_actual = float(periodo["monto_esperado"]) if periodo else float(apt.get("monto_alquiler") or 0)
        abonos = periodo.get("pagos", []) if periodo else []
        pagado_hasta_ahora = sum(float(p["monto"]) for p in abonos)
        deuda_actual = monto_esperado_actual - pagado_hasta_ahora

        st.markdown(f"**Monto esperado del mes:** {fmt_money(monto_esperado_actual)}  |  "
                    f"**Pagado hasta ahora:** {fmt_money(pagado_hasta_ahora)}  |  "
                    f"**Deuda actual:** {fmt_money(deuda_actual)}")

        with st.expander("✏️ Cambiar el monto esperado de este mes (si es distinto al alquiler habitual)"):
            with st.form("form_monto_esperado"):
                nuevo_monto_esperado = st.number_input(
                    "Monto esperado (Bs)", min_value=0.0, step=50.0, value=monto_esperado_actual
                )
                guardar_monto = st.form_submit_button("Guardar monto esperado")
                if guardar_monto:
                    try:
                        if periodo:
                            db.actualizar_periodo(periodo["id"], {"monto_esperado": nuevo_monto_esperado})
                        else:
                            db.obtener_o_crear_periodo(apt["id"], mes, int(anio), nuevo_monto_esperado)
                        limpiar_cache()
                        st.success("Monto esperado actualizado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

        st.divider()
        st.subheader("➕ Registrar un nuevo abono")
        with st.form("form_pago", clear_on_submit=True):
            monto_pago = st.number_input("Monto abonado (Bs)", min_value=0.0, step=50.0)
            fecha_pago = st.date_input("Fecha del abono", value=date.today(), format="DD/MM/YYYY")
            metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"])
            observacion = st.text_input("Observación (opcional)")

            guardar = st.form_submit_button("💾 Registrar abono")
            if guardar:
                if monto_pago <= 0:
                    st.error("El monto abonado debe ser mayor a 0.")
                else:
                    try:
                        periodo_actual = db.obtener_o_crear_periodo(apt["id"], mes, int(anio), monto_esperado_actual)
                        db.crear_pago({
                            "periodo_id": periodo_actual["id"],
                            "fecha": str(fecha_pago),
                            "monto": monto_pago,
                            "metodo_pago": metodo_pago,
                            "observacion": observacion or None,
                        })
                        limpiar_cache()
                        st.success("Abono registrado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

        if abonos:
            st.divider()
            st.subheader(f"Abonos ya registrados — {mes} {int(anio)}")
            for p in sorted(abonos, key=lambda x: x["fecha"]):
                with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                    with st.form(f'form_editar_pago_{p["id"]}'):
                        colf, colm = st.columns(2)
                        with colf:
                            _f = date.fromisoformat(str(p["fecha"])[:10])
                            edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY")
                        with colm:
                            edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                          value=float(p["monto"]))
                        edit_metodo = st.selectbox(
                            "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                            index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                            if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0
                        )
                        edit_obs = st.text_input("Observación", value=p.get("observacion") or "")

                        colg, cold = st.columns(2)
                        guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)

                        if guardar_edit:
                            try:
                                db.actualizar_pago(p["id"], {
                                    "fecha": str(edit_fecha),
                                    "monto": edit_monto,
                                    "metodo_pago": edit_metodo,
                                    "observacion": edit_obs or None,
                                })
                                limpiar_cache()
                                st.success("Abono actualizado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar: {e}")

                        if eliminar_edit:
                            try:
                                db.eliminar_pago(p["id"])
                                limpiar_cache()
                                st.success("Abono eliminado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al eliminar: {e}")

    with tab_historial:
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_apt = st.selectbox(
                "Filtrar por apartamento", ["Todos"] + [a["codigo"] for a in apartamentos]
            )
        with col2:
            filtro_anio = st.selectbox("Filtrar por año",
                                        ["Todos"] + list(range(date.today().year - 2, date.today().year + 2)))
        with col3:
            filtro_mes = st.selectbox("Filtrar por mes", ["Todos"] + MESES)

        apt_id = None
        if filtro_apt != "Todos":
            apt_id = next(a["id"] for a in apartamentos if a["codigo"] == filtro_apt)

        periodos = db.listar_periodos(
            apartamento_id=apt_id,
            anio=None if filtro_anio == "Todos" else filtro_anio,
            mes=None if filtro_mes == "Todos" else filtro_mes,
        )

        if not periodos:
            st.info("No hay periodos que coincidan con el filtro.")
        else:
            filas = []
            for p in periodos:
                apt_info = p.get("apartamentos") or {}
                pagado = total_pagado(p)
                deuda = float(p["monto_esperado"]) - pagado
                n_abonos = len(p.get("pagos") or [])
                filas.append({
                    "Apartamento": apt_info.get("codigo"),
                    "Inquilino": apt_info.get("inquilino_nombre"),
                    "Mes": p["mes"],
                    "Año": p["anio"],
                    "Esperado": p["monto_esperado"],
                    "Pagado": pagado,
                    "Deuda": deuda,
                    "N° de abonos": n_abonos,
                })
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

            total_esperado = sum(f["Esperado"] for f in filas)
            total_recaudado = sum(f["Pagado"] for f in filas)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total esperado", fmt_money(total_esperado))
            c2.metric("Total pagado", fmt_money(total_recaudado))
            c3.metric("Total deuda", fmt_money(total_esperado - total_recaudado))

            with st.expander("🔍 Ver y editar los abonos de un periodo específico"):
                opciones = [f'{f["Apartamento"]} — {f["Mes"]} {f["Año"]}' for f in filas]
                sel = st.selectbox("Periodo", range(len(opciones)), format_func=lambda i: opciones[i])
                detalle_periodo = periodos[sel]
                detalle_abonos = detalle_periodo.get("pagos") or []
                if not detalle_abonos:
                    st.write("Sin abonos registrados.")
                else:
                    for p in sorted(detalle_abonos, key=lambda x: x["fecha"]):
                        with st.expander(
                            f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'
                        ):
                            with st.form(f'form_editar_pago_hist_{p["id"]}'):
                                colf, colm = st.columns(2)
                                with colf:
                                    _f = date.fromisoformat(str(p["fecha"])[:10])
                                    edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY")
                                with colm:
                                    edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                                  value=float(p["monto"]))
                                edit_metodo = st.selectbox(
                                    "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                    index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                    if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0
                                )
                                edit_obs = st.text_input("Observación", value=p.get("observacion") or "")

                                colg, cold = st.columns(2)
                                guardar_edit = colg.form_submit_button("💾 Guardar cambios",
                                                                        use_container_width=True)
                                eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono",
                                                                         use_container_width=True)

                                if guardar_edit:
                                    try:
                                        db.actualizar_pago(p["id"], {
                                            "fecha": str(edit_fecha),
                                            "monto": edit_monto,
                                            "metodo_pago": edit_metodo,
                                            "observacion": edit_obs or None,
                                        })
                                        limpiar_cache()
                                        st.success("Abono actualizado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al actualizar: {e}")

                                if eliminar_edit:
                                    try:
                                        db.eliminar_pago(p["id"])
                                        limpiar_cache()
                                        st.success("Abono eliminado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: ELECTRICIDAD
# ==================================================================
elif pagina == "⚡ Electricidad":
    st.title("⚡ Control de Electricidad")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("Primero registra apartamentos en la sección **Apartamentos**.")
        st.stop()

    with st.expander("⚙️ Tarifa por Kwh vigente"):
        tarifa_actual = db.obtener_tarifa_kwh()
        with st.form("form_tarifa"):
            nueva_tarifa = st.number_input(
                "Tarifa por Kwh (Bs)", min_value=0.0, step=0.01, format="%.4f", value=tarifa_actual
            )
            if st.form_submit_button("Guardar tarifa"):
                try:
                    db.guardar_tarifa_kwh(nueva_tarifa)
                    st.success("Tarifa actualizada. Se usará como valor por defecto para nuevas lecturas.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar lectura y abono", "📜 Historial"])

    with tab_registrar:
        codigos = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
        idx = st.selectbox("Apartamento", range(len(apartamentos)), format_func=lambda i: codigos[i], key="elec_apt")
        apt = apartamentos[idx]

        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", MESES, index=date.today().month - 1, key="elec_mes")
        with col2:
            anio = st.number_input("Año", min_value=2000, max_value=2100, value=date.today().year, step=1,
                                    key="elec_anio")

        periodo = db.obtener_periodo_electricidad(apt["id"], mes, int(anio))

        if periodo:
            kwh_anterior_default = float(periodo["kwh_anterior"])
            kwh_actual_default = float(periodo["kwh_actual"])
            tarifa_default = float(periodo["tarifa_kwh"])
        else:
            anterior_periodo = db.ultimo_periodo_electricidad(apt["id"])
            kwh_anterior_default = float(anterior_periodo["kwh_actual"]) if anterior_periodo else 0.0
            kwh_actual_default = kwh_anterior_default
            tarifa_default = tarifa_actual

        st.subheader("📏 Lectura del medidor")
        with st.form("form_lectura"):
            colk1, colk2, colk3 = st.columns(3)
            with colk1:
                kwh_anterior = st.number_input("Kwh anterior", min_value=0.0, step=1.0, value=kwh_anterior_default)
            with colk2:
                kwh_actual = st.number_input("Kwh actual", min_value=0.0, step=1.0, value=kwh_actual_default)
            with colk3:
                tarifa_kwh = st.number_input("Tarifa por Kwh (Bs)", min_value=0.0, step=0.01, format="%.4f",
                                              value=tarifa_default)

            consumo = max(kwh_actual - kwh_anterior, 0)
            monto_calculado = consumo * tarifa_kwh
            st.caption(f"Consumo: {consumo:g} Kwh  ×  Bs {tarifa_kwh:.4f}  =  **{fmt_money(monto_calculado)}**")

            guardar_lectura = st.form_submit_button("💾 Guardar lectura")
            if guardar_lectura:
                payload = {
                    "kwh_anterior": kwh_anterior,
                    "kwh_actual": kwh_actual,
                    "tarifa_kwh": tarifa_kwh,
                    "monto_esperado": monto_calculado,
                }
                try:
                    if periodo:
                        db.actualizar_periodo_electricidad(periodo["id"], payload)
                    else:
                        payload.update({"apartamento_id": apt["id"], "mes": mes, "anio": int(anio)})
                        db.crear_periodo_electricidad(payload)
                    limpiar_cache()
                    st.success("Lectura guardada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

        if periodo:
            abonos = periodo.get("pagos_electricidad", []) or []
            pagado_hasta_ahora = sum(float(p["monto"]) for p in abonos)
            deuda_actual = float(periodo["monto_esperado"]) - pagado_hasta_ahora

            st.markdown(f"**Monto esperado del mes:** {fmt_money(periodo['monto_esperado'])}  |  "
                        f"**Pagado hasta ahora:** {fmt_money(pagado_hasta_ahora)}  |  "
                        f"**Deuda actual:** {fmt_money(deuda_actual)}")

            st.divider()
            st.subheader("➕ Registrar un nuevo abono")
            with st.form("form_pago_elec", clear_on_submit=True):
                monto_pago = st.number_input("Monto abonado (Bs)", min_value=0.0, step=10.0)
                fecha_pago = st.date_input("Fecha del abono", value=date.today(), format="DD/MM/YYYY")
                metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                            key="metodo_elec")
                observacion = st.text_input("Observación (opcional)", key="obs_elec")

                guardar = st.form_submit_button("💾 Registrar abono")
                if guardar:
                    if monto_pago <= 0:
                        st.error("El monto abonado debe ser mayor a 0.")
                    else:
                        try:
                            db.crear_pago_electricidad({
                                "periodo_id": periodo["id"],
                                "fecha": str(fecha_pago),
                                "monto": monto_pago,
                                "metodo_pago": metodo_pago,
                                "observacion": observacion or None,
                            })
                            limpiar_cache()
                            st.success("Abono registrado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

            if abonos:
                st.divider()
                st.subheader(f"Abonos ya registrados — {mes} {int(anio)}")
                for p in sorted(abonos, key=lambda x: x["fecha"]):
                    with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                        with st.form(f'form_editar_pago_elec_{p["id"]}'):
                            colf, colm = st.columns(2)
                            with colf:
                                _f = date.fromisoformat(str(p["fecha"])[:10])
                                edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY")
                            with colm:
                                edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                              value=float(p["monto"]))
                            edit_metodo = st.selectbox(
                                "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0
                            )
                            edit_obs = st.text_input("Observación", value=p.get("observacion") or "")

                            colg, cold = st.columns(2)
                            guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                            eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)

                            if guardar_edit:
                                try:
                                    db.actualizar_pago_electricidad(p["id"], {
                                        "fecha": str(edit_fecha),
                                        "monto": edit_monto,
                                        "metodo_pago": edit_metodo,
                                        "observacion": edit_obs or None,
                                    })
                                    limpiar_cache()
                                    st.success("Abono actualizado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al actualizar: {e}")

                            if eliminar_edit:
                                try:
                                    db.eliminar_pago_electricidad(p["id"])
                                    limpiar_cache()
                                    st.success("Abono eliminado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al eliminar: {e}")
        else:
            st.info("Guarda primero la lectura del medidor para poder registrar abonos de este mes.")

    with tab_historial:
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_apt = st.selectbox(
                "Filtrar por apartamento", ["Todos"] + [a["codigo"] for a in apartamentos], key="elec_hist_apt"
            )
        with col2:
            filtro_anio = st.selectbox("Filtrar por año",
                                        ["Todos"] + list(range(date.today().year - 2, date.today().year + 2)),
                                        key="elec_hist_anio")
        with col3:
            filtro_mes = st.selectbox("Filtrar por mes", ["Todos"] + MESES, key="elec_hist_mes")

        apt_id = None
        if filtro_apt != "Todos":
            apt_id = next(a["id"] for a in apartamentos if a["codigo"] == filtro_apt)

        periodos_elec = db.listar_periodos_electricidad(
            apartamento_id=apt_id,
            anio=None if filtro_anio == "Todos" else filtro_anio,
            mes=None if filtro_mes == "Todos" else filtro_mes,
        )

        if not periodos_elec:
            st.info("No hay periodos que coincidan con el filtro.")
        else:
            filas = []
            for p in periodos_elec:
                apt_info = p.get("apartamentos") or {}
                pagado = sum(float(a["monto"]) for a in (p.get("pagos_electricidad") or []))
                deuda = float(p["monto_esperado"]) - pagado
                filas.append({
                    "Apartamento": apt_info.get("codigo"),
                    "Inquilino": apt_info.get("inquilino_nombre"),
                    "Mes": p["mes"],
                    "Año": p["anio"],
                    "Kwh anterior": p["kwh_anterior"],
                    "Kwh actual": p["kwh_actual"],
                    "Consumo": float(p["kwh_actual"]) - float(p["kwh_anterior"]),
                    "Esperado": p["monto_esperado"],
                    "Pagado": pagado,
                    "Deuda": deuda,
                })
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

            total_esperado = sum(f["Esperado"] for f in filas)
            total_recaudado = sum(f["Pagado"] for f in filas)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total esperado", fmt_money(total_esperado))
            c2.metric("Total pagado", fmt_money(total_recaudado))
            c3.metric("Total deuda", fmt_money(total_esperado - total_recaudado))

            with st.expander("🔍 Ver y editar los abonos de un periodo específico"):
                opciones = [f'{f["Apartamento"]} — {f["Mes"]} {f["Año"]}' for f in filas]
                sel = st.selectbox("Periodo", range(len(opciones)), format_func=lambda i: opciones[i],
                                    key="sel_hist_elec")
                detalle_periodo = periodos_elec[sel]
                detalle_abonos = detalle_periodo.get("pagos_electricidad") or []
                if not detalle_abonos:
                    st.write("Sin abonos registrados.")
                else:
                    for p in sorted(detalle_abonos, key=lambda x: x["fecha"]):
                        with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                            with st.form(f'form_editar_pago_elec_hist_{p["id"]}'):
                                colf, colm = st.columns(2)
                                with colf:
                                    _f = date.fromisoformat(str(p["fecha"])[:10])
                                    edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY")
                                with colm:
                                    edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                                  value=float(p["monto"]))
                                edit_metodo = st.selectbox(
                                    "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                    index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                    if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0
                                )
                                edit_obs = st.text_input("Observación", value=p.get("observacion") or "")

                                colg, cold = st.columns(2)
                                guardar_edit = colg.form_submit_button("💾 Guardar cambios",
                                                                        use_container_width=True)
                                eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono",
                                                                         use_container_width=True)

                                if guardar_edit:
                                    try:
                                        db.actualizar_pago_electricidad(p["id"], {
                                            "fecha": str(edit_fecha),
                                            "monto": edit_monto,
                                            "metodo_pago": edit_metodo,
                                            "observacion": edit_obs or None,
                                        })
                                        limpiar_cache()
                                        st.success("Abono actualizado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al actualizar: {e}")

                                if eliminar_edit:
                                    try:
                                        db.eliminar_pago_electricidad(p["id"])
                                        limpiar_cache()
                                        st.success("Abono eliminado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al eliminar: {e}")
# ==================================================================
elif pagina == "💧 Agua":
    st.title("💧 Control de Agua")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("Primero registra apartamentos en la sección **Apartamentos**.")
        st.stop()

    with st.expander("⚙️ Tarifa por m³ vigente"):
        tarifa_actual = db.obtener_tarifa_agua()
        with st.form("form_tarifa_agua"):
            nueva_tarifa = st.number_input(
                "Tarifa por m³ (Bs)", min_value=0.0, step=0.01, format="%.4f", value=tarifa_actual
            )
            if st.form_submit_button("Guardar tarifa"):
                try:
                    db.guardar_tarifa_agua(nueva_tarifa)
                    st.success("Tarifa actualizada. Se usará como valor por defecto para nuevas lecturas.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar lectura y abono", "📜 Historial"])

    with tab_registrar:
        codigos = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
        idx = st.selectbox("Apartamento", range(len(apartamentos)), format_func=lambda i: codigos[i], key="agua_apt")
        apt = apartamentos[idx]

        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", MESES, index=date.today().month - 1, key="agua_mes")
        with col2:
            anio = st.number_input("Año", min_value=2000, max_value=2100, value=date.today().year, step=1,
                                    key="agua_anio")

        periodo = db.obtener_periodo_agua(apt["id"], mes, int(anio))

        if periodo:
            lectura_anterior_default = float(periodo["lectura_anterior"])
            lectura_actual_default = float(periodo["lectura_actual"])
            tarifa_default = float(periodo["tarifa_agua"])
        else:
            anterior_periodo = db.ultimo_periodo_agua(apt["id"])
            lectura_anterior_default = float(anterior_periodo["lectura_actual"]) if anterior_periodo else 0.0
            lectura_actual_default = lectura_anterior_default
            tarifa_default = tarifa_actual

        st.subheader("📏 Lectura del medidor")
        with st.form("form_lectura_agua"):
            colk1, colk2, colk3 = st.columns(3)
            with colk1:
                lectura_anterior = st.number_input("Lectura anterior (m³)", min_value=0.0, step=1.0,
                                                     value=lectura_anterior_default)
            with colk2:
                lectura_actual = st.number_input("Lectura actual (m³)", min_value=0.0, step=1.0,
                                                   value=lectura_actual_default)
            with colk3:
                tarifa_agua = st.number_input("Tarifa por m³ (Bs)", min_value=0.0, step=0.01, format="%.4f",
                                               value=tarifa_default)

            consumo = max(lectura_actual - lectura_anterior, 0)
            monto_calculado = consumo * tarifa_agua
            st.caption(f"Consumo: {consumo:g} m³  ×  Bs {tarifa_agua:.4f}  =  **{fmt_money(monto_calculado)}**")

            guardar_lectura = st.form_submit_button("💾 Guardar lectura")
            if guardar_lectura:
                payload = {
                    "lectura_anterior": lectura_anterior,
                    "lectura_actual": lectura_actual,
                    "tarifa_agua": tarifa_agua,
                    "monto_esperado": monto_calculado,
                }
                try:
                    if periodo:
                        db.actualizar_periodo_agua(periodo["id"], payload)
                    else:
                        payload.update({"apartamento_id": apt["id"], "mes": mes, "anio": int(anio)})
                        db.crear_periodo_agua(payload)
                    limpiar_cache()
                    st.success("Lectura guardada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

        if periodo:
            abonos = periodo.get("pagos_agua", []) or []
            pagado_hasta_ahora = sum(float(p["monto"]) for p in abonos)
            deuda_actual = float(periodo["monto_esperado"]) - pagado_hasta_ahora

            st.markdown(f"**Monto esperado del mes:** {fmt_money(periodo['monto_esperado'])}  |  "
                        f"**Pagado hasta ahora:** {fmt_money(pagado_hasta_ahora)}  |  "
                        f"**Deuda actual:** {fmt_money(deuda_actual)}")

            st.divider()
            st.subheader("➕ Registrar un nuevo abono")
            with st.form("form_pago_agua", clear_on_submit=True):
                monto_pago = st.number_input("Monto abonado (Bs)", min_value=0.0, step=10.0)
                fecha_pago = st.date_input("Fecha del abono", value=date.today(), format="DD/MM/YYYY")
                metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                            key="metodo_agua")
                observacion = st.text_input("Observación (opcional)", key="obs_agua")

                guardar = st.form_submit_button("💾 Registrar abono")
                if guardar:
                    if monto_pago <= 0:
                        st.error("El monto abonado debe ser mayor a 0.")
                    else:
                        try:
                            db.crear_pago_agua({
                                "periodo_id": periodo["id"],
                                "fecha": str(fecha_pago),
                                "monto": monto_pago,
                                "metodo_pago": metodo_pago,
                                "observacion": observacion or None,
                            })
                            limpiar_cache()
                            st.success("Abono registrado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

            if abonos:
                st.divider()
                st.subheader(f"Abonos ya registrados — {mes} {int(anio)}")
                for p in sorted(abonos, key=lambda x: x["fecha"]):
                    with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                        with st.form(f'form_editar_pago_agua_{p["id"]}'):
                            colf, colm = st.columns(2)
                            with colf:
                                _f = date.fromisoformat(str(p["fecha"])[:10])
                                edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY")
                            with colm:
                                edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                              value=float(p["monto"]))
                            edit_metodo = st.selectbox(
                                "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0
                            )
                            edit_obs = st.text_input("Observación", value=p.get("observacion") or "")

                            colg, cold = st.columns(2)
                            guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                            eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)

                            if guardar_edit:
                                try:
                                    db.actualizar_pago_agua(p["id"], {
                                        "fecha": str(edit_fecha),
                                        "monto": edit_monto,
                                        "metodo_pago": edit_metodo,
                                        "observacion": edit_obs or None,
                                    })
                                    limpiar_cache()
                                    st.success("Abono actualizado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al actualizar: {e}")

                            if eliminar_edit:
                                try:
                                    db.eliminar_pago_agua(p["id"])
                                    limpiar_cache()
                                    st.success("Abono eliminado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al eliminar: {e}")
        else:
            st.info("Guarda primero la lectura del medidor para poder registrar abonos de este mes.")

    with tab_historial:
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_apt = st.selectbox(
                "Filtrar por apartamento", ["Todos"] + [a["codigo"] for a in apartamentos], key="agua_hist_apt"
            )
        with col2:
            filtro_anio = st.selectbox("Filtrar por año",
                                        ["Todos"] + list(range(date.today().year - 2, date.today().year + 2)),
                                        key="agua_hist_anio")
        with col3:
            filtro_mes = st.selectbox("Filtrar por mes", ["Todos"] + MESES, key="agua_hist_mes")

        apt_id = None
        if filtro_apt != "Todos":
            apt_id = next(a["id"] for a in apartamentos if a["codigo"] == filtro_apt)

        periodos_agua = db.listar_periodos_agua(
            apartamento_id=apt_id,
            anio=None if filtro_anio == "Todos" else filtro_anio,
            mes=None if filtro_mes == "Todos" else filtro_mes,
        )

        if not periodos_agua:
            st.info("No hay periodos que coincidan con el filtro.")
        else:
            filas = []
            for p in periodos_agua:
                apt_info = p.get("apartamentos") or {}
                pagado = sum(float(a["monto"]) for a in (p.get("pagos_agua") or []))
                deuda = float(p["monto_esperado"]) - pagado
                filas.append({
                    "Apartamento": apt_info.get("codigo"),
                    "Inquilino": apt_info.get("inquilino_nombre"),
                    "Mes": p["mes"],
                    "Año": p["anio"],
                    "Lectura anterior": p["lectura_anterior"],
                    "Lectura actual": p["lectura_actual"],
                    "Consumo": float(p["lectura_actual"]) - float(p["lectura_anterior"]),
                    "Esperado": p["monto_esperado"],
                    "Pagado": pagado,
                    "Deuda": deuda,
                })
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

            total_esperado = sum(f["Esperado"] for f in filas)
            total_recaudado = sum(f["Pagado"] for f in filas)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total esperado", fmt_money(total_esperado))
            c2.metric("Total pagado", fmt_money(total_recaudado))
            c3.metric("Total deuda", fmt_money(total_esperado - total_recaudado))

            with st.expander("🔍 Ver y editar los abonos de un periodo específico"):
                opciones = [f'{f["Apartamento"]} — {f["Mes"]} {f["Año"]}' for f in filas]
                sel = st.selectbox("Periodo", range(len(opciones)), format_func=lambda i: opciones[i],
                                    key="sel_hist_agua")
                detalle_periodo = periodos_agua[sel]
                detalle_abonos = detalle_periodo.get("pagos_agua") or []
                if not detalle_abonos:
                    st.write("Sin abonos registrados.")
                else:
                    for p in sorted(detalle_abonos, key=lambda x: x["fecha"]):
                        with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                            with st.form(f'form_editar_pago_agua_hist_{p["id"]}'):
                                colf, colm = st.columns(2)
                                with colf:
                                    _f = date.fromisoformat(str(p["fecha"])[:10])
                                    edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY")
                                with colm:
                                    edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                                  value=float(p["monto"]))
                                edit_metodo = st.selectbox(
                                    "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                    index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                    if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0
                                )
                                edit_obs = st.text_input("Observación", value=p.get("observacion") or "")

                                colg, cold = st.columns(2)
                                guardar_edit = colg.form_submit_button("💾 Guardar cambios",
                                                                        use_container_width=True)
                                eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono",
                                                                         use_container_width=True)

                                if guardar_edit:
                                    try:
                                        db.actualizar_pago_agua(p["id"], {
                                            "fecha": str(edit_fecha),
                                            "monto": edit_monto,
                                            "metodo_pago": edit_metodo,
                                            "observacion": edit_obs or None,
                                        })
                                        limpiar_cache()
                                        st.success("Abono actualizado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al actualizar: {e}")

                                if eliminar_edit:
                                    try:
                                        db.eliminar_pago_agua(p["id"])
                                        limpiar_cache()
                                        st.success("Abono eliminado.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al eliminar: {e}")
