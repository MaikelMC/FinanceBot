"""
changelog.py - Control de versiones y mejoras del bot
Cuando actualices el bot, agrega una nueva entrada en CHANGELOG
y actualiza VERSION_ACTUAL. Los usuarios verán las mejoras automáticamente.
"""

VERSION_ACTUAL = "2.11"

CHANGELOG = {
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
