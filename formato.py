"""Helpers de presentación para los mensajes del bot.

Sistema de diseño definido en `REDISENO MENSAJES.md`: emojis semánticos
(tabla cerrada), separador corto, montos con separador de miles y jerarquía
de 3 niveles (título -> separador -> cuerpo).
"""

from typing import List, Optional

SEPARADOR = "┈┈┈┈┈┈┈┈┈┈"

EMOJI_INGRESO = "📈"
EMOJI_GASTO = "📉"
EMOJI_BALANCE = "💰"
EMOJI_PRESUPUESTO = "📊"
EMOJI_META = "🎯"
EMOJI_MONEDA = "💱"
EMOJI_NOTIFICACION = "🔔"
EMOJI_ADVERTENCIA = "⚠️"
EMOJI_OK = "✅"
EMOJI_ERROR = "❌"
EMOJI_INFO = "ℹ️"
EMOJI_ELIMINAR = "🗑️"


def fmt_monto(valor: float) -> str:
    """5000.0 -> '5,000.00'"""
    return f"{valor:,.2f}"


def fmt_moneda(valor: float, abrev: Optional[str] = None, signo: bool = False, simbolo: str = "$") -> str:
    """1650.0, 'USD' -> '$1,650.00 (USD)' ; con signo -> '+$1,650.00 (USD)'.

    `simbolo` permite usar el símbolo real de la moneda (€, ₿, £, ...).
    """
    prefijo = "+" if signo and valor >= 0 else ("-" if signo and valor < 0 else "")
    cuerpo = f"{prefijo}{simbolo}{fmt_monto(abs(valor)) if signo else fmt_monto(valor)}"
    return f"{cuerpo} ({abrev})" if abrev else cuerpo


def header(emoji: str, titulo: str) -> str:
    """Título de sección: un único emoji + negrita (Title Case)."""
    return f"{emoji} **{titulo}**"


NOMBRES_MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def nombre_mes_actual() -> str:
    """Nombre y año del mes en curso, p. ej. 'agosto 2026'."""
    from datetime import date
    hoy = date.today()
    return f"{NOMBRES_MESES.get(hoy.month, str(hoy.month))} {hoy.year}"


def barra_progreso(pct: float, largo: int = 10) -> str:
    """Barra de progreso en backticks, 0-100%."""
    pct = max(0.0, min(100.0, pct))
    llenos = round((pct / 100.0) * largo)
    return "`" + "█" * llenos + "░" * (largo - llenos) + "`"


def bloque(titulo_con_emoji: str, lineas: List[str], separador: bool = True) -> str:
    """Compone un bloque: título + separador (opcional) + líneas de datos."""
    partes = [titulo_con_emoji]
    if separador:
        partes.append(SEPARADOR)
    partes.extend(lineas)
    return "\n".join(partes)