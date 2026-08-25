"""
test_registro_conversacional.py - Verifica que frases conversacionales y con
tilde (ej. "me gasté 300 cup en una pizza", "me compré una pizza en 300 cup")
se procesan sin lanzar excepción y registran la transacción cuando hay balance.
Es regresión del bug reportado donde estas frases daban "Ups, algo salió mal".
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import asyncio
import tempfile
import unittest
from pathlib import Path

import ai_client
import config
import database
import database_sqlite

_TMP_DIR = tempfile.mkdtemp(prefix="finbot_conv_")
_DB_FILE = Path(_TMP_DIR) / "conv.db"
config.DB_PATH = _DB_FILE
database_sqlite.DB_PATH = _DB_FILE


def setUpModule():
    database.crear_tablas()


class TestRegistroConversacional(unittest.TestCase):
    def setUp(self):
        config.DB_PATH = _DB_FILE
        database_sqlite.DB_PATH = _DB_FILE
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(555, "Conv")
        self.cup = database.crear_moneda(self.usuario["id"], "Peso", "$", "CUP", es_default=True)
        database.crear_moneda(self.usuario["id"], "Dolar", "$", "USD")
        # Darle balance positivo para que registre directo (sin pendiente).
        cat = database.crear_categoria(self.usuario["id"], "Otros", "gastos")
        database.agregar_transaccion(self.usuario["id"], cat["id"], "ingreso", 1000.0, "salario", moneda_id=self.cup["id"])

    def _procesa(self, frase):
        respuesta, pendiente = asyncio.run(ai_client.AIResponder().responder(frase, self.usuario))
        self.assertIsInstance(respuesta, str)
        self.assertFalse(respuesta.startswith("⚠️ Ups"))
        return respuesta, pendiente

    def test_gaste_tilde_registra(self):
        resp, pend = self._procesa("me gasté 300 cup en una pizza")
        self.assertIsNone(pend, f"pendiente inesperado: {pend}")
        trans = database.obtener_transacciones(self.usuario["id"], 10)
        self.assertTrue(any(t["tipo"] == "gasto" and t["cantidad"] == 300.0 for t in trans),
                        f"transacciones={trans}")

    def test_compre_registra(self):
        resp, pend = self._procesa("me compré una pizza en 300 cup")
        self.assertIsNone(pend, f"pendiente inesperado: {pend}")
        trans = database.obtener_transacciones(self.usuario["id"], 10)
        self.assertTrue(any(t["tipo"] == "gasto" and t["cantidad"] == 300.0 for t in trans))

    def test_gaste_sin_tilde_registra(self):
        resp, pend = self._procesa("gasté 300 cup en una pizza")
        self.assertIsNone(pend, f"pendiente inesperado: {pend}")
        trans = database.obtener_transacciones(self.usuario["id"], 10)
        self.assertTrue(any(t["tipo"] == "gasto" and t["cantidad"] == 300.0 for t in trans))


if __name__ == "__main__":
    unittest.main(verbosity=2)
