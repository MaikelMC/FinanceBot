"""
knowledge.py - Módulo de IA para finanzas personales
Maneja la lógica de IA para preguntas en lenguaje natural relacionadas con finanzas.
"""

import logging
import re
from typing import Dict, Any, Optional

import database

logger = logging.getLogger(__name__)


def consultar_ia_finanzas(user_message: str, usuario: Dict[str, Any]) -> str:
    """
    Consulta la IA para interpretar y procesar mensajes financieros.
    """
    logger.info("Consulta IA de %s: %s", usuario["nombre"], user_message)

    # Intentar parsear primero con regex básico
    intent = _detectar_intencion_usuario(user_message)

    if intent:
        return _procesar_intencion_finanzas(intent, user_message, usuario)

    # Si no se puede parsear, responder con IA generica
    return _generar_respuesta_ia_finanzas(user_message, usuario)


def _detectar_intencion_usuario(mensaje: str) -> str:
    """Detecta la intención del usuario en un mensaje financiero."""
    mensaje_lower = mensaje.lower()

    # Patrones para diferentes tipos de transacciones
    patrones_gasto = [
        r"gasté\s+\$?(\d+(?:\.\d+)?)",
        r"compré\s+\$?(\d+(?:\.\d+)?)",
        r"pagó\s+\$?(\d+(?:\.\d+)?)",
        r"\$?(\d+(?:\.\d+)?)\s+en\s+",
        r"\$?(\d+(?:\.\d+)?)\s+para\s+",
    ]

    patrones_ingreso = [
        r"recibí\s+\$?(\d+(?:\.\d+)?)",
        r"salario\s+\$?(\d+(?:\.\d+)?)",
        r"pagaron\s+\$?(\d+(?:\.\d+)?)",
        r"ingresé\s+\$?(\d+(?:\.\d+)?)",
        r"\$?(\d+(?:\.\d+)?)\s+como\s+",
    ]

    for patron in patrones_gasto:
        if re.search(patron, mensaje_lower):
            return "gasto"

    for patron in patrones_ingreso:
        if re.search(patron, mensaje_lower):
            return "ingreso"

    # Detectar preguntas sobre balance
    if any(word in mensaje_lower for word in ["balance", "saldo", "total"]):
        return "balance"

    # Detectar preguntas sobre categorías
    if any(word in mensaje_lower for word in ["categoria", "categoría", "gastos", "ingresos"]):
        return "categorias"

    return None


def _procesar_intencion_finanzas(intencion: str, mensaje: str, usuario: Dict[str, Any]) -> str:
    """Procesa una intención financiera detectada."""

    if intencion == "gasto":
        return _procesar_gasto(mensaje, usuario)
    elif intencion == "ingreso":
        return _procesar_ingreso(mensaje, usuario)
    elif intencion == "balance":
        return _procesar_balance(usuario)
    elif intencion == "categorias":
        return _procesar_categorias(usuario)

    return _generar_respuesta_ia_finanzas(mensaje, usuario)


def _procesar_gasto(mensaje: str, usuario: Dict[str, Any]) -> str:
    """Procesa una transacción de gasto."""
    # Extraer cantidad y categoría del mensaje
    cantidad = None
    categoria = None
    descripcion = ""

    # Buscar cantidad
    texto_normalizado = re.sub(r'[\$\€\£\¥\¢]', '', mensaje).replace(',', '.')
    cantidad_match = re.search(r"(\d+(?:\.\d+)?)", texto_normalizado)
    if cantidad_match:
        cantidad = float(cantidad_match.group(1))

    # Buscar palabra clave de categoría
    categorias_gastos = ["comida", "supermercado", "restaurante", "desayuno", "almuerzo", "cena",
                         "transporte", "gasolina", "servicio", "hogar", "utiles"]

    for cat in categorias_gastos:
        if cat in mensaje.lower():
            categoria = cat
            break

    if not categoria:
        categoria = "otros"

    if not cantidad:
        return "No pude entender la cantidad en tu gasto. ¿Podrías especificar el monto?"

    # Registrar transacción
    try:
        # Primero obtener el ID de la categoría
        categorias = database.obtener_categorias(usuario["id"], categoria)
        categoria_id = categorias[0]["id"] if categorias else None

        if not categoria_id:
            # Crear categoría si no existe
            categoria_info = database.crear_categoria(usuario["id"], categoria, "gastos")
            categoria_id = categoria_info["id"]

        database.agregar_transaccion(usuario["id"], categoria_id, "gasto", cantidad,
                                   f"Gasto: {mensaje}")

        return f"✅ Gasto registrado: ${cantidad:.2f} en '{categoria}'"
    except Exception as e:
        logger.error("Error al procesar gasto: %s", e)
        return f"❌ Ocurrió un error al registrar tu gasto: {cantidad:.2f} en '{categoria}'. Por favor, inténtalo de nuevo."


def _procesar_ingreso(mensaje: str, usuario: Dict[str, Any]) -> str:
    """Procesa una transacción de ingreso."""
    cantidad = None
    categoria = None
    descripcion = ""

    # Buscar cantidad
    texto_normalizado = re.sub(r'[\$\€\£\¥\¢]', '', mensaje).replace(',', '.')
    cantidad_match = re.search(r"(\d+(?:\.\d+)?)", texto_normalizado)
    if cantidad_match:
        cantidad = float(cantidad_match.group(1))

    # Buscar palabra clave de categoría para ingresos
    categorias_ingresos = ["salario", "remuneración", "pago", "bonus", "bonificación", "intereses",
                           "dividendos", "regalo", "herencia", "ventas"]

    for cat in categorias_ingresos:
        if cat in mensaje.lower():
            categoria = cat
            break

    if not categoria:
        categoria = "otros ingresos"

    if not cantidad:
        return "No pude entender la cantidad en tu ingreso. ¿Podrías especificar el monto?"

    try:
        categorias = database.obtener_categorias(usuario["id"], "ingresos")
        categoria_id = None

        if categorias:
            # Buscar categoría exacta o usar la primera disponible
            for cat in categorias:
                if cat["nombre"] == categoria.lower():
                    categoria_id = cat["id"]
                    break

        if not categoria_id:
            # Crear categoría si no existe
            categoria_info = database.crear_categoria(usuario["id"], categoria, "ingresos")
            categoria_id = categoria_info["id"]

        database.agregar_transaccion(usuario["id"], categoria_id, "ingreso", cantidad,
                                   f"Ingreso: {mensaje}")

        return f"✅ Ingreso registrado: ${cantidad:.2f} de '{categoria}'"
    except Exception as e:
        logger.error("Error al procesar ingreso: %s", e)
        return f"❌ Ocurrió un error al registrar tu ingreso: {cantidad:.2f} de '{categoria}'. Por favor, inténtalo de nuevo."


def _procesar_balance(usuario: Dict[str, Any]) -> str:
    """Obtiene y muestra el balance del usuario."""
    try:
        balance = database.obtener_balance(usuario["id"])

        lineas = [
            "💰 **TU BALANCE FINANCIERO ACTUAL**",
            "━━━━━━━━━━━━━━━━━",
            f"💵 Total Ingresos: ${balance['ingresos']:.2f}",
            f"💳 Total Gastos: ${balance['gastos']:.2f}",
            f"📊 Balance Neto: ${balance['neto']:.2f}",
            "",
            "¿Necesitas detalles sobre transacciones recientes o quieres configurar un presupuesto?",
        ]

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error al obtener balance: %s", e)
        return "❌ Ocurrió un error al obtener tu balance. Por favor, inténtalo de nuevo."


def _procesar_transacciones(usuario: Dict[str, Any], limite: int = 10, tipo: Optional[str] = None) -> str:
    """Muestra las transacciones del usuario, opcionalmente filtradas por tipo (gasto/ingreso)."""
    try:
        transacciones = database.obtener_transacciones(usuario["id"], limite, tipo)

        if not transacciones:
            if tipo == "gasto":
                return "📝 No tienes gastos registrados todavia."
            if tipo == "ingreso":
                return "📝 No tienes ingresos registrados todavia."
            return "📝 No tienes transacciones registradas todavia."

        titulo = "TUS TRANSACCIONES RECIENTES"
        if tipo == "gasto":
            titulo = "TUS GASTOS RECIENTES"
        elif tipo == "ingreso":
            titulo = "TUS INGRESOS RECIENTES"

        emoji = {"gasto": "💸", "ingreso": "💰"}
        lineas = [f"📋 **{titulo}**", "━━━━━━━━━━━━━━━━━"]
        for t in transacciones:
            icono = emoji.get(t["tipo"], "🔹")
            categoria = t.get("categoria_nombre", "sin categoria")
            desc = t.get("descripcion", "") or ""
            fecha = t.get("fecha", "")[:10]
            lineas.append(f"{icono} **${t['cantidad']:.2f}** | {categoria}")
            if desc:
                lineas.append(f"   └ {desc}")
            lineas.append(f"   └ {fecha}")

        total = sum(t["cantidad"] for t in transacciones)
        if tipo:
            label = "gastado" if tipo == "gasto" else "recibido"
            lineas.append(f"\n💰 Total {label}: ${total:.2f}")
        lineas.append(f"📊 {len(transacciones)} registro(s)")
        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error al obtener transacciones: %s", e)
        return "Ocurrio un error al obtener tus transacciones."


def _procesar_gastos(usuario: Dict[str, Any]) -> str:
    """Muestra solo los gastos del usuario."""
    return _procesar_transacciones(usuario, tipo="gasto")


def _procesar_ingresos(usuario: Dict[str, Any]) -> str:
    """Muestra solo los ingresos del usuario."""
    return _procesar_transacciones(usuario, tipo="ingreso")


def _procesar_presupuestos(usuario: Dict[str, Any]) -> str:
    """Muestra los presupuestos activos del usuario."""
    try:
        presupuestos = database.obtener_presupuestos(usuario["id"])

        if not presupuestos:
            return "📋 No tienes presupuestos configurados. Usa: 'Mi presupuesto para X es $Y este mes'"

        lineas = ["📋 **TUS PRESUPUESTOS**", "━━━━━━━━━━━━━━━━━"]
        for p in presupuestos:
            cat = p.get("categoria_nombre", "General")
            planeado = p["cantidad_planejada"]
            gastado = p["cantidad_gastada"]
            restante = planeado - gastado
            progreso = (gastado / planeado * 100) if planeado > 0 else 0
            barra = "█" * int(progreso / 10) + "░" * (10 - int(progreso / 10))

            lineas.append(f"📌 **{cat}**")
            lineas.append(f"   Presupuesto: ${planeado:.2f}")
            lineas.append(f"   Gastado: ${gastado:.2f} ({progreso:.0f}%)")
            lineas.append(f"   Restante: ${restante:.2f}")
            lineas.append(f"   {barra}")
            if p["periodo"]:
                lineas.append(f"   Periodo: {p['periodo']}")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error al obtener presupuestos: %s", e)
        return "Ocurrio un error al obtener tus presupuestos."


def _procesar_categorias(usuario: Dict[str, Any]) -> str:
    """Muestra las categorías del usuario."""
    try:
        categorias_gastos = database.obtener_categorias(usuario["id"], "gastos")
        categorias_ingresos = database.obtener_categorias(usuario["id"], "ingresos")
        categorias_ahorros = database.obtener_categorias(usuario["id"], "ahorros")
        categorias_inversiones = database.obtener_categorias(usuario["id"], "inversiones")

        lineas = ["📋 **TUS CATEGORÍAS FINANCIERAS**", "━━━━━━━━━━━━━━━━━"]

        if categorias_gastos:
            lineas.append("💸 **Gastos:**")
            for cat in categorias_gastos:
                lineas.append(f"  • {cat['nombre']} - {cat.get('descripcion', '')}")

        if categorias_ingresos:
            lineas.append("\n💰 **Ingresos:**")
            for cat in categorias_ingresos:
                lineas.append(f"  • {cat['nombre']} - {cat.get('descripcion', '')}")

        if categorias_ahorros:
            lineas.append("\n🏦 **Ahorros:**")
            for cat in categorias_ahorros:
                lineas.append(f"  • {cat['nombre']} - {cat.get('descripcion', '')}")

        if categorias_inversiones:
            lineas.append("\n📈 **Inversiones:**")
            for cat in categorias_inversiones:
                lineas.append(f"  • {cat['nombre']} - {cat.get('descripcion', '')}")

        if not (categorias_gastos or categorias_ingresos or categorias_ahorros or categorias_inversiones):
            lineas.append("\n📝 No tienes categorías configuradas todavía. ¡Crea algunas para empezar!")

        lineas.append("\n¿Quieres crear una nueva categoría o registrar una transacción?")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error al obtener categorías: %s", e)
        return "❌ Ocurrió un error al obtener tus categorías. Por favor, inténtalo de nuevo."


def _generar_respuesta_ia_finanzas(mensaje: str, usuario: Dict[str, Any]) -> str:
    """
    Genera una respuesta genérica cuando la IA no puede determinar la intención exacta.
    """
    mensaje_lower = mensaje.lower()

    if any(word in mensaje_lower for word in ["hola", "hi", "buenas"]):
        return f"¡Hola! 👋 Soy FinanzasBot. ¿Cómo puedo ayudarte con tus finanzas hoy?"

    if any(word in mensaje_lower for word in ["ayuda", "help", "comandos"]):
        return "\n".join([
            "🤖 **COMANDOS DE FINANZAS BOT:**",
            "• /start - Iniciar/Reiniciar el bot",
            "• /user - Ver tu información de usuario",
            "• /help - Ver esta lista de comandos",
            "",
            "📝 Ejemplos de comandos en lenguaje natural:",
            "• 'Gasté $50 en comida para el desayuno'",
            "• 'Mi presupuesto para comida es $500 este mes'",
            "• 'Quiero ahorrar $2000 para unas vacaciones'",
            "• '¿Cuál es mi balance actual?'",
        ])

    # Para mensajes no reconocidos, intentar un último intento de parseo
    if "\\$" in mensaje and any(c in mensaje_lower for c in ["dólar", "usd", "\\$", "cup"]):
        cantidad = re.search(r"\$?(\d+(?:\.\d+)?)", mensaje)
        if cantidad:
            return f"👋 ¡Hola! Registré una transacción de ${cantidad.group(1)}. ¿Podrías especificarme el tipo (gasto/ingreso) y categoría?"

    return (
        f"👋 Hola! No entendí completamente tu mensaje: \"{mensaje}\".\n\n"
        "¿Podrías ser más específico? Por ejemplo:\n"
        "• 'Gasté $50 en comida' para registrar un gasto\n"
        "• 'Mi presupuesto es $300 para el mes' para configurar un presupuesto\n"
        "• '¿Cuál es mi balance?' para consultar tu saldo\n"
        "¿Cómo puedo ayudarte mejor?"
    )