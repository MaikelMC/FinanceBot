"""
test_ver_todas.py - Vista mensual de transacciones.

Cubre el nuevo diseño:
- El reporte muestra SOLO el mes en curso (no vuelca meses anteriores en el texto).
- Si hay movimientos en otros meses, ofrece el botón "Ver meses anteriores"
  (vía pendiente accion='hist_meses' / callback hist_meses:<tipo>).
- Los totales del mes se listan POR MONEDA (no mezclan divisas).
- La navegación hist_meses / hist_mes / hist_actual lleva a un mes concreto.
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import asyncio
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import ai_client
import config
import database
import database_sqlite
import knowledge
import menus

_TMP = tempfile.mkdtemp(prefix="finbot_ver_")
_DB = Path(_TMP) / "ver.db"
config.DB_PATH = _DB
database_sqlite.DB_PATH = _DB


def setUpModule():
    database.crear_tablas()


def _sembrar(usuario_id, moneda_id, tipo, cantidad, desc, fecha):
    """Agrega una transacción con fecha explícita (ISO YYYY-MM-DD)."""
    t = database.agregar_transaccion(usuario_id, 0, tipo, cantidad, desc, moneda_id)
    conn = database_sqlite.get_connection()
    conn.execute("UPDATE transacciones SET fecha = ? WHERE id = ?", (fecha, t["id"]))
    conn.commit()
    conn.close()


def _mes_anterior_iso() -> str:
    """Un ISO dentro del mes anterior al actual (día acotado a 28)."""
    hoy = date.today()
    if hoy.month == 1:
        base = date(hoy.year - 1, 12, 1)
    else:
        base = date(hoy.year, hoy.month - 1, 1)
    dia = min(hoy.day, 28)
    return date(base.year, base.month, dia).isoformat()


class TestPendienteMeses(unittest.TestCase):
    _seq = 0

    def setUp(self):
        database.crear_tablas()
        TestPendienteMeses._seq += 1
        self.usuario = database.obtener_o_crear_usuario(910000000 + TestPendienteMeses._seq, "Ver")
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)

    def test_sin_meses_anteriores_no_boton(self):
        _sembrar(self.usuario["id"], self.mon["id"], "gasto", 10.0, "gasto 0", date.today().isoformat())
        texto, pend = asyncio.run(ai_client.AIResponder().responder("ver mis gastos", self.usuario))
        self.assertIsInstance(texto, str)
        self.assertIsNone(pend)

    def test_mes_en_curso_con_todas_las_del_mes(self):
        # 12 gastos del mes actual: el mensaje debe listarlas (no limitar a 10).
        hoy = date.today().isoformat()
        for i in range(12):
            _sembrar(self.usuario["id"], self.mon["id"], "gasto", 10.0 + i, f"gasto {i}", hoy)
        texto, pend = asyncio.run(ai_client.AIResponder().responder("ver mis gastos", self.usuario))
        self.assertIsNone(pend)
        self.assertIn("gasto 0", texto)
        self.assertIn("gasto 11", texto)

    def test_con_meses_anteriores_muestra_boton(self):
        hoy = date.today().isoformat()
        _sembrar(self.usuario["id"], self.mon["id"], "gasto", 5.0, "actual", hoy)
        _sembrar(self.usuario["id"], self.mon["id"], "gasto", 99.0, "mes_anterior", _mes_anterior_iso())
        texto, pend = asyncio.run(ai_client.AIResponder().responder("ver mis gastos", self.usuario))
        self.assertIsNotNone(pend)
        self.assertEqual(pend["accion"], "hist_meses")
        self.assertEqual(pend["tipo"], "gasto")
        # Solo el mes en curso en el mensaje: lo anterior va detrás del botón.
        self.assertIn("actual", texto)
        self.assertNotIn("mes_anterior", texto)

    def test_por_tipo_gasto_e_ingreso(self):
        hoy = date.today().isoformat()
        _sembrar(self.usuario["id"], self.mon["id"], "ingreso", 500.0, "salario", hoy)
        _sembrar(self.usuario["id"], self.mon["id"], "ingreso", 400.0, "mes_anterior", _mes_anterior_iso())
        _, pend = asyncio.run(ai_client.AIResponder().responder("ver mis ingresos", self.usuario))
        self.assertEqual(pend["tipo"], "ingreso")


class TestBotonConstruye(unittest.TestCase):
    def test_crear_boton_meses_todas(self):
        from handlers import _crear_botones_pendiente
        kb = _crear_botones_pendiente({"accion": "hist_meses", "tipo": "all"}, 1)
        self.assertIsNotNone(kb)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "hist_meses:all")

    def test_crear_boton_meses_gasto(self):
        from handlers import _crear_botones_pendiente
        kb = _crear_botones_pendiente({"accion": "hist_meses", "tipo": "gasto"}, 1)
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "hist_meses:gasto")


class TestTotalesPorMoneda(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(910000500, "Monedas")
        self.cup = database.crear_moneda(self.usuario["id"], "Peso", "$", "CUP", es_default=True)
        self.usd = database.crear_moneda(self.usuario["id"], "Dólar", "$", "USD")

    def test_total_no_mezcla_divisas(self):
        hoy = date.today().isoformat()
        _sembrar(self.usuario["id"], self.cup["id"], "gasto", 10.0, "comida", hoy)
        _sembrar(self.usuario["id"], self.usd["id"], "gasto", 20.0, "café", hoy)
        texto = knowledge._vista_transacciones(self.usuario, tipo="gasto")["texto"]
        self.assertIn("Gastos:", texto)
        self.assertIn("(CUP)", texto)
        self.assertIn("(USD)", texto)
        self.assertNotIn("30.00", texto)  # nunca 10+20 mezclados en un solo monto

    def test_totales_en_vista_todas(self):
        hoy = date.today().isoformat()
        _sembrar(self.usuario["id"], self.cup["id"], "gasto", 30.0, "comida", hoy)
        _sembrar(self.usuario["id"], self.usd["id"], "ingreso", 50.0, "salario", hoy)
        texto = knowledge._vista_transacciones(self.usuario, tipo=None)["texto"]
        self.assertIn("Gastos:", texto)
        self.assertIn("Ingresos:", texto)
        self.assertIn("(CUP)", texto)
        self.assertIn("(USD)", texto)


class TestCallbackHistorial(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(910000777, "Cb")
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)
        hoy = date.today().isoformat()
        _sembrar(self.usuario["id"], self.mon["id"], "gasto", 10.0, "actual", hoy)
        _sembrar(self.usuario["id"], self.mon["id"], "gasto", 5.0, "mes_anterior", _mes_anterior_iso())

    def _run_callback(self, data):
        from handlers import handle_callback_query
        from unittest.mock import MagicMock, AsyncMock

        ctx = MagicMock()
        ctx.user_data = {}
        ctx.bot = MagicMock()
        ctx.bot.send_message = AsyncMock()

        query = MagicMock()
        query.data = data
        query.answer = AsyncMock()
        query.message = MagicMock()
        query.message.reply_text = AsyncMock()
        query.message.chat_id = 1
        query.edit_message_text = AsyncMock()

        user_mock = MagicMock()
        user_mock.id = self.usuario["telegram_user_id"]
        user_mock.first_name = "Cb"
        user_mock.username = None

        update = MagicMock()
        update.callback_query = query
        update.effective_user = user_mock

        asyncio.run(handle_callback_query(update, ctx))
        return query

    def test_hist_meses_abre_selector(self):
        query = self._run_callback("hist_meses:gasto")
        self.assertTrue(query.edit_message_text.called)
        texto = query.edit_message_text.call_args.args[0]
        self.assertIn("Historial de gastos", texto)

    def test_hist_mes_abre_mes_concreto(self):
        query = self._run_callback(f"hist_mes:gasto:{_mes_anterior_iso()[:7]}")
        self.assertTrue(query.edit_message_text.called)
        texto = query.edit_message_text.call_args.args[0]
        self.assertIn("mes_anterior", texto)
        self.assertNotIn("actual", texto)


class TestMenuMeses(unittest.TestCase):
    _seq = 0

    def setUp(self):
        database.crear_tablas()
        TestMenuMeses._seq += 1
        self.usuario = database.obtener_o_crear_usuario(910001000 + TestMenuMeses._seq, "MenuVT")
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)

    def _callbacks(self, tupla):
        texto, kb = tupla
        return [b.callback_data for fila in kb.inline_keyboard for b in fila]

    def test_menu_transacciones_incluye_meses_anteriores(self):
        hoy = date.today().isoformat()
        _sembrar(self.usuario["id"], self.mon["id"], "gasto", 10.0, "actual", hoy)
        _sembrar(self.usuario["id"], self.mon["id"], "gasto", 5.0, "mes_anterior", _mes_anterior_iso())
        cbs = self._callbacks(menus.menu_transacciones(self.usuario))
        self.assertIn("hist_meses:all", cbs)

    def test_menu_gastos_incluye_meses_anteriores(self):
        hoy = date.today().isoformat()
        _sembrar(self.usuario["id"], self.mon["id"], "gasto", 10.0, "actual", hoy)
        _sembrar(self.usuario["id"], self.mon["id"], "gasto", 5.0, "mes_anterior", _mes_anterior_iso())
        cbs = self._callbacks(menus._menu_ver_tipo(self.usuario, "gasto"))
        self.assertIn("hist_meses:gasto", cbs)

    def test_menu_ingresos_incluye_meses_anteriores(self):
        hoy = date.today().isoformat()
        _sembrar(self.usuario["id"], self.mon["id"], "ingreso", 100.0, "actual", hoy)
        _sembrar(self.usuario["id"], self.mon["id"], "ingreso", 50.0, "mes_anterior", _mes_anterior_iso())
        cbs = self._callbacks(menus._menu_ver_tipo(self.usuario, "ingreso"))
        self.assertIn("hist_meses:ingreso", cbs)

    def test_solo_mes_en_curso_no_boton(self):
        hoy = date.today().isoformat()
        for i in range(3):
            _sembrar(self.usuario["id"], self.mon["id"], "gasto", 10.0 + i, f"gasto {i}", hoy)
        cbs = self._callbacks(menus.menu_transacciones(self.usuario))
        self.assertNotIn("hist_meses:all", cbs)
        cbs2 = self._callbacks(menus._menu_ver_tipo(self.usuario, "gasto"))
        self.assertNotIn("hist_meses:gasto", cbs2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
