"""
test_responder_seguro.py - Verifica que los mensajes con Markdown invalido
(o que Telegram rechaza) se reenvian como HTML en vez de mostrar '**' literales.
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

import handlers
from formato import md_a_html


class TestResponderSeguro(unittest.TestCase):
    def test_markdown_valido_se_queda_en_markdown(self):
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        texto = "**Gasto registrado**"
        asyncio.run(handlers._responder_seguro(msg, texto))
        args, kwargs = msg.reply_text.call_args
        self.assertEqual(kwargs.get("parse_mode"), "Markdown")
        self.assertIn("**", args[0])

    def test_markdown_invalido_cae_a_html(self):
        # Simula que Telegram rechaza el Markdown (ej. entidad invalida).
        calls = []

        async def fake_reply(texto, **kwargs):
            calls.append((texto, kwargs.get("parse_mode")))
            if kwargs.get("parse_mode") == "Markdown":
                raise RuntimeError("Can't parse entities")
            return None

        msg = MagicMock()
        msg.reply_text = fake_reply
        texto = "**Gasto** con `codigo` y * algo"
        asyncio.run(handlers._responder_seguro(msg, texto))

        # Primero intento Markdown (falla), luego HTML.
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], "Markdown")
        self.assertEqual(calls[1][1], "HTML")
        # El HTML debe tener <b> y no **.
        self.assertIn("<b>", calls[1][0])
        self.assertNotIn("**", calls[1][0])
        self.assertEqual(calls[1][0], md_a_html(texto))


if __name__ == "__main__":
    unittest.main(verbosity=2)
