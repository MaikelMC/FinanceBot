"""
test_parsing_bugs.py - Tests mínimos que demuestran la resolución de dos bugs:

Bug 1 - Mezcla de monedas en balances:
  "gaste 50 usdt" y "recibi 1000 cup" deben quedar aislados por moneda
  (USDT y CUP por separado), sin contaminación cruzada.

Bug 2 - Pérdida de decimales:
  "322.45" debe guardarse como 322.45 (nunca 32245), soportando tanto
  punto (.) como coma (,) como separador decimal según el contexto.

Ejecutar con:
  venv\\Scripts\\python.exe -m unittest test_parsing_bugs -v
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
import knowledge

# Usar una base SQLite temporal aislada de la real (data/finanzas.db)
_TMP_DIR = tempfile.mkdtemp(prefix="finbot_test_")
_DB_FILE = Path(_TMP_DIR) / "test.db"
config.DB_PATH = _DB_FILE
database_sqlite.DB_PATH = _DB_FILE

_COUNTER = [0]


def setUpModule():
    database.crear_tablas()


def _crear_usuario_con_monedas():
    _COUNTER[0] += 1
    usuario = database.obtener_o_crear_usuario(900_000_000 + _COUNTER[0], "Test")
    cup = database.crear_moneda(usuario["id"], "Peso cubano", "$", "CUP", es_default=True)
    usdt = database.crear_moneda(usuario["id"], "Tether", "₮", "USDT", es_default=False)
    return usuario, cup, usdt


class TestParsearCantidad(unittest.TestCase):
    """Bug 2: los decimales no deben perderse ni confundirse."""

    def test_punto_decimal(self):
        self.assertEqual(knowledge._parsear_cantidad("322.45"), 322.45)
        self.assertEqual(knowledge._parsear_cantidad("$248.50"), 248.5)

    def test_coma_decimal(self):
        self.assertEqual(knowledge._parsear_cantidad("322,45"), 322.45)
        self.assertEqual(knowledge._parsear_cantidad("1.234,56"), 1234.56)

    def test_miles(self):
        self.assertEqual(knowledge._parsear_cantidad("1,234.56"), 1234.56)
        self.assertEqual(knowledge._parsear_cantidad("1,500"), 1500.0)
        self.assertEqual(knowledge._parsear_cantidad("1 248"), 1248.0)

    def test_entero(self):
        self.assertEqual(knowledge._parsear_cantidad("1000"), 1000.0)


class TestDetectarMoneda(unittest.TestCase):
    """Bug 1: la abreviatura no debe colisionar por substring (USD vs USDT)."""

    MONEDAS = [
        {"id": 1, "nombre": "Dolar", "abreviatura": "USD", "simbolo": "$"},
        {"id": 2, "nombre": "Tether", "abreviatura": "USDT", "simbolo": "₮"},
        {"id": 3, "nombre": "Peso cubano", "abreviatura": "CUP", "simbolo": "$"},
    ]

    def test_usdt_no_es_usd(self):
        moneda = knowledge._detectar_moneda_en_texto("gaste 50 usdt", self.MONEDAS)
        self.assertEqual(moneda["abreviatura"], "USDT")

    def test_cup_se_detecta(self):
        moneda = knowledge._detectar_moneda_en_texto("recibi 1000 cup", self.MONEDAS)
        self.assertEqual(moneda["abreviatura"], "CUP")

    def test_usd_explicito(self):
        moneda = knowledge._detectar_moneda_en_texto("pague 20 usd", self.MONEDAS)
        self.assertEqual(moneda["abreviatura"], "USD")


class TestBalancePorMoneda(unittest.TestCase):
    """Bug 1 end-to-end: USDT y CUP quedan separados en el balance."""

    def test_usdt_y_cup_separados(self):
        usuario, cup, usdt = _crear_usuario_con_monedas()
        monedas = database.obtener_monedas(usuario["id"])

        m_usdt = knowledge._detectar_moneda_en_texto("gaste 50 usdt", monedas)
        knowledge._procesar_gasto("gaste 50 usdt", usuario, moneda=m_usdt)
        m_cup = knowledge._detectar_moneda_en_texto("recibi 1000 cup", monedas)
        knowledge._procesar_ingreso("recibi 1000 cup", usuario, moneda=m_cup)

        balance = database.obtener_balance(usuario["id"])
        por_moneda = balance["por_moneda"]

        self.assertIn("USDT", por_moneda)
        self.assertIn("CUP", por_moneda)
        self.assertEqual(por_moneda["USDT"]["gastos"], 50.0)
        self.assertEqual(por_moneda["USDT"]["ingresos"], 0.0)
        self.assertEqual(por_moneda["CUP"]["ingresos"], 1000.0)
        self.assertEqual(por_moneda["CUP"]["gastos"], 0.0)

    def test_registro_con_moneda_desde_texto(self):
        """El fallback de texto fija la moneda aunque el fast-path no la provea."""
        from ai_client import AIResponder

        usuario, cup, usdt = _crear_usuario_con_monedas()
        # Simula el fast-path: cantidad presente pero 'moneda' ausente
        resultado = {"tipo": "gasto", "cantidad": 50.0, "descripcion": "usdt", "moneda": None}
        respuesta = asyncio.run(AIResponder()._procesar_registro(resultado, usuario, "gaste 50 usdt"))

        trans = database.obtener_transacciones(usuario["id"], 10)
        self.assertEqual(len(trans), 1)
        self.assertEqual(trans[0]["cantidad"], 50.0)
        self.assertEqual(trans[0]["moneda_id"], usdt["id"])

    def test_decimal_322_45_se_guarda(self):
        """Bug 2: '322.45' se guarda como 322.45, no como 32245."""
        usuario, cup, usdt = _crear_usuario_con_monedas()
        knowledge._procesar_gasto("gaste 322.45 en comida", usuario, moneda=usdt)

        trans = database.obtener_transacciones(usuario["id"], 10)
        self.assertEqual(len(trans), 1)
        self.assertEqual(trans[0]["cantidad"], 322.45)

    def test_multi_transaccion_por_moneda(self):
        """Varias transacciones en un mensaje conservan su moneda por separado."""
        usuario, cup, usdt = _crear_usuario_con_monedas()
        parsed = knowledge._parsear_multi_transaccion(
            "gaste 50 usdt y recibi 1000 cup", usuario
        )
        by_abrev = {t["moneda"]["abreviatura"]: t for t in parsed}
        self.assertEqual(by_abrev["USDT"]["cantidad"], 50.0)
        self.assertEqual(by_abrev["CUP"]["cantidad"], 1000.0)


class TestIntenciónAI(unittest.TestCase):
    """Bug 2: cantidades string de la IA pasan por el parser robusto."""

    def test_cantidad_string_con_coma(self):
        from intent_parser import _validar_resultado
        r = _validar_resultado({"intencion": "registrar", "tipo": "gasto", "cantidad": "322,45"})
        self.assertEqual(r["cantidad"], 322.45)

    def test_cantidad_string_con_punto(self):
        from intent_parser import _validar_resultado
        r = _validar_resultado({"intencion": "registrar", "tipo": "gasto", "cantidad": "322.45"})
        self.assertEqual(r["cantidad"], 322.45)


if __name__ == "__main__":
    unittest.main()
