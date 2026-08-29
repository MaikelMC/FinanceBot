"""
test_ver_todas.py - Botón "Ver todas" en la vista de transacciones.

Cubre:
- El reporte de consulta muestra solo las últimas 10 y ofrece el botón "Ver todas"
  (vía pendiente accion='ver_todas') cuando hay más de 10 transacciones.
- El botón se construye con el callback correcto.
- _procesar_transacciones_todas agrupa todo el historial por mes.
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import asyncio
import tempfile
import unittest
from datetime import date
from pathlib import Path

import ai_client
import config
import database
import database_sqlite
import knowledge

_TMP = tempfile.mkdtemp(prefix="finbot_ver_")
_DB = Path(_TMP) / "ver.db"
config.DB_PATH = _DB
database_sqlite.DB_PATH = _DB


def setUpModule():
    database.crear_tablas()


def _sembrar(usuario, moneda, n):
    for i in range(n):
        database.agregar_transaccion(usuario["id"], 0, "gasto", 10.0 + i, f"gasto {i}", moneda["id"])


class TestVerTodasPendiente(unittest.TestCase):
    _seq = 0

    def setUp(self):
        database.crear_tablas()
        TestVerTodasPendiente._seq += 1
        self.usuario = database.obtener_o_crear_usuario(910000000 + TestVerTodasPendiente._seq, "Ver")
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)

    def test_sin_mas_de_10_no_boton(self):
        _sembrar(self.usuario, self.mon, 3)
        texto, pend = asyncio.run(ai_client.AIResponder().responder("ver mis transacciones", self.usuario))
        self.assertIsInstance(texto, str)
        self.assertIsNone(pend)

    def test_mas_de_10_muestra_boton(self):
        _sembrar(self.usuario, self.mon, 12)
        texto, pend = asyncio.run(ai_client.AIResponder().responder("ver mis transacciones", self.usuario))
        self.assertIsNotNone(pend)
        self.assertEqual(pend["accion"], "ver_todas")
        self.assertIsNone(pend["tipo"])

    def test_boton_por_tipo_gasto(self):
        _sembrar(self.usuario, self.mon, 12)
        texto, pend = asyncio.run(ai_client.AIResponder().responder("ver mis gastos", self.usuario))
        self.assertEqual(pend["accion"], "ver_todas")
        self.assertEqual(pend["tipo"], "gasto")


class TestBotonConstruye(unittest.TestCase):
    def test_crear_boton_ver_todas(self):
        from handlers import _crear_botones_pendiente
        kb = _crear_botones_pendiente({"accion": "ver_todas", "tipo": "all"}, 1)
        self.assertIsNotNone(kb)
        # El callback debe ser ver_todas:<tipo>
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "ver_todas:all")

    def test_crear_boton_ver_todas_gasto(self):
        from handlers import _crear_botones_pendiente
        kb = _crear_botones_pendiente({"accion": "ver_todas", "tipo": "gasto"}, 1)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "ver_todas:gasto")


class TestTransaccionesTodas(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(910000500, "Todas")
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)
        _sembrar(self.usuario, self.mon, 12)

    def test_agrupa_por_mes_y_muestra_todas(self):
        texto = knowledge._procesar_transacciones_todas(self.usuario, None)
        mes_actual = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto",
                      "Septiembre","Octubre","Noviembre","Diciembre"][date.today().month - 1]
        self.assertIn(mes_actual, texto)
        self.assertIn("Neto acumulado", texto)
        # Debe listar las 12 transacciones (ícono de gasto).
        self.assertEqual(texto.count("📉"), 12)

    def test_filtro_por_tipo(self):
        # Añadir un ingreso y verificar que el filtro ingreso solo lo trae.
        database.agregar_transaccion(self.usuario["id"], 0, "ingreso", 500.0, "salario", self.mon["id"])
        texto = knowledge._procesar_transacciones_todas(self.usuario, "ingreso")
        self.assertIn("📈", texto)
        self.assertNotIn("gasto 0", texto)


class TestCallbackVerTodas(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(910000777, "Cb")
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)
        _sembrar(self.usuario, self.mon, 12)

    def test_callback_envia_agrupado(self):
        from handlers import handle_callback_query
        from unittest.mock import MagicMock, AsyncMock

        ctx = MagicMock()
        ctx.user_data = {}
        ctx.bot = MagicMock()
        ctx.bot.send_message = AsyncMock()

        query = MagicMock()
        query.data = "ver_todas:all"
        query.answer = AsyncMock()
        query.message = MagicMock()
        query.message.reply_text = AsyncMock()
        query.edit_message_text = AsyncMock()

        user_mock = MagicMock()
        user_mock.id = self.usuario["telegram_user_id"]
        user_mock.first_name = "Cb"
        user_mock.username = None

        update = MagicMock()
        update.callback_query = query
        update.effective_user = user_mock

        asyncio.run(handle_callback_query(update, ctx))

        self.assertTrue(query.message.reply_text.called)
        texto_enviado = query.message.reply_text.call_args.args[0]
        self.assertIn("Todas tus transacciones", texto_enviado)
        self.assertIn("Neto acumulado", texto_enviado)


if __name__ == "__main__":
    unittest.main(verbosity=2)
