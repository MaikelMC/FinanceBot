"""
test_resumen_diario.py - Verifica que el resumen diario trae los datos del
dia del USUARIO (zona America/Havana) aunque las transacciones se guarden en
UTC. Antes, al enviarse a las 21:30 Havana (= 01:30 UTC siguiente), el filtro
usaba date.today() (UTC) y omitia los movimientos del dia real.
"""

import os
os.environ["DB_BACKEND"] = "sqlite"

import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import config
import database
import database_sqlite
import notificaciones
from formato import md_a_html

# Forzar la zona del usuario para el test (igual que produccion: Cuba).
config.DEFAULT_TIMEZONE = "America/Havana"


class TestResumenDiarioZona(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        tmp = Path(tempfile.mkdtemp()) / "resumen.db"
        config.DB_PATH = tmp
        database_sqlite.DB_PATH = tmp
        database.crear_tablas()
        self.usuario = database.obtener_o_crear_usuario(909, "Resumen")
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "$", "CUP", es_default=True)

    def _fake_trans(self, fecha_utc, cantidad, tipo="gasto"):
        return {
            "id": 1, "usuario_id": self.usuario["id"], "tipo": tipo,
            "cantidad": cantidad, "descripcion": "x",
            "fecha": fecha_utc, "moneda_id": self.mon["id"],
            "categoria_id": 1,
        }

    def test_incluye_movimientos_de_la_noche_del_usuario(self):
        # "Ahora" del usuario = 25/08/2026 21:30 Havana.
        # En UTC eso es 26/08/2026 01:30. Una transaccion de las 17:00 Havana
        # se guarda como 25/08 21:00 UTC; una de las 21:30 Havana como 26/08 01:30 UTC.
        trans = [
            self._fake_trans("2026-08-25 21:00:00", 50.0),   # 17:00 Havana -> dia 25
            self._fake_trans("2026-08-26 01:30:00", 30.0),   # 21:30 Havana -> dia 25
            self._fake_trans("2026-08-26 12:00:00", 999.0),  # 08:00 Havana -> dia 26 (fuera)
        ]

        with patch.object(notificaciones.database, "obtener_transacciones_por_fecha",
                          return_value=trans), \
             patch.object(notificaciones, "_fecha_hoy_usuario",
                          return_value=datetime(2026, 8, 25).date()):
            texto = notificaciones.formatear_resumen_diario(self.usuario)

        self.assertIn("25/08/2026", texto)
        # Ambas transacciones del dia 25 deben contarse (50 + 30 = 80).
        self.assertIn("80", texto)
        self.assertNotIn("999", texto)
        # No debe decir que no hubo movimientos.
        self.assertNotIn("Sin movimientos hoy", texto)

    def test_resumen_vacio_cuando_no_hay_movimientos(self):
        with patch.object(notificaciones.database, "obtener_transacciones_por_fecha",
                          return_value=[]), \
             patch.object(notificaciones, "_fecha_hoy_usuario",
                          return_value=datetime(2026, 8, 25).date()):
            texto = notificaciones.formatear_resumen_diario(self.usuario)
            self.assertIn("Sin movimientos hoy", texto)


if __name__ == "__main__":
    unittest.main(verbosity=2)
