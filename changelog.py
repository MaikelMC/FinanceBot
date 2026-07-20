"""
changelog.py - Control de versiones y mejoras del bot
Cuando actualices el bot, agregá una nueva entrada en CHANGELOG
y actualizá VERSION_ACTUAL. Los usuarios verán las mejoras automáticamente.
"""

VERSION_ACTUAL = "2.1"

CHANGELOG = {
    "2.1": {
        "titulo": "🚀 Nuevas funciones disponibles",
        "mejoras": [
            "Análisis de gastos por fecha: preguntá qué gastaste esta semana, este mes o un día específico",
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
