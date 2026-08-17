# Personal Finance Bot — Stack completo

## 1. Resumen

Bot de Telegram para finanzas personales con procesamiento de lenguaje natural en español/inglés. Permite registrar gastos e ingresos, gestionar presupuestos (con nombre propio y moneda), metas de ahorro y múltiples monedas mediante mensajes conversacionales. Usa un pipeline híbrido: **fast-path regex** (cero costo, ~80% de mensajes) + **IA** (Mistral/Ollama) para comprensión avanzada, con caché de resultados. Persistencia en **SQLite (local)** o **Google Sheets (nube)** vía backend intercambiable.

Versión actual: `changelog.VERSION_ACTUAL` (2.9). El bot notifica a los usuarios las novedades de cada versión al arrancar.

---

## 2. Arquitectura General

```
Usuario ──> Telegram ──> python-telegram-bot ──> main.py (handlers registrados)
                                                     │
                                     ┌───────────────┴───────────────┐
                                     ▼                               ▼
                            handlers.py (comandos,          knowledge.py (procesa
                            callbacks, teclados,             y responde; multi-
                            flujos de moneda)                transacción, fechas)
                                     │                               │
                                     └───────────┬───────────────────┘
                                                 ▼
                                    ai_client.py (AIResponder.responder)
                                                 │
                                                 ▼
                                    intent_parser.py (clasificación)
                                     • fast-path regex
                                     • IA Mistral / Ollama (JSON)
                                     • caché de intenciones
                                                 │
                                                 ▼
                                    database.py (proxy DB_BACKEND)
                                   ┌────────────┴────────────┐
                                   ▼                         ▼
                        database_sqlite.py           database_gsheets.py
                          (data/finanzas.db)        (Google Sheets + caché)
```

**Pipeline de mensaje (lenguaje natural):**
```
Mensaje → handlers.handle_message()
         → ai_client.AIResponder().responder()
             → intent_parser.analizar_intencion()
                 → _fast_path()      (regex determinista; si match, retorna)
                 → caché (por mensaje)
                 → _call_ai()        (Mistral → fallback Ollama → vacío)
                     → _validar_resultado()   (normaliza el JSON de la IA)
             → despacho por intención (registrar, consultar, configurar, etc.)
             → knowledge.py procesa con datos reales de la BD y arma la respuesta
```

**Flujos paralelos en handlers.py:**
- **Comandos** (`/start`, `/resumen`, `/gastos`, ...) → función directa.
- **Botones inline** (callbacks) → `handle_callback_query` (edita el mensaje, nunca reenvía uno nuevo).
- **Teclado persistente** (💰 Balance, 📋 Transacciones, 📊 Presupuestos, 💱 Monedas).
- **Multi-transacción** (ej: "$50 en comida y $30 en taxi") → preview con botones para editar/quitar/guardar.
- **Flujo de moneda** (`_manejar_flujo_moneda`) y pendientes (`transaccion_pendiente`).

---

## 3. Stack Tecnológico

| Componente          | Tecnología                        | Versión |
|---------------------|-----------------------------------|---------|
| Lenguaje            | Python                            | 3.10+ (venv local) |
| Bot framework       | python-telegram-bot[webhooks]     | >=22.8  |
| Base de datos local | SQLite (`data/finanzas.db`)       | —       |
| Base de datos nube  | Google Sheets (gspread)           | >=6.2   |
| Cache / sesión      | telegram.ext.ContextTypes         | —       |
| IA proveedor 1      | Mistral AI (API)                  | >=2.5   |
| IA proveedor 2      | Ollama (local)                    | —       |
| Cliente HTTP        | httpx (vía python-telegram-bot)   | —       |
| Env config          | python-dotenv                     | >=1.2.2 |
| Spreadsheets        | pandas, gspread-dataframe         | >=3.0 / >=4.0 |

**Sistema operativo objetivo:** Windows (desarrollo) / Linux (Render.com, producción). Se usa virtualenv (`venv/`) — no hay instalaciones globales.

---

## 4. Estructura de Archivos

```
personal-finance-bot/
├── main.py                  ← Entry point. Registra comandos/handlers, arranca polling o webhook.
├── config.py                ← Lee .env, expone constantes (DB_PATH, tokens, webhook, etc.) y valida.
├── database.py              ← Proxy de BD: redirige a sqlite o gsheets según DB_BACKEND.
├── database_sqlite.py       ← Capa de datos SQLite (7 tablas, CRUD completo + migraciones ALTER).
├── database_gsheets.py      ← Capa de datos Google Sheets (misma interfaz, caché en memoria + flush).
├── intent_parser.py         ← Motor de intenciones: fast-path regex + IA (Mistral/Ollama) + caché.
├── ai_client.py             ← AIResponder: orquesta el pipeline y ejecuta la intención detectada.
├── handlers.py              ← Handlers de Telegram: comandos, callbacks, teclados, flujos de moneda.
├── knowledge.py             ← Procesamiento: gastos, ingresos, balance, presupuestos, metas, fechas, ayuda.
├── notificaciones.py        ← Alertas de presupuesto (80/100/125%), resumen diario, sweep y catch-up.
├── changelog.py             ← VERSION_ACTUAL + historial de versiones (notificaciones al usuario).
├── verify_system.py         ← Verificación de integridad del sistema.
├── check_structure.py       ← Verifica estructura de archivos.
├── create_venv.py           ← Crea entorno virtual desde cero (setup completo).
├── create_venv_simple.py    ← Setup rápido de venv.
├── setup_environment.py     ← Setup completo (venv + deps + verificación).
├── install_bot.py           ← Instalador opcional.
├── INSTALAR.bat             ← Instalador para Windows.
├── test_parsing_bugs.py     ← Suites de tests (unittest, 17 casos de regresión).
├── requirements.txt         ← Dependencias (ver sección 12).
├── prompts/
│   └── system_prompt.txt    ← Prompt del sistema para la IA (referencia).
├── data/
│   ├── finanzas.db          ← Base de datos SQLite (se crea sola).
│   └── images/              ← Imágenes del bot.
├── .github/
│   └── workflows/
│       └── notifications-wake.yml ← Wake diario del bot (Render free tier) para el resumen.
├── credentials.json         ← Credenciales de service account de Google (no subir a GitHub).
├── .env                     ← Token de Telegram + API keys (en .gitignore).
├── .gitignore
├── AGENTS.md                ← Instrucciones para agentes de IA (OpenCode).
├── STACK.md                 ← Este documento.
└── README.md                ← Resumen para usuarios.
```

---

## 5. Base de Datos — Dos Backends

`database.py` es un **proxy**: importa `*` de `database_sqlite` o `database_gsheets` según `DB_BACKEND` en `.env`. Las 14 funciones públicas tienen firmas idénticas en ambos backends; cambiar de backend no requiere tocar código.

### 5.1 Backend SQLite (`database_sqlite.py`)

Archivo: `data/finanzas.db`. `crear_tablas()` crea las 8 tablas y aplica migraciones idempotentes (`ALTER TABLE ... ADD COLUMN` con try/except) para columnas nuevas en BD existentes.

**usuarios**
| Columna           | Tipo      | Descripción                    |
|-------------------|-----------|--------------------------------|
| id                | INTEGER   | PK autoincrement               |
| telegram_user_id  | INTEGER   | UNIQUE, ID de Telegram         |
| nombre            | TEXT      | Nombre del usuario             |
| created_at        | TIMESTAMP | Fecha de creación              |
| updated_at        | TIMESTAMP | Fecha de actualización         |

**categorias**
| Columna      | Tipo     | Descripción                                  |
|--------------|----------|----------------------------------------------|
| id           | INTEGER  | PK                                           |
| usuario_id   | INTEGER  | FK → usuarios.id                             |
| nombre       | TEXT     | Nombre de la categoría                       |
| tipo         | TEXT     | CHECK: gastos, ingresos, ahorros, inversiones|
| descripcion  | TEXT     | Opcional                                     |
| icono_color  | TEXT     | Color hexadecimal (ej: #3498db)              |
| created_at   | TIMESTAMP|                                              |

**transacciones**
| Columna      | Tipo      | Descripción                          |
|--------------|-----------|--------------------------------------|
| id           | INTEGER   | PK                                   |
| usuario_id   | INTEGER   | FK → usuarios.id                     |
| categoria_id | INTEGER   | FK → categorias.id (nullable)        |
| tipo         | TEXT      | CHECK: gasto, ingreso                |
| cantidad     | REAL      | Monto numérico                       |
| descripcion  | TEXT      | Descripción textual                  |
| moneda_id    | INTEGER   | FK → monedas.id (nullable)           |
| fecha        | TIMESTAMP | Default CURRENT_TIMESTAMP            |
| created_at   | TIMESTAMP |                                      |

**presupuestos**
| Columna            | Tipo      | Descripción                     |
|--------------------|-----------|----------------------------------|
| id                 | INTEGER   | PK                               |
| usuario_id         | INTEGER   | FK → usuarios.id                 |
| categoria_id       | INTEGER   | FK → categorias.id (nullable)    |
| nombre             | TEXT      | Nombre propio (puede diferir de la categoría) |
| moneda_id          | INTEGER   | FK → monedas.id                  |
| cantidad_planejada | REAL      | Límite del presupuesto           |
| cantidad_gastada   | REAL      | Gasto acumulado (default 0)      |
| periodo            | TEXT      | CHECK: mensual, anual            |
| fecha_inicio       | DATE      | Inicio del período               |
| fecha_fin          | DATE      | Fin del período (opcional)       |
| created_at         | TIMESTAMP |                                  |

**metas_ahorro**
| Columna         | Tipo      | Descripción                     |
|-----------------|-----------|---------------------------------|
| id              | INTEGER   | PK                               |
| usuario_id      | INTEGER   | FK → usuarios.id                 |
| nombre          | TEXT      | Nombre de la meta                |
| objetivo        | REAL      | Meta total                       |
| cantidad_actual | REAL      | Progreso actual (default 0)      |
| fecha_inicio    | DATE      | Inicio                           |
| fecha_meta      | DATE      | Fecha objetivo                   |
| created_at      | TIMESTAMP |                                  |

**notificaciones**
| Columna     | Tipo      | Descripción                          |
|-------------|-----------|--------------------------------------|
| id          | INTEGER   | PK                                   |
| usuario_id  | INTEGER   | FK → usuarios.id                     |
| version     | TEXT      | Versión ya notificada                |
| enviada_en  | TIMESTAMP | Cuando se notificó                   |

**monedas**
| Columna     | Tipo      | Descripción                          |
|-------------|-----------|--------------------------------------|
| id          | INTEGER   | PK                                   |
| usuario_id  | INTEGER   | FK → usuarios.id                     |
| nombre      | TEXT      | Nombre (Peso cubano, Dólar, ...)     |
| simbolo     | TEXT      | Símbolo (ej: $, ₮, €) default '$'    |
| abreviatura | TEXT      | Código (CUP, USD, USDT, ...)         |
| es_default  | INTEGER   | 0/1, moneda por defecto              |
| created_at  | TIMESTAMP |                                      |

**preferencias_notificaciones** (1 fila por usuario)
| Columna       | Tipo      | Descripción                                    |
|---------------|-----------|------------------------------------------------|
| usuario_id    | INTEGER   | PK = FK → usuarios.id (UNIQUE)                 |
| alerta_80     | INTEGER   | 0/1, alerta al llegar al 80% del presupuesto   |
| alerta_100    | INTEGER   | 0/1, alerta al agotar el presupuesto (100%)    |
| alerta_125    | INTEGER   | 0/1, alerta al exceder el presupuesto (125%)   |
| resumen_diario| INTEGER   | 0/1, resumen diario activado                   |
| hora_resumen  | TEXT      | Hora local del resumen (HH:MM, default 20:00)  |
| zona_horaria  | TEXT      | Zona IANA (default America/Havana)             |
| ultimo_resumen| TEXT      | Fecha ISO (YYYY-MM-DD) del último resumen enviado |

### 5.2 Backend Google Sheets (`database_gsheets.py`)

Cada "tabla" es una hoja del spreadsheet (mismas columnas que el esquema SQLite; `SHEET_COLUMNS`). Características:
- **Caché en memoria** por hoja; escrituras diferidas con `flush` programado (3 s) y `flush_all()` al apagar.
- **IDs** autogenerados por hoja (contadores en memoria).
- **Fechas**: maneja seriales de Excel y cadenas (`DATE_COLUMNS`).
- **Reintentos** contra la API de Google (429/500/502/503 con backoff).
- Soporta credenciales como **archivo** (`GOOGLE_SHEETS_CREDENTIALS`) o **JSON string** (`GOOGLE_SHEETS_CREDENTIALS_JSON`, para Render).

---

## 6. Detección de Intenciones (`intent_parser.py`)

### 6.1 Intenciones Reconocidas (`_INTENCIONES_VALIDAS`)

| Intención                | Ejemplos de entrada                                            |
|--------------------------|---------------------------------------------------------------|
| `registrar`              | "gasté 50 en comida", "recibí 2000 de salario", "compré $30 de ropa" |
| `consultar`              | "cuánto tengo", "ver mis gastos", "ver presupuestos"          |
| `configurar_presupuesto` | "mi presupuesto para comida es $500", "añade 500 al presupuesto de barbería" |
| `configurar_ahorro`      | "quiero ahorrar 2000 para vacaciones"                          |
| `modificar`              | "cambia el monto del último gasto a 200", "cambia el tipo de X a ingreso" |
| `eliminar`               | "elimina el presupuesto de comida", "borra el último gasto"    |
| `analizar_por_fecha`     | "qué gasté hoy", "ver transacciones de esta semana"            |
| `ayuda_uso`              | "cómo registro un gasto", "para qué sirve", "ayuda"            |
| `general`                | Saludos y mensajes no reconocidos                               |

### 6.2 Subconsultas (`consultar` → `subconsulta`)

| Subconsulta                 | Qué responde                                          |
|-----------------------------|-------------------------------------------------------|
| `balance`                   | Saldo/balance agrupado por moneda                      |
| `transacciones` / `gastos` / `ingresos` | Lista de movimientos (filtrados por tipo)  |
| `presupuesto`               | Lista de presupuestos con progreso                     |
| `categorias`                | Categorías agrupadas por tipo                          |
| `presupuesto_especifico`    | Restante/disponible de UN presupuesto ("¿cuánto me queda de barbería?") |
| `mayor_gasto`               | Mayor gasto + top 3 de un período                      |
| `gastos_por_presupuestos`   | Cuánto gastó en un período desglosado por presupuesto + total |
| `gastos_por_fecha`          | Total gastado/recibido de un período, por moneda       |

### 6.3 Mecanismo (orden)

1. **Fast-path regex** (`_FAST_PATTERNS`): registro, ahorro, presupuesto (antes que el formato corto), consultas con fecha (antes que balance), ayuda, modificar, eliminar, saludo, categorías, presupuestos. Confianza 0.95-0.99.
2. **Caché** por mensaje (`_INTENT_CACHE`) — evita re-llamadas a IA.
3. **IA** (`_call_ai`): Mistral primero, Ollama como fallback. Envía `_SYSTEM_PROMPT` + prompt de usuario **con contexto real** (nombres de presupuestos y monedas del usuario) para que elija etiquetas exactas.
4. **Validación** (`_validar_resultado`): normaliza el JSON contra `_RESULTADO_VACIO`, filtros de intenciones/tipos/subconsultas válidas y re-parser de cantidades.

La IA **solo clasifica**; los números y respuestas los calcula el bot con datos reales de la BD (determinista).

---

## 7. Pipeline de IA (`ai_client.py`)

### 7.1 AIResponder.responder(mensaje, usuario) → (texto, pendiente)

| Método                     | Intención que ejecuta                              |
|----------------------------|----------------------------------------------------|
| `_procesar_ayuda`          | `ayuda_uso` (respuesta contextual o `_responder_ayuda_uso`) |
| `_procesar_registro`       | `registrar` (gasto/ingreso; detecta moneda, reutiliza la del presupuesto si aplica) |
| `_procesar_consulta`       | `consultar` (dispatch por `subconsulta`)           |
| `_procesar_analisis_fecha` | `analizar_por_fecha`                               |
| `_procesar_presupuesto`    | `configurar_presupuesto` (modo reemplazar/sumar, moneda, pendiente) |
| `_procesar_ahorro`         | `configurar_ahorro`                                |
| `_procesar_modificacion`   | `modificar`                                        |
| `_procesar_eliminacion`    | `eliminar` (transacción o presupuesto)             |
| `_procesar_general`        | `general` / fallback                               |
| `_generar_respuesta_error` | Fallback ante errores                              |

**Pendiente** (`transaccion_pendiente`): cuando falta información (elegir tipo gasto/ingreso, elegir moneda, moneda del presupuesto), el bot responde y guarda un `pendiente` que `handlers` convierte en **botones inline** para completar la acción.

### 7.2 Proveedores de IA

| Proveedor | Config (.env)                  | Modelo por defecto      |
|-----------|--------------------------------|------------------------|
| Mistral   | `AI_PROVIDER=mistral` + `MISTRAL_API_KEY` | `mistral-small-latest` |
| Ollama    | `AI_PROVIDER=ollama` + `OLLAMA_BASE_URL`  | `llama3.2`             |

### 7.3 Funciones de Procesamiento (`knowledge.py`)

| Función                          | Qué hace                                                |
|----------------------------------|--------------------------------------------------------|
| `_procesar_gasto(mensaje, usuario, moneda)` | Registra gasto; crea categoría; liga a presupuesto si se menciona (descuenta y muestra restante) |
| `_procesar_ingreso(mensaje, usuario, moneda)` | Registra ingreso; crea categoría si no existe |
| `_procesar_balance(usuario)`     | Balance agrupado por moneda (ingresos/gastos/neto)     |
| `_procesar_transacciones(usuario, limite, tipo)` | Lista movimientos, opcionalmente filtrados |
| `_procesar_gastos` / `_procesar_ingresos` | Wrappers de transacciones por tipo             |
| `_procesar_presupuestos(usuario)`| Presupuestos con nombre, moneda, barra de progreso     |
| `_procesar_presupuesto_especifico(usuario, etiqueta)` | Restante de un presupuesto (fuzzy match) |
| `_procesar_mayor_gasto(usuario, mensaje)` | Mayor gasto + top 3 + total por moneda de un período |
| `_procesar_gastos_por_presupuestos(usuario, mensaje)` | Gastos de un período desglosados por presupuesto + total |
| `_procesar_gastos_por_fecha(usuario, mensaje)` | Totales por moneda de un período            |
| `_procesar_categorias(usuario)`  | Categorías agrupadas por tipo                        |
| `_procesar_metas_ahorro(usuario)`| Metas de ahorro con progreso                          |
| `_procesar_resumen_mensual(usuario)` | Resumen del mes actual                            |
| `_analizar_transacciones_por_fecha(usuario, mensaje)` | Análisis por fecha: resumen por moneda, categorías, mayor gasto, detalle |
| `_parsear_fecha_natural(mensaje)`| Parsea hoy/ayer/esta semana/este mes/días/meses/últimos N días → (inicio, fin, etiqueta) |
| `_procesar_modificar_transaccion` / `_procesar_eliminar_presupuesto` / `_procesar_eliminar_transaccion` | Edición/borrado por lenguaje natural |
| `_parsear_multi_transaccion` / `_guardar_multi_transacciones` | Multi-transacciones con preview |
| `_detectar_moneda_en_texto`, `_detectar_presupuesto_en_gasto`, `_buscar_presupuesto`, `_formatear_monto`, `_moneda_lookup_usuario`, `_crear_barra_progreso` | Helpers |

### 7.4 Sistema de Notificaciones (`notificaciones.py`)

| Función | Qué hace |
|---------|----------|
| `verificar_alertas_presupuesto(prefs, planeado, antes, despues, nombre, simbolo, abreviatura)` | Devuelve texto de alerta si el gasto **cruza** el umbral 80/100/125% (nunca repite en gastos posteriores) o `None` |
| `formatear_resumen_diario(usuario)` | Resumen del día: movimientos de hoy + balance por moneda |
| `_hora_programada_hoy(hora, zona)` | datetime de hoy a la hora local del usuario (zona IANA) |
| `_resumen_due(usuario, prefs)` | ¿Corresponde enviar ahora? (resumen activo + ya pasó la hora de hoy + `ultimo_resumen` ≠ hoy) |
| `_enviar_resumen(context, usuario, motivo)` | Envía el resumen y marca `ultimo_resumen` (idempotente) |
| `enviar_resumen_pendiente(update, context)` | **Catch-up**: llamado desde `handle_message`; envía el resumen atrasado apenas el usuario escribe |
| `tarea_resumen_diario(context)` | **Sweep**: job `run_repeating(60 s)` en `main.py`; recorre usuarios con resumen activo y envía los que tocan |

**Flujo de alertas:** `knowledge._procesar_gasto` captura `gastado_antes` antes de `agregar_transaccion`, llama `verificar_alertas_presupuesto` (import lazy para evitar ciclos) y anexa el aviso al texto de confirmación. Las alertas se activan/desactivan desde `/notificaciones`.

**Persistencia:** cada usuario tiene 1 fila en `preferencias_notificaciones` (ambos backends, mismas firmas). Si no existe, `obtener_preferencias` devuelve los valores por defecto (alertas activas, resumen off). Por ahora la **hora (21:30) y la zona (America/Havana) del resumen son fijas** desde config; el menú `/notificaciones` solo permite activar/desactivar el resumen y cada alerta. Los campos `hora_resumen`/`zona_horaria` se conservan en BD para habilitar la personalización en el futuro.

---

## 8. Comandos de Telegram

Menú registrado con `set_my_commands` (sugerencias al escribir `/`).

| Comando      | Handler                  | Función                                   |
|--------------|--------------------------|-------------------------------------------|
| `/start`     | `start()`                | Inicia sesión, muestra estadísticas       |
| `/resumen`   | `consultar_resumen()`    | Resumen del mes actual                     |
| `/categorias`| `consultar_categorias()` | Ver categorías financieras                 |
| `/gastos`    | `consultar_gastos()`     | Ver últimos gastos                         |
| `/ingresos`  | `consultar_ingresos()`   | Ver últimos ingresos                       |
| `/metas`     | `consultar_metas()`      | Ver metas de ahorro                        |
| `/notificaciones` | `configurar_notificaciones()` | Alertas de presupuesto y resumen diario (21:30 hora de Cuba) |
| `/help`      | `consultar_comandos()`   | Lista de comandos y ejemplos               |
| `/user`      | `consultar_usuario()`    | Info del usuario                           |
| `/delete`    | `eliminar_historial()`   | Borrar todo el historial                   |
| `/anuncio`   | `anuncio()`              | Solo admin (`ADMIN_USER_ID`)               |

Cualquier texto que no sea comando se procesa como lenguaje natural vía `handle_message`.

**Teclado persistente:** 💰 Balance, 📋 Transacciones, 📊 Presupuestos, 💱 Monedas (`TECLADO_BUTTONS`).

**Botones inline (callbacks):** elección de moneda (`elegir_moneda`, `elegir_moneda_presupuesto`), confirmación de tipo gasto/ingreso, presets de moneda, multi-transacción, cancelar pendientes. Todos **editan** el mensaje original (`_responder_editando`).

---

## 9. Configuración y Variables de Entorno

Archivo `.env` (ejemplo en `AGENTS.md`):

```env
TELEGRAM_BOT_TOKEN=token_de_botfather
ADMIN_USER_ID=123456789

# Backend de base de datos
DB_BACKEND=sqlite                    # "sqlite" | "gsheets"
GOOGLE_SHEETS_CREDENTIALS=data/finanzas-sa.json   # (gsheets, archivo)
GOOGLE_SHEETS_CREDENTIALS_JSON=...   # (gsheets, JSON string para Render)
GOOGLE_SHEETS_SPREADSHEET_ID=...     # (gsheets, obligatorio)

AI_PROVIDER=mistral                  # "mistral" | "ollama"
MISTRAL_API_KEY=tu_api_key
MISTRAL_MODEL=mistral-small-latest
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Webhook (producción en Render.com; si está vacío usa polling)
WEBHOOK_URL=
WEBHOOK_SECRET=
ALLOWED_HOSTS=your-app.onrender.com
PORT=8000

# Notificaciones (resumen diario)
NOTIF_WAKE_UTC=01:30              # 1er wake (UTC): 21:30 hora de Cuba en verano
DEFAULT_TIMEZONE=America/Havana   # Zona del resumen diario (fija por ahora)
HORA_RESUMEN_DEFAULT=21:30        # Hora del resumen diario (fija para todos)
```

### Wake del bot (Render free tier)
Render duerme el servicio tras ~15 min sin tráfico. El resumen diario se envía a las **21:30 hora de Cuba** (fijo para todos):
1. Crear un **Secret** de GitHub Actions: `BOT_WEBHOOK_URL` = `https://TU-APP.onrender.com/webhook`.
2. El workflow `.github/workflows/notifications-wake.yml` hace `curl` a esa URL en **dos momentos** para cubrir ambas estaciones de Cuba:
   - **01:30 UTC** = 21:30 Cuba (horario de verano, UTC-4)
   - **02:30 UTC** = 21:30 Cuba (horario de invierno, UTC-5)
   El GET devuelve 405 (el webhook solo acepta POST) pero **despierta** a Render igualmente.
3. Dentro de la ventana (sweep cada 60 s), el job interno envía los resúmenes pendientes.
4. Si aun así el bot estaba dormido a la hora del resumen, el **catch-up** lo envía apenas el usuario vuelva a escribir.

### Validación (`config.validate_config()`)
- `TELEGRAM_BOT_TOKEN` — obligatorio.
- `DB_BACKEND` — debe ser `sqlite` o `gsheets`; si es `gsheets` exige credenciales (archivo o JSON) y `GOOGLE_SHEETS_SPREADSHEET_ID`.
- `AI_PROVIDER` — `mistral` exige `MISTRAL_API_KEY`; `ollama` exige `OLLAMA_BASE_URL`.

---

## 10. Versionado y Notificaciones (`changelog.py`)

- `VERSION_ACTUAL` define la versión vigente (2.8).
- `CHANGELOG` es un dict `{versión: {titulo, mejoras, emoji}}`.
- En cada mensaje, `handlers.handle_message` compara la última versión vista (`notificaciones` → `obtener_ultima_version_vista`) y, si hay novedades, envía el resumen de las versiones pendientes y marca como notificadas (`registrar_notificacion`).

---

## 11. Dependencias

`requirements.txt`:

```
python-telegram-bot[webhooks,job-queue]>=22.8
python-dotenv>=1.2.2
mistralai>=2.5.0
gspread>=6.2.0
pandas>=3.0.0
gspread-dataframe>=4.0.0
```

`[job-queue]` instala **APScheduler** (requerido para el sweep del resumen diario).

Instalación: `python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt`

Scripts de setup: `python create_venv.py` (completo) o `python setup_environment.py` (rápido). Verificación: `python verify_system.py` y `python check_structure.py`.

---

## 12. Flujo de Inicio (`main.py`)

```
main()
  ├─ Si WEBHOOK_URL → app.run_webhook(listen=0.0.0.0, port=PORT, url_path, secret_token)
  └─ Si no → asyncio.run(run_bot())  [modo polling local]
        → config.validate_config()
        → crear directorios data/ e images/
        → database.crear_tablas()
        → ApplicationBuilder().token().post_init(_post_init).build()
        → _post_init: set_my_commands(COMANDOS_MENU) + set_chat_menu_button
        → registrar handlers:
            CommandHandler: start, user, help, delete, anuncio, categorias, gastos, ingresos, metas, resumen, notificaciones
            CallbackQueryHandler(handle_callback_query)
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            add_error_handler(error_handler)
        → job_queue.run_repeating(notificaciones.tarea_resumen_diario, 60 s)  (si app.job_queue)
        → delete_webhook(drop_pending_updates=True)  (evita conflictos)
        → app.start() + updater.start_polling()
        → shutdown: flush_all() de gsheets si aplica
```

---

## 13. Recursos y Limitaciones

### Consumo
- **RAM**: ~50-100 MB (bot + BD + cliente HTTP)
- **CPU**: Mínimo (regex instantáneo; IA depende del proveedor externo)
- **Disco**: `data/finanzas.db` crece con uso (~1 KB por transacción)
- **Red**: Telegram API + (opcional) Mistral/Ollama + (opcional) Google Sheets

### Limitaciones conocidas
- **Multi-moneda sin conversión**: los totales se agrupan por moneda, no se convierten (CUP y USD se muestran por separado).
- **Gasto en moneda distinta al presupuesto**: se registra con la moneda indicada, pero el presupuesto descuenta el monto sin conversión.
- **Sin paginación real**: listas con límite fijo (`_procesar_transacciones` muestra 10; `obtener_transacciones` en la BD devuelve hasta 50).
- **Caché de IA por mensaje** (no por usuario): la clasificación de intención es idempotente por texto.
- **Sin autenticación**: cualquier usuario de Telegram que hable con el bot puede usarlo (datos aislados por `telegram_user_id`).
- **Español neutro** (sin voseo): el fast-path y la IA cubren variantes de dialecto (argentino, mexicano, venezolano, etc.); el inglés tiene cobertura básica (saludos y comandos).
- **Sin exportación CSV/JSON** de datos.
- **Google Sheets**: dependencia de cuotas de API (reintentos incluidos); el backend gsheets pierde la cache si no hay `flush_all` limpio.

### Puertos
- **Telegram API**: 443 (outbound)
- **Mistral API**: 443 (outbound, si está configurado)
- **Ollama**: 11434 (local, si está configurado)
- **Webhook (Render)**: `PORT` (8000 por defecto, inbound)
- **Polling**: ningún puerto abierto

---

## 14. Modo Offline vs Online

| Modo     | BD             | Proveedor IA  | Requiere Internet                 |
|----------|----------------|---------------|-----------------------------------|
| Local    | SQLite         | Mistral/Ollama| Telegram + (IA / Ollama)          |
| Nube     | Google Sheets  | Mistral       | Telegram + Mistral + Google APIs  |

En modo sin IA disponible, el bot cae a `general`/fallback y sigue respondiendo comandos básicos y fast-path.

---

## 15. Debugging y Logs

- Logging a stderr con formato `timestamp - name - level - message`, nivel `INFO` por defecto (`main.py:32`).
- Logs en consola (sin persistencia a archivo).
- Errores de IA/BD se capturan con try/except y respuesta amigable al usuario (`_generar_respuesta_error`).
- `verify_system.py` corre batería de verificación; `test_parsing_bugs.py` ejecuta 17 tests de regresión (módulos sin acentos en stdout en Windows cp1252).
- Para depurar clasificación: `intent_parser.limpiar_cache()` y logs `debug` de `analizar_intencion`.

---

## 16. Tests y Verificación

- `venv\Scripts\python.exe -m unittest test_parsing_bugs -v` — 17 tests (parsing de cantidades, monedas, balance por moneda, carga gsheets, decimales).
- `python verify_system.py` — chequeo de dependencias y configuración.
- `python check_structure.py` — valida estructura de archivos.
- Suites temporales de regresión (presupuestos, callbacks, gasto ligado, consultas, **notificaciones**) se mantienen fuera del repo en `%TEMP%\opencode\`.
