"""
test_start_aviso.py - Verifica que el aviso "Te cambié el teclado" en /start
solo aparece UNA vez (a usuarios legacy), no en cada /start ni en usuarios nuevos.

Ejecutar con:
  venv\\Scripts\\python.exe -m unittest test_start_aviso -v
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import asyncio
import tempfile
import unittest
from pathlib import Path

import config
import database
import database_sqlite
import handlers

_TMP_DIR = tempfile.mkdtemp(prefix="finbot_start_")
_DB_FILE = Path(_TMP_DIR) / "test_start.db"
config.DB_PATH = _DB_FILE
database_sqlite.DB_PATH = _DB_FILE


def setUpModule():
    config.DB_PATH = _DB_FILE
    database_sqlite.DB_PATH = _DB_FILE
    database.crear_tablas()


class _FakeUser:
    def __init__(self, uid, first_name="Test"):
        self.id = uid
        self.first_name = first_name


class _FakeMessage:
    def __init__(self):
        self.sent = []

    async def reply_text(self, text, *args, **kwargs):
        self.sent.append({"text": text, "kwargs": kwargs})
        return None


class _FakeBot:
    async def send_message(self, *args, **kwargs):
        return None


class _FakeContext:
    def __init__(self):
        self.user_data = {}
        self.bot = _FakeBot()


class _FakeUpdate:
    def __init__(self, uid):
        self.effective_user = _FakeUser(uid)
        self.message = _FakeMessage()


def _run_start(uid):
    update = _FakeUpdate(uid)
    context = _FakeContext()
    asyncio.run(handlers.start(update, context))
    return update.message.sent


class TestStartAviso(unittest.TestCase):
    AVISO = "🧭 Te cambié el teclado: ahora navegas con botones."

    def test_usuario_nuevo_no_muestra_aviso(self):
        sent = _run_start(930_000_001)
        textos = [s["text"] for s in sent]
        self.assertNotIn(self.AVISO, textos)
        self.assertEqual(len(sent), 1)  # solo el mensaje de bienvenida
        u = database.obtener_usuario(930_000_001)
        self.assertEqual(int(u.get("teclado_migrado") or 0), 1)

    def test_usuario_legacy_no_migrado_muestra_aviso_vez(self):
        # Usuario existente (legacy) sin marcar -> debe mostrar el aviso
        u = database.obtener_o_crear_usuario(930_000_002, "Legacy")
        self.assertEqual(int(u.get("teclado_migrado") or 0), 0)
        sent = _run_start(930_000_002)
        textos = [s["text"] for s in sent]
        self.assertIn(self.AVISO, textos)
        self.assertEqual(len(sent), 2)  # aviso + bienvenida
        u2 = database.obtener_usuario(930_000_002)
        self.assertEqual(int(u2.get("teclado_migrado") or 0), 1)

    def test_usuario_legacy_ya_migrado_no_repite(self):
        u = database.obtener_o_crear_usuario(930_000_003, "Legacy2")
        database.marcar_teclado_migrado(u["id"])
        sent = _run_start(930_000_003)
        textos = [s["text"] for s in sent]
        self.assertNotIn(self.AVISO, textos)
        self.assertEqual(len(sent), 1)  # solo bienvenida


if __name__ == "__main__":
    unittest.main()
