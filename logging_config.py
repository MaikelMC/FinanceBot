"""
logging_config.py - Sistema de logging centralizado para FinanceBot.

Configura el logger RAÍZ para que todos los módulos que usan
`logging.getLogger(__name__)` (handlers, knowledge, database, ai_client,
menus, etc.) escriban automáticamente con el mismo formato en:

  1. data/logs/finanzas.log -> RotatingFileHandler (rota cada 1 MB,
     mantiene 7 archivos: finanzas.log, finanzas.log.1 ... finanzas.log.7)
  2. Consola (stdout)       -> StreamHandler (visible en producción/Render)

Formato de cada línea:
  2026-08-21 14:03:22 | INFO     | handlers | Transacción registrada...

Nivel (variable LOG_LEVEL en .env):
  - INFO  (default, producción): eventos normales + errores
  - DEBUG (desarrollo): además incluye trazas detalladas
Los errores emitidos dentro de un bloque `except` incluyen el TRACEBACK
completo de forma automática, aunque la llamada sea `logger.error(...)`.

Uso (en main.py, antes de arrancar el bot):
  import logging_config
  logging_config.configurar_logging()

El módulo es idempotente: llamarlo más de una vez no duplica handlers.
"""

import logging
import logging.handlers
import sys
import threading

import config
import metricas

# ============================================================
# CONSTANTES DE CONFIGURACIÓN
# ============================================================

LOG_FILE_NAME = "finanzas.log"
MAX_BYTES = 1 * 1024 * 1024   # rotar cada 1 MB
BACKUP_COUNT = 7              # mantener 7 archivos rotados

FORMATO = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"

# Librerías terceras muy verbosas: solo se muestran WARNING o superior.
# (httpx/telegram generan cientos de líneas DEBUG por mensaje del bot)
_MODULOS_RUIDOSOS = ("httpx", "httpcore", "telegram", "apscheduler", "urllib3")

_lock = threading.Lock()
_ya_configurado = False


class TracebackEnErroresFormatter(logging.Formatter):
    """Formatter que adjunta el traceback completo a los ERROR/CRITICAL.

    Si el registro es de nivel ERROR o superior, no trae exc_info propio y
    se emitió DENTRO de un bloque except (hay excepción activa en el hilo),
    se le añade el traceback automáticamente. Así los `logger.error(...)`
    existentes registran el traceback sin cambiar cada llamada.
    """

    def format(self, record):
        if record.levelno >= logging.ERROR and not record.exc_info and not record.exc_text:
            excepcion_activa = sys.exc_info()
            if excepcion_activa and excepcion_activa[0] is not None:
                record.exc_info = excepcion_activa
        return super().format(record)


class ContadorDeErrores(logging.Handler):
    """Handler silencioso que suma cada registro ERROR+ a las métricas del bot.

    Se instala en la raíz con nivel ERROR; no escribe a ningún lado,
    solo alimenta metricas.errores_ultima_hora() para /metricas.
    """

    def __init__(self):
        super().__init__(level=logging.ERROR)

    def emit(self, record):
        try:
            metricas.registrar_error()
        except Exception:
            pass  # nunca romper el logging por un fallo de métricas


def _nivel_desde_texto(texto: str) -> int:
    """Convierte 'DEBUG'/'INFO'/'WARNING'/'ERROR' a constante logging. Default INFO."""
    return getattr(logging, str(texto).upper(), logging.INFO)


def configurar_logging(nivel: int = None) -> None:
    """Instala archivo rotativo + consola en el logger raíz.

    Args:
        nivel: nivel mínimo (constante logging). Si es None se toma
            config.LOG_LEVEL (variable LOG_LEVEL del .env; INFO por defecto).

    Idempotente y seguro de llamar varias veces: limpia handlers previos
    (p.ej. un basicConfig anterior) antes de instalar los suyos.
    """
    global _ya_configurado
    with _lock:
        if _ya_configurado:
            return
        _ya_configurado = True

    # Crear data/logs/ si no existe (idempotente)
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = TracebackEnErroresFormatter(FORMATO, datefmt=FORMATO_FECHA)
    nivel_efectivo = nivel if nivel is not None else _nivel_desde_texto(config.LOG_LEVEL)

    raiz = logging.getLogger()
    # La raíz deja pasar TODO; el filtrado fino lo hacen los handlers
    raiz.setLevel(logging.DEBUG)

    # Limpiar handlers previos (p.ej. basicConfig de otro módulo) para no duplicar
    for handler in list(raiz.handlers):
        raiz.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    # 1) ARCHIVO: data/logs/finanzas.log, rota cada 1 MB, mantiene 7
    archivo = logging.handlers.RotatingFileHandler(
        config.LOG_DIR / LOG_FILE_NAME,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    archivo.setLevel(nivel_efectivo)
    archivo.setFormatter(formatter)
    raiz.addHandler(archivo)

    # 2) CONSOLA (stdout): visible en producción (Render) y desarrollo
    consola = logging.StreamHandler(sys.stdout)
    consola.setLevel(nivel_efectivo)
    consola.setFormatter(formatter)
    raiz.addHandler(consola)

    # 3) CONTADOR DE ERRORES: alimenta /metricas (sin escribir a ningún lado)
    raiz.addHandler(ContadorDeErrores())

    # Reducir ruido de librerías terceras: solo WARNING+ de ellas
    for nombre in _MODULOS_RUIDOSOS:
        logging.getLogger(nombre).setLevel(logging.WARNING)

    logging.getLogger(__name__).debug(
        "Logging configurado: archivo=%s (rotación %d MB, %d archivos), "
        "consola=stdout, nivel=%s",
        config.LOG_DIR / LOG_FILE_NAME,
        MAX_BYTES // (1024 * 1024),
        BACKUP_COUNT,
        logging.getLevelName(nivel_efectivo),
    )
