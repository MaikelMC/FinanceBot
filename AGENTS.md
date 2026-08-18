# AGENTS.md - Personal Finance Bot

## Quick Start

**Start the bot:**
```bash
python main.py
```

**Create virtual environment:**
```bash
python -m venv venv && venv\\Scripts\\activate && pip install python-telegram-bot python-dotenv mistralai openpyxl
```

## Architecture & Entry Points

**Main flow:**
- `main.py:89` - Entry point, calls `run_bot()`
- `handlers.py` - Intent detection (English) + command/callback handlers
- `knowledge.py` - AI processing for Spanish messages
- `ai_client.py` - AI client integration
- `notificaciones.py` - Alertas de presupuesto (80/100/125%), resumen diario, sweep y catch-up
- `exportador.py` - Exportación a Excel (.xlsx) y CSV con paginación por límite de filas

**Database schema:**
- SQLite at `data/finanzas.db`
- Tables: `usuarios`, `categorias`, `transacciones`, `presupuestos`, `metas_ahorro`, `monedas`, `notificaciones`, `preferencias_notificaciones`

**Key directories:**
- `data/` - SQLite DB, images
- `prompts/` - System prompts

## Configuration

**Required env vars:**
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `AI_PROVIDER` - "ollama" or "mistral"
- For mistral: `MISTRAL_API_KEY`

**Environment file:**
```bash
# .env.example
title=``
TELEGRAM_BOT_TOKEN=your_token_here
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Notificaciones (resumen diario)
NOTIF_WAKE_UTC=01:30              # 1er wake (UTC): 21:30 Cuba en verano; el 2do es 02:30
DEFAULT_TIMEZONE=America/Havana   # Zona fija del resumen diario
HORA_RESUMEN_DEFAULT=21:30        # Hora fija del resumen diario (para todos)
```

## Development Commands

**Set up fresh environment:**
```bash
python create_venv.py          # Complete setup
python setup_environment.py     # Quick setup
```

**Verify installation:**
```bash
python verify_system.py         # Check all dependencies
```

**Run verification:**
```bash
python -c "import config, database, knowledge; config.validate_config(); database.crear_tablas(); print('✓ Config OK')"
```

## Language & Intent Detection

**English messages:** Use `handlers.py` for intent detection
- Keywords: "gast", "ingress", "presupuesto", "ahorrar", "consultar"
- Regex-based parsing for basic transactions

**Spanish messages:** Use `knowledge.py` for AI processing
- Intent patterns: gasto, ingreso, balance, categorias
- AI-powered natural language understanding

## Common Workflows

**User starts bot:**
- Command `/start` creates user entry
- Shows statistics and available features

**Register transaction (English):**
- Detect intent with `handlers._detectar_intencion()`
- Parse with `handlers._parsear_transaccion()`
- Store in database

**Register transaction (Spanish):**
- Process through AI client if no regex match
- Parse structured response from Mistral/Ollama

**Check balance:**
- Query `database.obtener_balance(usuario_id)`
- Aggregates ingresos/gastos/neto

**Export data (v2.10):**
- `/exportar` sin args → menú formato (Excel/CSV) → menú período (todo/mes/30 días); args: `/exportar xlsx todo|mes|YYYY-MM`, `/exportar csv 2026-07`
- Flujo NL: intent `exportar` → `ai_client._procesar_exportar` devuelve pendiente `{"accion": "exportar", "formato", "periodo"}` → `handlers.handle_message` llama `_enviar_exportacion`
- `_enviar_exportacion`: `_resolver_periodo(periodo)` → `obtener_transacciones[_por_fecha]` + `obtener_balance` + `obtener_monedas` → `exportador.generar_xlsx` (hojas Resumen/Movimientos/Gastos por categoría, paginada cada 100k filas) o `generar_csv_partes` (utf-8-sig, `_parte_N.csv`) → `send_document` → borra archivos en `try/finally`
- Callbacks: `exp_fmt_xlsx`/`exp_fmt_csv` → `exp_per_todo`/`exp_per_mes`/`exp_per_30`; formato temporal en `context.user_data["exp_formato"]`
- `requirements.txt` incluye `openpyxl>=3.1.5`; `exportador.py` es pura Python (OK en Render)
- Límite: no conversión de monedas; "este mes" usa fecha UTC del servidor; gsheets lento para "todo" con mucho historial

**Notifications (v2.9):**
- `/notificaciones` → `configurar_notificaciones()` renders menu; callbacks `notif_*` toggle resumen/alerts
- Hora y zona del resumen **fijas** para todos: 21:30 America/Havana (config.HORA_RESUMEN_DEFAULT / DEFAULT_TIMEZONE)
- Alertas en `knowledge._procesar_gasto`: captura `gastado_antes`, llama `notificaciones.verificar_alertas_presupuesto` (import lazy), anexa al texto
- Resumen diario: `main.py` programa `run_repeating(tarea_resumen_diario, 60s)`; `enviar_resumen_pendiente` (catch-up) se llama en `handle_message`
- Prefs en `preferencias_notificaciones` (ambos backends): `alerta_80/100/125`, `resumen_diario`, `ultimo_resumen` (hora/zona se guardan pero no se usan por ahora)
- Wake en Render free tier: `.github/workflows/notifications-wake.yml` (01:30 y 02:30 UTC) + Secret `BOT_WEBHOOK_URL`

## Important Gotchas

**Database user isolation:**
- Each Telegram user has isolated data
- User lookup by `telegram_user_id`
- Separate categories/transactions per user

**Category types:**
- Gastos, ingresos, ahorros, inversiones
- Each with specific validation rules

**AI provider switching:**
- Set `AI_PROVIDER` in `.env`
- Toggle between regex-based (handlers) and AI-based (knowledge)
- Fallback logic in `ai_client.py`

**Error handling:**
- All DB operations wrapped in try/catch
- Graceful fallbacks when AI unavailable
- Extensive logging for debugging

## Testing & Debugging

**Run verification:**
```bash
python verify_system.py
```

**Check structure:**
```bash
python check_structure.py
```

## Database Backends

**SQLite (default):** `database.py` → `database_sqlite.py`
- Local file at `data/finanzas.db`
- No extra config needed

**Google Sheets:** `database.py` → `database_gsheets.py`
- Requires `.env`: `DB_BACKEND=gsheets`, `GOOGLE_SHEETS_CREDENTIALS`, `GOOGLE_SHEETS_SPREADSHEET_ID`
- Install: `venv\Scripts\python.exe -m pip install gspread pandas gspread-dataframe`
- Setup: Create GCP service account, share sheet with its email, place JSON key at `data/finanzas-sa.json`

**Switching:**
- Change `DB_BACKEND` in `.env` — zero code changes needed
- All 16 public DB functions have identical signatures in both backends

## Monorepo Notes

Single package structure with clear boundaries:
- `main.py` - Orchestrates bot
- `config.py` - Central config
- `database.py` - Proxy backend (routes to sqlite/gsheets)
- `database_sqlite.py` - SQLite data access layer
- `database_gsheets.py` - Google Sheets data access layer
- `handlers.py` - Message parsing (EN)
- `knowledge.py` - AI processing (ES)
- `ai_client.py` - AI integration
- `notificaciones.py` - Alerts + daily summary (sweep & catch-up)
- `exportador.py` - Excel/CSV export + period resolution
- `setup_environment.py` - Dev environment setup

All dependencies in virtual environment - no global installs.

## Deployment (Render.com)

**1. Push to GitHub**
- Create new repo in GitHub
- Push code (credentials.json y .env estarán en .gitignore)

**2. Deploy en Render**
- New + → Web Service → Connect GitHub repo
- Build Command: `pip install -r requirements.txt`
- Start Command: `python main.py`

**3. Environment Variables in Render Dashboard**
- `TELEGRAM_BOT_TOKEN` (from @BotFather)
- `AI_PROVIDER` = `mistral`
- `MISTRAL_API_KEY` (from Mistral AI dashboard)
- `DB_BACKEND` = `gsheets` (opcional, default es sqlite)
- `GOOGLE_SHEETS_CREDENTIALS_JSON` = [JSON content of credentials file]
- `GOOGLE_SHEETS_SPREADSHEET_ID` = [your spreadsheet ID]

**Para subir el credentials.json a Render:**
1. Abrí el archivo `credentials.json`
2. Copiá todo el contenido JSON
3. En Render Dashboard → Environment → Add Variable
4. Clave: `GOOGLE_SHEETS_CREDENTIALS_JSON`, Valor: el JSON completo

**Nota:** Google Sheets funciona en Render con esta configuración.
