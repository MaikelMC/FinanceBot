"""Regresión del reporte de gastos hormiga (corrección de montos/ingresos/duplicados).

Verifica que el reporte derive el monto, la descripción y la fecha de la
transacción real, excluya ingresos y no duplique por transacción.
"""
import unittest

import database
import knowledge
import formato


_contador = [0]


def _crear_usuario():
    _contador[0] += 1
    return database.obtener_o_crear_usuario(980000000 + _contador[0], "FixHormiga")


def _sembrar_gasto(usuario, moneda, cantidad, descripcion, categoria="comida"):
    t = database.agregar_transaccion(
        usuario["id"], 0, "gasto", cantidad, descripcion, moneda_id=moneda["id"]
    )
    database.registrar_gasto_hormiga(t["id"], usuario["id"], categoria, cantidad, moneda["id"])
    return t


class TestMontoAutoritativo(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = _crear_usuario()
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)

    def test_monto_se_toma_de_la_transaccion_no_del_registro(self):
        # El registro hormiga guardó un monto ERRÓNEO (300); la transacción real es 960.
        t = database.agregar_transaccion(
            self.usuario["id"], 0, "gasto", 960.0, "gasté 960 cup en 2 cafes", moneda_id=self.mon["id"]
        )
        database.registrar_gasto_hormiga(t["id"], self.usuario["id"], "comida", 300.0, self.mon["id"])

        gastos = database.obtener_gastos_hormiga(self.usuario["id"], dias=30)
        self.assertEqual(len(gastos), 1)
        self.assertAlmostEqual(gastos[0]["monto"], 960.0, places=2)

        texto = knowledge._procesar_gastos_hormiga(self.usuario, dias=30, etiqueta="ultimos 30 dias")
        self.assertIn("960.00", texto)
        self.assertNotIn("300.00", texto)
        self.assertIn("960 cup en 2 cafes", texto)


class TestIngresosExcluidos(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = _crear_usuario()
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)

    def test_ingreso_no_aparece_como_hormiga(self):
        t = database.agregar_transaccion(
            self.usuario["id"], 0, "ingreso", 16800.0, "tuve un ingreso de 16800 cup", moneda_id=self.mon["id"]
        )
        # Se "marca" por error como hormiga.
        database.registrar_gasto_hormiga(t["id"], self.usuario["id"], "comida", 16800.0, self.mon["id"])

        gastos = database.obtener_gastos_hormiga(self.usuario["id"], dias=30)
        self.assertEqual(len(gastos), 0)

        texto = knowledge._procesar_gastos_hormiga(self.usuario, dias=30, etiqueta="ultimos 30 dias")
        self.assertNotIn("16800", texto)

    def test_nota_no_registra_ingreso(self):
        t = database.agregar_transaccion(
            self.usuario["id"], 0, "ingreso", 5000.0, "ingreso de 5000", moneda_id=self.mon["id"]
        )
        nota = knowledge._nota_gasto_hormiga(self.usuario, 5000.0, "ingreso de 5000", "comida", self.mon, t["id"])
        self.assertEqual(nota, "")
        self.assertEqual(len(database.obtener_gastos_hormiga(self.usuario["id"], dias=30)), 0)


class TestDedupe(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = _crear_usuario()
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)

    def test_no_duplicados_por_transaccion(self):
        t = _sembrar_gasto(self.usuario, self.mon, 50.0, "café diario")
        # Registrar dos veces la misma transacción (no debe duplicar).
        database.registrar_gasto_hormiga(t["id"], self.usuario["id"], "café", 50.0, self.mon["id"])
        gastos = database.obtener_gastos_hormiga(self.usuario["id"], dias=30)
        self.assertEqual(len(gastos), 1)


class TestFormatoProfesional(unittest.TestCase):
    def setUp(self):
        database.crear_tablas()
        self.usuario = _crear_usuario()
        self.mon = database.crear_moneda(self.usuario["id"], "Peso", "", "CUP", es_default=True)
        _sembrar_gasto(self.usuario, self.mon, 400.0, "pizza de 400 pesos", "comida")
        _sembrar_gasto(self.usuario, self.mon, 1500.0, "cable iphone 1500", "transporte")

    def test_reporte_tiene_porcentajes_y_fechas_cortas(self):
        texto = knowledge._procesar_gastos_hormiga(self.usuario, dias=30, etiqueta="ultimos 30 dias")
        self.assertIn("%", texto)          # porcentajes por categoría
        self.assertIn("/" , texto)         # fechas cortas DD/MM
        self.assertIn(formato.EMOJI_HORMIGA, texto)
        # El ingreso nunca debe colarse.
        self.assertNotIn("ingreso", texto.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
