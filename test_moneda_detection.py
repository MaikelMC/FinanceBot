"""
test_moneda_detection.py - Detecta moneda escrita sin tilde/plural y registra
automáticamente con la moneda predeterminada cuando no se especifica.
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
import knowledge

_TMP = tempfile.mkdtemp(prefix="finbot_mondet_")
_DB = Path(_TMP) / "md.db"
config.DB_PATH = _DB
database_sqlite.DB_PATH = _DB


def setUpModule():
    database.crear_tablas()


MONEDAS = [
    {"nombre": "Dólar", "simbolo": "$", "abreviatura": "USD"},
    {"nombre": "Euro", "simbolo": "€", "abreviatura": "EUR"},
    {"nombre": "Peso", "simbolo": "", "abreviatura": "CUP"},
]


class TestDeteccionTexto(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(880000001, "Det")
        for mm in MONEDAS:
            database.crear_moneda(self.usuario["id"], mm["nombre"], mm["simbolo"], mm["abreviatura"],
                                  es_default=(mm["abreviatura"] == "USD"))

    def _encontrar(self, texto, abrev):
        m = knowledge._detectar_moneda_en_texto(texto, database.obtener_monedas(self.usuario["id"]))
        self.assertIsNotNone(m, f"no detectó moneda en '{texto}'")
        self.assertEqual(m["abreviatura"], abrev, f"texto='{texto}'")

    def test_sin_tilde_y_plural(self):
        self._encontrar("gasté 50 dolares", "USD")
        self._encontrar("gasté 50 euros", "EUR")
        self._encontrar("gasté 50 pesos", "CUP")
        self._encontrar("recibí 1000 cup", "CUP")

    def test_con_simbolo_y_abrev(self):
        self._encontrar("pagué $20", "USD")
        self._encontrar("gaste 50 usd", "USD")
        self._encontrar("gaste 30 eur", "EUR")


class TestRegistroAutoMoneda(unittest.TestCase):
    _seq = 0

    def setUp(self):
        database.crear_tablas()
        TestRegistroAutoMoneda._seq += 1
        self.usuario = database.obtener_o_crear_usuario(880000900 + TestRegistroAutoMoneda._seq, "Auto")
        for mm in MONEDAS:
            database.crear_moneda(self.usuario["id"], mm["nombre"], mm["simbolo"], mm["abreviatura"],
                                  es_default=(mm["abreviatura"] == "USD"))

    def _registrar(self, mensaje, moneda_ia=None):
        # Llama directo al procesamiento de registro (sin IA de lenguaje).
        res = {"tipo": "gasto", "cantidad": 50.0, "descripcion": "comida", "moneda": moneda_ia}
        texto, pendiente = asyncio.run(
            ai_client.AIResponder()._procesar_registro(res, self.usuario, mensaje)
        )
        return texto, pendiente

    def _sembrar_saldo(self, abrev="USD", monto=1000.0):
        mon = next(m for m in database.obtener_monedas(self.usuario["id"]) if m["abreviatura"] == abrev)
        database.agregar_transaccion(self.usuario["id"], 0, "ingreso", monto, "saldo inicial", mon["id"])

    def test_sin_moneda_usa_default(self):
        self._sembrar_saldo("USD")
        texto, pendiente = self._registrar("gasté 50 en comida")
        self.assertIsNone(pendiente, "no debería pedir elegir moneda si hay default")
        trans = database.obtener_transacciones(self.usuario["id"], 10)
        gasto = next((t for t in trans if t["tipo"] == "gasto"), None)
        self.assertIsNotNone(gasto, "no se registró el gasto")
        usd = next(m for m in database.obtener_monedas(self.usuario["id"]) if m["abreviatura"] == "USD")
        self.assertEqual(gasto["moneda_id"], usd["id"])

    def test_moneda_en_texto_sin_tilde(self):
        self._sembrar_saldo("USD")
        # "dolares" (sin tilde) debe registrar en Dólar, no en la default.
        texto, pendiente = self._registrar("gasté 50 dolares")
        self.assertIsNone(pendiente)
        trans = database.obtener_transacciones(self.usuario["id"], 10)
        gasto = next((t for t in trans if t["tipo"] == "gasto"), None)
        self.assertIsNotNone(gasto, "no se registró el gasto")
        dol = next(m for m in database.obtener_monedas(self.usuario["id"]) if m["abreviatura"] == "USD")
        self.assertEqual(gasto["moneda_id"], dol["id"])

    def test_moneda_explicita_diferente_a_default(self):
        self._sembrar_saldo("EUR")
        texto, pendiente = self._registrar("gasté 50 euros")
        self.assertIsNone(pendiente)
        trans = database.obtener_transacciones(self.usuario["id"], 10)
        eur = next(m for m in database.obtener_monedas(self.usuario["id"]) if m["abreviatura"] == "EUR")
        self.assertEqual(trans[0]["moneda_id"], eur["id"])


class TestElegirMonedaSinDefault(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(880000700, "SinDef")
        database.crear_moneda(self.usuario["id"], "Dólar", "$", "USD", es_default=False)
        database.crear_moneda(self.usuario["id"], "Euro", "€", "EUR", es_default=False)

    def test_sin_default_ni_moneda_pide_elegir(self):
        res = {"tipo": "gasto", "cantidad": 50.0, "descripcion": "comida", "moneda": None}
        texto, pendiente = asyncio.run(
            ai_client.AIResponder()._procesar_registro(res, self.usuario, "gasté 50 en comida")
        )
        self.assertIsNotNone(pendiente)
        self.assertEqual(pendiente["accion"], "elegir_moneda")
        # Y al tocar la moneda, se registra (flujo existente).
        from handlers import handle_callback_query
        from unittest.mock import MagicMock, AsyncMock

        ctx = MagicMock()
        ctx.user_data = {"transaccion_pendiente": pendiente}
        ctx.bot = MagicMock()
        ctx.bot.send_message = AsyncMock()

        eur = next(m for m in database.obtener_monedas(self.usuario["id"]) if m["abreviatura"] == "EUR")

        class Q:
            data = f"moneda_confirmar_{eur['id']}"
            message = MagicMock()
            answer = AsyncMock()
            edit_message_text = AsyncMock()
        class U:
            callback_query = Q()
            effective_user = MagicMock()
            effective_user.id = self.usuario["telegram_user_id"]

        asyncio.run(handle_callback_query(U(), ctx))
        trans = database.obtener_transacciones(self.usuario["id"], 10)
        self.assertEqual(len(trans), 1)
        self.assertEqual(trans[0]["moneda_id"], eur["id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
