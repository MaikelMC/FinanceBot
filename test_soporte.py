"""
test_soporte.py - Comando /soporte: reporte al admin y contacto directo.

Cubre:
- El menú inline (📤 Enviar reporte / 💬 Escribir al admin directo / ❌ Cancelar) y
  que el botón "directo" solo aparece si ADMIN_TELEGRAM_USERNAME está configurado.
- /soporte con y sin argumentos.
- Los callbacks soporte:reporte / soporte:directo / soporte:cancelar.
- _enviar_ticket: formatea y envía el ticket al ADMIN_USER_ID.
- La entrada "Soporte" en el menú Más opciones (menus.procesar_callback).
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import config
import database
import database_sqlite
import menus

_TMP = tempfile.mkdtemp(prefix="finbot_soporte_")
_DB = Path(_TMP) / "soporte.db"
config.DB_PATH = _DB
database_sqlite.DB_PATH = _DB


def setUpModule():
    database.crear_tablas()


def _callbacks(kb) -> list:
    if kb is None:
        return []
    return [b.callback_data for fila in kb.inline_keyboard for b in fila]


class TestTecladoSoporte(unittest.TestCase):
    """El menú de soporte se construye según la config del admin."""

    def test_botones_base_con_directo(self):
        with patch("handlers.ADMIN_TELEGRAM_USERNAME", "thecanarymc"):
            kb = _callbacks(__import__("handlers")._crear_teclado_soporte())
        self.assertIn("soporte:reporte", kb)
        self.assertIn("soporte:directo", kb)
        self.assertIn("soporte:cancelar", kb)

    def test_directo_oculto_sin_username(self):
        with patch("handlers.ADMIN_TELEGRAM_USERNAME", ""):
            kb = _callbacks(__import__("handlers")._crear_teclado_soporte())
        self.assertIn("soporte:reporte", kb)
        self.assertNotIn("soporte:directo", kb)

    def test_texto_omite_directo_sin_username(self):
        with patch("handlers.ADMIN_TELEGRAM_USERNAME", ""):
            texto = __import__("handlers")._texto_soporte()
        self.assertIn("Soporte", texto)
        self.assertNotIn("Escribir directo", texto)


class TestComandoSoporte(unittest.TestCase):
    """/soporte sin args muestra el menú; con args envía ticket al admin."""

    def _update(self):
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.first_name = "Jose"
        update.effective_user.username = "josecito"
        update.effective_user.id = 920000101
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    def test_sin_args_muestra_menu(self):
        from handlers import soporte
        ctx = MagicMock()
        ctx.args = []
        ctx.user_data = {}
        update = self._update()
        asyncio.run(soporte(update, ctx))

        self.assertTrue(update.message.reply_text.called)
        texto = update.message.reply_text.call_args.args[0]
        kb = update.message.reply_text.call_args.kwargs.get("reply_markup")
        self.assertIn("Soporte", texto)
        self.assertIn("soporte:reporte", _callbacks(kb))

    def test_con_args_envia_ticket(self):
        from handlers import soporte
        ctx = MagicMock()
        ctx.args = ["no", "anda", "x"]
        ctx.user_data = {}
        ctx.bot = MagicMock()
        ctx.bot.send_message = AsyncMock()
        update = self._update()
        asyncio.run(soporte(update, ctx))

        args = ctx.bot.send_message.call_args
        self.assertEqual(args[0][0], config.ADMIN_USER_ID)
        ticket = args[0][1]
        self.assertIn("TICKET DE SOPORTE", ticket)
        self.assertIn("@josecito", ticket)
        self.assertIn("no anda x", ticket)
        self.assertIn("¡Reporte enviado!", update.message.reply_text.call_args.args[0])


class TestEnviarTicket(unittest.TestCase):
    """_enviar_ticket formatea el reporte y confirma al usuario."""

    def test_ticket_formato_y_destino(self):
        from handlers import _enviar_ticket
        ctx = MagicMock()
        ctx.bot = MagicMock()
        ctx.bot.send_message = AsyncMock()
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        user = SimpleNamespace(first_name="Maria", username="maria_gt", id=42)
        asyncio.run(_enviar_ticket(ctx, msg, user, "Se rompe al exportar"))

        args = ctx.bot.send_message.call_args
        self.assertEqual(args[0][0], config.ADMIN_USER_ID)
        ticket = args[0][1]
        self.assertIn("TICKET DE SOPORTE", ticket)
        self.assertIn("@maria_gt", ticket)
        self.assertIn("Se rompe al exportar", ticket)
        self.assertIn("¡Reporte enviado!", msg.reply_text.call_args.args[0])

    def test_error_al_enviar_avisa_al_usuario(self):
        from handlers import _enviar_ticket
        ctx = MagicMock()
        ctx.bot = MagicMock()
        ctx.bot.send_message = AsyncMock(side_effect=Exception("boom"))
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        user = SimpleNamespace(first_name="J", username=None, id=1)
        asyncio.run(_enviar_ticket(ctx, msg, user, "x"))

        self.assertIn("No pude entregar", msg.reply_text.call_args.args[0])


class TestCallbacksSoporte(unittest.TestCase):
    """Los callbacks soporte:* activan flujos según la acción."""

    _seq = 0

    def setUp(self):
        database.crear_tablas()
        TestCallbacksSoporte._seq += 1

    def _base(self):
        ctx = MagicMock()
        ctx.user_data = {}
        ctx.bot = MagicMock()
        ctx.bot.send_message = AsyncMock()
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        query.message.reply_text = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        update.effective_user = MagicMock()
        update.effective_user.id = 920000200 + TestCallbacksSoporte._seq
        update.effective_user.first_name = "Sop"
        update.effective_user.username = None
        return update, ctx, query

    def test_reporte_activa_captura(self):
        from handlers import handle_callback_query
        update, ctx, query = self._base()
        query.data = "soporte:reporte"
        asyncio.run(handle_callback_query(update, ctx))
        self.assertTrue(ctx.user_data.get("esperando_soporte"))
        self.assertIn("Enviar reporte", query.edit_message_text.call_args.args[0])

    def test_directo_muestra_boton_url(self):
        from handlers import handle_callback_query
        update, ctx, query = self._base()
        query.data = "soporte:directo"
        with patch("handlers.ADMIN_TELEGRAM_USERNAME", "thecanarymc"):
            asyncio.run(handle_callback_query(update, ctx))
        kb = query.edit_message_text.call_args.kwargs["reply_markup"]
        urls = [b.url for fila in kb.inline_keyboard for b in fila if getattr(b, "url", None)]
        self.assertEqual(urls, ["https://t.me/thecanarymc"])

    def test_directo_sin_username_degrada(self):
        from handlers import handle_callback_query
        update, ctx, query = self._base()
        query.data = "soporte:directo"
        with patch("handlers.ADMIN_TELEGRAM_USERNAME", ""):
            asyncio.run(handle_callback_query(update, ctx))
        texto = query.edit_message_text.call_args.args[0]
        self.assertIn("no está habilitado", texto)

    def test_cancelar_limpia_estado(self):
        from handlers import handle_callback_query
        update, ctx, query = self._base()
        ctx.user_data["esperando_soporte"] = True
        query.data = "soporte:cancelar"
        asyncio.run(handle_callback_query(update, ctx))
        self.assertNotIn("esperando_soporte", ctx.user_data)
        self.assertIn("Soporte cancelado", query.edit_message_text.call_args.args[0])


class TestMenuMasSoporte(unittest.TestCase):
    """La sección Más opciones incluye Soporte y despliega el menú."""

    def test_boton_en_mas_opciones(self):
        _, kb = menus.menu_mas()
        self.assertIn("menu_mas_soporte", _callbacks(kb))

    def test_flujo_menu_mas_soporte(self):
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.message = MagicMock()
        query.message.chat_id = 1
        ctx = MagicMock()
        ctx.user_data = {}
        ok = asyncio.run(menus.procesar_callback("menu_mas_soporte", query, ctx, {}, 1))
        self.assertTrue(ok)
        kb = query.edit_message_text.call_args.kwargs["reply_markup"]
        self.assertIn("soporte:reporte", _callbacks(kb))


if __name__ == "__main__":
    unittest.main(verbosity=2)