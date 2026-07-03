"""
database.py - Proxy de base de datos
Redirige a database_sqlite.py o database_gsheets.py según DB_BACKEND en .env.
Mantiene la misma interfaz pública para compatibilidad total.
"""

import logging

from config import DB_BACKEND

logger = logging.getLogger(__name__)

if DB_BACKEND == "gsheets":
    logger.info("Usando backend: Google Sheets")
    from database_gsheets import *
elif DB_BACKEND == "sqlite":
    logger.info("Usando backend: SQLite")
    from database_sqlite import *
else:
    raise ValueError(
        f"DB_BACKEND='{DB_BACKEND}' no válido. Usa 'sqlite' o 'gsheets'."
    )
