"""
test_presupuesto_excedido.py - Gasto que excede el disponible del presupuesto.

Valida:
  - Un gasto dentro del disponible se registra sin pedir confirmación.
  - Un gasto mayor al disponible devuelve un pendiente de confirmación y NO
    registra la transacción todavía.
  - Al confirmar (forzar=True) el presupuesto se capa en lo planeado (queda
    "completado") y el saldo faltante se descuenta del balance disponible.
  - La lista de presupuestos muestra el badge "Completado".
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import config
import database
import database_sqlite
import knowledge

_TMP_DIR = tempfile.mkdtemp(prefix="finbot_exc_")
_DB_FILE = Path(_TMP_DIR) / "test.db"
config.DB_PATH = _DB_FILE
database_sqlite.DB_PATH = _DB_FILE


def _inicio_mes():
    return datetime.now().replace(day=1).strftime("%Y-%m-%d")


def setUpModule():
    database.crear_tablas()


_UID = [0]


class TestPresupuestoExcedido(unittest.TestCase):
    def setUp(self):
        _UID[0] += 1
        self.usuario = database.obtener_o_crear_usuario(777_555_000 + _UID[0], "ExcTest")
        self.cup = database.crear_moneda(self.usuario["id"], "Peso cubano", "$", "CUP", es_default=True)
        self.cat = database.crear_categoria(self.usuario["id"], "Comida", "gastos")
        database.crear_presupuesto(
            self.usuario["id"], self.cat["id"], 100.0, "mensual",
            _inicio_mes(), moneda_id=self.cup["id"],
        )
        # Ingreso grande para que el balance libre no limite la prueba.
        database.agregar_transaccion(self.usuario["id"], None, "ingreso", 1000.0, moneda_id=self.cup["id"])
        self.presupuesto = database.obtener_presupuestos(self.usuario["id"])[0]

    def _disp_balance(self):
        return database.obtener_balance(self.usuario["id"])["disponible"]

    def test_gasto_dentro_no_pide_confirmacion(self):
        texto, pendiente = knowledge._procesar_gasto(
            "gaste 40 cup", self.usuario, moneda=self.cup,
            presupuesto=self.presupuesto,
        )
        self.assertIsNone(pendiente)
        self.assertIn("Te quedan", texto)
        p = database.obtener_presupuestos(self.usuario["id"])[0]
        self.assertAlmostEqual(float(p["cantidad_gastada"]), 40.0)

    def test_gasto_excede_pide_confirmacion_y_no_registra(self):
        disp_antes = self._disp_balance()
        n_txn_antes = len(database.obtener_transacciones(self.usuario["id"], 100))
        # Dejamos el presupuesto con 40 gastados (disponible 60).
        knowledge._procesar_gasto("gaste 40 cup", self.usuario, moneda=self.cup,
                                  presupuesto=self.presupuesto, forzar=True)
        self.presupuesto = database.obtener_presupuestos(self.usuario["id"])[0]
        texto, pendiente = knowledge._procesar_gasto(
            "gaste 80 cup", self.usuario, moneda=self.cup, presupuesto=self.presupuesto,
        )
        self.assertIsNotNone(pendiente)
        self.assertEqual(pendiente["accion"], "confirmar_gasto_excedido")
        self.assertIn("exceder", texto)
        # No se registró ninguna transacción nueva todavía.
        n_txn_despues = len(database.obtener_transacciones(self.usuario["id"], 100))
        self.assertEqual(n_txn_despues, n_txn_antes + 1)
        # El balance disponible NO cambió (no se registró el gasto excedido).
        self.assertAlmostEqual(self._disp_balance(), disp_antes)

    def test_confirmar_descuenta_faltante_y_completa(self):
        # Dejamos el presupuesto con 40 gastados (disponible 60) y luego excedemos.
        knowledge._procesar_gasto("gaste 40 cup", self.usuario, moneda=self.cup,
                                  presupuesto=self.presupuesto, forzar=True)
        self.presupuesto = database.obtener_presupuestos(self.usuario["id"])[0]
        disp_antes = self._disp_balance()  # 1000 - reservado(60) = 940
        texto, pendiente = knowledge._procesar_gasto(
            "gaste 80 cup", self.usuario, moneda=self.cup, presupuesto=self.presupuesto,
        )
        self.assertIsNotNone(pendiente)
        # Confirmar (el saldo faltante es 80 - 60 = 20).
        texto2, pendiente2 = knowledge._procesar_gasto(
            "gaste 80 cup", self.usuario, moneda=self.cup,
            presupuesto=self.presupuesto, forzar=True,
        )
        self.assertIsNone(pendiente2)
        self.assertIn("completado", texto2.lower())
        # El presupuesto quedó exactamente en lo planeado (100).
        p = database.obtener_presupuestos(self.usuario["id"])[0]
        self.assertAlmostEqual(float(p["cantidad_gastada"]), 100.0)
        # El balance disponible bajó exactamente el faltante (20).
        self.assertAlmostEqual(self._disp_balance(), disp_antes - 20.0)

    def test_lista_muestra_completado(self):
        knowledge._procesar_gasto("gaste 100 cup", self.usuario, moneda=self.cup,
                                  presupuesto=self.presupuesto, forzar=True)
        lista = knowledge._procesar_presupuestos(self.usuario)
        self.assertIn("Completado", lista)


if __name__ == "__main__":
    unittest.main()
