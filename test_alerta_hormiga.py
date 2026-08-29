"""
test_alerta_hormiga.py - La alerta de gastos hormiga debe dispararse SOLO cuando se
acumulan `frecuencia_minima` (3) gastos hormiga en la misma semana, no en cada gasto
pequeño. Verifica el gating por semana y el contenido del aviso.
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import unittest
from pathlib import Path
import tempfile

import config
import database
import database_sqlite
import knowledge

_TMP = tempfile.mkdtemp(prefix="finbot_alert_")
_DB = Path(_TMP) / "alert.db"
config.DB_PATH = _DB
database_sqlite.DB_PATH = _DB


def setUpModule():
    database.crear_tablas()


def _sembrar_hormiga(usuario, moneda, monto=30.0, desc="café", cat="Café"):
    txn = database.agregar_transaccion(usuario["id"], 0, "gasto", monto, desc, moneda["id"])
    database.registrar_gasto_hormiga(txn["id"], usuario["id"], cat, monto, moneda["id"])
    return txn


class TestAlertaHormigaSemanal(unittest.TestCase):
    _seq = 0

    def setUp(self):
        database.crear_tablas()
        TestAlertaHormigaSemanal._seq += 1
        self.usuario = database.obtener_o_crear_usuario(900100000 + TestAlertaHormigaSemanal._seq, "Alert")
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)
        knowledge._invalidar_cache_hormiga(self.usuario["id"])

    def test_sin_llegar_al_umbral_no_alerta(self):
        # Solo 1 gasto hormiga en la semana -> no debe alertar (para no ser molesto).
        nota = knowledge._nota_gasto_hormiga(self.usuario, 30.0, "café", "Café", self.mon,
                                             _sembrar_hormiga(self.usuario, self.mon)["id"])
        self.assertEqual(nota, "")

    def test_alerta_cuando_3_en_la_semana(self):
        # Sembrar 2 previos; el 3ro se registra a través de la propia nota -> debe alertar con el conteo 3.
        _sembrar_hormiga(self.usuario, self.mon)
        _sembrar_hormiga(self.usuario, self.mon)
        txn3 = database.agregar_transaccion(self.usuario["id"], 0, "gasto", 30.0, "otro café", self.mon["id"])
        nota = knowledge._nota_gasto_hormiga(self.usuario, 30.0, "otro café más", "Café", self.mon, txn3["id"])
        self.assertIn("3 gastos hormiga esta semana", nota)
        self.assertIn("/gastos_hormiga", nota)
        self.assertIn("CUP", nota)

    def test_no_alerta_si_notificaciones_inactivas(self):
        cfg = database.obtener_config_gastos_hormiga(self.usuario["id"])
        cfg["notificaciones_activas"] = False
        database.guardar_config_gastos_hormiga(self.usuario["id"], cfg)
        knowledge._invalidar_cache_hormiga(self.usuario["id"])
        _sembrar_hormiga(self.usuario, self.mon)
        _sembrar_hormiga(self.usuario, self.mon)
        txn3 = _sembrar_hormiga(self.usuario, self.mon)
        nota = knowledge._nota_gasto_hormiga(self.usuario, 30.0, "café", "Café", self.mon, txn3["id"])
        self.assertEqual(nota, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
