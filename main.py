"""
main.py - Bot de finanzas personales
Punto de entrada del bot. Configura el bot con inteligencia financiera y arranca el polling.
"""

import asyncio
import logging
import signal
import sys
from urllib.parse import urlparse
from telegram import Bot, BotCommand, MenuButtonCommands
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

import config
import database
import logging_config

# Logging centralizado: archivo rotativo (data/logs/finanzas.log) + consola.
# Debe ejecutarse ANTES de que los demás módulos emitan sus primeros logs.
logging_config.configurar_logging()

from handlers import start, handle_message, error_handler
from handlers import consultar_usuario, consultar_comandos, handle_callback_query, eliminar_historial, anuncio
from handlers import configurar_notificaciones
from handlers import consultar_categorias, consultar_gastos, consultar_ingresos, consultar_metas, consultar_resumen
from handlers import exportar_datos
from handlers import ver_metricas, soporte
import notificaciones
import rate_limiter
import metricas

logger = logging.getLogger(__name__)

COMANDOS_MENU = [
    BotCommand("start", "Iniciar o reiniciar el bot y ver tu balance"),
    BotCommand("resumen", "Resumen del mes actual"),
    BotCommand("categorias", "Ver tus categorías financieras"),
    BotCommand("gastos", "Ver tus últimos gastos"),
    BotCommand("ingresos", "Ver tus últimos ingresos"),
    BotCommand("metas", "Ver tus metas de ahorro"),
    BotCommand("notificaciones", "Alertas de presupuesto y resumen diario"),
    BotCommand("exportar", "Exporta tus datos a Excel/CSV"),
    BotCommand("help", "Ver todos los comandos y ejemplos de uso"),
    BotCommand("user", "Ver tu información de usuario"),
    BotCommand("delete", "Borrar todo el historial de transacciones"),
    BotCommand("soporte", "Reportar un problema al administrador"),
]


async def _post_init(application):
    """Registra el menú de comandos de Telegram (sugerencias al escribir '/')."""
    await application.bot.set_my_commands(COMANDOS_MENU)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("Menú de comandos registrado (%d comandos).", len(COMANDOS_MENU))


def _build_app():
    """Construye y configura la aplicación del bot con todos los handlers."""
    config.validate_config()
    logger.info("Configuración validada correctamente.")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    database.crear_tablas()
    logger.info("Base de datos de finanzas inicializada.")

    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).post_init(_post_init).build()

    # === RATE LIMITING (anti-flood, corre antes que todos los handlers) ===
    limiter = rate_limiter.RateLimiter()
    app.add_handler(rate_limiter.RateLimitMiddleware(limiter), group=-1)
    logger.info(
        "Rate limiting activo: %d mensajes / %ds por usuario (exentos: %s).",
        limiter.max_requests, int(limiter.window), ", ".join(rate_limiter.COMANDOS_EXENTOS),
    )

    # === COMANDOS PRINCIPALES ===
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("user", consultar_usuario))
    app.add_handler(CommandHandler("help", consultar_comandos))
    app.add_handler(CommandHandler("delete", eliminar_historial))
    app.add_handler(CommandHandler("anuncio", anuncio))
    app.add_handler(CommandHandler("categorias", consultar_categorias))
    app.add_handler(CommandHandler("gastos", consultar_gastos))
    app.add_handler(CommandHandler("ingresos", consultar_ingresos))
    app.add_handler(CommandHandler("metas", consultar_metas))
    app.add_handler(CommandHandler("resumen", consultar_resumen))
    app.add_handler(CommandHandler("notificaciones", configurar_notificaciones))
    app.add_handler(CommandHandler("exportar", exportar_datos))
    app.add_handler(CommandHandler("soporte", soporte))
    app.add_handler(CommandHandler("metricas", ver_metricas))

    # === JOB DE RESÚMENES DIARIOS (sweep cada 60s) ===
    if app.job_queue is not None:
        app.job_queue.run_repeating(
            notificaciones.tarea_resumen_diario,
            interval=60,
            first=10,
            name="resumen_diario",
        )
        logger.info("Job de resumen diario programado (intervalo 60s).")

        # === LIMPIEZA DE CONTADORES DE RATE LIMIT (cada minuto) ===
        app.job_queue.run_repeating(
            rate_limiter.tarea_limpieza(limiter),
            interval=max(int(limiter.window), 1),
            first=int(limiter.window),
            name="rate_limit_cleanup",
        )

        # === PODA DE ACTIVIDAD VIEJA EN MÉTRICAS (cada 30 min) ===
        app.job_queue.run_repeating(
            metricas.tarea_poda(),
            interval=1800,
            first=1800,
            name="metricas_poda",
        )
    else:
        logger.warning("JobQueue no disponible (falta apscheduler). El resumen diario solo llegará por catch-up.")

    # === BOTONES INLINE ===
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # === MANEJO DE MENSAJES EN LENGUAJE NATURAL ===
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # === MANEJO DE ERRORES ===
    app.add_error_handler(error_handler)

    logger.info(
        "Bot de finanzas iniciado correctamente. Proveedor IA: %s | Modelo: %s",
        config.AI_PROVIDER,
        config.OLLAMA_MODEL if config.AI_PROVIDER == "ollama" else config.MISTRAL_MODEL,
    )

    return app


async def run_bot():
    """Ejecuta el bot en modo polling (desarrollo local)."""
    app = _build_app()

    await app.initialize()

    # Forzar deleteWebhook para evitar conflictos si hay un webhook activo
    bot = Bot(config.TELEGRAM_BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook eliminado (si existía). Iniciando polling...")

    await app.start()
    try:
        await app.updater.start_polling(
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error("Error starting polling: %s", e)
        raise

    stop_event = asyncio.Event()

    def _signal_handler():
        stop_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Apagando bot de finanzas...")
        try:
            import database_gsheets
            database_gsheets.flush_all()
        except Exception:
            pass
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


def main():
    logger.info("Iniciando finanzas-mypime...")

    if config.WEBHOOK_URL:
        # Modo webhook (producción en Render.com)
        logger.info("Iniciando en modo webhook: %s", config.WEBHOOK_URL)
        app = _build_app()

        # Extraer el path del webhook_url para que coincida con el servidor local
        url_path = urlparse(config.WEBHOOK_URL).path.lstrip("/")

        logger.info("Iniciando servidor webhook en puerto %s (path: /%s)", config.WEBHOOK_PORT, url_path)
        app.run_webhook(
            listen="0.0.0.0",
            port=config.WEBHOOK_PORT,
            url_path=url_path,
            webhook_url=config.WEBHOOK_URL,
            secret_token=config.WEBHOOK_SECRET,
        )
    else:
        # Modo polling (desarrollo local)
        asyncio.run(run_bot())


if __name__ == "__main__":
    main()
