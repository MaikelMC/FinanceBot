# Personal Finance Bot — Stack completo

## 1. Resumen

Bot de Telegram para finanzas personales con procesamiento de lenguaje natural en español/inglés. Permite registrar gastos, ingresos, presupuestos y metas de ahorro mediante mensajes de texto conversacionales. Usa un pipeline híbrido: regex nativo rápido + IA (Mistral/Ollama) para comprensión avanzada.

---

## 2. Arquitectura General

```
Usuario ──> Telegram ──> python-telegram-bot ──> handlers.py (intent detection)
                                                    │
                                          ┌─────────┴──────────┐
                                          ▼                    ▼
                                    Regex nativo          AI Client
                                    (handlers.py)     (ai_client.py)
                                          │                    │
                                          ▼                    ▼
                                     knowledge.py ────> Mistral / Ollama
                                          │
                                          ▼
                                     database.py ───> SQLite
```

**Pipeline de mensaje:**
```
Mensaje → handle_message()
         → AIResponder.responder()
             → _procesar_con_regex_nativo()  (intento rápido)
                 → _detectar_intencion()     (clasifica intento)
                 → función específica        (procesa y responde)
             → fallback: _consultar_mistral() (IA avanzada)
                 → parsea respuesta estructurada
                 → redirige a función nativa
```

---

## 3. Stack Tecnológico

| Componente        | Tecnología                     | Versión |
|------------------|--------------------------------|---------|
| Lenguaje         | Python                         | 3.14    |
| Bot framework    | python-telegram-bot            | 22.8    |
| Base de datos    | SQLite (local)                 | —       |
| Cache / sesión   | telegram.ext.ContextTypes      | —       |
| IA proveedor 1   | Mistral AI (API)               | 2.5.1   |
| IA proveedor 2   | Ollama (local)                 | —       |
| Cliente HTTP     | httpx                          | 0.28    |
| Env config       | python-dotenv                  | 1.2     |
| Tipos            | pydantic (vía mistralai)       | 2.13    |

**Sistema operativo objetivo:** Windows / Linux (compatible con ambos).

---

## 4. Estructura de Archivos

```
personal-finance-bot/
├── main.py                  ← Entry point. Arranca polling y registra handlers.
├── config.py                ← Lee .env, expone constantes (DB_PATH, tokens, etc.)
├── database.py              ← Capa de datos SQLite (5 tablas, CRUD completo).
├── handlers.py              ← Intents: detección con keywords + parsing regex.
├── knowledge.py             ← Funciones de procesamiento: balance, gastos, presupuestos.
├── ai_client.py             ← Cliente Mistral/Ollama con fallback.
├── verify_system.py         ← Script de verificación de integridad.
├── check_structure.py       ← Verifica estructura de archivos.
├── create_venv.py           ← Crea entorno virtual desde cero.
├── setup_environment.py     ← Setup completo (venv + deps + verificación).
├── prompts/
│   └── system_prompt.txt    ← Prompt del sistema para la IA.
├── data/
│   └── finanzas.db          ← Base de datos SQLite (se crea sola).
├── .env                     ← Token de Telegram + API keys.
├── AGENTS.md                ← Instrucciones para OpenCode.
├── STACK.md                 ← Este documento.
└── requirements.txt / pyproject.toml  ← (no existe, deps se instalan directo)
```

---

## 5. Base de Datos — SQLite

Archivo: `data/finanzas.db` (creación automática en `database.crear_tablas()`).

### 5.1 Tabla `usuarios`
| Columna           | Tipo     | Descripción                  |
|------------------|----------|------------------------------|
| id               | INTEGER  | PK autoincrement             |
| telegram_user_id | INTEGER  | UNIQUE, ID de Telegram       |
| nombre           | TEXT     | Nombre del usuario           |
| created_at       | TIMESTAMP| Fecha de creación            |
| updated_at       | TIMESTAMP| Fecha de actualización       |

### 5.2 Tabla `categorias`
| Columna     | Tipo     | Descripción                          |
|------------|----------|--------------------------------------|
| id         | INTEGER  | PK                                   |
| usuario_id | INTEGER  | FK → usuarios.id                     |
| nombre     | TEXT     | Nombre de la categoría               |
| tipo       | TEXT     | CHECK: gastos, ingresos, ahorros, inversiones |
| descripcion| TEXT     | Opcional                             |
| icono_color| TEXT     | Color hexadecimal (ej: #3498db)       |

### 5.3 Tabla `transacciones`
| Columna      | Tipo     | Descripción                     |
|-------------|----------|----------------------------------|
| id          | INTEGER  | PK                               |
| usuario_id  | INTEGER  | FK → usuarios.id                 |
| categoria_id| INTEGER  | FK → categorias.id (nullable)    |
| tipo        | TEXT     | CHECK: gasto, ingreso            |
| cantidad    | REAL     | Monto numérico                   |
| descripcion | TEXT     | Descripción textual              |
| fecha       | TIMESTAMP| Fecha (default CURRENT_TIMESTAMP)|

### 5.4 Tabla `presupuestos`
| Columna           | Tipo     | Descripción                     |
|------------------|----------|----------------------------------|
| id               | INTEGER  | PK                               |
| usuario_id       | INTEGER  | FK → usuarios.id                 |
| categoria_id     | INTEGER  | FK → categorias.id               |
| cantidad_planejada| REAL    | Límite del presupuesto           |
| cantidad_gastada | REAL     | Gasto acumulado (default 0)      |
| periodo          | TEXT     | CHECK: mensual, anual            |
| fecha_inicio     | DATE     | Inicio del período               |
| fecha_fin        | DATE     | Fin del período (opcional)       |

### 5.5 Tabla `metas_ahorro`
| Columna        | Tipo     | Descripción                     |
|---------------|----------|----------------------------------|
| id            | INTEGER  | PK                               |
| usuario_id    | INTEGER  | FK → usuarios.id                 |
| nombre        | TEXT     | Nombre de la meta                |
| objetivo      | REAL     | Meta total                       |
| cantidad_actual| REAL    | Progreso actual (default 0)      |
| fecha_inicio  | DATE     | Inicio                           |
| fecha_meta    | DATE     | Fecha objetivo                   |

---

## 6. Detección de Intenciones (handlers.py)

### 6.1 Intenciones Reconocidas

| Intención                    | Ejemplos de entrada                                     |
|------------------------------|--------------------------------------------------------|
| `registrar_transaccion`      | "gasté 50 en comida", "recibí 2000 de salario"        |
| `consultar_gastos`           | "ver mis gastos", "historial de gastos"               |
| `consultar_ingresos`         | "mostrarme los ingresos", "ingresos del mes"          |
| `consultar_transacciones`    | "dame el historial", "muestrame las transacciones"    |
| `consultar_balance`          | "cual es mi balance", "saldo actual"                  |
| `consultar_presupuesto`      | "como va mi presupuesto", "ver presupuestos"          |
| `consultar_categorias`       | "ver mis categorias"                                   |
| `configurar_presupuesto`     | "fijar presupuesto de 500 para comida"                |
| `configurar_ahorro`          | "quiero ahorrar 2000 para vacaciones"                 |
| `start`                      | "hola", "/start"                                       |
| `general`                    | Mensajes no reconocidos                                |

### 6.2 Mecanismo
1. **Keywords de consulta** (`ver`, `mostrar`, `dame`, `historial`, etc.)
2. **Keywords de registro** (`gasté`, `compré`, `recibí`, etc.)
3. **Keywords de presupuesto/ahorro** (`fijar`, `establecer`, `presupuesto`, `ahorrar`)
4. Fallback a `general`

### 6.3 Parsing de Transacciones
- Extracción de `cantidad` mediante regex (`\d+(?:\.\d+)?`)
- Detección de tipo (gasto/ingreso) por palabras clave
- Categorización automática por palabras como "comida", "salario", etc.
- Las palabras de relleno se filtran (artículos, preposiciones, etc.)

---

## 7. Pipeline de IA (ai_client.py + knowledge.py)

### 7.1 Orden de Procesamiento
```
1. Regex nativo en handlers._detectar_intencion()
2. Si intención clara → procesar con función de knowledge.py
3. Si no clara → consultar Mistral / Ollama
4. Mistral responde con estructura: INTENTION, CANTIDAD, CATEGORIA, etc.
5. Se parsea la respuesta y se redirige a la función nativa correspondiente
```

### 7.2 Proveedores de IA

| Proveedor | Config (.env)              | Modelo por defecto      |
|----------|---------------------------|------------------------|
| Mistral  | `AI_PROVIDER=mistral` + `MISTRAL_API_KEY` | `mistral-small-latest` |
| Ollama   | `AI_PROVIDER=ollama` + `OLLAMA_BASE_URL`  | `llama3.2`             |

### 7.3 Funciones de Procesamiento (knowledge.py)

| Función                          | Qué hace                                                |
|----------------------------------|--------------------------------------------------------|
| `_procesar_transacciones(usuario, tipo)` | Lista transacciones, opcionalmente filtradas        |
| `_procesar_gastos(usuario)`      | Solo gastos (wrapper de transacciones con tipo=gasto) |
| `_procesar_ingresos(usuario)`    | Solo ingresos (wrapper de transacciones con tipo=ingreso) |
| `_procesar_balance(usuario)`     | Totales: ingresos, gastos, neto                       |
| `_procesar_presupuestos(usuario)`| Presupuestos activos con barra de progreso            |
| `_procesar_categorias(usuario)`  | Lista categorías agrupadas por tipo                   |
| `_procesar_gasto(mensaje, usuario)` | Registra un gasto y crea categoría si no existe   |
| `_procesar_ingreso(mensaje, usuario)` | Registra un ingreso y crea categoría si no existe |

---

## 8. Comandos de Telegram

| Comando   | Handler                  | Función                        |
|----------|--------------------------|--------------------------------|
| `/start` | `start()`                | Inicia sesión, muestra stats   |
| `/user`  | `consultar_usuario()`    | Muestra info del usuario       |
| `/help`  | `consultar_comandos()`   | Lista de comandos disponibles   |

Cualquier mensaje de texto que no sea comando se procesa como lenguaje natural.

---

## 9. Configuración y Variables de Entorno

Archivo `.env`:

```env
TELEGRAM_BOT_TOKEN=token_de_botfather
AI_PROVIDER=mistral              # "mistral" | "ollama"
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
MISTRAL_API_KEY=tu_api_key
MISTRAL_MODEL=mistral-small-latest
```

### Validación (config.py)
- `TELEGRAM_BOT_TOKEN` — obligatorio
- `AI_PROVIDER` — debe ser "mistral" o "ollama"
- `MISTRAL_API_KEY` — obligatorio si AI_PROVIDER=mistral
- `OLLAMA_BASE_URL` — obligatorio si AI_PROVIDER=ollama

---

## 10. Dependencias

Instalación directa con pip (no hay `requirements.txt`):

```
python-telegram-bot>=22.8
python-dotenv
mistralai
```

---

## 11. Flujo de Inicio (main.py)

```
main()
  → asyncio.run(run_bot())
      → config.validate_config()
      → crear directorios data/ e images/
      → database.crear_tablas()
      → ApplicationBuilder().token().build()
      → registrar handlers:
          CommandHandler("start", start)
          CommandHandler("user", consultar_usuario)
          CommandHandler("help", consultar_comandos)
          MessageHandler(TEXT, handle_message)  ← NLP
          error_handler
      → app.run_polling()
```

---

## 12. Recursos y Limitaciones

### Consumo
- **RAM**: ~50-100 MB (bot + SQLite + cliente HTTP)
- **CPU**: Mínimo (regex es instantáneo; IA depende del proveedor externo)
- **Disco**: `data/finanzas.db` crece con uso (~1 KB por transacción)
- **Red**: Necesita conexión a Telegram API + opcional a Mistral/Ollama API

### Limitaciones conocidas
- **Sin tests automatizados** — no hay framework de testing configurado
- **Sin migraciones de DB** — cambiar schema requiere borrar la DB
- **Sin paginación** — límite fijo de 50 transacciones por consulta
- **Sin caché** — cada consulta a IA hace request HTTP
- **Sin autenticación** — cualquier usuario de Telegram con el token puede usar el bot
- **Español/Inglés** — el parsing de intents está orientado a español con mezcla de inglés
- **Sin exportación** — no se puede exportar datos a CSV/JSON

### Puertos
- **Telegram API**: 443 (outbound)
- **Mistral API**: 443 (outbound, si está configurado)
- **Ollama**: 11434 (local, si está configurado)
- **Bot**: ningún puerto abierto (usa polling, no webhook)

---

## 13. Modo Offline vs Online

| Modo    | Proveedor IA | Requiere Internet |
|---------|-------------|-------------------|
| Offline | Ollama local | Solo Telegram API |
| Online  | Mistral API  | Telegram + Mistral |

En modo offline sin Ollama, el bot cae a respuestas de fallback genéricas pero sigue funcionando para comandos básicos.

---

## 14. Debugging y Logs

- Logging a stderr con formato timestamp + nivel + mensaje
- Nivel: `INFO` por defecto (configurable en `main.py:27-30`)
- Archivos de log: no hay persistencia (solo consola)
- Errores de AI se capturan con mensaje amigable al usuario
- `verify_system.py` corre una batería de tests de integración
