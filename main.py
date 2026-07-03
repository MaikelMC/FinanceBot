"""
main.py - Bot de finanzas personales
Punto de entrada del bot. Configura el bot con inteligencia financiera y arranca el polling.
"""

import asyncio
import json
import logging
import signal
import sys
import urllib.request
import urllib.error
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
import database
from handlers import start, handle_message, error_handler
from handlers import consultar_usuario, consultar_comandos

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _setup_webhook():
    """
    Registra el webhook en Telegram vía API REST directamente.
    Usa urllib (stdlib) para evitar conflictos con el event loop de run_webhook().
    """
    logger.info("Configurando webhook en Telegram: %s", config.WEBHOOK_URL)

    data = json.dumps({
        "url": config.WEBHOOK_URL,
        "secret_token": config.WEBHOOK_SECRET,
        "drop_pending_updates": True,
    }).encode()

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/setWebhook",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                logger.info("✓ Webhook configurado exitosamente en Telegram")
            else:
                logger.warning("⚠ Telegram rechazó el webhook: %s", result.get("description", ""))
    except urllib.error.URLError as e:
        logger.warning("⚠ No se pudo configurar el webhook (error de red): %s", e)


def _build_app():
    """Construye y configura la aplicación del bot con todos los handlers."""
    config.validate_config()
    logger.info("Configuración validada correctamente.")

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    database.crear_tablas()
    logger.info("Base de datos de finanzas inicializada.")

    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()

    # === COMANDOS PRINCIPALES ===
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("user", consultar_usuario))
    app.add_handler(CommandHandler("help", consultar_comandos))

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
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


def main():
    logger.info("Iniciando finanzas-mypime...")

    if config.WEBHOOK_URL:
        # Modo webhook (producción en Render.com)
        logger.info("Iniciando en modo webhook: %s", config.WEBHOOK_URL)
        app = _build_app()

        # Auto-configurar webhook en Telegram antes de iniciar el servidor
        _setup_webhook()

        logger.info("Iniciando servidor webhook en puerto %s", config.WEBHOOK_PORT)
        app.run_webhook(
            listen="0.0.0.0",
            port=config.WEBHOOK_PORT,
            webhook_url=config.WEBHOOK_URL,
            secret_token=config.WEBHOOK_SECRET,
        )
    else:
        # Modo polling (desarrollo local)
        asyncio.run(run_bot())


if __name__ == "__main__":
    main()
