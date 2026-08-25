"""
test_presupuestos_balance.py - Coherencia del balance con presupuestos.

Valida la corrección de presupuestos vs balance:
  - El dinero planeado en presupuestos se "reserva" del disponible.
  - disponible = neto - reservado ; reservado = Σplaneado - Σgastado (por moneda).
  - Se mantienen 'gastos' (todos) y 'neto' (ingresos - gastos) -> no rompe v2.11.
  - El flag es_presupuesto marca los gastos imputados a un presupuesto.
  - La validación v2.11 (no crear presupuesto que exceda el balance libre) sigue firme.

Escenarios del prompt original + multi-moneda + invariantes.

Ejecutar con:
  venv\\Scripts\\python.exe -m unittest test_presupuestos_balance -v
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import ai_client
import config
import database
import database_sqlite
import database_gsheets

_TMP_DIR = tempfile.mkdtemp(prefix="finbot_pres_")
_DB_FILE = Path(_TMP_DIR) / "test.db"
config.DB_PATH = _DB_FILE
database_sqlite.DB_PATH = _DB_FILE

_COUNTER = [0]


def _inicio_mes():
    return datetime.now().replace(day=1).strftime("%Y-%m-%d")


def setUpModule():
    database.crear_tablas()


# ---------------------------------------------------------------------------
# API común: tanto el módulo `database` (sqlite) como una instancia en memoria
# del backend gsheets exponen los mismos métodos que usamos aquí.
# ---------------------------------------------------------------------------

def _nuevo_usuario(api):
    _COUNTER[0] += 1
    usuario = api.obtener_o_crear_usuario(910_000_000 + _COUNTER[0], "PresTest")
    cup = api.crear_moneda(usuario["id"], "Peso cubano", "$", "CUP", es_default=True)
    return usuario, cup


def _semilla_basica(api):
    """Ingreso 2000 CUP, presupuesto Comida 1500, gasto 500 imputado a Comida."""
    usuario, cup = _nuevo_usuario(api)
    cat = api.crear_categoria(usuario["id"], "Comida", "gastos")
    api.crear_presupuesto(usuario["id"], cat["id"], 1500.0, "mensual",
                          _inicio_mes(), moneda_id=cup["id"])
    api.agregar_transaccion(usuario["id"], None, "ingreso", 2000.0, moneda_id=cup["id"])
    api.agregar_transaccion(usuario["id"], cat["id"], "gasto", 500.0,
                            moneda_id=cup["id"], es_presupuesto=True)
    return usuario, cup, cat


def _assert_escenario_basico(test, balance):
    test.assertEqual(balance["ingresos"], 2000.0)
    test.assertEqual(balance["gastos"], 500.0)
    test.assertEqual(balance["neto"], 1500.0)
    test.assertEqual(balance["reservado"], 1000.0)     # 1500 - 500 gastado
    test.assertEqual(balance["disponible"], 500.0)      # 2000 - 500 - 1000
    d = balance["por_moneda"]["CUP"]
    test.assertEqual(d["reservado"], 1000.0)
    test.assertEqual(d["disponible"], 500.0)
    test.assertEqual(d["gastos_en"], 500.0)
    test.assertEqual(d["gastos_fuera"], 0.0)
    # Invariantes
    test.assertEqual(d["disponible"], round(d["ingresos"] - d["gastos"] - d["reservado"], 2))
    test.assertEqual(d["neto"], round(d["ingresos"] - d["gastos"], 2))
    test.assertEqual(balance["disponible"], round(balance["neto"] - balance["reservado"], 2))


# ---------------------------------------------------------------------------
# Backend SQLite (API pública)
# ---------------------------------------------------------------------------

class _SqliteBase(unittest.TestCase):
    def setUp(self):
        # Aislar de otros módulos de test que mutan la global DB_PATH
        config.DB_PATH = _DB_FILE
        database_sqlite.DB_PATH = _DB_FILE
        database.crear_tablas()


class TestPresupuestosBalanceSQLite(_SqliteBase):
    def test_escenario_basico(self):
        usuario, cup, cat = _semilla_basica(database)
        balance = database.obtener_balance(usuario["id"])
        _assert_escenario_basico(self, balance)

    def test_flag_es_presupuesto(self):
        usuario, cup, cat = _semilla_basica(database)
        trans = database.obtener_transacciones(usuario["id"], limite=50)
        imputado = [t for t in trans if t.get("categoria_id") == cat["id"]]
        self.assertTrue(imputado)
        self.assertTrue(int(imputado[0].get("es_presupuesto") or 0))

        # Un gasto fuera de presupuesto no debe marcarse
        cat2 = database.crear_categoria(usuario["id"], "Ocio", "gastos")
        database.agregar_transaccion(usuario["id"], cat2["id"], "gasto", 80.0, moneda_id=cup["id"])
        trans2 = database.obtener_transacciones(usuario["id"], limite=50)
        ocio = [t for t in trans2 if t.get("categoria_id") == cat2["id"]]
        self.assertTrue(ocio)
        self.assertFalse(int(ocio[0].get("es_presupuesto") or 0))

    def test_multi_moneda(self):
        usuario, cup = _nuevo_usuario(database)
        usd = database.crear_moneda(usuario["id"], "Dólar", "$", "USD", es_default=False)
        cat_comida = database.crear_categoria(usuario["id"], "Comida", "gastos")
        cat_ocio = database.crear_categoria(usuario["id"], "Ocio", "gastos")
        database.crear_presupuesto(usuario["id"], cat_comida["id"], 1500.0, "mensual",
                                   _inicio_mes(), moneda_id=cup["id"])
        database.agregar_transaccion(usuario["id"], None, "ingreso", 2000.0, moneda_id=cup["id"])
        database.agregar_transaccion(usuario["id"], cat_comida["id"], "gasto", 500.0,
                                     moneda_id=cup["id"], es_presupuesto=True)
        database.agregar_transaccion(usuario["id"], None, "ingreso", 100.0, moneda_id=usd["id"])
        database.agregar_transaccion(usuario["id"], cat_ocio["id"], "gasto", 30.0,
                                     moneda_id=usd["id"])  # sin presupuesto USD

        balance = database.obtener_balance(usuario["id"])
        # Flat desde moneda default (CUP)
        self.assertEqual(balance["ingresos"], 2000.0)
        self.assertEqual(balance["gastos"], 500.0)
        self.assertEqual(balance["reservado"], 1000.0)
        self.assertEqual(balance["disponible"], 500.0)

        cup_d = balance["por_moneda"]["CUP"]
        self.assertEqual(cup_d["reservado"], 1000.0)
        self.assertEqual(cup_d["disponible"], 500.0)
        self.assertEqual(cup_d["gastos_en"], 500.0)

        usd_d = balance["por_moneda"]["USD"]
        self.assertEqual(usd_d["ingresos"], 100.0)
        self.assertEqual(usd_d["gastos"], 30.0)
        self.assertEqual(usd_d["reservado"], 0.0)
        self.assertEqual(usd_d["disponible"], 70.0)


# ---------------------------------------------------------------------------
# Backend Google Sheets (instancia en memoria, sin red)
# ---------------------------------------------------------------------------

def _fake_gsheets_db():
    db = object.__new__(database_gsheets.GoogleSheetsDB)
    db._cache = {n: [] for n in database_gsheets.SHEET_COLUMNS}
    db._cache_dirty = set()
    db._next_ids = {}
    db._initialized = True
    db._spreadsheet = None
    db._client = None
    db._flush_timer = None
    db._schedule_flush = lambda: None  # sin red
    return db


class TestPresupuestosBalanceGsheets(unittest.TestCase):
    def setUp(self):
        self.db = _fake_gsheets_db()

    def test_escenario_basico(self):
        usuario, cup, cat = _semilla_basica(self.db)
        balance = self.db.obtener_balance(usuario["id"])
        _assert_escenario_basico(self, balance)

    def test_flag_es_presupuesto(self):
        usuario, cup, cat = _semilla_basica(self.db)
        trans = self.db.obtener_transacciones(usuario["id"], limite=50)
        gasto = [t for t in trans if t.get("tipo") == "gasto"]
        self.assertTrue(gasto)
        self.assertTrue(int(gasto[0].get("es_presupuesto") or 0))

    def test_multi_moneda(self):
        usuario, cup = _nuevo_usuario(self.db)
        usd = self.db.crear_moneda(usuario["id"], "Dólar", "$", "USD", es_default=False)
        cat_comida = self.db.crear_categoria(usuario["id"], "Comida", "gastos")
        cat_ocio = self.db.crear_categoria(usuario["id"], "Ocio", "gastos")
        self.db.crear_presupuesto(usuario["id"], cat_comida["id"], 1500.0, "mensual",
                                  _inicio_mes(), moneda_id=cup["id"])
        self.db.agregar_transaccion(usuario["id"], None, "ingreso", 2000.0, moneda_id=cup["id"])
        self.db.agregar_transaccion(usuario["id"], cat_comida["id"], "gasto", 500.0,
                                    moneda_id=cup["id"], es_presupuesto=True)
        self.db.agregar_transaccion(usuario["id"], None, "ingreso", 100.0, moneda_id=usd["id"])
        self.db.agregar_transaccion(usuario["id"], cat_ocio["id"], "gasto", 30.0,
                                    moneda_id=usd["id"])

        balance = self.db.obtener_balance(usuario["id"])
        self.assertEqual(balance["ingresos"], 2000.0)
        self.assertEqual(balance["disponible"], 500.0)
        self.assertEqual(balance["por_moneda"]["USD"]["disponible"], 70.0)


# ---------------------------------------------------------------------------
# Guarda v2.11: no crear presupuesto que exceda el balance libre.
# _balance_disponible_moneda usa ingresos - gastos (neto), que NO cambiamos.
# ---------------------------------------------------------------------------

class TestGuardV211(_SqliteBase):
    def test_rechaza_presupuesto_que_excede_balance(self):
        _COUNTER[0] += 1
        usuario = database.obtener_o_crear_usuario(920_000_000 + _COUNTER[0], "GuardTest")
        cup = database.crear_moneda(usuario["id"], "Peso cubano", "$", "CUP", es_default=True)
        database.agregar_transaccion(usuario["id"], None, "ingreso", 2000.0, moneda_id=cup["id"])
        database.agregar_transaccion(usuario["id"], None, "gasto", 500.0, moneda_id=cup["id"])
        # neto = 1500 -> un presupuesto de 2000 debe rechazarse
        ai = ai_client.AIResponder()
        texto, pendiente = ai._procesar_presupuesto(
            {"cantidad": 2000.0, "categoria": "comida", "nombre": "comida",
             "modo_presupuesto": "crear"},
            usuario,
            "presupuesto para comida 2000 cup",
            moneda=cup,
        )
        self.assertIsNone(pendiente)
        self.assertTrue(texto.startswith("❌"))

    def test_acepta_presupuesto_dentro_de_balance(self):
        _COUNTER[0] += 1
        usuario = database.obtener_o_crear_usuario(930_000_000 + _COUNTER[0], "GuardOk")
        cup = database.crear_moneda(usuario["id"], "Peso cubano", "$", "CUP", es_default=True)
        database.agregar_transaccion(usuario["id"], None, "ingreso", 2000.0, moneda_id=cup["id"])
        database.agregar_transaccion(usuario["id"], None, "gasto", 500.0, moneda_id=cup["id"])
        ai = ai_client.AIResponder()
        texto, pendiente = ai._procesar_presupuesto(
            {"cantidad": 1000.0, "categoria": "comida", "nombre": "comida",
             "modo_presupuesto": "crear"},
            usuario,
            "presup",  # moneda va por parámetro
            moneda=cup,
        )
        self.assertFalse(texto.startswith("❌"))
        presus = database.obtener_presupuestos(usuario["id"])
        self.assertEqual(len(presus), 1)
        self.assertEqual(presus[0]["cantidad_planejada"], 1000.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
