"""
test_elegir_moneda.py - Reproduce el flujo de "elegir moneda" cuando la
instrucción no especifica la moneda (varias monedas configuradas).
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import ai_client
import config
import database
import database_sqlite
import handlers

_TMP_DIR = tempfile.mkdtemp(prefix="finbot_monedasel_")
_DB_FILE = Path(_TMP_DIR) / "ms.db"
config.DB_PATH = _DB_FILE
database_sqlite.DB_PATH = _DB_FILE

_UID = [0]


def setUpModule():
    database.crear_tablas()


class _FakeMessage:
    chat_id = 12345


class _FakeQuery:
    def __init__(self, data):
        self.data = data
        self.message = _FakeMessage()
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()


class _FakeUser:
    id = 777
    first_name = "Test"


class _FakeUpdate:
    def __init__(self, data):
        self.callback_query = _FakeQuery(data)
        self.effective_user = _FakeUser()


class _FakeContext:
    def __init__(self):
        self.user_data = {}
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()


class TestElegirMoneda(unittest.TestCase):
    def setUp(self):
        config.DB_PATH = _DB_FILE
        database_sqlite.DB_PATH = _DB_FILE
        database.crear_tablas()
        _UID[0] += 1
        self.usuario = database.obtener_o_crear_usuario(770_000_000 + _UID[0], "Test")
        # Sin moneda predeterminada: el bot debe preguntar qué moneda usar.
        self.usd = database.crear_moneda(self.usuario["id"], "Dólar", "$", "USD", es_default=False)
        self.eur = database.crear_moneda(self.usuario["id"], "Euro", "€", "EUR", es_default=False)

    def test_responder_pide_moneda_y_botones(self):
        respuesta, pendiente = asyncio.run(ai_client.AIResponder().responder("gasté 50 en comida", self.usuario))
        self.assertIsNotNone(pendiente)
        self.assertEqual(pendiente["accion"], "elegir_moneda")
        botones = handlers._crear_botones_pendiente(pendiente, self.usuario["id"])
        self.assertIsNotNone(botones)
        print("PENDIENTE:", pendiente)
        print("BOTONES:", botones.inline_keyboard)

    def test_callback_registra_con_moneda_elegida(self):
        respuesta, pendiente = asyncio.run(ai_client.AIResponder().responder("gasté 50 en comida", self.usuario))
        self.assertEqual(pendiente["accion"], "elegir_moneda")

        ctx = _FakeContext()
        ctx.user_data["transaccion_pendiente"] = pendiente
        upd = _FakeUpdate(f"moneda_confirmar_{self.eur['id']}")
        upd.effective_user.id = self.usuario["telegram_user_id"]

        asyncio.run(handlers.handle_callback_query(upd, ctx))

        trans = database.obtener_transacciones(self.usuario["id"], 10)
        self.assertEqual(len(trans), 1, f"transacciones={trans}")
        self.assertEqual(trans[0]["moneda_id"], self.eur["id"], f"moneda={trans[0]['moneda_id']}")
        self.assertEqual(trans[0]["cantidad"], 50.0)

    def test_callback_funciona_con_ids_string_estilo_sheets(self):
        """Regresión: en Google Sheets los IDs de moneda llegan como STRING.
        El callback debe comparar de forma robusta y registrar igual."""
        respuesta, pendiente = asyncio.run(ai_client.AIResponder().responder("gasté 50 en comida", self.usuario))
        self.assertEqual(pendiente["accion"], "elegir_moneda")

        # Simula el backend de Sheets: obtener_monedas devuelve IDs en string.
        monedas_real = database.obtener_monedas(self.usuario["id"])
        monedas_str = [{**m, "id": str(m["id"])} for m in monedas_real]
        orig = database.obtener_monedas
        database.obtener_monedas = lambda uid: monedas_str
        try:
            ctx = _FakeContext()
            ctx.user_data["transaccion_pendiente"] = pendiente
            upd = _FakeUpdate(f"moneda_confirmar_{self.eur['id']}")
            upd.effective_user.id = self.usuario["telegram_user_id"]
            asyncio.run(handlers.handle_callback_query(upd, ctx))
        finally:
            database.obtener_monedas = orig

        trans = database.obtener_transacciones(self.usuario["id"], 10)
        self.assertEqual(len(trans), 1, f"transacciones={trans}")
        self.assertEqual(trans[0]["moneda_id"], self.eur["id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
