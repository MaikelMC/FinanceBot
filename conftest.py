"""
conftest.py - Configuración de pytest.

Asegura que la raíz del proyecto esté en sys.path para que los tests
(viviendo en tests/) puedan importar los módulos del bot (config, database,
handlers, menus, ...) aunque pytest se ejecute con el binario directo.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))