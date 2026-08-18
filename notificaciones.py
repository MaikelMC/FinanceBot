"""
notificaciones.py - Notificaciones del bot de finanzas personales

Incluye:
- Alertas de presupuesto en tiempo real (80% / 100% / 125%)
- Resumen diario programado (hora fija 21:30 hora de Cuba)
- Catch-up de resúmenes perdidos (Render free tier)
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import config
import database
import formato
import knowledge

logger = logging.getLogger(__name__)

UMBRALES_ALERTA: List[tuple] = [
    (80, "alerta_80"),
    (100, "alerta_100"),
    (125, "alerta_125"),
]


def _parse_hora(hora: str) -> tuple:
    """Parsea 'HH:MM' (o 'HH:MM:SS') a (hora, minuto). Default 21:30."""
    try:
        partes = str(hora).split(":")
        hh = int(partes[0])
        mm = int(partes[1]) if len(partes) > 1 else 0
        return (hh, mm)
    except (ValueError, IndexError):
        return (21, 30)


def _hora_programada_hoy(zona: str, hora: str) -> datetime:
    """Retorna el datetime de hoy en la zona del usuario a la hora configurada."""
    ahora = datetime.now(ZoneInfo(zona))
    hh, mm = _parse_hora(hora)
    return ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)


def verificar_alertas_presupuesto(
    prefs: Dict[str, Any],
    planeado: float,
    gastado_antes: float,
    gastado_despues: float,
    label: str,
    simbolo: str = "$",
    abreviatura: str = "",
) -> Optional[str]:
    """Devuelve las líneas de alerta por umbrales recién cruzados (80/100/125%).

    Solo alerta cuando el porcentaje *cruza* el umbral en este gasto (evita
    repetir la alerta en cada gasto posterior). Devuelve None si no cruza nada.
    """
    if planeado <= 0:
        return None

    pct_antes = gastado_antes / planeado * 100
    pct_despues = gastado_despues / planeado * 100
    abrev = abreviatura or None

    lineas: List[str] = []
    for umbral, clave in UMBRALES_ALERTA:
        if not prefs.get(clave):
            continue
        if pct_antes < umbral <= pct_despues:
            monto_actual = formato.fmt_moneda(gastado_despues, simbolo=simbolo)
            monto_total = formato.fmt_moneda(planeado, abrev=abrev, simbolo=simbolo)
            if umbral == 80:
                lineas.append(
                    f"{formato.EMOJI_ADVERTENCIA} **{label}** cerca del límite: "
                    f"{monto_actual} de {monto_total} — 80%"
                )
            elif umbral == 100:
                lineas.append(
                    f"{formato.EMOJI_ADVERTENCIA} **{label}** agotado: "
                    f"{monto_actual} de {monto_total}"
                )
            else:
                lineas.append(
                    f"{formato.EMOJI_ADVERTENCIA} **{label}** excedido: "
                    f"{monto_actual} de {monto_total} — {pct_despues:.0f}%"
                )

    return "\n".join(lineas) if lineas else None


def formatear_resumen_diario(usuario: Dict[str, Any]) -> str:
    """Compone el texto del resumen diario (gastos/ingresos de hoy + balance)."""
    try:
        hoy = date.today().isoformat()
        uid = usuario["id"]
        moneda_lookup = knowledge._moneda_lookup_usuario(usuario)

        gastos = database.obtener_transacciones_por_fecha(uid, hoy, hoy, "gasto")
        ingresos = database.obtener_transacciones_por_fecha(uid, hoy, hoy, "ingreso")

        def totales_por_moneda(trans):
            agg: Dict[Any, float] = {}
            for t in trans:
                mid = t.get("moneda_id")
                agg[mid] = agg.get(mid, 0.0) + float(t.get("cantidad", 0))
            return agg

        total_g = totales_por_moneda(gastos)
        total_i = totales_por_moneda(ingresos)

        lineas = [
            f"{formato.EMOJI_PRESUPUESTO} **Resumen diario**",
            f"📅 {date.today().strftime('%d/%m/%Y')}",
            formato.SEPARADOR,
        ]

        if total_i or total_g:
            if total_g:
                for mid, monto in total_g.items():
                    lineas.append(f"{formato.EMOJI_GASTO} Gastos: {knowledge._formatear_monto(moneda_lookup, mid, monto)}")
            else:
                lineas.append(f"{formato.EMOJI_GASTO} Gastos: $0.00")
            if total_i:
                for mid, monto in total_i.items():
                    lineas.append(f"{formato.EMOJI_INGRESO} Ingresos: {knowledge._formatear_monto(moneda_lookup, mid, monto)}")
            else:
                lineas.append(f"{formato.EMOJI_INGRESO} Ingresos: $0.00")
            lineas.append(f"📋 {len(gastos) + len(ingresos)} movimiento(s) registrado(s).")
        else:
            lineas.append("😴 Sin movimientos hoy.")

        # Balance del mes (el balance del bot se consulta por mes en curso)
        balance = database.obtener_balance(uid)
        por_moneda = balance.get("por_moneda", {})
        lineas.append("")
        if len(por_moneda) == 1 and list(por_moneda.keys()) == ["Sin moneda"]:
            lineas.append(f"{formato.EMOJI_BALANCE} Balance del mes: **{formato.fmt_moneda(balance.get('neto', 0), signo=True)}**")
        elif por_moneda:
            for abrev, datos in por_moneda.items():
                simbolo = datos.get("simbolo", "$")
                neto = datos["ingresos"] - datos["gastos"]
                lineas.append(
                    f"{formato.EMOJI_BALANCE} Balance del mes: "
                    f"**{formato.fmt_moneda(neto, abrev=abrev, signo=True, simbolo=simbolo)}**"
                )
        else:
            lineas.append(f"{formato.EMOJI_BALANCE} Balance: **{formato.fmt_moneda(0, signo=True)}**")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error formateando resumen diario: %s", e)
        return "📊 No pude generar tu resumen diario.\nIntenta de nuevo o escribe /help."


def _resumen_due(usuario: Dict[str, Any], prefs: Dict[str, Any]) -> bool:
    """True si el resumen diario del usuario está pendiente de envío hoy.

    Por ahora la hora y la zona están fijas para todos (21:30 hora de Cuba)
    configuradas en config.HORA_RESUMEN_DEFAULT / config.DEFAULT_TIMEZONE.
    """
    if not prefs.get("resumen_diario"):
        return False
    hora = config.HORA_RESUMEN_DEFAULT
    zona = config.DEFAULT_TIMEZONE
    try:
        programado = _hora_programada_hoy(zona, hora)
    except Exception:
        return False
    ahora = datetime.now(ZoneInfo(zona))
    return ahora >= programado and prefs.get("ultimo_resumen") != ahora.date().isoformat()


async def _enviar_resumen(context, usuario: Dict[str, Any], motivo: str, chat_id: Optional[int] = None) -> None:
    """Envía el resumen diario pendiente y lo marca como enviado (si aplica)."""
    uid = usuario.get("id")
    chat_id = chat_id or usuario.get("telegram_user_id")
    if not uid or not chat_id:
        return
    try:
        prefs = database.obtener_preferencias(uid)
    except Exception as e:
        logger.error("No se pudo leer preferencias de %d: %s", uid, e)
        return
    if not _resumen_due(usuario, prefs):
        return

    texto = formatear_resumen_diario(usuario)
    try:
        await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode="Markdown")
    except Exception as e:
        logger.error("Error enviando resumen diario a %d (%s): %s", uid, motivo, e)
        return

    zona = config.DEFAULT_TIMEZONE
    try:
        hoy_str = datetime.now(ZoneInfo(zona)).date().isoformat()
    except Exception:
        hoy_str = date.today().isoformat()
    try:
        database.guardar_preferencias(uid, ultimo_resumen=hoy_str)
    except Exception as e:
        logger.error("Error marcando ultimo_resumen de %d: %s", uid, e)
    logger.info("Resumen diario enviado a usuario %d (%s)", uid, motivo)


async def tarea_resumen_diario(context) -> None:
    """Job de barrido: envía los resúmenes diarios pendientes (cada 60s)."""
    try:
        usuarios = database.obtener_todos_los_usuarios()
    except Exception as e:
        logger.error("Error listando usuarios en sweep: %s", e)
        return
    for u in usuarios:
        try:
            await _enviar_resumen(context, u, "sweep")
        except Exception as e:
            logger.error("Error en sweep para usuario %s: %s", u.get("id"), e)


async def enviar_resumen_pendiente(context, chat_id: int, usuario: Dict[str, Any]) -> None:
    """Catch-up: envía el resumen atrasado al primer mensaje del usuario."""
    try:
        await _enviar_resumen(context, usuario, "catch-up", chat_id=chat_id)
    except Exception as e:
        logger.error("Error en catch-up para %s: %s", usuario.get("id"), e)