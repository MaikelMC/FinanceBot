"""
notificaciones.py - Notificaciones del bot de finanzas personales

Incluye:
- Alertas de presupuesto en tiempo real (80% / 100% / 125%)
- Resumen diario programado (sweep con zona horaria por usuario)
- Catch-up de resúmenes perdidos (Render free tier)
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import config
import database
import knowledge

logger = logging.getLogger(__name__)

UMBRALES_ALERTA: List[tuple] = [
    (80, "alerta_80"),
    (100, "alerta_100"),
    (125, "alerta_125"),
]


def _parse_hora(hora: str) -> tuple:
    """Parsea 'HH:MM' (o 'HH:MM:SS') a (hora, minuto). Default 20:00."""
    try:
        partes = str(hora).split(":")
        hh = int(partes[0])
        mm = int(partes[1]) if len(partes) > 1 else 0
        return (hh, mm)
    except (ValueError, IndexError):
        return (20, 0)


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
    abrev = f" ({abreviatura})" if abreviatura else ""

    lineas: List[str] = []
    for umbral, clave in UMBRALES_ALERTA:
        if not prefs.get(clave):
            continue
        if pct_antes < umbral <= pct_despues:
            if umbral == 80:
                lineas.append(
                    f"⚠️ *Presupuesto '{label}'* al 80%: "
                    f"{simbolo}{gastado_despues:.2f}{abrev} de {simbolo}{planeado:.2f}{abrev}. ¡Cuidado!"
                )
            elif umbral == 100:
                lineas.append(
                    f"🚨 *Presupuesto '{label}'* agotado: "
                    f"{simbolo}{gastado_despues:.2f}{abrev} de {simbolo}{planeado:.2f}{abrev}."
                )
            else:
                lineas.append(
                    f"⛔ *Presupuesto '{label}'* excedido: "
                    f"{simbolo}{gastado_despues:.2f}{abrev} de {simbolo}{planeado:.2f}{abrev} "
                    f"({pct_despues:.0f}%)."
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
            "📊 *RESUMEN DIARIO*",
            f"📅 {date.today().strftime('%d/%m/%Y')}",
            "━━━━━━━━━━━━━━━━━",
        ]

        if total_i or total_g:
            if total_g:
                for mid, monto in total_g.items():
                    lineas.append(f"💸 Gastos: {knowledge._formatear_monto(moneda_lookup, mid, monto)}")
            else:
                lineas.append("💸 Gastos: $0.00")
            if total_i:
                for mid, monto in total_i.items():
                    lineas.append(f"💰 Ingresos: {knowledge._formatear_monto(moneda_lookup, mid, monto)}")
            else:
                lineas.append("💰 Ingresos: $0.00")
            lineas.append(f"📋 {len(gastos) + len(ingresos)} movimiento(s) registrado(s).")
        else:
            lineas.append("😴 Sin movimientos hoy.")

        # Balance actual
        balance = database.obtener_balance(uid)
        por_moneda = balance.get("por_moneda", {})
        lineas.append("")
        if len(por_moneda) == 1 and list(por_moneda.keys()) == ["Sin moneda"]:
            lineas.append(f"💵 Balance actual: ${balance.get('neto', 0):.2f}")
        elif por_moneda:
            for abrev, datos in por_moneda.items():
                simbolo = datos.get("simbolo", "$")
                neto = datos["ingresos"] - datos["gastos"]
                lineas.append(f"💵 Balance actual ({abrev}): {simbolo}{neto:.2f}")
        else:
            lineas.append("💵 Balance actual: $0.00")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error formateando resumen diario: %s", e)
        return "📊 No pude generar tu resumen diario en este momento."


def _resumen_due(usuario: Dict[str, Any], prefs: Dict[str, Any]) -> bool:
    """True si el resumen diario del usuario está pendiente de envío hoy."""
    if not prefs.get("resumen_diario"):
        return False
    hora = prefs.get("hora_resumen") or config.HORA_RESUMEN_DEFAULT
    zona = prefs.get("zona_horaria") or config.DEFAULT_TIMEZONE
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

    zona = prefs.get("zona_horaria") or config.DEFAULT_TIMEZONE
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