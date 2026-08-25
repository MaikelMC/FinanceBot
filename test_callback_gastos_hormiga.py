"""
test_callback_gastos_hormiga.py - Reproduce el flujo del botón "Gastos Hormiga"
(menu_gastos_hormiga) a través de handle_callback_query, para verificar que
SIEMPRE produce una respuesta al usuario (edit_message_text o send_message).
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import config
import database
import database_sqlite
import handlers

_TMP_DIR = tempfile.mkdtemp(prefix="finbot_cb_")
_DB_FILE = Path(_TMP_DIR) / "cb.db"
config.DB_PATH = _DB_FILE
database_sqlite.DB_PATH = _DB_FILE


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


class TestCallbackGastosHormiga(unittest.TestCase):
    def setUp(self):
        config.DB_PATH = _DB_FILE
        database_sqlite.DB_PATH = _DB_FILE
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(777, "Test")
        cat = database.crear_categoria(self.usuario["id"], "Café", "gastos")
        txn = database.agregar_transaccion(self.usuario["id"], cat["id"], "gasto", 5.0, "café")
        database.registrar_gasto_hormiga(txn["id"], self.usuario["id"], "café", 5.0, "CUP")

    def test_menu_gastos_hormiga_produce_respuesta(self):
        ctx = _FakeContext()
        upd = _FakeUpdate("menu_gastos_hormiga")
        asyncio.run(handlers.handle_callback_query(upd, ctx))

        editado = upd.callback_query.edit_message_text.called
        enviado = ctx.bot.send_message.called
        self.assertTrue(editado or enviado, "El callback NO produjo ninguna respuesta")

        if editado:
            args, kwargs = upd.callback_query.edit_message_text.call_args
            texto_enviado = args[0] if args else kwargs.get("text", "")
            print("EDIT text:", texto_enviado[:120])
            print("EDIT parse_mode:", kwargs.get("parse_mode"))
            self.assertEqual(kwargs.get("parse_mode"), "HTML")
            # El markdown ** debe haberse convertido a <b>
            self.assertIn("<b>", texto_enviado)
            self.assertNotIn("**", texto_enviado)
        if enviado:
            for c in ctx.bot.send_message.call_args_list:
                a, k = c
                print("SEND text:", (a[1] if len(a) > 1 else k.get("text", ""))[:120])

    def test_menu_gastos_hormiga_responde_aunque_answer_falle(self):
        """Regresión: si query.answer() lanza (timeout/rate-limit), el handler
        NO debe morir silenciosamente; debe editar/enviar la respuesta igual."""
        ctx = _FakeContext()
        upd = _FakeUpdate("menu_gastos_hormiga")
        # Simula query.answer() lanzando (ej. TimedOut de la API de Telegram)
        upd.callback_query.answer = AsyncMock(side_effect=RuntimeError("simulated timeout"))

        asyncio.run(handlers.handle_callback_query(upd, ctx))

        editado = upd.callback_query.edit_message_text.called
        enviado = ctx.bot.send_message.called
        self.assertTrue(
            editado or enviado,
            "El callback no produjo respuesta pese a que query.answer() falló",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
