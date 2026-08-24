"""
test_gastos_hormiga.py - Verifica la función "Gastos Hormiga" adaptada a la
arquitectura v2.14 (proxy database + backends sqlite/gsheets, knowledge.py,
handlers.py, menus.py).

Cobertura:
  - Detección multicriterio (monto/umbral, categoría, conversión de moneda).
  - Registro y estadísticas en backend SQLite (real).
  - Hook de _procesar_gasto -> _nota_gasto_hormiga -> registrar_gasto_hormiga.
  - Reporte _procesar_gastos_hormiga y configuración _procesar_config_gastos_hormiga.
  - Backend Google Sheets en memoria (sin red) para las 5 funciones.

Ejecutar con:
  venv\\Scripts\\python.exe -m unittest test_gastos_hormiga -v
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import tempfile
import unittest
from pathlib import Path

import config
import database
import database_sqlite
import knowledge
import formato
from database_gsheets import GoogleSheetsDB, SHEET_COLUMNS

# Nota: el backend Google Sheets no se prueba en mutaciones porque _schedule_flush
# intenta escribir a Google (red) y cuelga en entorno sin conectividad. El backend
# SQLite cubre toda la lógica; el espejo gsheets usa el mismo patrón de caché en
# memoria que las pruebas de parseo de test_parsing_bugs.py. La clase de LECTURA
# abajo sí es offline: obtener_* solo lee la caché y no dispara flush.

# Base SQLite temporal aislada de la real (data/finanzas.db)
_TMP_DIR = tempfile.mkdtemp(prefix="finbot_hormiga_")
_DB_FILE = Path(_TMP_DIR) / "test_hormiga.db"
config.DB_PATH = _DB_FILE
database_sqlite.DB_PATH = _DB_FILE

_COUNTER = [0]


def setUpModule():
    database.crear_tablas()


def _crear_usuario() -> dict:
    _COUNTER[0] += 1
    return database.obtener_o_crear_usuario(910_000_000 + _COUNTER[0], "Test Hormiga")


class TestDetectarGastoHormiga(unittest.TestCase):
    """Criterio multicriterio: monto bajo + categoría, con conversión de moneda."""

    def setUp(self):
        self.usuario = _crear_usuario()

    def test_categoria_en_lista_detecta(self):
        # 3 USD, café (en categorias_auto por defecto), umbral 5 USD -> hormiga
        self.assertTrue(
            knowledge.detectar_gasto_hormiga(self.usuario, 3.0, "café", "café", None)
        )

    def test_monto_grande_no_es_hormiga_aunque_categoria(self):
        # 100 USD supera el umbral -> no hormiga (aunque sea cafetería)
        self.assertFalse(
            knowledge.detectar_gasto_hormiga(self.usuario, 100.0, "café caro", "café", None)
        )

    def test_categoria_fuera_de_lista_no_detecta(self):
        # 'tech' no está en categorias_auto y monto pequeño sin frecuencia -> no hormiga
        self.assertFalse(
            knowledge.detectar_gasto_hormiga(self.usuario, 3.0, "cable", "tech", None)
        )

    def test_conversion_eur_bajo_umbral(self):
        moneda_eur = {"abreviatura": "EUR"}
        # umbral 5 USD ~ 4.63 EUR; 3 EUR < 4.63 y categoría café -> hormiga
        self.assertTrue(
            knowledge.detectar_gasto_hormiga(self.usuario, 3.0, "café", "café", moneda_eur)
        )

    def test_conversion_eur_sobre_umbral(self):
        moneda_eur = {"abreviatura": "EUR"}
        # 6 EUR > 4.63 EUR convertido -> no hormiga
        self.assertFalse(
            knowledge.detectar_gasto_hormiga(self.usuario, 6.0, "café", "café", moneda_eur)
        )


class TestRegistroYEstadisticasSQLite(unittest.TestCase):
    """Almacenamiento y agregación en backend SQLite real."""

    def setUp(self):
        self.usuario = _crear_usuario()

    def test_registrar_y_obtener(self):
        database.registrar_gasto_hormiga(101, self.usuario["id"], "café", 3.50)
        database.registrar_gasto_hormiga(102, self.usuario["id"], "café", 2.00)
        database.registrar_gasto_hormiga(103, self.usuario["id"], "snacks", 1.25)

        gastos = database.obtener_gastos_hormiga(self.usuario["id"], dias=30)
        self.assertEqual(len(gastos), 3)

        stats = database.obtener_estadisticas_gastos_hormiga(self.usuario["id"], dias=30)
        self.assertAlmostEqual(stats["total"], 6.75, places=2)
        self.assertEqual(stats["cantidad"], 3)
        cats = {c["categoria"]: c["total"] for c in stats["por_categoria"]}
        self.assertAlmostEqual(cats["café"], 5.50, places=2)
        self.assertAlmostEqual(cats["snacks"], 1.25, places=2)

    def test_fuera_de_ventana_no_se_incluye(self):
        database.registrar_gasto_hormiga(201, self.usuario["id"], "café", 4.0)
        # Ventana normal: el registro de hoy cuenta.
        self.assertEqual(len(database.obtener_gastos_hormiga(self.usuario["id"], dias=30)), 1)
        # Ventana negativa: excluye todo (edad 0 no es <= -1).
        self.assertEqual(len(database.obtener_gastos_hormiga(self.usuario["id"], dias=-1)), 0)


class TestHookProcesarGasto(unittest.TestCase):
    """El hook _nota_gasto_hormiga registra cuando detecta hormiga."""

    def setUp(self):
        self.usuario = _crear_usuario()

    def test_nota_registra_hormiga(self):
        nota = knowledge._nota_gasto_hormiga(
            self.usuario, 3.0, "café", "café", None, transaccion_id=555
        )
        self.assertIn(formato.EMOJI_HORMIGA, nota)
        gastos = database.obtener_gastos_hormiga(self.usuario["id"], dias=30)
        self.assertEqual(len(gastos), 1)
        self.assertEqual(gastos[0]["categoria"], "café")

    def test_nota_vacia_si_no_es_hormiga(self):
        nota = knowledge._nota_gasto_hormiga(
            self.usuario, 100.0, "notebook", "tech", None, transaccion_id=556
        )
        self.assertEqual(nota, "")

    def test_procesar_gasto_no_crashea(self):
        texto = knowledge._procesar_gasto("gaste 3 en café", self.usuario)
        self.assertIsInstance(texto, str)
        self.assertTrue(len(texto) > 0)


class TestReporteYConfig(unittest.TestCase):
    """Reporte y configuración vía knowledge (capa de lenguaje natural)."""

    def setUp(self):
        self.usuario = _crear_usuario()
        database.registrar_gasto_hormiga(301, self.usuario["id"], "café", 2.50)
        database.registrar_gasto_hormiga(302, self.usuario["id"], "café", 2.50)

    def test_reporte_con_datos(self):
        texto = knowledge._procesar_gastos_hormiga(self.usuario)
        self.assertIn(formato.EMOJI_HORMIGA, texto)
        self.assertIn("café", texto)

    def test_reporte_vacio(self):
        u = _crear_usuario()
        texto = knowledge._procesar_gastos_hormiga(u)
        self.assertIn(formato.EMOJI_HORMIGA, texto)

    def test_config_mostrar(self):
        texto = knowledge._procesar_config_gastos_hormiga(self.usuario, "mostrar")
        self.assertIn("Umbral", texto)

    def test_config_umbral_eur(self):
        knowledge._procesar_config_gastos_hormiga(self.usuario, "umbral 10 eur")
        cfg = database.obtener_config_gastos_hormiga(self.usuario["id"])
        self.assertAlmostEqual(float(cfg["umbral_base"]), 10.0, places=2)
        self.assertEqual(str(cfg["umbral_moneda"]).upper(), "EUR")

    def test_config_frecuencia(self):
        knowledge._procesar_config_gastos_hormiga(self.usuario, "frecuencia 4")
        cfg = database.obtener_config_gastos_hormiga(self.usuario["id"])
        self.assertEqual(int(cfg["frecuencia_minima"]), 4)

    def test_config_categorias(self):
        knowledge._procesar_config_gastos_hormiga(self.usuario, "categorías café,taxi,netflix")
        cfg = database.obtener_config_gastos_hormiga(self.usuario["id"])
        self.assertEqual(cfg["categorias_auto"], "café,taxi,netflix")

    def test_config_notificaciones_off(self):
        knowledge._procesar_config_gastos_hormiga(self.usuario, "notificaciones off")
        cfg = database.obtener_config_gastos_hormiga(self.usuario["id"])
        self.assertFalse(bool(int(cfg["notificaciones_activas"])))


class TestGastosHormigaGSheetsLectura(unittest.TestCase):
    """Valida el parseo de LECTURA gsheets (offline, sin flush de red): monto
    numérico (incluido locale latino), fecha YYYY-MM-DD intacta, moneda_id
    vacío y agregación de estadísticas. Cubre las consideraciones 1 y 2."""

    def setUp(self):
        self.db = GoogleSheetsDB()
        self.uid = 930_500_001
        raw = [SHEET_COLUMNS["gastos_hormiga"]]
        # monto como texto "3.50" y "2,00" (latino) para probar el parseo numérico
        raw.append([1, 10, self.uid, "café", "3.50", "", "2026-08-24", "2026-08-24 19:34:21", 1])
        raw.append([2, 11, self.uid, "café", "2,00", "", "2026-08-25", "2026-08-25 10:00:00", 1])
        raw.append([3, 12, 999, "snacks", 1.25, "", "2026-08-26", "2026-08-26 08:00:00", 1])
        filas = self.db._filas_desde_valores("gastos_hormiga", raw)
        self.db._cache["gastos_hormiga"] = filas

    def test_monto_numerico_y_fecha(self):
        gastos = self.db.obtener_gastos_hormiga(self.uid, dias=30)
        cafe = [g for g in gastos if g["categoria"] == "café"]
        self.assertEqual(len(cafe), 2)
        total_cafe = sum(g["monto"] for g in cafe)
        self.assertAlmostEqual(total_cafe, 5.50, places=2)
        for g in gastos:
            # fecha se conserva como texto YYYY-MM-DD (no serial de Excel)
            self.assertTrue(str(g["fecha"]).startswith("2026-08-"))

    def test_moneda_id_vacio_sin_enriquecer(self):
        gastos = self.db.obtener_gastos_hormiga(self.uid, dias=30)
        for g in gastos:
            self.assertNotIn("moneda_simbolo", g)  # moneda_id vacío -> sin enriquecer

    def test_estadisticas(self):
        stats = self.db.obtener_estadisticas_gastos_hormiga(self.uid, dias=30)
        self.assertAlmostEqual(stats["total"], 5.50, places=2)
        self.assertEqual(stats["cantidad"], 2)


class TestCacheConfigHormiga(unittest.TestCase):
    """La detección corre en el hot-path de cada gasto, así que la config
    debe cachearse por usuario y soportar invalidación al editarse."""

    UID = 940_001

    @classmethod
    def setUpClass(cls):
        database.guardar_config_gastos_hormiga(
            cls.UID, {"umbral_base": 5.0, "umbral_moneda": "USD"}
        )

    def test_cache_devuelve_misma_instancia(self):
        knowledge._invalidar_cache_hormiga(self.UID)
        c1 = knowledge._obtener_config_hormiga_cacheada(self.UID)
        c2 = knowledge._obtener_config_hormiga_cacheada(self.UID)
        self.assertIs(c1, c2)

    def test_invalidar_refleja_cambio_en_bd(self):
        knowledge._invalidar_cache_hormiga(self.UID)
        knowledge._obtener_config_hormiga_cacheada(self.UID)
        # cambio en BD sin invalidar -> la caché (TTL) sigue viva
        database.guardar_config_gastos_hormiga(self.UID, {"umbral_base": 99.0})
        stale = knowledge._obtener_config_hormiga_cacheada(self.UID)
        self.assertEqual(stale.get("umbral_base"), 5.0)
        # tras invalidar, la próxima lectura refleja el cambio
        knowledge._invalidar_cache_hormiga(self.UID)
        fresh = knowledge._obtener_config_hormiga_cacheada(self.UID)
        self.assertEqual(fresh.get("umbral_base"), 99.0)

    def test_hot_path_usa_cache(self):
        knowledge._invalidar_cache_hormiga(self.UID)
        usuario = {"id": self.UID, "nombre": "Cache"}
        # primera llamada cachea; la segunda (mismo gasto) reusa sin reconsultar
        r1 = knowledge.detectar_gasto_hormiga(usuario, 1.0, "café", "café")
        r2 = knowledge.detectar_gasto_hormiga(usuario, 1.0, "café", "café")
        self.assertTrue(r1)
        self.assertTrue(r2)


if __name__ == "__main__":
    unittest.main()
