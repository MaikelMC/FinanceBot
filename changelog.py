"""
changelog.py - Control de versiones y mejoras del bot
Cuando actualices el bot, agrega una nueva entrada en CHANGELOG
y actualiza VERSION_ACTUAL. Los usuarios verán las mejoras automáticamente.
"""

VERSION_ACTUAL = "2.14.4"

CHANGELOG = {
    "2.14.4": {
        "titulo": "🛡️ Validaciones más robustas de tus entradas",
        "mejoras": [
            "Montos: solo se aceptan valores positivos; '-50', '0' o texto sin número muestran 'Monto inválido. Usa un formato como: $50 o 100.50'",
            "Fechas: al cambiar la fecha de una transacción se valida que exista (rechaza 2024-02-30) y que no sea futura",
            "Descripciones: se recortan automáticamente a 200 caracteres para evitar errores al guardar",
            "La validación aplica en todos los caminos: lenguaje natural, botones del menú y respuestas de la IA"
        ],
        "emoji": "🛡️"
    },
    "2.14.3": {
        "titulo": "🚦 Protección anti-flood del bot",
        "mejoras": [
            "Límite de 30 mensajes por minuto por usuario para evitar bloqueos de Telegram",
            "Si excedes el límite, el bot avisa: 'Demasiadas solicitudes. Intenta de nuevo en N segundos'",
            "/start y /help nunca se bloquean: los comandos críticos siempre funcionan",
            "Los contadores se limpian automáticamente cada minuto"
        ],
        "emoji": "🚦"
    },
    "2.14.2": {
        "titulo": "🎯 Los flujos de presupuestos y ahorros recuerdan lo que seleccionaste",
        "mejoras": [
            "En Presupuestos → Restante de un presupuesto, ahora puedes restar un gasto directamente: elige un presupuesto, toca 'Restar gasto de este presupuesto' y escribe el monto (ej: 'gasté 50 cup')",
            "Si seleccionas un presupuesto y escribes un gasto, se registra asociado a ESE presupuesto (se descuenta de su categoría), ya no como un gasto general",
            "En Ahorros → Agregar dinero a una meta, al elegir la meta puedes escribir solo el monto (ej: '500') y se suma a la meta seleccionada, sin necesidad de repetir su nombre",
            "Escribe 'cancelar' en cualquier flujo para salir sin aplicar el cambio"
        ],
        "emoji": "🎯"
    },
    "2.14.0": {
        "titulo": "🧭 Navegación guiada con botones",
        "mejoras": [
            "Nuevo menú principal con 7 secciones: Balance, Presupuestos, Ahorros, Monedas, Transacciones, Ayuda y Más opciones",
            "Cada sección tiene botones para sus acciones y un botón Volver; se navega tocando (el teclado de texto ya no se usa)",
            "Consultas al instante: balance del mes, gastos, ingresos, presupuestos, restante, metas, monedas, resumen y últimas transacciones",
            "Acciones con datos (crear presupuesto/meta, agregar dinero, registrar gasto/ingreso) te guían con un ejemplo para escribir en lenguaje natural",
            "Más opciones agrupa Notificaciones, Exportar, Resumen del mes y Borrar historial",
            "La IA sigue disponible: siempre puedes escribir directo, y al terminar verás el menú principal"
        ],
        "emoji": "🧭"
    },
    "2.13.5": {
        "titulo": "🧹 Eliminar todas las metas de ahorro en un mensaje",
        "mejoras": [
            "\"Elimina todas mis metas\", \"borra todos mis ahorros\" borra TODAS tus metas de ahorro de una vez",
            "Confirma cuántas metas se eliminaron; si no tienes ninguna, te lo avisa",
            "Nueva función masiva en ambos backends (SQLite y Google Sheets)"
        ],
        "emoji": "🧹"
    },
    "2.13.4": {
        "titulo": "🗑️ Eliminación de metas de ahorro corregida",
        "mejoras": [
            "\"Elimina la meta de ahorro del regalo de mi novia\" ahora borra la META (antes se mezclaba con presupuestos o transacciones)",
            "Búsqueda de la meta por nombre con coincidencias parciales y fuzzy; si no la encuentra, muestra tus metas actuales",
            "Nueva función de eliminación en ambos backends (SQLite y Google Sheets)"
        ],
        "emoji": "🗑️"
    },
    "2.13.3": {
        "titulo": "➕ Agregar dinero a metas de ahorro existentes",
        "mejoras": [
            "\"Agrega 900 cup a la meta de ahorro del regalo de mi novia\" ahora SUMA a la meta existente (antes creaba una meta nueva duplicada)",
            "Las metas con nombres sucios (\"cup para un regalo de mi novia\") se limpian automáticamente",
            "Si no encuentro la meta mencionada, te muestro tus metas actuales para que elijas la correcta"
        ],
        "emoji": "➕"
    },
    "2.13.2": {
        "titulo": "🎯 Consulta y creación de metas de ahorro corregidas",
        "mejoras": [
            "\"Ver mis ahorros\", \"revisar mis metas\" y \"cuánto llevo ahorrado\" ahora muestran tus metas de ahorro (antes saltaban a balance o presupuestos)",
            "Al crear una meta, el objetivo ya no queda en pronombres como \"eso\" o \"ello\": se usa el propósito real (\"quiero ahorrar 5000 para vacaciones\" → \"vacaciones\")",
            "Nueva subconsulta \"metas\" en el motor de intenciones (IA + regex) para que no se confunda con balance ni presupuestos"
        ],
        "emoji": "🎯"
    },
    "2.13.1": {
        "titulo": "🏷️ Nombres de presupuesto más inteligentes",
        "mejoras": [
            "El nombre del presupuesto ya no queda en pronombres como \"ello\" o \"eso\": si tras el monto solo hay una referencia, el bot usa el tema real de tu mensaje",
            "Ejemplo: \"quiero comprarme un cable nuevo para cargar mi teléfono, presupuesto de 1000 cup para ello\" crea el presupuesto \"cable de carga\", no \"ello\"",
            "Los nombres que sean referencias se corrigen solos (fallback + IA) sin cambiar el monto ni la moneda"
        ],
        "emoji": "🏷️"
    },
    "2.13": {
        "titulo": "📅 Balance por mes (se resetea cada mes)",
        "mejoras": [
            "El balance consultado ahora es del mes en curso: al pasar de mes se resetea solo, sin borrar tu historial",
            "El encabezado indica el período: \"Balance de agosto 2026\" en botón, /user y consultas",
            "Los presupuestos se validan contra el balance del mes, no contra todo el historial",
            "El resumen diario y el resumen mensual muestran el balance del mes",
            "El histórico queda intacto: puedes consultarlo con el resumen mensual, análisis por fecha y /exportar"
        ],
        "emoji": "📅"
    },
    "2.12": {
        "titulo": "🎨 Mensajes rediseñados, más claros",
        "mejoras": [
            "Diseño unificado de mensajes: emojis semánticos, montos con separador de miles (1,500.00) y jerarquía clara",
            "Balance y resumen mensual por moneda en formato tabular: 📈 ingresos · 📉 gastos → neto",
            "Presupuestos con barra de progreso y porcentaje en una sola línea, con la abreviatura de la moneda",
            "Alertas de presupuesto con un único emoji de aviso y el nombre del presupuesto en negrita",
            "El bot que no entiende te muestra 3 ejemplos cortos y te deriva a /help"
        ],
        "emoji": "🎨"
    },
    "2.11": {
        "titulo": "⚖️ Presupuestos ligados a tu balance real",
        "mejoras": [
            "No puedes crear un presupuesto mayor al balance disponible en su moneda (ej: con $200 USD no puedes fijar $300)",
            "La suma de todos tus presupuestos de una moneda no puede exceder el balance de esa moneda",
            "Al añadir dinero a un presupuesto se respeta la moneda que ya tiene (no se mezclan CUP y USD)",
            "Si el monto no cabe, te decimos cuánto balance tienes, cuánto ya comprometiste y cuánto te queda libre"
        ],
        "emoji": "⚖️"
    },
    "2.10": {
        "titulo": "📤 Exporta tus datos a Excel",
        "mejoras": [
            "Descargá tus movimientos como archivo Excel (.xlsx) listo para abrir y editar, con balance, movimientos y gastos por categoría",
            "También podés exportar en formato CSV compatible con otras apps",
            "Elegí el período: todo el historial, este mes o los últimos 30 días (también con /exportar 2026-07)",
            "Con lenguaje natural: 'exporta mis datos del mes', 'descarga mi historial'",
            "Si hay demasiados movimientos, se dividen automáticamente en varias hojas para no pasar los límites de Excel"
        ],
        "emoji": "📤"
    },
    "2.9": {
        "titulo": "🔔 Notificaciones: alertas y resumen diario",
        "mejoras": [
            "Alertas en tiempo real cuando un presupuesto llega al 80%, se agota (100%) o se excede (125%)",
            "Resumen diario automático todos los días a las 21:30 (hora de Cuba)",
            "Activa o desactiva el resumen y cada alerta desde el comando /notificaciones",
            "Si el bot estaba dormido a la hora del resumen, te lo envía apenas vuelvas a escribir"
        ],
        "emoji": "🔔"
    },
    "2.8": {
        "titulo": "🗣️ Pregúntale a tu bot en tus palabras",
        "mejoras": [
            "Responde consultas con vocabulario libre: 'cuánto me queda de mi presupuesto para barbería', 'cuánto puedo gastar todavía de comida'",
            "Descubrí cuánto gastaste de tus presupuestos en un período: 'cuánto gasté ayer de mis presupuestos'",
            "Te muestra el mayor gasto de un día, semana o mes: 'cuál fue el gasto que más tuve ayer'",
            "Los análisis por fecha muestran la moneda de cada transacción y tus totales por moneda"
        ],
        "emoji": "🗣️"
    },
    "2.7": {
        "titulo": "📉 Gastos ligados a presupuestos",
        "mejoras": [
            "Si registrás un gasto mencionando tu presupuesto (ej: 'gasté 500 del presupuesto para barbería'), se descuenta automáticamente de ese presupuesto",
            "La respuesta te muestra cuánto llevás gastado y cuánto te queda del presupuesto",
            "Aumentá el dinero de un presupuesto con lenguaje natural: 'añade 500 al presupuesto de barbería'"
        ],
        "emoji": "📉"
    },
    "2.6": {
        "titulo": "💱 Presupuestos con moneda",
        "mejoras": [
            "Los presupuestos ahora usan la moneda que digas (CUP, USD, USDT, etc.)",
            "Si tenés varias monedas y no aclarás cuál usar, el bot te pide elegir con botones (igual que las transacciones)",
            "El menú y la consulta de presupuestos muestran el símbolo de la moneda de cada uno"
        ],
        "emoji": "💱"
    },
    "2.5": {
        "titulo": "🧠 Respuestas reales y presupuestos por nombre",
        "mejoras": [
            "Eliminá presupuestos en lenguaje natural: 'Elimina el presupuesto de comida'",
            "Los presupuestos tienen nombre propio y se reutilizan si repetís el mismo nombre (sin duplicados)",
            "Las preguntas y pedidos de consejo financiero ahora se responden con una respuesta relacionada a lo que preguntás",
            "Agregar monto a un presupuesto funciona aunque tengas varios de la misma categoría"
        ],
        "emoji": "🧠"
    },
    "2.4": {
        "titulo": "💰 Presupuestos que se actualizan",
        "mejoras": [
            "Al decir 'añade 500 al presupuesto de comida', el bot suma al presupuesto existente en vez de crear uno nuevo",
            "Redefinir un presupuesto por categoría reemplaza el anterior (sin duplicados)",
            "El bot responde el total disponible tras añadir al presupuesto"
        ],
        "emoji": "💰"
    },
    "2.3": {
        "titulo": "💬 Conversaciones más limpias",
        "mejoras": [
            "Al confirmar una acción, el bot reemplaza el mensaje con los botones por la respuesta final",
            "Menos mensajes repetidos al gestionar monedas, borrar historial y registrar transacciones",
            "El preview de varias transacciones se actualiza en un solo mensaje al quitar elementos"
        ],
        "emoji": "💬"
    },
    "2.2": {
        "titulo": "📋 Nuevos comandos y correcciones",
        "mejoras": [
            "Nuevos comandos: /resumen, /categorias, /gastos, /ingresos y /metas",
            "Menú de comandos de Telegram con descripciones (escribe / para verlos)",
            "Corregido: crear presupuestos por lenguaje natural",
            "Corregido: crear y ver metas de ahorro",
            "Búsqueda por lenguaje natural distingue gastos e ingresos"
        ],
        "emoji": "✨"
    },
    "2.1": {
        "titulo": "🚀 Nuevas funciones disponibles",
        "mejoras": [
            "Análisis de gastos por fecha: pregunta qué gastaste esta semana, este mes o un día específico",
            "Varias transacciones de una sola vez: \"Gasté $50 en comida y $30 en taxi\"",
            "Interpretación robusta de números: $248.50, 1.500 pesos, todo funciona bien",
            "Categorías más inteligentes: cervezas va a Ocio, inversiones se reconocen como ingresos"
        ],
        "emoji": "🎉"
    },
    "2.0": {
        "titulo": "🔧 Mejoras importantes",
        "mejoras": [
            "Corregí errores que afectaban a otros usuarios",
            "El bot ahora es más estable y confiable",
            "Respuestas más claras cuando algo no se entiende"
        ],
        "emoji": "✅"
    }
}
