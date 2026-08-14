"""
changelog.py - Control de versiones y mejoras del bot
Cuando actualices el bot, agrega una nueva entrada en CHANGELOG
y actualiza VERSION_ACTUAL. Los usuarios verán las mejoras automáticamente.
"""

VERSION_ACTUAL = "2.4"

CHANGELOG = {
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
