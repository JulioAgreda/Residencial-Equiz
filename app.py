import calendar
import copy
import io
import json
import openpyxl
import zipfile
import streamlit as st
import pandas as pd
from datetime import date
import bcrypt
import db
import accesos
import aire_acondicionado
import compromisos
import conciliacion
import conciliacion_reportes
import cuadre
import consumo as calc_consumo
import estados
import exinquilinos
import extracto
import inventario
import inventario_reportes
import moras
import servicios_basicos
import recibo
# Las fechas operativas deben usar recibo.hoy_bolivia() (UTC-4), no date.today() del servidor.
import rendicion
import reportes
import deudas
import deudores

st.set_page_config(page_title="Residencial EQUIZ", page_icon="🏢", layout="wide", initial_sidebar_state="expanded")


# ------------------------------------------------------------------
# Adaptación móvil: estilos responsivos, cierre del menú y protección
# frente a recargas/cierres accidentales del navegador.
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Áreas táctiles cómodas y mejor aprovechamiento del ancho. */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
            padding-top: 1rem !important;
            padding-bottom: 4.5rem !important;
        }
        h1 { font-size: 1.65rem !important; line-height: 1.2 !important; }
        h2 { font-size: 1.35rem !important; }
        h3 { font-size: 1.15rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.65rem !important; }
        div[data-testid="stButton"] > button,
        div[data-testid="stFormSubmitButton"] > button {
            min-height: 2.8rem !important;
            width: 100%;
            white-space: normal !important;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input,
        div[data-testid="stSelectbox"] div[role="combobox"] {
            min-height: 2.7rem !important;
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            overflow-x: auto !important;
            max-width: 100% !important;
        }
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.65rem !important;
        }
        div[data-testid="column"] {
            min-width: min(100%, 280px) !important;
            flex: 1 1 100% !important;
        }
        section[data-testid="stSidebar"] {
            z-index: 1000000 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.55rem;
        }
        /* Evita que etiquetas largas rompan el ancho del teléfono. */
        label, p, span, div {
            overflow-wrap: anywhere;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# El componente instala listeners en el documento principal para cerrar el
# sidebar después de seleccionar una opción en pantallas móviles.
st.components.v1.html(
    """
    <script>
    (function () {
      try {
        const host = window.parent;
        if (!host || !host.document) return;

        // Advertencia nativa del navegador al recargar/cerrar/salir de la página.
        // No se activa al cambiar de módulo dentro de Streamlit (rerun normal).
        if (!host.__equizBeforeUnloadBound) {
          host.__equizBeforeUnloadBound = true;
          host.addEventListener("beforeunload", function (event) {
            event.preventDefault();
            event.returnValue = "";
            return "";
          });
        }

        // Cierre móvil robusto: escuchar la selección del menú en el documento
        // principal. El listener persiste aunque Streamlit vuelva a renderizar
        // el componente después de cambiar de página.
        const mobile = () => host.matchMedia("(max-width: 768px)").matches;

        const closeSidebarOnMobile = function () {
          if (!mobile()) return false;
          const doc = host.document;
          const sidebar = doc.querySelector('section[data-testid="stSidebar"]');
          if (!sidebar) return false;

          const candidates = [
            sidebar.querySelector('button[data-testid="stSidebarCollapseButton"]'),
            sidebar.querySelector('button[aria-label*="Collapse"]'),
            sidebar.querySelector('button[aria-label*="Close"]'),
            sidebar.querySelector('button[aria-label*="Cerrar"]'),
            sidebar.querySelector('button[kind="header"]')
          ].filter(Boolean);

          for (const btn of candidates) {
            const r = btn.getBoundingClientRect();
            const visible = r.width > 0 && r.height > 0 &&
              host.getComputedStyle(btn).visibility !== "hidden" &&
              host.getComputedStyle(btn).display !== "none";
            if (visible) {
              btn.click();
              return true;
            }
          }
          return false;
        };

        const scheduleSidebarClose = function () {
          // Streamlit procesa el cambio de radio y puede reconstruir el DOM.
          // Reintentar durante el rerun para cerrar el panel cuando reaparezca.
          [80, 180, 350, 650, 1000].forEach(ms => {
            host.setTimeout(closeSidebarOnMobile, ms);
          });
        };

        if (!host.__equizMobileSidebarListener) {
          host.__equizMobileSidebarListener = true;
          const isSidebarNavigation = function (target) {
            if (!target || !target.closest) return false;
            const sidebar = target.closest('section[data-testid="stSidebar"]');
            if (!sidebar) return false;
            return !!target.closest(
              'input[type="radio"], label, [role="radio"], button'
            );
          };

          host.document.addEventListener("change", function (event) {
            if (isSidebarNavigation(event.target)) scheduleSidebarClose();
          }, true);

          host.document.addEventListener("click", function (event) {
            if (isSidebarNavigation(event.target)) scheduleSidebarClose();
          }, true);
        }

        // También intenta cerrar si el componente se monta con el menú abierto.
        scheduleSidebarClose();
      } catch (e) {
        // La app sigue funcionando aunque el navegador limite el acceso al DOM.
      }
    })();
    </script>
    """,
    height=0,
    scrolling=False,
)

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

PISOS = ["Planta Baja", "Primer Piso", "Segundo Piso", "Tercer Piso"]
ROLES = ["Administrador", "Cobrador"]

CATEGORIAS_COMPRA = ["Artículos de limpieza", "Repuestos", "Herramientas", "Dispositivos", "Otros artículos"]
CATEGORIAS_GASTO_OPERATIVO = ["Electricidad", "Agua", "Internet", "Honorarios", "Sueldos", "Viáticos", "Impuestos", "Otros servicios y gastos"]
# Compatibilidad temporal con ramas históricas de la aplicación que se conservan para reversión.
CATEGORIAS_GASTO = CATEGORIAS_COMPRA
CATEGORIAS_PAGO = CATEGORIAS_GASTO_OPERATIVO
CONCEPTOS_VENTA = ["Muebles", "Equipos", "Copias de llave", "Otros"]
METODOS_PAGO_MOVIMIENTOS = ["Efectivo", "QR", "Transferencia Bancaria", "Tarjeta", "Otro"]

PRIORIDADES_PENDIENTE = ["Urgente", "Alta", "Media", "Baja"]
ESTADOS_PENDIENTE = ["Pendiente", "En Proceso", "Terminado"]
COLOR_PRIORIDAD = {"Urgente": "🔴", "Alta": "🟠", "Media": "🟡", "Baja": "🟢"}
ICONO_ESTADO = {"Pendiente": "⏳", "En Proceso": "🔧", "Terminado": "✅"}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ------------------------------------------------------------------
# Autenticación con usuario/contraseña y roles (Administrador / Cobrador)
# ------------------------------------------------------------------
def check_login():
    if st.session_state.get("usuario"):
        return True

    # Pantalla de acceso: identidad institucional limpia y adaptable.
    st.markdown(
        """
        <style>
        /* El login usa un lienzo más compacto que el resto del sistema. */
        .block-container {
            max-width: 900px !important;
            padding-top: clamp(1.2rem, 5vh, 3.5rem) !important;
            padding-bottom: 2rem !important;
        }
        .login-brand {
            text-align: center;
            margin: 0 auto 1.25rem auto;
        }
        .login-brand h1 {
            font-size: clamp(1.55rem, 4vw, 2.15rem);
            line-height: 1.15;
            margin: .25rem 0 .35rem 0;
            letter-spacing: -.025em;
        }
        .login-brand p {
            color: #A8B3C2;
            margin: 0;
            font-size: .96rem;
        }
        .login-tag {
            display: inline-block;
            color: #D8B15A;
            border: 1px solid rgba(216,177,90,.38);
            border-radius: 999px;
            padding: .25rem .75rem;
            font-size: .76rem;
            letter-spacing: .08em;
            text-transform: uppercase;
            margin-bottom: .55rem;
        }
        /* Centra y limita el formulario en escritorio; en móvil ocupa el ancho útil. */
        div[data-testid="stForm"] {
            max-width: 490px;
            margin: 0 auto !important;
            padding: clamp(1rem, 3vw, 1.55rem) !important;
            border: 1px solid rgba(216,177,90,.30) !important;
            border-radius: 16px !important;
            background: rgba(255,255,255,.025);
        }
        div[data-testid="stForm"] input {
            min-height: 2.9rem;
        }
        div[data-testid="stForm"] button {
            min-height: 2.9rem;
            width: 100%;
            font-weight: 650;
        }
        div[data-testid="stExpander"] {
            max-width: 490px;
            margin: .75rem auto 0 auto;
        }
        .login-foot {
            text-align: center;
            color: #8792A1;
            font-size: .78rem;
            margin-top: 1.4rem;
        }
        @media (max-width: 600px) {
            .block-container {
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-top: 1.25rem !important;
            }
            .login-brand { margin-bottom: 1rem; }
        div[data-testid="stImage"] img { display:block; margin-left:auto; margin-right:auto; max-width:100%; height:auto; }
            .login-brand p { font-size: .88rem; }
            div[data-testid="stForm"] {
                width: 100%;
                padding: 1rem !important;
                border-radius: 13px !important;
            }
            div[data-testid="stExpander"] { width: 100%; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    logo_login = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo_equise_horizontal.png")
    if os.path.exists(logo_login):
        st.image(logo_login, width=260)

    st.markdown(
        """
        <div class="login-brand">
            <span class="login-tag">Acceso seguro</span>
            <h1>Edificio Residencial Equise</h1>
            <p>Sistema de administración y control residencial</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        usuarios_existentes = db.listar_usuarios()
    except Exception as e:
        st.error(f"No se pudo conectar con la base de usuarios: {e}")
        st.info("Verifica la conexión con Supabase y que esté instalada la migración de usuarios.")
        return False

    if not usuarios_existentes:
        st.info("Configuración inicial: crea la cuenta del Administrador principal.")
        with st.form("form_primer_admin"):
            username = st.text_input("Usuario", placeholder="Crea tu nombre de usuario")
            nombre = st.text_input("Nombre completo", placeholder="Nombre del administrador")
            pwd1 = st.text_input("Contraseña", type="password", placeholder="Crea una contraseña segura")
            pwd2 = st.text_input("Confirmar contraseña", type="password", placeholder="Repite la contraseña")
            crear = st.form_submit_button("Crear administrador")
            if crear:
                if not username or not pwd1:
                    st.error("Usuario y contraseña son obligatorios.")
                elif pwd1 != pwd2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    try:
                        db.crear_usuario({
                            "username": username.strip().lower(),
                            "nombre": nombre or None,
                            "password_hash": hash_password(pwd1),
                            "rol": "Administrador",
                            "activo": True,
                        })
                        st.success("Administrador creado. Ahora inicia sesión.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear el usuario: {e}")
        st.markdown('<div class="login-foot">Residencial Equise · Administración residencial</div>', unsafe_allow_html=True)
        return False

    with st.form("form_login", clear_on_submit=False):
        username = st.text_input(
            "Usuario", placeholder="Ingresa tu usuario",
            autocomplete="username"
        )
        pwd = st.text_input(
            "Contraseña", type="password", placeholder="Ingresa tu contraseña",
            autocomplete="current-password"
        )
        ingresar = st.form_submit_button("Ingresar al sistema", use_container_width=True)
        if ingresar:
            if not username.strip() or not pwd:
                st.warning("Ingresa tu usuario y contraseña.")
            else:
                usuario = db.obtener_usuario_por_username(username.strip().lower())
                if usuario and usuario.get("activo") and verificar_password(pwd, usuario["password_hash"]):
                    st.session_state["usuario"] = usuario
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos, o el usuario está desactivado.")

    with st.expander("¿Problemas para ingresar?"):
        st.caption("Usa esta opción únicamente si eres administrador y tienes la clave general.")
        with st.form("form_login_general"):
            pwd_general = st.text_input("Clave general de administrador", type="password")
            ingresar_general = st.form_submit_button("Ingresar como administrador", use_container_width=True)
            if ingresar_general:
                if pwd_general and pwd_general == st.secrets.get("APP_PASSWORD", ""):
                    st.session_state["usuario"] = {
                        "username": "admin", "nombre": "Administrador", "rol": "Administrador"
                    }
                    st.rerun()
                else:
                    st.error("Clave incorrecta.")

    st.markdown(
        '<div class="login-foot">Acceso exclusivo para personal autorizado · Residencial Equise</div>',
        unsafe_allow_html=True,
    )
    return False


if not check_login():
    st.stop()

usuario_actual = st.session_state["usuario"]
es_admin = usuario_actual.get("rol") == "Administrador"
# Solo el Administrador y el usuario Viovip pueden modificar el Estado de Compras, Pagos y Ventas
puede_editar_estado = estados.puede_modificar(usuario_actual, es_admin)


# ------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------
def fmt_money(v):
    try:
        return f"Bs {float(v):,.2f}"
    except (TypeError, ValueError):
        return "Bs 0.00"


def detalle_monto_servicio(consumo, tarifa):
    """Resultado de consumo × tarifa para mostrar en pantalla: 'Bs 76.70 → **Bs 77.00** (redondeado al entero)'
    si el redondeo cambia el monto, o solo '**Bs 77.00**' si ya era entero."""
    exacto = calc_consumo.monto_exacto(consumo, tarifa)
    final = calc_consumo.calcular_monto(consumo, tarifa)
    if abs(exacto - final) > 0.004:
        return f"{fmt_money(exacto)} → **{fmt_money(final)}** (redondeado al entero)"
    return f"**{fmt_money(final)}**"


def _solo_permitidos(cargador, campo="apartamento_id", permitir_vacio=False):
    """Envuelve un cargador en caché para que cada usuario vea SOLO los datos de sus apartamentos asignados.
    La caché guarda los datos de todos (se comparte entre usuarios); el filtro se aplica DESPUÉS, por usuario.
    Así ninguna pantalla puede olvidarse de filtrar: todas leen a través de estos cargadores."""
    def filtrado(*args, **kwargs):
        return accesos.filtrar(cargador(*args, **kwargs), ids_apartamentos_permitidos(), campo, permitir_vacio)
    filtrado.clear = cargador.clear          # limpiar_cache() sigue funcionando igual
    return filtrado


def _solo_mis_apartamentos(registros, campo="apartamento_id", permitir_vacio=False):
    """Filtro para lecturas directas a la base que no pasan por un cargador."""
    return accesos.filtrar(registros, ids_apartamentos_permitidos(), campo, permitir_vacio)


@st.cache_data(ttl=30)
def _cargar_apartamentos_todos():
    return db.listar_apartamentos()


@st.cache_data(ttl=30)
def _cargar_periodos_todos(apartamento_id=None, anio=None, mes=None):
    # solo_activos: los periodos cerrados de inquilinos que ya salieron NO se mezclan con los del inquilino actual
    # (se ven en «🚪 Ex inquilinos»)
    return db.listar_periodos(apartamento_id=apartamento_id, anio=anio, mes=mes, solo_activos=True)


@st.cache_data(ttl=30)
def _cargar_periodos_electricidad_todos(anio=None, mes=None):
    return db.listar_periodos_servicio("electricidad", anio=anio, mes=mes, solo_activos=True)


@st.cache_data(ttl=30)
def _cargar_periodos_agua_todos(anio=None, mes=None):
    return db.listar_periodos_servicio("agua", anio=anio, mes=mes, solo_activos=True)


@st.cache_data(ttl=60)
def _cargar_periodos_abiertos_todos(tipo):
    return db.listar_periodos_abiertos(tipo)


cargar_apartamentos = _solo_permitidos(_cargar_apartamentos_todos, campo="id")
cargar_periodos = _solo_permitidos(_cargar_periodos_todos)
cargar_periodos_electricidad = _solo_permitidos(_cargar_periodos_electricidad_todos)
cargar_periodos_agua = _solo_permitidos(_cargar_periodos_agua_todos)
cargar_periodos_abiertos = _solo_permitidos(_cargar_periodos_abiertos_todos)


@st.cache_data(ttl=60)
def _cargar_periodos_cerrados_todos(tipo):
    """Periodos cerrados de los ex inquilinos (alquiler / electricidad / agua), con sus abonos."""
    return db.listar_periodos_cerrados(tipo)


@st.cache_data(ttl=60)
def _cargar_historial_todos():
    return db.listar_inquilinos_historial()


cargar_periodos_cerrados = _solo_permitidos(_cargar_periodos_cerrados_todos)
cargar_historial = _solo_permitidos(_cargar_historial_todos)


@st.cache_data(ttl=30)
def cargar_inventario_articulos():
    return db.listar_inventario_articulos()


@st.cache_data(ttl=30)
def cargar_inventario_movimientos():
    return db.listar_inventario_movimientos()


AVISO_MIGRACION_DEVOLUCION = (
    "Para registrar **a quién se realizó la devolución**, ejecuta el archivo "
    "`migracion_devolucion_usuario.sql` en el SQL Editor de Supabase. Mientras tanto, esta sección "
    "funciona normal, sin ese dato."
)


AVISO_MIGRACION_ESTADOS = (
    "El campo **Estado** todavía no está activo en la base de datos: ejecuta el archivo "
    "`migracion_estados_movimientos.sql` en el SQL Editor de Supabase. Mientras tanto, esta sección "
    "funciona normal, sin ese campo."
)


AVISO_MIGRACION_AIRE = (
    "El dato **Aire acondicionado** todavía no está activo en la base de datos: ejecuta el archivo "
    "`migracion_aire_acondicionado.sql` en el SQL Editor de Supabase. Mientras tanto, los apartamentos "
    "funcionan normal, sin ese dato."
)

AVISO_MIGRACION_AIRE_PROPIEDAD = (
    "Falta activar **«¿de quién es el aire acondicionado?»**: vuelve a ejecutar completo el archivo "
    "`migracion_aire_acondicionado.sql` en el SQL Editor de Supabase (es repetible). Mientras tanto solo se "
    "guarda si tiene aire o no."
)

@st.cache_data(ttl=30)
def cargar_accesos_apartamentos():
    """{usuario_id: {"todos": bool, "ids": set}}; se relee cada 30 s (y al instante cuando el administrador guarda un cambio)."""
    return accesos.construir_accesos(db.listar_usuarios(), db.listar_accesos_apartamentos())


def acceso_por_apartamento_activo():
    return estado_disponible("usuarios", "acceso_todos_apartamentos") and estado_disponible("usuarios_apartamentos", "usuario_id")


def ids_apartamentos_permitidos():
    """None = ve todos los apartamentos; si no, el conjunto de ids que puede ver el usuario actual.
    El administrador siempre ve todos. Sin la migración SQL no hay restricciones (funciona como antes)."""
    if es_admin:
        return None
    activo = acceso_por_apartamento_activo()
    return accesos.resolver(es_admin, usuario_actual.get("id"), cargar_accesos_apartamentos() if activo else {}, activo)


AVISO_PERIODOS_ILEGIBLES = (
    "⚠️ Hay **{n}** periodo(s) de pagos con un mes o año que la app no reconoce. **Sus pagos y deudas NO se están "
    "contando** en estos reportes. Corrígelos en Supabase (tablas `periodos_alquiler`, `periodos_electricidad` o "
    "`periodos_agua`): el mes debe ser uno de Enero … Diciembre."
)


@st.cache_data(ttl=60)
def estado_disponible(tabla, columna):
    """¿Ya existe la columna de estado? (si aún no se ejecutó la migración, la app sigue funcionando sin ella)"""
    return db.columna_disponible(tabla, columna)


@st.cache_data(ttl=60)
def devolucion_a_disponible(tabla):
    """¿Ya existe la columna `devolucion_a` (a quién se le devolvió el dinero)?"""
    return estado_disponible(tabla, "devolucion_a")


def selector_devolucion_a(key, actual=None):
    """«Devolución realizada a» de Compras y Pagos: un usuario activo (más el ya guardado, si ya no está activo) o
    «Tercero (persona externa)» con el nombre escrito aparte. Solo la pueden cambiar el Administrador y Viovip, igual
    que el Estado. Devuelve lo que se guarda («Nombre», «Tercero: Nombre») o None."""
    guardado, nombre_guardado = estados.separar_devolucion_a(actual)
    nombres = {u.get("nombre") or u.get("username") for u in cargar_usuarios_activos()}
    opciones = ["—"] + sorted((n for n in nombres if n), key=str.casefold)
    if guardado and guardado not in opciones and guardado != estados.OPCION_TERCERO:
        opciones.append(guardado)
    opciones.append(estados.OPCION_TERCERO)
    elegido = st.selectbox(
        "Devolución realizada a", opciones, index=opciones.index(guardado) if guardado in opciones else 0, key=key,
        disabled=not puede_editar_estado,
        help=(estados.AYUDA_SIN_PERMISO if not puede_editar_estado else
              "Elige el usuario al que se le devolvió el dinero, o «Tercero (persona externa)» si se le devolvió a alguien que "
              "no es usuario del sistema. Solo se guarda si el Estado indica que la devolución ya se realizó."))
    nombre_tercero = st.text_input(
        "Nombre del tercero (solo si elegiste «Tercero»)", value=nombre_guardado, key=f"{key}_tercero",
        disabled=not puede_editar_estado, max_chars=100, placeholder="Persona o empresa externa que recibió la devolución")
    return estados.componer_devolucion_a(None if elegido == "—" else elegido, nombre_tercero)


def texto_error_inventario(prefijo, error):
    """Mensaje de error del inventario; si parece que falta crear las tablas, lo dice."""
    texto = str(error)
    if any(x in texto.lower() for x in ("inventario_", "does not exist", "could not find", "schema cache")):
        texto += ("\n\nParece que falta crear las tablas del inventario: ejecuta `migracion_inventario.sql` en el SQL Editor "
                  "de Supabase (una sola vez).")
    return f"{prefijo}: {texto}"


def texto_error_historial(prefijo, error):
    """Mensaje de error del historial de inquilinos; si parece que falta algo en la base de datos, lo dice."""
    texto = str(error)
    if any(x in texto.lower() for x in ("registrar_salida_inquilino", "inquilinos_historial", "inquilino_historial_id", "could not find", "does not exist")):
        texto += ("\n\nParece que falta algo del historial de inquilinos en la base de datos. Ejecuta "
                  "`verificar_historial_inquilinos.sql` en el SQL Editor de Supabase para ver qué falta.")
    return f"{prefijo}: {texto}"


def texto_error_guardado(prefijo, error):
    """Mensaje de error de guardado; si parece un problema de migración pendiente, lo dice."""
    texto = str(error)
    if any(x in texto.lower() for x in ("estado_devolucion", "devolucion_a", "value too long", "check constraint")):
        texto += ("\n\nSi acabas de actualizar la aplicación, ejecuta `migracion_devolucion_usuario.sql` "
                  "en el SQL Editor de Supabase.")
    return f"{prefijo}: {texto}"


@st.cache_data(ttl=30)
def cargar_servicios_basicos():
    return db.listar_servicios_basicos()


@st.cache_data(ttl=30)
def _cargar_compromisos_todos():
    return db.listar_compromisos()


cargar_compromisos = _solo_permitidos(_cargar_compromisos_todos)


@st.cache_data(ttl=30)
def cargar_actividad(desde, hasta):
    """Pagos, compras y ventas del rango (completos, sin el tope de 1000 filas)."""
    return {t: db.listar_actividad_rango(t, desde, hasta) for t in ("pagos_generales", "compras", "ventas")}


def movimientos_financieros_para_conciliacion(desde, hasta):
    """Convierte pagos/cobros de los auxiliares financieros en movimientos comparables con el banco.

    No crea ni modifica asientos: solo lee los movimientos existentes de Finanzas.
    pago_capital de una obligación = egreso; cobro de una cuenta por cobrar = ingreso.
    """
    desde_f, hasta_f = date.fromisoformat(str(desde)[:10]), date.fromisoformat(str(hasta)[:10])
    obligaciones = db.listar_obligaciones_financieras()
    movs_obligaciones = db.listar_movimientos_obligaciones()
    cuentas = db.listar_cuentas_por_cobrar()
    movs_cuentas = db.listar_movimientos_cuentas_cobrar()
    obligaciones_por_id = {x.get("id"): x for x in obligaciones}
    cuentas_por_id = {x.get("id"): x for x in cuentas}
    salida = []

    def fecha_en_rango(valor):
        try:
            f = date.fromisoformat(str(valor)[:10])
            return f if desde_f <= f <= hasta_f else None
        except (TypeError, ValueError):
            return None

    # El desembolso original del préstamo también debe compararse con el banco.
    # Se lee de la obligación existente; no se crea un ingreso nuevo ni se altera Finanzas.
    # Se incluye aunque la obligación esté cancelada, porque el saldo cero normalmente
    # significa que el capital ya fue devuelto, no que el desembolso original no existió.
    for obligacion in obligaciones:
        f_origen = fecha_en_rango(obligacion.get("fecha_origen"))
        monto_origen = round(float(obligacion.get("monto_original") or 0), 2)
        if not f_origen or monto_origen <= 0:
            continue
        salida.append({
            "id": obligacion.get("id") or 0,
            "fecha": f_origen,
            "tipo": "Ingreso",
            "origen": "Finanzas - préstamo recibido",
            "categoria": obligacion.get("categoria") or "Préstamo recibido",
            "detalle": " ".join(x for x in (
                obligacion.get("codigo") or "",
                obligacion.get("descripcion") or "Desembolso de préstamo",
                obligacion.get("documento_referencia") or "",
                obligacion.get("observaciones") or ""
            ) if x),
            "persona": obligacion.get("acreedor") or "",
            "comprobante": obligacion.get("documento_referencia") or "",
            "metodo": "Sin método",
            "metodo_original": "Sin método",
            "estado": obligacion.get("estado") or "Registrado",
            "monto": monto_origen,
            "encargado": obligacion.get("creado_por") or "",
        })

    for m in movs_obligaciones:
        if m.get("tipo") != "pago_capital":
            continue
        f = fecha_en_rango(m.get("fecha"))
        obligacion = obligaciones_por_id.get(m.get("obligacion_id"), {})
        if not f:
            continue
        metodo_original = m.get("metodo") or ""
        salida.append({
            "id": m.get("id") or 0, "fecha": f, "tipo": "Egreso",
            "origen": "Finanzas - devolución de préstamo",
            "categoria": obligacion.get("categoria") or "Devolución de capital",
            "detalle": " ".join(x for x in (
                obligacion.get("descripcion") or "Devolución de capital",
                m.get("referencia") or "", m.get("observacion") or "") if x),
            "persona": obligacion.get("acreedor") or "",
            "comprobante": m.get("referencia") or "",
            "metodo": cuadre.grupo_metodo(metodo_original),
            "metodo_original": metodo_original,
            "estado": "Registrado", "monto": round(float(m.get("monto") or 0), 2),
            "encargado": m.get("registrado_por") or "",
        })

    for m in movs_cuentas:
        if m.get("tipo") != "cobro":
            continue
        f = fecha_en_rango(m.get("fecha"))
        cuenta = cuentas_por_id.get(m.get("cuenta_id"), {})
        if not f:
            continue
        metodo_original = m.get("metodo") or ""
        salida.append({
            "id": m.get("id") or 0, "fecha": f, "tipo": "Ingreso",
            "origen": "Finanzas - cobro de préstamo",
            "categoria": cuenta.get("categoria") or "Cobro de capital",
            "detalle": " ".join(x for x in (
                cuenta.get("descripcion") or "Cobro de capital",
                m.get("referencia") or "", m.get("observacion") or "") if x),
            "persona": cuenta.get("deudor") or "",
            "comprobante": m.get("referencia") or "",
            "metodo": cuadre.grupo_metodo(metodo_original),
            "metodo_original": metodo_original,
            "estado": "Registrado", "monto": round(float(m.get("monto") or 0), 2),
            "encargado": m.get("registrado_por") or "",
        })

    return salida


@st.cache_data(ttl=300, show_spinner=False)
def _actividad_excel_cache(reps, desde, hasta, emitido_por):
    return reportes.generar_excel_reporte(reps, desde, hasta, emitido_por=emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _actividad_pdf_cache(reps, desde, hasta, emitido_por):
    return reportes.generar_pdf_reporte(reps, desde, hasta, emitido_por=emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _rendicion_excel_cache(r, emitido_por):
    return rendicion.generar_excel_rendicion(r, emitido_por=emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _rendicion_pdf_cache(r, emitido_por):
    return rendicion.generar_pdf_rendicion(r, emitido_por=emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _inv_excel_existencias(filas, valor_total, hoy, emitido_por):
    return inventario_reportes.generar_excel_existencias(filas, valor_total, hoy, emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _inv_pdf_existencias(filas, resumen, hoy, emitido_por):
    return inventario_reportes.generar_pdf_existencias(filas, resumen, hoy, emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _inv_excel_kardex(articulo, kp, desde, hasta, emitido_por):
    return inventario_reportes.generar_excel_kardex(articulo, kp, desde, hasta, emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _inv_pdf_kardex(articulo, kp, desde, hasta, emitido_por):
    return inventario_reportes.generar_pdf_kardex(articulo, kp, desde, hasta, emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _inv_excel_movimientos(mv, desde, hasta, emitido_por):
    return inventario_reportes.generar_excel_movimientos(mv, desde, hasta, emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _inv_pdf_movimientos(mv, desde, hasta, emitido_por):
    return inventario_reportes.generar_pdf_movimientos(mv, desde, hasta, emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _leer_extracto_cache(contenido, nombre, mapeo):
    """Lee el extracto del banco (mapeo: tupla de (campo, columna) para forzar las columnas, o None)."""
    return extracto.leer_extracto(contenido, nombre, dict(mapeo) if mapeo else None)


@st.cache_data(ttl=300, show_spinner=False)
def _conc_excel_cache(r, ext, emitido_por):
    return conciliacion_reportes.generar_excel(r, ext, emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _conc_pdf_cache(r, ext, emitido_por):
    return conciliacion_reportes.generar_pdf(r, ext, emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _cuadre_excel_cache(q, emitido_por):
    return cuadre.generar_excel_cuadre(q, emitido_por=emitido_por)


@st.cache_data(ttl=300, show_spinner=False)
def _cuadre_pdf_cache(q, emitido_por):
    return cuadre.generar_pdf_cuadre(q, emitido_por=emitido_por)


# Incrementar esta versión cuando cambie el diseño del Estado de Cuenta.
# Forma parte de la clave de caché para evitar que se reutilicen documentos antiguos.
REPORTE_DISENO_VERSION = "equise-estado-cuenta-2026-11-07-v3"


@st.cache_data(ttl=300, show_spinner=False)
def _reporte_pdf_cache(datos, version=REPORTE_DISENO_VERSION):
    return recibo.generar_reporte_inquilino_pdf(datos)


@st.cache_data(ttl=300, show_spinner=False)
def _reporte_png_cache(datos, version=REPORTE_DISENO_VERSION):
    return recibo.generar_reporte_inquilino_png(datos)


def _nombre_archivo_reporte(apt, hoy, extension):
    codigo = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(apt.get("codigo") or "apto"))
    return f"estado_cuenta_{codigo}_{hoy:%Y-%m-%d}.{extension}"


def total_pagado(periodo):
    return sum(float(p["monto"]) for p in (periodo.get("pagos") or []))


def mostrar_botones_recibo_garantia(garantia, apartamento, key_sufijo):
    """Descargas PDF y PNG del comprobante de recepción de garantía."""
    try:
        # El recibo debe identificar al usuario que registró originalmente la garantía,
        # no a quien está consultando o descargando el documento actualmente.
        datos = recibo.construir_datos_recibo_garantia(garantia, apartamento)
        c_pdf, c_png = st.columns(2)
        with c_pdf:
            st.download_button(
                "📄 Descargar recibo de garantía (PDF)",
                data=recibo.generar_recibo_pdf(datos),
                file_name=f'{datos["numero_recibo"]}.pdf',
                mime="application/pdf", use_container_width=True,
                key=f"recibo_garantia_pdf_{key_sufijo}",
            )
        with c_png:
            st.download_button(
                "🖼️ Descargar recibo de garantía (PNG)",
                data=recibo.generar_recibo_png(datos),
                file_name=f'{datos["numero_recibo"]}.png',
                mime="image/png", use_container_width=True,
                key=f"recibo_garantia_png_{key_sufijo}",
            )
    except Exception as exc:
        st.caption(f"⚠️ No se pudo preparar el recibo de garantía: {exc}")


def mostrar_botones_recibo(pago, periodo, apartamento, total_pagado_periodo, key_sufijo, servicio=None):
    """Muestra dos botones de descarga (PDF y PNG) para el recibo de un abono de alquiler
    (servicio=None) o de un servicio ('electricidad' / 'agua'). Se usa tanto en la vista normal
    como en el historial."""
    try:
        constructor = (recibo.construir_datos_recibo if servicio is None
                       else lambda *a, **k: recibo.construir_datos_recibo_servicio(servicio, *a, **k))
        datos_recibo = constructor(
            pago, periodo, apartamento, total_pagado_periodo,
            recibido_por=usuario_actual.get("nombre") or usuario_actual.get("username"),
        )
        col_pdf, col_png = st.columns(2)
        with col_pdf:
            st.download_button(
                "📄 Descargar recibo (PDF)",
                data=recibo.generar_recibo_pdf(datos_recibo),
                file_name=f'{datos_recibo["numero_recibo"]}.pdf',
                mime="application/pdf",
                use_container_width=True,
                key=f'recibo_pdf_{key_sufijo}',
            )
        with col_png:
            st.download_button(
                "🖼️ Descargar recibo (PNG)",
                data=recibo.generar_recibo_png(datos_recibo),
                file_name=f'{datos_recibo["numero_recibo"]}.png',
                mime="image/png",
                use_container_width=True,
                key=f'recibo_png_{key_sufijo}',
            )
    except Exception as e:
        st.caption(f"⚠️ No se pudo preparar el recibo: {e}")


@st.cache_data(ttl=30)
def _cargar_pendientes_todos(estado=None, prioridad=None, asignado_a=None):
    return db.listar_pendientes(estado=estado, prioridad=prioridad, asignado_a=asignado_a)


# un pendiente «General» (sin apartamento) lo ve cualquiera; uno ligado a un apartamento, solo quien tiene acceso a él
cargar_pendientes = _solo_permitidos(_cargar_pendientes_todos, permitir_vacio=True)


@st.cache_data(ttl=30)
def cargar_reuniones(fecha_desde=None, fecha_hasta=None):
    return db.listar_reuniones(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)


@st.cache_data(ttl=30)
def cargar_participantes_reuniones():
    return db.listar_participantes_reuniones()


@st.cache_data(ttl=60)
def cargar_usuarios_activos():
    return [u for u in db.listar_usuarios() if u.get("activo")]


@st.cache_data(ttl=60)
def cargar_todos_los_usuarios():
    return db.listar_usuarios()


def limpiar_cache():
    cargar_accesos_apartamentos.clear()
    cargar_servicios_basicos.clear()
    estado_disponible.clear()
    cargar_compromisos.clear()
    cargar_actividad.clear()
    cargar_apartamentos.clear()
    cargar_periodos.clear()
    cargar_periodos_electricidad.clear()
    cargar_periodos_agua.clear()
    cargar_periodos_abiertos.clear()
    cargar_periodos_cerrados.clear()
    cargar_historial.clear()
    cargar_inventario_articulos.clear()
    cargar_inventario_movimientos.clear()
    cargar_pendientes.clear()
    cargar_reuniones.clear()
    cargar_participantes_reuniones.clear()
    cargar_usuarios_activos.clear()
    cargar_todos_los_usuarios.clear()


def parse_fecha(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def estado_contrato_alerta(apt):
    """Devuelve (nivel, texto) para contratos vencidos o por vencer en los próximos 30 días. None si no aplica."""
    hoy = recibo.hoy_bolivia()
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
    hoy = recibo.hoy_bolivia()
    resultado = []
    for i in range(n - 1, -1, -1):
        offset = hoy.month - 1 - i
        anio = hoy.year + offset // 12
        mes_num = offset % 12 + 1
        resultado.append((anio, mes_num))
    return resultado


# ------------------------------------------------------------------
# Electricidad y Agua: la misma pantalla para los dos servicios
# ------------------------------------------------------------------
METODOS_ABONO = ["Efectivo", "Transferencia", "QR", "Otro"]

# Lo único que cambia entre Electricidad y Agua: textos, unidad y nombres de las columnas de lectura/tarifa.
SERVICIOS_UI = {
    "electricidad": {
        "clave": "elec", "titulo": "⚡ Control de Electricidad", "unidad": "Kwh",
        "expander_tarifa": "⚙️ Tarifa por Kwh vigente", "etq_tarifa": "Tarifa por Kwh (Bs)",
        "etq_anterior": "Kwh anterior", "etq_actual": "Kwh actual",
        "col_anterior": "kwh_anterior", "col_actual": "kwh_actual", "col_tarifa": "tarifa_kwh",
        "tabla_anterior": "Kwh anterior", "tabla_actual": "Kwh actual",
    },
    "agua": {
        "clave": "agua", "titulo": "💧 Control de Agua", "unidad": "m³",
        "expander_tarifa": "⚙️ Tarifa por m³ vigente", "etq_tarifa": "Tarifa por m³ (Bs)",
        "etq_anterior": "Lectura anterior (m³)", "etq_actual": "Lectura actual (m³)",
        "col_anterior": "lectura_anterior", "col_actual": "lectura_actual", "col_tarifa": "tarifa_agua",
        "tabla_anterior": "Lectura anterior", "tabla_actual": "Lectura actual",
    },
}


def _formulario_editar_abono(servicio, p, prefijo):
    """Formulario para editar o eliminar un abono (el mismo en el registro y en el historial; servicio=None = alquiler).
    'prefijo' mantiene únicas las claves de los widgets (p. ej. 'elec' o 'elec_hist')."""
    pid = p["id"]
    # servicio=None: abono de ALQUILER; 'electricidad' / 'agua': abono de ese servicio
    actualizar = (db.actualizar_pago if servicio is None else lambda i, datos: db.actualizar_pago_servicio(servicio, i, datos))
    eliminar = (db.eliminar_pago if servicio is None else lambda i: db.eliminar_pago_servicio(servicio, i))
    with st.form(f"form_editar_pago_{prefijo}_{pid}"):
        colf, colm = st.columns(2)
        with colf:
            edit_fecha = st.date_input("Fecha", value=date.fromisoformat(str(p["fecha"])[:10]),
                                       format="DD/MM/YYYY", key=f"{prefijo}_fecha_{pid}")
        with colm:
            edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0, value=float(p["monto"]),
                                         key=f"{prefijo}_monto_{pid}")
        metodo = p.get("metodo_pago")
        edit_metodo = st.selectbox("Método de pago", METODOS_ABONO,
                                   index=METODOS_ABONO.index(metodo) if metodo in METODOS_ABONO else 0,
                                   key=f"{prefijo}_metodo_{pid}")
        edit_obs = st.text_input("Observación", value=p.get("observacion") or "", key=f"{prefijo}_obs_{pid}")

        if es_admin:
            colg, cold = st.columns(2)
            guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
            eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)
        else:
            guardar_edit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
            eliminar_edit = False

        if guardar_edit:
            try:
                actualizar(pid, {
                    "fecha": str(edit_fecha), "monto": edit_monto,
                    "metodo_pago": edit_metodo, "observacion": edit_obs or None,
                })
                limpiar_cache()
                st.success("Abono actualizado.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar: {e}")

        if eliminar_edit:
            try:
                eliminar(pid)
                limpiar_cache()
                st.success("Abono eliminado.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")


def pagina_consumo(servicio):
    """Pantalla completa de Electricidad ('electricidad') o Agua ('agua'): tarifa, lectura del medidor,
    abonos e historial."""
    ui = SERVICIOS_UI[servicio]
    k, unidad = ui["clave"], ui["unidad"]
    campo_pagos = f"pagos_{servicio}"
    st.title(ui["titulo"])

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("Primero registra apartamentos en la sección **Apartamentos**.")
        st.stop()

    tarifa_actual = db.obtener_tarifa(servicio)
    if es_admin:
        with st.expander(ui["expander_tarifa"]):
            with st.form(f"form_tarifa_{k}"):
                nueva_tarifa = st.number_input(
                    ui["etq_tarifa"], min_value=0.0, step=0.01, format="%.4f", value=tarifa_actual
                )
                if st.form_submit_button("Guardar tarifa"):
                    try:
                        db.guardar_tarifa(servicio, nueva_tarifa)
                        st.success("Tarifa actualizada. Se usará como valor por defecto para nuevas lecturas.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar lectura y abono", "📜 Historial"])

    with tab_registrar:
        codigos = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
        idx = st.selectbox("Apartamento", range(len(apartamentos)), format_func=lambda i: codigos[i],
                           key=f"{k}_apt")
        apt = apartamentos[idx]

        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes", MESES, index=recibo.hoy_bolivia().month - 1, key=f"{k}_mes")
        with col2:
            anio = st.number_input("Año", min_value=2000, max_value=2100, value=recibo.hoy_bolivia().year, step=1,
                                   key=f"{k}_anio")

        periodo = db.obtener_periodo_servicio(servicio, apt["id"], mes, int(anio))

        # Apartamentos con 2 medidores de luz (ver consumo.APARTAMENTOS_DOS_MEDIDORES): se registran las lecturas
        # de los dos y el cobro es la suma. Siguen siendo UN solo periodo por mes.
        medidores = calc_consumo.cantidad_medidores_luz(apt) if servicio == "electricidad" else 1
        anterior_2_default = actual_2_default = 0.0

        if periodo:
            anterior_default = float(periodo[ui["col_anterior"]])
            actual_default = float(periodo[ui["col_actual"]])
            tarifa_default = float(periodo[ui["col_tarifa"]])
            if medidores == 2:
                anterior_2_default = float(periodo.get("kwh_anterior_2") or 0)
                actual_2_default = float(periodo.get("kwh_actual_2") or 0)
        else:
            ultimo = db.ultimo_periodo_servicio(servicio, apt["id"])
            anterior_default = float(ultimo[ui["col_actual"]]) if ultimo else 0.0
            actual_default = anterior_default
            tarifa_default = tarifa_actual
            if medidores == 2:
                anterior_2_default = float((ultimo or {}).get("kwh_actual_2") or 0)
                actual_2_default = anterior_2_default

        st.subheader("📏 Lectura del medidor" if medidores == 1 else "📏 Lectura de los 2 medidores")
        if medidores == 2:
            st.info("⚡ Este apartamento tiene **2 medidores** de energía eléctrica. Registra la lectura de cada uno: "
                    "el cobro es la suma de los dos consumos.")
        with st.form(f"form_lectura_{k}"):
            if medidores == 2:
                st.markdown("**Medidor 1**")
                colm1a, colm1b = st.columns(2)
                with colm1a:
                    lectura_anterior = st.number_input(f"Medidor 1 · {ui['etq_anterior']}", min_value=0.0, step=1.0,
                                                       value=anterior_default)
                with colm1b:
                    lectura_actual = st.number_input(f"Medidor 1 · {ui['etq_actual']}", min_value=0.0, step=1.0,
                                                     value=actual_default)
                st.markdown("**Medidor 2**")
                colm2a, colm2b = st.columns(2)
                with colm2a:
                    lectura_anterior_2 = st.number_input(f"Medidor 2 · {ui['etq_anterior']}", min_value=0.0, step=1.0,
                                                         value=anterior_2_default)
                with colm2b:
                    lectura_actual_2 = st.number_input(f"Medidor 2 · {ui['etq_actual']}", min_value=0.0, step=1.0,
                                                       value=actual_2_default)
                tarifa = st.number_input(ui["etq_tarifa"], min_value=0.0, step=0.01, format="%.4f",
                                         value=tarifa_default)
                consumo_1 = calc_consumo.calcular_consumo(lectura_anterior, lectura_actual)
                consumo_2 = calc_consumo.calcular_consumo(lectura_anterior_2, lectura_actual_2)
                consumo = consumo_1 + consumo_2
                notas_redondeo = [
                    f"medidor {i}, {n}" for i, n in (
                        (1, calc_consumo.nota_redondeo(lectura_anterior, lectura_actual)),
                        (2, calc_consumo.nota_redondeo(lectura_anterior_2, lectura_actual_2)))
                    if n
                ]
            else:
                colk1, colk2, colk3 = st.columns(3)
                with colk1:
                    lectura_anterior = st.number_input(ui["etq_anterior"], min_value=0.0, step=1.0,
                                                       value=anterior_default)
                with colk2:
                    lectura_actual = st.number_input(ui["etq_actual"], min_value=0.0, step=1.0,
                                                     value=actual_default)
                with colk3:
                    tarifa = st.number_input(ui["etq_tarifa"], min_value=0.0, step=0.01, format="%.4f",
                                             value=tarifa_default)
                consumo = calc_consumo.calcular_consumo(lectura_anterior, lectura_actual)   # número entero (redondeo normal)
                notas_redondeo = [calc_consumo.nota_redondeo(lectura_anterior, lectura_actual)]

            monto_calculado = calc_consumo.calcular_monto(consumo, tarifa)
            if medidores == 2:
                st.caption(f"Medidor 1: {consumo_1} {unidad}  +  Medidor 2: {consumo_2} {unidad}")
            etiqueta_consumo = "Consumo total" if medidores == 2 else "Consumo"
            st.caption(f"{etiqueta_consumo}: {consumo} {unidad}  ×  Bs {tarifa:.4f}  =  {detalle_monto_servicio(consumo, tarifa)}")
            for nota_redondeo in notas_redondeo:
                if nota_redondeo:
                    st.caption(f"ℹ️ El consumo se redondea a número entero: {nota_redondeo}.")

            if st.form_submit_button("💾 Guardar lectura"):
                payload = {
                    ui["col_anterior"]: lectura_anterior,
                    ui["col_actual"]: lectura_actual,
                    ui["col_tarifa"]: tarifa,
                    "monto_esperado": monto_calculado,
                }
                if medidores == 2:
                    payload.update({"kwh_anterior_2": lectura_anterior_2, "kwh_actual_2": lectura_actual_2})
                try:
                    if periodo:
                        db.actualizar_periodo_servicio(servicio, periodo["id"], payload)
                    else:
                        payload.update({"apartamento_id": apt["id"], "mes": mes, "anio": int(anio)})
                        db.crear_periodo_servicio(servicio, payload)
                    limpiar_cache()
                    st.success("Lectura guardada.")
                    st.rerun()
                except Exception as e:
                    if "kwh_anterior_2" in str(e) or "kwh_actual_2" in str(e):
                        st.error("Falta crear las columnas del segundo medidor en la base de datos: ejecuta "
                                 "`migracion_dos_medidores.sql` en el SQL Editor de Supabase y vuelve a intentar.")
                    else:
                        st.error(f"Error al guardar: {e}")

        if periodo:
            abonos = periodo.get(campo_pagos, []) or []
            total_abonos = sum(float(p["monto"]) for p in abonos)
            deuda_actual = float(periodo["monto_esperado"]) - total_abonos

            st.markdown(f"**Monto esperado del mes:** {fmt_money(periodo['monto_esperado'])}  |  "
                        f"**Pagado hasta ahora:** {fmt_money(total_abonos)}  |  "
                        f"**Deuda actual:** {fmt_money(deuda_actual)}")

            st.divider()
            st.subheader("➕ Registrar un nuevo abono")
            with st.form(f"form_pago_{k}", clear_on_submit=True):
                monto_pago = st.number_input("Monto abonado (Bs)", min_value=0.0, step=10.0)
                fecha_pago = st.date_input("Fecha del abono", value=recibo.hoy_bolivia(), format="DD/MM/YYYY")
                metodo_pago = st.selectbox("Método de pago", METODOS_ABONO, key=f"metodo_{k}")
                observacion = st.text_input("Observación (opcional)", key=f"obs_{k}")

                if st.form_submit_button("💾 Registrar abono"):
                    if monto_pago <= 0:
                        st.error("El monto abonado debe ser mayor a 0.")
                    else:
                        try:
                            db.crear_pago_servicio(servicio, {
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
                        mostrar_botones_recibo(p, periodo, apt, total_abonos,
                                               key_sufijo=f'{k}_{p["id"]}', servicio=servicio)
                        st.divider()
                        _formulario_editar_abono(servicio, p, k)
        else:
            st.info("Guarda primero la lectura del medidor para poder registrar abonos de este mes.")

    with tab_historial:
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_apt = st.selectbox(
                "Filtrar por apartamento", ["Todos"] + [a["codigo"] for a in apartamentos], key=f"{k}_hist_apt"
            )
        with col2:
            filtro_anio = st.selectbox("Filtrar por año",
                                       ["Todos"] + list(range(recibo.hoy_bolivia().year - 2, recibo.hoy_bolivia().year + 2)),
                                       key=f"{k}_hist_anio")
        with col3:
            filtro_mes = st.selectbox("Filtrar por mes", ["Todos"] + MESES, key=f"{k}_hist_mes")

        apt_id = None
        if filtro_apt != "Todos":
            apt_id = next(a["id"] for a in apartamentos if a["codigo"] == filtro_apt)

        st.caption("Se muestran solo los registros del inquilino actual. Los de inquilinos que ya salieron están en «🚪 Ex inquilinos».")
        periodos = _solo_mis_apartamentos(db.listar_periodos_servicio(
            servicio,
            apartamento_id=apt_id,
            anio=None if filtro_anio == "Todos" else filtro_anio,
            mes=None if filtro_mes == "Todos" else filtro_mes,
            solo_activos=True,
        ))

        if not periodos:
            st.info("No hay periodos que coincidan con el filtro.")
            return

        hay_medidor_2 = servicio == "electricidad" and any(p.get("kwh_actual_2") is not None for p in periodos)
        filas = []
        for p in periodos:
            apt_info = p.get("apartamentos") or {}
            pagado = sum(float(a["monto"]) for a in (p.get(campo_pagos) or []))
            fila = {
                "Apartamento": apt_info.get("codigo"),
                "Inquilino": apt_info.get("inquilino_nombre"),
                "Mes": p["mes"],
                "Año": p["anio"],
                ui["tabla_anterior"]: p[ui["col_anterior"]],
                ui["tabla_actual"]: p[ui["col_actual"]],
            }
            if hay_medidor_2:      # solo los apartamentos con 2 medidores traen datos aquí
                fila[f"{ui['tabla_anterior']} (medidor 2)"] = p.get("kwh_anterior_2")
                fila[f"{ui['tabla_actual']} (medidor 2)"] = p.get("kwh_actual_2")
            fila.update({
                "Consumo": calc_consumo.consumo_total(p, servicio),
                "Esperado": p["monto_esperado"],
                "Pagado": pagado,
                "Deuda": float(p["monto_esperado"]) - pagado,
            })
            filas.append(fila)
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
        if hay_medidor_2:
            st.caption("Los apartamentos con 2 medidores muestran las lecturas del segundo en las columnas «(medidor 2)»; "
                       "el consumo es la suma de los dos.")

        total_esperado = sum(f["Esperado"] for f in filas)
        total_recaudado = sum(f["Pagado"] for f in filas)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total esperado", fmt_money(total_esperado))
        c2.metric("Total pagado", fmt_money(total_recaudado))
        c3.metric("Total deuda", fmt_money(total_esperado - total_recaudado))

        with st.expander("🔍 Ver y editar los abonos de un periodo específico"):
            opciones = [f'{f["Apartamento"]} — {f["Mes"]} {f["Año"]}' for f in filas]
            sel = st.selectbox("Periodo", range(len(opciones)), format_func=lambda i: opciones[i],
                               key=f"sel_hist_{k}")
            detalle_periodo = periodos[sel]
            detalle_abonos = detalle_periodo.get(campo_pagos) or []
            if not detalle_abonos:
                st.write("Sin abonos registrados.")
            else:
                total_detalle = sum(float(x["monto"]) for x in detalle_abonos)
                for p in sorted(detalle_abonos, key=lambda x: x["fecha"]):
                    with st.expander(f'{p["fecha"]} — {fmt_money(p["monto"])} — {p.get("metodo_pago") or ""}'):
                        mostrar_botones_recibo(
                            p, detalle_periodo, detalle_periodo.get("apartamentos"), total_detalle,
                            key_sufijo=f'{k}_hist_{p["id"]}', servicio=servicio)
                        st.divider()
                        _formulario_editar_abono(servicio, p, f"{k}_hist")


# ------------------------------------------------------------------
# Sidebar / navegación
# ------------------------------------------------------------------
st.sidebar.title("🏢 Residencial EQUIZ")
st.sidebar.caption(f'👤 {usuario_actual.get("nombre") or usuario_actual.get("username")} · {usuario_actual.get("rol")}')
_permitidos_barra = ids_apartamentos_permitidos()
if _permitidos_barra is not None:
    st.sidebar.caption(f"🔒 Acceso a {len(_permitidos_barra)} apartamento(s) asignado(s)" if _permitidos_barra
                       else "🔒 No tienes apartamentos asignados: pídele al administrador que te asigne")

if es_admin:
    opciones_principal = ["📊 Dashboard", "🏠 Apartamentos", "💳 Gestión de cobros",
                          "🤝 Compromisos de pago", "🚪 Ex inquilinos", "👥 Usuarios", "💰 Finanzas"]
else:
    # El Cobrador trabaja desde la pantalla unificada de cobros.
    opciones_principal = ["📊 Dashboard", "🏠 Inquilinos", "💳 Gestión de cobros",
                          "🤝 Compromisos de pago", "🚪 Ex inquilinos", "💰 Finanzas"]

opciones_administracion = ["(ninguno)", "✅ Pendientes", "🔌 Servicios Básicos", "📦 Inventario", "🗒️ Reuniones"]
opciones_reportes = ["(ninguno)", "📑 Estado de cuenta", "📋 Rendición de alquileres", "📊 Actividad por usuario", "💰 Cuadre de tesorería", "🏦 Conciliación bancaria"]

# La navegación financiera queda integrada dentro de Finanzas; ya no existe
# un segundo bloque lateral de Egresos/Ventas.
_MODULOS_NAV = ["nav_administracion", "nav_reportes"]


def _reiniciar_modulos():
    for clave in _MODULOS_NAV:
        st.session_state[clave] = "(ninguno)"


def _al_elegir_principal():
    _reiniciar_modulos()


def _al_elegir_administracion():
    if st.session_state["nav_administracion"] != "(ninguno)":
        st.session_state["nav_reportes"] = "(ninguno)"


def _al_elegir_reportes():
    if st.session_state["nav_reportes"] != "(ninguno)":
        st.session_state["nav_administracion"] = "(ninguno)"

pagina_principal = st.sidebar.radio("Gestión del Residencial", opciones_principal, key="nav_principal",
                                     on_change=_al_elegir_principal)
st.sidebar.divider()
st.sidebar.caption("🗂️ Módulo Administración")
pagina_administracion = st.sidebar.radio("Administración", opciones_administracion, key="nav_administracion",
                                          label_visibility="collapsed", on_change=_al_elegir_administracion)
st.sidebar.divider()
st.sidebar.caption("📑 Módulo de Reportes")
pagina_reportes = st.sidebar.radio("Reportes", opciones_reportes, key="nav_reportes",
                                    label_visibility="collapsed", on_change=_al_elegir_reportes)

if pagina_administracion != "(ninguno)":
    pagina = pagina_administracion
elif pagina_reportes != "(ninguno)":
    pagina = pagina_reportes
else:
    pagina = pagina_principal

# Selector interno de Finanzas: Préstamos, Egresos e Ingresos.
if es_admin and pagina_principal == "💰 Finanzas" and pagina == "💰 Finanzas":
    seccion_finanzas = st.radio(
        "Operaciones financieras",
        ["🤝 Préstamos", "💸 Egresos", "💰 Ingresos"],
        horizontal=True,
        key="v13_seccion_finanzas",
        label_visibility="collapsed",
    )
    pagina = {
        "🤝 Préstamos": "💰 Finanzas",
        "💸 Egresos": "💸 Egresos",
        "💰 Ingresos": "💸 Ventas",
    }[seccion_finanzas]

st.sidebar.divider()
if st.sidebar.button("🔄 Actualizar datos"):
    limpiar_cache()
    st.rerun()
if st.sidebar.button("🚪 Cerrar sesión"):
    del st.session_state["usuario"]
    st.rerun()



# ==================================================================
# PÁGINA: FINANZAS - CUENTAS POR PAGAR Y POR COBRAR
# ==================================================================
elif pagina == "💰 Finanzas" and not es_admin:
    # Vista limitada para Cobrador: registrar cobros y consultar el historial.
    # No se muestran préstamos recibidos, creación de cuentas, egresos,
    # ingresos, saldos de obligaciones ni controles administrativos.
    st.title("💰 Finanzas")
    st.caption("Registro de cobros y consulta del historial. Las cuentas y sus condiciones son administradas por el Administrador.")

    try:
        cuentas_cobrador = db.listar_cuentas_por_cobrar()
        movimientos_cobrador = db.listar_movimientos_cuentas_cobrar()
    except Exception as e:
        st.error("No se pudo cargar la información de cobros.")
        st.caption(f"Detalle: {e}")
        st.stop()

    movimientos_por_cuenta_cobrador = {}
    for mov in movimientos_cobrador:
        movimientos_por_cuenta_cobrador.setdefault(mov.get("cuenta_id"), []).append(mov)

    cuentas_disponibles = []
    for cuenta in cuentas_cobrador:
        saldo_actual = deudores.calcular_saldo(
            cuenta, movimientos_por_cuenta_cobrador.get(cuenta.get("id"), [])
        )
        if float(saldo_actual) > 0:
            cuentas_disponibles.append((cuenta, saldo_actual))

    st.subheader("Registrar cobro")
    if cuentas_disponibles:
        mapa_cobrador = {
            f'{c.get("codigo", "—")} · {c.get("deudor", "Sin deudor")} · saldo Bs {float(s):,.2f}': (c, s)
            for c, s in cuentas_disponibles
        }
        with st.form("cobrador_registrar_cobro_cxc", clear_on_submit=True):
            etiqueta_cuenta = st.selectbox("Cuenta por cobrar", list(mapa_cobrador))
            cuenta_sel, saldo_sel = mapa_cobrador[etiqueta_cuenta]
            st.caption(f'Deudor: {cuenta_sel.get("deudor", "—")} · Saldo pendiente: {fmt_money(saldo_sel)}')
            fecha_cobro_cobrador = st.date_input("Fecha del cobro", key="cobrador_fecha_cobro_cxc")
            monto_cobrado_cobrador = st.number_input(
                "Monto cobrado (Bs)", min_value=0.01, max_value=float(saldo_sel),
                step=10.0, format="%.2f", key="cobrador_monto_cobro_cxc"
            )
            metodo_cobro_cobrador = st.selectbox(
                "Medio de cobro", ["Efectivo", "QR", "Transferencia Bancaria", "Otro"],
                key="cobrador_metodo_cobro_cxc"
            )
            referencia_cobrador = st.text_input(
                "N.º de comprobante / referencia", key="cobrador_ref_cobro_cxc"
            )
            observacion_cobrador = st.text_input("Observación", key="cobrador_obs_cobro_cxc")
            confirmar_cobro_cobrador = st.form_submit_button("Registrar cobro")
            if confirmar_cobro_cobrador:
                try:
                    saldo_verificado = deudores.calcular_saldo(
                        cuenta_sel, movimientos_por_cuenta_cobrador.get(cuenta_sel.get("id"), [])
                    )
                    if float(monto_cobrado_cobrador) > float(saldo_verificado):
                        raise ValueError("El cobro supera el saldo pendiente de la cuenta.")
                    db.crear_movimiento_cuenta_cobrar({
                        "cuenta_id": cuenta_sel["id"],
                        "fecha": str(fecha_cobro_cobrador),
                        "tipo": "cobro",
                        "monto": float(monto_cobrado_cobrador),
                        "metodo": metodo_cobro_cobrador,
                        "referencia": referencia_cobrador.strip() or None,
                        "observacion": observacion_cobrador.strip() or None,
                        "registrado_por": usuario_actual.get("username"),
                    })
                    st.success("Cobro registrado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo registrar el cobro: {e}")
    else:
        st.info("No hay cuentas por cobrar con saldo pendiente para registrar cobros.")

    st.divider()
    st.subheader("Historial de cobros")
    cuentas_por_id_cobrador = {c.get("id"): c for c in cuentas_cobrador}
    historial_cobrador = []
    for mov in movimientos_cobrador:
        if mov.get("tipo") != "cobro":
            continue
        cuenta = cuentas_por_id_cobrador.get(mov.get("cuenta_id"), {})
        historial_cobrador.append({
            "Fecha": mov.get("fecha") or "—",
            "Código": cuenta.get("codigo") or "—",
            "Deudor": cuenta.get("deudor") or "—",
            "Monto cobrado": float(mov.get("monto") or 0),
            "Medio": mov.get("metodo") or "—",
            "Referencia": mov.get("referencia") or "—",
            "Registrado por": mov.get("registrado_por") or "—",
            "Observación": mov.get("observacion") or "—",
        })
    if historial_cobrador:
        import pandas as pd
        df_historial_cobrador = pd.DataFrame(historial_cobrador)
        st.dataframe(
            df_historial_cobrador.sort_values("Fecha", ascending=False),
            use_container_width=True, hide_index=True,
            column_config={"Monto cobrado": st.column_config.NumberColumn("Monto cobrado", format="Bs %.2f")}
        )
        st.caption(f"Registros históricos: {len(historial_cobrador)}. Esta vista es de solo lectura.")
        st.markdown("**Generar recibo de un cobro registrado**")
        cobros_cobrador = [m for m in movimientos_cobrador if m.get("tipo") == "cobro" and m.get("cuenta_id") in cuentas_por_id_cobrador]
        if cobros_cobrador:
            mapa_recibos_cobrador = {
                f'{m.get("fecha", "—")} · {cuentas_por_id_cobrador[m.get("cuenta_id")].get("codigo", "—")} · Bs {float(m.get("monto") or 0):,.2f} · {cuentas_por_id_cobrador[m.get("cuenta_id")].get("deudor", "—")}': m
                for m in cobros_cobrador
            }
            etiqueta_recibo_cobrador = st.selectbox(
                "Selecciona el cobro", list(mapa_recibos_cobrador), key="cxc_recibo_cobrador_selector"
            )
            movimiento_recibo_cobrador = mapa_recibos_cobrador[etiqueta_recibo_cobrador]
            cuenta_recibo_cobrador = cuentas_por_id_cobrador[movimiento_recibo_cobrador.get("cuenta_id")]
            datos_recibo_cobrador = recibo.construir_datos_recibo_cuenta_cobrar(
                cuenta_recibo_cobrador, movimiento_recibo_cobrador,
                movimientos_por_cuenta_cobrador.get(cuenta_recibo_cobrador.get("id"), [])
            )
            col_pdf_cobrador, col_png_cobrador = st.columns(2)
            col_pdf_cobrador.download_button(
                "📄 Descargar recibo PDF",
                data=recibo.generar_recibo_pdf(datos_recibo_cobrador),
                file_name=f'{datos_recibo_cobrador["numero_recibo"]}.pdf',
                mime="application/pdf", key="cxc_recibo_cobrador_pdf"
            )
            col_png_cobrador.download_button(
                "🖼️ Descargar recibo PNG",
                data=recibo.generar_recibo_png(datos_recibo_cobrador),
                file_name=f'{datos_recibo_cobrador["numero_recibo"]}.png',
                mime="image/png", key="cxc_recibo_cobrador_png"
            )
        else:
            st.info("No hay cobros registrados para generar recibos.")
    else:
        st.info("Todavía no hay cobros registrados.")

elif pagina == "💰 Finanzas":
    st.title("🤝 Préstamos")
    st.caption("Registro de préstamos recibidos y préstamos realizados, sin intereses. Solo administrador.")
    if not es_admin:
        st.error("No tienes permiso para acceder a este módulo.")
        st.stop()

    tab_resumen, tab_pagar, tab_cobrar = st.tabs(
        ["📊 Resumen de préstamos", "📥 Préstamos recibidos", "📤 Préstamos realizados"]
    )

    try:
        obligaciones = db.listar_obligaciones_financieras()
        movimientos_obl = db.listar_movimientos_obligaciones()
        cuentas_cobrar = db.listar_cuentas_por_cobrar()
        movimientos_cxc = db.listar_movimientos_cuentas_cobrar()
    except Exception as e:
        st.error("No se pudieron cargar las tablas financieras. Verifica que la migración financiera V13 esté aplicada.")
        st.exception(e)
        st.stop()

    mov_obl_por_id = {}
    for m in movimientos_obl:
        mov_obl_por_id.setdefault(m.get("obligacion_id"), []).append(m)
    mov_cxc_por_id = {}
    for m in movimientos_cxc:
        mov_cxc_por_id.setdefault(m.get("cuenta_id"), []).append(m)

    resumen_obl = deudas.resumir_obligaciones(obligaciones, mov_obl_por_id)
    resumen_cxc = deudores.resumir_cuentas(cuentas_cobrar, mov_cxc_por_id)
    mensaje_finanzas = st.session_state.pop("finanzas_mensaje_exito", None)
    if mensaje_finanzas:
        st.success(mensaje_finanzas)
    total_pagar = float(resumen_obl["total_pendiente"])
    total_cobrar = float(resumen_cxc["total_por_cobrar"])

    with tab_resumen:
        c1, c2, c3 = st.columns(3)
        c1.metric("Préstamos recibidos pendientes", fmt_money(total_pagar))
        c2.metric("Préstamos realizados pendientes", fmt_money(total_cobrar))
        c3.metric("Saldo neto de estas cuentas", fmt_money(total_cobrar-total_pagar))
        st.info("Este panel muestra los saldos de capital de préstamos recibidos y realizados. No incluye intereses ni equivale al saldo de caja y bancos.")
        st.subheader("Préstamos recibidos pendientes")
        if resumen_obl["obligaciones"]:
            st.dataframe(pd.DataFrame(resumen_obl["obligaciones"])[
                ["codigo","categoria","acreedor","fecha_origen","fecha_vencimiento","saldo_pendiente","estado_calculado"]
            ], use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay obligaciones registradas.")
        st.subheader("Préstamos realizados pendientes")
        if resumen_cxc["cuentas"]:
            st.dataframe(pd.DataFrame(resumen_cxc["cuentas"])[
                ["codigo","categoria","deudor","fecha_origen","fecha_vencimiento","saldo_por_cobrar","estado_calculado"]
            ], use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay cuentas por cobrar registradas.")

    with tab_pagar:
        st.subheader("Registrar préstamo recibido")
        with st.form("v12_nueva_obligacion", clear_on_submit=True):
            a,b=st.columns(2)
            a.text_input("Código único", value="Se genera automáticamente al guardar", disabled=True)
            categoria=a.selectbox("Tipo de obligación", list(deudas.CATEGORIAS_DEUDA))
            acreedor=b.text_input("Acreedor")
            identificacion=b.text_input("CI/NIT del acreedor (opcional)")
            descripcion=st.text_input("Descripción")
            c,d,e=st.columns(3)
            fecha_origen=c.date_input("Fecha de origen")
            fecha_corte=d.date_input("Fecha de corte / saldo inicial")
            vencimiento=e.date_input("Vencimiento", value=None)
            f,g=st.columns(2)
            monto=f.number_input("Monto original (Bs)", min_value=0.01, step=10.0, format="%.2f")
            situacion_obl=st.radio(
                "Situación de la obligación a la fecha de corte",
                ["El monto completo sigue pendiente", "Ya se realizaron pagos antes de la fecha de corte"],
                index=0, key="v13_situacion_obligacion",
                help="Si todavía no devolviste capital, EQUISE tomará automáticamente el monto original como saldo pendiente."
            )
            if situacion_obl == "El monto completo sigue pendiente":
                saldo=float(monto)
                st.info(f"Saldo inicial que se registrará: {fmt_money(saldo)}")
            else:
                saldo=st.number_input(
                    "Saldo pendiente a la fecha de corte (Bs)", min_value=0.0,
                    max_value=float(monto), step=10.0, format="%.2f", key="v13_saldo_obligacion"
                )
            documento=st.text_input("Contrato, factura o documento de respaldo")
            obs=st.text_area("Observaciones")
            guardar=st.form_submit_button("Guardar obligación")
            if guardar:
                try:
                    payload={"categoria":categoria,"acreedor":acreedor.strip(),
                        "identificacion_acreedor":identificacion.strip() or None,"descripcion":descripcion or None,
                        "fecha_origen":str(fecha_origen),"fecha_corte":str(fecha_corte),
                        "monto_original":monto,"saldo_apertura":saldo,
                        "fecha_vencimiento":str(vencimiento) if vencimiento else None,
                        "documento_referencia":documento or None,"observaciones":obs or None,
                        "estado":"Vigente","creado_por":usuario_actual.get("username")}
                    deudas.validar_obligacion({**payload,"monto_original":monto})
                    if saldo > monto: raise ValueError("El saldo inicial no puede superar el monto original.")
                    resultado_obligacion = db.crear_obligacion_financiera(payload)
                    fila_creada = (resultado_obligacion.data or [{}])[0] if getattr(resultado_obligacion, "data", None) else {}
                    st.session_state["finanzas_mensaje_exito"] = (
                        f"Obligación registrada con código {fila_creada.get('codigo', 'asignado por el sistema')}."
                    )
                    st.rerun()
                except Exception as e: st.error(f"No se pudo guardar: {e}")

        # Detecta obligaciones que se guardaron con saldo inicial cero y aún no tienen
        # movimientos. Solo se ofrecen para corrección tras confirmación expresa.
        obligaciones_a_revisar=[]
        obligaciones_con_saldo=[]
        for obligacion in obligaciones:
            movs_obl=mov_obl_por_id.get(obligacion.get("id"), [])
            saldo_calculado=float(deudas.calcular_saldo(obligacion, movs_obl))
            if saldo_calculado > 0:
                obligaciones_con_saldo.append((obligacion, saldo_calculado))
            elif (saldo_calculado == 0
                  and float(obligacion.get("monto_original") or 0) > 0
                  and not movs_obl):
                obligaciones_a_revisar.append(obligacion)

        if obligaciones_a_revisar:
            with st.expander("⚠️ Revisar obligación registrada sin saldo inicial", expanded=True):
                st.warning(
                    "Hay obligaciones sin movimientos cuyo saldo inicial es Bs 0,00. "
                    "Si el capital completo sigue pendiente de devolución, puedes corregirlo aquí."
                )
                mapa_reparacion_obl={
                    f'{o.get("codigo") or "SIN CÓDIGO"} · {o.get("acreedor") or "Sin acreedor"} · monto original Bs {float(o.get("monto_original") or 0):,.2f}':o
                    for o in obligaciones_a_revisar
                }
                etiqueta_reparar_obl=st.selectbox(
                    "Obligación que necesita corrección", list(mapa_reparacion_obl),
                    key="v13_obl_reparar_seleccion"
                )
                obligacion_reparar=mapa_reparacion_obl[etiqueta_reparar_obl]
                confirmar_reparacion_obl=st.checkbox(
                    "Confirmo que esta obligación no tuvo devoluciones anteriores y que el capital completo sigue pendiente.",
                    key="v13_obl_confirmar_reparacion"
                )
                if st.button("Corregir saldo inicial de la obligación", key="v13_obl_boton_reparar", disabled=not confirmar_reparacion_obl):
                    try:
                        # La capa de datos vuelve a comprobar que no existan movimientos.
                        monto_reparacion_obl=float(obligacion_reparar.get("monto_original") or 0)
                        db.actualizar_saldo_apertura_obligacion(
                            obligacion_reparar["id"], monto_reparacion_obl
                        )
                        st.success(
                            f"Saldo inicial corregido a {fmt_money(monto_reparacion_obl)}. "
                            "Ahora puedes registrar la devolución de capital."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo corregir el saldo inicial: {e}")

        st.subheader("Registrar devolución de capital")
        if obligaciones_con_saldo:
            mapa={
                f'{o.get("codigo") or "SIN CÓDIGO"} · {o.get("acreedor") or "Sin acreedor"} · saldo Bs {saldo:,.2f}':(o, saldo)
                for o, saldo in obligaciones_con_saldo
            }
            with st.form("v12_pago_obligacion", clear_on_submit=True):
                elegido=st.selectbox("Obligación",list(mapa), key="v13_obligacion_selector_pago")
                o, saldo_disponible_obl=mapa[elegido]
                st.caption(f"Capital pendiente: {fmt_money(saldo_disponible_obl)}")
                fecha=st.date_input("Fecha del pago",key="v12_fecha_pago")
                monto_pago=st.number_input(
                    "Capital pagado (Bs)", min_value=0.01, max_value=float(saldo_disponible_obl),
                    step=10.0, format="%.2f", key="v12_monto_pago"
                )
                metodo=st.selectbox("Medio de pago",["Efectivo","QR","Transferencia Bancaria","Otro"],key="v12_metodo_pago")
                referencia=st.text_input("N.º de comprobante / referencia",key="v12_ref_pago")
                obs_pago=st.text_input("Observación",key="v12_obs_pago")
                ok=st.form_submit_button("Registrar pago")
                if ok:
                    try:
                        saldo_actual=deudas.calcular_saldo(o,mov_obl_por_id.get(o["id"],[]))
                        if monto_pago > float(saldo_actual): raise ValueError("El pago supera el saldo pendiente.")
                        db.crear_movimiento_obligacion({"obligacion_id":o["id"],"fecha":str(fecha),
                            "tipo":"pago_capital","monto":monto_pago,"metodo":metodo,
                            "referencia":referencia or None,"observacion":obs_pago or None,
                            "registrado_por":usuario_actual.get("username")})
                        st.success("Pago registrado en el auxiliar de deuda. Aún no genera movimiento automático en caja/bancos.")
                        st.rerun()
                    except Exception as e: st.error(f"No se pudo registrar el pago: {e}")
        elif obligaciones_a_revisar:
            st.info("Las obligaciones aparecen aquí para corregir su saldo inicial. Confirma la que todavía tenga capital pendiente.")
        elif obligaciones:
            st.info("Todas las obligaciones registradas tienen saldo cero. No hay capital pendiente de devolución.")
        else:
            st.info("Registra primero una obligación.")

        st.subheader("Detalle de obligaciones")
        if resumen_obl["obligaciones"]:
            st.dataframe(pd.DataFrame(resumen_obl["obligaciones"]),use_container_width=True,hide_index=True)

    with tab_cobrar:
        st.subheader("Registrar préstamo realizado")
        with st.form("v12_nueva_cxc", clear_on_submit=True):
            a,b=st.columns(2)
            a.text_input("Código único", value="Se genera automáticamente al guardar", disabled=True)
            categoria_c=a.selectbox("Tipo de cuenta",list(deudores.CATEGORIAS_COBRO))
            deudor=b.text_input("Deudor")
            identificacion_c=b.text_input("CI/NIT del deudor (opcional)")
            descripcion_c=st.text_input("Descripción",key="v12_desc_cxc")
            c,d,e=st.columns(3)
            fecha_origen_c=c.date_input("Fecha de origen",key="v12_origen_cxc")
            fecha_corte_c=d.date_input("Fecha de corte / saldo inicial",key="v12_corte_cxc")
            vencimiento_c=e.date_input("Vencimiento",value=None,key="v12_venc_cxc")
            monto_c=st.number_input("Monto original (Bs)",min_value=0.01,step=10.0,key="v12_monto_cxc")
            situacion_c=st.radio(
                "Situación de la deuda a la fecha de corte",
                ["El monto completo sigue pendiente", "Ya se recibieron pagos antes de la fecha de corte"],
                index=0, key="v12_situacion_cxc", horizontal=False,
                help="Si no hubo pagos anteriores, EQUISE tomará automáticamente el monto original como saldo inicial."
            )
            if situacion_c == "El monto completo sigue pendiente":
                saldo_c=float(monto_c)
                st.info(f"Saldo inicial que se registrará: {fmt_money(saldo_c)}")
            else:
                saldo_c=st.number_input(
                    "Saldo pendiente a la fecha de corte (Bs)", min_value=0.0,
                    max_value=float(monto_c), step=10.0, format="%.2f", key="v12_saldo_cxc"
                )
            documento_c=st.text_input("Contrato, recibo o respaldo",key="v12_doc_cxc")
            obs_c=st.text_area("Observaciones",key="v12_obs_cxc")
            guardar_c=st.form_submit_button("Guardar cuenta por cobrar")
            if guardar_c:
                try:
                    payload={"categoria":categoria_c,"deudor":deudor.strip(),
                        "identificacion_deudor":identificacion_c.strip() or None,"descripcion":descripcion_c or None,
                        "fecha_origen":str(fecha_origen_c),"fecha_corte":str(fecha_corte_c),
                        "monto_original":monto_c,"saldo_apertura":saldo_c,
                        "fecha_vencimiento":str(vencimiento_c) if vencimiento_c else None,
                        "documento_referencia":documento_c or None,"observaciones":obs_c or None,
                        "estado":"Vigente","creado_por":usuario_actual.get("username")}
                    deudores.validar_cuenta({**payload,"monto_original":monto_c})
                    if saldo_c > monto_c: raise ValueError("El saldo inicial no puede superar el monto original.")
                    resultado_cxc = db.crear_cuenta_por_cobrar(payload)
                    fila_cxc_creada = (resultado_cxc.data or [{}])[0] if getattr(resultado_cxc, "data", None) else {}
                    st.session_state["finanzas_mensaje_exito"] = (
                        f"Cuenta por cobrar registrada con código {fila_cxc_creada.get('codigo', 'asignado por el sistema')}."
                    )
                    st.rerun()
                except Exception as e: st.error(f"No se pudo guardar: {e}")

        st.divider()
        st.subheader("Registrar devolución recibida")
        cuentas_con_saldo = []
        cuentas_a_revisar = []
        for cuenta_c in cuentas_cobrar:
            movimientos_c = mov_cxc_por_id.get(cuenta_c.get("id"), [])
            saldo_actual_c = float(deudores.calcular_saldo(cuenta_c, movimientos_c))
            if saldo_actual_c > 0:
                cuentas_con_saldo.append((cuenta_c, saldo_actual_c))
            elif saldo_actual_c == 0 and float(cuenta_c.get("monto_original") or 0) > 0 and not movimientos_c:
                # Cuenta creada sin movimientos y con saldo inicial cero: permite corregirla
                # desde la aplicación, sin SQL y sin tocar cuentas con historial.
                cuentas_a_revisar.append(cuenta_c)

        if cuentas_a_revisar:
            with st.expander("⚠️ Revisar cuenta registrada sin saldo inicial", expanded=True):
                st.warning(
                    "Hay cuentas sin movimientos cuyo saldo inicial es Bs 0,00. "
                    "Si el monto original sigue totalmente pendiente, puedes corregir el saldo desde aquí."
                )
                mapa_reparacion = {
                    f'{c.get("codigo", "—")} · {c.get("deudor", "—")} · monto original Bs {float(c.get("monto_original") or 0):,.2f}': c
                    for c in cuentas_a_revisar
                }
                cuenta_reparar_label = st.selectbox(
                    "Cuenta que necesita corrección", list(mapa_reparacion), key="v13_cxc_reparar_seleccion"
                )
                cuenta_reparar = mapa_reparacion[cuenta_reparar_label]
                confirmar_reparacion = st.checkbox(
                    f"Confirmo que {cuenta_reparar.get('codigo')} no tuvo cobros anteriores y que el monto completo sigue pendiente.",
                    key="v13_cxc_confirmar_reparacion"
                )
                if st.button("Corregir saldo inicial", key="v13_cxc_boton_reparar", disabled=not confirmar_reparacion):
                    try:
                        # Segunda comprobación inmediatamente antes de actualizar.
                        movimientos_verificados = db.listar_movimientos_cuentas_cobrar()
                        tiene_movimientos = any(m.get("cuenta_id") == cuenta_reparar.get("id") for m in movimientos_verificados)
                        if tiene_movimientos:
                            st.error("La cuenta ya tiene movimientos. No se modificó para proteger su historial.")
                        else:
                            monto_reparacion = float(cuenta_reparar.get("monto_original") or 0)
                            db.actualizar_saldo_apertura_cuenta_por_cobrar(cuenta_reparar["id"], monto_reparacion)
                            st.success(f"Saldo inicial corregido a {fmt_money(monto_reparacion)}. Ahora puedes registrar el cobro.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo corregir el saldo inicial: {e}")

        if cuentas_con_saldo:
            mapa_c={
                f'{x.get("codigo", "—")} · {x.get("deudor", "—")} · saldo Bs {saldo:,.2f}': (x, saldo)
                for x, saldo in cuentas_con_saldo
            }
            with st.form("v12_cobro_cxc", clear_on_submit=True):
                elegido_c=st.selectbox("Cuenta por cobrar",list(mapa_c), key="v13_cxc_selector_cobro")
                x, saldo_disponible_c = mapa_c[elegido_c]
                st.caption(f"Saldo pendiente disponible: {fmt_money(saldo_disponible_c)}")
                fecha_c=st.date_input("Fecha del cobro",key="v12_fecha_cobro")
                monto_cobro=st.number_input(
                    "Monto cobrado (Bs)", min_value=0.01, max_value=float(saldo_disponible_c),
                    step=10.0, format="%.2f", key="v12_monto_cobro"
                )
                metodo_cobro=st.selectbox("Medio de cobro",["Efectivo","QR","Transferencia Bancaria","Otro"],key="v12_metodo_cobro")
                referencia_cobro=st.text_input("N.º de comprobante / referencia",key="v12_ref_cobro")
                obs_cobro=st.text_input("Observación",key="v12_obs_cobro")
                ok_c=st.form_submit_button("Registrar cobro")
                if ok_c:
                    try:
                        saldo_actual=deudores.calcular_saldo(x,mov_cxc_por_id.get(x["id"],[]))
                        if monto_cobro > float(saldo_actual): raise ValueError("El cobro supera el saldo por cobrar.")
                        db.crear_movimiento_cuenta_cobrar({"cuenta_id":x["id"],"fecha":str(fecha_c),
                            "tipo":"cobro","monto":monto_cobro,"metodo":metodo_cobro,
                            "referencia":referencia_cobro.strip() or None,"observacion":obs_cobro.strip() or None,
                            "registrado_por":usuario_actual.get("username")})
                        st.success("Cobro registrado en el auxiliar de cuentas por cobrar. Aún no genera movimiento automático en caja/bancos.")
                        st.rerun()
                    except Exception as e: st.error(f"No se pudo registrar el cobro: {e}")
        elif not cuentas_a_revisar:
            st.info("No hay cuentas por cobrar con saldo pendiente. Verifica que exista una cuenta registrada con saldo inicial mayor a cero.")
        st.subheader("Detalle de cuentas por cobrar")
        if resumen_cxc["cuentas"]:
            st.dataframe(pd.DataFrame(resumen_cxc["cuentas"]),use_container_width=True,hide_index=True)

        st.divider()
        st.subheader("Historial de cobros y emisión de recibos")
        cobros_admin = [m for m in movimientos_cxc if m.get("tipo") == "cobro" and m.get("cuenta_id") in {c.get("id") for c in cuentas_cobrar}]
        cuentas_por_id_admin = {c.get("id"): c for c in cuentas_cobrar}
        if cobros_admin:
            historial_admin = []
            for mov_admin in cobros_admin:
                cuenta_admin = cuentas_por_id_admin.get(mov_admin.get("cuenta_id"), {})
                historial_admin.append({
                    "Fecha": mov_admin.get("fecha") or "—",
                    "Código": cuenta_admin.get("codigo") or "—",
                    "Deudor": cuenta_admin.get("deudor") or "—",
                    "Monto cobrado": float(mov_admin.get("monto") or 0),
                    "Medio": mov_admin.get("metodo") or "—",
                    "Registrado por": mov_admin.get("registrado_por") or "—",
                })
            st.dataframe(pd.DataFrame(historial_admin), use_container_width=True, hide_index=True)
            mapa_recibos_admin = {
                f'{m.get("fecha", "—")} · {cuentas_por_id_admin[m.get("cuenta_id")].get("codigo", "—")} · Bs {float(m.get("monto") or 0):,.2f} · {cuentas_por_id_admin[m.get("cuenta_id")].get("deudor", "—")}': m
                for m in cobros_admin
            }
            etiqueta_recibo_admin = st.selectbox(
                "Selecciona el cobro para generar su recibo", list(mapa_recibos_admin), key="cxc_recibo_admin_selector"
            )
            movimiento_recibo_admin = mapa_recibos_admin[etiqueta_recibo_admin]
            cuenta_recibo_admin = cuentas_por_id_admin[movimiento_recibo_admin.get("cuenta_id")]
            datos_recibo_admin = recibo.construir_datos_recibo_cuenta_cobrar(
                cuenta_recibo_admin, movimiento_recibo_admin,
                mov_cxc_por_id.get(cuenta_recibo_admin.get("id"), [])
            )
            col_pdf_admin, col_png_admin = st.columns(2)
            col_pdf_admin.download_button(
                "📄 Descargar recibo PDF",
                data=recibo.generar_recibo_pdf(datos_recibo_admin),
                file_name=f'{datos_recibo_admin["numero_recibo"]}.pdf',
                mime="application/pdf", key="cxc_recibo_admin_pdf"
            )
            col_png_admin.download_button(
                "🖼️ Descargar recibo PNG",
                data=recibo.generar_recibo_png(datos_recibo_admin),
                file_name=f'{datos_recibo_admin["numero_recibo"]}.png',
                mime="image/png", key="cxc_recibo_admin_png"
            )
        else:
            st.info("Todavía no hay cobros registrados para estas cuentas.")


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

    # ---------------- Moras: alquiler, electricidad y agua ----------------
    hoy = recibo.hoy_bolivia()
    cfg_col = {
        "Departamento": st.column_config.TextColumn("Departamento", width="small"),
        "Inquilino": st.column_config.TextColumn("Inquilino", width="large"),
        "Meses atrasados": st.column_config.NumberColumn("Meses atrasados", format="%d", width="small"),
        "Deuda total": st.column_config.NumberColumn("Deuda total", format="Bs %.2f", width="small"),
    }
    mora_alquiler = moras.calcular_mora_alquiler(apartamentos, cargar_periodos_abiertos("alquiler"), hoy)
    mora_elec = moras.calcular_mora_consumo(
        apartamentos, cargar_periodos_abiertos("electricidad"), "pagos_electricidad", hoy)
    mora_agua = moras.calcular_mora_consumo(
        apartamentos, cargar_periodos_abiertos("agua"), "pagos_agua", hoy)

    def _total(filas):
        return sum(f["Deuda total"] for f in filas)

    n_ilegibles = sum(moras.contar_ilegibles(cargar_periodos_abiertos(t)) for t in ("alquiler", "electricidad", "agua"))
    if n_ilegibles:
        st.warning(AVISO_PERIODOS_ILEGIBLES.format(n=n_ilegibles))
    st.subheader("🚨 Moras (deudas pendientes)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"💵 Alquiler ({len(mora_alquiler)} deptos.)", fmt_money(_total(mora_alquiler)))
    m2.metric(f"⚡ Electricidad ({len(mora_elec)} deptos.)", fmt_money(_total(mora_elec)))
    m3.metric(f"💧 Agua ({len(mora_agua)} deptos.)", fmt_money(_total(mora_agua)))
    m4.metric("Total en mora", fmt_money(_total(mora_alquiler) + _total(mora_elec) + _total(mora_agua)))

    for titulo, filas, vacio in [
        ("💵 Mora de alquiler", mora_alquiler, "Sin alquileres atrasados."),
        ("⚡ Mora de electricidad", mora_elec, "Sin deudas de electricidad."),
        ("💧 Mora de agua", mora_agua, "Sin deudas de agua."),
    ]:
        with st.container(border=True):
            st.markdown(f"**{titulo}**")
            if filas:
                st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True,
                             column_config=cfg_col)
            else:
                st.success(vacio)
    st.caption(
        "Alquiler: deuda real. Cuenta los meses con saldo pendiente cuyo día de pago ya pasó (campo «Día de "
        "Pago» de la ficha; si no hay, el día de ingreso) y también los meses sin ningún registro desde el "
        "primer mes registrado (o la fecha de ingreso) hasta hoy; no incluye contratos de anticrético. "
        "Electricidad y agua: toda factura registrada con saldo pendiente. Solo se considera al inquilino "
        "actual de los apartamentos ocupados."
    )
    st.divider()

    # ---------------- Alertas: contratos ----------------
    filas_contrato = []
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
    if filas_contrato:
        st.subheader("📄 Contratos vencidos o por vencer (30 días)")
        filas_contrato.sort(key=lambda f: f["_orden"])
        st.dataframe(pd.DataFrame(filas_contrato).drop(columns=["_orden"]),
                     use_container_width=True, hide_index=True)
        st.divider()

    col1, col2 = st.columns(2)
    with col1:
        anio_sel = st.selectbox("Año", options=list(range(recibo.hoy_bolivia().year - 2, recibo.hoy_bolivia().year + 2)),
                                 index=2)
    with col2:
        mes_sel = st.selectbox("Mes", options=MESES, index=recibo.hoy_bolivia().month - 1)

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
    st.subheader("🔝 Mayor consumo (Top 5)")
    colsel1, colsel2 = st.columns(2)
    with colsel1:
        anio_consumo = st.selectbox("Año ", options=list(range(recibo.hoy_bolivia().year - 2, recibo.hoy_bolivia().year + 2)),
                                     index=2, key="anio_consumo")
    with colsel2:
        mes_consumo = st.selectbox("Mes ", options=MESES, index=recibo.hoy_bolivia().month - 1, key="mes_consumo")

    periodos_elec_sel = cargar_periodos_electricidad(anio=anio_consumo, mes=mes_consumo)
    periodos_agua_sel = cargar_periodos_agua(anio=anio_consumo, mes=mes_consumo)

    colE, colW = st.columns(2)
    with colE:
        st.markdown("**⚡ Electricidad (Kwh)**")
        filas_elec = []
        for p in periodos_elec_sel:
            apt_info = p.get("apartamentos") or {}
            consumo = calc_consumo.consumo_total(p, "electricidad")
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
            consumo = calc_consumo.consumo_total(p, "agua")
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
    if not es_admin:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()
    st.title("🏠 Gestión de Apartamentos")
    apt_con_aire = estado_disponible("apartamentos", "aire_acondicionado")
    apt_con_propiedad = apt_con_aire and estado_disponible("apartamentos", "aire_acondicionado_propiedad")
    if not apt_con_aire:
        st.warning(AVISO_MIGRACION_AIRE)
    elif not apt_con_propiedad:
        st.warning(AVISO_MIGRACION_AIRE_PROPIEDAD)

    tab_lista, tab_salida, tab_garantias, tab_nuevo, tab_importar = st.tabs(["📋 Lista y edición", "🚪 Salida de inquilino", "🛡️ Garantías", "➕ Nuevo apartamento", "📥 Importar CSV"])

    with tab_lista:
        apartamentos = cargar_apartamentos()
        if not apartamentos:
            st.info("No hay apartamentos registrados todavía.")
        else:
            codigos = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
            idx = st.selectbox("Selecciona un apartamento para ver o editar", range(len(apartamentos)),
                                format_func=lambda i: codigos[i])
            apt = apartamentos[idx]
            _tipos_contrato_edit = ["", "Alquiler", "Anticrético"]
            tipo_contrato = st.selectbox(
                "Tipo de contrato",
                _tipos_contrato_edit,
                index=_tipos_contrato_edit.index(apt["tipo_contrato"]) if apt.get("tipo_contrato") in _tipos_contrato_edit else 0,
                key=f"tipo_contrato_edit_{apt['id']}"
            )

            with st.form("editar_apartamento"):
                col1, col2 = st.columns(2)
                with col1:
                    codigo = st.text_input("Código", value=apt["codigo"])
                    piso = st.selectbox("Piso", PISOS, index=PISOS.index(apt["piso"]) if apt["piso"] in PISOS else 0)
                    estado = apt.get("estado") or "Desocupado"
                    st.text_input("Estado de ocupación", value=estado, disabled=True,
                                  help="La ocupación solo cambia mediante el procedimiento de salida o ingreso del inquilino.")
                    inquilino_nombre = apt.get("inquilino_nombre") or ""
                    st.text_input("Inquilino registrado", value=inquilino_nombre, disabled=True,
                                  help="Para cambiar de inquilino debe archivarse primero al ocupante anterior.")
                    celular = st.text_input("Celular", value=apt.get("celular") or "")
                    cedula_identidad = st.text_input("Cédula de identidad", value=apt.get("cedula_identidad") or "")
                    nacionalidad = st.text_input("Nacionalidad", value=apt.get("nacionalidad") or "")
                    if tipo_contrato == "Alquiler":
                        monto_alquiler = st.number_input("Monto de alquiler mensual (Bs)", min_value=0.0,
                                                          value=float(apt.get("monto_alquiler") or 0), step=50.0)
                    else:
                        monto_alquiler = float(apt.get("monto_alquiler") or 0)
                        st.caption("El monto mensual de alquiler no aplica a este contrato; se conserva el dato histórico.")
                with col2:
                    referencia_nombre = st.text_input("Referencia - nombre", value=apt.get("referencia_nombre") or "")
                    referencia_celular = st.text_input("Referencia - celular", value=apt.get("referencia_celular") or "")
                    _raw_fecha = apt.get("fecha_ingreso")
                    try:
                        _fecha_val = date.fromisoformat(str(_raw_fecha)[:10]) if _raw_fecha else None
                    except ValueError:
                        _fecha_val = None
                    fecha_ingreso = st.date_input("Fecha de ingreso", value=_fecha_val, format="DD/MM/YYYY")
                    if tipo_contrato == "Alquiler":
                        garantia = st.text_input("Garantía", value=apt.get("garantia") or "")
                    else:
                        garantia = None
                    amoblado = st.text_area("Amoblado", value=apt.get("amoblado") or "", height=70)
                    detalle = st.text_area("Detalle (ej. incluye agua/internet)", value=apt.get("detalle") or "",
                                            height=70)
                    if apt_con_aire:
                        tiene_aire = st.checkbox("❄️ Cuenta con aire acondicionado",
                                                 value=aire_acondicionado.a_bool(apt.get("aire_acondicionado")),
                                                 key=f'aire_edit_{apt["id"]}')
                        if apt_con_propiedad:
                            propiedad_aire = st.selectbox(
                                "Si tiene aire: ¿de quién es?", aire_acondicionado.OPCIONES_PROPIEDAD,
                                index=aire_acondicionado.indice_propiedad(apt.get("aire_acondicionado_propiedad")),
                                format_func=aire_acondicionado.etiqueta_propiedad,
                                key=f'aire_prop_edit_{apt["id"]}')
                    if tipo_contrato == "Alquiler":
                        _opciones_dia_pago = ["(sin definir)"] + [str(d) for d in range(1, 32)]
                        _dia_pago_actual = apt.get("dia_pago")
                        _idx_dia_pago = _opciones_dia_pago.index(str(_dia_pago_actual)) if _dia_pago_actual else 0
                        dia_pago_sel = st.selectbox("Día de Pago (día fijo del mes)", _opciones_dia_pago,
                                                     index=_idx_dia_pago)
                    else:
                        dia_pago_sel = str(apt.get("dia_pago")) if apt.get("dia_pago") else "(sin definir)"

                st.divider()
                st.markdown("**📄 Datos del contrato**")
                colc2 = st.container()
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

                if tipo_contrato == "Anticrético":
                    st.markdown("**💰 Datos específicos del anticrético**")
                    st.caption("Registra el capital entregado y la fecha en que corresponde devolverlo según el contrato.")
                    ca1, ca2 = st.columns(2)
                    with ca1:
                        monto_anticretico = st.number_input(
                            "Monto anticrético entregado", min_value=0.0, step=500.0,
                            value=float(apt.get("monto_anticretico") or 0), key=f"antic_monto_edit_{apt['id']}")
                        _monedas_antic = ["BOB (Bs)", "USD ($)"]
                        _moneda_actual = apt.get("anticretico_moneda") or "BOB"
                        moneda_anticretico = st.selectbox(
                            "Moneda del anticrético", _monedas_antic,
                            index=1 if _moneda_actual == "USD" else 0, key=f"antic_moneda_edit_{apt['id']}")
                    with ca2:
                        _raw_entrega = apt.get("anticretico_fecha_entrega")
                        try:
                            _entrega_val = date.fromisoformat(str(_raw_entrega)[:10]) if _raw_entrega else None
                        except ValueError:
                            _entrega_val = None
                        anticretico_fecha_entrega = st.date_input(
                            "Fecha de entrega del dinero", value=_entrega_val, format="DD/MM/YYYY",
                            key=f"antic_entrega_edit_{apt['id']}")
                        _raw_devol = apt.get("anticretico_fecha_devolucion")
                        try:
                            _devol_val = date.fromisoformat(str(_raw_devol)[:10]) if _raw_devol else None
                        except ValueError:
                            _devol_val = None
                        anticretico_fecha_devolucion = st.date_input(
                            "Fecha pactada para devolver el capital", value=_devol_val, format="DD/MM/YYYY",
                            key=f"antic_devol_edit_{apt['id']}")
                    anticretico_condiciones = st.text_area(
                        "Condiciones de devolución según contrato",
                        value=apt.get("anticretico_condiciones") or "",
                        key=f"antic_cond_edit_{apt['id']}",
                        help="Transcribir o resumir el plazo, aviso previo, forma y demás condiciones pactadas; prevalece el contrato firmado.")

                guardar = st.form_submit_button("💾 Guardar cambios", use_container_width=True)

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
                        "referencia_celular": referencia_celular or None,
                        "fecha_ingreso": str(fecha_ingreso) if fecha_ingreso else None,
                        "garantia": (garantia or None) if tipo_contrato == "Alquiler" else None,
                        "amoblado": amoblado or None,
                        "detalle": detalle or None,
                        "monto_alquiler": monto_alquiler,
                        "dia_pago": int(dia_pago_sel) if dia_pago_sel != "(sin definir)" else None,
                        "tipo_contrato": tipo_contrato or None,
                        "estado_contrato": estado_contrato,
                        "contrato_fecha_inicio": str(contrato_fecha_inicio) if contrato_fecha_inicio else None,
                        "contrato_fecha_fin": str(contrato_fecha_fin) if contrato_fecha_fin else None,
                        "contrato_observaciones": contrato_observaciones or None,
                        "monto_anticretico": monto_anticretico if tipo_contrato == "Anticrético" else 0,
                        "anticretico_moneda": "USD" if moneda_anticretico == "USD ($)" else "BOB",
                        "anticretico_fecha_entrega": str(anticretico_fecha_entrega) if tipo_contrato == "Anticrético" and anticretico_fecha_entrega else None,
                        "anticretico_fecha_devolucion": str(anticretico_fecha_devolucion) if tipo_contrato == "Anticrético" and anticretico_fecha_devolucion else None,
                        "anticretico_condiciones": anticretico_condiciones or None if tipo_contrato == "Anticrético" else None,
                    }
                    if tipo_contrato == "Anticrético":
                        if monto_anticretico <= 0:
                            st.error("Para un contrato de anticrético debes registrar el monto entregado.")
                            st.stop()
                        if anticretico_fecha_entrega and anticretico_fecha_devolucion and anticretico_fecha_devolucion < anticretico_fecha_entrega:
                            st.error("La fecha pactada de devolución no puede ser anterior a la entrega del dinero.")
                            st.stop()
                    if apt_con_aire:
                        payload["aire_acondicionado"] = bool(tiene_aire)
                    if apt_con_propiedad:
                        payload["aire_acondicionado_propiedad"] = aire_acondicionado.propiedad_a_guardar(tiene_aire, propiedad_aire)
                    error_aire = aire_acondicionado.validar(tiene_aire, propiedad_aire) if apt_con_propiedad else None
                    if error_aire:
                        st.error(error_aire)
                    else:
                        try:
                            db.actualizar_apartamento(apt["id"], payload)
                            limpiar_cache()
                            st.success("Apartamento actualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")

            if apt.get("estado") == "Ocupado" and (apt.get("inquilino_nombre") or "").strip():
                st.info("🚪 ¿Este inquilino se fue? Regístralo en la pestaña **«🚪 Salida de inquilino»** (arriba, junto a «Lista y edición»).")



            # Control de devolución del capital anticrético (no se mezcla con alquileres).
            if apt.get("tipo_contrato") == "Anticrético":
                st.divider()
                st.subheader("↩️ Devolución del capital anticrético")
                moneda = apt.get("anticretico_moneda") or "BOB"
                simbolo = "USD" if moneda == "USD" else "Bs"
                capital = float(apt.get("monto_anticretico") or 0)
                try:
                    devoluciones = db.listar_devoluciones_anticretico(apt["id"])
                except Exception as exc:
                    devoluciones = []
                    st.error(f"No se pudo consultar el historial de devoluciones. Verifica la migración anticrético: {exc}")
                devuelto = sum(float(x.get("monto") or 0) for x in devoluciones)
                saldo = max(0.0, capital - devuelto)
                k1, k2, k3 = st.columns(3)
                k1.metric("Capital anticrético", f"{simbolo} {capital:,.2f}")
                k2.metric("Capital devuelto", f"{simbolo} {devuelto:,.2f}")
                k3.metric("Saldo por devolver", f"{simbolo} {saldo:,.2f}")
                fecha_pactada = apt.get("anticretico_fecha_devolucion")
                if fecha_pactada:
                    fpd = parse_fecha(fecha_pactada)
                    if fpd and saldo > 0:
                        if recibo.hoy_bolivia() > fpd:
                            st.error(f"El plazo pactado de devolución venció el {fpd.strftime('%d/%m/%Y')}. Saldo pendiente: {simbolo} {saldo:,.2f}.")
                        elif (fpd - recibo.hoy_bolivia()).days <= 30:
                            st.warning(f"La devolución está prevista para el {fpd.strftime('%d/%m/%Y')}; faltan {(fpd-recibo.hoy_bolivia()).days} días.")
                        else:
                            st.info(f"Fecha pactada de devolución: {fpd.strftime('%d/%m/%Y')}.")
                if apt.get("anticretico_condiciones"):
                    st.caption("Condiciones pactadas: " + str(apt.get("anticretico_condiciones")))
                if devoluciones:
                    st.dataframe(pd.DataFrame([{
                        "Fecha": parse_fecha(x.get("fecha")),
                        "Monto devuelto": float(x.get("monto") or 0),
                        "Medio": x.get("medio_devolucion") or "—",
                        "Comprobante": x.get("comprobante") or "—",
                        "Registrado por": x.get("registrado_por") or "—",
                        "Observación": x.get("observacion") or "—",
                    } for x in devoluciones]), use_container_width=True, hide_index=True)
                if saldo > 0:
                    with st.form(f"form_devolucion_anticretico_{apt['id']}"):
                        st.markdown("**Registrar devolución de capital**")
                        rd1, rd2 = st.columns(2)
                        with rd1:
                            fecha_dev = st.date_input("Fecha de devolución", value=recibo.hoy_bolivia(), format="DD/MM/YYYY")
                            monto_dev = st.number_input("Monto devuelto", min_value=0.01, max_value=float(saldo),
                                                        value=min(float(saldo), 100.0), step=100.0)
                        with rd2:
                            medio_dev = st.selectbox("Medio de devolución", ["Efectivo", "Transferencia bancaria", "QR", "Cheque", "Otro"])
                            comprobante_dev = st.text_input("N.º de recibo o comprobante")
                        observacion_dev = st.text_area("Observación")
                        registrar_dev = st.form_submit_button("Registrar devolución")
                        if registrar_dev:
                            if monto_dev > saldo + 0.001:
                                st.error("El monto supera el saldo pendiente de devolución.")
                            else:
                                try:
                                    db.registrar_devolucion_anticretico({
                                        "apartamento_id": apt["id"],
                                        "fecha": str(fecha_dev),
                                        "monto": round(float(monto_dev), 2),
                                        "medio_devolucion": medio_dev,
                                        "comprobante": comprobante_dev.strip() or None,
                                        "observacion": observacion_dev.strip() or None,
                                        "registrado_por": usuario_actual.get("nombre") or usuario_actual.get("username"),
                                    })
                                    limpiar_cache()
                                    st.success("Devolución registrada.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"No se pudo registrar la devolución: {exc}")
                else:
                    st.success("El capital anticrético está totalmente devuelto.")

                # Registro separado de entregas recibidas del capital anticrético.
                st.divider()
                st.subheader("💰 Entregas del capital anticrético")
                st.caption("Registra cada entrega por su fecha real de recepción, incluso si ocurrió antes de firmar el contrato. Cada entrega genera un recibo independiente.")
                try:
                    entregas_ac = db.listar_entregas_anticretico(apt["id"], incluir_anuladas=True)
                except Exception as exc:
                    entregas_ac = []
                    st.error(f"No se pudo consultar el historial de entregas. Verifica la migración de entregas anticréticas: {exc}")
                entregas_vigentes_ac = [x for x in entregas_ac if (x.get("estado") or "vigente") == "vigente"]
                moneda_ac = str(apt.get("anticretico_moneda") or "BOB").upper()
                capital_ac = float(apt.get("monto_anticretico") or 0)
                total_recibido_ac = sum(float(x.get("monto") or 0) for x in entregas_vigentes_ac if str(x.get("moneda") or moneda_ac).upper() == moneda_ac)
                saldo_recibir_ac = max(0.0, capital_ac - total_recibido_ac)
                simbolo_ac = "USD" if moneda_ac == "USD" else "Bs"
                ec1, ec2, ec3 = st.columns(3)
                ec1.metric("Capital acordado", f"{simbolo_ac} {capital_ac:,.2f}")
                ec2.metric("Total recibido", f"{simbolo_ac} {total_recibido_ac:,.2f}")
                ec3.metric("Saldo por recibir", f"{simbolo_ac} {saldo_recibir_ac:,.2f}")
                if total_recibido_ac > capital_ac + 0.004:
                    st.error("Las entregas vigentes superan el capital contractual. No registres nuevos pagos; revisa los movimientos.")
                elif saldo_recibir_ac <= 0.004:
                    st.success("El capital anticrético está completamente recibido.")
                elif total_recibido_ac > 0:
                    st.info("Estado de recepción: pago parcial.")
                else:
                    st.info("Estado de recepción: pendiente de recibir.")

                if saldo_recibir_ac > 0.004 and total_recibido_ac <= capital_ac + 0.004:
                    with st.expander("➕ Registrar nueva entrega", expanded=not entregas_vigentes_ac):
                        with st.form(f"form_entrega_anticretico_{apt['id']}"):
                            ea1, ea2 = st.columns(2)
                            with ea1:
                                fecha_entrega_ac = st.date_input("Fecha real de recepción del dinero", value=recibo.hoy_bolivia(), format="DD/MM/YYYY", key=f"fecha_entrega_ac_{apt['id']}")
                                monto_entrega_ac = st.number_input("Monto recibido", min_value=0.01, max_value=float(saldo_recibir_ac), value=min(float(saldo_recibir_ac), 100.0), step=100.0, key=f"monto_entrega_ac_{apt['id']}")
                                etapa_entrega_ac = st.selectbox("Momento respecto a la firma", ["Antes de firmar el contrato", "Después de firmar el contrato"], key=f"etapa_entrega_ac_{apt['id']}")
                            with ea2:
                                medio_entrega_ac = st.selectbox("Medio de recepción", ["Efectivo", "Transferencia bancaria", "QR", "Depósito", "Cheque", "Otro"], key=f"medio_entrega_ac_{apt['id']}")
                                referencia_entrega_ac = st.text_input("N.º de comprobante / referencia", key=f"ref_entrega_ac_{apt['id']}")
                                entregante_ac = st.text_input("Nombre de quien entrega el dinero", value=apt.get("inquilino_nombre") or "", key=f"entregante_ac_{apt['id']}")
                            anuladas_para_reemplazo_ac = [x for x in entregas_ac if (x.get("estado") or "vigente") == "anulado"]
                            opciones_reemplazo_ac = {"No reemplaza otro recibo": None}
                            for x_rep in anuladas_para_reemplazo_ac:
                                opciones_reemplazo_ac[f"{x_rep.get('numero_recibo')} · {x_rep.get('fecha_entrega')} · {float(x_rep.get('monto') or 0):,.2f}"] = x_rep.get("id")
                            reemplazo_label_ac = st.selectbox("Recibo anulado que reemplaza (si corresponde)", list(opciones_reemplazo_ac.keys()), key=f"reemplazo_ac_{apt['id']}")
                            concepto_entrega_ac = st.text_input("Concepto", value="Entrega a cuenta del capital anticrético acordado", key=f"concepto_entrega_ac_{apt['id']}")
                            observacion_entrega_ac = st.text_area("Observaciones", key=f"obs_entrega_ac_{apt['id']}")
                            confirmar_entrega_ac = st.checkbox("Confirmo que el dinero fue efectivamente recibido y que los datos son correctos.", key=f"conf_entrega_ac_{apt['id']}")
                            guardar_entrega_ac = st.form_submit_button("Registrar entrega y generar recibo", type="primary")
                        if guardar_entrega_ac:
                            if not confirmar_entrega_ac:
                                st.error("Debes confirmar la recepción efectiva del dinero.")
                            elif not entregante_ac.strip():
                                st.error("Registra el nombre de quien entregó el dinero.")
                            elif monto_entrega_ac <= 0 or monto_entrega_ac > saldo_recibir_ac + 0.004:
                                st.error("El monto debe ser positivo y no puede superar el saldo por recibir.")
                            else:
                                try:
                                    nueva_entrega_ac = db.registrar_entrega_anticretico({
                                        "p_apartamento_id": apt["id"],
                                        "p_fecha_entrega": str(fecha_entrega_ac),
                                        "p_monto": round(float(monto_entrega_ac), 2),
                                        "p_moneda": moneda_ac,
                                        "p_etapa": "antes_firma" if etapa_entrega_ac.startswith("Antes") else "despues_firma",
                                        "p_medio_pago": medio_entrega_ac,
                                        "p_referencia": referencia_entrega_ac.strip() or None,
                                        "p_entregante": entregante_ac.strip(),
                                        "p_concepto": concepto_entrega_ac.strip() or "Entrega a cuenta del capital anticrético",
                                        "p_observacion": observacion_entrega_ac.strip() or None,
                                        "p_registrado_por": usuario_actual.get("nombre") or usuario_actual.get("username") or "Usuario",
                                        "p_reemplaza_id": opciones_reemplazo_ac.get(reemplazo_label_ac),
                                    })
                                    limpiar_cache()
                                    st.session_state[f"ultima_entrega_anticretico_{apt['id']}"] = nueva_entrega_ac
                                    st.success("Entrega registrada correctamente. El recibo está disponible en el historial.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"No se pudo registrar la entrega: {exc}")

                if entregas_ac:
                    st.markdown("**Historial de entregas y recibos**")
                    filas_entregas_ac = []
                    for x in entregas_ac:
                        filas_entregas_ac.append({
                            "Recibo": x.get("numero_recibo") or "—",
                            "Fecha real": parse_fecha(x.get("fecha_entrega")),
                            "Etapa": "Antes de firma" if x.get("etapa") == "antes_firma" else "Después de firma",
                            "Entregante": x.get("entregante") or "—",
                            "Monto": f'{x.get("moneda") or moneda_ac} {float(x.get("monto") or 0):,.2f}',
                            "Medio": x.get("medio_pago") or "—",
                            "Estado": "VIGENTE" if (x.get("estado") or "vigente") == "vigente" else "ANULADO",
                        })
                    st.dataframe(pd.DataFrame(filas_entregas_ac), use_container_width=True, hide_index=True)
                    datos_estado_ac = {
                        "apartamento": recibo.formatear_apartamento(apt),
                        "titular": apt.get("inquilino_nombre") or "—",
                        "moneda": moneda_ac,
                        "capital": capital_ac,
                        "recibido": total_recibido_ac,
                        "saldo": saldo_recibir_ac,
                        "entregas": entregas_ac,
                    }
                    st.download_button("📄 Descargar estado de cuenta consolidado (PDF)",
                        data=recibo.generar_estado_cuenta_anticretico_pdf(datos_estado_ac),
                        file_name=f"estado_cuenta_anticretico_{apt.get('codigo') or apt['id']}.pdf",
                        mime="application/pdf", key=f"estado_cuenta_ac_{apt['id']}")
                    acumulado_por_id_ac = {}
                    acumulado_ac = 0.0
                    for x_crono_ac in sorted(entregas_ac, key=lambda z: (z.get("fecha_entrega") or "", z.get("created_at") or "")):
                        if (x_crono_ac.get("estado") or "vigente") == "vigente":
                            acumulado_ac += float(x_crono_ac.get("monto") or 0)
                        acumulado_por_id_ac[x_crono_ac.get("id")] = max(0.0, capital_ac - acumulado_ac)
                    for x in entregas_ac:
                        with st.expander(f"🧾 {x.get('numero_recibo') or 'Recibo'} · {x.get('fecha_entrega')} · {x.get('estado', 'vigente').upper()}"):
                            st.write(f"**Entregante:** {x.get('entregante') or '—'}")
                            st.write(f"**Monto:** {x.get('moneda') or moneda_ac} {float(x.get('monto') or 0):,.2f}")
                            st.write(f"**Concepto:** {x.get('concepto') or '—'}")
                            st.write(f"**Medio:** {x.get('medio_pago') or '—'} · **Referencia:** {x.get('referencia') or '—'}")
                            if x.get("observacion"):
                                st.caption("Observación: " + str(x.get("observacion")))
                            estado_x = x.get("estado") or "vigente"
                            saldo_despues_x = acumulado_por_id_ac.get(x.get("id"), capital_ac)
                            datos_pdf_ac = {
                                "numero_recibo": x.get("numero_recibo") or "—",
                                "fecha_entrega": x.get("fecha_entrega") or "—",
                                "apartamento": recibo.formatear_apartamento(apt),
                                "entregante": x.get("entregante") or "—",
                                "recibido_por": x.get("registrado_por") or "—",
                                "monto_texto": f'{x.get("moneda") or moneda_ac} {float(x.get("monto") or 0):,.2f}',
                                "moneda": x.get("moneda") or moneda_ac,
                                "etapa_texto": "Antes de firmar el contrato" if x.get("etapa") == "antes_firma" else "Después de firmar el contrato",
                                "medio_pago": x.get("medio_pago") or "—",
                                "referencia": x.get("referencia") or "—",
                                "saldo_posterior": f'{x.get("moneda") or moneda_ac} {saldo_despues_x:,.2f}',
                                "concepto": x.get("concepto"),
                                "observacion": x.get("observacion"),
                                "estado_recibo": estado_x,
                            }
                            st.download_button("Descargar recibo PDF", data=recibo.generar_recibo_anticretico_pdf(datos_pdf_ac), file_name=f"{x.get('numero_recibo') or 'recibo_anticretico'}.pdf", mime="application/pdf", key=f"pdf_entrega_ac_{x['id']}")
                            if estado_x == "vigente" and es_admin:
                                with st.form(f"anular_entrega_ac_{x['id']}"):
                                    motivo_anulacion_x = st.text_input("Motivo de anulación", key=f"motivo_anular_ac_{x['id']}")
                                    confirmar_anulacion_x = st.checkbox("Confirmo que este recibo debe quedar anulado; no se borrará del historial.", key=f"confirm_anular_ac_{x['id']}")
                                    anular_btn_x = st.form_submit_button("Anular recibo")
                                if anular_btn_x:
                                    if not motivo_anulacion_x.strip() or not confirmar_anulacion_x:
                                        st.error("Indica el motivo y confirma la anulación.")
                                    else:
                                        try:
                                            db.anular_entrega_anticretico(x["id"], motivo_anulacion_x.strip(), usuario_actual.get("nombre") or usuario_actual.get("username") or "Usuario")
                                            limpiar_cache()
                                            st.success("Recibo anulado. El registro original permanece en el historial.")
                                            st.rerun()
                                        except Exception as exc:
                                            st.error(f"No se pudo anular el recibo: {exc}")
                            if estado_x == "anulado":
                                st.error(f"ANULADO · Motivo: {x.get('motivo_anulacion') or 'No especificado'} · Por: {x.get('anulado_por') or '—'}")

    with tab_salida:
        st.markdown("**Registrar que un inquilino se fue**")
        st.caption("Archiva al inquilino en el historial y deja el apartamento libre. Su deuda queda a su nombre: si después paga, "
                   "se le registra el pago en «🚪 Ex inquilinos» y la deuda se actualiza. Solo aparecen los apartamentos ocupados "
                   "que tienen un inquilino registrado.")
        aptos_ocupados = [a for a in cargar_apartamentos() if a.get("estado") == "Ocupado" and (a.get("inquilino_nombre") or "").strip()]
        if not aptos_ocupados:
            st.info("No hay apartamentos ocupados con un inquilino registrado. Si un apartamento debería aparecer aquí, revisa en "
                    "«Lista y edición» que esté como «Ocupado» y tenga el nombre del inquilino.")
        else:
            idx_salida = st.selectbox("Apartamento del que sale el inquilino", range(len(aptos_ocupados)), key="salida_apt_sel",
                                      format_func=lambda i: f'{aptos_ocupados[i]["codigo"]} — {aptos_ocupados[i]["inquilino_nombre"]}')
            apt = aptos_ocupados[idx_salida]
            st.caption("Archiva al inquilino en el historial y deja el apartamento libre. Su deuda queda a su nombre: si "
                       "después paga, se le registra el pago en «🚪 Ex inquilinos» y la deuda se actualiza.")
            sa1, sa2 = st.columns(2)
            with sa1:
                fecha_salida = st.date_input("Fecha de salida", value=recibo.hoy_bolivia(), format="DD/MM/YYYY",
                                             key=f'salida_fecha_{apt["id"]}')
            with sa2:
                registrar_meses = st.checkbox(
                    "Registrar como deuda los meses de alquiler vencidos sin ningún pago", value=True,
                    key=f'salida_meses_{apt["id"]}',
                    help="Si no se marca, esos meses no quedarían registrados como deuda del ex inquilino.")
            obs_salida = st.text_area("Observación (motivo, estado del apartamento, acuerdo de pago…)", height=70,
                                      key=f'salida_obs_{apt["id"]}')
            periodos_salida = {t: [p for p in cargar_periodos_abiertos(t) if p.get("apartamento_id") == apt["id"]]
                               for t in ("alquiler", "electricidad", "agua")}
            resumen_s = exinquilinos.resumen_salida(
                apt, periodos_salida["alquiler"], periodos_salida["electricidad"], periodos_salida["agua"],
                fecha_salida or recibo.hoy_bolivia(), registrar_meses)
            st.markdown(f"**Deuda con la que sale:** alquiler {fmt_money(resumen_s['alquiler'])} · luz {fmt_money(resumen_s['luz'])} · "
                        f"agua {fmt_money(resumen_s['agua'])} · **total {fmt_money(resumen_s['total'])}**")
            if resumen_s["meses_sin_registro"]:
                st.caption("Meses de alquiler sin ningún pago: " + ", ".join(m["etiqueta"] for m in resumen_s["meses_sin_registro"]) + ".")
            confirmar_salida = st.checkbox(
                "Confirmo que este inquilino ya salió: su ficha se archivará y el apartamento quedará desocupado.",
                key=f'salida_confirmar_{apt["id"]}')
            if st.button("🚪 Registrar salida", key=f'salida_boton_{apt["id"]}'):
                errores_salida = exinquilinos.validar_salida(apt, fecha_salida, confirmar_salida)
                for e in errores_salida:
                    st.error(e)
                if not errores_salida:
                    try:
                        if registrar_meses:
                            for m in resumen_s["meses_sin_registro"]:
                                db.obtener_o_crear_periodo(apt["id"], m["mes"], m["anio"], m["monto"], apt.get("inquilino_nombre"))
                        db.registrar_salida_inquilino(
                            apt["id"], fecha_salida, obs_salida, usuario_actual.get("nombre") or usuario_actual.get("username"))
                        # Solo después de guardar la salida, pasar la garantía a liquidación.
                        garantias_activas_salida = db.listar_garantias_alquiler(apartamento_id=apt["id"], estado="Vigente")
                        for garantia_activa in garantias_activas_salida:
                            db.actualizar_garantia_alquiler(garantia_activa["id"], {
                                "estado": "Pendiente de liquidación",
                                "fecha_salida": str(fecha_salida),
                                "observacion_salida": obs_salida or None,
                            })
                        limpiar_cache()
                        st.success("Salida registrada. El inquilino quedó en el historial con su deuda. Si paga después, "
                                   "regístralo en «🚪 Ex inquilinos».")
                        st.rerun()
                    except Exception as e:
                        st.error(texto_error_historial("No se pudo registrar la salida", e))

    with tab_garantias:
        st.subheader("🛡️ Control de garantías de alquiler")
        apartamentos_por_id_g = {str(a.get("id")): a for a in cargar_apartamentos()}
        st.caption("La garantía es un depósito reembolsable: no es ingreso por alquiler. Cada garantía queda vinculada al inquilino y a su periodo de ocupación.")
        ocupados_g = [a for a in cargar_apartamentos()
                      if a.get("estado") == "Ocupado" and a.get("tipo_contrato") == "Alquiler"
                      and (a.get("inquilino_nombre") or "").strip()]
        tg1, tg2 = st.tabs(["➕ Registrar garantía recibida", "📋 Garantías y liquidaciones"])
        with tg1:
            if not ocupados_g:
                st.info("No hay apartamentos ocupados con contrato de alquiler.")
            else:
                apt_g_idx = st.selectbox("Apartamento e inquilino", range(len(ocupados_g)),
                    format_func=lambda i: f'{ocupados_g[i]["codigo"]} — {ocupados_g[i]["inquilino_nombre"]}',
                    key="garantia_apto_reg")
                apt_g = ocupados_g[apt_g_idx]
                monto_sugerido = float(apt_g.get("monto_alquiler") or 0)
                with st.form("form_registrar_garantia_alquiler", clear_on_submit=True):
                    g1, g2 = st.columns(2)
                    with g1:
                        monto_g = st.number_input("Monto de garantía recibido (Bs)", min_value=0.01,
                            value=max(monto_sugerido, 0.01), step=50.0)
                        fecha_g = st.date_input("Fecha de recepción", value=recibo.hoy_bolivia(), format="DD/MM/YYYY")
                    with g2:
                        medio_g = st.selectbox("Medio de recepción", ["Efectivo", "Transferencia bancaria", "QR", "Depósito", "Otro"])
                        recibo_g = st.text_input("N.º de recibo o comprobante")
                    obs_g = st.text_area("Observaciones")
                    guardar_g = st.form_submit_button("Registrar garantía")
                    if guardar_g:
                        try:
                            existentes = db.listar_garantias_alquiler(apartamento_id=apt_g["id"], estado="Vigente")
                            if existentes:
                                st.error("Este apartamento ya tiene una garantía vigente. Revisa el historial antes de registrar otra.")
                            else:
                                db.crear_garantia_alquiler({
                                    "apartamento_id": apt_g["id"],
                                    "inquilino_nombre": apt_g.get("inquilino_nombre"),
                                    "fecha_recepcion": str(fecha_g),
                                    "monto_recibido": round(float(monto_g), 2),
                                    "moneda": "BOB",
                                    "monto_alquiler_referencia": round(monto_sugerido, 2),
                                    "medio_recepcion": medio_g,
                                    "comprobante_recepcion": recibo_g.strip() or None,
                                    "observacion": obs_g.strip() or None,
                                    "estado": "Vigente",
                                    "registrado_por": usuario_actual.get("nombre") or usuario_actual.get("username"),
                                })
                                limpiar_cache()
                                st.success("Garantía registrada y vinculada al inquilino.")
                                st.rerun()
                        except Exception as exc:
                            st.error(f"No se pudo registrar la garantía: {exc}")
        with tg2:
            st.markdown("**Movimientos de tesorería vinculados a garantías**")
            try:
                movs_garantia = db.listar_movimientos_garantias_tesoreria()
                if movs_garantia:
                    st.dataframe(pd.DataFrame([{
                        "Fecha": m.get("fecha"),
                        "Movimiento": "Entrada" if m.get("direccion") == "ENTRADA" else "Salida",
                        "Concepto": m.get("concepto"),
                        "Monto": float(m.get("monto") or 0),
                        "Medio": m.get("medio") or "—",
                        "Apartamento": m.get("apartamento_id"),
                        "Persona": m.get("persona") or "—",
                        "Comprobante": m.get("comprobante") or "—",
                    } for m in movs_garantia]), use_container_width=True, hide_index=True)
                else:
                    st.info("Todavía no hay movimientos de tesorería por garantías.")
            except Exception as exc:
                st.error(f"No se pudieron cargar los movimientos de tesorería: {exc}")
            st.divider()
            try:
                garantias = db.listar_garantias_alquiler()
            except Exception as exc:
                garantias = []
                st.error(f"No se pudieron cargar las garantías. Verifica la migración V15: {exc}")
            if garantias:
                for g in garantias:
                    danos_g = db.listar_danos_garantia(g["id"])
                    devoluciones_g = db.listar_devoluciones_garantia(g["id"])
                    total_danos = sum(float(d.get("monto_aprobado") or 0) for d in danos_g)
                    total_devuelto = sum(float(d.get("monto") or 0) for d in devoluciones_g)
                    saldo = max(0.0, float(g.get("monto_recibido") or 0) - total_danos - total_devuelto)
                    with st.expander(f'{g.get("inquilino_nombre") or "Inquilino"} — {g.get("estado")} — Bs {saldo:,.2f} por devolver'):
                        apt_g_recibo = apartamentos_por_id_g.get(str(g.get("apartamento_id")), {
                            "codigo": str(g.get("apartamento_id") or "—"), "piso": ""
                        })
                        mostrar_botones_recibo_garantia(g, apt_g_recibo, key_sufijo=f'g_{g["id"]}')
                        x1, x2, x3 = st.columns(3)
                        x1.metric("Garantía recibida", f'Bs {float(g.get("monto_recibido") or 0):,.2f}')
                        x2.metric("Descuentos aprobados", f'Bs {total_danos:,.2f}')
                        x3.metric("Devoluciones realizadas", f'Bs {total_devuelto:,.2f}')
                        st.caption(f'Recepción: {g.get("fecha_recepcion")} · Comprobante: {g.get("comprobante_recepcion") or "—"} · Apartamento ID: {g.get("apartamento_id")}')
                        if danos_g:
                            st.markdown("**Daños y cotizaciones**")
                            st.dataframe(pd.DataFrame([{
                                "Fecha": d.get("fecha"), "Daño": d.get("descripcion"),
                                "Cotización": d.get("proveedor_cotizacion") or "—",
                                "Monto cotizado": float(d.get("monto_cotizado") or 0),
                                "Monto aprobado": float(d.get("monto_aprobado") or 0),
                                "Comprobante": d.get("comprobante") or "—",
                            } for d in danos_g]), use_container_width=True, hide_index=True)
                        if devoluciones_g:
                            st.markdown("**Devoluciones registradas**")
                            st.dataframe(pd.DataFrame([{
                                "Fecha": d.get("fecha"), "Monto": float(d.get("monto") or 0),
                                "Medio": d.get("medio") or "—", "Comprobante": d.get("comprobante") or "—",
                            } for d in devoluciones_g]), use_container_width=True, hide_index=True)
                        if g.get("estado") in ("Vigente", "Pendiente de liquidación", "Devolución parcial"):
                            with st.form(f"form_dano_garantia_{g['id']}"):
                                st.markdown("**Registrar desperfecto o daño**")
                                dg1, dg2 = st.columns(2)
                                with dg1:
                                    fecha_dano = st.date_input("Fecha de inspección/cotización", value=recibo.hoy_bolivia(), format="DD/MM/YYYY", key=f"fd_{g['id']}")
                                    descripcion_dano = st.text_input("Descripción del daño", key=f"dd_{g['id']}")
                                    proveedor_dano = st.text_input("Proveedor o responsable de cotización", key=f"pd_{g['id']}")
                                with dg2:
                                    cotizado_dano = st.number_input("Monto cotizado (Bs)", min_value=0.0, step=10.0, key=f"cd_{g['id']}")
                                    aprobado_dano = st.number_input("Monto aprobado para descuento (Bs)", min_value=0.0, step=10.0, key=f"ad_{g['id']}")
                                    comprobante_dano = st.text_input("Referencia de cotización/factura", key=f"refd_{g['id']}")
                                obs_dano = st.text_area("Observaciones del daño", key=f"od_{g['id']}")
                                guardar_dano = st.form_submit_button("Guardar daño y cotización")
                                if guardar_dano:
                                    if not descripcion_dano.strip():
                                        st.error("Describe el daño.")
                                    elif aprobado_dano > cotizado_dano:
                                        st.error("El monto aprobado no puede superar la cotización.")
                                    elif total_danos + aprobado_dano + total_devuelto > float(g.get("monto_recibido") or 0):
                                        st.error("El descuento supera el saldo disponible de la garantía.")
                                    else:
                                        db.crear_dano_garantia({
                                            "garantia_id": g["id"], "fecha": str(fecha_dano),
                                            "descripcion": descripcion_dano.strip(),
                                            "proveedor_cotizacion": proveedor_dano.strip() or None,
                                            "monto_cotizado": round(float(cotizado_dano),2),
                                            "monto_aprobado": round(float(aprobado_dano),2),
                                            "comprobante": comprobante_dano.strip() or None,
                                            "observacion": obs_dano.strip() or None,
                                            "registrado_por": usuario_actual.get("nombre") or usuario_actual.get("username"),
                                        })
                                        st.success("Daño registrado.")
                                        st.rerun()
                            if g.get("estado") == "Vigente":
                                if st.button("Marcar inquilino retirado e iniciar liquidación", key=f"retirar_g_{g['id']}"):
                                    db.actualizar_garantia_alquiler(g["id"], {"estado":"Pendiente de liquidación", "fecha_salida":str(recibo.hoy_bolivia())})
                                    st.rerun()
                        if g.get("estado") == "Pendiente de liquidación" and saldo <= 0.001 and total_devuelto <= 0.001:
                            if st.button("Cerrar liquidación: garantía retenida por daños documentados", key=f"cerrar_garantia_danos_{g['id']}"):
                                db.actualizar_garantia_alquiler(g["id"], {"estado": "Liquidada sin devolución"})
                                st.success("Liquidación cerrada.")
                                st.rerun()
                        if g.get("estado") in ("Pendiente de liquidación", "Devolución parcial") and saldo > 0:
                            with st.form(f"form_devolver_garantia_{g['id']}"):
                                st.markdown("**Registrar devolución de garantía**")
                                dv1, dv2 = st.columns(2)
                                with dv1:
                                    fecha_devol_g = st.date_input("Fecha de devolución", value=recibo.hoy_bolivia(), format="DD/MM/YYYY", key=f"fdevg_{g['id']}")
                                    monto_devol_g = st.number_input("Monto a devolver (Bs)", min_value=0.01, max_value=float(saldo),
                                        value=float(saldo), step=50.0, key=f"mdevg_{g['id']}")
                                with dv2:
                                    medio_devol_g = st.selectbox("Medio de devolución", ["Efectivo", "Transferencia bancaria", "QR", "Cheque", "Otro"], key=f"meddevg_{g['id']}")
                                    comprobante_devol_g = st.text_input("N.º de comprobante de devolución", key=f"compdevg_{g['id']}")
                                obs_devol_g = st.text_area("Observación de devolución", key=f"obsdevg_{g['id']}")
                                confirmar_devol_g = st.form_submit_button("Registrar devolución")
                                if confirmar_devol_g:
                                    if monto_devol_g > saldo + 0.001:
                                        st.error("La devolución supera el saldo de la garantía.")
                                    else:
                                        db.registrar_devolucion_garantia({
                                            "garantia_id": g["id"], "fecha":str(fecha_devol_g),
                                            "monto":round(float(monto_devol_g),2), "medio":medio_devol_g,
                                            "comprobante":comprobante_devol_g.strip() or None,
                                            "observacion":obs_devol_g.strip() or None,
                                            "registrado_por":usuario_actual.get("nombre") or usuario_actual.get("username"),
                                        })
                                        nuevo_devuelto = total_devuelto + float(monto_devol_g)
                                        estado_nuevo = "Liquidada" if nuevo_devuelto + total_danos >= float(g.get("monto_recibido") or 0) - 0.001 else "Devolución parcial"
                                        db.actualizar_garantia_alquiler(g["id"], {"estado":estado_nuevo})
                                        st.success("Devolución registrada.")
                                        st.rerun()
            else:
                st.info("Todavía no hay garantías registradas.")

    with tab_nuevo:
        tipo_contrato = st.selectbox("Tipo de contrato", ["", "Alquiler", "Anticrético"], key="tipo_nuevo_selector")
        with st.form("nuevo_apartamento", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código (ej. PB-01)")
                piso = st.selectbox("Piso", PISOS)
                estado = st.selectbox("Estado", ["Ocupado", "Desocupado"])
                inquilino_nombre = st.text_input("Nombre del inquilino")
                celular = st.text_input("Celular")
                if tipo_contrato == "Alquiler":
                    monto_alquiler = st.number_input("Monto de alquiler mensual (Bs)", min_value=0.0, step=50.0)
                else:
                    monto_alquiler = 0.0
                    st.caption("El monto mensual de alquiler no aplica a este contrato.")
            with col2:
                cedula_identidad = st.text_input("Cédula de identidad")
                nacionalidad = st.text_input("Nacionalidad")
                fecha_ingreso = st.date_input("Fecha de ingreso", value=None, format="DD/MM/YYYY")
                if tipo_contrato == "Alquiler":
                    garantia = st.text_input("Garantía")
                else:
                    garantia = None
                detalle = st.text_input("Detalle (ej. incluye agua/internet)")
                if tipo_contrato == "Alquiler":
                    dia_pago_sel = st.selectbox("Día de Pago (día fijo del mes)",
                                                 ["(sin definir)"] + [str(d) for d in range(1, 32)])
                else:
                    dia_pago_sel = "(sin definir)"
                if apt_con_aire:
                    tiene_aire_nuevo = st.checkbox("❄️ Cuenta con aire acondicionado", key="aire_nuevo")
                    if apt_con_propiedad:
                        propiedad_aire_nuevo = st.selectbox(
                            "Si tiene aire: ¿de quién es?", aire_acondicionado.OPCIONES_PROPIEDAD,
                            format_func=aire_acondicionado.etiqueta_propiedad, key="aire_prop_nuevo")

            st.divider()
            st.markdown("**📄 Datos del contrato**")
            estado_contrato = st.selectbox("Estado de contrato", ["Sin Contrato", "Vigente", "Caducado"],
                                            key="estado_c_nuevo")
            colc3, colc4 = st.columns(2)
            with colc3:
                contrato_fecha_inicio = st.date_input("Fecha inicio", value=None, format="DD/MM/YYYY", key="ci_nuevo")
            with colc4:
                contrato_fecha_fin = st.date_input("Fecha fin", value=None, format="DD/MM/YYYY", key="cf_nuevo")
            contrato_observaciones = st.text_area("Observaciones del contrato", key="obs_c_nuevo")

            if tipo_contrato == "Anticrético":
                st.markdown("**💰 Datos específicos del anticrético**")
                st.caption("Si seleccionas Anticrético, registra el capital recibido y la fecha en que corresponde devolverlo según el contrato.")
                nac1, nac2 = st.columns(2)
                with nac1:
                    monto_anticretico_nuevo = st.number_input("Monto anticrético entregado (Bs o USD)", min_value=0.0, step=500.0, key="antic_monto_nuevo")
                    moneda_anticretico_nuevo = st.selectbox("Moneda del anticrético", ["BOB (Bs)", "USD ($)"], key="antic_moneda_nuevo")
                with nac2:
                    anticretico_fecha_entrega_nuevo = st.date_input("Fecha de entrega del dinero", value=None, format="DD/MM/YYYY", key="antic_entrega_nuevo")
                    anticretico_fecha_devolucion_nuevo = st.date_input("Fecha pactada para devolver el capital", value=None, format="DD/MM/YYYY", key="antic_devol_nuevo")
                anticretico_condiciones_nuevo = st.text_area(
                    "Condiciones de devolución según contrato", key="antic_cond_nuevo",
                    help="Plazo, aviso previo, forma y demás condiciones pactadas en el contrato firmado.")
    
            if tipo_contrato != "Anticrético":
                monto_anticretico_nuevo = 0.0
                moneda_anticretico_nuevo = "BOB (Bs)"
                anticretico_fecha_entrega_nuevo = None
                anticretico_fecha_devolucion_nuevo = None
                anticretico_condiciones_nuevo = ""

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
                        "garantia": (garantia or None) if tipo_contrato == "Alquiler" else None,
                        "detalle": detalle or None,
                        "monto_alquiler": monto_alquiler,
                        "dia_pago": int(dia_pago_sel) if dia_pago_sel != "(sin definir)" else None,
                        "tipo_contrato": tipo_contrato or None,
                        "estado_contrato": estado_contrato,
                        "contrato_fecha_inicio": str(contrato_fecha_inicio) if contrato_fecha_inicio else None,
                        "contrato_fecha_fin": str(contrato_fecha_fin) if contrato_fecha_fin else None,
                        "contrato_observaciones": contrato_observaciones or None,
                        "monto_anticretico": monto_anticretico_nuevo if tipo_contrato == "Anticrético" else 0,
                        "anticretico_moneda": "USD" if moneda_anticretico_nuevo == "USD ($)" else "BOB",
                        "anticretico_fecha_entrega": str(anticretico_fecha_entrega_nuevo) if tipo_contrato == "Anticrético" and anticretico_fecha_entrega_nuevo else None,
                        "anticretico_fecha_devolucion": str(anticretico_fecha_devolucion_nuevo) if tipo_contrato == "Anticrético" and anticretico_fecha_devolucion_nuevo else None,
                        "anticretico_condiciones": anticretico_condiciones_nuevo or None if tipo_contrato == "Anticrético" else None,
                    }
                    if tipo_contrato == "Anticrético":
                        if monto_anticretico_nuevo <= 0:
                            st.error("Para un contrato de anticrético debes registrar el monto entregado.")
                            st.stop()
                        if anticretico_fecha_entrega_nuevo and anticretico_fecha_devolucion_nuevo and anticretico_fecha_devolucion_nuevo < anticretico_fecha_entrega_nuevo:
                            st.error("La fecha pactada de devolución no puede ser anterior a la entrega del dinero.")
                            st.stop()
                    if apt_con_aire:
                        payload["aire_acondicionado"] = bool(tiene_aire_nuevo)
                    if apt_con_propiedad:
                        payload["aire_acondicionado_propiedad"] = aire_acondicionado.propiedad_a_guardar(
                            tiene_aire_nuevo, propiedad_aire_nuevo)
                    error_aire = (aire_acondicionado.validar(tiene_aire_nuevo, propiedad_aire_nuevo)
                                  if apt_con_propiedad else None)
                    if error_aire:
                        st.error(error_aire)
                    else:
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
            "Opcionalmente también `aire_acondicionado` (Sí / No) y `aire_acondicionado_propiedad` "
            "(Del edificio / Del inquilino; solo se guarda si `aire_acondicionado` es Sí). "
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
                    if "aire_acondicionado" in payload:
                        if apt_con_aire:
                            payload["aire_acondicionado"] = aire_acondicionado.a_bool(payload["aire_acondicionado"])
                        else:
                            payload.pop("aire_acondicionado")      # la columna aún no existe: se omite en vez de fallar
                    if "aire_acondicionado_propiedad" in payload or "aire_acondicionado" in payload:
                        if apt_con_propiedad:
                            payload["aire_acondicionado_propiedad"] = aire_acondicionado.propiedad_a_guardar(
                                payload.get("aire_acondicionado"), payload.get("aire_acondicionado_propiedad"))
                        else:
                            payload.pop("aire_acondicionado_propiedad", None)
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
# PÁGINA: GESTIÓN UNIFICADA DE COBROS
# ==================================================================
elif pagina == "💳 Gestión de cobros":
    st.title("💳 Gestión de cobros por apartamento")
    st.caption("Administra alquiler, electricidad y agua desde una sola pantalla, sin volver a seleccionar el apartamento.")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("Primero registra apartamentos en la sección Apartamentos.")
        st.stop()

    codigos_cobros = [
        f'{a.get("codigo") or "Sin código"} — {a.get("inquilino_nombre") or "Sin inquilino"}'
        for a in apartamentos
    ]
    if "cobros_apartamento_idx" not in st.session_state:
        st.session_state["cobros_apartamento_idx"] = 0
    st.session_state["cobros_apartamento_idx"] = min(
        max(int(st.session_state["cobros_apartamento_idx"]), 0), len(apartamentos) - 1
    )

    # Los callbacks actualizan el estado ANTES de que Streamlit vuelva a crear
    # el selectbox. No se debe modificar la clave de un widget después de instanciarlo.
    def _cobros_ir_anterior():
        st.session_state["cobros_apartamento_idx"] = max(
            0, int(st.session_state.get("cobros_apartamento_idx", 0)) - 1
        )

    def _cobros_ir_siguiente():
        st.session_state["cobros_apartamento_idx"] = min(
            len(apartamentos) - 1,
            int(st.session_state.get("cobros_apartamento_idx", 0)) + 1
        )

    c_busca, c_periodo, c_nav = st.columns([2.5, 1.25, 1.4])
    with c_busca:
        idx_cobros = st.selectbox(
            "Buscar apartamento o inquilino", options=list(range(len(apartamentos))),
            format_func=lambda i: codigos_cobros[i], key="cobros_apartamento_idx"
        )
    with c_periodo:
        mes_cobros = st.selectbox("Mes", MESES, index=recibo.hoy_bolivia().month - 1, key="cobros_mes")
        anio_cobros = st.number_input(
            "Año", min_value=2000, max_value=2100, value=recibo.hoy_bolivia().year,
            step=1, key="cobros_anio"
        )
    with c_nav:
        st.write("")
        st.write("")
        nav_ant, nav_sig = st.columns(2)
        with nav_ant:
            st.button(
                "← Anterior", use_container_width=True,
                disabled=idx_cobros <= 0, key="cobros_anterior",
                on_click=_cobros_ir_anterior,
            )
        with nav_sig:
            st.button(
                "Siguiente →", use_container_width=True,
                disabled=idx_cobros >= len(apartamentos) - 1,
                key="cobros_siguiente", on_click=_cobros_ir_siguiente,
            )

    apt_cobros = apartamentos[idx_cobros]
    tipo_contrato_cobros = str(apt_cobros.get("tipo_contrato") or "").strip().lower()
    es_anticretico_cobros = tipo_contrato_cobros in ("anticrético", "anticretico")
    st.divider()
    ca, cb, cc = st.columns([1.2, 2.4, 1.4])
    with ca:
        st.markdown("#### 🏢 " + str(apt_cobros.get("codigo") or "Apartamento"))
    with cb:
        st.markdown("**" + str(apt_cobros.get("inquilino_nombre") or "Sin inquilino registrado") + "**")
        st.caption(f'Piso: {apt_cobros.get("piso") or "—"} · Estado: {apt_cobros.get("estado") or "—"}')
    with cc:
        if es_anticretico_cobros:
            moneda_antic_cobros = str(apt_cobros.get("anticretico_moneda") or "BOB").upper()
            simbolo_antic_cobros = "USD" if moneda_antic_cobros == "USD" else "Bs"
            st.metric("Capital anticrético", f"{simbolo_antic_cobros} {float(apt_cobros.get('monto_anticretico') or 0):,.2f}")
            st.caption("No corresponde cobro mensual de alquiler.")
        else:
            st.metric("Alquiler habitual", fmt_money(float(apt_cobros.get("monto_alquiler") or 0)))

    periodo_alq_cobros = db.obtener_periodo(apt_cobros["id"], mes_cobros, int(anio_cobros))
    periodo_elec_cobros = db.obtener_periodo_servicio("electricidad", apt_cobros["id"], mes_cobros, int(anio_cobros))
    periodo_agua_cobros = db.obtener_periodo_servicio("agua", apt_cobros["id"], mes_cobros, int(anio_cobros))

    def _resumen_servicio_cobros(periodo, campo_pagos, monto_base=0.0):
        esperado = float((periodo or {}).get("monto_esperado") or monto_base or 0)
        abonos_local = (periodo or {}).get(campo_pagos) or []
        pagado_local = sum(float(x.get("monto") or 0) for x in abonos_local)
        return esperado, pagado_local, esperado - pagado_local

    alq_esp, alq_pag, alq_deu = _resumen_servicio_cobros(periodo_alq_cobros, "pagos", float(apt_cobros.get("monto_alquiler") or 0))
    # Un contrato anticrético no genera alquiler mensual. Excluir cualquier monto_alquiler
    # heredado y los pagos asociados de los totales actuales de cobros.
    if es_anticretico_cobros:
        alq_esp, alq_pag, alq_deu = 0.0, 0.0, 0.0
    elec_esp, elec_pag, elec_deu = _resumen_servicio_cobros(periodo_elec_cobros, "pagos_electricidad")
    agua_esp, agua_pag, agua_deu = _resumen_servicio_cobros(periodo_agua_cobros, "pagos_agua")

    st.subheader(f"Estado de cobros — {mes_cobros} {int(anio_cobros)}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total esperado", fmt_money(alq_esp + elec_esp + agua_esp))
    m2.metric("Total pagado", fmt_money(alq_pag + elec_pag + agua_pag))
    m3.metric("Saldo pendiente", fmt_money(alq_deu + elec_deu + agua_deu))

    def _tarjeta_estado_cobro(titulo, esperado, pagado, deuda, periodo):
        estado = "Sin periodo" if periodo is None else ("Pagado" if deuda <= 0.004 else ("Parcial" if pagado > 0 else "Pendiente"))
        st.markdown(f"**{titulo}**")
        st.metric("Esperado", fmt_money(esperado), help=f"Estado: {estado}")
        st.caption(f"Pagado: {fmt_money(pagado)} · Saldo: {fmt_money(deuda)}")
        if periodo is None:
            st.caption("Aún no existe periodo/lectura registrado para este servicio.")

    etiqueta_contrato_cobros = "💰 Anticrético" if es_anticretico_cobros else "🏠 Alquiler"
    tab_resumen_cobros, tab_alquiler_cobros, tab_elec_cobros, tab_agua_cobros, tab_hist_cobros = st.tabs(
        ["📊 Resumen", etiqueta_contrato_cobros, "⚡ Electricidad", "💧 Agua", "📜 Historial"]
    )

    with tab_resumen_cobros:
        if es_anticretico_cobros:
            r1, r2, r3 = st.columns(3)
            with r1:
                st.metric("Capital anticrético", f"{simbolo_antic_cobros} {float(apt_cobros.get('monto_anticretico') or 0):,.2f}")
            with r2:
                st.metric("Electricidad pendiente", fmt_money(elec_deu))
            with r3:
                st.metric("Agua pendiente", fmt_money(agua_deu))
            st.info("Este apartamento tiene contrato de anticrético. No se genera alquiler mensual; aquí se gestionan únicamente los servicios y el historial.")
        else:
            r1, r2, r3 = st.columns(3)
            with r1:
                _tarjeta_estado_cobro("🏠 Alquiler", alq_esp, alq_pag, alq_deu, periodo_alq_cobros)
            with r2:
                _tarjeta_estado_cobro("⚡ Electricidad", elec_esp, elec_pag, elec_deu, periodo_elec_cobros)
            with r3:
                _tarjeta_estado_cobro("💧 Agua", agua_esp, agua_pag, agua_deu, periodo_agua_cobros)
            st.info("Selecciona una pestaña de servicio para registrar un pago o abono. El apartamento y el periodo se mantienen seleccionados.")

    with tab_alquiler_cobros:
        if es_anticretico_cobros:
            st.subheader("💰 Información del contrato anticrético")
            st.metric("Capital recibido", f"{simbolo_antic_cobros} {float(apt_cobros.get('monto_anticretico') or 0):,.2f}")
            st.caption("No corresponde registrar alquiler mensual para este apartamento.")
            if apt_cobros.get("anticretico_fecha_entrega"):
                st.write(f"**Fecha de entrega:** {apt_cobros.get('anticretico_fecha_entrega')}")
            if apt_cobros.get("anticretico_fecha_devolucion"):
                st.write(f"**Fecha pactada de devolución:** {apt_cobros.get('anticretico_fecha_devolucion')}")
            if apt_cobros.get("anticretico_condiciones"):
                st.write(f"**Condiciones:** {apt_cobros.get('anticretico_condiciones')}")
            if periodo_alq_cobros and periodo_alq_cobros.get("pagos"):
                st.warning("Existen pagos históricos clasificados como alquiler en este periodo. Se conservan para consulta, pero no se incluyen en los cobros actuales del anticrético.")
                for pago_hist_antic_cobros in periodo_alq_cobros.get("pagos") or []:
                    st.caption(f"{pago_hist_antic_cobros.get('fecha')} · {fmt_money(pago_hist_antic_cobros.get('monto'))} · Registro histórico")
        else:
            st.subheader("🏠 Pago de alquiler")
            _tarjeta_estado_cobro("Alquiler del periodo", alq_esp, alq_pag, alq_deu, periodo_alq_cobros)
            if es_admin:
                with st.expander("✏️ Ajustar monto esperado del alquiler"):
                    nuevo_esperado_cobros = st.number_input(
                        "Monto esperado (Bs)", min_value=0.0, step=50.0, value=alq_esp,
                        key=f"cobros_alq_esperado_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                    )
                    if st.button("Guardar monto esperado", key=f"cobros_alq_guardar_esp_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"):
                        try:
                            if periodo_alq_cobros:
                                db.actualizar_periodo(periodo_alq_cobros["id"], {"monto_esperado": nuevo_esperado_cobros})
                            else:
                                db.obtener_o_crear_periodo(
                                    apt_cobros["id"], mes_cobros, int(anio_cobros),
                                    nuevo_esperado_cobros, apt_cobros.get("inquilino_nombre")
                                )
                            limpiar_cache()
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo actualizar el monto: {e}")
            with st.form(f"cobros_form_alq_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    monto_alq_nuevo = st.number_input(
                        "Monto recibido (Bs)", min_value=0.0, step=10.0,
                        key=f"cobros_alq_monto_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                    )
                    fecha_alq_nuevo = st.date_input(
                        "Fecha de pago", value=recibo.hoy_bolivia(), format="DD/MM/YYYY",
                        key=f"cobros_alq_fecha_bo_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                    )
                with c2:
                    metodo_alq_nuevo = st.selectbox(
                        "Método de pago", METODOS_ABONO,
                        key=f"cobros_alq_metodo_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                    )
                    obs_alq_nuevo = st.text_input(
                        "Observación (opcional)",
                        key=f"cobros_alq_obs_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                    )
                if st.form_submit_button("💾 Registrar pago de alquiler", use_container_width=True):
                    if monto_alq_nuevo <= 0:
                        st.error("El monto debe ser mayor a cero.")
                    else:
                        try:
                            periodo_guardar_alq = db.obtener_o_crear_periodo(
                                apt_cobros["id"], mes_cobros, int(anio_cobros),
                                alq_esp, apt_cobros.get("inquilino_nombre")
                            )
                            db.crear_pago({
                                "periodo_id": periodo_guardar_alq["id"],
                                "fecha": str(fecha_alq_nuevo),
                                "monto": monto_alq_nuevo,
                                "metodo_pago": metodo_alq_nuevo,
                                "observacion": obs_alq_nuevo or None,
                            })
                            limpiar_cache()
                            st.success("Pago de alquiler registrado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo registrar el pago: {e}")
            if periodo_alq_cobros and periodo_alq_cobros.get("pagos"):
                st.markdown("**Abonos de este periodo**")
                for pago_cobros in sorted(periodo_alq_cobros["pagos"], key=lambda x: x.get("fecha") or ""):
                    with st.expander(
                        f'{pago_cobros.get("fecha")} · {fmt_money(pago_cobros.get("monto"))} · {pago_cobros.get("metodo_pago") or ""}'
                    ):
                        mostrar_botones_recibo(
                            pago_cobros, periodo_alq_cobros, apt_cobros, alq_pag,
                            key_sufijo=f"cobros_alq_{pago_cobros['id']}"
                        )

    def _panel_pago_servicio_cobros(servicio, periodo, campo_pagos, esperado, pagado, deuda, etiqueta):
        st.subheader(etiqueta)
        _tarjeta_estado_cobro(etiqueta, esperado, pagado, deuda, periodo)

        ui_lectura = SERVICIOS_UI[servicio]
        # Lecturas visibles tanto para periodos nuevos como para periodos ya creados.
        with st.expander("📏 Consultar o modificar lectura", expanded=False):
            if periodo is None:
                st.caption("Todavía no existe un periodo para este servicio y mes. Registra las lecturas para crearlo y habilitar los pagos.")
            else:
                st.caption("Este periodo ya existe. Puedes corregir las lecturas; los pagos registrados se conservarán y el saldo se recalculará con el nuevo monto esperado.")

            try:
                tarifa_actual_integrada = float(db.obtener_tarifa(servicio) or 0)
            except Exception:
                tarifa_actual_integrada = 0.0

            ultimo_integrado = db.ultimo_periodo_servicio(servicio, apt_cobros["id"])
            medidores_integrados = calc_consumo.cantidad_medidores_luz(apt_cobros) if servicio == "electricidad" else 1

            # Si el periodo existe, precargar sus lecturas. Si no, usar la lectura final del periodo anterior.
            ant_default_integrado = float(
                (periodo or {}).get(ui_lectura["col_anterior"])
                if (periodo or {}).get(ui_lectura["col_anterior"]) is not None
                else (ultimo_integrado or {}).get(ui_lectura["col_actual"]) or 0
            )
            act_default_integrado = float((periodo or {}).get(ui_lectura["col_actual"]) or ant_default_integrado)
            tarifa_default_integrada = float(
                (periodo or {}).get(ui_lectura["col_tarifa"])
                if (periodo or {}).get(ui_lectura["col_tarifa"]) is not None
                else tarifa_actual_integrada
            )
            ant2_default_integrado = float(
                (periodo or {}).get("kwh_anterior_2")
                if (periodo or {}).get("kwh_anterior_2") is not None
                else (ultimo_integrado or {}).get("kwh_actual_2") or 0
            )
            act2_default_integrado = float((periodo or {}).get("kwh_actual_2") or ant2_default_integrado)

            with st.form(f"cobros_lectura_{servicio}_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"):
                if medidores_integrados == 2:
                    st.markdown("**Medidor 1**")
                cl1, cl2 = st.columns(2)
                with cl1:
                    lectura_ant_integrada = st.number_input(
                        ui_lectura["etq_anterior"], min_value=0.0, step=1.0,
                        value=ant_default_integrado,
                        key=f"cobros_{servicio}_ant_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                    )
                with cl2:
                    lectura_act_integrada = st.number_input(
                        ui_lectura["etq_actual"], min_value=0.0, step=1.0,
                        value=act_default_integrado,
                        key=f"cobros_{servicio}_act_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                    )

                if medidores_integrados == 2:
                    st.markdown("**Medidor 2**")
                    cl3, cl4 = st.columns(2)
                    with cl3:
                        lectura_ant2_integrada = st.number_input(
                            "Medidor 2 · Kwh anterior", min_value=0.0, step=1.0,
                            value=ant2_default_integrado,
                            key=f"cobros_{servicio}_ant2_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                        )
                    with cl4:
                        lectura_act2_integrada = st.number_input(
                            "Medidor 2 · Kwh actual", min_value=0.0, step=1.0,
                            value=act2_default_integrado,
                            key=f"cobros_{servicio}_act2_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                        )
                else:
                    lectura_ant2_integrada = lectura_act2_integrada = 0.0

                tarifa_integrada = st.number_input(
                    ui_lectura["etq_tarifa"], min_value=0.0, step=0.01,
                    value=tarifa_default_integrada, format="%.4f",
                    key=f"cobros_{servicio}_tarifa_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                )
                consumo_integrado_1 = calc_consumo.calcular_consumo(lectura_ant_integrada, lectura_act_integrada)
                consumo_integrado_2 = calc_consumo.calcular_consumo(lectura_ant2_integrada, lectura_act2_integrada) if medidores_integrados == 2 else 0
                consumo_integrado = consumo_integrado_1 + consumo_integrado_2
                monto_integrado = calc_consumo.calcular_monto(consumo_integrado, tarifa_integrada)
                st.info(f"Consumo: {consumo_integrado} {ui_lectura['unidad']} × Bs {tarifa_integrada:.4f} = **{fmt_money(monto_integrado)}**")

                pagos_existentes_lectura = (periodo or {}).get(campo_pagos) or []
                if pagos_existentes_lectura:
                    st.warning(
                        f"Este periodo tiene {len(pagos_existentes_lectura)} pago(s) registrado(s) por "
                        f"{fmt_money(sum(float(x.get('monto') or 0) for x in pagos_existentes_lectura))}. "
                        "Al modificar la lectura se recalculará el saldo; los pagos no se eliminarán."
                    )
                    confirmar_recalculo_lectura = st.checkbox(
                        "Confirmo que deseo guardar la corrección de lectura y recalcular el saldo.",
                        key=f"cobros_confirmar_lectura_{servicio}_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                    )
                else:
                    confirmar_recalculo_lectura = True

                texto_boton_lectura = "💾 Actualizar lectura y recalcular saldo" if periodo else "💾 Guardar lectura y crear periodo"
                if st.form_submit_button(texto_boton_lectura, use_container_width=True):
                    if lectura_act_integrada < lectura_ant_integrada or (medidores_integrados == 2 and lectura_act2_integrada < lectura_ant2_integrada):
                        st.error("La lectura actual no puede ser menor que la lectura anterior.")
                    elif not confirmar_recalculo_lectura:
                        st.error("Confirma que deseas recalcular el saldo antes de guardar.")
                    else:
                        payload_integrado = {
                            ui_lectura["col_anterior"]: lectura_ant_integrada,
                            ui_lectura["col_actual"]: lectura_act_integrada,
                            ui_lectura["col_tarifa"]: tarifa_integrada,
                            "monto_esperado": monto_integrado,
                            "apartamento_id": apt_cobros["id"],
                            "mes": mes_cobros,
                            "anio": int(anio_cobros),
                        }
                        if medidores_integrados == 2:
                            payload_integrado.update({
                                "kwh_anterior_2": lectura_ant2_integrada,
                                "kwh_actual_2": lectura_act2_integrada,
                            })
                        try:
                            if periodo:
                                db.actualizar_periodo_servicio(servicio, periodo["id"], payload_integrado)
                                mensaje_lectura = "Lectura actualizada. Los pagos existentes se conservaron y el saldo se recalculó."
                            else:
                                db.crear_periodo_servicio(servicio, payload_integrado)
                                mensaje_lectura = "Lectura guardada y periodo creado. Ahora puedes registrar el abono."
                            limpiar_cache()
                            st.success(mensaje_lectura)
                            st.rerun()
                        except Exception as exc_integrado:
                            st.error(f"No se pudo guardar la lectura: {exc_integrado}")

        if periodo is None:
            st.info("Primero registra la lectura en «Consultar o modificar lectura» para habilitar el registro de pagos.")
            return

        st.markdown(f"**Monto esperado:** {fmt_money(esperado)} · **Pagado:** {fmt_money(pagado)} · **Saldo:** {fmt_money(deuda)}")
        with st.form(f"cobros_form_{servicio}_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                monto_serv_nuevo = st.number_input(
                    "Monto recibido (Bs)", min_value=0.0, step=10.0,
                    key=f"cobros_{servicio}_monto_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                )
                fecha_serv_nuevo = st.date_input(
                    "Fecha de pago", value=recibo.hoy_bolivia(), format="DD/MM/YYYY",
                    key=f"cobros_{servicio}_fecha_bo_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                )
            with c2:
                metodo_serv_nuevo = st.selectbox(
                    "Método de pago", METODOS_ABONO,
                    key=f"cobros_{servicio}_metodo_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                )
                obs_serv_nuevo = st.text_input(
                    "Observación (opcional)",
                    key=f"cobros_{servicio}_obs_{apt_cobros['id']}_{mes_cobros}_{anio_cobros}"
                )
            if st.form_submit_button(f"💾 Registrar abono de {etiqueta.lower()}", use_container_width=True):
                if monto_serv_nuevo <= 0:
                    st.error("El monto debe ser mayor a cero.")
                else:
                    try:
                        db.crear_pago_servicio(servicio, {
                            "periodo_id": periodo["id"], "fecha": str(fecha_serv_nuevo),
                            "monto": monto_serv_nuevo, "metodo_pago": metodo_serv_nuevo,
                            "observacion": obs_serv_nuevo or None,
                        })
                        limpiar_cache()
                        st.success(f"Abono de {etiqueta.lower()} registrado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo registrar el abono: {e}")

        abonos_serv_local = periodo.get(campo_pagos) or []
        if abonos_serv_local:
            st.markdown("**Abonos de este periodo**")
            for pago_serv_local in sorted(abonos_serv_local, key=lambda x: x.get("fecha") or ""):
                with st.expander(f'{pago_serv_local.get("fecha")} · {fmt_money(pago_serv_local.get("monto"))} · {pago_serv_local.get("metodo_pago") or ""}'):
                    mostrar_botones_recibo(
                        pago_serv_local, periodo, apt_cobros, pagado,
                        key_sufijo=f"cobros_{servicio}_{pago_serv_local['id']}", servicio=servicio
                    )
                    _formulario_editar_abono(servicio, pago_serv_local, f"cobros_{servicio}")

    with tab_elec_cobros:
        _panel_pago_servicio_cobros("electricidad", periodo_elec_cobros, "pagos_electricidad", elec_esp, elec_pag, elec_deu, "⚡ Electricidad")
    with tab_agua_cobros:
        _panel_pago_servicio_cobros("agua", periodo_agua_cobros, "pagos_agua", agua_esp, agua_pag, agua_deu, "💧 Agua")

    with tab_hist_cobros:
        st.subheader("Historial completo de pagos del apartamento")
        hcol1, hcol2 = st.columns(2)
        with hcol1:
            filtro_hist_anio = st.selectbox(
                "Año del historial", ["Todos"] + list(range(recibo.hoy_bolivia().year - 5, recibo.hoy_bolivia().year + 2)),
                key=f"cobros_hist_anio_{apt_cobros['id']}"
            )
        with hcol2:
            filtro_hist_servicio = st.selectbox(
                "Servicio", ["Todos", "Alquiler", "Electricidad", "Agua"],
                key=f"cobros_hist_servicio_{apt_cobros['id']}"
            )
        anio_hist_consulta = None if filtro_hist_anio == "Todos" else int(filtro_hist_anio)
        filas_hist_cobros = []

        # Alquiler: solo contratos de alquiler.
        if not es_anticretico_cobros and filtro_hist_servicio in ("Todos", "Alquiler"):
            for per_hist in db.listar_periodos(
                apartamento_id=apt_cobros["id"], anio=anio_hist_consulta, solo_activos=True
            ):
                for pago_hist in per_hist.get("pagos") or []:
                    filas_hist_cobros.append({
                        "Fecha": pago_hist.get("fecha"), "Periodo": f"{per_hist.get('mes')} {per_hist.get('anio')}",
                        "Servicio": "Alquiler", "Monto (Bs)": float(pago_hist.get("monto") or 0),
                        "Método": pago_hist.get("metodo_pago") or "", "Observación": pago_hist.get("observacion") or ""
                    })

        if filtro_hist_servicio in ("Todos", "Electricidad"):
            for per_hist in db.listar_periodos_servicio(
                "electricidad", apartamento_id=apt_cobros["id"], anio=anio_hist_consulta, solo_activos=True
            ):
                for pago_hist in per_hist.get("pagos_electricidad") or []:
                    filas_hist_cobros.append({
                        "Fecha": pago_hist.get("fecha"), "Periodo": f"{per_hist.get('mes')} {per_hist.get('anio')}",
                        "Servicio": "Electricidad", "Monto (Bs)": float(pago_hist.get("monto") or 0),
                        "Método": pago_hist.get("metodo_pago") or "", "Observación": pago_hist.get("observacion") or ""
                    })

        if filtro_hist_servicio in ("Todos", "Agua"):
            for per_hist in db.listar_periodos_servicio(
                "agua", apartamento_id=apt_cobros["id"], anio=anio_hist_consulta, solo_activos=True
            ):
                for pago_hist in per_hist.get("pagos_agua") or []:
                    filas_hist_cobros.append({
                        "Fecha": pago_hist.get("fecha"), "Periodo": f"{per_hist.get('mes')} {per_hist.get('anio')}",
                        "Servicio": "Agua", "Monto (Bs)": float(pago_hist.get("monto") or 0),
                        "Método": pago_hist.get("metodo_pago") or "", "Observación": pago_hist.get("observacion") or ""
                    })

        if filas_hist_cobros:
            df_hist_cobros = pd.DataFrame(filas_hist_cobros)
            df_hist_cobros["Fecha"] = pd.to_datetime(df_hist_cobros["Fecha"], errors="coerce")
            df_hist_cobros = df_hist_cobros.sort_values("Fecha", ascending=False)
            st.metric("Total de pagos encontrados", fmt_money(df_hist_cobros["Monto (Bs)"].sum()))
            st.dataframe(df_hist_cobros, use_container_width=True, hide_index=True)
        else:
            st.info("No se encontraron pagos con los filtros seleccionados. Prueba con «Todos» los años y servicios.")

    st.divider()
    st.caption("Los pagos se guardan en las tablas actuales de EQUISE. No se crean tablas nuevas ni se duplican registros.")


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
            mes = st.selectbox("Mes", MESES, index=recibo.hoy_bolivia().month - 1)
        with col2:
            anio = st.number_input("Año", min_value=2000, max_value=2100, value=recibo.hoy_bolivia().year, step=1)

        # obtiene (o prepara) el periodo de este apartamento/mes/año, con sus abonos ya hechos
        periodo = db.obtener_periodo(apt["id"], mes, int(anio))
        monto_esperado_actual = float(periodo["monto_esperado"]) if periodo else float(apt.get("monto_alquiler") or 0)
        abonos = periodo.get("pagos", []) if periodo else []
        pagado_hasta_ahora = sum(float(p["monto"]) for p in abonos)
        deuda_actual = monto_esperado_actual - pagado_hasta_ahora

        st.markdown(f"**Monto esperado del mes:** {fmt_money(monto_esperado_actual)}  |  "
                    f"**Pagado hasta ahora:** {fmt_money(pagado_hasta_ahora)}  |  "
                    f"**Deuda actual:** {fmt_money(deuda_actual)}")

        if es_admin:
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
            fecha_pago = st.date_input("Fecha del abono", value=recibo.hoy_bolivia(), format="DD/MM/YYYY")
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
                    mostrar_botones_recibo(p, periodo, apt, pagado_hasta_ahora, key_sufijo=f'alq_{p["id"]}')
                    st.divider()
                    with st.form(f'form_editar_pago_{p["id"]}'):
                        colf, colm = st.columns(2)
                        with colf:
                            _f = date.fromisoformat(str(p["fecha"])[:10])
                            edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY",
                                                        key=f'alq_fecha_{p["id"]}')
                        with colm:
                            edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                          value=float(p["monto"]), key=f'alq_monto_{p["id"]}')
                        edit_metodo = st.selectbox(
                            "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                            index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                            if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0,
                            key=f'alq_metodo_{p["id"]}'
                        )
                        edit_obs = st.text_input("Observación", value=p.get("observacion") or "",
                                                  key=f'alq_obs_{p["id"]}')

                        if es_admin:
                            colg, cold = st.columns(2)
                            guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                            eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)
                        else:
                            guardar_edit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                            eliminar_edit = False

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
                                        ["Todos"] + list(range(recibo.hoy_bolivia().year - 2, recibo.hoy_bolivia().year + 2)))
        with col3:
            filtro_mes = st.selectbox("Filtrar por mes", ["Todos"] + MESES)

        apt_id = None
        if filtro_apt != "Todos":
            apt_id = next(a["id"] for a in apartamentos if a["codigo"] == filtro_apt)

        st.caption("Se muestran solo los registros del inquilino actual. Los de inquilinos que ya salieron están en «🚪 Ex inquilinos».")
        periodos = _solo_mis_apartamentos(db.listar_periodos(
            apartamento_id=apt_id,
            anio=None if filtro_anio == "Todos" else filtro_anio,
            mes=None if filtro_mes == "Todos" else filtro_mes,
            solo_activos=True,
        ))

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
                            mostrar_botones_recibo(
                                p, detalle_periodo, detalle_periodo.get("apartamentos"),
                                total_pagado(detalle_periodo), key_sufijo=f'alq_hist_{p["id"]}'
                            )
                            st.divider()
                            with st.form(f'form_editar_pago_hist_{p["id"]}'):
                                colf, colm = st.columns(2)
                                with colf:
                                    _f = date.fromisoformat(str(p["fecha"])[:10])
                                    edit_fecha = st.date_input("Fecha", value=_f, format="DD/MM/YYYY",
                                                                key=f'alq_hist_fecha_{p["id"]}')
                                with colm:
                                    edit_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0,
                                                                  value=float(p["monto"]),
                                                                  key=f'alq_hist_monto_{p["id"]}')
                                edit_metodo = st.selectbox(
                                    "Método de pago", ["Efectivo", "Transferencia", "QR", "Otro"],
                                    index=["Efectivo", "Transferencia", "QR", "Otro"].index(p.get("metodo_pago"))
                                    if p.get("metodo_pago") in ["Efectivo", "Transferencia", "QR", "Otro"] else 0,
                                    key=f'alq_hist_metodo_{p["id"]}'
                                )
                                edit_obs = st.text_input("Observación", value=p.get("observacion") or "",
                                                          key=f'alq_hist_obs_{p["id"]}')

                                if es_admin:
                                    colg, cold = st.columns(2)
                                    guardar_edit = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                    eliminar_edit = cold.form_submit_button("🗑️ Eliminar abono", use_container_width=True)
                                else:
                                    guardar_edit = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                                    eliminar_edit = False

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
    pagina_consumo("electricidad")

elif pagina == "💧 Agua":
    pagina_consumo("agua")


# ==================================================================
# PÁGINA: ESTADO DE CUENTA (deuda real por inquilino)
# ==================================================================
elif pagina == "📑 Estado de cuenta":
    st.title("📑 Estado de cuenta")
    st.subheader("Estado de cuenta por apartamento")
    st.caption(
        "Reporte para entregar al inquilino con sus pagos realizados y su deuda real de alquiler y "
        "electricidad, calculada a la fecha de hoy. Aplica a apartamentos ocupados con contrato de alquiler. Solo cuenta al "
        "inquilino actual: los inquilinos que ya salieron aparecen aparte, al final."
    )

    hoy_rep = recibo.hoy_bolivia()
    nombre_emisor = usuario_actual.get("nombre") or usuario_actual.get("username")
    apartamentos = cargar_apartamentos()
    alq_por_apt, elec_por_apt = {}, {}
    for p in cargar_periodos_abiertos("alquiler"):
        alq_por_apt.setdefault(p["apartamento_id"], []).append(p)
    for p in cargar_periodos_abiertos("electricidad"):
        elec_por_apt.setdefault(p["apartamento_id"], []).append(p)

    n_ilegibles = (moras.contar_ilegibles(cargar_periodos_abiertos("alquiler"))
                   + moras.contar_ilegibles(cargar_periodos_abiertos("electricidad")))
    if n_ilegibles:
        st.warning(AVISO_PERIODOS_ILEGIBLES.format(n=n_ilegibles))

    estados_cuenta, no_aplican = [], []
    for apt in apartamentos:
        d = moras.deuda_real_inquilino(apt, alq_por_apt.get(apt["id"], []), elec_por_apt.get(apt["id"], []), hoy_rep)
        if d["aplica"]:
            estados_cuenta.append((apt, d))
        else:
            no_aplican.append((apt, d["motivo"]))

    if not estados_cuenta:
        st.info("No hay apartamentos ocupados con contrato de alquiler.")
    else:
        # ---------- Resumen de todos los apartamentos ----------
        total_alq = sum(d["alquiler"]["deuda"] for _a, d in estados_cuenta)
        total_elec = sum(d["electricidad"]["deuda"] for _a, d in estados_cuenta)
        r1, r2, r3 = st.columns(3)
        r1.metric("💵 Deuda de alquiler", fmt_money(total_alq))
        r2.metric("⚡ Deuda de electricidad", fmt_money(total_elec))
        r3.metric("Deuda total", fmt_money(total_alq + total_elec))

        filas_resumen = []
        for apt, d in estados_cuenta:
            up = d["alquiler"]["ultimo_pago"]
            filas_resumen.append({
                "Departamento": apt.get("codigo") or "—",
                "Inquilino": apt.get("inquilino_nombre") or "—",
                "Meses atrasados": d["alquiler"]["meses_atrasados"],
                "Deuda alquiler": d["alquiler"]["deuda"],
                "Deuda electricidad": d["electricidad"]["deuda"],
                "Deuda total": d["deuda_total"],
                "Último pago de alquiler": up["fecha"].strftime("%d/%m/%Y") if up else "Sin pagos",
            })
        filas_resumen.sort(key=lambda f: (-f["Deuda total"], f["Departamento"]))
        with st.container(border=True):
            st.markdown("**Resumen de deuda real por apartamento**")
            st.dataframe(
                pd.DataFrame(filas_resumen), use_container_width=True, hide_index=True,
                column_config={
                    "Meses atrasados": st.column_config.NumberColumn(format="%d"),
                    "Deuda alquiler": st.column_config.NumberColumn(format="Bs %.2f"),
                    "Deuda electricidad": st.column_config.NumberColumn(format="Bs %.2f"),
                    "Deuda total": st.column_config.NumberColumn(format="Bs %.2f"),
                },
            )

        # ---------- Reporte individual (vista previa + descargas) ----------
        st.divider()
        st.markdown("### Reporte para entregar al inquilino")
        etiquetas = [f'{a.get("codigo")} — {a.get("inquilino_nombre") or "sin nombre"}' for a, _d in estados_cuenta]
        indice = st.selectbox("Apartamento", range(len(estados_cuenta)), format_func=lambda i: etiquetas[i],
                              key="rep_apartamento")
        apt_sel, deuda_sel = estados_cuenta[indice]
        datos_rep = recibo.construir_datos_reporte_inquilino(apt_sel, deuda_sel, emitido_por=nombre_emisor)
        pdf_rep = _reporte_pdf_cache(datos_rep, REPORTE_DISENO_VERSION)
        png_rep = _reporte_png_cache(datos_rep, REPORTE_DISENO_VERSION)

        b1, b2 = st.columns(2)
        with b1:
            st.download_button("📄 Descargar reporte (PDF)", data=pdf_rep,
                               file_name=_nombre_archivo_reporte(apt_sel, hoy_rep, "pdf"),
                               mime="application/pdf", key="rep_pdf", use_container_width=True)
        with b2:
            st.download_button("🖼️ Descargar reporte (PNG)", data=png_rep,
                               file_name=_nombre_archivo_reporte(apt_sel, hoy_rep, "png"),
                               mime="image/png", key="rep_png", use_container_width=True)
        st.image(png_rep, width=640)

        # ---------- Transparencia: qué pagos lee este reporte (para comparar con la realidad) ----------
        with st.expander("🔎 Ver los pagos que usa este reporte (los 10 más recientes)"):
            def _abonos_leidos(periodos, campo_pagos):
                filas = [{"Fecha": f'{f:%d/%m/%Y}' if (f := parse_fecha(pg.get("fecha"))) else str(pg.get("fecha")),
                          "Periodo": f'{p.get("mes")} {p.get("anio")}', "Monto": float(pg.get("monto") or 0),
                          "_orden": str(pg.get("fecha") or "")}
                         for p in periodos for pg in (p.get(campo_pagos) or [])]
                return sorted(filas, key=lambda x: x["_orden"], reverse=True)

            def _tabla_abonos(titulo, periodos, campo_pagos):
                claves = sorted(k for k in (moras._clave_periodo(p) for p in periodos) if k)
                st.markdown(f"**{titulo}**")
                if claves:
                    st.caption(f"{len(periodos)} periodo(s) leídos, de {moras.MESES[claves[0][1] - 1]} {claves[0][0]} "
                               f"a {moras.MESES[claves[-1][1] - 1]} {claves[-1][0]}.")
                else:
                    st.caption("No hay periodos registrados para este inquilino.")
                filas = _abonos_leidos(periodos, campo_pagos)[:10]
                if filas:
                    st.dataframe(pd.DataFrame(filas).drop(columns=["_orden"]), use_container_width=True, hide_index=True,
                                 column_config={"Monto": st.column_config.NumberColumn(format="Bs %.2f")})
                else:
                    st.caption("Sin pagos registrados.")

            xa, xb = st.columns(2)
            with xa:
                _tabla_abonos("Alquiler", alq_por_apt.get(apt_sel["id"], []), "pagos")
            with xb:
                _tabla_abonos("Electricidad", elec_por_apt.get(apt_sel["id"], []), "pagos_electricidad")
            st.caption("«Último pago» es la fecha más reciente de esta lista. Si falta un pago que sí hiciste, revisa que esté "
                       "registrado en «Pagos de Alquiler» con esa fecha y dentro del periodo del inquilino actual.")

        # ---------- Todos los apartamentos en un solo ZIP ----------
        st.divider()
        st.markdown("### Descargar todos los reportes")
        st.caption("Genera un ZIP con el PDF de cada apartamento ocupado en alquiler, listo para imprimir o enviar.")
        if st.button("📦 Preparar ZIP con todos los PDF"):
            with st.spinner("Generando reportes..."):
                memoria = io.BytesIO()
                with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zf:
                    for apt, d in estados_cuenta:
                        datos_i = recibo.construir_datos_reporte_inquilino(apt, d, emitido_por=nombre_emisor)
                        zf.writestr(_nombre_archivo_reporte(apt, hoy_rep, "pdf"), _reporte_pdf_cache(datos_i, REPORTE_DISENO_VERSION))
                st.session_state["rep_zip"] = (hoy_rep, memoria.getvalue(), len(estados_cuenta))
        zip_guardado = st.session_state.get("rep_zip")
        if zip_guardado and zip_guardado[0] == hoy_rep:
            st.download_button(f"⬇️ Descargar ZIP ({zip_guardado[2]} reportes)", data=zip_guardado[1],
                               file_name=f"estados_de_cuenta_{hoy_rep:%Y-%m-%d}.zip",
                               mime="application/zip", key="rep_zip_dl")

    if no_aplican:
        with st.expander(f"Apartamentos sin reporte ({len(no_aplican)})"):
            for apt, motivo in no_aplican:
                st.write(f'**{apt.get("codigo")}**: {motivo}')

    # ---------- Ex inquilinos: su deuda queda a su nombre, separada de la del inquilino actual ----------
    try:
        historial_ec = cargar_historial()
        cerrados_ec = {t: cargar_periodos_cerrados(t) for t in ("alquiler", "electricidad", "agua")}
    except Exception:
        historial_ec, cerrados_ec = [], {}          # si el historial no se puede leer, la pantalla «Ex inquilinos» muestra el detalle del error
    por_hist_ec = exinquilinos.agrupar_por_historial(cerrados_ec)
    apts_ec = {a["id"]: a for a in apartamentos}
    filas_ex_ec = []
    for h_ec in historial_ec:
        deuda_ec = exinquilinos.deuda_ex_inquilino(por_hist_ec.get(h_ec["id"], {}))
        if deuda_ec["total"] > exinquilinos.TOLERANCIA:
            filas_ex_ec.append({"Apartamento": (apts_ec.get(h_ec.get("apartamento_id")) or {}).get("codigo") or "—",
                                "Ex inquilino": exinquilinos.nombre_ex_inquilino(h_ec),
                                "Fecha de salida": str(h_ec.get("fecha_salida") or "—")[:10],
                                "Alquiler": deuda_ec["alquiler"], "Luz": deuda_ec["luz"], "Agua": deuda_ec["agua"],
                                "Deuda total": deuda_ec["total"]})
    if filas_ex_ec:
        with st.container(border=True):
            st.markdown("**👥 Ex inquilinos con deuda pendiente** (separada de la deuda de los inquilinos actuales)")
            st.dataframe(pd.DataFrame(filas_ex_ec), use_container_width=True, hide_index=True, column_config={
                c: st.column_config.NumberColumn(format="Bs %.2f") for c in ("Alquiler", "Luz", "Agua", "Deuda total")})
            st.caption(f"Total: {fmt_money(sum(f['Deuda total'] for f in filas_ex_ec))}. Para ver el detalle o registrar un pago, "
                       "ve a «🚪 Ex inquilinos».")

elif pagina == "📊 Actividad por usuario":
    st.title("📊 Reporte de actividad por usuario")
    st.caption(
        "Pagos, compras y ventas registrados por cada usuario (campo «Encargado») entre dos fechas. "
        "Los abonos de alquiler, electricidad y agua no guardan quién los cobró, por eso no aparecen aquí."
    )
    hoy_act = recibo.hoy_bolivia()
    nombre_emisor = usuario_actual.get("nombre") or usuario_actual.get("username")
    ca1, ca2 = st.columns(2)
    with ca1:
        act_desde = st.date_input("Desde", value=hoy_act.replace(day=1), format="DD/MM/YYYY", key="act_desde")
    with ca2:
        act_hasta = st.date_input("Hasta", value=hoy_act, format="DD/MM/YYYY", key="act_hasta")
    if not act_desde or not act_hasta:
        st.warning("Elige las dos fechas.")
        st.stop()
    if act_desde > act_hasta:
        st.error("La fecha «Desde» no puede ser posterior a «Hasta».")
        st.stop()

    datos_act = cargar_actividad(str(act_desde), str(act_hasta))
    activos = sorted({(u.get("nombre") or u.get("username")) for u in cargar_todos_los_usuarios()
                      if u.get("activo")} - {None})
    grupos = reportes.agrupar_actividad_por_usuario(
        datos_act["pagos_generales"], datos_act["compras"], datos_act["ventas"], usuarios_extra=activos)

    OPCION_TODOS = "📋 Todos los usuarios (reporte general)"
    opcion = st.selectbox("Usuario", [OPCION_TODOS] + list(grupos.keys()), key="act_usuario")
    elegidos = list(grupos.items()) if opcion == OPCION_TODOS else [(opcion, grupos[opcion])]
    reps = [reportes.construir_reporte_usuario(n, d) for n, d in elegidos]

    n_mov = sum(len(f) for _n, d in elegidos for f in d.values())
    k1, k2, k3 = st.columns(3)
    k1.metric("Movimientos", n_mov)
    k2.metric("Egresos (pagos + compras)", fmt_money(sum(r["total_egresos"] for r in reps)))
    k3.metric("Ingresos (ventas)", fmt_money(sum(r["total_ingresos"] for r in reps)))

    if n_mov == 0:
        st.info("No hay pagos, compras ni ventas registrados en ese periodo para la selección.")
    else:
        cfg_bs = {c: st.column_config.NumberColumn(format="Bs %.2f")
                  for c in ("Pagos realizados", "Compras realizadas", "Ventas realizadas",
                            "Egresos", "Ingresos", "Monto")}
        if len(reps) > 1:
            with st.container(border=True):
                st.markdown("**Resumen por usuario**")
                st.dataframe(pd.DataFrame([{
                    "Usuario": r["usuario"],
                    "Pagos realizados": r["categorias"]["pagos_generales"]["total"],
                    "Compras realizadas": r["categorias"]["compras"]["total"],
                    "Ventas realizadas": r["categorias"]["ventas"]["total"],
                    "Egresos": r["total_egresos"], "Ingresos": r["total_ingresos"],
                } for r in reps]), use_container_width=True, hide_index=True, column_config=cfg_bs)

        for r in reps:
            with st.expander(f'{r["usuario"]} — egresos {fmt_money(r["total_egresos"])} · '
                             f'ingresos {fmt_money(r["total_ingresos"])}', expanded=(len(reps) == 1)):
                for clave, titulo, _tipo in reportes.CATEGORIAS:
                    cat = r["categorias"][clave]
                    st.markdown(f"**{titulo}** ({len(cat['filas'])})")
                    if cat["filas"]:
                        st.dataframe(pd.DataFrame(cat["filas"]), use_container_width=True, hide_index=True,
                                     column_config=cfg_bs)
                        st.caption(f"Subtotal: {fmt_money(cat['total'])}")
                    else:
                        st.caption("Sin registros en este periodo.")

        # ---------- Descargas ----------
        etiqueta_archivo = "general" if opcion == OPCION_TODOS else \
            "".join(c if c.isalnum() else "_" for c in opcion).strip("_")
        base_archivo = f"actividad_{etiqueta_archivo}_{act_desde:%Y-%m-%d}_{act_hasta:%Y-%m-%d}"
        txt_desde, txt_hasta = f"{act_desde:%d/%m/%Y}", f"{act_hasta:%d/%m/%Y}"
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "📊 Descargar Excel", data=_actividad_excel_cache(reps, txt_desde, txt_hasta, nombre_emisor),
                file_name=f"{base_archivo}.xlsx", key="act_xlsx", use_container_width=True,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with d2:
            st.download_button(
                "📄 Descargar PDF", data=_actividad_pdf_cache(reps, txt_desde, txt_hasta, nombre_emisor),
                file_name=f"{base_archivo}.pdf", mime="application/pdf", key="act_pdf", use_container_width=True)

# ==================================================================
# PÁGINA: CUADRE DE TESORERÍA (libro de movimientos y cuadre de fin de mes)
# ==================================================================
elif pagina == "💰 Cuadre de tesorería":
    st.title("💰 Cuadre de tesorería")
    st.caption(
        "Todos los pagos, compras (egresos) y ventas (ingresos) del periodo, con los totales para cuadrar la caja. "
        "Los montos no se descuentan según el Estado (devolución / entrega): ese dato se muestra aparte."
    )
    hoy_cd = recibo.hoy_bolivia()
    nombre_emisor_cd = usuario_actual.get("nombre") or usuario_actual.get("username")

    modo_cd = st.radio("Periodo", ["Mes completo", "Rango de fechas"], horizontal=True, key="cd_modo")
    if modo_cd == "Mes completo":
        cm1, cm2 = st.columns(2)
        with cm1:
            mes_cd = st.selectbox("Mes", MESES, index=hoy_cd.month - 1, key="cd_mes")
        with cm2:
            anio_cd = int(st.number_input("Año", min_value=2000, max_value=2100, value=hoy_cd.year, step=1, key="cd_anio"))
        mes_num_cd = MESES.index(mes_cd) + 1
        cd_desde = date(anio_cd, mes_num_cd, 1)
        cd_hasta = date(anio_cd, mes_num_cd, calendar.monthrange(anio_cd, mes_num_cd)[1])
    else:
        cr1, cr2 = st.columns(2)
        with cr1:
            cd_desde = st.date_input("Desde", value=hoy_cd.replace(day=1), format="DD/MM/YYYY", key="cd_desde")
        with cr2:
            cd_hasta = st.date_input("Hasta", value=hoy_cd, format="DD/MM/YYYY", key="cd_hasta")
        if not cd_desde or not cd_hasta:
            st.warning("Elige las dos fechas.")
            st.stop()
        if cd_desde > cd_hasta:
            st.error("La fecha «Desde» no puede ser posterior a «Hasta».")
            st.stop()

    st.markdown("**Cuadre de efectivo** (opcional)")
    ce1, ce2 = st.columns(2)
    with ce1:
        saldo_inicial_cd = st.number_input(
            "Saldo inicial en efectivo (Bs)", min_value=0.0, step=10.0, value=0.0, key=f"cd_ini_{cd_desde}_{cd_hasta}",
            help="Efectivo con el que se abrió la caja al inicio del periodo (normalmente el efectivo contado al cierre del mes anterior).")
    with ce2:
        contado_cd = st.number_input(
            "Efectivo contado en caja (Bs)", min_value=0.0, step=10.0, value=None, placeholder="Escribe lo que contaste",
            key=f"cd_contado_{cd_desde}_{cd_hasta}", help="Lo que realmente hay en caja hoy. Se compara con el efectivo esperado.")

    datos_cd = cargar_actividad(str(cd_desde), str(cd_hasta))
    movs_cd = cuadre.construir_movimientos(datos_cd["pagos_generales"], datos_cd["compras"], datos_cd["ventas"])
    q = cuadre.construir_cuadre(movs_cd, cd_desde, cd_hasta, saldo_inicial=saldo_inicial_cd, efectivo_contado=contado_cd)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Movimientos", q["n_mov"])
    k2.metric("Ingresos (ventas)", fmt_money(q["ingresos"]))
    k3.metric("Egresos (pagos + compras)", fmt_money(q["egresos"]))
    k4.metric("Resultado", fmt_money(q["resultado"]))

    if q["n_mov"] == 0:
        st.info("No hay pagos, compras ni ventas registrados en ese periodo.")
        st.stop()

    ef = q["efectivo"]
    with st.container(border=True):
        st.markdown("**💵 Cuadre de efectivo en caja**")
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Saldo inicial", fmt_money(ef["saldo_inicial"]))
        e2.metric("+ Ingresos en efectivo", fmt_money(ef["ingresos"]))
        e3.metric("− Egresos en efectivo", fmt_money(ef["egresos"]))
        e4.metric("= Efectivo esperado", fmt_money(ef["esperado"]))
        if ef["diferencia"] is None:
            st.caption("Escribe el efectivo contado en caja para ver si cuadra.")
        elif abs(ef["diferencia"]) < 0.005:
            st.success(f"✅ Cuadra: el efectivo contado ({fmt_money(ef['contado'])}) coincide con lo esperado.")
        elif ef["diferencia"] > 0:
            st.warning(f"⚠️ Sobran {fmt_money(ef['diferencia'])}: hay más efectivo del esperado "
                       f"(contado {fmt_money(ef['contado'])} vs. esperado {fmt_money(ef['esperado'])}).")
        else:
            st.error(f"⚠️ Faltan {fmt_money(-ef['diferencia'])}: hay menos efectivo del esperado "
                     f"(contado {fmt_money(ef['contado'])} vs. esperado {fmt_money(ef['esperado'])}).")
        if any(m["metodo"] == cuadre.SIN_METODO for m in q["por_metodo"]):
            st.caption("ℹ️ Hay movimientos sin método de pago: no se incluyen en el efectivo. Revísalos en la pestaña «Por revisar».")

    pe = q["pendientes"]
    if any(pe.values()):
        st.caption(f"Según el Estado de cada registro — egresos con devolución pendiente: {fmt_money(pe['devolucion_pendiente'])} · "
                   f"devolución realizada: {fmt_money(pe['devolucion_realizada'])} · ingresos con entrega pendiente: "
                   f"{fmt_money(pe['entrega_pendiente'])} · entrega realizada: {fmt_money(pe['entrega_realizada'])}.")

    cfg_cd = {c: st.column_config.NumberColumn(format="Bs %.2f")
              for c in ("Ingreso", "Egreso", "Acumulado", "Ingresos", "Egresos", "Neto", "Neto del día", "Total", "Monto")}
    t_libro, t_dia, t_metodo, t_cat, t_ven, t_pag, t_com, t_rev = st.tabs([
        "📒 Libro diario", "📅 Por día", "💳 Por método", "🗂️ Por categoría", "💸 Ventas", "💳 Pagos", "🧾 Compras",
        f"🔎 Por revisar ({len(q['revisar'])})"])
    with t_libro:
        st.dataframe(pd.DataFrame([{
            "Fecha": m["fecha_txt"], "Registro": m["origen"], "Categoría / Concepto": m["categoria"],
            "Descripción": m["detalle"], "Persona / Empresa": m["persona"], "Método": m["metodo_original"] or "—",
            "Estado": reportes._estado_txt(m["estado"]), "Devolución a": m["devolucion_a"],
            "Ingreso": m["ingreso"], "Egreso": m["egreso"],
            "Acumulado": m["acumulado"]} for m in q["libro"]]),
            use_container_width=True, hide_index=True, column_config=cfg_cd)
        st.caption("«Persona / Empresa» es el comprador (ventas), el beneficiario (pagos) o el proveedor (compras). "
                   "«Devolución a» indica a quién se le devolvió el dinero (un usuario o «Tercero: nombre») cuando el Estado dice que la devolución ya se realizó. "
                   "«Acumulado» es el resultado acumulado del periodo (ingresos − egresos).")
    with t_dia:
        st.dataframe(pd.DataFrame([{"Fecha": d["fecha_txt"], "Movimientos": d["n"], "Ingresos": d["ingresos"],
                                    "Egresos": d["egresos"], "Neto del día": d["neto"], "Acumulado": d["acumulado"]}
                                   for d in q["por_dia"]]),
                     use_container_width=True, hide_index=True, column_config=cfg_cd)
    with t_metodo:
        st.dataframe(pd.DataFrame([{"Método": m["metodo"], "Movimientos": m["n"], "Ingresos": m["ingresos"],
                                    "Egresos": m["egresos"], "Neto": m["neto"]} for m in q["por_metodo"]]),
                     use_container_width=True, hide_index=True, column_config=cfg_cd)
        st.caption("Sirve para cuadrar por separado el efectivo, los QR y las transferencias con el banco.")
    with t_cat:
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**Egresos por categoría**")
            st.dataframe(pd.DataFrame([{"Categoría": c["categoria"], "Movimientos": c["n"], "Total": c["total"]}
                                       for c in q["categorias_egreso"]]),
                         use_container_width=True, hide_index=True, column_config=cfg_cd)
        with cc2:
            st.markdown("**Ingresos por concepto**")
            st.dataframe(pd.DataFrame([{"Concepto": c["categoria"], "Movimientos": c["n"], "Total": c["total"]}
                                       for c in q["categorias_ingreso"]]),
                         use_container_width=True, hide_index=True, column_config=cfg_cd)
    for pestana, origen, vacio in ((t_ven, "Venta", "ventas"), (t_pag, "Pago", "pagos"), (t_com, "Compra", "compras")):
        with pestana:
            filas_o = cuadre.filas_por_origen(q, origen)
            if filas_o:
                st.dataframe(pd.DataFrame(filas_o), use_container_width=True, hide_index=True, column_config=cfg_cd)
            else:
                st.caption(f"Sin {vacio} en este periodo.")
    with t_rev:
        if q["revisar"]:
            st.caption("Sugerencias para revisar antes de cerrar el mes (no son errores obligatorios).")
            st.dataframe(pd.DataFrame(q["revisar"]), use_container_width=True, hide_index=True, column_config=cfg_cd)
        else:
            st.success("Nada por revisar: todos los registros tienen método y comprobante.")

    base_cd = f"cuadre_tesoreria_{cd_desde:%Y-%m-%d}_{cd_hasta:%Y-%m-%d}"
    dd1, dd2 = st.columns(2)
    with dd1:
        st.download_button("📊 Descargar Excel", data=_cuadre_excel_cache(q, nombre_emisor_cd), file_name=f"{base_cd}.xlsx",
                           key="cd_xlsx", use_container_width=True,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with dd2:
        st.download_button("📄 Descargar PDF", data=_cuadre_pdf_cache(q, nombre_emisor_cd), file_name=f"{base_cd}.pdf",
                           mime="application/pdf", key="cd_pdf", use_container_width=True)

# ==================================================================
# PÁGINA: RENDICIÓN DE ALQUILERES (qué se cobró, qué se pagó y qué se debe, por mes o rango de fechas)
# ==================================================================
elif pagina == "📋 Rendición de alquileres":
    st.title("📋 Rendición de alquileres")
    st.caption(
        "El dinero que ingresó en el periodo: cada pago cuenta en la fecha en que se recibió, sin importar a qué mes corresponda "
        "(un pago hecho en julio por el alquiler de octubre aparece en julio). Sirve para rendir cuentas del dinero recolectado."
    )
    hoy_rd = recibo.hoy_bolivia()

    modo_rd = st.radio("Periodo", ["Mes completo", "Rango de fechas"], horizontal=True, key="rd_modo")
    if modo_rd == "Mes completo":
        rm1, rm2 = st.columns(2)
        with rm1:
            mes_rd = st.selectbox("Mes", MESES, index=hoy_rd.month - 1, key="rd_mes")
        with rm2:
            anio_rd = int(st.number_input("Año", min_value=2000, max_value=2100, value=hoy_rd.year, step=1, key="rd_anio"))
        mes_num_rd = MESES.index(mes_rd) + 1
        rd_desde = date(anio_rd, mes_num_rd, 1)
        rd_hasta = date(anio_rd, mes_num_rd, calendar.monthrange(anio_rd, mes_num_rd)[1])
    else:
        rr1, rr2 = st.columns(2)
        with rr1:
            rd_desde = st.date_input("Desde", value=hoy_rd.replace(day=1), format="DD/MM/YYYY", key="rd_desde")
        with rr2:
            rd_hasta = st.date_input("Hasta", value=hoy_rd, format="DD/MM/YYYY", key="rd_hasta")
        if not rd_desde or not rd_hasta:
            st.warning("Elige las dos fechas.")
            st.stop()
        if rd_desde > rd_hasta:
            st.error("La fecha «Desde» no puede ser posterior a «Hasta».")
            st.stop()
        if len(rendicion.meses_en_rango(rd_desde, rd_hasta)) > rendicion.MAX_MESES:
            st.error(f"El rango no puede pasar de {rendicion.MAX_MESES} meses.")
            st.stop()
    st.markdown(f"**Dinero recibido del {rd_desde:%d/%m/%Y} al {rd_hasta:%d/%m/%Y}** (ambas fechas incluidas)")

    filtro_rd = st.radio("Apartamentos a mostrar", ["Todos", "Solo con cobros en el periodo", "Solo con deuda pendiente"],
                         horizontal=True, key="rd_filtro")

    periodos_rd = {t: cargar_periodos_abiertos(t) for t in ("alquiler", "electricidad", "agua")}
    n_ilegibles_rd = sum(moras.contar_ilegibles(p) for p in periodos_rd.values())
    if n_ilegibles_rd:
        st.warning(f"⚠️ Hay **{n_ilegibles_rd}** periodo(s) de pagos con un mes o año que la app no reconoce. Sus pagos SÍ se cuentan "
                   "como dinero recibido (en «Mes que paga» aparece «—»), pero su deuda no entra en «Deuda pendiente». "
                   "Corrígelos en Supabase: el mes debe ser uno de Enero … Diciembre.")
    try:                       # ex inquilinos: si pagan después, ese cobro también es dinero recibido
        historial_rd = cargar_historial()
        cerrados_rd = {t: cargar_periodos_cerrados(t) for t in ("alquiler", "electricidad", "agua")}
    except Exception as e:
        historial_rd, cerrados_rd = [], {}
        st.warning(texto_error_historial("No se pudo leer el historial de ex inquilinos: este reporte NO incluye sus pagos ni su deuda", e))
    rd = rendicion.construir_rendicion(
        cargar_apartamentos(), periodos_rd["alquiler"], periodos_rd["electricidad"], periodos_rd["agua"], rd_desde, rd_hasta, hoy_rd,
        solo_con_deuda=filtro_rd == "Solo con deuda pendiente", solo_con_cobros=filtro_rd == "Solo con cobros en el periodo",
        cerrados=cerrados_rd, historial=historial_rd)

    td = rd["totales"]
    rk1, rk2, rk3, rk4, rk5 = st.columns(5)
    rk1.metric("Total cobrado", fmt_money(td["total"]), help=f'{rd["n_pagos"]} pago(s) recibido(s) en el periodo')
    rk2.metric("Alquiler", fmt_money(td["alquiler"]))
    rk3.metric("Luz", fmt_money(td["luz"]))
    rk4.metric("Agua", fmt_money(td["agua"]))
    rk5.metric("Deuda pendiente", fmt_money(td["deuda"]),
               help=f'Lo que aún falta pagar de {rendicion.texto_meses(rd)} (a hoy). {rd["con_deuda"]} de {rd["n_apartamentos"]} apartamentos con deuda.')

    if rd["n_ex_inquilinos"]:
        st.caption(f"👥 Incluye {fmt_money(rd['cobrado_ex'])} cobrados a ex inquilinos ({rd['n_ex_inquilinos']}), marcados «ex inquilino». "
                   f"Lo que todavía deben suma {fmt_money(rd['deuda_ex'])}.")

    if not rd["filas"]:
        st.info("No hay apartamentos para mostrar en este periodo.")
        st.stop()

    cfg_rd = {c: st.column_config.NumberColumn(format="Bs %.2f") for c in (
        "Alquiler cobrado", "Luz cobrada", "Agua cobrada", "Total cobrado", "Deuda pendiente", "Alquiler a cobrar", "Alquiler pagado",
        "Alquiler deuda", "Luz a cobrar", "Luz pagado", "Luz deuda", "Agua a cobrar", "Agua pagado", "Agua deuda", "Deuda total", "Monto")}
    t_res, t_mov, t_det = st.tabs(["📋 Resumen por apartamento", f"💵 Pagos recibidos ({rd['n_pagos']})", "🔎 Deuda por servicio"])
    with t_res:
        filas_rd = [{enc: f[clave] for clave, enc, _t in rendicion.COLUMNAS_RESUMEN} for f in rd["filas"]]
        filas_rd.append({enc: ("TOTAL" if clave == "apartamento" else td.get(clave, "")) for clave, enc, _t in rendicion.COLUMNAS_RESUMEN})
        st.dataframe(pd.DataFrame(filas_rd), use_container_width=True, hide_index=True, column_config=cfg_rd)
        st.caption("«Cobrado» es el dinero recibido entre las dos fechas. «Deuda pendiente» es lo que aún falta pagar de "
                   f"{rendicion.texto_meses(rd)} (a hoy), sin importar cuándo se pagó. Cada apartamento muestra a su inquilino actual; las filas "
                   "«Ex inquilino» son inquilinos que ya salieron (su deuda es todo lo que aún deben).")
    with t_mov:
        if rd["movimientos"]:
            st.dataframe(pd.DataFrame([{enc: m[clave] for clave, enc, _t in rendicion.COLUMNAS_MOVIMIENTOS} for m in rd["movimientos"]]),
                         use_container_width=True, hide_index=True, column_config=cfg_rd)
            st.caption("Por concepto: " + " · ".join(f"{c['concepto']} {fmt_money(c['total'])}" for c in rd["pagos_por_concepto"]) + ".")
        else:
            st.info("No se recibió ningún pago en este periodo.")
    with t_det:
        st.dataframe(pd.DataFrame([{enc: f[clave] for clave, enc, _t in rendicion.COLUMNAS_DETALLE} for f in rd["filas"]]),
                     use_container_width=True, hide_index=True, column_config=cfg_rd)
        st.caption(f"Cobros y deuda de los meses del periodo ({rendicion.texto_meses(rd)}). «Pagado» incluye los pagos de esos meses "
                   "hechos en cualquier fecha, por eso puede no coincidir con lo cobrado en el periodo.")

    base_rd = f"rendicion_alquileres_{rd_desde:%Y-%m-%d}_{rd_hasta:%Y-%m-%d}"
    nombre_emisor_rd = usuario_actual.get("nombre") or usuario_actual.get("username")
    rdl1, rdl2 = st.columns(2)
    with rdl1:
        st.download_button("📊 Descargar Excel", data=_rendicion_excel_cache(rd, nombre_emisor_rd), file_name=f"{base_rd}.xlsx",
                           key="rd_xlsx", use_container_width=True,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with rdl2:
        st.download_button("📄 Descargar PDF", data=_rendicion_pdf_cache(rd, nombre_emisor_rd), file_name=f"{base_rd}.pdf",
                           mime="application/pdf", key="rd_pdf", use_container_width=True)

# ==================================================================
# PÁGINA: INVENTARIO (materiales, repuestos y suministros: entradas, salidas y Kardex)
# ==================================================================
elif pagina == "📦 Inventario":
    st.title("📦 Inventario")
    st.caption("Materiales, repuestos y suministros del edificio: entradas, salidas y Kardex valorizado a costo promedio ponderado.")
    try:
        articulos_inv = cargar_inventario_articulos()
        movimientos_inv = cargar_inventario_movimientos()
    except Exception as e:
        st.error(texto_error_inventario("No se pudo leer el inventario", e))
        st.stop()

    ex_inv = inventario.existencias(articulos_inv, movimientos_inv)
    estado_art = {f["id"]: f for f in ex_inv["filas"]}
    nombres_orden = [f["id"] for f in ex_inv["filas"]]
    articulos_por_id = {a["id"]: a for a in articulos_inv}
    activos_inv = [articulos_por_id[i] for i in nombres_orden if articulos_por_id[i].get("activo", True) is not False]
    todos_inv = [articulos_por_id[i] for i in nombres_orden]
    movs_de = lambda art_id: [m for m in movimientos_inv if m["articulo_id"] == art_id]
    hoy_inv = recibo.hoy_bolivia()
    emisor_inv = usuario_actual.get("nombre") or usuario_actual.get("username")
    categorias_inv = inventario.CATEGORIAS + sorted({a["categoria"] for a in articulos_inv if a.get("categoria")} - set(inventario.CATEGORIAS))
    cant = inventario.formato_cantidad
    if st.session_state.get("inv_msg"):
        st.success(st.session_state.pop("inv_msg"))

    t_exist, t_mov, t_kardex, t_hist, t_art = st.tabs(
        ["📊 Existencias", "➕ Registrar movimiento", "📒 Kardex", "🕘 Movimientos", "🧰 Artículos"])

    # ------------------------------------------------------------ Existencias
    with t_exist:
        ik1, ik2, ik3, ik4 = st.columns(4)
        ik1.metric("Artículos activos", ex_inv["n_activos"])
        ik2.metric("Valor del inventario", fmt_money(ex_inv["valor_total"]))
        ik3.metric("Stock bajo", ex_inv["n_bajo"], help="Artículos cuyo stock llegó al mínimo definido")
        ik4.metric("Sin stock", ex_inv["n_sin_stock"])
        if not ex_inv["filas"]:
            st.info("Todavía no hay artículos. Regístralos en la pestaña **🧰 Artículos** y luego sus entradas en **➕ Registrar movimiento**.")
        else:
            if1, if2, if3 = st.columns([2, 1, 1])
            with if1:
                texto_inv = st.text_input("Buscar", placeholder="código, nombre, categoría o ubicación", key="inv_buscar")
            with if2:
                cat_inv = st.selectbox("Categoría", ["Todas"] + categorias_inv, key="inv_cat")
            with if3:
                solo_alertas = st.checkbox("Solo stock bajo o sin stock", key="inv_alertas")
            vista_inv = inventario.filtrar_existencias(ex_inv["filas"], texto_inv, cat_inv, solo_alertas)
            iconos = {"OK": "✅ OK", "Stock bajo": "⚠️ Stock bajo", "Sin stock": "🔴 Sin stock"}
            if vista_inv:
                st.dataframe(pd.DataFrame([{
                    "Código": f["codigo"], "Artículo": f["nombre"], "Categoría": f["categoria"], "Unidad": f["unidad"],
                    "Ubicación": f["ubicacion"], "Stock": f["cantidad"], "Mínimo": f["stock_minimo"],
                    "Costo promedio": f["costo_promedio"], "Valor": f["valor"], "Estado": iconos[f["estado"]]} for f in vista_inv]),
                    use_container_width=True, hide_index=True, column_config={
                        "Costo promedio": st.column_config.NumberColumn(format="Bs %.1f"), "Valor": st.column_config.NumberColumn(format="Bs %.2f")})
                st.caption(f"Valor de lo que se muestra: {fmt_money(sum(f['valor'] for f in vista_inv))}. Costo promedio ponderado.")
                ie1, ie2 = st.columns(2)
                with ie1:
                    st.download_button("📊 Descargar Excel", data=_inv_excel_existencias(vista_inv, sum(f["valor"] for f in vista_inv), hoy_inv, emisor_inv),
                                       file_name=f"existencias_inventario_{hoy_inv:%Y-%m-%d}.xlsx", key="inv_xlsx_ex", use_container_width=True,
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                with ie2:
                    resumen_vista = {**ex_inv, "valor_total": round(sum(f["valor"] for f in vista_inv), 2),
                                     "n_activos": sum(1 for f in vista_inv if f["activo"]),
                                     "n_bajo": sum(1 for f in vista_inv if f["estado"] == "Stock bajo"),
                                     "n_sin_stock": sum(1 for f in vista_inv if f["estado"] == "Sin stock")}
                    st.download_button("📄 Descargar PDF", data=_inv_pdf_existencias(vista_inv, resumen_vista, hoy_inv, emisor_inv),
                                       file_name=f"existencias_inventario_{hoy_inv:%Y-%m-%d}.pdf", mime="application/pdf", key="inv_pdf_ex",
                                       use_container_width=True)
            else:
                st.info("Ningún artículo coincide con el filtro.")

    # ------------------------------------------------------------ Registrar movimiento
    with t_mov:
        if not activos_inv:
            st.info("Primero registra al menos un artículo en la pestaña **🧰 Artículos**.")
        else:
            n_form = st.session_state.get("inv_n_form", 0)          # cambia al guardar: así el formulario se limpia
            idx_art = st.selectbox(
                "Artículo", range(len(activos_inv)), key=f"inv_art_{n_form}",
                format_func=lambda i: f'{activos_inv[i]["codigo"]} — {activos_inv[i]["nombre"]} '
                                      f'(stock: {cant(estado_art[activos_inv[i]["id"]]["cantidad"])} {activos_inv[i]["unidad"]})')
            art = activos_inv[idx_art]
            stock_art = estado_art[art["id"]]["cantidad"]
            tipo_inv = st.radio("Tipo de movimiento", ["Entrada", "Salida"], horizontal=True, key=f"inv_tipo_{n_form}",
                                help="Entrada: llega material (compra, donación…). Salida: se usa o se pierde material.")
            im1, im2, im3 = st.columns(3)
            with im1:
                fecha_inv = st.date_input("Fecha", value=hoy_inv, format="DD/MM/YYYY", key=f"inv_fecha_{n_form}")
            with im2:
                cantidad_inv = st.number_input(f"Cantidad ({art['unidad']})", min_value=0.0, step=1.0, format="%.1f", value=0.0,
                                               key=f"inv_cant_{n_form}")
            with im3:
                costo_inv = (st.number_input("Costo unitario (Bs)", min_value=0.0, step=0.5, format="%.1f", value=0.0, key=f"inv_costo_{n_form}",
                                             help="Lo que costó cada unidad, con 1 decimal (ej. 3.5). Pon 0 si fue una donación.")
                             if tipo_inv == "Entrada" else None)
                if tipo_inv == "Salida":
                    st.caption(f"Se valora al costo promedio actual: Bs {inventario_reportes._costo(estado_art[art['id']]['costo_promedio'])}")
            motivo_inv = st.selectbox("Motivo", inventario.MOTIVOS[tipo_inv], key=f"inv_motivo_{tipo_inv}_{n_form}")
            destino_inv, apartamento_inv = None, None
            if tipo_inv == "Salida":
                id1, id2 = st.columns(2)
                with id1:
                    if motivo_inv == inventario.MOTIVO_USO_APARTAMENTO:
                        destino_tipo = inventario.DESTINO_APARTAMENTO          # el motivo ya dice que es un apartamento
                        st.caption("Destino: un apartamento (elige cuál)")
                    else:
                        destino_tipo = st.selectbox("Destino", inventario.DESTINOS, key=f"inv_destino_{n_form}")
                if destino_tipo == inventario.DESTINO_APARTAMENTO:
                    apts_inv = cargar_apartamentos()
                    with id2:
                        if apts_inv:
                            j_apt = st.selectbox("Apartamento", range(len(apts_inv)), key=f"inv_apt_{n_form}",
                                                 format_func=lambda j: f'{apts_inv[j]["codigo"]} — {apts_inv[j].get("inquilino_nombre") or "vacío"}')
                            apartamento_inv, destino_inv = apts_inv[j_apt]["id"], apts_inv[j_apt]["codigo"]
                        else:
                            st.warning("No hay apartamentos registrados.")
                else:
                    destino_inv = destino_tipo
            ido1, ido2 = st.columns(2)
            with ido1:
                documento_inv = st.text_input("N° de documento (factura, vale, recibo)", key=f"inv_doc_{n_form}")
            with ido2:
                obs_inv = st.text_input("Observación (opcional)", key=f"inv_obs_{n_form}")
            if cantidad_inv > 0:
                if tipo_inv == "Entrada":
                    st.caption(f"Stock: {cant(stock_art)} → {cant(stock_art + cantidad_inv)} {art['unidad']} · Valor de la entrada: "
                               f"{fmt_money(round(cantidad_inv * (costo_inv or 0), 2))}")
                else:
                    st.caption(f"Stock: {cant(stock_art)} → {cant(stock_art - cantidad_inv)} {art['unidad']}")
            if st.button("💾 Registrar movimiento", key=f"inv_guardar_{n_form}"):
                errores_inv = inventario.validar_movimiento(tipo_inv, cantidad_inv, costo_inv, fecha_inv, motivo_inv, destino_inv, apartamento_inv, hoy_inv)
                nuevo_inv = inventario.armar_movimiento(art["id"], tipo_inv, fecha_inv, cantidad_inv, costo_inv, motivo_inv, destino_inv,
                                                        apartamento_inv, documento_inv, obs_inv, emisor_inv)
                if not errores_inv:
                    error_kardex = inventario.validar_en_kardex(movs_de(art["id"]), nuevo_inv, unidad=art["unidad"])
                    if error_kardex:
                        errores_inv.append(error_kardex)
                for e in errores_inv:
                    st.error(e)
                if not errores_inv:
                    try:
                        db.crear_inventario_movimiento(nuevo_inv)
                        limpiar_cache()
                        st.session_state["inv_n_form"] = n_form + 1
                        st.session_state["inv_msg"] = (f"{tipo_inv} registrada: {cant(cantidad_inv)} {art['unidad']} de {art['nombre']} "
                                                       f"({motivo_inv}).")
                        st.rerun()
                    except Exception as e:
                        st.error(texto_error_inventario("Error al guardar", e))

    # ------------------------------------------------------------ Kardex
    with t_kardex:
        if not todos_inv:
            st.info("Todavía no hay artículos.")
        else:
            ik_art = st.selectbox("Artículo", range(len(todos_inv)), key="inv_k_art",
                                  format_func=lambda i: f'{todos_inv[i]["codigo"]} — {todos_inv[i]["nombre"]}'
                                                        + ("" if todos_inv[i].get("activo", True) is not False else " (inactivo)"))
            art_k = todos_inv[ik_art]
            k_todo = st.checkbox("Todo el historial", value=True, key="inv_k_todo")
            k_desde = k_hasta = None
            if not k_todo:
                kc1, kc2 = st.columns(2)
                with kc1:
                    k_desde = st.date_input("Desde", value=hoy_inv.replace(day=1), format="DD/MM/YYYY", key="inv_k_desde")
                with kc2:
                    k_hasta = st.date_input("Hasta", value=hoy_inv, format="DD/MM/YYYY", key="inv_k_hasta")
                if not k_desde or not k_hasta or k_desde > k_hasta:
                    st.error("Revisa las fechas: «Desde» no puede ser posterior a «Hasta».")
                    st.stop()
            kp = inventario.kardex_periodo(movs_de(art_k["id"]), k_desde, k_hasta)
            sf = kp["saldo_final"]
            kk1, kk2, kk3, kk4, kk5 = st.columns(5)
            kk1.metric("Saldo", f"{cant(sf['cantidad'])} {art_k['unidad']}")
            kk2.metric("Costo promedio", f"Bs {inventario_reportes._costo(sf['costo'])}")
            kk3.metric("Valor", fmt_money(sf["valor"]))
            kk4.metric("Entradas", fmt_money(kp["entradas"]["valor"]), help=f"{cant(kp['entradas']['cantidad'])} {art_k['unidad']} en el periodo")
            kk5.metric("Salidas", fmt_money(kp["salidas"]["valor"]), help=f"{cant(kp['salidas']['cantidad'])} {art_k['unidad']} en el periodo")
            if any(f["negativo"] for f in kp["filas"]):
                st.error("⚠️ Este Kardex tiene un saldo negativo (hay más salidas que entradas). Revisa los movimientos del artículo.")
            filas_k = inventario_reportes.filas_kardex(kp)
            if filas_k:
                st.dataframe(pd.DataFrame([{enc: f.get(clave) for clave, enc, _t in inventario_reportes.COLUMNAS_KARDEX} for f in filas_k]),
                             use_container_width=True, hide_index=True, column_config={
                                 **{enc: st.column_config.NumberColumn(format="Bs %.1f") for _c, enc, t in inventario_reportes.COLUMNAS_KARDEX if "costo" in enc.lower()},
                                 **{enc: st.column_config.NumberColumn(format="Bs %.2f") for _c, enc, t in inventario_reportes.COLUMNAS_KARDEX if enc.endswith("valor")}})
                st.caption("Kardex con costo promedio ponderado: cada salida se valora al costo promedio que tenía el artículo ese día. El costo promedio se muestra con 1 decimal, pero el valor se calcula con el promedio exacto.")
            else:
                st.info("Este artículo no tiene movimientos en el periodo.")
            kd1, kd2 = st.columns(2)
            with kd1:
                st.download_button("📊 Descargar Excel", data=_inv_excel_kardex(art_k, kp, k_desde, k_hasta, emisor_inv),
                                   file_name=f"kardex_{art_k['codigo']}.xlsx", key="inv_xlsx_k", use_container_width=True,
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with kd2:
                st.download_button("📄 Descargar PDF", data=_inv_pdf_kardex(art_k, kp, k_desde, k_hasta, emisor_inv),
                                   file_name=f"kardex_{art_k['codigo']}.pdf", mime="application/pdf", key="inv_pdf_k", use_container_width=True)

    # ------------------------------------------------------------ Movimientos (historial)
    with t_hist:
        hc1, hc2, hc3, hc4 = st.columns(4)
        with hc1:
            h_desde = st.date_input("Desde", value=hoy_inv.replace(day=1), format="DD/MM/YYYY", key="inv_h_desde")
        with hc2:
            h_hasta = st.date_input("Hasta", value=hoy_inv, format="DD/MM/YYYY", key="inv_h_hasta")
        with hc3:
            h_tipo = st.selectbox("Tipo", ["Todos"] + inventario.TIPOS, key="inv_h_tipo")
        with hc4:
            h_art = st.selectbox("Artículo", ["Todos"] + [f'{a["codigo"]} — {a["nombre"]}' for a in todos_inv], key="inv_h_art")
        if not h_desde or not h_hasta or h_desde > h_hasta:
            st.error("Revisa las fechas: «Desde» no puede ser posterior a «Hasta».")
            st.stop()
        h_art_id = None if h_art == "Todos" else todos_inv[[f'{a["codigo"]} — {a["nombre"]}' for a in todos_inv].index(h_art)]["id"]
        mv_inv = inventario.movimientos_valorizados(articulos_inv, movimientos_inv, h_desde, h_hasta, h_art_id, h_tipo)
        hk1, hk2, hk3 = st.columns(3)
        hk1.metric("Entradas", fmt_money(mv_inv["entradas_valor"]), help=f'{mv_inv["n_entradas"]} movimiento(s)')
        hk2.metric("Salidas", fmt_money(mv_inv["salidas_valor"]), help=f'{mv_inv["n_salidas"]} movimiento(s)')
        hk3.metric("Movimientos", len(mv_inv["filas"]))
        if not mv_inv["filas"]:
            st.info("No hay movimientos con ese filtro.")
        else:
            st.dataframe(pd.DataFrame([{enc: f[clave] for clave, enc, _t in inventario_reportes.COLUMNAS_MOVIMIENTOS} for f in mv_inv["filas"]]),
                         use_container_width=True, hide_index=True, column_config={
                             "Costo unitario (Bs)": st.column_config.NumberColumn(format="Bs %.1f"), "Valor (Bs)": st.column_config.NumberColumn(format="Bs %.2f")})
            st.caption("Las salidas se valoran al costo promedio que tenía el artículo ese día.")
            hd1, hd2 = st.columns(2)
            with hd1:
                st.download_button("📊 Descargar Excel", data=_inv_excel_movimientos(mv_inv, h_desde, h_hasta, emisor_inv),
                                   file_name=f"movimientos_inventario_{h_desde:%Y-%m-%d}_{h_hasta:%Y-%m-%d}.xlsx", key="inv_xlsx_h",
                                   use_container_width=True, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with hd2:
                st.download_button("📄 Descargar PDF", data=_inv_pdf_movimientos(mv_inv, h_desde, h_hasta, emisor_inv),
                                   file_name=f"movimientos_inventario_{h_desde:%Y-%m-%d}_{h_hasta:%Y-%m-%d}.pdf", mime="application/pdf",
                                   key="inv_pdf_h", use_container_width=True)
            with st.expander("✏️ Corregir o eliminar un movimiento"):
                st.caption("Se pueden corregir el documento y la observación. Para cambiar la cantidad, la fecha o el costo hay que eliminar el "
                           "movimiento (solo el Administrador) y registrarlo de nuevo: así el Kardex nunca queda alterado.")
                i_mov = st.selectbox("Movimiento", range(len(mv_inv["filas"])), key="inv_h_sel",
                                     format_func=lambda i: f'{mv_inv["filas"][i]["fecha_txt"]} — {mv_inv["filas"][i]["codigo"]} '
                                                           f'{mv_inv["filas"][i]["articulo"]} — {mv_inv["filas"][i]["tipo"]} '
                                                           f'{cant(mv_inv["filas"][i]["cantidad"])} {mv_inv["filas"][i]["unidad"]}')
                fila_m = mv_inv["filas"][i_mov]
                mov_orig = next(m for m in movimientos_inv if m["id"] == fila_m["id"])
                art_m = articulos_por_id[mov_orig["articulo_id"]]
                with st.form(f'inv_editar_{mov_orig["id"]}'):
                    doc_nuevo = st.text_input("N° de documento", value=mov_orig.get("documento") or "")
                    obs_nueva = st.text_input("Observación", value=mov_orig.get("observacion") or "")
                    guardar_m = st.form_submit_button("💾 Guardar cambios")
                if guardar_m:
                    try:
                        db.actualizar_inventario_movimiento(mov_orig["id"], inventario.armar_edicion(
                            mov_orig.get("destino"), mov_orig.get("apartamento_id"), doc_nuevo, obs_nueva, mov_orig["tipo"]))
                        limpiar_cache()
                        st.success("Movimiento actualizado.")
                        st.rerun()
                    except Exception as e:
                        st.error(texto_error_inventario("Error al actualizar", e))
                if es_admin:
                    confirmar_del = st.checkbox("Confirmo que quiero eliminar este movimiento", key=f'inv_del_conf_{mov_orig["id"]}')
                    if st.button("🗑️ Eliminar movimiento", key=f'inv_del_{mov_orig["id"]}'):
                        error_del = inventario.validar_en_kardex(movs_de(art_m["id"]), excluir_id=mov_orig["id"], unidad=art_m["unidad"])
                        if not confirmar_del:
                            st.error("Marca la casilla de confirmación para eliminar.")
                        elif error_del:
                            st.error(error_del)
                        else:
                            try:
                                db.eliminar_inventario_movimiento(mov_orig["id"])
                                limpiar_cache()
                                st.success("Movimiento eliminado.")
                                st.rerun()
                            except Exception as e:
                                st.error(texto_error_inventario("Error al eliminar", e))

    # ------------------------------------------------------------ Artículos
    with t_art:
        if todos_inv:
            st.dataframe(pd.DataFrame([{
                "Código": f["codigo"], "Artículo": f["nombre"], "Categoría": f["categoria"], "Unidad": f["unidad"], "Ubicación": f["ubicacion"],
                "Stock mínimo": f["stock_minimo"], "Stock": f["cantidad"], "Movimientos": f["n_movimientos"],
                "Activo": "Sí" if f["activo"] else "No"} for f in ex_inv["filas"]]), use_container_width=True, hide_index=True)
        with st.expander("➕ Nuevo artículo", expanded=not todos_inv):
            with st.form("inv_nuevo_articulo", clear_on_submit=True):
                na1, na2 = st.columns(2)
                with na1:
                    n_codigo = st.text_input("Código", value=inventario.siguiente_codigo(articulos_inv),
                                             help="Se sugiere el siguiente libre; puedes cambiarlo (no se puede repetir).")
                with na2:
                    n_nombre = st.text_input("Nombre del artículo", placeholder="Ej. Foco LED 9W")
                na3, na4, na5 = st.columns(3)
                with na3:
                    n_cat = st.selectbox("Categoría", categorias_inv, index=len(inventario.CATEGORIAS) - 1)
                with na4:
                    n_uni = st.selectbox("Unidad de medida", inventario.UNIDADES)
                with na5:
                    n_min = st.number_input("Stock mínimo", min_value=0.0, step=1.0, format="%.1f", value=0.0,
                                            help="Cuando el stock llegue a este número, el artículo se marca como «Stock bajo». 0 = sin alerta.")
                n_ubic = st.text_input("Ubicación (opcional)", placeholder="Ej. Bodega, cuarto de máquinas")
                n_notas = st.text_area("Notas (opcional)", height=70)
                if st.form_submit_button("💾 Guardar artículo"):
                    errores_art = inventario.validar_articulo(n_codigo, n_nombre, n_uni, n_min, articulos_inv)
                    for e in errores_art:
                        st.error(e)
                    if not errores_art:
                        try:
                            db.crear_inventario_articulo(inventario.armar_articulo(n_codigo, n_nombre, n_cat, n_uni, n_min, n_ubic, n_notas,
                                                                                    True, emisor_inv))
                            limpiar_cache()
                            st.session_state["inv_msg"] = f"Artículo «{n_nombre.strip()}» registrado. Ahora registra su entrada inicial en «➕ Registrar movimiento»."
                            st.rerun()
                        except Exception as e:
                            st.error(texto_error_inventario("Error al guardar", e))
        if todos_inv:
            with st.expander("✏️ Editar un artículo"):
                i_art = st.selectbox("Artículo", range(len(todos_inv)), key="inv_e_sel",
                                     format_func=lambda i: f'{todos_inv[i]["codigo"]} — {todos_inv[i]["nombre"]}')
                a_ed = todos_inv[i_art]
                n_movs_ed = estado_art[a_ed["id"]]["n_movimientos"]
                with st.form(f'inv_editar_art_{a_ed["id"]}'):
                    ea1, ea2 = st.columns(2)
                    with ea1:
                        e_codigo = st.text_input("Código", value=a_ed.get("codigo") or "")
                    with ea2:
                        e_nombre = st.text_input("Nombre", value=a_ed.get("nombre") or "")
                    ea3, ea4, ea5 = st.columns(3)
                    with ea3:
                        e_cat = st.selectbox("Categoría", categorias_inv, index=categorias_inv.index(a_ed["categoria"]) if a_ed.get("categoria") in categorias_inv else len(inventario.CATEGORIAS) - 1)
                    with ea4:
                        unidades_ed = inventario.UNIDADES + ([a_ed["unidad"]] if a_ed.get("unidad") not in inventario.UNIDADES else [])
                        e_uni = st.selectbox("Unidad de medida", unidades_ed, index=unidades_ed.index(a_ed["unidad"]) if a_ed.get("unidad") in unidades_ed else 0)
                    with ea5:
                        e_min = st.number_input("Stock mínimo", min_value=0.0, step=1.0, format="%.1f", value=float(a_ed.get("stock_minimo") or 0))
                    e_ubic = st.text_input("Ubicación", value=a_ed.get("ubicacion") or "")
                    e_notas = st.text_area("Notas", value=a_ed.get("notas") or "", height=70)
                    e_activo = st.checkbox("Activo", value=a_ed.get("activo", True) is not False,
                                           help="Un artículo inactivo no aparece al registrar movimientos ni cuenta en el valor del inventario.")
                    guardar_a = st.form_submit_button("💾 Guardar cambios")
                if guardar_a:
                    errores_ed = inventario.validar_articulo(e_codigo, e_nombre, e_uni, e_min, articulos_inv, a_ed["id"])
                    if not e_activo and estado_art[a_ed["id"]]["cantidad"] > 0:
                        st.warning("Este artículo todavía tiene stock; al desactivarlo deja de contar en el valor del inventario.")
                    for e in errores_ed:
                        st.error(e)
                    if not errores_ed:
                        try:
                            db.actualizar_inventario_articulo(a_ed["id"], inventario.armar_articulo(e_codigo, e_nombre, e_cat, e_uni, e_min, e_ubic, e_notas, e_activo))
                            limpiar_cache()
                            st.success("Artículo actualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(texto_error_inventario("Error al actualizar", e))
                if es_admin:
                    if n_movs_ed:
                        st.caption(f"Este artículo tiene {n_movs_ed} movimiento(s), por eso no se puede eliminar: desmarca «Activo» para dejar de usarlo.")
                    else:
                        conf_art = st.checkbox("Confirmo que quiero eliminar este artículo", key=f'inv_delart_conf_{a_ed["id"]}')
                        if st.button("🗑️ Eliminar artículo", key=f'inv_delart_{a_ed["id"]}'):
                            if not conf_art:
                                st.error("Marca la casilla de confirmación para eliminar.")
                            else:
                                try:
                                    db.eliminar_inventario_articulo(a_ed["id"])
                                    limpiar_cache()
                                    st.success("Artículo eliminado.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(texto_error_inventario("Error al eliminar", e))


# ==================================================================
# PÁGINA: CONCILIACIÓN BANCARIA (extracto del banco vs. registros del sistema)
# ==================================================================
elif pagina == "🏦 Conciliación bancaria":
    st.title("🏦 Conciliación bancaria")
    st.caption(
        "Compara el extracto de tu cuenta bancaria con lo registrado en el sistema: qué cobros y pagos coinciden y cuáles no, y por qué "
        "(probablemente no se registraron, se registraron con otro monto o fecha, o fueron en efectivo)."
    )
    if not puede_editar_estado:
        st.error("Esta pantalla es solo para el Administrador y la tesorería, porque muestra el extracto del banco.")
        st.stop()

    archivo_cb = st.file_uploader("Extracto del banco (Excel .xlsx o CSV)", type=["xlsx", "csv", "txt"], key="cb_archivo")
    if archivo_cb is None:
        st.info(
            "Sube el extracto que descargas del banco. Debe tener una columna de **Fecha** y una de **Monto** (negativo = sale dinero), o bien "
            "**Débito** y **Crédito**. Si trae **Nota** (a quién o de quién), **Saldo** y una columna **sin título entre la Nota y el Monto** donde "
            "anotas de qué fue cada movimiento (ej. «Alquiler PP-03 (Ana - Octubre)»), la comparación es mucho más precisa."
        )
        st.caption("🔒 El archivo no se guarda: se lee solo para esta comparación.")
        st.stop()
    contenido_cb = archivo_cb.getvalue()
    firma_cb = f"{archivo_cb.name}_{len(contenido_cb)}"
    try:
        ext_cb = _leer_extracto_cache(contenido_cb, archivo_cb.name, None)
    except extracto.ErrorExtracto as e:
        st.error(str(e))
        st.stop()

    campos_cb = ["fecha", "monto", "debito", "credito", "contraparte", "detalle", "saldo", "hora", "nro", "transaccion"]
    with st.expander("🔧 Columnas del extracto (revisa que estén bien detectadas)", expanded=bool(ext_cb["faltan"])):
        if ext_cb["faltan"]:
            st.warning("No pude identificar todas las columnas obligatorias. Elígelas aquí (fecha y monto, o débito y crédito).")
        opciones_cb = [-1] + list(range(len(ext_cb["encabezados"])))
        nombre_col_cb = lambda i: "(ninguna)" if i < 0 else f'{openpyxl.utils.get_column_letter(i + 1)} — {ext_cb["encabezados"][i] or "(sin título)"}'
        mapeo_cb, columnas_ui = {}, st.columns(2)
        for i_cb, campo_cb in enumerate(campos_cb):
            with columnas_ui[i_cb % 2]:
                elegido_cb = st.selectbox(extracto.NOMBRES_CAMPOS[campo_cb], opciones_cb, index=opciones_cb.index(ext_cb["columnas"].get(campo_cb, -1)),
                                          format_func=nombre_col_cb, key=f"cb_col_{campo_cb}_{firma_cb}")
            if elegido_cb >= 0:
                mapeo_cb[campo_cb] = elegido_cb
        if mapeo_cb != ext_cb["columnas"]:
            try:
                ext_cb = _leer_extracto_cache(contenido_cb, archivo_cb.name, tuple(sorted(mapeo_cb.items())))
            except extracto.ErrorExtracto as e:
                st.error(str(e))
                st.stop()
    if ext_cb["faltan"] or not ext_cb["lineas"]:
        st.error("Elige al menos la columna de fecha y la de monto (o las de débito y crédito) para continuar.")
        st.stop()

    # ---------------- 1. Lo que se leyó ----------------
    st.subheader("1. Lo que leí del extracto")
    ck1, ck2, ck3, ck4, ck5 = st.columns(5)
    ck1.metric("Movimientos", len(ext_cb["lineas"]))
    ck2.metric("Créditos (entra)", fmt_money(ext_cb["total_creditos"]))
    ck3.metric("Débitos (sale)", fmt_money(ext_cb["total_debitos"]))
    ck4.metric("Periodo", f'{ext_cb["desde"]:%d/%m} al {ext_cb["hasta"]:%d/%m/%Y}')
    ck5.metric("Saldo final", fmt_money(ext_cb["saldo_final"]) if ext_cb["saldo_final"] is not None else "—")
    for aviso_cb in ext_cb["avisos"]:
        st.caption(f"ℹ️ {aviso_cb}")
    if ext_cb["problemas_saldo"]:
        st.warning(f"⚠️ El saldo del extracto no cuadra en {len(ext_cb['problemas_saldo'])} línea(s): puede faltar un movimiento, haber uno repetido o "
                   "estar mal leído. Revisa antes de confiar en la comparación.")
        st.dataframe(pd.DataFrame([{"Fila del archivo": p["fila"], "Fecha": p["fecha"], "Monto": p["monto"], "Saldo esperado": p["saldo_esperado"],
                                    "Saldo del extracto": p["saldo_extracto"], "Diferencia": p["diferencia"]} for p in ext_cb["problemas_saldo"]]),
                     use_container_width=True, hide_index=True)
    elif ext_cb["saldo_final"] is not None:
        st.success("✅ El saldo del extracto es coherente (saldo anterior + monto = saldo): no faltan ni sobran movimientos.")
    else:
        st.caption("El extracto no trae columna de saldo, así que no se pudo controlar que esté completo.")
    with st.expander("Ver los movimientos leídos"):
        st.dataframe(pd.DataFrame([{"Fecha": l["fecha"], "Hora": l["hora"], "N° transacción": l["nro"], "Transacción": l["transaccion"],
                                    "Nota": l["contraparte"], "Detalle": l["detalle"], "Monto": l["monto"], "Saldo": l["saldo"]} for l in ext_cb["lineas"]]),
                     use_container_width=True, hide_index=True)

    # ---------------- 2. Cómo comparar ----------------
    st.subheader("2. Cómo comparar")
    co1, co2 = st.columns(2)
    with co1:
        dias_cb = int(st.number_input("Diferencia de fechas aceptada (días)", min_value=0, max_value=15, value=3, step=1, key="cb_dias",
                                      help="Un pago se considera el mismo si el monto es exacto y las fechas del banco y del sistema difieren hasta estos días."))
    with co2:
        efectivo_cb = st.checkbox("Comparar también los pagos en efectivo", key="cb_efectivo",
                                  help="Por defecto solo se comparan los registros que no son en efectivo (QR, transferencia…). Actívalo si a veces depositas "
                                       "en el banco el efectivo cobrado.")
    palabras_cb = st.text_input("Ignorar movimientos del banco que contengan (separa con comas)", key="cb_palabras", placeholder="pago de banco, traspaso propio",
                                help="Para dejar fuera movimientos que no son del negocio (pagos personales, traspasos entre tus cuentas…).")
    if ids_apartamentos_permitidos() is not None:
        st.warning("Tu usuario ve solo algunos apartamentos: los cobros de los demás saldrán como «sin registrar» aunque estén registrados.")

    # ---------------- 3. Registros del sistema ----------------
    st.caption("La comparación incluye pagos, compras, ventas, alquiler/servicios y movimientos auxiliares de Finanzas "
               "(devoluciones de préstamos y cobros de cuentas por cobrar). Estos últimos se leen para conciliar; no se duplican ni se contabilizan otra vez.")
    margen_cb = max(dias_cb, conciliacion.VENTANA_AGRUPADA)
    desde_sis_cb = date.fromordinal(ext_cb["desde"].toordinal() - margen_cb)
    hasta_sis_cb = date.fromordinal(ext_cb["hasta"].toordinal() + margen_cb)
    try:
        actividad_cb = cargar_actividad(str(desde_sis_cb), str(hasta_sis_cb))
        movs_cuadre_cb = cuadre.construir_movimientos(actividad_cb["pagos_generales"], actividad_cb["compras"], actividad_cb["ventas"])
        # Incluir auxiliares de Finanzas en la conciliación sin duplicar ni crear movimientos contables.
        movs_cuadre_cb.extend(movimientos_financieros_para_conciliacion(str(desde_sis_cb), str(hasta_sis_cb)))
        periodos_cb = {t: cargar_periodos_abiertos(t) for t in ("alquiler", "electricidad", "agua")}
        try:
            historial_cb = cargar_historial()
            cerrados_cb = {t: cargar_periodos_cerrados(t) for t in ("alquiler", "electricidad", "agua")}
        except Exception as e:
            historial_cb, cerrados_cb = [], {}
            st.warning(texto_error_historial("No se pudo leer el historial de ex inquilinos: no se incluyen sus pagos", e))
        rd_cb = rendicion.construir_rendicion(cargar_apartamentos(), periodos_cb["alquiler"], periodos_cb["electricidad"], periodos_cb["agua"],
                                              desde_sis_cb, hasta_sis_cb, recibo.hoy_bolivia(), cerrados=cerrados_cb, historial=historial_cb)
    except Exception as e:
        st.error(f"No se pudieron leer los registros del sistema: {e}")
        st.stop()
    r_cb = conciliacion.conciliar(
        ext_cb["lineas"], conciliacion.unificar_sistema(rd_cb["movimientos"], movs_cuadre_cb), dias=dias_cb, incluir_efectivo=efectivo_cb,
        palabras_excluir=[p.strip() for p in palabras_cb.split(",") if p.strip()], desde=ext_cb["desde"], hasta=ext_cb["hasta"])
    # Conservar el resultado automático original y aplicar encima las correcciones manuales.
    r_cb_base = r_cb
    clave_manual_cb = f"{firma_cb}_{ext_cb['desde']}_{ext_cb['hasta']}"
    clave_estado_manual_cb = f"cb_asignaciones_manuales_{clave_manual_cb}"
    if clave_estado_manual_cb not in st.session_state:
        st.session_state[clave_estado_manual_cb] = {}
    # Al reabrir una conciliación, restaurar sus asignaciones manuales sobre el extracto
    # que el usuario volvió a cargar. Solo se restauran referencias; nunca se insertan
    # pagos, compras, ventas ni movimientos de Finanzas.
    reapertura_cb = st.session_state.get("cb_reapertura_pendiente")
    if reapertura_cb:
        detalle_reapertura_cb = reapertura_cb.get("detalle") or {}
        if str(reapertura_cb.get("periodo_desde")) == str(ext_cb["desde"]) and str(reapertura_cb.get("periodo_hasta")) == str(ext_cb["hasta"]):
            st.session_state[clave_estado_manual_cb] = copy.deepcopy(detalle_reapertura_cb.get("conciliacion_manual") or {})
            st.session_state["cb_grupo_version_activo"] = {
                "grupo_id": reapertura_cb.get("grupo_id") or reapertura_cb.get("id"),
                "version_anterior": int(reapertura_cb.get("version") or 1),
                "cuenta": reapertura_cb.get("cuenta")
            }
            st.session_state.pop("cb_reapertura_pendiente", None)
            st.success("Conciliación reabierta. Se restauraron las asignaciones manuales; revisa los datos antes de guardar una nueva versión.")
        else:
            st.warning("La conciliación seleccionada corresponde a otro periodo. Carga el extracto original de ese mismo periodo para reabrirla.")
    asignaciones_manual_cb = st.session_state[clave_estado_manual_cb]

    # Reconstruir el resultado visible liberando cualquier coincidencia automática
    # que use un registro reasignado manualmente.
    r_cb = copy.deepcopy(r_cb_base)
    banco_por_idx_cb = {int(x["idx"]): x for x in r_cb_base["banco"]}
    sistema_por_idx_cb = {}
    for par_base_cb in r_cb_base["pares"]:
        for mov_base_cb in par_base_cb["sistema"]:
            sistema_por_idx_cb[int(mov_base_cb["idx"])] = mov_base_cb
    for pendiente_base_cb in r_cb_base["sistema_sin_banco"]:
        mov_base_cb = pendiente_base_cb["mov"]
        sistema_por_idx_cb[int(mov_base_cb["idx"])] = mov_base_cb

    indices_sistema_manuales_cb = {
        int(parte_cb["sistema_idx"])
        for asignacion_cb in asignaciones_manual_cb.values()
        for parte_cb in asignacion_cb.get("asignaciones", [])
    }
    pares_restantes_cb = []
    pares_liberados_cb = []
    for par_cb in r_cb["pares"]:
        ids_par_cb = {int(m["idx"]) for m in par_cb["sistema"]}
        if ids_par_cb & indices_sistema_manuales_cb:
            pares_liberados_cb.append(par_cb)
        else:
            pares_restantes_cb.append(par_cb)
    r_cb["pares"] = pares_restantes_cb

    bancos_pendientes_cb = {int(x["linea"]["idx"]): x for x in r_cb["banco_sin_registro"]}
    sistemas_pendientes_cb = {int(x["mov"]["idx"]): x for x in r_cb["sistema_sin_banco"]}
    for par_liberado_cb in pares_liberados_cb:
        for banco_liberado_cb in par_liberado_cb["banco"]:
            bancos_pendientes_cb[int(banco_liberado_cb["idx"])] = {
                "linea": banco_liberado_cb,
                "causas": ["Coincidencia automática liberada por una corrección manual."],
                "sugerencia": "Revisar y volver a asignar manualmente."
            }
        for sistema_liberado_cb in par_liberado_cb["sistema"]:
            sistemas_pendientes_cb[int(sistema_liberado_cb["idx"])] = {
                "mov": sistema_liberado_cb,
                "causas": ["Registro liberado de una coincidencia automática por corrección manual."]
            }

    manual_bancos_cb = set()
    manual_sistemas_usados_cb = {}
    motivos_saldo_pendiente_cb = {}
    pares_manuales_cb = []
    for idx_banco_asig_cb, asignacion_cb in asignaciones_manual_cb.items():
        idx_banco_asig_cb = int(idx_banco_asig_cb)
        linea_asig_cb = banco_por_idx_cb.get(idx_banco_asig_cb)
        if not linea_asig_cb:
            continue
        manual_bancos_cb.add(idx_banco_asig_cb)
        bancos_pendientes_cb.pop(idx_banco_asig_cb, None)
        sistemas_par_manual_cb = []
        for parte_cb in asignacion_cb.get("asignaciones", []):
            idx_sistema_parte_cb = int(parte_cb["sistema_idx"])
            mov_original_parte_cb = sistema_por_idx_cb.get(idx_sistema_parte_cb)
            if not mov_original_parte_cb:
                continue
            importe_parte_cb = round(float(parte_cb["monto"]), 2)
            manual_sistemas_usados_cb[idx_sistema_parte_cb] = manual_sistemas_usados_cb.get(idx_sistema_parte_cb, 0.0) + importe_parte_cb
            if asignacion_cb.get("motivo_saldo_pendiente"):
                motivos_saldo_pendiente_cb[idx_sistema_parte_cb] = asignacion_cb.get("motivo_saldo_pendiente")
            mov_parte_cb = dict(mov_original_parte_cb)
            mov_parte_cb["monto"] = importe_parte_cb
            mov_parte_cb["monto_conciliado_manual"] = importe_parte_cb
            sistemas_par_manual_cb.append(mov_parte_cb)
        pares_manuales_cb.append({
            "banco": [linea_asig_cb],
            "sistema": sistemas_par_manual_cb,
            "union": "Conciliación manual",
            "confianza": "Manual",
            "dias": max([abs((linea_asig_cb["fecha"] - x["fecha"]).days) for x in sistemas_par_manual_cb] or [0]),
            "razones": ["Asignación confirmada manualmente por el usuario."],
            "estado_conciliacion": asignacion_cb.get("estado_conciliacion", "exacta"),
            "total_asignado": round(sum(float(a.get("monto") or 0) for a in asignacion_cb.get("asignaciones", [])), 2),
            "diferencia": round(float(asignacion_cb.get("diferencia") or 0), 2),
            "observacion_diferencia": asignacion_cb.get("observacion_diferencia", ""),
            "saldo_pendiente_registro": round(float(asignacion_cb.get("saldo_pendiente_registro") or 0), 2),
            "motivo_saldo_pendiente": asignacion_cb.get("motivo_saldo_pendiente", "")
        })

    # Retirar del listado pendiente los registros usados manualmente; si la asignación
    # fue parcial, dejar únicamente el saldo no aplicado como pendiente.
    for idx_sistema_usado_cb, monto_usado_cb in manual_sistemas_usados_cb.items():
        mov_original_cb = sistema_por_idx_cb[idx_sistema_usado_cb]
        sistemas_pendientes_cb.pop(idx_sistema_usado_cb, None)
        saldo_residual_cb = round(abs(float(mov_original_cb.get("monto") or 0)) - monto_usado_cb, 2)
        if saldo_residual_cb > 0.004:
            mov_residual_cb = dict(mov_original_cb)
            mov_residual_cb["monto"] = saldo_residual_cb
            motivo_residual_cb = motivos_saldo_pendiente_cb.get(idx_sistema_usado_cb, "")
            if motivo_residual_cb == "Reembolso/devolución pendiente de recibir":
                mov_residual_cb["detalle"] = (
                    str(mov_original_cb.get("detalle") or "")
                    + f" [REEMBOLSO PENDIENTE Bs {saldo_residual_cb:,.2f}]"
                ).strip()
                causa_residual_cb = (
                    f"Saldo de Bs {saldo_residual_cb:,.2f} pendiente de reembolso/devolución. "
                    "Aún no se recibió el dinero; permanece pendiente y no se considera conciliado."
                )
            else:
                mov_residual_cb["detalle"] = (str(mov_original_cb.get("detalle") or "") + " [saldo no asignado]").strip()
                causa_residual_cb = (
                    f"Saldo restante de Bs {saldo_residual_cb:,.2f} de un registro parcialmente conciliado. "
                    + (motivo_residual_cb or "Pendiente de aclaración.")
                )
            sistemas_pendientes_cb[idx_sistema_usado_cb] = {
                "mov": mov_residual_cb,
                "causas": [causa_residual_cb]
            }

    r_cb["pares"].extend(pares_manuales_cb)
    r_cb["banco_sin_registro"] = sorted(bancos_pendientes_cb.values(), key=lambda x: (x["linea"]["fecha"], x["linea"]["idx"]))
    r_cb["sistema_sin_banco"] = sorted(sistemas_pendientes_cb.values(), key=lambda x: (x["mov"]["fecha"], x["mov"]["idx"]))
    r_cb["pares"].sort(key=lambda p: (p["banco"][0]["fecha"], p["banco"][0]["idx"]))
    sistema_resumen_cb = conciliacion._preparar_sistema(
        conciliacion.unificar_sistema(rd_cb["movimientos"], movs_cuadre_cb)
    )
    for mov_resumen_cb in sistema_resumen_cb:
        mov_resumen_cb["en_periodo"] = ext_cb["desde"] <= mov_resumen_cb["fecha"] <= ext_cb["hasta"]
    r_cb["resumen"] = conciliacion._resumen(
        r_cb["banco"], r_cb["pares"], r_cb["banco_sin_registro"], r_cb["sistema_sin_banco"],
        r_cb["excluidos"], sistema_resumen_cb, r_cb["efectivo"]
    )
    rs_cb = r_cb["resumen"]
    cantidad_resuelta_manual_cb = len(pares_manuales_cb)

    # ---------------- 4. Resultado ----------------
    st.subheader("3. Resultado")
    comparables_cb = rs_cb["banco"]["n"] - rs_cb["excluidos"]["n"]
    conciliados_totales_cb = rs_cb["conciliado"]["n"]
    pendientes_banco_cb = rs_cb["sin_registro"]["n"]
    pct_cb = round(100 * conciliados_totales_cb / comparables_cb) if comparables_cb else 0
    cr1, cr2, cr3, cr4 = st.columns(4)
    cr1.metric("Conciliados", f'{conciliados_totales_cb} de {comparables_cb}', help=f"{pct_cb}% de los movimientos bancarios están conciliados automática o manualmente")
    cr2.metric("En el banco, sin registrar", pendientes_banco_cb,
               help=f'Entra {fmt_money(rs_cb["sin_registro"]["creditos"])} · Sale {fmt_money(rs_cb["sin_registro"]["debitos"])}')
    cr3.metric("En el sistema, sin banco", rs_cb["sistema_sin_banco"]["n"],
               help=f'Ingresos {fmt_money(rs_cb["sistema_sin_banco"]["ingresos"])} · Egresos {fmt_money(rs_cb["sistema_sin_banco"]["egresos"])}')
    cr4.metric("Efectivo (no comparado)", rs_cb["efectivo_no_comparado"]["n"])
    st.markdown(f"**{pct_cb}%** de los movimientos del banco están conciliados automática o manualmente. "
                f"Pendientes de resolver: {pendientes_banco_cb}.")
    if cantidad_resuelta_manual_cb:
        st.caption(f"Se han vinculado manualmente {cantidad_resuelta_manual_cb} movimiento(s) bancario(s) en esta revisión.")
    if rs_cb["por_confianza"]["Revisar"] or rs_cb["por_confianza"]["Media"]:
        st.caption(f'Coincidencias: {rs_cb["por_confianza"]["Alta"]} con confianza alta, {rs_cb["por_confianza"]["Media"]} media y '
                   f'{rs_cb["por_confianza"]["Revisar"]} para revisar (pestaña «Conciliados»).')

    fmt_cb = {c: st.column_config.NumberColumn(format="Bs %.2f") for c in ("Monto", "Monto banco", "Monto sistema", "Saldo")}
    t_sin, t_sis, t_con, t_ext, t_efe = st.tabs([
        f"⚠️ En el banco, sin registrar ({rs_cb['sin_registro']['n']})", f"📋 En el sistema, sin banco ({rs_cb['sistema_sin_banco']['n']})",
        f"✅ Conciliados ({len(r_cb['pares'])})", "🏦 Extracto completo", f"💵 Efectivo ({rs_cb['efectivo_no_comparado']['n']})"])
    with t_sin:
        filas_sin_cb = conciliacion_reportes.filas_banco_sin_registro(r_cb)
        if filas_sin_cb:
            st.caption("Movimientos que están en el banco pero no encontré en el sistema. «Causa probable» te dice por qué.")
            st.dataframe(pd.DataFrame([{enc: f[c] for c, enc, _t in conciliacion_reportes.COL_BANCO_SIN if c not in ("hora", "nro", "transaccion", "otras")}
                                       for f in filas_sin_cb]), use_container_width=True, hide_index=True, column_config=fmt_cb)
            with st.expander("Ver todas las pistas de cada movimiento"):
                for x_cb in r_cb["banco_sin_registro"]:
                    l_cb = x_cb["linea"]
                    st.markdown(f"**{l_cb['fecha']:%d/%m/%Y} · Bs {l_cb['monto']:,.2f} · {l_cb['contraparte'] or l_cb['transaccion']}**"
                                + (f" — _{l_cb['detalle']}_" if l_cb["detalle"] else ""))
                    for causa_cb in x_cb["causas"]:
                        st.markdown(f"- {causa_cb}")

            # ---------- Conciliación manual: asignar un movimiento bancario a uno o varios registros ----------
            st.divider()
            st.subheader("Resolver movimientos manualmente")
            st.info("Selecciona los registros del sistema que corresponden a cada movimiento bancario. La suma asignada debe ser exactamente igual al importe del banco. Esto solo crea una relación de conciliación: no modifica ni duplica ingresos o gastos.")
            asignaciones_manual_cb = st.session_state[clave_estado_manual_cb]

            movimientos_sistema_libres_cb = list(sistema_por_idx_cb.values())
            def _etiqueta_mov_sistema_cb(m):
                return (f"{m['fecha']:%d/%m/%Y} · {m.get('tipo','')} · Bs {abs(float(m.get('monto') or 0)):,.2f} · "
                        f"{m.get('origen','')} · {m.get('persona','')} · {m.get('detalle','')[:75]}")

            total_resueltos_manual_cb = 0
            filas_editables_manual_cb = list(r_cb_base["banco_sin_registro"])
            ids_banco_editables_cb = {int(x["linea"]["idx"]) for x in filas_editables_manual_cb}
            for idx_banco_guardado_cb in asignaciones_manual_cb:
                if int(idx_banco_guardado_cb) not in ids_banco_editables_cb and int(idx_banco_guardado_cb) in banco_por_idx_cb:
                    filas_editables_manual_cb.append({"linea": banco_por_idx_cb[int(idx_banco_guardado_cb)], "causas": [], "sugerencia": ""})
            for item_manual_cb in filas_editables_manual_cb:
                linea_manual_cb = item_manual_cb["linea"]
                idx_banco_manual_cb = int(linea_manual_cb["idx"])
                monto_banco_manual_cb = round(abs(float(linea_manual_cb["monto"])), 2)
                direccion_signo_banco_cb = "Ingreso" if float(linea_manual_cb["monto"]) > 0 else "Egreso"
                asignacion_existente_cb = asignaciones_manual_cb.get(str(idx_banco_manual_cb))
                direccion_guardada_cb = (
                    asignacion_existente_cb.get("direccion_manual")
                    if asignacion_existente_cb else None
                )
                direccion_predeterminada_cb = direccion_guardada_cb or direccion_signo_banco_cb

                titulo_manual_cb = (f"{linea_manual_cb['fecha']:%d/%m/%Y} · "
                                    f"Movimiento bancario · Bs {monto_banco_manual_cb:,.2f} · "
                                    f"{linea_manual_cb.get('contraparte') or linea_manual_cb.get('transaccion') or 'Sin descripción'}")
                with st.expander(("✅ " if asignacion_existente_cb else "⚠️ ") + titulo_manual_cb,
                                 expanded=not bool(asignacion_existente_cb)):
                    opciones_direccion_cb = ["Ingreso", "Egreso"]
                    indice_direccion_cb = opciones_direccion_cb.index(direccion_predeterminada_cb)
                    direccion_manual_cb = st.selectbox(
                        "Clasificación del movimiento bancario",
                        options=opciones_direccion_cb,
                        index=indice_direccion_cb,
                        key=f"cb_direccion_manual_{clave_manual_cb}_{idx_banco_manual_cb}",
                        help="Usa esta opción cuando el signo importado no represente la naturaleza real del movimiento. Ejemplo: interés ganado = Ingreso."
                    )
                    if direccion_manual_cb != direccion_signo_banco_cb:
                        st.warning(
                            f"El signo del extracto lo clasificó como {direccion_signo_banco_cb}, "
                            f"pero estás indicando {direccion_manual_cb}. Verifica el concepto bancario antes de confirmar."
                        )
                    if asignacion_existente_cb:
                        if asignacion_existente_cb.get("estado_conciliacion") == "con_diferencia":
                            st.warning(
                                f"Conciliación cerrada CON DIFERENCIA: Bs {abs(float(asignacion_existente_cb.get('diferencia') or 0)):,.2f}. "
                                f"Motivo: {asignacion_existente_cb.get('observacion_diferencia') or 'Sin observación registrada'}"
                            )
                        else:
                            st.success("Conciliación manual exacta guardada para esta revisión.")
                        for a_cb in asignacion_existente_cb["asignaciones"]:
                            mov_a_cb = next((m for m in movimientos_sistema_libres_cb if int(m["idx"]) == int(a_cb["sistema_idx"])), None)
                            etiqueta_a_cb = _etiqueta_mov_sistema_cb(mov_a_cb) if mov_a_cb else f"Registro sistema #{a_cb['sistema_idx']}"
                            st.write(f"• Bs {float(a_cb['monto']):,.2f} → {etiqueta_a_cb}")
                        col_editar_asig_cb, col_quitar_asig_cb = st.columns(2)
                        if col_editar_asig_cb.button("Modificar asignación", key=f"cb_editar_manual_{clave_manual_cb}_{idx_banco_manual_cb}"):
                            asignaciones_manual_cb.pop(str(idx_banco_manual_cb), None)
                            st.session_state[clave_estado_manual_cb] = asignaciones_manual_cb
                            st.rerun()
                        if col_quitar_asig_cb.button("Quitar asignación manual", key=f"cb_quitar_manual_{clave_manual_cb}_{idx_banco_manual_cb}"):
                            asignaciones_manual_cb.pop(str(idx_banco_manual_cb), None)
                            st.session_state[clave_estado_manual_cb] = asignaciones_manual_cb
                            st.rerun()
                        total_resueltos_manual_cb += 1
                        continue

                    candidatos_manual_cb = []
                    for mov_candidato_cb in movimientos_sistema_libres_cb:
                        # Una misma operación bancaria puede respaldarse con varios
                        # registros del sistema, incluso de distinta naturaleza:
                        # ingresos y egresos (p. ej. anticipo, rendición y devolución).
                        diferencia_dias_cb = abs((linea_manual_cb["fecha"] - mov_candidato_cb["fecha"]).days)
                        if diferencia_dias_cb > max(45, dias_cb):
                            continue
                        candidatos_manual_cb.append(mov_candidato_cb)

                    if not candidatos_manual_cb:
                        st.warning("No hay registros del sistema con la misma dirección (ingreso/egreso) dentro de los 45 días.")
                        continue
                    ids_automaticos_candidatos_cb = {
                        int(m["idx"])
                        for par_auto_cb in r_cb_base["pares"]
                        for m in par_auto_cb["sistema"]
                    }
                    if any(int(m["idx"]) in ids_automaticos_candidatos_cb for m in candidatos_manual_cb):
                        st.warning("También puedes seleccionar registros que ya aparecen en «Conciliados». Al confirmar, EQUISE liberará su coincidencia automática anterior y la sustituirá por esta asignación manual. El otro movimiento bancario quedará pendiente para revisión.")

                    usados_sistema_manual_cb = {}
                    for clave_banco_otro_cb, asignacion_otro_cb in asignaciones_manual_cb.items():
                        if str(clave_banco_otro_cb) == str(idx_banco_manual_cb):
                            continue
                        for parte_cb in asignacion_otro_cb.get("asignaciones", []):
                            k_s_cb = str(parte_cb["sistema_idx"])
                            usados_sistema_manual_cb[k_s_cb] = usados_sistema_manual_cb.get(k_s_cb, 0.0) + float(parte_cb["monto"])

                    etiquetas_candidatos_cb = {int(m["idx"]): _etiqueta_mov_sistema_cb(m) for m in candidatos_manual_cb}
                    # Buscador por nombre, apartamento, concepto, periodo, fecha o importe.
                    clave_busqueda_cb = f"cb_buscar_sistema_{clave_manual_cb}_{idx_banco_manual_cb}"
                    busqueda_sistema_cb = st.text_input(
                        "Buscar registro por inquilino, acreedor, apartamento, concepto, mes o importe",
                        key=clave_busqueda_cb,
                        placeholder="Ej.: Dussan, mayo, apartamento SP, alquiler, 1100..."
                    ).strip().casefold()

                    def _texto_busqueda_mov_cb(m):
                        campos = (
                            m.get("fecha"), m.get("tipo"), m.get("monto"), m.get("origen"),
                            m.get("persona"), m.get("apartamento"), m.get("categoria"),
                            m.get("periodo"), m.get("detalle"), m.get("comprobante"),
                            m.get("metodo"), m.get("metodo_original")
                        )
                        return " ".join(str(x or "") for x in campos).casefold()

                    candidatos_filtrados_cb = [
                        m for m in candidatos_manual_cb
                        if not busqueda_sistema_cb or busqueda_sistema_cb in _texto_busqueda_mov_cb(m)
                    ]
                    ids_filtrados_cb = [int(m["idx"]) for m in candidatos_filtrados_cb]
                    st.caption(
                        f"Mostrando {len(candidatos_filtrados_cb)} de {len(candidatos_manual_cb)} registros disponibles. "
                        "Escribe una palabra, nombre, mes, apartamento o importe para reducir la lista."
                    )

                    # Mantener visibles las selecciones anteriores aunque el usuario cambie el texto de búsqueda.
                    key_multiselect_cb = f"cb_seleccion_manual_{clave_manual_cb}_{idx_banco_manual_cb}"
                    seleccion_previa_cb = st.session_state.get(key_multiselect_cb, [])
                    opciones_candidatos_cb = list(dict.fromkeys(ids_filtrados_cb + [
                        int(v) for v in seleccion_previa_cb if int(v) in etiquetas_candidatos_cb
                    ]))
                    seleccion_manual_cb = st.multiselect(
                        "Registros del sistema que corresponden a este movimiento",
                        options=opciones_candidatos_cb,
                        format_func=lambda v: etiquetas_candidatos_cb.get(v, str(v)),
                        key=key_multiselect_cb,
                        help="Puedes seleccionar uno o varios registros. El buscador anterior filtra por nombre, apartamento, concepto, periodo, fecha o importe."
                    )
                    if seleccion_manual_cb:
                        st.caption("Indica cuánto del importe de cada registro corresponde a esta transferencia.")
                        partes_nuevas_manual_cb = []
                        for idx_sistema_sel_cb in seleccion_manual_cb:
                            mov_sel_cb = next(m for m in candidatos_manual_cb if int(m["idx"]) == int(idx_sistema_sel_cb))
                            saldo_disp_cb = round(abs(float(mov_sel_cb.get("monto") or 0)) - usados_sistema_manual_cb.get(str(idx_sistema_sel_cb), 0.0), 2)
                            if saldo_disp_cb <= 0:
                                st.warning(f"El registro seleccionado ya está asignado completamente: {etiquetas_candidatos_cb[idx_sistema_sel_cb]}")
                                continue
                            monto_sugerido_cb = min(monto_banco_manual_cb, saldo_disp_cb)
                            monto_parte_cb = st.number_input(
                                f"Importe a asignar · {etiquetas_candidatos_cb[idx_sistema_sel_cb]}",
                                min_value=0.0, max_value=float(saldo_disp_cb), value=float(monto_sugerido_cb),
                                step=0.01, format="%.2f",
                                key=f"cb_monto_manual_{clave_manual_cb}_{idx_banco_manual_cb}_{idx_sistema_sel_cb}"
                            )
                            saldo_pendiente_parte_cb = round(max(0.0, saldo_disp_cb - float(monto_parte_cb)), 2)
                            partes_nuevas_manual_cb.append({
                                "sistema_idx": int(idx_sistema_sel_cb),
                                "monto": round(float(monto_parte_cb), 2),
                                "saldo_pendiente": saldo_pendiente_parte_cb
                            })
                        suma_asignada_cb = round(sum(x["monto"] for x in partes_nuevas_manual_cb), 2)
                        saldo_pendiente_registro_cb = round(sum(x.get("saldo_pendiente", 0.0) for x in partes_nuevas_manual_cb), 2)
                        tipos_seleccionados_cb = {
                            next(m["tipo"] for m in candidatos_manual_cb if int(m["idx"]) == int(x["sistema_idx"]))
                            for x in partes_nuevas_manual_cb
                        }
                        if len(tipos_seleccionados_cb) > 1:
                            st.info("Estás combinando ingresos y egresos del sistema en una misma conciliación. Verifica que correspondan a la misma operación, anticipo o rendición.")
                        diferencia_manual_cb = round(monto_banco_manual_cb - suma_asignada_cb, 2)
                        # Inicializar todas las variables de decisión antes de las ramas.
                        # Evita NameError cuando se confirma una conciliación con diferencia.
                        motivo_saldo_pendiente_cb = ""
                        aceptar_saldo_pendiente_cb = True
                        aceptar_diferencia_cb = False
                        observacion_diferencia_cb = ""
                        st.write(f"**Total asignado:** Bs {suma_asignada_cb:,.2f} / **Banco:** Bs {monto_banco_manual_cb:,.2f}")
                        if abs(diferencia_manual_cb) <= 0.004 and saldo_pendiente_registro_cb <= 0.004:
                            st.success("Los importes del banco y de los registros seleccionados coinciden. Puedes cerrar como conciliación exacta.")
                            observacion_diferencia_cb = ""
                            motivo_saldo_pendiente_cb = ""
                            aceptar_saldo_pendiente_cb = True
                        elif abs(diferencia_manual_cb) <= 0.004 and saldo_pendiente_registro_cb > 0.004:
                            st.warning(
                                f"El movimiento bancario está cubierto por Bs {suma_asignada_cb:,.2f}, "
                                f"pero queda un saldo de Bs {saldo_pendiente_registro_cb:,.2f} del/de los registro(s) del sistema. "
                                "Ese saldo NO está conciliado."
                            )
                            motivo_saldo_pendiente_cb = st.selectbox(
                                "¿Qué representa el saldo que queda pendiente?",
                                options=[
                                    "Reembolso/devolución pendiente de recibir",
                                    "Saldo pendiente de pago",
                                    "Otro saldo pendiente de aclaración"
                                ],
                                index=0,
                                key=f"cb_motivo_saldo_{clave_manual_cb}_{idx_banco_manual_cb}"
                            )
                            st.caption(
                                f"Se mantendrán Bs {saldo_pendiente_registro_cb:,.2f} en «En el sistema, sin banco» "
                                "hasta que se registre y concilie el reembolso/devolución correspondiente."
                            )
                            aceptar_saldo_pendiente_cb = st.checkbox(
                                f"Confirmo que Bs {saldo_pendiente_registro_cb:,.2f} queda pendiente y NO debe marcarse como conciliado.",
                                value=False,
                                key=f"cb_aceptar_saldo_{clave_manual_cb}_{idx_banco_manual_cb}"
                            )
                            observacion_diferencia_cb = ""
                        else:
                            st.warning(
                                f"Existe una diferencia de Bs {abs(diferencia_manual_cb):,.2f}. "
                                + ("El banco registra más que los registros seleccionados." if diferencia_manual_cb > 0
                                   else "Los registros seleccionados suman más que el movimiento bancario.")
                            )
                            observacion_diferencia_cb = st.text_area(
                                "Justificación obligatoria de la diferencia",
                                key=f"cb_motivo_diferencia_{clave_manual_cb}_{idx_banco_manual_cb}",
                                placeholder="Ej.: devolución realizada en noviembre; comisión bancaria; pago parcial; diferencia pendiente de identificar...",
                                help="La conciliación quedará identificada como CON DIFERENCIA. No se creará automáticamente ningún ingreso o gasto por el importe restante."
                            ).strip()
                            st.caption("Podrás cerrar con diferencia, pero el importe quedará visible como pendiente de aclaración; no se considerará conciliación exacta.")
                            aceptar_diferencia_cb = st.checkbox(
                                f"Confirmo que revisé la diferencia de Bs {abs(diferencia_manual_cb):,.2f}, estoy de acuerdo con cerrar esta conciliación con diferencia y acepto que quede pendiente de aclaración.",
                                value=False,
                                key=f"cb_aceptar_diferencia_{clave_manual_cb}_{idx_banco_manual_cb}"
                            )

                        if st.button("Confirmar conciliación manual", key=f"cb_confirmar_manual_{clave_manual_cb}_{idx_banco_manual_cb}",
                                      disabled=(not partes_nuevas_manual_cb or
                                                (abs(diferencia_manual_cb) > 0.004 and
                                                 (not observacion_diferencia_cb or not aceptar_diferencia_cb)) or
                                                (saldo_pendiente_registro_cb > 0.004 and
                                                 not aceptar_saldo_pendiente_cb)),
                                      use_container_width=True):
                            if abs(diferencia_manual_cb) > 0.004 and not observacion_diferencia_cb:
                                st.error("Para cerrar con diferencia debes escribir una justificación.")
                            elif abs(diferencia_manual_cb) > 0.004 and not aceptar_diferencia_cb:
                                st.error("Debes confirmar expresamente que estás de acuerdo con cerrar esta conciliación con diferencia.")
                            elif saldo_pendiente_registro_cb > 0.004 and not aceptar_saldo_pendiente_cb:
                                st.error("Debes confirmar que el saldo restante quedará pendiente y no se marcará como conciliado.")
                            else:
                                # Revalidar capacidad disponible para evitar asignar dos veces el mismo registro.
                                capacidad_ok_cb = True
                                for parte_cb in partes_nuevas_manual_cb:
                                    mov_validar_cb = next(m for m in candidatos_manual_cb if int(m["idx"]) == parte_cb["sistema_idx"])
                                    ya_usado_cb = usados_sistema_manual_cb.get(str(parte_cb["sistema_idx"]), 0.0)
                                    if parte_cb["monto"] <= 0 or parte_cb["monto"] > round(abs(float(mov_validar_cb.get("monto") or 0)) - ya_usado_cb, 2):
                                        capacidad_ok_cb = False
                                if not capacidad_ok_cb:
                                    st.error("Uno de los registros supera su saldo disponible. Revisa los importes.")
                                else:
                                    asignaciones_manual_cb[str(idx_banco_manual_cb)] = {
                                        "banco_idx": idx_banco_manual_cb,
                                        "fecha_banco": str(linea_manual_cb["fecha"]),
                                        "monto_banco": float(linea_manual_cb["monto"]),
                                        "descripcion_banco": str(linea_manual_cb.get("contraparte") or linea_manual_cb.get("transaccion") or ""),
                                        "direccion_manual": direccion_manual_cb,
                                        "asignaciones": partes_nuevas_manual_cb,
                                        "estado_conciliacion": (
                                            "parcial_con_saldo_pendiente" if saldo_pendiente_registro_cb > 0.004
                                            else ("exacta" if abs(diferencia_manual_cb) <= 0.004 else "con_diferencia")
                                        ),
                                        "total_asignado": suma_asignada_cb,
                                        "diferencia": diferencia_manual_cb,
                                        "observacion_diferencia": observacion_diferencia_cb,
                                        "saldo_pendiente_registro": saldo_pendiente_registro_cb,
                                        "motivo_saldo_pendiente": motivo_saldo_pendiente_cb
                                    }
                                    st.session_state[clave_estado_manual_cb] = asignaciones_manual_cb
                                    st.rerun()
                    else:
                        st.caption("Selecciona al menos un registro para habilitar la conciliación manual.")

            st.caption(f"Movimientos bancarios resueltos manualmente en esta revisión: {total_resueltos_manual_cb} de {len(r_cb['banco_sin_registro'])}.")
        else:
            st.success("Todos los movimientos del banco están registrados en el sistema. 🎉")
    with t_sis:
        filas_sis_cb = conciliacion_reportes.filas_sistema_sin_banco(r_cb)
        if filas_sis_cb:
            st.caption("Registros del sistema que no aparecen en el extracto (no incluye los pagos en efectivo, salvo que actives esa opción).")
            st.dataframe(pd.DataFrame([{enc: f[c] for c, enc, _t in conciliacion_reportes.COL_SISTEMA_SIN if c != "otras"} for f in filas_sis_cb]),
                         use_container_width=True, hide_index=True, column_config=fmt_cb)
        else:
            st.success("Todos los registros del sistema aparecen en el banco.")
    with t_con:
        filas_con_cb = conciliacion_reportes.filas_conciliados(r_cb)
        if filas_con_cb:
            filtro_con_cb = st.selectbox("Confianza", ["Todas", "Alta", "Media", "Revisar"], key="cb_filtro_conf",
                                         help="Alta: el texto confirma la coincidencia. Media: coincide el monto y la fecha pero el texto no lo confirma. Revisar: conviene verificarla.")
            vista_con_cb = [f for f in filas_con_cb if filtro_con_cb == "Todas" or f["confianza"] == filtro_con_cb]
            st.dataframe(pd.DataFrame([{enc: f[c] for c, enc, _t in conciliacion_reportes.COL_CONCILIADOS} for f in vista_con_cb]),
                         use_container_width=True, hide_index=True, column_config=fmt_cb)
        else:
            st.info("No hubo coincidencias.")
    with t_ext:
        iconos_cb = {"Conciliado": "✅ Conciliado", "Sin registrar en el sistema": "⚠️ Sin registrar", "Excluido": "➖ Excluido"}
        st.dataframe(pd.DataFrame([{**{enc: f[c] for c, enc, _t in conciliacion_reportes.COL_EXTRACTO if c not in ("estado", "n", "hora", "nro")},
                                    "Estado": iconos_cb[f["estado"]]} for f in conciliacion_reportes.filas_extracto(r_cb)]),
                     use_container_width=True, hide_index=True, column_config=fmt_cb)
    with t_efe:
        if r_cb["efectivo"]:
            st.caption("Registros pagados en efectivo en las fechas del extracto: no pasan por el banco, por eso no se compararon.")
            st.dataframe(pd.DataFrame([{enc: f[c] for c, enc, _t in conciliacion_reportes.COL_EFECTIVO} for f in conciliacion_reportes.filas_efectivo(r_cb)]),
                         use_container_width=True, hide_index=True, column_config=fmt_cb)
        else:
            st.info("No hay registros en efectivo para mostrar (o activaste «Comparar también los pagos en efectivo»).")

    # ---------------- 5. Guardar y consultar historial ----------------
    st.divider()
    st.subheader("4. Guardar conciliación e historial")
    st.caption("Guarda el resultado de esta revisión para consultarlo después. Se almacena una instantánea de los datos; no se duplican ingresos ni egresos y no se guardan imágenes ni el archivo del extracto.")
    col_guardar_cb, col_hist_cb = st.columns([1, 1])
    with col_guardar_cb:
        cuenta_cb = st.text_input("Identificación de la cuenta bancaria (opcional)", key="cb_cuenta_historial", placeholder="Ej. Banco Unión · Cuenta terminación 1234")
        confirmar_guardado_cb = st.checkbox("Confirmo que deseo guardar esta versión de la conciliación", key="cb_confirmar_guardado")
        if st.button("💾 Guardar conciliación", key="cb_guardar_historial", disabled=not confirmar_guardado_cb, use_container_width=True):
            try:
                resumen_guardado = rs_cb
                instantanea = json.loads(json.dumps({
                    "pares": r_cb["pares"],
                    "banco_sin_registro": r_cb["banco_sin_registro"],
                    "sistema_sin_banco": r_cb["sistema_sin_banco"],
                    "excluidos": r_cb["excluidos"],
                    "efectivo": r_cb["efectivo"],
                    "banco": r_cb["banco"],
                    "resumen": resumen_guardado,
                    "conciliacion_manual": st.session_state.get(clave_estado_manual_cb, {}) if "clave_estado_manual_cb" in locals() else {},
                    "parametros": {"dias": dias_cb, "incluir_efectivo": efectivo_cb, "palabras_excluir": [p.strip() for p in palabras_cb.split(",") if p.strip()]}
                }, default=str))
                grupo_activo_cb = st.session_state.get("cb_grupo_version_activo") or {}
                grupo_id_cb = grupo_activo_cb.get("grupo_id")
                version_cb = int(grupo_activo_cb.get("version_anterior") or 0) + 1 if grupo_id_cb else 1
                db.guardar_conciliacion_bancaria({
                    "grupo_id": grupo_id_cb,
                    "version": version_cb,
                    "estado": "guardada",
                    "periodo_desde": str(ext_cb["desde"]), "periodo_hasta": str(ext_cb["hasta"]),
                    "cuenta": cuenta_cb.strip() or grupo_activo_cb.get("cuenta") or None,
                    "total_movimientos": int(resumen_guardado["banco"]["n"]),
                    "conciliados": int(resumen_guardado["conciliado"]["n"]),
                    "pendientes": int(resumen_guardado["sin_registro"]["n"] + resumen_guardado["sistema_sin_banco"]["n"]),
                    "monto_banco": float(resumen_guardado["banco"]["creditos"] + resumen_guardado["banco"]["debitos"]),
                    "creado_por": usuario_actual.get("nombre") or usuario_actual.get("username"),
                    "detalle": instantanea
                })
                st.session_state.pop("cb_grupo_version_activo", None)
                st.success(f"Versión {version_cb} guardada. Las versiones anteriores se mantienen intactas.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo guardar. Verifica que hayas ejecutado la migración SQL de historial: {e}")
    with col_hist_cb:
        st.markdown("**Conciliaciones guardadas**")
        try:
            historial_cb = db.listar_conciliaciones_bancarias(100)
            if historial_cb:
                df_hist_cb = pd.DataFrame([{
                    "Desde": x.get("periodo_desde"), "Hasta": x.get("periodo_hasta"),
                    "Cuenta": x.get("cuenta") or "—", "Movimientos": x.get("total_movimientos"),
                    "Conciliados": x.get("conciliados"), "Pendientes": x.get("pendientes"),
                    "Versión": x.get("version", 1), "Estado": x.get("estado") or "guardada",
                    "Guardado por": x.get("creado_por") or "—", "Fecha de guardado": x.get("created_at")
                } for x in historial_cb])
                st.dataframe(df_hist_cb, use_container_width=True, hide_index=True)
                mapa_hist_cb = {f'{x.get("periodo_desde")} a {x.get("periodo_hasta")} · V{x.get("version", 1)} · {x.get("cuenta") or "Sin cuenta"} · {x.get("created_at", "")[:16]}': x for x in historial_cb}
                elegido_hist_cb = st.selectbox("Seleccionar conciliación / versión", list(mapa_hist_cb), key="cb_historial_selector")
                col_ver_hist_cb, col_reabrir_hist_cb = st.columns(2)
                if col_ver_hist_cb.button("Consultar detalle guardado", key="cb_historial_abrir", use_container_width=True):
                    st.session_state["cb_historial_consulta_id"] = mapa_hist_cb[elegido_hist_cb]["id"]
                if col_reabrir_hist_cb.button("↩️ Reabrir conciliación", key="cb_historial_reabrir", use_container_width=True):
                    st.session_state["cb_reapertura_pendiente"] = db.obtener_conciliacion_bancaria(mapa_hist_cb[elegido_hist_cb]["id"])
                    st.session_state["cb_historial_consulta_id"] = mapa_hist_cb[elegido_hist_cb]["id"]
                    st.info("Conciliación seleccionada para reabrir. Vuelve a cargar el extracto bancario original del mismo periodo; al procesarlo se restaurarán las asignaciones.")
                consulta_id_cb = st.session_state.get("cb_historial_consulta_id")
                if consulta_id_cb:
                    guardada_cb = db.obtener_conciliacion_bancaria(consulta_id_cb)
                    if guardada_cb:
                        det_cb = guardada_cb.get("detalle") or {}
                        st.caption(f'Consulta histórica: {guardada_cb.get("periodo_desde")} a {guardada_cb.get("periodo_hasta")} · {guardada_cb.get("creado_por") or "—"}')
                        st.json(det_cb.get("resumen", {}), expanded=False)
                        pares_hist_cb = det_cb.get("pares", [])
                        if pares_hist_cb:
                            st.write("**Coincidencias guardadas**")
                            filas_hist_cb = []
                            for par in pares_hist_cb:
                                for b in par.get("banco", []):
                                    filas_hist_cb.append({"Fecha banco": b.get("fecha"), "Importe banco": b.get("monto"), "Tipo de cruce": par.get("union"), "Confianza": par.get("confianza"), "Registros asociados": len(par.get("sistema", []))})
                            st.dataframe(pd.DataFrame(filas_hist_cb), use_container_width=True, hide_index=True)
                        if det_cb.get("banco_sin_registro"):
                            st.write("**Movimientos bancarios pendientes al guardar**")
                            st.dataframe(pd.DataFrame([{"Fecha": x.get("linea", {}).get("fecha"), "Importe": x.get("linea", {}).get("monto"), "Causas": "; ".join(x.get("causas", []))} for x in det_cb["banco_sin_registro"]]), use_container_width=True, hide_index=True)
            else:
                st.info("Todavía no hay conciliaciones guardadas.")
        except Exception as e:
            st.warning(f"No se pudo consultar el historial. Verifica la migración SQL: {e}")

    emisor_cb = usuario_actual.get("nombre") or usuario_actual.get("username")
    base_cb = f"conciliacion_bancaria_{ext_cb['desde']:%Y-%m-%d}_{ext_cb['hasta']:%Y-%m-%d}"
    dc1, dc2 = st.columns(2)
    with dc1:
        st.download_button("📊 Descargar Excel", data=_conc_excel_cache(r_cb, ext_cb, emisor_cb), file_name=f"{base_cb}.xlsx", key="cb_xlsx",
                           use_container_width=True, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with dc2:
        st.download_button("📄 Descargar PDF", data=_conc_pdf_cache(r_cb, ext_cb, emisor_cb), file_name=f"{base_cb}.pdf", mime="application/pdf",
                           key="cb_pdf", use_container_width=True)


# ==================================================================
# PÁGINA: EX INQUILINOS (historial, deuda y pagos de los inquilinos que ya salieron)
# ==================================================================
elif pagina == "🚪 Ex inquilinos":
    st.title("🚪 Ex inquilinos")
    st.caption(
        "Inquilinos que ya salieron. Su ficha y su deuda quedan archivadas a su nombre: si pagan después, registra el pago "
        "aquí y la deuda se actualiza. Esos cobros aparecen en la Rendición de alquileres marcados como «ex inquilino»."
    )
    try:
        historial_ex = cargar_historial()
        cerrados_ex = {t: cargar_periodos_cerrados(t) for t in ("alquiler", "electricidad", "agua")}
    except Exception as e:
        st.error(texto_error_historial("No se pudo leer el historial de inquilinos", e))
        st.stop()
    apts_ex = {a["id"]: a for a in cargar_apartamentos()}
    por_hist_ex = exinquilinos.agrupar_por_historial(cerrados_ex)
    vacio_ex = {"alquiler": [], "electricidad": [], "agua": []}

    filas_ex = []
    for h in historial_ex:
        d_ex = exinquilinos.deuda_ex_inquilino(por_hist_ex.get(h["id"], vacio_ex))
        filas_ex.append({"h": h, "deuda": d_ex, "codigo": (apts_ex.get(h.get("apartamento_id")) or {}).get("codigo") or "—"})
    if not filas_ex:
        st.info("Todavía no hay inquilinos en el historial. Cuando un inquilino se vaya, registra su salida en "
                "**Apartamentos → pestaña 🚪 Salida de inquilino**.")
        st.stop()

    solo_deuda_ex = st.checkbox("Mostrar solo ex inquilinos con deuda", value=True, key="ex_solo_deuda")
    visibles_ex = [f for f in filas_ex if not solo_deuda_ex or f["deuda"]["total"] > exinquilinos.TOLERANCIA]
    ek1, ek2, ek3 = st.columns(3)
    ek1.metric("Ex inquilinos con deuda", sum(1 for f in filas_ex if f["deuda"]["total"] > exinquilinos.TOLERANCIA))
    ek2.metric("Deuda total de ex inquilinos", fmt_money(sum(f["deuda"]["total"] for f in filas_ex)))
    ek3.metric("Ex inquilinos en el historial", len(filas_ex))
    if not visibles_ex:
        st.success("Ningún ex inquilino tiene deuda pendiente.")
        st.stop()

    st.dataframe(pd.DataFrame([{
        "Apartamento": f["codigo"], "Ex inquilino": exinquilinos.nombre_ex_inquilino(f["h"]),
        "Fecha de salida": (parse_fecha(f["h"].get("fecha_salida")) or "—") if f["h"].get("fecha_salida") else "—",
        "Alquiler": f["deuda"]["alquiler"], "Luz": f["deuda"]["luz"], "Agua": f["deuda"]["agua"], "Deuda total": f["deuda"]["total"],
    } for f in visibles_ex]), use_container_width=True, hide_index=True, column_config={
        c: st.column_config.NumberColumn(format="Bs %.2f") for c in ("Alquiler", "Luz", "Agua", "Deuda total")})

    idx_ex = st.selectbox(
        "Elige un ex inquilino para ver su ficha y registrar pagos", range(len(visibles_ex)), key="ex_sel",
        format_func=lambda i: (f'{visibles_ex[i]["codigo"]} — {exinquilinos.nombre_ex_inquilino(visibles_ex[i]["h"])} '
                               f'— debe {fmt_money(visibles_ex[i]["deuda"]["total"])}'))
    h = visibles_ex[idx_ex]["h"]
    apt_h = apts_ex.get(h.get("apartamento_id")) or {}
    apt_recibo = {"codigo": visibles_ex[idx_ex]["codigo"], "piso": apt_h.get("piso"),
                  "inquilino_nombre": exinquilinos.nombre_ex_inquilino(h)}

    with st.expander("📄 Ficha archivada del ex inquilino", expanded=False):
        etiquetas_ficha = {"inquilino_nombre": "Nombre", "celular": "Celular", "cedula_identidad": "Cédula de identidad",
                           "nacionalidad": "Nacionalidad", "referencia_nombre": "Referencia", "referencia_celular": "Celular de la referencia",
                           "fecha_ingreso": "Fecha de ingreso", "fecha_salida": "Fecha de salida", "garantia": "Garantía",
                           "monto_alquiler": "Alquiler mensual (Bs)", "tipo_contrato": "Tipo de contrato",
                           "observacion": "Observación de la salida", "registrado_por": "Salida registrada por"}
        ocultas = {"id", "apartamento_id", "created_at", "updated_at"}
        ficha = [(etiquetas_ficha.get(k, k.replace("_", " ").capitalize()), str(v)) for k, v in h.items()
                 if k not in ocultas and v not in (None, "")]
        st.dataframe(pd.DataFrame(ficha, columns=["Dato", "Valor"]), use_container_width=True, hide_index=True)

    # Periodos de este ex inquilino con todos los datos (lecturas incluidas, para los recibos)
    try:
        completos_ex = {
            "alquiler": [p for p in db.listar_periodos(apartamento_id=h["apartamento_id"]) if p.get("inquilino_historial_id") == h["id"]],
            "electricidad": [p for p in db.listar_periodos_servicio("electricidad", apartamento_id=h["apartamento_id"])
                             if p.get("inquilino_historial_id") == h["id"]],
            "agua": [p for p in db.listar_periodos_servicio("agua", apartamento_id=h["apartamento_id"])
                     if p.get("inquilino_historial_id") == h["id"]],
        }
    except Exception as e:
        st.error(texto_error_historial("No se pudieron leer los periodos del ex inquilino", e))
        st.stop()

    st.markdown("**Lo que debe, mes por mes**")
    filas_per = []
    for nombre_c, tipo_c, campo_c, _clave in exinquilinos.CONCEPTOS:
        for p in sorted(completos_ex[tipo_c], key=lambda p: (moras._clave_periodo(p) or (0, 0))):
            filas_per.append({"Concepto": nombre_c, "Mes": exinquilinos.etiqueta_periodo(p), "A cobrar": float(p.get("monto_esperado") or 0),
                              "Pagado": float(exinquilinos.pagado(p, campo_c)), "Saldo": exinquilinos.saldo(p, campo_c)})
    if filas_per:
        st.dataframe(pd.DataFrame(filas_per), use_container_width=True, hide_index=True, column_config={
            c: st.column_config.NumberColumn(format="Bs %.2f") for c in ("A cobrar", "Pagado", "Saldo")})
    else:
        st.info("Este ex inquilino no tiene periodos registrados.")

    st.divider()
    st.subheader("➕ Registrar un pago del ex inquilino")
    conceptos_pend = [(n, t, c) for n, t, c, _k in exinquilinos.CONCEPTOS if exinquilinos.periodos_con_saldo(completos_ex[t], c)]
    if not conceptos_pend:
        st.success("Este ex inquilino no tiene deuda pendiente.")
    else:
        sel_c = st.selectbox("Concepto", range(len(conceptos_pend)), format_func=lambda i: conceptos_pend[i][0], key=f'ex_concepto_{h["id"]}')
        nombre_c, tipo_c, campo_c = conceptos_pend[sel_c]
        con_saldo = exinquilinos.periodos_con_saldo(completos_ex[tipo_c], campo_c)
        sel_p = st.selectbox("Mes que paga", range(len(con_saldo)), key=f'ex_periodo_{h["id"]}_{tipo_c}',
                             format_func=lambda i: f'{exinquilinos.etiqueta_periodo(con_saldo[i])} — saldo {fmt_money(exinquilinos.saldo(con_saldo[i], campo_c))}')
        periodo_ex = con_saldo[sel_p]
        saldo_ex = exinquilinos.saldo(periodo_ex, campo_c)
        px1, px2 = st.columns(2)
        with px1:
            monto_ex = st.number_input("Monto abonado (Bs)", min_value=0.0, step=10.0, value=float(saldo_ex),
                                       key=f'ex_monto_{h["id"]}_{tipo_c}_{periodo_ex["id"]}')
        with px2:
            fecha_ex = st.date_input("Fecha del pago", value=recibo.hoy_bolivia(), format="DD/MM/YYYY", key=f'ex_fecha_{h["id"]}_{tipo_c}')
        metodo_ex = st.selectbox("Método de pago", METODOS_ABONO, key=f'ex_metodo_{h["id"]}_{tipo_c}')
        obs_ex = st.text_input("Observación (opcional)", key=f'ex_obs_{h["id"]}_{tipo_c}_{periodo_ex["id"]}')
        if st.button("💾 Registrar pago", key=f'ex_guardar_{h["id"]}_{tipo_c}'):
            error_ex = exinquilinos.validar_abono(monto_ex, saldo_ex)
            if error_ex:
                st.error(error_ex)
            else:
                datos_pago = {"periodo_id": periodo_ex["id"], "fecha": str(fecha_ex), "monto": monto_ex,
                              "metodo_pago": metodo_ex, "observacion": obs_ex or None}
                try:
                    if tipo_c == "alquiler":
                        db.crear_pago(datos_pago)
                    else:
                        db.crear_pago_servicio(tipo_c, datos_pago)
                    limpiar_cache()
                    st.success(f"Pago registrado. Saldo restante de {exinquilinos.etiqueta_periodo(periodo_ex)}: "
                               f"{fmt_money(max(saldo_ex - monto_ex, 0))}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    # Pagos ya registrados (con recibo y corrección)
    pagos_ex = [(n, t, c, p, a) for n, t, c, _k in exinquilinos.CONCEPTOS for p in completos_ex[t] for a in (p.get(c) or [])]
    if pagos_ex:
        st.divider()
        st.subheader("Pagos registrados")
        for nombre_c, tipo_c, campo_c, p, a in sorted(pagos_ex, key=lambda t: str(t[4].get("fecha")), reverse=True):
            with st.expander(f'{a["fecha"]} — {nombre_c} — {exinquilinos.etiqueta_periodo(p)} — {fmt_money(a["monto"])}'):
                mostrar_botones_recibo(a, p, apt_recibo, float(exinquilinos.pagado(p, campo_c)),
                                       key_sufijo=f'ex_{tipo_c}_{a["id"]}', servicio=None if tipo_c == "alquiler" else tipo_c)
                st.divider()
                _formulario_editar_abono(None if tipo_c == "alquiler" else tipo_c, a, f'ex_{tipo_c}')


# ==================================================================
# PÁGINA: INQUILINOS (solo lectura, para todos los usuarios)
# ==================================================================
elif pagina == "🏠 Inquilinos":
    st.title("🏠 Inquilinos por apartamento")
    st.caption("Consulta de datos. Es solo lectura: para corregir o actualizar un dato, avisa a un Administrador.")

    def _md(valor):
        """Texto del usuario seguro para st.markdown (sin interpretar *, _, $, etc.). Vacío -> —"""
        texto = str(valor).strip() if valor not in (None, "") else ""
        if not texto:
            return "—"
        for ch in "\\`*_[]$<>~|":
            texto = texto.replace(ch, "\\" + ch)
        return texto

    def _f(valor):
        fecha = parse_fecha(valor)
        return fecha.strftime("%d/%m/%Y") if fecha else "—"

    def _ficha(pares):
        for etiqueta, valor in pares:
            st.markdown(f"**{etiqueta}:** {valor}")

    apartamentos = cargar_apartamentos()
    if not apartamentos:
        st.info("No hay apartamentos registrados todavía.")
    else:
        with st.container(border=True):
            st.markdown("**Resumen de apartamentos**")
            st.dataframe(pd.DataFrame([{
                "Apartamento": a.get("codigo"), "Piso": a.get("piso"), "Estado": a.get("estado"),
                "Inquilino": a.get("inquilino_nombre") or "—", "Celular": a.get("celular") or "—",
                "Alquiler": float(a.get("monto_alquiler") or 0),
                "Aire acond.": aire_acondicionado.resumen(a.get("aire_acondicionado"), a.get("aire_acondicionado_propiedad"),
                                                          con_propiedad="aire_acondicionado_propiedad" in a),
                "Contrato": a.get("estado_contrato") or "—",
            } for a in apartamentos]), use_container_width=True, hide_index=True,
                column_config={"Alquiler": st.column_config.NumberColumn(format="Bs %.2f")})

        etiquetas_inq = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "vacío"}' for a in apartamentos]
        idx_inq = st.selectbox("Apartamento", range(len(apartamentos)), format_func=lambda i: etiquetas_inq[i],
                               key="inq_apartamento")
        apt = apartamentos[idx_inq]

        st.subheader(f'{apt["codigo"]} · {apt.get("piso") or ""}')
        if apt.get("estado") != "Ocupado":
            st.info("Este apartamento está desocupado.")

        ci1, ci2 = st.columns(2)
        with ci1:
            with st.container(border=True):
                st.markdown("**👤 Inquilino**")
                _ficha([("Nombre", _md(apt.get("inquilino_nombre"))), ("Celular", _md(apt.get("celular"))),
                        ("Cédula de identidad", _md(apt.get("cedula_identidad"))),
                        ("Nacionalidad", _md(apt.get("nacionalidad"))),
                        ("Fecha de nacimiento", _f(apt.get("fecha_nacimiento")))])
            with st.container(border=True):
                st.markdown("**👥 Referencia**")
                _ficha([("Nombre", _md(apt.get("referencia_nombre"))),
                        ("Parentesco", _md(apt.get("referencia_parentesco"))),
                        ("Celular", _md(apt.get("referencia_celular")))])
        with ci2:
            with st.container(border=True):
                st.markdown("**🏠 Ocupación**")
                datos_ocupacion = [("Estado", _md(apt.get("estado"))), ("Fecha de ingreso", _f(apt.get("fecha_ingreso")))]
                if apt.get("tipo_contrato") == "Anticrético":
                    moneda_ac = "USD" if apt.get("anticretico_moneda") == "USD" else "Bs"
                    datos_ocupacion.extend([
                        ("Capital anticrético", f"{moneda_ac} {float(apt.get('monto_anticretico') or 0):,.2f}"),
                        ("Fecha de entrega", _f(apt.get("anticretico_fecha_entrega"))),
                        ("Fecha pactada de devolución", _f(apt.get("anticretico_fecha_devolucion"))),
                        ("Condiciones de devolución", _md(apt.get("anticretico_condiciones"))),
                    ])
                else:
                    datos_ocupacion.extend([
                        ("Día de pago", _md(apt.get("dia_pago"))),
                        ("Alquiler mensual", fmt_money(apt.get("monto_alquiler") or 0)),
                    ])
                datos_ocupacion.extend([
                    ("Aire acondicionado", aire_acondicionado.descripcion(
                        apt.get("aire_acondicionado"), apt.get("aire_acondicionado_propiedad"),
                        con_propiedad="aire_acondicionado_propiedad" in apt)),
                    ("Garantía", _md(apt.get("garantia"))), ("Amoblado", _md(apt.get("amoblado"))),
                    ("Detalle", _md(apt.get("detalle")))])
                _ficha(datos_ocupacion)
            with st.container(border=True):
                st.markdown("**📄 Contrato**")
                _ficha([("Tipo", _md(apt.get("tipo_contrato"))), ("Estado", _md(apt.get("estado_contrato"))),
                        ("Fecha inicio", _f(apt.get("contrato_fecha_inicio"))),
                        ("Fecha fin", _f(apt.get("contrato_fecha_fin"))),
                        ("Observaciones", _md(apt.get("contrato_observaciones")))])

elif pagina == "🤝 Compromisos de pago":
    st.title("🤝 Compromisos de pago")
    st.caption(
        "Historial de los motivos de retraso que informa el inquilino y de los acuerdos de pago (compromiso, "
        "fecha plazo y monto). Todos los usuarios pueden registrar y editar; solo el Administrador puede eliminar."
    )
    mensaje_flash = st.session_state.pop("compromiso_msg", None)
    if mensaje_flash:
        st.success(mensaje_flash)

    hoy_c = recibo.hoy_bolivia()
    nombre_c = usuario_actual.get("nombre") or usuario_actual.get("username")
    apartamentos = cargar_apartamentos()
    try:
        todos_comp = cargar_compromisos()
    except Exception as e:
        st.error("No se pudo leer el historial de compromisos. Si es la primera vez que usas esta sección, "
                 "ejecuta el archivo `migracion_compromisos_pago.sql` en el SQL Editor de Supabase.")
        st.caption(f"Detalle técnico: {e}")
        st.stop()

    ocupados = [a for a in apartamentos if a.get("estado") == "Ocupado"]
    codigo_por_id = {a["id"]: a.get("codigo") for a in apartamentos}

    def _fmt_f(valor):
        f = parse_fecha(valor)
        return f.strftime("%d/%m/%Y") if f else "—"

    def _codigo_de(c):
        return (c.get("apartamentos") or {}).get("codigo") or codigo_por_id.get(c["apartamento_id"]) or "—"

    n_form = st.session_state.get("comp_form_n", 0)   # cambia al guardar: así el formulario se limpia solo si salió bien
    tab_nuevo_c, tab_hist_c = st.tabs(["➕ Nuevo compromiso", "📋 Historial y edición"])

    # ---------------- Nuevo compromiso ----------------
    with tab_nuevo_c:
        if not ocupados:
            st.info("No hay apartamentos ocupados.")
        else:
            etiquetas_c = [f'{a["codigo"]} — {a.get("inquilino_nombre") or "sin nombre"}' for a in ocupados]
            i_c = st.selectbox("Apartamento", range(len(ocupados)), format_func=lambda i: etiquetas_c[i],
                               key="comp_apto")
            apt_c = ocupados[i_c]

            # Contexto: deuda actual, con la misma regla del Dashboard y del estado de cuenta
            alq_c = [p for p in cargar_periodos_abiertos("alquiler") if p["apartamento_id"] == apt_c["id"]]
            elec_c = [p for p in cargar_periodos_abiertos("electricidad") if p["apartamento_id"] == apt_c["id"]]
            d_c = moras.deuda_real_inquilino(apt_c, alq_c, elec_c, hoy_c)
            if d_c["aplica"]:
                m_atr = d_c["alquiler"]["meses_atrasados"]
                st.info(
                    f'Deuda actual — alquiler: {fmt_money(d_c["alquiler"]["deuda"])} '
                    f'({m_atr} mes{"es" if m_atr != 1 else ""} atrasado{"s" if m_atr != 1 else ""}) · '
                    f'electricidad: {fmt_money(d_c["electricidad"]["deuda"])} · '
                    f'**total: {fmt_money(d_c["deuda_total"])}**')
            else:
                st.caption(d_c["motivo"])
            abiertos = [c for c in todos_comp if c["apartamento_id"] == apt_c["id"]
                        and compromisos.estado_efectivo(c, hoy_c) in ("Pendiente", "Vencido")]
            if abiertos:
                st.warning(f'Este apartamento ya tiene {len(abiertos)} compromiso(s) pendiente(s) o vencido(s). '
                           'Revisa el historial antes de registrar otro.')

            with st.form(f"form_nuevo_compromiso_{n_form}"):
                fecha_reg = st.date_input("Fecha del registro", value=hoy_c, format="DD/MM/YYYY",
                                          key=f"cn_fecha_{n_form}")
                motivo = st.text_area("Motivo del retraso (lo que informó el inquilino)", max_chars=2000,
                                      key=f"cn_motivo_{n_form}")
                compromiso_txt = st.text_area(
                    "Compromiso asumido (opcional)", max_chars=2000, key=f"cn_comp_{n_form}",
                    placeholder='Ej. "Pagará la mitad esta semana y el resto el 30"')
                cp1, cp2 = st.columns(2)
                with cp1:
                    plazo = st.date_input("Fecha plazo (opcional)", value=None, format="DD/MM/YYYY",
                                          key=f"cn_plazo_{n_form}")
                with cp2:
                    monto = st.number_input("Monto acordado a pagar (Bs)", min_value=0.0, step=10.0,
                                            format="%.2f", value=0.0, key=f"cn_monto_{n_form}")
                st.caption(f"Se guardará como registrado por: **{nombre_c}**")
                guardar_c = st.form_submit_button("💾 Guardar compromiso")

            if guardar_c:
                errores = compromisos.validar_compromiso(motivo, compromiso_txt, fecha_reg, plazo, monto)
                for err in errores:
                    st.error(err)
                if not errores:
                    try:
                        db.crear_compromiso(compromisos.armar_registro(
                            motivo, compromiso_txt, fecha_reg, plazo, monto, "Pendiente", nombre_c, apartamento=apt_c))
                        limpiar_cache()
                        st.session_state["comp_form_n"] = n_form + 1
                        st.session_state["compromiso_msg"] = f'Compromiso registrado para {apt_c["codigo"]}.'
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo guardar: {e}")

    # ---------------- Historial y edición ----------------
    with tab_hist_c:
        ids_con_datos = {c["apartamento_id"] for c in todos_comp}
        apts_filtro = [a for a in apartamentos if a.get("estado") == "Ocupado" or a["id"] in ids_con_datos]
        nombres_apt = {a["id"]: f'{a["codigo"]} — {a.get("inquilino_nombre") or "sin inquilino"}' for a in apts_filtro}
        f1, f2 = st.columns(2)
        with f1:
            filtro_id = st.selectbox("Apartamento", [None] + [a["id"] for a in apts_filtro],
                                     format_func=lambda i: "Todos los apartamentos" if i is None else nombres_apt[i],
                                     key="comp_filtro_apto")
        with f2:
            filtro_estado = st.selectbox("Estado", ["Todos", "Pendiente", "Vencido", "Cumplido", "Incumplido"],
                                         key="comp_filtro_estado")

        base_c = [c for c in todos_comp if filtro_id is None or c["apartamento_id"] == filtro_id]
        pend_c = [c for c in base_c if compromisos.estado_efectivo(c, hoy_c) in ("Pendiente", "Vencido")]
        venc_c = [c for c in base_c if compromisos.estado_efectivo(c, hoy_c) == compromisos.ESTADO_VENCIDO]
        k1, k2, k3 = st.columns(3)
        k1.metric("Pendientes", len(pend_c))
        k2.metric("Vencidos", len(venc_c))
        k3.metric("Monto acordado por cobrar", fmt_money(sum(float(c.get("monto_comprometido") or 0) for c in pend_c)))

        filtrados = [c for c in base_c if filtro_estado == "Todos"
                     or compromisos.estado_efectivo(c, hoy_c) == filtro_estado]
        filtrados = (compromisos.ordenar_por_plazo(filtrados) if filtro_estado in ("Pendiente", "Vencido")
                     else compromisos.ordenar_historial(filtrados))

        if not filtrados:
            st.info("No hay compromisos registrados con ese filtro.")
        else:
            iconos = {"Pendiente": "🟡 Pendiente", "Vencido": "🔴 Vencido",
                      "Cumplido": "🟢 Cumplido", "Incumplido": "⚫ Incumplido"}
            st.dataframe(pd.DataFrame([{
                "Registro": _fmt_f(c.get("fecha_registro")),
                "Apartamento": _codigo_de(c),
                "Inquilino": c.get("inquilino_nombre") or "—",
                "Motivo del retraso": c.get("motivo_retraso") or "—",
                "Compromiso": c.get("compromiso") or "—",
                "Fecha plazo": _fmt_f(c.get("fecha_plazo")),
                "Monto acordado": float(c["monto_comprometido"]) if c.get("monto_comprometido") is not None else None,
                "Estado": iconos[compromisos.estado_efectivo(c, hoy_c)],
                "Registrado por": c.get("registrado_por") or "—",
                "Editado por": c.get("editado_por") or "—",
            } for c in filtrados]), use_container_width=True, hide_index=True,
                column_config={
                    "Motivo del retraso": st.column_config.TextColumn(width="large"),
                    "Compromiso": st.column_config.TextColumn(width="large"),
                    "Monto acordado": st.column_config.NumberColumn(format="Bs %.2f"),
                })

            st.divider()
            st.markdown("### ✏️ Editar un compromiso")
            por_id = {c["id"]: c for c in filtrados}

            def _etiqueta_comp(cid):
                c = por_id[cid]
                motivo_corto = (c.get("motivo_retraso") or "").replace("\n", " ")
                if len(motivo_corto) > 45:
                    motivo_corto = motivo_corto[:45] + "…"
                return f'{_fmt_f(c.get("fecha_registro"))} · {_codigo_de(c)} · {motivo_corto}'

            cid = st.selectbox("Compromiso", list(por_id.keys()), format_func=_etiqueta_comp, key="comp_editar_sel")
            c_sel = por_id[cid]
            with st.form(f"form_edit_compromiso_{cid}"):
                e_fecha = st.date_input("Fecha del registro", value=parse_fecha(c_sel.get("fecha_registro")) or hoy_c,
                                        format="DD/MM/YYYY", key=f"ce_fecha_{cid}")
                e_motivo = st.text_area("Motivo del retraso", value=c_sel.get("motivo_retraso") or "",
                                        max_chars=2000, key=f"ce_motivo_{cid}")
                e_comp = st.text_area("Compromiso asumido", value=c_sel.get("compromiso") or "",
                                      max_chars=2000, key=f"ce_comp_{cid}")
                ce1, ce2 = st.columns(2)
                with ce1:
                    e_plazo = st.date_input("Fecha plazo (opcional)", value=parse_fecha(c_sel.get("fecha_plazo")),
                                            format="DD/MM/YYYY", key=f"ce_plazo_{cid}")
                    quitar_plazo = (st.checkbox("Quitar la fecha plazo", key=f"ce_quitar_{cid}")
                                    if c_sel.get("fecha_plazo") else False)
                with ce2:
                    e_monto = st.number_input("Monto acordado a pagar (Bs)", min_value=0.0, step=10.0, format="%.2f",
                                              value=float(c_sel.get("monto_comprometido") or 0), key=f"ce_monto_{cid}")
                estado_actual = c_sel.get("estado") if c_sel.get("estado") in compromisos.ESTADOS else "Pendiente"
                e_estado = st.selectbox("Estado", compromisos.ESTADOS, index=compromisos.ESTADOS.index(estado_actual),
                                        key=f"ce_estado_{cid}")
                st.caption(f'Registrado por **{c_sel.get("registrado_por") or "—"}** · '
                           f'última edición por **{c_sel.get("editado_por") or "—"}**')
                if es_admin:
                    confirmar_borrar = st.checkbox("Confirmo que quiero eliminar este compromiso",
                                                   key=f"ce_confirmar_{cid}")
                    cg, cd = st.columns(2)
                    guardar_e = cg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                    eliminar_e = cd.form_submit_button("🗑️ Eliminar", use_container_width=True)
                else:
                    confirmar_borrar, eliminar_e = False, False
                    guardar_e = st.form_submit_button("💾 Guardar cambios", use_container_width=True)

            if guardar_e:
                plazo_final = None if quitar_plazo else e_plazo
                errores = compromisos.validar_compromiso(e_motivo, e_comp, e_fecha, plazo_final, e_monto)
                for err in errores:
                    st.error(err)
                if not errores:
                    try:
                        db.actualizar_compromiso(cid, compromisos.armar_registro(
                            e_motivo, e_comp, e_fecha, plazo_final, e_monto, e_estado, nombre_c))
                        limpiar_cache()
                        st.session_state["compromiso_msg"] = "Compromiso actualizado."
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo actualizar: {e}")

            if eliminar_e and es_admin:
                if not confirmar_borrar:
                    st.warning("Marca la casilla de confirmación para poder eliminar.")
                else:
                    try:
                        db.eliminar_compromiso(cid)
                        limpiar_cache()
                        st.session_state["compromiso_msg"] = "Compromiso eliminado."
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo eliminar: {e}")

elif pagina == "🔌 Servicios Básicos":
    st.title("🔌 Servicios Básicos")
    st.caption("Datos de contacto de los proveedores de servicios básicos del edificio "
               "(electricidad, agua, internet, gas, etc.).")
    mensaje_flash = st.session_state.pop("servicio_msg", None)
    if mensaje_flash:
        st.success(mensaje_flash)
    try:
        servicios = servicios_basicos.ordenar(cargar_servicios_basicos())
    except Exception as e:
        st.error("No se pudo leer la lista de servicios básicos.")
        st.caption(f"Detalle técnico: {e}")
        st.stop()
    usuarios_por_id_sb = {u["id"]: (u.get("nombre") or u.get("username")) for u in cargar_todos_los_usuarios()}
    n_form_sb = st.session_state.get("serv_form_n", 0)   # cambia al guardar: el formulario se limpia solo si salió bien

    tab_nuevo_sb, tab_lista_sb = st.tabs(["➕ Nuevo servicio", "📋 Lista"])

    # ---------------- Nuevo servicio ----------------
    with tab_nuevo_sb:
        with st.form(f"form_nuevo_servicio_{n_form_sb}"):
            sb_nombre = st.text_input("Nombre del Servicio", placeholder='Ej. "Electricidad", "Agua", "Internet"',
                                      max_chars=100, key=f"sbn_nombre_{n_form_sb}")
            sb_empresa = st.text_input("Empresa proveedora", max_chars=150, key=f"sbn_empresa_{n_form_sb}")
            sbc1, sbc2 = st.columns(2)
            with sbc1:
                sb_telefono = st.text_input("Teléfono", max_chars=50, key=f"sbn_tel_{n_form_sb}")
            with sbc2:
                sb_codigo = st.text_input("Código (cliente / cuenta / NIS)", max_chars=80, key=f"sbn_cod_{n_form_sb}")
            sb_titular = st.text_input("Titular", max_chars=150, key=f"sbn_titular_{n_form_sb}")
            sb_obs = st.text_area("Observación", max_chars=2000, key=f"sbn_obs_{n_form_sb}")
            guardar_sb = st.form_submit_button("💾 Guardar servicio")
        if guardar_sb:
            errores_sb = servicios_basicos.validar_servicio(sb_nombre, sb_empresa, sb_telefono, sb_codigo, sb_titular, sb_obs)
            for err in errores_sb:
                st.error(err)
            if not errores_sb:
                try:
                    db.crear_servicio_basico(servicios_basicos.armar_registro(
                        sb_nombre, sb_empresa, sb_telefono, sb_codigo, sb_titular, sb_obs,
                        creado_por=usuario_actual.get("id")))
                    limpiar_cache()
                    st.session_state["serv_form_n"] = n_form_sb + 1
                    st.session_state["servicio_msg"] = "Servicio guardado."
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo guardar: {e}")

    # ---------------- Lista ----------------
    with tab_lista_sb:
        if not servicios:
            st.info("Todavía no hay servicios registrados.")
        else:
            texto_sb = st.text_input("Buscar", placeholder="Servicio, empresa, teléfono, código o titular",
                                     key="serv_buscar")
            visibles = servicios_basicos.filtrar(servicios, texto_sb)
            if not visibles:
                st.info("Ningún servicio coincide con la búsqueda.")
            else:
                st.dataframe(pd.DataFrame([{
                    "Servicio": x.get("nombre_servicio") or "", "Empresa proveedora": x.get("empresa_proveedor") or "",
                    "Teléfono": x.get("telefono") or "", "Código": x.get("codigo") or "", "Titular": x.get("titular") or "",
                    "Observación": x.get("observacion") or "",
                    "Registrado por": usuarios_por_id_sb.get(x.get("creado_por")) or "—",
                } for x in visibles]), use_container_width=True, hide_index=True,
                    column_config={"Observación": st.column_config.TextColumn(width="large")})

                st.divider()
                st.markdown("### ✏️ Editar un servicio")
                por_id_sb = {x["id"]: x for x in visibles}
                id_sb = st.selectbox(
                    "Servicio", list(por_id_sb.keys()), key="serv_editar_sel",
                    format_func=lambda i: f'{por_id_sb[i].get("nombre_servicio")} — {por_id_sb[i].get("empresa_proveedor") or "sin empresa"}')
                x_sel = por_id_sb[id_sb]
                with st.form(f"form_editar_servicio_{id_sb}"):
                    e_nombre = st.text_input("Nombre del Servicio", value=x_sel.get("nombre_servicio") or "",
                                             max_chars=100, key=f"sbe_nombre_{id_sb}")
                    e_empresa = st.text_input("Empresa proveedora", value=x_sel.get("empresa_proveedor") or "",
                                              max_chars=150, key=f"sbe_empresa_{id_sb}")
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_telefono = st.text_input("Teléfono", value=x_sel.get("telefono") or "", max_chars=50,
                                                   key=f"sbe_tel_{id_sb}")
                    with ec2:
                        e_codigo = st.text_input("Código (cliente / cuenta / NIS)", value=x_sel.get("codigo") or "",
                                                 max_chars=80, key=f"sbe_cod_{id_sb}")
                    e_titular = st.text_input("Titular", value=x_sel.get("titular") or "", max_chars=150,
                                              key=f"sbe_titular_{id_sb}")
                    e_obs = st.text_area("Observación", value=x_sel.get("observacion") or "", max_chars=2000,
                                         key=f"sbe_obs_{id_sb}")
                    if es_admin:
                        confirmar_borrar_sb = st.checkbox("Confirmo que quiero eliminar este servicio",
                                                          key=f"sbe_confirmar_{id_sb}")
                        cgs, cds = st.columns(2)
                        guardar_e_sb = cgs.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        eliminar_e_sb = cds.form_submit_button("🗑️ Eliminar", use_container_width=True)
                    else:
                        confirmar_borrar_sb, eliminar_e_sb = False, False
                        guardar_e_sb = st.form_submit_button("💾 Guardar cambios", use_container_width=True)

                if guardar_e_sb:
                    errores_e = servicios_basicos.validar_servicio(e_nombre, e_empresa, e_telefono, e_codigo, e_titular, e_obs)
                    for err in errores_e:
                        st.error(err)
                    if not errores_e:
                        try:
                            db.actualizar_servicio_basico(id_sb, servicios_basicos.armar_registro(
                                e_nombre, e_empresa, e_telefono, e_codigo, e_titular, e_obs))
                            limpiar_cache()
                            st.session_state["servicio_msg"] = "Servicio actualizado."
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo actualizar: {e}")
                if eliminar_e_sb and es_admin:
                    if not confirmar_borrar_sb:
                        st.warning("Marca la casilla de confirmación para poder eliminar.")
                    else:
                        try:
                            db.eliminar_servicio_basico(id_sb)
                            limpiar_cache()
                            st.session_state["servicio_msg"] = "Servicio eliminado."
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo eliminar: {e}")

elif pagina == "✅ Pendientes":
    st.title("✅ Pendientes")
    st.caption("Tareas y actividades del edificio: cualquier colaborador puede crearlas, "
               "asignarlas y actualizar su estado.")

    usuarios_activos = cargar_usuarios_activos()
    usuarios_todos = cargar_todos_los_usuarios()
    usuarios_por_id = {u["id"]: u for u in usuarios_todos}
    apartamentos_pend = cargar_apartamentos()
    nombre_usuario_actual = usuario_actual.get("nombre") or usuario_actual.get("username")

    def nombre_de(u):
        return u.get("nombre") or u.get("username") or "—"

    tab_nuevo, tab_tablero = st.tabs(["➕ Nuevo pendiente", "📋 Tablero"])

    # ---------------- Nuevo pendiente ----------------
    with tab_nuevo:
        with st.form("form_nuevo_pendiente", clear_on_submit=True):
            titulo = st.text_input("Título", placeholder='Ej. "Cambiar foco del pasillo piso 2"')
            descripcion = st.text_area("Descripción (opcional)")
            que_falta = st.text_input(
                "¿Qué falta para realizarlo? (opcional)",
                placeholder='Ej. "Comprar lampas", "Contratar personal", "Terminar tumbado antes"')
            observacion = st.text_area("Observación (opcional)")

            col1, col2, col3 = st.columns(3)
            with col1:
                prioridad = st.selectbox("Prioridad", PRIORIDADES_PENDIENTE, index=2)
            with col2:
                opciones_asignado = ["Sin asignar"] + [nombre_de(u) for u in usuarios_activos]
                asignado_sel = st.selectbox("Asignar a (opcional)", opciones_asignado)
            with col3:
                fecha_limite = st.date_input("Fecha límite (opcional)", value=None, format="DD/MM/YYYY")

            opciones_apto = ["(General, sin apartamento)"] + [f'{a["codigo"]} — {a.get("inquilino_nombre") or ""}'
                                                                for a in apartamentos_pend]
            apto_sel = st.selectbox("Apartamento relacionado (opcional)", opciones_apto)

            st.caption(f"Creado por: **{nombre_usuario_actual}**")
            guardar = st.form_submit_button("💾 Crear pendiente")

            if guardar:
                if not titulo.strip():
                    st.error("El título es obligatorio.")
                else:
                    try:
                        asignado_a_id = None
                        if asignado_sel != "Sin asignar":
                            idx = opciones_asignado.index(asignado_sel) - 1
                            asignado_a_id = usuarios_activos[idx]["id"]
                        apartamento_id_sel = None
                        if apto_sel != "(General, sin apartamento)":
                            idx_a = opciones_apto.index(apto_sel) - 1
                            apartamento_id_sel = apartamentos_pend[idx_a]["id"]

                        db.crear_pendiente({
                            "titulo": titulo.strip(),
                            "descripcion": descripcion or None,
                            "que_falta": que_falta or None,
                            "observacion": observacion or None,
                            "prioridad": prioridad,
                            "estado": "Pendiente",
                            "asignado_a": asignado_a_id,
                            "creado_por": usuario_actual.get("id"),
                            "apartamento_id": apartamento_id_sel,
                            "fecha_limite": str(fecha_limite) if fecha_limite else None,
                        })
                        limpiar_cache()
                        st.success("Pendiente creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    # ---------------- Tablero / listado ----------------
    with tab_tablero:
        colf1, colf2, colf3 = st.columns(3)
        with colf1:
            filtro_estado = st.selectbox("Estado", ["Todos"] + ESTADOS_PENDIENTE, key="pend_filtro_estado")
        with colf2:
            filtro_prioridad = st.selectbox("Prioridad", ["Todas"] + PRIORIDADES_PENDIENTE, key="pend_filtro_prioridad")
        with colf3:
            opciones_filtro_asig = ["Todos"] + [nombre_de(u) for u in usuarios_activos]
            filtro_asignado = st.selectbox("Asignado a", opciones_filtro_asig, key="pend_filtro_asignado")

        asignado_a_filtro_id = None
        if filtro_asignado != "Todos":
            idx_f = opciones_filtro_asig.index(filtro_asignado) - 1
            asignado_a_filtro_id = usuarios_activos[idx_f]["id"]

        pendientes = cargar_pendientes(
            estado=None if filtro_estado == "Todos" else filtro_estado,
            prioridad=None if filtro_prioridad == "Todas" else filtro_prioridad,
            asignado_a=asignado_a_filtro_id,
        )

        if not pendientes:
            st.info("No hay pendientes que coincidan con el filtro.")
        else:
            orden_prioridad = {"Urgente": 0, "Alta": 1, "Media": 2, "Baja": 3}
            pendientes = sorted(pendientes, key=lambda p: orden_prioridad.get(p["prioridad"], 9))

            colm1, colm2, colm3 = st.columns(3)
            colm1.metric("⏳ Pendientes", sum(1 for p in pendientes if p["estado"] == "Pendiente"))
            colm2.metric("🔧 En Proceso", sum(1 for p in pendientes if p["estado"] == "En Proceso"))
            colm3.metric("✅ Terminados", sum(1 for p in pendientes if p["estado"] == "Terminado"))

            st.divider()

            for p in pendientes:
                asignado_info = usuarios_por_id.get(p.get("asignado_a"))
                creador_info = usuarios_por_id.get(p.get("creado_por"))
                apto_info = p.get("apartamentos")
                asignado_txt = nombre_de(asignado_info) if asignado_info else "Sin asignar"
                apto_txt = f' · 🏠 {apto_info["codigo"]}' if apto_info else ""
                vencida = False
                if p.get("fecha_limite") and p["estado"] != "Terminado":
                    fl = parse_fecha(p["fecha_limite"])
                    vencida = bool(fl and fl < recibo.hoy_bolivia())

                titulo_linea = (f'{COLOR_PRIORIDAD.get(p["prioridad"], "")} **{p["titulo"]}**  '
                                 f'{ICONO_ESTADO.get(p["estado"], "")} _{p["estado"]}_'
                                 + (" ⚠️ Vencido" if vencida else ""))

                with st.expander(titulo_linea):
                    if p.get("descripcion"):
                        st.write(p["descripcion"])
                    st.caption(f'Prioridad: **{p["prioridad"]}** · Asignado a: **{asignado_txt}**{apto_txt}'
                               + (f' · Vence: {p["fecha_limite"]}' if p.get("fecha_limite") else ""))
                    if p.get("que_falta"):
                        st.markdown(f'🧰 **¿Qué falta?:** {p["que_falta"]}')
                    if p.get("observacion"):
                        st.markdown(f'📝 **Observación:** {p["observacion"]}')
                    if p.get("creado_por"):
                        st.caption(f'Creado por {nombre_de(creador_info)} el {str(p["created_at"])[:10]}')

                    with st.form(f'form_pendiente_{p["id"]}'):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            nuevo_estado = st.selectbox("Estado", ESTADOS_PENDIENTE,
                                                         index=ESTADOS_PENDIENTE.index(p["estado"]),
                                                         key=f'pend_estado_{p["id"]}')
                        with col2:
                            nueva_prioridad = st.selectbox("Prioridad", PRIORIDADES_PENDIENTE,
                                                            index=PRIORIDADES_PENDIENTE.index(p["prioridad"]),
                                                            key=f'pend_prioridad_{p["id"]}')
                        with col3:
                            opciones_asig_edit = ["Sin asignar"] + [nombre_de(u) for u in usuarios_activos]
                            idx_actual = 0
                            if asignado_info:
                                for i, u in enumerate(usuarios_activos):
                                    if u["id"] == asignado_info["id"]:
                                        idx_actual = i + 1
                                        break
                            nuevo_asignado = st.selectbox("Asignado a (opcional)", opciones_asig_edit,
                                                           index=idx_actual, key=f'pend_asignado_{p["id"]}')

                        nuevo_titulo = st.text_input("Título", value=p["titulo"], key=f'pend_titulo_{p["id"]}')
                        nueva_desc = st.text_area("Descripción", value=p.get("descripcion") or "",
                                                   key=f'pend_desc_{p["id"]}')
                        nuevo_que_falta = st.text_input("¿Qué falta para realizarlo?",
                                                         value=p.get("que_falta") or "",
                                                         key=f'pend_quefalta_{p["id"]}')
                        nueva_observacion = st.text_area("Observación", value=p.get("observacion") or "",
                                                          key=f'pend_obs_{p["id"]}')
                        nueva_fecha_limite = st.date_input(
                            "Fecha límite", value=parse_fecha(p.get("fecha_limite")), format="DD/MM/YYYY",
                            key=f'pend_fecha_{p["id"]}')

                        colg, cold = st.columns(2)
                        guardar_p = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        eliminar_p = cold.form_submit_button("🗑️ Eliminar", use_container_width=True)

                        if guardar_p:
                            try:
                                nuevo_asignado_id = None
                                if nuevo_asignado != "Sin asignar":
                                    idx_na = opciones_asig_edit.index(nuevo_asignado) - 1
                                    nuevo_asignado_id = usuarios_activos[idx_na]["id"]

                                payload = {
                                    "titulo": nuevo_titulo.strip() or p["titulo"],
                                    "descripcion": nueva_desc or None,
                                    "que_falta": nuevo_que_falta or None,
                                    "observacion": nueva_observacion or None,
                                    "prioridad": nueva_prioridad,
                                    "asignado_a": nuevo_asignado_id,
                                    "fecha_limite": str(nueva_fecha_limite) if nueva_fecha_limite else None,
                                }
                                if nuevo_estado != p["estado"]:
                                    db.cambiar_estado_pendiente(p["id"], nuevo_estado)
                                db.actualizar_pendiente(p["id"], payload)
                                limpiar_cache()
                                st.success("Pendiente actualizado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar: {e}")

                        if eliminar_p:
                            try:
                                db.eliminar_pendiente(p["id"])
                                limpiar_cache()
                                st.success("Pendiente eliminado.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: REUNIONES (área administrativa)
# Solo el Administrador puede crear/editar; el resto solo visualiza.
# ==================================================================
elif pagina == "🗒️ Reuniones":
    st.title("🗒️ Reuniones con el Área Administrativa")

    usuarios_todos_reu = cargar_todos_los_usuarios()
    usuarios_activos_reu = cargar_usuarios_activos()
    usuarios_por_id_reu = {u["id"]: u for u in usuarios_todos_reu}

    # Mapa reunion_id -> [usuario_id, ...], armado en Python en vez de con un
    # embed anidado (reuniones -> reuniones_participantes -> usuarios), que
    # resultó frágil en la librería de Supabase.
    participantes_ids_por_reunion = {}
    for fila in cargar_participantes_reuniones():
        participantes_ids_por_reunion.setdefault(fila["reunion_id"], []).append(fila["usuario_id"])

    def _nombre_usuario_reu(u):
        return u.get("nombre") or u.get("username") or "—"

    def _participantes_de(r):
        """Nombres de los usuarios del sistema que participaron en la reunión r."""
        ids = participantes_ids_por_reunion.get(r["id"], [])
        return [_nombre_usuario_reu(usuarios_por_id_reu[uid]) for uid in ids if uid in usuarios_por_id_reu]

    def _mostrar_reunion(r):
        """Vista de solo lectura de una reunión (usada tanto por Administrador como Cobrador)."""
        st.markdown(f'📅 **{r["fecha"]}**')
        st.markdown("**Puntos tratados:**")
        st.write(r["puntos_tratados"])
        if r.get("descripcion_acuerdos"):
            st.markdown("**Lo acordado:**")
            st.write(r["descripcion_acuerdos"])
        nombres_participantes = _participantes_de(r)
        partes = []
        if nombres_participantes:
            partes.append("👤 " + ", ".join(nombres_participantes))
        if r.get("invitados"):
            partes.append("🙋 Invitados: " + r["invitados"])
        if partes:
            st.caption(" · ".join(partes))
        if r.get("creado_por"):
            creador = usuarios_por_id_reu.get(r["creado_por"])
            if creador:
                st.caption(f'Registrado por {_nombre_usuario_reu(creador)}')

    if not es_admin:
        st.caption("Solo el Administrador puede crear o editar reuniones. Aquí puedes consultarlas.")
        reuniones = cargar_reuniones()
        if not reuniones:
            st.info("Todavía no hay reuniones registradas.")
        else:
            for r in reuniones:
                with st.expander(f'{r["fecha"]} — {(r["puntos_tratados"] or "")[:60]}'):
                    _mostrar_reunion(r)

    else:
        tab_nueva, tab_historial = st.tabs(["➕ Nueva reunión", "📋 Historial"])

        with tab_nueva:
            with st.form("form_nueva_reunion", clear_on_submit=True):
                fecha_reunion = st.date_input("Fecha de la reunión", value=recibo.hoy_bolivia(), format="DD/MM/YYYY")
                puntos_tratados = st.text_area(
                    "Puntos tratados", height=120,
                    placeholder="Ej.\n- Estado de cobranza del mes\n- Mantenimiento del ascensor\n- Otros temas")
                descripcion_acuerdos = st.text_area(
                    "Descripción de lo acordado", height=100,
                    placeholder="Ej. Se acuerda solicitar 3 cotizaciones para el mantenimiento del ascensor...")

                opciones_participantes = [_nombre_usuario_reu(u) for u in usuarios_activos_reu]
                participantes_sel = st.multiselect("Participantes (usuarios del sistema)", opciones_participantes)
                invitados = st.text_input(
                    "Invitados (personas externas, opcional)",
                    placeholder="Ej. Juan Pérez (propietario PB-01), representante de la empresa X")

                st.caption(f'Registrado por: **{usuario_actual.get("nombre") or usuario_actual.get("username")}**')
                guardar = st.form_submit_button("💾 Guardar reunión")

                if guardar:
                    if not puntos_tratados.strip():
                        st.error("Los puntos tratados son obligatorios.")
                    else:
                        try:
                            ids_participantes = [
                                usuarios_activos_reu[opciones_participantes.index(nombre)]["id"]
                                for nombre in participantes_sel
                            ]
                            db.crear_reunion({
                                "fecha": str(fecha_reunion),
                                "puntos_tratados": puntos_tratados.strip(),
                                "descripcion_acuerdos": descripcion_acuerdos or None,
                                "invitados": invitados or None,
                                "creado_por": usuario_actual.get("id"),
                            }, ids_participantes)
                            limpiar_cache()
                            st.success("Reunión registrada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

        with tab_historial:
            reuniones = cargar_reuniones()
            if not reuniones:
                st.info("Todavía no hay reuniones registradas.")
            else:
                for r in reuniones:
                    with st.expander(f'{r["fecha"]} — {(r["puntos_tratados"] or "")[:60]}'):
                        _mostrar_reunion(r)
                        st.divider()

                        ids_actuales = participantes_ids_por_reunion.get(r["id"], [])
                        nombres_actuales = [
                            _nombre_usuario_reu(usuarios_por_id_reu[uid])
                            for uid in ids_actuales if uid in usuarios_por_id_reu
                        ]

                        with st.form(f'form_editar_reunion_{r["id"]}'):
                            e_fecha = st.date_input("Fecha", value=date.fromisoformat(str(r["fecha"])[:10]),
                                                     format="DD/MM/YYYY", key=f'reu_fecha_{r["id"]}')
                            e_puntos = st.text_area("Puntos tratados", value=r["puntos_tratados"],
                                                     height=120, key=f'reu_puntos_{r["id"]}')
                            e_acuerdos = st.text_area("Descripción de lo acordado",
                                                       value=r.get("descripcion_acuerdos") or "",
                                                       height=100, key=f'reu_acuerdos_{r["id"]}')
                            opciones_part_edit = [_nombre_usuario_reu(u) for u in usuarios_activos_reu]
                            e_participantes_sel = st.multiselect(
                                "Participantes (usuarios del sistema)", opciones_part_edit,
                                default=[n for n in nombres_actuales if n in opciones_part_edit],
                                key=f'reu_participantes_{r["id"]}')
                            e_invitados = st.text_input("Invitados (personas externas, opcional)",
                                                         value=r.get("invitados") or "",
                                                         key=f'reu_invitados_{r["id"]}')

                            colg, cold = st.columns(2)
                            guardar_e = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                            eliminar_e = cold.form_submit_button("🗑️ Eliminar reunión", use_container_width=True)

                            if guardar_e:
                                if not e_puntos.strip():
                                    st.error("Los puntos tratados son obligatorios.")
                                else:
                                    try:
                                        ids_nuevos = [
                                            usuarios_activos_reu[opciones_part_edit.index(nombre)]["id"]
                                            for nombre in e_participantes_sel
                                        ]
                                        db.actualizar_reunion(r["id"], {
                                            "fecha": str(e_fecha),
                                            "puntos_tratados": e_puntos.strip(),
                                            "descripcion_acuerdos": e_acuerdos or None,
                                            "invitados": e_invitados or None,
                                        }, ids_nuevos)
                                        limpiar_cache()
                                        st.success("Reunión actualizada.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al actualizar: {e}")

                            if eliminar_e:
                                try:
                                    db.eliminar_reunion(r["id"])
                                    limpiar_cache()
                                    st.success("Reunión eliminada.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: USUARIOS (solo Administrador)
# ==================================================================
elif pagina == "👥 Usuarios":
    if not es_admin:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("👥 Usuarios")
    st.caption("Administra quién puede entrar al sistema y con qué rol.")

    tab_lista, tab_nuevo, tab_acceso = st.tabs(["📋 Lista y edición", "➕ Nuevo usuario", "🏢 Acceso a apartamentos"])

    with tab_acceso:
        st.caption("Define qué apartamentos puede ver y gestionar cada usuario. Los administradores siempre ven todos. "
                   "Un usuario con «Todos los apartamentos» (el valor por defecto) no tiene restricciones.")
        if not acceso_por_apartamento_activo():
            st.warning("Esta función todavía no está activa: ejecuta el archivo `migracion_acceso_apartamentos.sql` "
                       "en el SQL Editor de Supabase. Mientras tanto todos los usuarios ven todos los apartamentos.")
        else:
            todos_los_apts = cargar_apartamentos()          # el administrador ve todos
            usuarios_acc = db.listar_usuarios()
            mapa_accesos = accesos.construir_accesos(usuarios_acc, db.listar_accesos_apartamentos())
            ids_existentes = {a["id"] for a in todos_los_apts}
            with st.container(border=True):
                st.markdown("**Acceso actual de cada usuario**")
                st.dataframe(pd.DataFrame([{
                    "Usuario": u["username"], "Nombre": u.get("nombre") or "", "Rol": u["rol"],
                    "Activo": "Sí" if u.get("activo", True) else "No",
                    "Apartamentos": accesos.resumen(
                        {**mapa_accesos.get(u["id"], {"todos": True, "ids": set()}),
                         "ids": mapa_accesos.get(u["id"], {"ids": set()})["ids"] & ids_existentes},
                        len(todos_los_apts), es_admin=(u["rol"] == "Administrador")),
                } for u in usuarios_acc]), use_container_width=True, hide_index=True)

            candidatos = [u for u in usuarios_acc if u["rol"] != "Administrador"]
            if not candidatos:
                st.info("Todos los usuarios son administradores, que siempre ven todos los apartamentos.")
            else:
                mensaje_acc = st.session_state.pop("acceso_msg", None)
                if mensaje_acc:
                    st.success(mensaje_acc)
                i_acc = st.selectbox("Usuario", range(len(candidatos)), key="acc_usuario",
                                     format_func=lambda i: f'{candidatos[i]["username"]} — {candidatos[i].get("nombre") or ""}')
                u_acc = candidatos[i_acc]
                cfg_acc = mapa_accesos.get(u_acc["id"], {"todos": True, "ids": set()})
                etiqueta_apt = {a["id"]: f'{a["codigo"]} — {a.get("inquilino_nombre") or "sin inquilino"}' for a in todos_los_apts}
                MODO_TODOS, MODO_SOLO = "Todos los apartamentos", "Solo los apartamentos asignados"
                with st.form(f'form_acceso_{u_acc["id"]}'):
                    modo = st.radio("Acceso", [MODO_TODOS, MODO_SOLO], index=0 if cfg_acc["todos"] else 1,
                                    key=f'acc_modo_{u_acc["id"]}')
                    elegidos = st.multiselect(
                        "Apartamentos asignados (se usan solo con «Solo los apartamentos asignados»)",
                        options=[a["id"] for a in todos_los_apts], format_func=lambda i: etiqueta_apt[i],
                        default=[i for i in sorted(cfg_acc["ids"]) if i in ids_existentes], key=f'acc_ids_{u_acc["id"]}')
                    guardar_acc = st.form_submit_button("💾 Guardar acceso")
                if guardar_acc:
                    if modo == MODO_SOLO and not elegidos:
                        st.error("Elige al menos un apartamento, o selecciona «Todos los apartamentos». "
                                 "Para impedir que alguien entre, desactiva al usuario en «Lista y edición».")
                    else:
                        try:
                            db.guardar_acceso_apartamentos(u_acc["id"], modo == MODO_TODOS, elegidos)
                            limpiar_cache()
                            st.session_state["acceso_msg"] = (
                                f'Acceso de {u_acc["username"]} actualizado: '
                                + ("todos los apartamentos." if modo == MODO_TODOS else f"{len(elegidos)} apartamento(s) asignado(s)."))
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo guardar: {e}")

    with tab_lista:
        usuarios = db.listar_usuarios()
        if not usuarios:
            st.info("No hay usuarios registrados.")
        else:
            etiquetas = [f'{u["username"]} — {u.get("nombre") or ""} ({u["rol"]})' for u in usuarios]
            idx = st.selectbox("Selecciona un usuario", range(len(usuarios)), format_func=lambda i: etiquetas[i])
            u = usuarios[idx]

            with st.form("form_editar_usuario"):
                nombre = st.text_input("Nombre completo", value=u.get("nombre") or "")
                rol = st.selectbox("Rol", ROLES, index=ROLES.index(u["rol"]) if u["rol"] in ROLES else 0)
                activo = st.checkbox("Usuario activo", value=u.get("activo", True))
                st.caption("Deja la contraseña en blanco si no quieres cambiarla.")
                nueva_pwd = st.text_input("Nueva contraseña (opcional)", type="password")

                col_a, col_b = st.columns(2)
                guardar = col_a.form_submit_button("💾 Guardar cambios", use_container_width=True)
                eliminar = col_b.form_submit_button("🗑️ Eliminar usuario", use_container_width=True)

                if guardar:
                    if u["username"] == usuario_actual.get("username") and (not activo or rol != "Administrador"):
                        st.error("No puedes quitarte a ti mismo el acceso de Administrador o desactivarte.")
                    else:
                        payload = {"nombre": nombre or None, "rol": rol, "activo": activo}
                        if nueva_pwd:
                            payload["password_hash"] = hash_password(nueva_pwd)
                        try:
                            db.actualizar_usuario(u["id"], payload)
                            st.success("Usuario actualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")

                if eliminar:
                    if u["username"] == usuario_actual.get("username"):
                        st.error("No puedes eliminar tu propio usuario.")
                    else:
                        try:
                            db.eliminar_usuario(u["id"])
                            st.success("Usuario eliminado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")

    with tab_nuevo:
        with st.form("form_nuevo_usuario", clear_on_submit=True):
            username = st.text_input("Usuario (para iniciar sesión)")
            nombre = st.text_input("Nombre completo")
            rol = st.selectbox("Rol", ROLES, index=1)
            pwd1 = st.text_input("Contraseña", type="password")
            pwd2 = st.text_input("Repetir contraseña", type="password")

            crear = st.form_submit_button("➕ Crear usuario")
            if crear:
                if not username or not pwd1:
                    st.error("Usuario y contraseña son obligatorios.")
                elif pwd1 != pwd2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    try:
                        db.crear_usuario({
                            "username": username.strip().lower(),
                            "nombre": nombre or None,
                            "password_hash": hash_password(pwd1),
                            "rol": rol,
                            "activo": True,
                        })
                        st.success(f"Usuario {username} creado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear (¿usuario repetido?): {e}")


# ==================================================================
# PÁGINA: EGRESOS UNIFICADOS (compras + gastos/pagos)
# ==================================================================
elif pagina == "💸 Egresos":
    st.title("💸 Egresos")
    st.caption("Un solo formulario para compras de bienes y pagos de servicios u obligaciones operativas.")
    if not es_admin:
        st.error("No tienes permiso para registrar egresos.")
        st.stop()
    nombre_encargado = usuario_actual.get("nombre") or usuario_actual.get("username")
    tab_reg, tab_hist = st.tabs(["➕ Registrar egreso", "📜 Historial consolidado"])
    with tab_reg:
        # El selector de tipo debe quedar FUERA del formulario:
        # los widgets dentro de st.form no provocan rerun al cambiar, por lo que
        # la lista de categorías podía quedarse mostrando las opciones de Compra.
        tipo = st.radio(
            "Tipo de egreso",
            ["Compra", "Gasto / pago"],
            horizontal=True,
            key="v13_tipo_egreso",
        )
        categorias = CATEGORIAS_COMPRA if tipo == "Compra" else CATEGORIAS_GASTO_OPERATIVO
        clave_categoria = "compra" if tipo == "Compra" else "pago"
        with st.form("v13_form_egreso_unico", clear_on_submit=True):
            categoria = st.selectbox(
                "Categoría",
                categorias,
                key=f"v13_categoria_egreso_{clave_categoria}",
            )
            fecha = st.date_input("Fecha", value=recibo.hoy_bolivia(), format="DD/MM/YYYY")
            monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0, format="%.2f")
            col1, col2 = st.columns(2)
            with col1:
                beneficiario = st.text_input("Proveedor / beneficiario")
                metodo = st.selectbox("Medio de pago", METODOS_PAGO_MOVIMIENTOS)
            with col2:
                comprobante = st.text_input("N.º de factura / recibo / comprobante")
                descripcion = st.text_area("Descripción / detalle")
            st.caption(f"Registrado por: **{nombre_encargado}**")
            guardar = st.form_submit_button("💾 Registrar egreso", use_container_width=True)
            if guardar:
                if monto <= 0:
                    st.error("El monto debe ser mayor a cero.")
                else:
                    try:
                        if tipo == "Compra":
                            db.crear_compra({"fecha_compra":str(fecha),"categoria":categoria,
                                "descripcion":descripcion or None,"monto_total":monto,"metodo_pago":metodo,
                                "proveedor":beneficiario or None,"numero_comprobante":comprobante or None,
                                "encargado":nombre_encargado})
                        else:
                            db.crear_pago_general({"fecha_pago":str(fecha),"categoria":categoria,
                                "descripcion":descripcion or None,"monto":monto,"metodo_pago":metodo,
                                "beneficiario":beneficiario or None,"encargado":nombre_encargado})
                        st.success("Egreso registrado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo registrar el egreso: {e}")
    with tab_hist:
        desde = st.date_input("Desde", value=recibo.hoy_bolivia().replace(day=1), format="DD/MM/YYYY", key="v13_eg_desde")
        hasta = st.date_input("Hasta", value=recibo.hoy_bolivia(), format="DD/MM/YYYY", key="v13_eg_hasta")
        compras = db.listar_compras(fecha_desde=str(desde), fecha_hasta=str(hasta))
        pagos = db.listar_pagos_generales(fecha_desde=str(desde), fecha_hasta=str(hasta))
        filas = ([{"Fecha":x.get("fecha_compra"),"Tipo":"Compra","Categoría":x.get("categoria"),
                   "Detalle":x.get("descripcion") or "","Beneficiario":x.get("proveedor") or "",
                   "Monto (Bs)":float(x.get("monto_total") or 0),"Medio":x.get("metodo_pago") or "",
                   "Comprobante":x.get("numero_comprobante") or "","Responsable":x.get("encargado") or ""} for x in compras] +
                 [{"Fecha":x.get("fecha_pago"),"Tipo":"Gasto / pago","Categoría":x.get("categoria"),
                   "Detalle":x.get("descripcion") or "","Beneficiario":x.get("beneficiario") or "",
                   "Monto (Bs)":float(x.get("monto") or 0),"Medio":x.get("metodo_pago") or "",
                   "Comprobante":"","Responsable":x.get("encargado") or ""} for x in pagos])
        if filas:
            df = pd.DataFrame(filas).sort_values("Fecha", ascending=False)
            st.metric("Total de egresos registrados", fmt_money(df["Monto (Bs)"].sum()))
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay egresos registrados en el periodo seleccionado.")

# ==================================================================
# PÁGINA: COMPRAS (Gastos / Egresos)
# ==================================================================
elif pagina == "🧾 Compras":
    st.title("🧾 Compras (Gastos)")
    st.caption("Registro de salidas de dinero del edificio: reparaciones, artículos de limpieza, servicios, etc.")
    compras_con_estado = estado_disponible("compras", "estado_devolucion")
    if not compras_con_estado:
        st.warning(AVISO_MIGRACION_ESTADOS)
    compras_con_devolucion = compras_con_estado and devolucion_a_disponible("compras")
    if compras_con_estado and not compras_con_devolucion:
        st.warning(AVISO_MIGRACION_DEVOLUCION)

    nombre_encargado = usuario_actual.get("nombre") or usuario_actual.get("username")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar compra", "📜 Historial"])

    with tab_registrar:
        with st.form("form_nueva_compra", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha_compra = st.date_input("Fecha de compra", value=recibo.hoy_bolivia(), format="DD/MM/YYYY")
                categoria_sel = st.selectbox("Categoría / Rubro", CATEGORIAS_GASTO)
                categoria_otro = st.text_input("Especificar categoría") if categoria_sel == "Otro" else ""
                monto_total = st.number_input("Monto total (Bs)", min_value=0.0, step=10.0)
                metodo_pago_sel = st.selectbox("Método de pago", METODOS_PAGO_MOVIMIENTOS)
                metodo_pago_otro = st.text_input("Especificar método de pago") if metodo_pago_sel == "Otro" else ""
            with col2:
                proveedor = st.text_input("Proveedor (tienda o técnico)")
                numero_comprobante = st.text_input("Número de comprobante (factura/recibo)")
                if compras_con_estado:
                    estado_compra = st.selectbox("Estado", estados.ESTADOS_DEVOLUCION, key="compra_estado",
                                          disabled=not puede_editar_estado,
                                          help=None if puede_editar_estado else estados.AYUDA_SIN_PERMISO)
                if compras_con_devolucion:
                    devolucion_compra = selector_devolucion_a("compra_devolucion_a")
            descripcion = st.text_area("Descripción detallada",
                                        placeholder='Ej. "Compra de 4 focos LED para el pasillo del piso 3"')

            st.caption(f"Registrado por: **{nombre_encargado}**")

            guardar = st.form_submit_button("💾 Registrar compra")
            if guardar:
                error_devolucion = (estados.validar_devolucion(estado_compra, devolucion_compra)
                                    if compras_con_devolucion and puede_editar_estado else None)
                if monto_total <= 0:
                    st.error("El monto total debe ser mayor a 0.")
                elif error_devolucion:
                    st.error(error_devolucion)
                else:
                    try:
                        nueva_compra = {
                            "fecha_compra": str(fecha_compra),
                            "categoria": categoria_otro if categoria_sel == "Otro" and categoria_otro else categoria_sel,
                            "descripcion": descripcion or None,
                            "monto_total": monto_total,
                            "metodo_pago": metodo_pago_otro if metodo_pago_sel == "Otro" and metodo_pago_otro else metodo_pago_sel,
                            "proveedor": proveedor or None,
                            "numero_comprobante": numero_comprobante or None,
                            "encargado": nombre_encargado,
                        }
                        if compras_con_estado and puede_editar_estado:
                            nueva_compra["estado_devolucion"] = estado_compra
                            if compras_con_devolucion:
                                nueva_compra["devolucion_a"] = estados.devolucion_a_a_guardar(estado_compra, devolucion_compra)
                        db.crear_compra(nueva_compra)
                        st.success("Compra registrada.")
                        st.rerun()
                    except Exception as e:
                        st.error(texto_error_guardado("Error al guardar", e))

    with tab_historial:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filtro_desde = st.date_input("Desde", value=recibo.hoy_bolivia().replace(day=1), format="DD/MM/YYYY",
                                          key="compras_desde")
        with col2:
            filtro_hasta = st.date_input("Hasta", value=recibo.hoy_bolivia(), format="DD/MM/YYYY", key="compras_hasta")
        with col3:
            filtro_categoria = st.selectbox("Categoría", ["Todas"] + CATEGORIAS_GASTO, key="compras_cat")
        with col4:
            filtro_estado = (st.selectbox("Estado", ["Todos"] + estados.ESTADOS_DEVOLUCION, key="compras_estado_filtro")
                             if compras_con_estado else "Todos")

        compras = db.listar_compras(
            fecha_desde=str(filtro_desde), fecha_hasta=str(filtro_hasta),
            categoria=None if filtro_categoria == "Todas" else filtro_categoria,
        )
        compras = estados.filtrar_por_estado(compras, "estado_devolucion", filtro_estado, estados.ESTADOS_DEVOLUCION)

        if not compras:
            st.info("No hay compras que coincidan con el filtro.")
        else:
            total = sum(float(c["monto_total"]) for c in compras)
            mc1, mc2 = st.columns(2)
            mc1.metric("Total gastado en el periodo", fmt_money(total))
            if compras_con_estado:
                mc2.metric("Pendiente de devolución", fmt_money(estados.monto_pendiente(
                    compras, "estado_devolucion", "monto_total", estados.PENDIENTE_DEVOLUCION)))
            st.dataframe(
                pd.DataFrame([{
                    "Fecha": c["fecha_compra"], "Categoría": c["categoria"],
                    "Descripción": c.get("descripcion") or "", "Monto": c["monto_total"],
                    "Proveedor": c.get("proveedor") or "", "Comprobante N°": c.get("numero_comprobante") or "",
                    "Encargado": c.get("encargado") or "",
                    **({"Estado": estados.normalizar(c.get("estado_devolucion"), estados.ESTADOS_DEVOLUCION)}
                       if compras_con_estado else {}),
                    **({"Devolución a": estados.texto_devolucion_a(c.get("estado_devolucion"), c.get("devolucion_a"))}
                       if compras_con_devolucion else {}),
                } for c in compras]),
                use_container_width=True, hide_index=True,
            )

            with st.expander("✏️ Editar o eliminar una compra"):
                opciones = [f'{c["fecha_compra"]} — {c["categoria"]} — {fmt_money(c["monto_total"])}'
                            for c in compras]
                sel = st.selectbox("Compra", range(len(opciones)), format_func=lambda i: opciones[i])
                c = compras[sel]
                if c.get("archivo_url"):
                    st.markdown(f'📎 [Ver comprobante adjunto]({c["archivo_url"]})')
                with st.form(f'form_editar_compra_{c["id"]}'):
                    e_fecha = st.date_input("Fecha", value=date.fromisoformat(str(c["fecha_compra"])[:10]),
                                             format="DD/MM/YYYY")
                    e_categoria = st.text_input("Categoría", value=c["categoria"])
                    e_descripcion = st.text_area("Descripción", value=c.get("descripcion") or "")
                    e_monto = st.number_input("Monto total (Bs)", min_value=0.0, step=10.0,
                                               value=float(c["monto_total"]))
                    e_metodo = st.text_input("Método de pago", value=c.get("metodo_pago") or "")
                    e_proveedor = st.text_input("Proveedor", value=c.get("proveedor") or "")
                    e_comprobante = st.text_input("N° de comprobante", value=c.get("numero_comprobante") or "")
                    if compras_con_estado:
                        e_estado = st.selectbox(
                            "Estado", estados.ESTADOS_DEVOLUCION,
                            index=estados.indice(c.get("estado_devolucion"), estados.ESTADOS_DEVOLUCION),
                            disabled=not puede_editar_estado,
                            help=None if puede_editar_estado else estados.AYUDA_SIN_PERMISO,
                            key=f'compra_estado_edit_{c["id"]}')
                    if compras_con_devolucion:
                        e_devolucion = selector_devolucion_a(f'compra_devolucion_a_edit_{c["id"]}', c.get("devolucion_a"))

                    if es_admin:
                        colg, cold = st.columns(2)
                        g = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = cold.form_submit_button("🗑️ Eliminar compra", use_container_width=True)
                    else:
                        g = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = False

                    error_devolucion = (estados.validar_devolucion(e_estado, e_devolucion)
                                        if compras_con_devolucion and puede_editar_estado else None)
                    if g and error_devolucion:
                        st.error(error_devolucion)
                    elif g:
                        try:
                            cambios_compra = {
                                "fecha_compra": str(e_fecha), "categoria": e_categoria,
                                "descripcion": e_descripcion or None, "monto_total": e_monto,
                                "metodo_pago": e_metodo or None, "proveedor": e_proveedor or None,
                                "numero_comprobante": e_comprobante or None,
                            }
                            if compras_con_estado and puede_editar_estado:
                                cambios_compra["estado_devolucion"] = e_estado
                                if compras_con_devolucion:
                                    cambios_compra["devolucion_a"] = estados.devolucion_a_a_guardar(e_estado, e_devolucion)
                            db.actualizar_compra(c["id"], cambios_compra)
                            st.success("Compra actualizada.")
                            st.rerun()
                        except Exception as e:
                            st.error(texto_error_guardado("Error al actualizar", e))
                    if d:
                        try:
                            db.eliminar_compra(c["id"])
                            st.success("Compra eliminada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: PAGOS (pagos generales, sin comprobante adjunto)
# ==================================================================
elif pagina == "💳 Pagos":
    st.title("💳 Pagos")
    st.caption("Pagos generales del edificio que no requieren comprobante adjunto: "
               "sueldos, servicios, pagos a proveedores, etc.")
    pagos_con_estado = estado_disponible("pagos_generales", "estado_devolucion")
    if not pagos_con_estado:
        st.warning(AVISO_MIGRACION_ESTADOS)
    pagos_con_devolucion = pagos_con_estado and devolucion_a_disponible("pagos_generales")
    if pagos_con_estado and not pagos_con_devolucion:
        st.warning(AVISO_MIGRACION_DEVOLUCION)

    nombre_encargado = usuario_actual.get("nombre") or usuario_actual.get("username")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar pago", "📜 Historial"])

    with tab_registrar:
        with st.form("form_nuevo_pago_general", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha_pago = st.date_input("Fecha de pago", value=recibo.hoy_bolivia(), format="DD/MM/YYYY")
                categoria_sel = st.selectbox("Categoría / Concepto", CATEGORIAS_PAGO)
                categoria_otro = st.text_input("Especificar categoría") if categoria_sel == "Otro" else ""
                monto = st.number_input("Monto pagado (Bs)", min_value=0.0, step=10.0)
            with col2:
                metodo_pago_sel = st.selectbox("Método de pago", METODOS_PAGO_MOVIMIENTOS)
                metodo_pago_otro = st.text_input("Especificar método de pago") if metodo_pago_sel == "Otro" else ""
                beneficiario = st.text_input("Beneficiario (a quién se le pagó)")
                if pagos_con_estado:
                    estado_pago = st.selectbox("Estado", estados.ESTADOS_DEVOLUCION, key="pago_estado",
                                          disabled=not puede_editar_estado,
                                          help=None if puede_editar_estado else estados.AYUDA_SIN_PERMISO)
                if pagos_con_devolucion:
                    devolucion_pago = selector_devolucion_a("pago_devolucion_a")
            descripcion = st.text_area("Descripción",
                                        placeholder='Ej. "Pago de factura de luz de áreas comunes, septiembre"')

            st.caption(f"Registrado por: **{nombre_encargado}**")

            guardar = st.form_submit_button("💾 Registrar pago")
            if guardar:
                error_devolucion = (estados.validar_devolucion(estado_pago, devolucion_pago)
                                    if pagos_con_devolucion and puede_editar_estado else None)
                if monto <= 0:
                    st.error("El monto pagado debe ser mayor a 0.")
                elif error_devolucion:
                    st.error(error_devolucion)
                else:
                    try:
                        nuevo_pago = {
                            "fecha_pago": str(fecha_pago),
                            "categoria": categoria_otro if categoria_sel == "Otro" and categoria_otro else categoria_sel,
                            "descripcion": descripcion or None,
                            "monto": monto,
                            "metodo_pago": metodo_pago_otro if metodo_pago_sel == "Otro" and metodo_pago_otro else metodo_pago_sel,
                            "beneficiario": beneficiario or None,
                            "encargado": nombre_encargado,
                        }
                        if pagos_con_estado and puede_editar_estado:
                            nuevo_pago["estado_devolucion"] = estado_pago
                            if pagos_con_devolucion:
                                nuevo_pago["devolucion_a"] = estados.devolucion_a_a_guardar(estado_pago, devolucion_pago)
                        db.crear_pago_general(nuevo_pago)
                        st.success("Pago registrado.")
                        st.rerun()
                    except Exception as e:
                        st.error(texto_error_guardado("Error al guardar", e))

    with tab_historial:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filtro_desde = st.date_input("Desde", value=recibo.hoy_bolivia().replace(day=1), format="DD/MM/YYYY",
                                          key="pagos_gen_desde")
        with col2:
            filtro_hasta = st.date_input("Hasta", value=recibo.hoy_bolivia(), format="DD/MM/YYYY", key="pagos_gen_hasta")
        with col3:
            filtro_categoria = st.selectbox("Categoría", ["Todas"] + CATEGORIAS_PAGO, key="pagos_gen_cat")
        with col4:
            filtro_estado = (st.selectbox("Estado", ["Todos"] + estados.ESTADOS_DEVOLUCION, key="pagos_gen_estado_filtro")
                             if pagos_con_estado else "Todos")

        pagos_generales = db.listar_pagos_generales(
            fecha_desde=str(filtro_desde), fecha_hasta=str(filtro_hasta),
            categoria=None if filtro_categoria == "Todas" else filtro_categoria,
        )
        pagos_generales = estados.filtrar_por_estado(
            pagos_generales, "estado_devolucion", filtro_estado, estados.ESTADOS_DEVOLUCION)

        if not pagos_generales:
            st.info("No hay pagos que coincidan con el filtro.")
        else:
            total = sum(float(pg["monto"]) for pg in pagos_generales)
            mp1, mp2 = st.columns(2)
            mp1.metric("Total pagado en el periodo", fmt_money(total))
            if pagos_con_estado:
                mp2.metric("Pendiente de devolución", fmt_money(estados.monto_pendiente(
                    pagos_generales, "estado_devolucion", "monto", estados.PENDIENTE_DEVOLUCION)))
            st.dataframe(
                pd.DataFrame([{
                    "Fecha": pg["fecha_pago"], "Categoría": pg["categoria"],
                    "Descripción": pg.get("descripcion") or "", "Monto": pg["monto"],
                    "Método de pago": pg.get("metodo_pago") or "", "Beneficiario": pg.get("beneficiario") or "",
                    "Encargado": pg.get("encargado") or "",
                    **({"Estado": estados.normalizar(pg.get("estado_devolucion"), estados.ESTADOS_DEVOLUCION)}
                       if pagos_con_estado else {}),
                    **({"Devolución a": estados.texto_devolucion_a(pg.get("estado_devolucion"), pg.get("devolucion_a"))}
                       if pagos_con_devolucion else {}),
                } for pg in pagos_generales]),
                use_container_width=True, hide_index=True,
            )

            with st.expander("✏️ Editar o eliminar un pago"):
                opciones = [f'{pg["fecha_pago"]} — {pg["categoria"]} — {fmt_money(pg["monto"])}'
                            for pg in pagos_generales]
                sel = st.selectbox("Pago", range(len(opciones)), format_func=lambda i: opciones[i])
                pg = pagos_generales[sel]
                with st.form(f'form_editar_pago_general_{pg["id"]}'):
                    e_fecha = st.date_input("Fecha", value=date.fromisoformat(str(pg["fecha_pago"])[:10]),
                                             format="DD/MM/YYYY")
                    e_categoria = st.text_input("Categoría", value=pg["categoria"])
                    e_descripcion = st.text_area("Descripción", value=pg.get("descripcion") or "")
                    e_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0, value=float(pg["monto"]))
                    e_metodo = st.text_input("Método de pago", value=pg.get("metodo_pago") or "")
                    e_beneficiario = st.text_input("Beneficiario", value=pg.get("beneficiario") or "")
                    if pagos_con_estado:
                        e_estado = st.selectbox(
                            "Estado", estados.ESTADOS_DEVOLUCION,
                            index=estados.indice(pg.get("estado_devolucion"), estados.ESTADOS_DEVOLUCION),
                            disabled=not puede_editar_estado,
                            help=None if puede_editar_estado else estados.AYUDA_SIN_PERMISO,
                            key=f'pago_estado_edit_{pg["id"]}')
                    if pagos_con_devolucion:
                        e_devolucion = selector_devolucion_a(f'pago_devolucion_a_edit_{pg["id"]}', pg.get("devolucion_a"))

                    if es_admin:
                        colg, cold = st.columns(2)
                        g = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = cold.form_submit_button("🗑️ Eliminar pago", use_container_width=True)
                    else:
                        g = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = False

                    error_devolucion = (estados.validar_devolucion(e_estado, e_devolucion)
                                        if pagos_con_devolucion and puede_editar_estado else None)
                    if g and error_devolucion:
                        st.error(error_devolucion)
                    elif g:
                        try:
                            cambios_pago = {
                                "fecha_pago": str(e_fecha), "categoria": e_categoria,
                                "descripcion": e_descripcion or None, "monto": e_monto,
                                "metodo_pago": e_metodo or None, "beneficiario": e_beneficiario or None,
                            }
                            if pagos_con_estado and puede_editar_estado:
                                cambios_pago["estado_devolucion"] = e_estado
                                if pagos_con_devolucion:
                                    cambios_pago["devolucion_a"] = estados.devolucion_a_a_guardar(e_estado, e_devolucion)
                            db.actualizar_pago_general(pg["id"], cambios_pago)
                            st.success("Pago actualizado.")
                            st.rerun()
                        except Exception as e:
                            st.error(texto_error_guardado("Error al actualizar", e))
                    if d:
                        try:
                            db.eliminar_pago_general(pg["id"])
                            st.success("Pago eliminado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")


# ==================================================================
# PÁGINA: VENTAS (Ingresos extraordinarios)
# ==================================================================
elif pagina == "💸 Ventas":
    st.title("💸 Ingresos por ventas")
    st.caption("Registro de ventas de muebles, equipos, copias de llave y otros ingresos autorizados.")
    ventas_con_estado = estado_disponible("ventas", "estado_entrega")
    if not ventas_con_estado:
        st.warning(AVISO_MIGRACION_ESTADOS)

    nombre_encargado = usuario_actual.get("nombre") or usuario_actual.get("username")

    tab_registrar, tab_historial = st.tabs(["➕ Registrar venta", "📜 Historial"])

    with tab_registrar:
        with st.form("form_nueva_venta", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha_venta = st.date_input("Fecha de venta", value=recibo.hoy_bolivia(), format="DD/MM/YYYY")
                concepto_sel = st.selectbox("Concepto de ingreso", CONCEPTOS_VENTA)
                concepto_otro = st.text_input("Especificar concepto") if concepto_sel == "Otro" else ""
                monto = st.number_input("Monto recibido (Bs)", min_value=0.0, step=10.0)
            with col2:
                forma_cobro_sel = st.selectbox("Forma de cobro", METODOS_PAGO_MOVIMIENTOS)
                forma_cobro_otro = st.text_input("Especificar forma de cobro") if forma_cobro_sel == "Otro" else ""
                comprador = st.text_input("Comprador (residente, departamento u otra persona)")
                recibo_emitido = st.text_input("N° de recibo emitido")
                if ventas_con_estado:
                    estado_venta = st.selectbox("Estado", estados.ESTADOS_ENTREGA, key="venta_estado",
                                          disabled=not puede_editar_estado,
                                          help=None if puede_editar_estado else estados.AYUDA_SIN_PERMISO)
            descripcion = st.text_area("Descripción",
                                        placeholder='Ej. "Alquiler del salón de eventos al departamento 402"')

            st.caption(f"Registrado por: **{nombre_encargado}**")

            guardar = st.form_submit_button("💾 Registrar venta")
            if guardar:
                if monto <= 0:
                    st.error("El monto recibido debe ser mayor a 0.")
                else:
                    try:
                        nueva_venta = {
                            "fecha_venta": str(fecha_venta),
                            "concepto": concepto_otro if concepto_sel == "Otro" and concepto_otro else concepto_sel,
                            "descripcion": descripcion or None,
                            "monto": monto,
                            "forma_cobro": forma_cobro_otro if forma_cobro_sel == "Otro" and forma_cobro_otro else forma_cobro_sel,
                            "comprador": comprador or None,
                            "recibo_emitido": recibo_emitido or None,
                            "encargado": nombre_encargado,
                        }
                        if ventas_con_estado and puede_editar_estado:
                            nueva_venta["estado_entrega"] = estado_venta
                        db.crear_venta(nueva_venta)
                        st.success("Venta registrada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

    with tab_historial:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filtro_desde = st.date_input("Desde", value=recibo.hoy_bolivia().replace(day=1), format="DD/MM/YYYY",
                                          key="ventas_desde")
        with col2:
            filtro_hasta = st.date_input("Hasta", value=recibo.hoy_bolivia(), format="DD/MM/YYYY", key="ventas_hasta")
        with col3:
            filtro_concepto = st.selectbox("Concepto", ["Todos"] + CONCEPTOS_VENTA, key="ventas_concepto")
        with col4:
            filtro_estado = (st.selectbox("Estado", ["Todos"] + estados.ESTADOS_ENTREGA, key="ventas_estado_filtro")
                             if ventas_con_estado else "Todos")

        ventas = db.listar_ventas(
            fecha_desde=str(filtro_desde), fecha_hasta=str(filtro_hasta),
            concepto=None if filtro_concepto == "Todos" else filtro_concepto,
        )
        ventas = estados.filtrar_por_estado(ventas, "estado_entrega", filtro_estado, estados.ESTADOS_ENTREGA)

        if not ventas:
            st.info("No hay ventas que coincidan con el filtro.")
        else:
            total = sum(float(v["monto"]) for v in ventas)
            mv1, mv2 = st.columns(2)
            mv1.metric("Total recibido en el periodo", fmt_money(total))
            if ventas_con_estado:
                mv2.metric("Pendiente de entrega", fmt_money(estados.monto_pendiente(
                    ventas, "estado_entrega", "monto", estados.PENDIENTE_ENTREGA)))
            st.dataframe(
                pd.DataFrame([{
                    "Fecha": v["fecha_venta"], "Concepto": v["concepto"],
                    "Descripción": v.get("descripcion") or "", "Monto": v["monto"],
                    "Comprador": v.get("comprador") or "", "Recibo N°": v.get("recibo_emitido") or "",
                    "Encargado": v.get("encargado") or "",
                    **({"Estado": estados.normalizar(v.get("estado_entrega"), estados.ESTADOS_ENTREGA)}
                       if ventas_con_estado else {}),
                } for v in ventas]),
                use_container_width=True, hide_index=True,
            )

            with st.expander("✏️ Editar o eliminar una venta"):
                opciones = [f'{v["fecha_venta"]} — {v["concepto"]} — {fmt_money(v["monto"])}' for v in ventas]
                sel = st.selectbox("Venta", range(len(opciones)), format_func=lambda i: opciones[i])
                v = ventas[sel]
                with st.form(f'form_editar_venta_{v["id"]}'):
                    e_fecha = st.date_input("Fecha", value=date.fromisoformat(str(v["fecha_venta"])[:10]),
                                             format="DD/MM/YYYY")
                    e_concepto = st.text_input("Concepto", value=v["concepto"])
                    e_descripcion = st.text_area("Descripción", value=v.get("descripcion") or "")
                    e_monto = st.number_input("Monto (Bs)", min_value=0.0, step=10.0, value=float(v["monto"]))
                    e_forma_cobro = st.text_input("Forma de cobro", value=v.get("forma_cobro") or "")
                    e_comprador = st.text_input("Comprador", value=v.get("comprador") or "")
                    e_recibo = st.text_input("N° de recibo", value=v.get("recibo_emitido") or "")
                    if ventas_con_estado:
                        e_estado = st.selectbox(
                            "Estado", estados.ESTADOS_ENTREGA,
                            index=estados.indice(v.get("estado_entrega"), estados.ESTADOS_ENTREGA),
                            disabled=not puede_editar_estado,
                            help=None if puede_editar_estado else estados.AYUDA_SIN_PERMISO,
                            key=f'venta_estado_edit_{v["id"]}')

                    if es_admin:
                        colg, cold = st.columns(2)
                        g = colg.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = cold.form_submit_button("🗑️ Eliminar venta", use_container_width=True)
                    else:
                        g = st.form_submit_button("💾 Guardar cambios", use_container_width=True)
                        d = False

                    if g:
                        try:
                            cambios_venta = {
                                "fecha_venta": str(e_fecha), "concepto": e_concepto,
                                "descripcion": e_descripcion or None, "monto": e_monto,
                                "forma_cobro": e_forma_cobro or None, "comprador": e_comprador or None,
                                "recibo_emitido": e_recibo or None,
                            }
                            if ventas_con_estado and puede_editar_estado:
                                cambios_venta["estado_entrega"] = e_estado
                            db.actualizar_venta(v["id"], cambios_venta)
                            st.success("Venta actualizada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
                    if d:
                        try:
                            db.eliminar_venta(v["id"])
                            st.success("Venta eliminada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")
