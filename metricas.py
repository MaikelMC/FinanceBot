"""
metricas.py - Métricas en memoria para el comando admin /metricas.

Contadores thread-safe que viven mientras corre el proceso del bot:
- Mensajes procesados / bloqueados por flood
- Usuarios activos por ventana de tiempo (5 min, 1 h)
- Transacciones registradas hoy (auto-reset al cambiar la fecha)
- Errores de la última hora (alimentado desde logging_config)
- Uptime del proceso

NO se persisten: al reiniciar el bot los contadores empiezan de cero
(las métricas "hoy" y "última hora" se recalculan solas con el uso).
"""

import threading
import time
from collections import deque
from datetime import datetime, timezone


class Metricas:
    """Contadores thread-safe en memoria."""

    def __init__(self):
        self.inicio = time.time()
        self._lock = threading.Lock()
        self.mensajes_procesados = 0
        self.mensajes_bloqueados = 0
        # Actividad por usuario: {telegram_user_id: último timestamp}
        self._actividad = {}
        # Transacciones hoy: {"fecha": "YYYY-MM-DD", "total": int}
        self._trans_hoy = {"fecha": self._hoy(), "total": 0}
        # Timestamps de errores recientes (ventana de 1 h)
        self._errores = deque()

    @staticmethod
    def _hoy() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # Registro de eventos
    # ------------------------------------------------------------------
    def registrar_mensaje(self, telegram_user_id: int, bloqueado: bool = False) -> None:
        """Llamar por cada mensaje de texto recibido (bloqueado o no)."""
        ahora = time.time()
        with self._lock:
            if bloqueado:
                self.mensajes_bloqueados += 1
            else:
                self.mensajes_procesados += 1
            self._actividad[telegram_user_id] = ahora

    def registrar_transaccion(self, cantidad: int = 1) -> None:
        """Suma transacciones registradas hoy; resetea el contador al cambiar el día."""
        with self._lock:
            hoy = self._hoy()
            if self._trans_hoy["fecha"] != hoy:
                self._trans_hoy = {"fecha": hoy, "total": 0}
            self._trans_hoy["total"] += cantidad

    def registrar_error(self) -> None:
        """Marca un error ocurrido ahora (lo llama el handler de logging)."""
        with self._lock:
            self._errores.append(time.time())

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def activos(self, segundos: int) -> int:
        """Usuarios distintos con actividad en los últimos N segundos."""
        limite = time.time() - segundos
        with self._lock:
            return sum(1 for t in self._actividad.values() if t > limite)

    def limpiar_actividad_vieja(self, segundos: int = 7200) -> None:
        """Poda entradas de actividad más viejas que N segundos (default 2 h)."""
        limite = time.time() - segundos
        with self._lock:
            self._actividad = {u: t for u, t in self._actividad.items() if t > limite}

    def transacciones_hoy(self) -> int:
        with self._lock:
            if self._trans_hoy["fecha"] != self._hoy():
                return 0
            return self._trans_hoy["total"]

    def errores_ultima_hora(self) -> int:
        """Cantidad de errores registrados en los últimos 60 minutos."""
        corte = time.time() - 3600
        with self._lock:
            while self._errores and self._errores[0] <= corte:
                self._errores.popleft()
            return len(self._errores)

    def uptime_str(self) -> str:
        """Uptime legible, ej: '2d 4h 12m' o '35m'."""
        segs = int(time.time() - self.inicio)
        dias, segs = divmod(segs, 86400)
        horas, segs = divmod(segs, 3600)
        minutos = segs // 60
        if dias:
            return f"{dias}d {horas}h {minutos}m"
        if horas:
            return f"{horas}h {minutos}m"
        return f"{minutos}m"


# Instancia única para toda la app
_instancia = Metricas()


# ============================================================
# API a nivel de módulo (la usan handlers, rate_limiter, etc.)
# ============================================================

def registrar_mensaje(telegram_user_id: int, bloqueado: bool = False) -> None:
    _instancia.registrar_mensaje(telegram_user_id, bloqueado)


def registrar_transaccion(cantidad: int = 1) -> None:
    _instancia.registrar_transaccion(cantidad)


def registrar_error() -> None:
    _instancia.registrar_error()


def activos(segundos: int) -> int:
    return _instancia.activos(segundos)


def limpiar_actividad_vieja(segundos: int = 7200) -> None:
    _instancia.limpiar_actividad_vieja(segundos)


def snapshot() -> dict:
    """Estado completo de los contadores en un dict plano (para volcar a JSON)."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_segundos": round(time.time() - _instancia.inicio, 1),
        "mensajes_procesados": _instancia.mensajes_procesados,
        "mensajes_bloqueados": _instancia.mensajes_bloqueados,
        "activos_5min": _instancia.activos(300),
        "activos_1hora": _instancia.activos(3600),
        "transacciones_hoy": _instancia.transacciones_hoy(),
        "errores_ultima_hora": _instancia.errores_ultima_hora(),
    }


def transacciones_hoy() -> int:
    return _instancia.transacciones_hoy()


def errores_ultima_hora() -> int:
    return _instancia.errores_ultima_hora()


def uptime_str() -> str:
    return _instancia.uptime_str()


def mensajes() -> tuple:
    """Retorna (procesados, bloqueados)."""
    with _instancia._lock:
        return _instancia.mensajes_procesados, _instancia.mensajes_bloqueados


def reset() -> None:
    """Reinicia todos los contadores (para tests)."""
    global _instancia
    _instancia = Metricas()


def tarea_poda():
    """Callback del JobQueue que poda la actividad vieja cada 30 min."""

    async def _poda(context):
        _instancia.limpiar_actividad_vieja()

    return _poda
