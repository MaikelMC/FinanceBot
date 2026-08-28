"""
test_balance_presupuesto.py - El "disponible" mostrado excluye el apartado en
presupuestos (neto - reservado). Un gasto que NO es de un presupuesto y supera
el disponible debe advertir, porque el usuario sabe cuanto puede gastar.
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import unittest
import tempfile
from pathlib import Path

import config
import database
import database_sqlite
import knowledge

_TMP = tempfile.mkdtemp(prefix="finbot_balpres_")
_DB = Path(_TMP) / "bp.db"
config.DB_PATH = _DB
database_sqlite.DB_PATH = _DB

MONEDA = {"nombre": "Peso", "simbolo": "", "abreviatura": "CUP"}


def setUpModule():
    database.crear_tablas()


class TestBalancePresupuesto(unittest.TestCase):
    _seq = 0

    def setUp(self):
        database.crear_tablas()
        TestBalancePresupuesto._seq += 1
        self.usuario = database.obtener_o_crear_usuario(890000000 + TestBalancePresupuesto._seq, "BP")
        self.cup = database.crear_moneda(self.usuario["id"], MONEDA["nombre"], MONEDA["simbolo"],
                                         MONEDA["abreviatura"], es_default=True)
        database.agregar_transaccion(self.usuario["id"], 0, "ingreso", 860.0, "saldo", self.cup["id"])
        cat = database.crear_categoria(self.usuario["id"], "comida", "gastos")
        database.guardar_presupuesto(self.usuario["id"], cat["id"], 500.0, "fijar",
                                     nombre="comida", moneda_id=self.cup["id"])

    def test_disponible_excluye_apartado(self):
        # 860 neto, 500 apartado -> disponible mostrado = 360.
        b = database.obtener_balance(self.usuario["id"])
        d = b["por_moneda"]["CUP"]
        self.assertEqual(d["reservado"], 500.0)
        self.assertEqual(d["disponible"], 360.0)
        self.assertEqual(d["neto"], 860.0)

    def test_gasto_fuera_de_presupuesto_excede_disponible_advierte(self):
        # Gasto de 400 que no es de presupuesto > disponible (360) -> advierte.
        texto, pendiente = knowledge._procesar_gasto("gaste 400 en transporte", self.usuario,
                                                     moneda=self.cup, forzar=False)
        self.assertIsNotNone(pendiente, f"deberia advertir: {texto}")
        self.assertEqual(pendiente["accion"], "confirmar_gasto_balance")

    def test_gasto_dentro_de_disponible_se_registra(self):
        # Gasto de 300 (<= 360 disponible) fuera de presupuesto -> se registra.
        texto, pendiente = knowledge._procesar_gasto("gaste 300 en transporte", self.usuario,
                                                     moneda=self.cup, forzar=False)
        self.assertIsNone(pendiente, f"no deberia advertir: {texto}")
        self.assertIn("registrado", texto)

    def test_gasto_supera_neto_advierte(self):
        # 900 > neto (860) -> advierte siempre.
        texto, pendiente = knowledge._procesar_gasto("gaste 900 en transporte", self.usuario,
                                                     moneda=self.cup, forzar=False)
        self.assertIsNotNone(pendiente)
        self.assertEqual(pendiente["accion"], "confirmar_gasto_balance")


if __name__ == "__main__":
    unittest.main(verbosity=2)
