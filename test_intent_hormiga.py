"""
test_intent_hormiga.py - La capacidad "gastos hormiga" existe (comando y botón) pero
estaba DESCONECTADA del pipeline de lenguaje natural: la IA no podía devolver la
subconsulta, no había fast-path y el dispatcher no tenía rama. Por eso "muéstrame mis
gastos hormiga de la semana" devolvía el historial general de gastos.

Cubre el hilo completo: fast-path -> analizar_intencion -> _procesar_consulta -> reporte,
más el filtrado por período en gastos/ingresos/transacciones.
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
import intent_parser
import knowledge

_TMP = tempfile.mkdtemp(prefix="finbot_horm_")
_DB = Path(_TMP) / "horm.db"
config.DB_PATH = _DB
database_sqlite.DB_PATH = _DB


def setUpModule():
    database.crear_tablas()


def _sembrar(usuario_id, moneda_id, tipo, monto, descripcion, fecha_iso):
    """Inserta una transacción con fecha explícita y cierra la conexión (evita lock)."""
    conn = database_sqlite.get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO transacciones (usuario_id, categoria_id, tipo, cantidad, descripcion, moneda_id, fecha) "
        "VALUES (?, 0, ?, ?, ?, ?, ?)",
        (usuario_id, tipo, monto, descripcion, moneda_id, fecha_iso + " 10:00:00"),
    )
    conn.commit()
    conn.close()


class TestExtraerPeriodo(unittest.TestCase):
    def test_frases_comunes(self):
        self.assertEqual(intent_parser._extraer_dias_periodo("hoy")[0], 1)
        self.assertEqual(intent_parser._extraer_dias_periodo("ayer")[0], 2)
        self.assertEqual(intent_parser._extraer_dias_periodo("de la semana")[0], 7)
        self.assertEqual(intent_parser._extraer_dias_periodo("esta semana")[0], 7)
        self.assertEqual(intent_parser._extraer_dias_periodo("este mes")[0], 30)
        self.assertEqual(intent_parser._extraer_dias_periodo("últimos 10 días")[0], 10)
        self.assertEqual(intent_parser._extraer_dias_periodo("sin periodo")[0], 30)

    def test_etiqueta(self):
        self.assertEqual(intent_parser._extraer_dias_periodo("de la semana")[1], "esta semana")
        self.assertEqual(intent_parser._extraer_dias_periodo("hoy")[1], "hoy")

    def test_explicito(self):
        self.assertTrue(intent_parser._extraer_dias_periodo("de la semana")[2])
        self.assertFalse(intent_parser._extraer_dias_periodo("ver mis gastos")[2])
        self.assertFalse(intent_parser._extraer_dias_periodo("sin periodo")[2])


class TestFastPathHormiga(unittest.TestCase):
    def test_fast_path_detecta_hormiga(self):
        for msg in ("muéstrame mis gastos hormiga de la semana",
                    "ver mis gastos hormiga", "gasto hormiga", "mis hormigas"):
            r = intent_parser._fast_path(msg)
            self.assertIsNotNone(r, f"fast-path no capturó: {msg}")
            self.assertEqual(r["intencion"], "consultar", msg)
            self.assertEqual(r["subconsulta"], "gastos_hormiga", msg)

    def test_fast_path_no_confunde_gastos_general(self):
        # "gastos de la semana" (sin 'hormiga') NO debe ir al reporte de hormiga.
        r = intent_parser._fast_path("muéstrame mis gastos de la semana")
        if r is not None:
            self.assertNotEqual(r["subconsulta"], "gastos_hormiga")


class TestAnalizarIntencion(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(890000001, "Horm")

    def test_intencion_hormiga_sin_ia(self):
        res = asyncio.run(intent_parser.analizar_intencion(
            "muéstrame mis gastos hormiga de la semana", self.usuario))
        self.assertEqual(res["intencion"], "consultar")
        self.assertEqual(res["subconsulta"], "gastos_hormiga")


class TestEnrutadoConsulta(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(890000002, "Ruta")

    def test_consulta_hormiga_enruta_al_reporte(self):
        texto = ai_client.AIResponder()._procesar_consulta(
            {"subconsulta": "gastos_hormiga"}, self.usuario, "gastos hormiga de la semana")
        self.assertIn("hormiga", texto.lower())
        self.assertIn("esta semana", texto)
        self.assertNotIn("recientes", texto)

    def test_consulta_gastos_filtra_periodo(self):
        mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)
        hoy_iso = date.today().isoformat()
        vieja_iso = (date.today() - timedelta(days=40)).isoformat()
        _sembrar(self.usuario["id"], mon["id"], "gasto", 100.0, "hoy", hoy_iso)
        _sembrar(self.usuario["id"], mon["id"], "gasto", 50.0, "viejo", vieja_iso)

        texto = knowledge._procesar_gastos(self.usuario, fecha_inicio=hoy_iso, fecha_fin=hoy_iso,
                                            periodo_label="hoy")
        self.assertIn("hoy", texto.lower())
        self.assertIn("100", texto)
        self.assertNotIn("50", texto)

    def test_consulta_gastos_de_la_semana_usa_periodo(self):
        mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)
        hoy_iso = date.today().isoformat()
        vieja_iso = (date.today() - timedelta(days=40)).isoformat()
        _sembrar(self.usuario["id"], mon["id"], "gasto", 999.0, "viejo", vieja_iso)
        _sembrar(self.usuario["id"], mon["id"], "gasto", 100.0, "hoy", hoy_iso)

        texto = ai_client.AIResponder()._procesar_consulta(
            {"subconsulta": "gastos"}, self.usuario, "ver mis gastos de la semana")
        self.assertIn("100", texto)
        self.assertNotIn("999", texto)


if __name__ == "__main__":
    unittest.main(verbosity=2)
