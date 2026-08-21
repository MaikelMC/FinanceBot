"""
rate_limiter.py - Rate limiting por usuario para evitar flood/ban en Telegram.

Middleware simple basado en ventana deslizante en memoria:
- Máximo RATE_LIMIT_MAX mensajes por RATE_LIMIT_WINDOW segundos por usuario.
- Comandos críticos (/start, /help) nunca se bloquean ni cuentan.
- Limpieza automática de timestamps viejos (perezosa + job cada minuto).

Se integra en main.py como un handler en el grupo -1: corre antes que todos
los demás handlers; si el usuario excede el límite responde con el aviso y
detiene el procesamiento del update con ApplicationHandlerStop.
"""

import logging
import threading
import time

from telegram import Update
from telegram.ext import ApplicationHandlerStop, TypeHandler

import config

logger = logging.getLogger(__name__)

# Comandos críticos que siempre pasan (no se bloquean ni cuentan)
COMANDOS_EXENTOS = ("/start", "/help")

# Segundos mínimos entre avisos de "demasiadas solicitudes" al mismo usuario
AVISO_CADA_SEGUNDOS = 3


class RateLimiter:
    """Ventana deslizante en memoria: {telegram_user_id: [timestamps]}."""

    def __init__(self, max_requests: int = None, window_seconds: int = None):
        self.max_requests = max_requests if max_requests is not None else config.RATE_LIMIT_MAX
        self.window = float(window_seconds if window_seconds is not None else config.RATE_LIMIT_WINDOW)
        self._requests = {}  # telegram_user_id -> list[float] de timestamps
        self._avisos = {}    # telegram_user_id -> timestamp del último aviso enviado
        self._lock = threading.Lock()
        self._ultima_limpieza = time.time()

    # ------------------------------------------------------------------
    # Limpieza
    # ------------------------------------------------------------------
    def limpiar(self) -> int:
        """Elimina usuarios sin requests dentro de la ventana. Retorna cuántos."""
        ahora = time.time()
        limite = ahora - self.window
        with self._lock:
            vivos = {}
            for uid, stamps in self._requests.items():
                recientes = [t for t in stamps if t > limite]
                if recientes:
                    vivos[uid] = recientes
            eliminados = len(self._requests) - len(vivos)
            self._requests = vivos
            for uid in [u for u, t in self._avisos.items() if ahora - t > self.window]:
                del self._avisos[uid]
            self._ultima_limpieza = ahora
            return eliminados

    def _limpiar_si_toca(self, ahora: float) -> None:
        """Limpieza perezosa: como máximo una vez por ventana (sin job_queue)."""
        if ahora - self._ultima_limpieza >= self.window:
            self.limpiar()

    # ------------------------------------------------------------------
    # Verificación
    # ------------------------------------------------------------------
    def verificar(self, telegram_user_id: int, mensaje: str = "") -> tuple:
        """
        Registra el request y decide si pasa.

        Retorna (permitido, segundos_de_espera):
        - permitido=True  -> procesar el mensaje normalmente.
        - permitido=False -> responder 'Intenta de nuevo en N segundos'.
        """
        texto = (mensaje or "").strip().lower()
        for cmd in COMANDOS_EXENTOS:
            if texto.startswith(cmd):
                return True, 0

        ahora = time.time()
        limite = ahora - self.window
        with self._lock:
            self._limpiar_si_toca(ahora)
            stamps = [t for t in self._requests.get(telegram_user_id, []) if t > limite]
            if len(stamps) >= self.max_requests:
                espera = max(int(stamps[0] + self.window - ahora) + 1, 1)
                self._requests[telegram_user_id] = stamps
                return False, espera
            stamps.append(ahora)
            self._requests[telegram_user_id] = stamps
            return True, 0

    def debe_avisar(self, telegram_user_id: int) -> bool:
        """True si toca enviar otro aviso (máx. 1 cada AVISO_CADA_SEGUNDOS)."""
        ahora = time.time()
        with self._lock:
            ultimo = self._avisos.get(telegram_user_id, 0)
            if ahora - ultimo >= AVISO_CADA_SEGUNDOS:
                self._avisos[telegram_user_id] = ahora
                return True
            return False

    def reset(self, telegram_user_id: int = None) -> None:
        """Limpia contadores de un usuario (o de todos si es None)."""
        with self._lock:
            if telegram_user_id is None:
                self._requests.clear()
                self._avisos.clear()
            else:
                self._requests.pop(telegram_user_id, None)
                self._avisos.pop(telegram_user_id, None)


async def _callback_noop(update, context):
    """Callback requerido por TypeHandler; nunca se ejecuta (handle_update lo reemplaza)."""


class RateLimitMiddleware(TypeHandler):
    """Handler que corre primero (grupo -1) y corta updates si hay flood.

    Solo limita mensajes de texto (no callbacks de botones). Los comandos
    exentos (/start, /help) pasan siempre.
    """

    def __init__(self, limiter: RateLimiter = None):
        super().__init__(Update, _callback_noop)
        self.limiter = limiter or RateLimiter()

    async def check_update(self, update: object):
        """Aplica a todo update con usuario; decide en handle_update."""
        if isinstance(update, Update) and update.effective_user is not None:
            return True
        return None

    async def handle_update(self, update, application, check_result, context):
        mensaje = update.effective_message
        if mensaje is None or not getattr(mensaje, "text", None):
            return  # callbacks, ediciones no-texto, etc.: dejar pasar

        permitido, espera = self.limiter.verificar(update.effective_user.id, mensaje.text)
        if permitido:
            return

        try:
            if self.limiter.debe_avisar(update.effective_user.id):
                await mensaje.reply_text(
                    f"⚠️ Demasiadas solicitudes. Intenta de nuevo en {espera} segundos."
                )
        except Exception as e:
            logger.warning("No se pudo enviar aviso de rate limit: %s", e)

        raise ApplicationHandlerStop


def tarea_limpieza(limiter: RateLimiter):
    """Crea el callback del JobQueue que limpia los contadores cada minuto."""

    async def _limpiar(context):
        eliminados = limiter.limpiar()
        if eliminados:
            logger.info("Rate limiter: %d usuarios limpiados.", eliminados)

    return _limpiar
