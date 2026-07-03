"""
config.py - Configuración del bot de finanzas personales
Carga variables de entorno y expone la configuración centralizada.
"""

import os
import sys
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "finanzas.db"
IMAGES_DIR = DATA_DIR / "images"
PROMPTS_DIR = BASE_DIR / "prompts"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Backend de base de datos: "sqlite" (default) o "gsheets"
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").lower()

# Google Sheets (solo si DB_BACKEND=gsheets)
# Option 1: File path (local development)
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
# Option 2: JSON string (Render.com - set as env var)
GOOGLE_SHEETS_CREDENTIALS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "")
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")

AI_PROVIDER = os.getenv("AI_PROVIDER", "mistral").lower()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt.txt"

# Webhook (para despliegue en Render.com)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")
WEBHOOK_PORT = int(os.getenv("PORT", 8000))


def get_system_prompt() -> str:
    """Lee y retorna el prompt del sistema desde el archivo de texto."""
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return "Sos un asistente financiero personal experto. Ayudás a los usuarios a registrar gastos, ingresos, ahorrar, y gestionar presupuestos mientras mantené un control claro de su situación financiera."


def validate_config():
    """Valida que la configuración mínima esté presente."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError(
            "Falta TELEGRAM_BOT_TOKEN. "
            "Obtén uno en @BotFather y definilo en el archivo .env"
        )
    if DB_BACKEND not in ("sqlite", "gsheets"):
        raise ValueError(
            f"DB_BACKEND='{DB_BACKEND}' no válido. Usa 'sqlite' o 'gsheets'."
        )
    if DB_BACKEND == "gsheets":
        if not GOOGLE_SHEETS_CREDENTIALS and not GOOGLE_SHEETS_CREDENTIALS_JSON:
            raise ValueError(
                "DB_BACKEND=gsheets pero falta GOOGLE_SHEETS_CREDENTIALS o GOOGLE_SHEETS_CREDENTIALS_JSON en .env"
            )
        # Only check file existence if GOOGLE_SHEETS_CREDENTIALS looks like a path (not JSON)
        if GOOGLE_SHEETS_CREDENTIALS and not GOOGLE_SHEETS_CREDENTIALS_JSON:
            if not Path(GOOGLE_SHEETS_CREDENTIALS).exists():
                raise ValueError(
                    f"Archivo de credenciales no encontrado: {GOOGLE_SHEETS_CREDENTIALS}"
                )
        if not GOOGLE_SHEETS_SPREADSHEET_ID:
            raise ValueError(
                "DB_BACKEND=gsheets pero falta GOOGLE_SHEETS_SPREADSHEET_ID en .env"
            )
    if AI_PROVIDER == "mistral" and not MISTRAL_API_KEY:
        raise ValueError(
            "AI_PROVIDER es 'mistral' pero falta MISTRAL_API_KEY en .env"
        )
    if AI_PROVIDER == "ollama" and not OLLAMA_BASE_URL:
        raise ValueError(
            "AI_PROVIDER es 'ollama' pero no se pudo resolver OLLAMA_BASE_URL"
        )