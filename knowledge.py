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
    elif intencion == "modificar_transaccion":
        return _procesar_modificar_transaccion(mensaje, usuario)
    elif intencion == "eliminar_transaccion":
        return _procesar_eliminar_transaccion(mensaje, usuario)

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
                                   mensaje)

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
                                   mensaje)

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

        emoji = {"gasto": "📉", "ingreso": "📈"}
        lineas = [f"📋 **{titulo}**", "━━━━━━━━━━━━━━━━━"]
        for t in transacciones:
            icono = emoji.get(t["tipo"], "🔹")
            tipo_label = "Ingreso" if t["tipo"] == "ingreso" else "Gasto"
            desc = _limpiar_descripcion(t.get("descripcion", "") or "")
            fecha = t.get("fecha", "")[:19]
            lineas.append(f"{icono} ${t['cantidad']:.2f} - {tipo_label}: {desc} ({fecha})")

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
            "",
            "✏️ Modificar datos:",
            "• 'Cambia el gasto de $50 a ingreso'",
            "• 'Modifica la descripción de mi último gasto'",
            "• 'Elimina la transacción de $30'",
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
        "• 'Cambia el gasto a ingreso' para modificar datos\n"
        "¿Cómo puedo ayudarte mejor?"
    )


# ============================================================
# FUNCIONES DE MODIFICACIÓN DE TRANSACCIONES
# ============================================================

def _limpiar_descripcion(desc: str) -> str:
    """Elimina prefijos y palabras innecesarias de la descripción."""
    if not desc:
        return ""
    if desc.lower().startswith("gasto: "):
        desc = desc[7:].strip()
    elif desc.lower().startswith("ingreso: "):
        desc = desc[9:].strip()
    # Eliminar palabras verbales al inicio
    for prefijo in ["gasté ", "gaste ", "recibí ", "recibi ", "compré ", "compre ", "pagué ", "pague "]:
        if desc.lower().startswith(prefijo):
            desc = desc[len(prefijo):].strip()
            break
    return desc


def _detectar_modificacion(mensaje: str) -> Dict[str, Any]:
    """
    Detecta qué quiere modificar el usuario y extrae los parámetros.
    Retorna un dict con:
      - accion: "cambiar_tipo" | "cambiar_monto" | "cambiar_descripcion" | "cambiar_categoria" | "cambiar_fecha" | "eliminar" | "desconocido"
      - valor_nuevo: el nuevo valor (si aplica)
      - referencia: texto para buscar la transacción (ej: "último gasto", "$50")
    """
    mensaje_lower = mensaje.lower().strip()
    resultado = {"accion": "desconocido", "valor_nuevo": None, "referencia": None}

    # --- ELIMINAR ---
    if any(w in mensaje_lower for w in ["eliminar", "elimina", "borrar", "borra", "quitar", "quita", "remover", "remueve"]):
        resultado["accion"] = "eliminar"
        resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
        return resultado

    # --- CAMBIAR TIPO (gasto <-> ingreso) ---
    # Patrones amplios: "de gasto a ingreso", "a ingreso", "como ingreso", "que sea ingreso"
    patron_tipo = re.search(
        r'(?:de|desde|que\s+(?:era|fue|es|esta))?\s*(?:gasto|gastos|ingreso|ingresos)'
        r'\s+(?:a|al|para|por|como|que\s+(?:sea|pase|quede|pueda\s+ser))\s*'
        r'(?:un?\s*)?(ingreso|gasto|ingresos|gastos)',
        mensaje_lower
    )
    if patron_tipo:
        nuevo_tipo_raw = patron_tipo.group(1)
        nuevo_tipo = "ingreso" if "ingreso" in nuevo_tipo_raw else "gasto"
        resultado["accion"] = "cambiar_tipo"
        resultado["valor_nuevo"] = nuevo_tipo
        resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
        return resultado

    # Patrones simples: "a ingreso", "a gasto"
    if any(w in mensaje_lower for w in ["a ingreso", "a ingresos", "como ingreso", "tipo ingreso", "que sea ingreso"]):
        resultado["accion"] = "cambiar_tipo"
        resultado["valor_nuevo"] = "ingreso"
        resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
        return resultado

    if any(w in mensaje_lower for w in ["a gasto", "a gastos", "como gasto", "tipo gasto", "que sea gasto"]):
        resultado["accion"] = "cambiar_tipo"
        resultado["valor_nuevo"] = "gasto"
        resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
        return resultado

    # --- CAMBIAR MONTO ---
    if any(w in mensaje_lower for w in ["monto", "cantidad", "importe", "precio"]):
        nuevo_monto = _extraer_nuevo_valor(mensaje_lower)
        if nuevo_monto is not None:
            resultado["accion"] = "cambiar_monto"
            resultado["valor_nuevo"] = nuevo_monto
            resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
            return resultado

    # Detectar patrón "de $X a $Y"
    patron_de_a = re.search(r'de\s+\$?(\d+(?:\.\d+)?)\s+a\s+\$?(\d+(?:\.\d+)?)', mensaje_lower)
    if patron_de_a:
        resultado["accion"] = "cambiar_monto"
        resultado["valor_nuevo"] = float(patron_de_a.group(2))
        resultado["referencia"] = f"${patron_de_a.group(1)}"
        return resultado

    # --- CAMBIAR DESCRIPCIÓN ---
    if any(w in mensaje_lower for w in ["descripción", "descripcion", "nombre", "texto", "detalle"]):
        nueva_desc = _extraer_nueva_descripcion(mensaje_lower)
        if nueva_desc:
            resultado["accion"] = "cambiar_descripcion"
            resultado["valor_nuevo"] = nueva_desc
            resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
            return resultado

    # --- CAMBIAR CATEGORÍA ---
    if any(w in mensaje_lower for w in ["categoría", "categoria", "clasificar", "clasificacion"]):
        nueva_cat = _extraer_nueva_categoria(mensaje_lower)
        if nueva_cat:
            resultado["accion"] = "cambiar_categoria"
            resultado["valor_nuevo"] = nueva_cat
            resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
            return resultado

    # --- CAMBIAR FECHA ---
    if any(w in mensaje_lower for w in ["fecha", "día", "dia", "cuándo", "cuando"]):
        nueva_fecha = _extraer_nueva_fecha(mensaje_lower)
        if nueva_fecha:
            resultado["accion"] = "cambiar_fecha"
            resultado["valor_nuevo"] = nueva_fecha
            resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
            return resultado

    return resultado


def _extraer_referencia_transaccion(mensaje_lower: str) -> Optional[str]:
    """
    Extrae una referencia para identificar qué transacción modificar.
    Puede ser: 'último gasto', '$50', 'la de ayer', etc.
    """
    # "el último gasto/ingreso"
    for w in ["último", "ultimo", "ultima", "última", "mas reciente", "más reciente", "reciente"]:
        if w in mensaje_lower:
            if "gasto" in mensaje_lower:
                return "ultimo_gasto"
            if "ingreso" in mensaje_lower:
                return "ultimo_ingreso"
            return "ultimo"

    # "el gasto de $X"
    monto_ref = re.search(r'(?:de|por)\s+\$?(\d+(?:\.\d+)?)', mensaje_lower)
    if monto_ref:
        return f"${monto_ref.group(1)}"

    # "el gasto/ingreso de ayer/hoy"
    for fecha in ["ayer", "hoy", "anteayer"]:
        if fecha in mensaje_lower:
            if "gasto" in mensaje_lower:
                return f"gasto_{fecha}"
            if "ingreso" in mensaje_lower:
                return f"ingreso_{fecha}"
            return fecha

    # genérico
    if "gasto" in mensaje_lower:
        return "gasto"
    if "ingreso" in mensaje_lower:
        return "ingreso"

    return None


def _extraer_nuevo_valor(mensaje_lower: str) -> Optional[float]:
    """Extrae el nuevo valor/monto del mensaje."""
    # Buscar "$X" o "a $X"
    match = re.search(r'(?:a|de|por|son|valor)\s+\$?(\d+(?:\.\d+)?)', mensaje_lower)
    if match:
        return float(match.group(1))

    # Buscar patrón "$X"
    match = re.search(r'\$(\d+(?:\.\d+)?)', mensaje_lower)
    if match:
        return float(match.group(1))

    return None


def _extraer_nueva_descripcion(mensaje_lower: str) -> Optional[str]:
    """Extrae la nueva descripción del mensaje."""
    # "cambia la descripción a X" / "ponle descripción X"
    match = re.search(r'(?:a|como|poner?|ponle?|que diga|que sea)\s+(.+)', mensaje_lower)
    if match:
        desc = match.group(1).strip()
        palabras = desc.split()
        desc_limpia = [p for p in palabras if p not in {
            "el", "la", "los", "las", "un", "una", "de", "del", "por", "para",
            "que", "y", "o", "pero", "también", "tambien",
        } and len(p) > 1]
        return " ".join(desc_limpia) if desc_limpia else None

    return None


def _extraer_nueva_categoria(mensaje_lower: str) -> Optional[str]:
    """Extrae la nueva categoría del mensaje."""
    categorias_conocidas = [
        "comida", "supermercado", "restaurante", "transporte", "gasolina",
        "servicio", "hogar", "salud", "ocio", "educación", "educacion",
        "ropa", "tecnología", "tecnologia", "suscripción", "suscripcion",
        "salario", "bonus", "inversiones", "regalos", "otros",
    ]

    # "a la categoría X" / "en categoría X"
    match = re.search(r'(?:a|en|de|categoría?|categoria?)\s+(?:la\s+)?(?:categoría?\s+)?(\w+)', mensaje_lower)
    if match:
        cat = match.group(1)
        if cat in categorias_conocidas:
            return cat

    # Buscar directamente una categoría conocida
    for cat in categorias_conocidas:
        if cat in mensaje_lower:
            return cat

    return None


def _extraer_nueva_fecha(mensaje_lower: str) -> Optional[str]:
    """Extrae la nueva fecha del mensaje."""
    from datetime import datetime, timedelta

    hoy = datetime.now()

    textos_fecha = {
        "hoy": hoy.strftime("%Y-%m-%d"),
        "ayer": (hoy - timedelta(days=1)).strftime("%Y-%m-%d"),
        "anteayer": (hoy - timedelta(days=2)).strftime("%Y-%m-%d"),
        "el lunes": (hoy - timedelta(days=(hoy.weekday() + 7) % 7 or 7)).strftime("%Y-%m-%d"),
        "el martes": (hoy - timedelta(days=(hoy.weekday() - 1 + 7) % 7 or 7)).strftime("%Y-%m-%d"),
        "el miércoles": (hoy - timedelta(days=(hoy.weekday() - 2 + 7) % 7 or 7)).strftime("%Y-%m-%d"),
        "el jueves": (hoy - timedelta(days=(hoy.weekday() - 3 + 7) % 7 or 7)).strftime("%Y-%m-%d"),
        "el viernes": (hoy - timedelta(days=(hoy.weekday() - 4 + 7) % 7 or 7)).strftime("%Y-%m-%d"),
    }

    for key, fecha in textos_fecha.items():
        if key in mensaje_lower:
            return fecha

    # Buscar formato YYYY-MM-DD
    match = re.search(r'(\d{4}-\d{2}-\d{2})', mensaje_lower)
    if match:
        return match.group(1)

    # Buscar formato DD/MM/YYYY o DD-MM-YYYY
    match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', mensaje_lower)
    if match:
        return f"{match.group(3)}-{match.group(2).zfill(2)}-{match.group(1).zfill(2)}"

    return None


def _buscar_transaccion(usuario: Dict[str, Any], referencia: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Busca una transacción del usuario basándose en una referencia.
    Retorna la transacción encontrada o None.
    """
    if not referencia:
        # Sin referencia: tomar la última transacción
        transacciones = database.obtener_transacciones(usuario["id"], 1)
        return transacciones[0] if transacciones else None

    # "ultimo_gasto"
    if referencia == "ultimo_gasto":
        transacciones = database.obtener_transacciones(usuario["id"], 10, "gasto")
        return transacciones[0] if transacciones else None

    # "ultimo_ingreso"
    if referencia == "ultimo_ingreso":
        transacciones = database.obtener_transacciones(usuario["id"], 10, "ingreso")
        return transacciones[0] if transacciones else None

    # "ultimo" (cualquiera)
    if referencia == "ultimo":
        transacciones = database.obtener_transacciones(usuario["id"], 1)
        return transacciones[0] if transacciones else None

    # "$X" - buscar por monto
    if referencia.startswith("$"):
        monto_str = referencia[1:]
        try:
            monto = float(monto_str)
        except ValueError:
            return None
        transacciones = database.obtener_transacciones(usuario["id"], 50)
        for t in transacciones:
            if abs(t["cantidad"] - monto) < 0.01:
                return t
        return None

    # "gasto_ayer" / "ingreso_ayer" etc
    if "_ayer" in referencia or "_hoy" in referencia:
        partes = referencia.split("_")
        tipo = partes[0] if partes[0] in ("gasto", "ingreso") else None
        fecha_ref = partes[1] if len(partes) > 1 else None

        transacciones = database.obtener_transacciones(usuario["id"], 50, tipo)
        if fecha_ref == "ayer":
            from datetime import datetime, timedelta
            fecha_ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            for t in transacciones:
                if t.get("fecha", "").startswith(fecha_ayer):
                    return t
        elif fecha_ref == "hoy":
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            for t in transacciones:
                if t.get("fecha", "").startswith(fecha_hoy):
                    return t

        return transacciones[0] if transacciones else None

    # "gasto" o "ingreso" genérico
    if referencia in ("gasto", "ingreso"):
        transacciones = database.obtener_transacciones(usuario["id"], 1, referencia)
        return transacciones[0] if transacciones else None

    # "ayer" genérico
    if referencia == "ayer":
        from datetime import datetime, timedelta
        fecha_ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        transacciones = database.obtener_transacciones(usuario["id"], 50)
        for t in transacciones:
            if t.get("fecha", "").startswith(fecha_ayer):
                return t
        return None

    return None


def _procesar_modificar_transaccion(mensaje: str, usuario: Dict[str, Any]) -> str:
    """Procesa una solicitud de modificación de transacción."""
    mod = _detectar_modificacion(mensaje)
    accion = mod["accion"]

    if accion == "desconocido":
        return (
            "🤔 No pude entender qué querés modificar.\n\n"
            "Podés hacer cosas como:\n"
            "• 'Cambia el gasto a ingreso'\n"
            "• 'Modifica el monto a $100'\n"
            "• 'Cambia la descripción a almuerzo'\n"
            "• 'Cambia la categoría a transporte'\n"
            "• 'Elimina el último gasto'"
        )

    # Buscar la transacción objetivo
    transaccion = _buscar_transaccion(usuario, mod["referencia"])

    if not transaccion:
        return "❌ No encontré la transacción que querés modificar. ¿Podés especificar cuál?"

    tid = transaccion["id"]

    # --- ELIMINAR ---
    if accion == "eliminar":
        confirmado = database.eliminar_transaccion(usuario["id"], tid)
        if confirmado:
            tipo_icono = "📉" if transaccion["tipo"] == "gasto" else "📈"
            tipo_label = "Gasto" if transaccion["tipo"] == "gasto" else "Ingreso"
            desc = _limpiar_descripcion(transaccion.get("descripcion", "Sin descripción"))
            return (
                f"🗑️ **Transacción eliminada:**\n"
                f"{tipo_icono} ${transaccion['cantidad']:.2f} - {tipo_label}: {desc}"
            )
        return "❌ No pude eliminar la transacción. Intenta de nuevo."

    # --- CAMBIAR TIPO ---
    if accion == "cambiar_tipo":
        nuevo_tipo = mod["valor_nuevo"]
        if nuevo_tipo == transaccion["tipo"]:
            return f"ℹ️ La transacción ya es un **{nuevo_tipo}**. No hay cambios necesarios."

        # Buscar o crear categoría del nuevo tipo
        nuevo_tipo_cat = "ingresos" if nuevo_tipo == "ingreso" else "gastos"
        categorias = database.obtener_categorias(usuario["id"], nuevo_tipo_cat)
        nueva_categoria_id = categorias[0]["id"] if categorias else None

        if not nueva_categoria_id:
            cat_info = database.crear_categoria(usuario["id"], "otros", nuevo_tipo_cat)
            nueva_categoria_id = cat_info["id"]

        actualizada = database.actualizar_transaccion(
            usuario["id"], tid,
            tipo=nuevo_tipo,
            categoria_id=nueva_categoria_id
        )

        if actualizada:
            emoji_nuevo = "📈" if nuevo_tipo == "ingreso" else "📉"
            label_nuevo = "Ingreso" if nuevo_tipo == "ingreso" else "Gasto"
            label_viejo = "Gasto" if nuevo_tipo == "ingreso" else "Ingreso"
            desc = _limpiar_descripcion(transaccion.get("descripcion", "Sin descripción"))
            return (
                f"✅ **Tipo cambiado:**\n"
                f"De: 📉 {label_viejo}: {desc}\n"
                f"A: {emoji_nuevo} ${transaccion['cantidad']:.2f} - {label_nuevo}: {desc}"
            )
        return "❌ No pude cambiar el tipo. Intenta de nuevo."

    # --- CAMBIAR MONTO ---
    if accion == "cambiar_monto":
        nuevo_monto = mod["valor_nuevo"]
        if nuevo_monto is None or nuevo_monto <= 0:
            return "❌ El monto nuevo no es válido. Especificá un número positivo."

        actualizada = database.actualizar_transaccion(
            usuario["id"], tid, cantidad=nuevo_monto
        )
        if actualizada:
            return (
                f"✅ **Monto actualizado:**\n"
                f"De ${transaccion['cantidad']:.2f} → **${nuevo_monto:.2f}**"
            )
        return "❌ No pude actualizar el monto. Intenta de nuevo."

    # --- CAMBIAR DESCRIPCIÓN ---
    if accion == "cambiar_descripcion":
        nueva_desc = mod["valor_nuevo"]
        if not nueva_desc:
            return "❌ No pude entender la nueva descripción. Especificá el texto."

        actualizada = database.actualizar_transaccion(
            usuario["id"], tid, descripcion=nueva_desc
        )
        if actualizada:
            return (
                f"✅ **Descripción actualizada:**\n"
                f"De '{transaccion.get('descripcion', 'Sin descripción')}' → **'{nueva_desc}'**"
            )
        return "❌ No pude actualizar la descripción. Intenta de nuevo."

    # --- CAMBIAR CATEGORÍA ---
    if accion == "cambiar_categoria":
        nueva_cat_nombre = mod["valor_nuevo"]
        if not nueva_cat_nombre:
            return "❌ No pude entender la nueva categoría."

        tipo_cat = "ingresos" if transaccion["tipo"] == "ingreso" else "gastos"
        categorias = database.obtener_categorias(usuario["id"], tipo_cat)

        cat_encontrada = None
        for c in categorias:
            if c["nombre"].lower() == nueva_cat_nombre.lower():
                cat_encontrada = c
                break

        if not cat_encontrada:
            cat_info = database.crear_categoria(usuario["id"], nueva_cat_nombre, tipo_cat)
            cat_encontrada = cat_info

        actualizada = database.actualizar_transaccion(
            usuario["id"], tid, categoria_id=cat_encontrada["id"]
        )
        if actualizada:
            return (
                f"✅ **Categoría cambiada:**\n"
                f"De '{transaccion.get('categoria_nombre', 'Sin categoría')}' → **'{nueva_cat_nombre}'**"
            )
        return "❌ No pude cambiar la categoría. Intenta de nuevo."

    # --- CAMBIAR FECHA ---
    if accion == "cambiar_fecha":
        nueva_fecha = mod["valor_nuevo"]
        if not nueva_fecha:
            return "❌ No pude entender la nueva fecha."

        actualizada = database.actualizar_transaccion(
            usuario["id"], tid, fecha=nueva_fecha
        )
        if actualizada:
            fecha_ant = transaccion.get("fecha", "N/A")[:10]
            return (
                f"✅ **Fecha actualizada:**\n"
                f"De {fecha_ant} → **{nueva_fecha}**"
            )
        return "❌ No pude actualizar la fecha. Intenta de nuevo."

    return "❌ Ocurrió un error al procesar la modificación. Intenta de nuevo."


def _procesar_eliminar_transaccion(mensaje: str, usuario: Dict[str, Any]) -> str:
    """Procesa una solicitud de eliminación de transacción."""
    mod = _detectar_modificacion(mensaje)
    referencia = mod.get("referencia")

    transaccion = _buscar_transaccion(usuario, referencia)

    if not transaccion:
        return "❌ No encontré la transacción que querés eliminar. ¿Podés especificar cuál?"

    tid = transaccion["id"]
    confirmado = database.eliminar_transaccion(usuario["id"], tid)

    if confirmado:
        tipo_icono = "📉" if transaccion["tipo"] == "gasto" else "📈"
        tipo_label = "Gasto" if transaccion["tipo"] == "gasto" else "Ingreso"
        desc = _limpiar_descripcion(transaccion.get("descripcion", "Sin descripción"))
        return (
            f"🗑️ **Transacción eliminada:**\n"
            f"{tipo_icono} ${transaccion['cantidad']:.2f} - {tipo_label}: {desc}"
        )
    return "❌ No pude eliminar la transacción. Intenta de nuevo."