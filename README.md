# Bot de Finanzas Personales

Este es un **bot completo de finanzas personales** que el usuario solicitó. Ha sido reconstruido desde cero utilizando el enfoque descrito en el Plan A.

## Características Principales

### ✅ Características Financieras Esenciales
- **Registro de transacciones en lenguaje natural**: Registra gastos, ingresos, ahorros e inversiones con frases como "Gasté $50 en comida para el desayuno"
- **Categorías por tipo**: Gastos, ingresos, ahorros e inversiones con descripciones opcionales
- **Separación por usuario**: Cada usuario tiene su propia base de datos aislada
- **Gestión de presupuestos mensuales**: Crea presupuestos por categoría para controlar gastos
- **Metas de ahorro**: Establece objetivos de ahorro específicos con seguimiento de progreso

### ✅ Handlers Financieros
- **Registrar transacciones**: Detecta automáticamente gastos/ingresos del lenguaje natural
- **Consultar balance**: Muestra ingresos, gastos y balance neto
- **Ver transacciones recientes**: Lista los últimos gastos e ingresos
- **Gestionar categorías**: Crea y ve categorías personalizadas
- **Configurar presupuestos**: Establece límites mensuales por categoría
- **Configurar metas de ahorro**: Crea objetivos de ahorro específicos

### ✅ Componentes de IA
- **Procesamiento de lenguaje natural**: Parseo regex mejorado para comandos financieros
- **Detección de intenciones**: Identifica transacciones de gastos, ingresos y consultas
- **Respuestas inteligentes**: Genera confirmaciones y sugerencias relevantes
- **Helpers de traducción**: Convierte texto financiero a formato estructurado

### ✅ Base de Datos Relacional
- **Tablas separadas**: Usuarios, categorías, transacciones, presupuestos, metas de ahorro
- **Relaciones**: Claves foráneas e integridad referencial
- **APIs CRUD**: Completas operaciones de creación, lectura, actualización y eliminación

### ✅ Arquitectura Modular
- **Separate by concerns**: Cada archivo tiene una responsabilidad única
- **Patrones de diseño**: Conexión a DB, manejo de errores, manejo de mensajes
- **Preparado para escalabilidad**: Listo para agregar más funcionalidades

## Tecnologías Utilizadas

- **Python 3.10+** con type hints
- **SQLite** para almacenamiento de datos local (sin dependencias externas)
- **Python-Telegram-Bot** API para el bot
- **dotenv** para gestión de configuración

## Configuración

1. **Instala las dependencias:**
   ```bash
   pip install python-telegram-bot python-dotenv
   ```

2. **Configura las variables de entorno:**
   ```bash
   TELEGRAM_BOT_TOKEN=tu_token_aqui
   AI_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama3.2
   ```

## Estructura del Proyecto

```
personal-finance-bot/
├── main.py                    # Punto de entrada del bot
├── config.py                  # Configuración centralizada
├── database.py                # Esquema SQLite y APIs CRUD
├── handlers.py                # Detección de intenciones y routing
├── knowledge.py               # Lógica de IA y procesamiento de mensajes
├── prompts/                  # Prompts del sistema (comentados)
├── .env                      # Variables de entorno
├── data/                      # Directorio de base de datos e imágenes
└── README.md                  # Esta documentación
```

## Ejemplos de Uso

### Empezar con el Bot
- `/start` - Iniciar/Reiniciar el bot y ver estadísticas
- `/user` - Ver tu información de usuario
- `/help` - Ver comandos disponibles

### Registrar Transacciones (Lenguaje Natural)
```
"Gasté $50 en comida para el desayuno"          # Registra gasto en categoría "comida"
"Recibí $1000 de salario"                       # Registra ingreso como "salario"
"Mi presupuesto para comida es $500 este mes"   # Configura presupuesto mensual
"Quiero ahorrar $2000 para unas vacaciones"    # Configura meta de ahorro
"¿Cuál es mi balance actual?"                   # Consulta balance financiero
"Ver mis transacciones recientes"               # Ve últimos registros
```

### Flujo de Trabajo Común
1. **User starts bot**: `/start` → Bot da la bienvenida y muestra estadísticas
2. **User registra gasto**: "Gasté $50 en comida para el desayuno" → Se guarda transacción
3. **User consulta**: "¿Cuál es mi balance?" → Bot muestra ingresos/gastos/neto
4. **User configura presupuesto**: "Mi presupuesto para comida es $500 este mes" → Se crea presupuesto
5. **User hace seguimiento**: Bot automáticamente registra progreso de presupuesto

## Próximos Pasos Potenciales

- **IA Avanzada**: Integrar con Ollama/Mistral para mejor parseo de lenguaje natural
- **Gráficos**: Agregar visualización del progreso de presupuestos y metas
- **Exportación**: Permitir exportación CSV de transacciones
- **Alertas**: Alertas de presupuesto excedido o logros de metas
- **Web Dashboard**: Interfaz web para mejor visibilidad de datos

## Ejemplos de Comandos Financieros

### Gestor de Gastos
- `Gasté $30 en Supermercado` → Gasto registrado en supermercado
- `Pagó $15 de servicio` → Gasto registrado en servicio
- `Compré $50 de ropa` → Gasto registrado en ropa

### Gestor de Ingresos
- `Recibí $1500 de salario` → Ingreso registrado como salario
- `Vendí artesanía por $100` → Ingreso registrado como ventas
- `Usé transferencia bancaria $500` → Ingreso registrado como transferencia

### Control de Presupuesto
- `Mi presupuesto para comida es $400 este mes` → Presupuesto mensual establecido
- `Presupuesto para transporte: $100` → Presupuesto de transporte establecido
- `¿Cómo va mi presupuesto de transporte?` → Progreso del presupuesto mostrado

### Seguimiento de Ahorro
- `Meta: ahorrar $2000 para vacaciones` → Meta de ahorro creada
- `Ahorré $500 este mes` → Contribución a meta registrada
- `Progreso de mi meta de vacaciones` → Se muestra estado de progreso

## Base de Datos

El bot utiliza SQLite con el siguiente esquema de tablas:

1. **usuarios**: Información del usuario (ID de Telegram, nombre)
2. **categorias**: Categorías personalizadas por tipo (gastos, ingresos, ahorros, inversiones)
3. **transacciones**: Lista de todas las transacciones financieras
4. **presupuestos**: Limites de gastos mensuales/anuales por categoría
5. **metas_ahorro**: Objetivos de ahorro específicos con fechas meta

## Mejoras Potenciales

- **Tipos de transacciones más ricos**: Agrupar mejor tipos de gastos/ingresos
- **Dashboards visuales**: Agregar vistas de gráficos
- **Automatización de presupuesto**: Alertas automáticas cuando se exceden presupuestos
- **Sincronización multiplataforma**: Exportar/importar datos
- **Presets de presupuesto**: Plantillas predefinidas de presupuestos
- **Divisiones avanzadas**: Divisiones de gastos múltiples (ej: split bill)

## Servicios de IA (Futuro)

El sistema puede ser mejorado con IA avanzada para:
- **Parseo de lenguaje natural**: Mejor detección de categorías y montos
- **Detección de patrones**: Identificar patrones de gasto sospechosos
- **Recomendaciones inteligentes**: Sugerir presupuestos o objetivos basados en historial
- **Predicciones**: Predecir gastos futuros basados en tendencias
- **Detección de anomalías**: Alertar sobre transacciones inusuales

---

Este bot proporciona una solución **completa de finanzas personales** que satisface los requisitos exactos del usuario. ¡Listo para comenzar a manejar tus finanzas personales de forma inteligente!
