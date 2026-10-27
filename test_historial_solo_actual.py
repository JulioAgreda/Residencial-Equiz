"""Los historiales muestran SOLO al inquilino actual  ->  python test_historial_solo_actual.py
Simula la base de datos en memoria (periodos abiertos y cerrados de ex inquilinos) y ejecuta las funciones reales de db.py;
además revisa en app.py qué consulta usa cada pantalla.  (necesita db.py y app.py en la misma carpeta o una arriba)"""
import importlib.util, os, re, sys, types
from types import SimpleNamespace

base = os.path.dirname(os.path.abspath(__file__))
def ruta(nombre):
    for carpeta in (base, os.path.join(base, "..")):
        if os.path.exists(os.path.join(carpeta, nombre)):
            return os.path.join(carpeta, nombre)

# ---- módulos externos falsos (db.py importa streamlit y supabase) ----
st = types.ModuleType("streamlit"); st.cache_resource = lambda f: f; st.cache_data = lambda *a, **k: (lambda f: f); sys.modules["streamlit"] = st
sup = types.ModuleType("supabase"); sup.create_client = lambda *a: None; sup.Client = object; sys.modules["supabase"] = sup
spec = importlib.util.spec_from_file_location("db_real", ruta("db.py")); db = importlib.util.module_from_spec(spec); spec.loader.exec_module(db)

class Consulta:
    """Mini PostgREST en memoria: select / eq / is_ / gt / order / limit / range / execute."""
    def __init__(self, filas): self.filas, self.orden, self.tope, self.rango = [dict(f) for f in filas], [], None, None
    def select(self, *a, **k): return self
    def eq(self, col, val): self.filas = [f for f in self.filas if f.get(col) == val]; return self
    def is_(self, col, val):
        assert val == "null"; self.filas = [f for f in self.filas if f.get(col) is None]; return self
    def gt(self, col, val): self.filas = [f for f in self.filas if f.get(col) is not None and f[col] > val]; return self
    def order(self, col, desc=False): self.orden.append((col, desc)); return self
    def limit(self, n): self.tope = n; return self
    def range(self, a, b): self.rango = (a, b); return self
    def execute(self):
        filas = self.filas
        for col, desc in reversed(self.orden):
            filas = sorted(filas, key=lambda f: (f.get(col) is None, f.get(col)), reverse=desc)
        if self.rango: filas = filas[self.rango[0]:self.rango[1] + 1]
        if self.tope: filas = filas[:self.tope]
        return SimpleNamespace(data=filas)

HIST = 5   # id del historial del ex inquilino
TABLAS = {
    "periodos_alquiler": [
        {"id": 1, "apartamento_id": 1, "mes": "Octubre", "anio": 2026, "inquilino_historial_id": HIST, "created_at": "2026-10-01"},   # del ex inquilino
        {"id": 2, "apartamento_id": 1, "mes": "Junio", "anio": 2026, "inquilino_historial_id": HIST, "created_at": "2026-06-01"},      # del ex inquilino
        {"id": 3, "apartamento_id": 1, "mes": "Octubre", "anio": 2026, "inquilino_historial_id": None, "created_at": "2026-10-20"},   # del inquilino NUEVO (mismo mes)
        {"id": 4, "apartamento_id": 2, "mes": "Octubre", "anio": 2026, "inquilino_historial_id": None, "created_at": "2026-10-02"}],  # otro apartamento
    "periodos_electricidad": [
        {"id": 10, "apartamento_id": 1, "mes": "Octubre", "anio": 2026, "kwh_actual": 8370, "inquilino_historial_id": HIST, "created_at": "2026-10-30"},
        {"id": 11, "apartamento_id": 2, "mes": "Octubre", "anio": 2026, "kwh_actual": 500, "inquilino_historial_id": None, "created_at": "2026-10-02"}],
    "periodos_agua": [
        {"id": 20, "apartamento_id": 1, "mes": "Octubre", "anio": 2026, "inquilino_historial_id": HIST, "created_at": "2026-10-30"}],
}
class Cliente:
    def table(self, nombre): return Consulta(TABLAS[nombre])
db.get_client = lambda: Cliente()
ids = lambda filas: sorted(f["id"] for f in filas)

# ================= historiales y Dashboard: solo el inquilino actual =================
assert ids(db.listar_periodos(solo_activos=True)) == [3, 4]                                  # sin los del ex inquilino
assert ids(db.listar_periodos(apartamento_id=1, solo_activos=True)) == [3]                   # el apartamento 1 solo muestra al inquilino nuevo
assert ids(db.listar_periodos()) == [1, 2, 3, 4]                                             # (sin el filtro se verían todos: eso era el problema)
assert ids(db.listar_periodos_servicio("electricidad", solo_activos=True)) == [11]
assert ids(db.listar_periodos_servicio("electricidad", apartamento_id=1, solo_activos=True)) == []     # el apartamento 1 quedó sin registros de luz: nada del ex inquilino
assert ids(db.listar_periodos_servicio("agua", solo_activos=True)) == [] and ids(db.listar_periodos_servicio("agua")) == [20]
# ================= Estado de cuenta, moras y Rendición: abiertos / cerrados =================
assert ids(db.listar_periodos_abiertos("alquiler")) == [3, 4] and ids(db.listar_periodos_abiertos("electricidad")) == [11]
assert ids(db.listar_periodos_cerrados("alquiler")) == [1, 2] and ids(db.listar_periodos_cerrados("electricidad")) == [10] and ids(db.listar_periodos_cerrados("agua")) == [20]
# ================= registrar una lectura y el pago: nunca sobre el periodo del ex inquilino =================
assert db.obtener_periodo_servicio("electricidad", 1, "Octubre", 2026) is None               # el inquilino nuevo no hereda el periodo cerrado del anterior
assert db.obtener_periodo_servicio("electricidad", 2, "Octubre", 2026)["id"] == 11
# ================= la lectura del medidor SÍ continúa (el medidor es del apartamento, no del inquilino) =================
assert db.ultimo_periodo_servicio("electricidad", 1)["kwh_actual"] == 8370                   # el nuevo inquilino parte de la última lectura del anterior
assert db.ultimo_periodo_servicio("electricidad", 99) is None

# ================= qué consulta usa cada pantalla de app.py =================
app = open(ruta("app.py"), encoding="utf-8").read()
for nombre, texto in (("_cargar_periodos_todos", "db.listar_periodos("), ("_cargar_periodos_electricidad_todos", "db.listar_periodos_servicio("),
                      ("_cargar_periodos_agua_todos", "db.listar_periodos_servicio(")):
    cuerpo = app[app.index(f"def {nombre}("):].split("\n\n\n")[0]
    assert "solo_activos=True" in cuerpo, f"{nombre} (Dashboard) debe mostrar solo al inquilino actual"
# historiales de Alquiler y de Electricidad/Agua (llaman a la base directamente)
llamadas = re.findall(r"_solo_mis_apartamentos\(db\.(listar_periodos(?:_servicio)?)\(\n(.*?)\n\s*\)\)", app, re.S)
assert len(llamadas) == 2 and all("solo_activos=True" in cuerpo for _fn, cuerpo in llamadas), llamadas
assert app.count("Se muestran solo los registros del inquilino actual") == 2                  # y lo explican en pantalla
# la pantalla «Ex inquilinos» necesita VER los cerrados: no debe filtrar
ex = app[app.index('elif pagina == "🚪 Ex inquilinos":'):app.index("# PÁGINA: INQUILINOS")]
assert "solo_activos" not in ex and "db.listar_periodos(" in ex and "db.listar_periodos_servicio(" in ex
# el Estado de cuenta usa solo periodos abiertos y muestra aparte a los ex inquilinos con deuda
ec = app[app.index('elif pagina == "📑 Estado de cuenta":'):app.index('elif pagina == "📊 Actividad por usuario":')]
assert 'cargar_periodos_abiertos("alquiler")' in ec and "cargar_periodos(" not in ec and "Ex inquilinos con deuda pendiente" in ec
print("PRUEBAS DE HISTORIAL (SOLO INQUILINO ACTUAL) OK")
