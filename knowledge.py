"""
knowledge.py - Módulo de IA para finanzas personales
Maneja la lógica de IA para preguntas en lenguaje natural relacionadas con finanzas.
"""

import logging
import re
from typing import Dict, Any, Optional, List

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
    cantidad = _parsear_cantidad(mensaje)

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
        categorias = database.obtener_categorias(usuario["id"], "gastos")
        categoria_id = None

        for cat in categorias:
            if cat["nombre"].lower() == categoria.lower():
                categoria_id = cat["id"]
                break

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
    cantidad = _parsear_cantidad(mensaje)

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

        for cat in categorias:
            if cat["nombre"].lower() == categoria.lower():
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
    """Obtiene y muestra el balance del usuario, agrupado por moneda."""
    try:
        balance = database.obtener_balance(usuario["id"])
        por_moneda = balance.get("por_moneda", {})

        lineas = [
            "💰 **TU BALANCE FINANCIERO ACTUAL**",
            "━━━━━━━━━━━━━━━━━",
        ]

        if len(por_moneda) > 1 or (len(por_moneda) == 1 and list(por_moneda.keys()) != ["Sin moneda"]):
            for abrev, datos in por_moneda.items():
                simbolo = datos.get("simbolo", "$")
                nombre = datos.get("nombre", abrev)
                neto_m = datos["ingresos"] - datos["gastos"]
                lineas.append(f"**{simbolo} {nombre} ({abrev})**")
                lineas.append(f"  📈 Ingresos: {simbolo}{datos['ingresos']:.2f}")
                lineas.append(f"  📉 Gastos: {simbolo}{datos['gastos']:.2f}")
                lineas.append(f"  💵 Neto: {simbolo}{neto_m:.2f}")
                lineas.append("")
        else:
            lineas.append(f"💵 Total Ingresos: ${balance['ingresos']:.2f}")
            lineas.append(f"💳 Total Gastos: ${balance['gastos']:.2f}")
            lineas.append(f"📊 Balance Neto: ${balance['neto']:.2f}")

        lineas.append("")
        lineas.append("¿Necesitas detalles sobre transacciones recientes o quieres configurar un presupuesto?")

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
            fecha = t.get("fecha", "")[:10]
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
    if "$" in mensaje or any(c in mensaje_lower for c in ["dólar", "usd", "cup"]):
        cantidad_val = _parsear_cantidad(mensaje)
        if cantidad_val:
            return f"👋 ¡Hola! Registré una transacción de ${cantidad_val:.2f}. ¿Podrías especificarme el tipo (gasto/ingreso) y categoría?"

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
# PARSING DE MÚLTIPLES TRANSACCIONES
# ============================================================

# Palabras que indican separación entre transacciones
SEPARADORES_MENSAJE = re.compile(
    r'\s*(?:'
    r'\by\s+también\b|\by\s+además\b|\by\b'
    r'|\btambién\b|\bademás\b'
    r'|\bluego\b|\bdespués\b|\bdespues\b'
    r'|\bes\s+todo\b|\bes\s+todo\s+lo\s+que\b'
    r'|,\s*;?\s*'
    r')\s*',
    re.IGNORECASE
)


def _parsear_cantidad(texto: str) -> Optional[float]:
    """
    Parser robusto de cantidades monetarias.
    Convención: punto (.) = decimal SIEMPRE, coma (,) = miles SIEMPRE.
    Ejemplos: $248.50 → 248.5, 1,500 → 1500, 1,248.50 → 1248.5, 248,50 → 24850 (coma=miles)
    Retorna float o None si no encuentra número.
    """
    # Eliminar espacios que separan miles: "1 248" -> "1248"
    texto = re.sub(r'(?<=\d)\s(?=\d{3})', '', texto)
    # Normalizar "dólares"/"dolares"/"pesos" a "$"
    texto = re.sub(r'\b(dólares?|dolares?|pesos?|bs?\.?)\b', '$', texto, flags=re.IGNORECASE)
    # Eliminar símbolos de moneda
    texto_limpio = re.sub(r'[\$\€\£\¥\¢]', '', texto)

    # Caso 1: Punto como decimal SIEMPRE (248.50, 1,248.50, 1.248.50)
    match_decimal = re.search(r'(\d{1,3}(?:,\d{3})*\.\d{1,2})\b', texto_limpio)
    if match_decimal:
        num_str = match_decimal.group(1).replace(',', '')
        try:
            return float(num_str)
        except ValueError:
            pass

    # Caso 2: Número con coma como separador de miles, sin decimal (1,500 o 1,248,000)
    match_miles_coma = re.search(r'(\d{1,3}(?:,\d{3})+)\b', texto_limpio)
    if match_miles_coma:
        num_str = match_miles_coma.group(1).replace(',', '')
        try:
            return float(num_str)
        except ValueError:
            pass

    # Caso 3: Número simple (248, 50, 100, 1500)
    match_simple = re.search(r'(\d+(?:\.\d+)?)', texto_limpio)
    if match_simple:
        try:
            return float(match_simple.group(1))
        except ValueError:
            pass

    return None


def _esensaje_multi_transaccion(mensaje: str) -> bool:
    """
    Detecta si un mensaje contiene múltiples transacciones.
    Usa múltiples señales: varios montos, conectores temporales, verbos de acción repetidos.
    """
    msg = mensaje.lower()

    # Señal 1: Dos o más montos con símbolo $
    montos_dolar = re.findall(r'\$[\d\.,]+', mensaje)
    if len(montos_dolar) >= 2:
        return True

    # Señal 2: Dos o más números seguidos de contexto monetario (con o sin verbos)
    montos_texto = re.findall(
        r'\d+(?:[.,]\d+)?\s*(?:dólares?|dolares?|pesos?|bs?\.?|en\s|de\s|para\s)',
        msg
    )
    if len(montos_texto) >= 2:
        return True

    # Señal 3: Dos o más números con palabras de contexto entre ellos
    # Ej: "50 taxi 100 comida", "comida 50 transporte 100"
    numeros_con_contexto = re.findall(
        r'\d+(?:[.,]\d+)?\s*\w+',
        msg
    )
    if len(numeros_con_contexto) >= 2:
        return True

    # Señal 4: Números separados por conectores
    # Ej: "50 en taxi. 100 en comida", "50 taxi; 100 comida"
    tiene_dos_numeros = len(re.findall(r'\d+', msg)) >= 2
    tiene_separador = any(s in msg for s in [
        ".", ";", "y", "luego", "después", "despues", "también", "tambien",
        "además", "ademas", "ah y", "por cierto", "de paso",
    ])
    if tiene_dos_numeros and tiene_separador:
        return True

    # Señal 5: Números + conectores temporales que indican secuencia de acciones
    tiene_conector = any(w in msg for w in [
        "luego", "después", "despues", "y también", "y tambien",
        "además", "ademas", "es todo lo que", "es todo"
    ])
    tiene_numero = bool(re.search(r'\d+', msg))
    tiene_verbo_accion = any(w in msg for w in [
        "gasté", "gaste", "compré", "compre", "pagué", "pague",
        "recibí", "recibi", "cobré", "cobro", "gané", "gane",
        "ingresé", "ingrese", "costó", "costo", "perdí", "perdi",
        "me costó", "me costo", "me salió", "me salio", "me cobró", "me cobro",
    ])
    if tiene_conector and tiene_numero and tiene_verbo_accion:
        return True

    return False


def _split_transacciones(mensaje: str) -> List[str]:
    """
    Divide un mensaje en fragmentos, cada uno conteniendo una transacción.
    Maneja conectores naturales: 'y', 'luego', 'después', comas, puntos, etc.
    """
    # Paso 1: Normalizar separadores fuertes a marcador
    msg = mensaje
    for sep in [r'\bluego\b', r'\bdespués\b', r'\bdespues\b', r'\bes\s+todo\b',
                r'\by\s+también\b', r'\by\s+tambien\b', r'\bademás\b', r'\bademas\b',
                r'\bpor\s+cierto\b', r'\bde\s+paso\b', r'\bpor\s+último\b', r'\bpor\s+ultimo\b',
                r'\by\s+otra\s+cosa\b', r'\by\s+una\s+cosa\s+más\b', r'\by\s+una\s+cosa\s+mas\b',
                r'\bah\s*,?\s*y\b']:
        msg = re.sub(sep, ' ||| ', msg, flags=re.IGNORECASE)

    # Paso 2: Separar por marcador fuerte
    fragmentos = [f.strip() for f in re.split(r'\|\|\|', msg) if f.strip()]

    # Paso 3: Separar por puntuación fuerte (punto y coma, dos puntos)
    # NOTA: NO separamos por "." porque el punto es EXCLUSIVAMENTE decimal (234.60)
    fragmentos_puntuacion = []
    for frag in fragmentos:
        partes = re.split(r'[;:]\s*', frag)
        if len(partes) >= 2 and sum(1 for p in partes if re.search(r'[\d.]+', p)) >= 2:
            fragmentos_puntuacion.extend([p.strip() for p in partes if p.strip()])
        else:
            fragmentos_puntuacion.append(frag)
    fragmentos = fragmentos_puntuacion

    # Paso 3b: Separar por "también"/"tambien" (sin "y" delante)
    fragmentos_tambien = []
    for frag in fragmentos:
        partes = re.split(r'\s*también\s+|\s*tambien\s*', frag, flags=re.IGNORECASE)
        if len(partes) >= 2 and sum(1 for p in partes if re.search(r'[\d.]+', p)) >= 2:
            fragmentos_tambien.extend([p.strip() for p in partes if p.strip()])
        else:
            fragmentos_tambien.append(frag)
    fragmentos = fragmentos_tambien

    # Paso 4: Para cada fragmento, intentar separar por comas si hay acción múltiple
    fragmentos_expandidos = []
    for frag in fragmentos:
        # Proteger comas dentro de números decimales (248,50 → 248{COMA}50)
        frag_protegido = re.sub(r'(\d),(\d)', r'\1{COMA}\2', frag)
        partes_coma = re.split(r',\s*', frag_protegido)
        # Restaurar comas protegidas
        partes_coma = [p.replace('{COMA}', ',') for p in partes_coma]
        if len(partes_coma) >= 2 and sum(1 for p in partes_coma if re.search(r'[\d.]+', p)) >= 2:
            fragmentos_expandidos.extend([p.strip() for p in partes_coma if p.strip()])
        else:
            fragmentos_expandidos.append(frag)

    # Paso 5: Separar por "y" + verbo de acción O "y" + número O "y" + contexto monetario
    verbos_accion = [
        "gasté", "gaste", "compré", "compre", "pagué", "pague", "costó", "costo",
        "recibí", "recibi", "cobré", "cobro", "gané", "gane", "ingresé", "ingrese",
        "perdí", "perdi", "pagamos", "compramos", "gastamos", "cobramos", "ganamos",
        "recibimos", "ingresamos", "salí", "salio", "salimos",
        "me costó", "me costo", "me salió", "me salio", "me cobró", "me cobro",
    ]
    verbo_pattern = '|'.join(re.escape(v) for v in verbos_accion)
    resultado = []
    for frag in fragmentos_expandidos:
        # Separar por "y" + verbo
        partes = re.split(
            r'\s+y\s+(?:' + verbo_pattern + r')',
            frag, flags=re.IGNORECASE
        )
        # También separar por "y" + "$" (ej: "comida y $20 de transporte")
        partes_expandidas = []
        for p in partes:
            sub = re.split(r'\s+y\s+\$', p, flags=re.IGNORECASE)
            partes_expandidas.extend(sub)
        # También separar por "y" + número (ej: "50 en taxi y 100 en comida")
        partes_finales = []
        for p in partes_expandidas:
            sub = re.split(r'\s+y\s+(?=[\d.])', p, flags=re.IGNORECASE)
            partes_finales.extend(sub)
        # Separar por "y" + palabra de contexto + número (ej: "taxi 50 y uber 30")
        # Usar lookahead para no consumir la palabra de contexto
        CONTEXT_WORDS = r'(?:taxi|uber|bus|comida|supermercado|restaurante|farmacia|ropa|luz|agua|internet|alquiler|salario|sueldo|bonus|regalo|venta|compra|pago|transporte|servicio|ocio|salud|educación)'
        partes_ctx = []
        for p in partes_finales:
            sub = re.split(r'\s+y\s+(?=' + CONTEXT_WORDS + r'\s+[\d.])', p, flags=re.IGNORECASE)
            partes_ctx.extend(sub)
        resultado.extend([p.strip() for p in partes_ctx if p.strip()])

    # Paso 6: Filtrar fragmentos sin número
    result = [f for f in resultado if re.search(r'[\d.]+', f)]

    # Paso 7: Si un fragmento tiene dos números con palabra de contexto entre ellos,
    # separar por la palabra de contexto (ej: "50 taxi 100 comida" → "50 taxi" + "100 comida")
    CTX = r'(?:taxi|uber|bus|comida|supermercado|restaurante|farmacia|ropa|luz|agua|internet|alquiler|salario|sueldo|bonus|regalo|venta|compra|pago|transporte|servicio|ocio|salud|educación)'
    result_final = []
    for f in result:
        # Buscar patrón: número + palabra_contexto + número (preservando decimales)
        match = re.search(r'([\d.]+)\s+' + CTX + r'\s+([\d.]+)', f, flags=re.IGNORECASE)
        if match:
            # Encontrar el índice donde empieza la palabra de contexto
            ctx_match = re.search(r'\s+' + CTX + r'\s+', f, flags=re.IGNORECASE)
            if ctx_match:
                idx = ctx_match.start()
                primera = f[:idx].strip()
                segunda = f[idx:].strip()
                if primera and re.search(r'[\d.]+', primera):
                    result_final.append(primera)
                if segunda and re.search(r'[\d.]+', segunda):
                    result_final.append(segunda)
                continue
        result_final.append(f)

    return result_final if result_final else [mensaje]


def _detectar_cantidad_en_texto(texto: str) -> Optional[float]:
    """Detecta una cantidad monetaria en un fragmento de texto."""
    return _parsear_cantidad(texto)


def _detectar_tipo_en_texto(texto: str) -> Optional[str]:
    """Detecta si un fragmento describe un gasto o ingreso."""
    t = texto.lower()
    gasto_kw = [
        "gasté", "gaste", "gasto", "gastos", "compré", "compre", "compra", "compras",
        "pagué", "pague", "pago", "pagos", "costó", "costo", "pagar",
        "perdí", "perdi", "pérdida", "perdida",
        "invertí", "inverti", "inversión", "inversion",
        "me costó", "me costo", "me salió", "me salio", "me cobró", "me cobro",
        "le di", "le pagué", "le pague",
    ]
    ingreso_kw = [
        "recibí", "recibi", "ingresé", "ingrese", "cobré", "cobro",
        "gané", "gane", "salario", "sueldo", "ingreso", "ingresos",
        "bonus", "bono", "regalo", "ganancia", "dividendos", "intereses",
        "agrega", "agregar", "remuneración", "herencia",
        "me dieron", "me pagan", "me pagan",
    ]
    if any(re.search(r'\b' + kw + r'\b', t) for kw in gasto_kw):
        return "gasto"
    if any(re.search(r'\b' + kw + r'\b', t) for kw in ingreso_kw):
        return "ingreso"
    return None


def _detectar_categoria_en_texto(texto: str, tipo: str) -> str:
    """Detecta la categoría de un fragmento de texto."""
    t = texto.lower()

    if tipo == "gasto":
        cats = {
            "comida": ["comida", "comer", "almuerzo", "cena", "desayuno", "restaurante",
                       "restaurant", "mcdo", "mcdonald", "burger", "pizza", "supermercado",
                       "super", "mercado", "almacén", "almacen"],
            "ocio": ["ocio", "entretenimiento", "diversión", "diversion", "juego",
                    "juegos", "cinema", "cine", "teatro", "concierto", "música",
                    "musica", "netflix", "spotify", "streaming", "cerveza", "cervezas",
                    "bar", "birra", "alcohol", "trago", "tragos", "copa", "copas",
                    "fiesta", "party", "rumba", "disco"],
            "transporte": ["transporte", "gasolina", "uber", "taxi", "bus", "peaje",
                          "estacionamiento", "parking", "mecánico", "mekaniko",
                          "combustible", "nafta", "garaje"],
            "servicio": ["servicio", "servicios", "luz", "agua", "internet", "teléfono",
                        "telefono", "cable", "electricidad"],
            "hogar": ["hogar", "casa", "alquiler", "renta", "hipoteca", "mantenimiento",
                     "reparación", "reparacion", "mueble"],
            "salud": ["salud", "médico", "medico", "farmacia", "medicina", "doctor",
                     "hospital", "clínica", "clinica", "dentista"],
            "educación": ["educación", "educacion", "curso", "clase", "universidad",
                         "colegio", "escuela", "libro", "libros", "uteniles", "útiles"],
            "ropa": ["ropa", "vestido", "camisa", "pantalón", "zapato", "calzado",
                    "tienda"],
            "tecnología": ["tecnología", "tecnologia", "computadora", "celular",
                          "teléfono", "telefono", "electrónica", "electronica", "equipo"],
            "suscripción": ["suscripción", "suscripcion", "mensualidad", "abono"],
        }
        for cat, keywords in cats.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', t) for kw in keywords):
                return cat

    elif tipo == "ingreso":
        cats = {
            "salario": ["salario", "sueldo", "remuneración", "remuneracion", "pago",
                       "nómina", "nomina"],
            "bonus": ["bonus", "bono", "bonificación", "bonificacion", "prima",
                     "comisión", "comision"],
            "inversiones": ["inversión", "inversion", "inversiones", "dividendos",
                          "intereses", "bitcoin", "crypto", "staking", "acciones"],
            "regalos": ["regalo", "regalos", "herencia", "donación", "donacion"],
            "ventas": ["venta", "ventas", "vendí", "vendi", "cobro"],
        }
        for cat, keywords in cats.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', t) for kw in keywords):
                return cat

    return "otros"


def _extraer_descripcion_limpia(texto: str, cantidad_texto: str = "") -> str:
    """Extrae la descripción limpia de un fragmento, removiendo montos, números y verbos."""
    desc = texto
    # Remover el texto del monto si está
    if cantidad_texto:
        desc = desc.replace(cantidad_texto, "")
    # Remover verbos comunes al inicio
    for verb in ["gasté", "gaste", "recibí", "recibi", "compré", "compre",
                 "pagué", "pague", "costó", "costo", "cobré", "cobro",
                 "gané", "gane", "perdí", "perdi", "ingresé", "ingrese",
                 "pagamos", "compramos", "gastamos", "cobramos", "ganamos",
                 "recibimos", "ingresamos", "salimos", "salí", "salio"]:
        if desc.lower().startswith(verb + " "):
            desc = desc[len(verb):].strip()
            break
    # Remover conectores al final (y recibi, y gaste, luego, despues, etc.)
    desc = re.sub(r'\s*,?\s*\by\s+(?:recib[íi]|gast[ée]|compr[ée]|pag[ué]|cobr[éi]|gan[éi]|ingres[éi]|perdí|costó|cobro|salio|salimos)\b.*$', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'\s*,?\s*(?:luego|después|despues|además|ademas)\s+.*$', '', desc, flags=re.IGNORECASE)
    # Remover símbolos de moneda y palabras de moneda
    desc = re.sub(r'[\$\€\£\¥\¢]', '', desc)
    desc = re.sub(r'\b(dólares?|dolares?|pesos?|bs?\.?)\b', '', desc, flags=re.IGNORECASE)
    # Remover números (el monto ya se extrajo)
    desc = re.sub(r'\b\d+(?:[.,]\d+)?\b', '', desc)
    # Remover espacios dobles y puntuación suelta al inicio/final
    desc = re.sub(r'\s+', ' ', desc).strip()
    desc = re.sub(r'^[,;\s]+|[,;\s]+$', '', desc)
    # Limpiar palabras de relleno al inicio
    palabras = desc.split()
    relleno = {"el", "la", "los", "las", "un", "una", "unas", "unos", "de", "del", "en", "por",
               "para", "que", "y", "o", "con", "a", "al", "lo", "le", "se",
               "su", "mis", "tus", "sus", "mi", "tu", "las", "los", "unas", "unos",
               "que", "lo", "q", "he", "hice", "hoy"}
    while palabras and palabras[0].lower() in relleno:
        palabras.pop(0)
    # También limpiar al final
    while palabras and palabras[-1].lower() in relleno:
        palabras.pop()
    return " ".join(palabras).strip() if palabras else ""


def _parsear_multi_transaccion(mensaje: str) -> List[Dict[str, Any]]:
    """
    Parsea un mensaje que puede contener múltiples transacciones.
    Retorna una lista de dicts con: {tipo, cantidad, descripcion, categoria}
    """
    fragmentos = _split_transacciones(mensaje)

    transacciones = []
    for frag in fragmentos:
        cantidad = _detectar_cantidad_en_texto(frag)
        if cantidad is None or cantidad <= 0:
            continue

        tipo = _detectar_tipo_en_texto(frag)
        if not tipo:
            # Inferir por contexto (ampliado para mensajes naturales)
            frag_lower = frag.lower()
            # Patrones de gasto: "en", "para", verbos, preposiciones con contexto de gasto
            patrones_gasto = ["en ", "para ", "compr", "gast", "pag", "cost",
                             "taxi", "uber", "bus", "comida", "supermercado",
                             "restaurante", "farmacia", "médico", "ropa",
                             "luz", "agua", "internet", "teléfono", "alquiler"]
            if any(w in frag_lower for w in patrones_gasto):
                tipo = "gasto"
            elif re.search(r'\$\s*\d+.*\bde\s+\w', frag_lower):
                tipo = "gasto"
            # Patrones de ingreso: "de", "recib", "cobr", "ingres", "gan", "salario"
            patrones_ingreso = ["de ", "recib", "cobr", "ingres", "gan",
                               "salario", "sueldo", "bonus", "regalo",
                               "dividendos", "intereses", "venta"]
            if any(w in frag_lower for w in patrones_ingreso):
                tipo = "ingreso"
            else:
                tipo = "gasto"  # default

        categoria = _detectar_categoria_en_texto(frag, tipo)
        descripcion = _extraer_descripcion_limpia(frag)

        transacciones.append({
            "tipo": tipo,
            "cantidad": cantidad,
            "descripcion": descripcion or f"Transacción de ${cantidad:.2f}",
            "categoria": categoria,
        })

    return transacciones


def _formatear_preview_transacciones(transacciones: List[Dict[str, Any]]) -> str:
    """Formatea una lista de transacciones como preview para confirmación."""
    if not transacciones:
        return "❌ No pude detectar ninguna transacción en tu mensaje."

    lineas = ["📋 **Transacciones detectadas:**", "━━━━━━━━━━━━━━━━━"]
    total_ingresos = 0
    total_gastos = 0

    for i, t in enumerate(transacciones, 1):
        emoji = "📈" if t["tipo"] == "ingreso" else "📉"
        label = "Ingreso" if t["tipo"] == "ingreso" else "Gasto"
        desc = t.get("descripcion", "Sin descripción")
        cat = t.get("categoria", "otros")
        lineas.append(f"{emoji} **{i}.** ${t['cantidad']:.2f} - {label}: {desc} ({cat})")
        if t["tipo"] == "ingreso":
            total_ingresos += t["cantidad"]
        else:
            total_gastos += t["cantidad"]

    lineas.append("━━━━━━━━━━━━━━━━━")
    neto = total_ingresos - total_gastos
    if total_ingresos > 0:
        lineas.append(f"📈 Total ingresos: ${total_ingresos:.2f}")
    if total_gastos > 0:
        lineas.append(f"📉 Total gastos: ${total_gastos:.2f}")
    lineas.append(f"💵 Neto: ${neto:.2f}")
    lineas.append("")
    lineas.append("¿Quieres guardar estas transacciones?")

    return "\n".join(lineas)


def _guardar_multi_transacciones(transacciones: List[Dict[str, Any]], usuario: Dict[str, Any]) -> str:
    """Guarda una lista de transacciones en la base de datos."""
    guardadas = 0
    errores = 0

    for t in transacciones:
        try:
            # Obtener o crear categoría
            tipo_cat = "ingresos" if t["tipo"] == "ingreso" else "gastos"
            categorias = database.obtener_categorias(usuario["id"], tipo_cat)
            categoria_id = None

            for cat in categorias:
                if cat["nombre"].lower() == t["categoria"].lower():
                    categoria_id = cat["id"]
                    break

            if not categoria_id:
                cat_info = database.crear_categoria(usuario["id"], t["categoria"], tipo_cat)
                categoria_id = cat_info["id"]

            database.agregar_transaccion(
                usuario["id"], categoria_id, t["tipo"],
                t["cantidad"], t["descripcion"]
            )
            guardadas += 1
        except Exception as e:
            logger.error("Error guardando transacción: %s", e)
            errores += 1

    if guardadas == 0:
        return "❌ No pude guardar ninguna transacción. Intenta de nuevo."

    resultado = f"✅ **{guardadas} transacción(es) guardada(s)**"
    if errores > 0:
        resultado += f"\n⚠️ {errores} no se pudieron guardar"

    return resultado


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
    patron_de_a = re.search(r'de\s+\$?([\d.,]+)\s+a\s+\$?([\d.,]+)', mensaje_lower)
    if patron_de_a:
        val_viejo = _parsear_cantidad(patron_de_a.group(1))
        val_nuevo = _parsear_cantidad(patron_de_a.group(2))
        if val_viejo and val_nuevo:
            resultado["accion"] = "cambiar_monto"
            resultado["valor_nuevo"] = val_nuevo
            resultado["referencia"] = f"${val_viejo}"
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
    monto_val = _parsear_cantidad(mensaje_lower)
    if monto_val and "de" in mensaje_lower or "por" in mensaje_lower:
        return f"${monto_val}"

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
    return _parsear_cantidad(mensaje_lower)


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
            "🤔 No pude entender qué quieres modificar.\n\n"
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
        return "❌ No encontré la transacción que quieres modificar. ¿Podés especificar cuál?"

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


# ============================================================
# RESPUESTAS CONTEXTUALES CUANDO NO ENTIENDE
# ============================================================

_ACCIONES_FINANCIERAS = [
    "gasté", "gaste", "compré", "compre", "pagué", "pague", "costó", "costo",
    "recibí", "recibi", "cobré", "cobro", "gané", "gane", "ingresé", "ingrese",
    "invertí", "inverti", "ahorré", "ahorre", "pagué", "pague",
    "compramos", "gastamos", "cobramos", "ganamos", "recibimos",
]

_CONSULTAS = [
    "cuánto", "cuanto", "cuántos", "cuantos", "cuál", "cual", "cuáles", "cuales",
    "balance", "saldo", "cuenta", "tengo", "dónde", "donde", "qué tengo",
    "mostrar", "ver", "listar", "resumen", "consulta", "consultar",
]

_CONFIGURACION = [
    "presupuesto", "meta", "ahorro", "ahorrar", "inversión", "inversion",
    "objetivo", "plan", "categoría", "categoria", "configurar", "establecer",
    "definir", "fijar", "asignar",
]

_MODIFICACION = [
    "cambiar", "modificar", "editar", "actualizar", "corregir", "mover",
    "convertir", "eliminar", "borrar", "quitar", "suprimir",
]


def _responder_ayuda_uso(mensaje: str) -> str:
    """Responde con ayuda contextual según lo que el usuario pregunte."""
    m = mensaje.lower()
    nombre = "amigo"

    # Detectar INTENCIÓN de la pregunta (cualquier forma)
    # 1. Registrar gasto
    if any(w in m for w in ["gasto", "gastar", "gasté", "gaste", "compra", "comprar",
                            "compré", "compre", "pago", "pagar", "pagué", "pague"]):
        return "\n".join([
            "💰 **Cómo registrar un gasto:**",
            "",
            "Escribe un mensaje con tu gasto en lenguaje natural:",
            "",
            "• `Gasté $50 en comida`",
            "• `Compré $30 de ropa`",
            "• `Pagué $100 de luz`",
            "• `$20 en transporte`",
            "• `Gasto $75 en supermercado`",
            "",
            "El bot detecta automáticamente la categoría y el monto.",
            "También puedes registrar varios gastos juntos:",
            "• `$50 en comida y $30 en transporte`",
        ])

    # 2. Registrar ingreso
    if any(w in m for w in ["ingreso", "ingresar", "ingresé", "ingrese",
                            "salario", "cobrar", "cobré", "cobro", "ganar",
                            "gané", "gane", "agrega", "agregar"]):
        return "\n".join([
            "📈 **Cómo registrar un ingreso:**",
            "",
            "Escribe un mensaje con tu ingreso:",
            "",
            "• `Recibí $2000 de salario`",
            "• `Ingresé $500 de trading`",
            "• `Cobré $300 de freelance`",
            "• `Agrega $100 de dividendos`",
            "• `Gané $150 de ventas`",
            "",
            "El bot lo clasifica como ingreso automáticamente.",
        ])

    # 3. Ver balance / saldo
    if any(w in m for w in ["balance", "saldo", "cuánto tengo", "cuanto tengo",
                            "ver dinero", "mi plata", "mi dinero", "mis finanzas"]):
        return "\n".join([
            "💵 **Cómo ver tu balance:**",
            "",
            "• `¿Cuánto tengo?` — Balance general",
            "• `¿Cuál es mi saldo?` — Ver saldo actual",
            "• `Ver balance` — Resumen de finanzas",
            "",
            "Te mostrará tus ingresos totales, gastos totales y saldo neto.",
        ])

    # 4. Ver transacciones / historial
    if any(w in m for w in ["transacción", "transaccion", "transacciones", "historial",
                            "movimiento", "movimientos", "ver mis", "listar",
                            "mostrar", "qué hice", "que hice", "últimas"]):
        return "\n".join([
            "📋 **Cómo ver tu historial:**",
            "",
            "• `¿Qué gasté hoy?` — Transacciones de hoy",
            "• `¿Qué hice ayer?` — Transacciones de ayer",
            "• `Ver transacciones` — Últimas transacciones",
            "• `Historial de esta semana` — Resumen semanal",
            "",
            "También puedes filtrar por categoría o fecha.",
        ])

    # 5. Ver gastos por categoría
    if any(w in m for w in ["categoría", "categoria", "categorías", "categorias",
                            "qué categoría", "que categoria"]):
        return "\n".join([
            "🏷️ **Cómo ver categorías:**",
            "",
            "• `¿Cuánto gasté en comida?` — Gastos en comida",
            "• `¿Cuánto gasté en transporte?` — Gastos en transporte",
            "• `¿Qué categorías tengo?` — Ver todas las categorías",
            "",
            "Las categorías se crean automáticamente al registrar transacciones.",
        ])

    # 6. Presupuesto
    if any(w in m for w in ["presupuesto", "budget", "planea", "planifica",
                            "límite", "limite", "tope"]):
        return "\n".join([
            "📊 **Cómo configurar un presupuesto:**",
            "",
            "• `Mi presupuesto para comida es $500 este mes`",
            "• `Presupuesto de transporte $200`",
            "• `Límite de gasto $1000 por mes`",
            "",
            "El bot te avisará cuando estés cerca del límite.",
        ])

    # 7. Ahorro / metas
    if any(w in m for w in ["ahorrar", "ahorro", "meta", "objetivo",
                            "vacaciones", "viaje", "emergencia"]):
        return "\n".join([
            "🎯 **Cómo configurar una meta de ahorro:**",
            "",
            "• `Quiero ahorrar $5000 para vacaciones`",
            "• `Meta de ahorro $3000 para emergencias`",
            "• `Objetivo: ahorrar $10000 este año`",
            "",
            "El bot te mostrará cuánto has ahorrado hacia tu meta.",
        ])

    # 8. Modificar transacción
    if any(w in m for w in ["modificar", "cambiar", "editar", "corregir",
                            "actualizar", "cambio"]):
        return "\n".join([
            "✏️ **Cómo modificar una transacción:**",
            "",
            "• `Cambiar mi último gasto a $75`",
            "• `Modifica la descripción de mi último gasto`",
            "• `Cambia el monto de $100 a $150`",
            "• `Pasa ese gasto a la categoría transporte`",
            "",
            "Puedes modificar monto, descripción, categoría o fecha.",
        ])

    # 9. Eliminar transacción
    if any(w in m for w in ["eliminar", "borrar", "quitar", "suprimir",
                            "delet", "remover"]):
        return "\n".join([
            "🗑️ **Cómo eliminar transacciones:**",
            "",
            "• `Eliminar mi último gasto`",
            "• `Borrar la transacción de $50`",
            "• `Quitar el gasto de comida`",
            "• `/delete` — Borrar todo el historial",
            "",
            "⚠️ Cuidado: eliminar todo el historial es irreversible.",
        ])

    # 10. Comandos generales del bot
    if any(w in m for w in ["comando", "comandos", "qué puedo", "que puedo",
                            "funciones", "opciones", "menú", "menu",
                            "qué hace", "que hace", "para qué sirve",
                            "cómo funciona", "como funciona"]):
        return "\n".join([
            "🤖 **Qué puedo hacer:**",
            "",
            "📝 **Registrar:**",
            "• Gastos: `Gasté $50 en comida`",
            "• Ingresos: `Recibí $2000 de salario`",
            "• Varios: `$50 comida y $30 transporte`",
            "",
            "📊 **Consultar:**",
            "• Balance: `¿Cuánto tengo?`",
            "• Historial: `¿Qué gasté hoy?`",
            "• Categorías: `¿Cuánto en comida?`",
            "",
            "⚙️ **Configurar:**",
            "• Presupuesto: `Mi presupuesto es $500 para comida`",
            "• Metas: `Quiero ahorrar $5000 para vacaciones`",
            "",
            "✏️ **Modificar/Eliminar:**",
            "• Cambiar: `Cambiar mi último gasto a $75`",
            "• Eliminar: `Eliminar mi último gasto`",
            "",
            "📋 **Comandos:**",
            "• `/start` — Iniciar el bot",
            "• `/help` — Ver ayuda completa",
            "• `/user` — Tu información",
            "• `/delete` — Borrar historial",
        ])

    # 11. Respuesta genérica para preguntas de uso no categorizadas
    return "\n".join([
        "🤖 **Cómo puedo ayudarte:**",
        "",
        "Pregúntame sobre cualquier funcionalidad:",
        "",
        "• ¿Cómo registro un gasto?",
        "• ¿Cómo veo mi balance?",
        "• ¿Cómo pongo un presupuesto?",
        "• ¿Cómo creo una meta de ahorro?",
        "• ¿Cómo modifico una transacción?",
        "• ¿Cómo elimino algo?",
        "• ¿Qué comandos tienes?",
        "",
        "O simplemente escribe tu gasto o ingreso directamente.",
    ])


def _generar_respuesta_no_entendido(mensaje: str, usuario: Dict[str, Any]) -> str:
    """
    Genera una respuesta contextual cuando el bot no entiende el mensaje.
    Analiza parcialmente la intención y guía al usuario con ejemplos específicos.
    """
    msg = mensaje.lower().strip()
    nombre = usuario.get("nombre", "amigo")

    # Señal 1: Tiene número pero no se detectó transacción
    tiene_numero = bool(re.search(r'\d+', msg))
    # Señal 2: Tiene palabras de acción financiera
    tiene_accion = any(w in msg for w in _ACCIONES_FINANCIERAS)
    # Señal 3: Tiene palabras de consulta
    tiene_consulta = any(w in msg for w in _CONSULTAS)
    # Señal 4: Tiene palabras de configuración
    tiene_config = any(w in msg for w in _CONFIGURACION)
    # Señal 5: Tiene palabras de modificación
    tiene_mod = any(w in msg for w in _MODIFICACION)
    # Señal 6: Saludo
    es_saludo = any(w in msg for w in ["hola", "hi", "hey", "buenas", "buenos", "buen"])

    # --- CASOS ESPECÍFICOS ---

    if es_saludo and len(msg.split()) <= 3:
        return (
            f"¡Hola {nombre}! 👋 ¿En qué te puedo ayudar?\n\n"
            "Podés:\n"
            "• 💸 Registrar un gasto: `Gasté $50 en comida`\n"
            "• 💰 Registrar un ingreso: `Recibí $300 de salario`\n"
            "• 📊 Ver tu balance: `¿Cuánto tengo?`\n"
            "• 📋 Ver transacciones: `¿Qué gasté hoy?`\n"
            "• ⚙️ Configurar presupuesto: `Mi presupuesto es $500 para comida`"
        )

    if tiene_consulta and not tiene_accion:
        return (
            f"🤔 {nombre}, parece que quieres **consultar** algo sobre tus finanzas.\n\n"
            "¿Qué te gustaría saber?\n"
            "• `¿Cuánto tengo?` — Ver balance general\n"
            "• `¿Qué gasté hoy?` — Transacciones de hoy\n"
            "• `¿Qué hice ayer?` — Transacciones de ayer\n"
            "• `¿Cuánto gasté en julio?` — Análisis mensual\n"
            "• `¿Qué gasté esta semana?` — Resumen semanal\n"
            "• `¿Cuánto gasté en comida?` — Gastos por categoría\n"
            "• `¿Cuánto ingresé?` — Ver ingresos\n"
            "• `Del 1 al 10 de julio` — Rango de fechas\n"
            "• `¿Cómo va mi presupuesto?` — Ver presupuestos"
        )

    if tiene_config:
        return (
            f"⚙️ {nombre}, veo que quieres **configurar** algo.\n\n"
            "¿Qué necesitas?\n"
            "• `Mi presupuesto para comida es $500 este mes`\n"
            "• `Quiero ahorrar $2000 para vacaciones`\n"
            "• `Crear categoría: Suscripciones`\n"
            "• `Mi meta de ahorro es $5000 para diciembre`"
        )

    if tiene_mod:
        return (
            f"✏️ {nombre}, parece que quieres **modificar** algo.\n\n"
            "¿Qué necesitas cambiar?\n"
            "• `Cambiar el monto de mi último gasto a $75`\n"
            "• `Eliminar mi último gasto`\n"
            "• `Cambiar la categoría de mi último ingreso a bonus`\n"
            "• `Editar mi último gasto: descripción a uber`"
        )

    if tiene_accion and tiene_numero:
        # Intentó registrar algo pero no se entendió
        return (
            f"💡 {nombre}, veo que mencionás un **monto** pero no pude procesar tu registro.\n\n"
            "¿Podés intentar con este formato?\n"
            "• `Gasté $50 en comida` —Registrar un gasto\n"
            "• `Recibí $300 de salario` — Registrar un ingreso\n"
            "• `Pagué $20 de transporte` — Registrar un pago\n"
            "• `$100 en supermercado` — Formato corto\n\n"
            "También puedes incluir la fecha:\n"
            "• `Gasté $50 en comida ayer`\n"
            "• `Recibí $300 el lunes`"
        )

    if tiene_accion and not tiene_numero:
        return (
            f"💡 {nombre}, mencionás una **acción financiera** pero no veo un monto.\n\n"
            "Para registrar necesito el monto:\n"
            "• `Gasté $50 en comida`\n"
            "• `Recibí $300 de salario`\n"
            "• `$100 de uber`"
        )

    if tiene_numero and not tiene_accion:
        return (
            f"💡 {nombre}, veo un **monto** pero no sé qué hacer con él.\n\n"
            "¿Querés registrarlo?\n"
            "• `Gasté ${re.search(r'\\d+', msg).group()} en comida`\n"
            "• `Recibí ${re.search(r'\\d+', msg).group()} de salario`\n\n"
            "¿O es parte de una consulta?\n"
            "• `¿Cuánto gasté en ${re.search(r'\\d+', msg).group()}?`"
        )

    # --- RESPUESTA GENÉRICA CON EJEMPLOS ---
    return (
        f"🤔 {nombre}, no estoy seguro de qué quieres hacer con: \"{mensaje}\"\n\n"
        "¿Podés decirme algo como?\n\n"
        "💸 **Registrar:**\n"
        "• `Gasté $50 en comida`\n"
        "• `Recibí $300 de salario`\n"
        "• `$20 en transporte`\n\n"
        "📊 **Consultar:**\n"
        "• `¿Cuánto tengo?`\n"
        "• `¿Qué gasté hoy?`\n"
        "• `¿Cuánto gasté en comida?`\n\n"
        "⚙️ **Configurar:**\n"
        "• `Mi presupuesto es $500 para comida`\n"
        "• `Quiero ahorrar $2000`\n\n"
        "✏️ **Modificar:**\n"
        "• `Cambiar mi último gasto a $75`\n"
        "• `Eliminar mi último gasto`\n\n"
        "¿Qué necesitas? 😊"
    )

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
        return "❌ No encontré la transacción que quieres eliminar. ¿Podés especificar cuál?"

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


# ============================================================
# ANÁLISIS DE TRANSACCIONES POR FECHA
# ============================================================

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _parsear_fecha_natural(mensaje: str):
    """
    Parsea referencias de fecha en lenguaje natural.
    Retorna (fecha_inicio, fecha_fin, etiqueta) o None.
    Las fechas son strings 'YYYY-MM-DD'.
    """
    from datetime import date, timedelta

    msg = mensaje.lower().strip()
    hoy = date.today()

    # --- Días relativos ---
    if re.search(r'\bhoy\b', msg):
        f = hoy.isoformat()
        return f, f, "hoy"

    if re.search(r'\bayer\b', msg):
        f = (hoy - timedelta(days=1)).isoformat()
        return f, f, "ayer"

    if re.search(r'\banteayer\b', msg):
        f = (hoy - timedelta(days=2)).isoformat()
        return f, f, "anteayer"

    # "el lunes", "el martes", etc.
    dias_semana = {
        "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
        "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6,
    }
    for dia_nombre, dia_num in dias_semana.items():
        match = re.search(r'\b(el\s+)?' + dia_nombre + r'\b', msg)
        if match:
            dias_atras = (hoy.weekday() - dia_num) % 7
            if dias_atras == 0:
                dias_atras = 7
            fecha = hoy - timedelta(days=dias_atras)
            f = fecha.isoformat()
            return f, f, f"el {dia_nombre}"

    # --- Semanas ---
    if re.search(r'\besta\s+semana\b', msg):
        inicio = hoy - timedelta(days=hoy.weekday())
        return inicio.isoformat(), hoy.isoformat(), "esta semana"

    if re.search(r'\bsemana\s+pasada\b', msg):
        fin = hoy - timedelta(days=hoy.weekday() + 1)
        inicio = fin - timedelta(days=6)
        return inicio.isoformat(), fin.isoformat(), "la semana pasada"

    # --- Meses ---
    if re.search(r'\beste\s+mes\b', msg):
        inicio = hoy.replace(day=1)
        return inicio.isoformat(), hoy.isoformat(), "este mes"

    if re.search(r'\bmes\s+pasado\b', msg):
        primeroeste = hoy.replace(day=1)
        fin = primeroeste - timedelta(days=1)
        inicio = fin.replace(day=1)
        return inicio.isoformat(), fin.isoformat(), "el mes pasado"

    # --- Rangos (PRIMERO que días específicos) ---
    # "del 1 al 10 de julio"
    match = re.search(r'del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+(\w+)', msg)
    if match:
        dia_inicio = int(match.group(1))
        dia_fin = int(match.group(2))
        mes_nombre = match.group(3)
        mes_num = MESES_ES.get(mes_nombre)
        if mes_num:
            anio = hoy.year
            try:
                inicio = date(anio, mes_num, dia_inicio)
                fin = date(anio, mes_num, dia_fin)
                return inicio.isoformat(), fin.isoformat(), f"del {dia_inicio} al {dia_fin} de {mes_nombre}"
            except ValueError:
                pass

    # --- Días específicos ---
    # "el 15 de julio", "15 de julio 2026"
    match = re.search(
        r'(?:el\s+)?(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(?:\s+(\d{4}))?',
        msg
    )
    if match:
        dia = int(match.group(1))
        mes_num = MESES_ES[match.group(2)]
        anio = int(match.group(3)) if match.group(3) else hoy.year
        try:
            fecha = date(anio, mes_num, dia)
            f = fecha.isoformat()
            return f, f, f"{dia} de {match.group(2)} {anio}"
        except ValueError:
            pass

    # "15/07/2026" o "15-07-2026" o "15/07"
    match = re.search(r'(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?', msg)
    if match:
        dia = int(match.group(1))
        mes = int(match.group(2))
        anio = int(match.group(3)) if match.group(3) else hoy.year
        if anio < 100:
            anio += 2000
        try:
            fecha = date(anio, mes, dia)
            f = fecha.isoformat()
            return f, f, f"{dia}/{mes:02d}/{anio}"
        except ValueError:
            pass

    # --- Mes genérico (DESPUÉS de todo lo anterior) ---
    # "en julio", "de julio", "julio 2026", "mes de julio"
    for mes_nombre, mes_num in MESES_ES.items():
        match = re.search(r'(?:en|de|mes\s+de\s+|el\s+mes\s+de\s+)' + mes_nombre + r'(?:\s+(\d{4}))?', msg)
        if match:
            anio = int(match.group(1)) if match.group(1) else hoy.year
            inicio = date(anio, mes_num, 1)
            if mes_num == 12:
                fin = date(anio + 1, 1, 1) - timedelta(days=1)
            else:
                fin = date(anio, mes_num + 1, 1) - timedelta(days=1)
            if inicio > hoy:
                inicio = hoy
            if fin > hoy:
                fin = hoy
            return inicio.isoformat(), fin.isoformat(), f"{mes_nombre} {anio}"

    # Solo nombre de mes: "julio", "junio"
    for mes_nombre, mes_num in MESES_ES.items():
        if re.search(r'\b' + mes_nombre + r'\b', msg):
            anio = hoy.year
            inicio = date(anio, mes_num, 1)
            if mes_num == 12:
                fin = date(anio + 1, 1, 1) - timedelta(days=1)
            else:
                fin = date(anio, mes_num + 1, 1) - timedelta(days=1)
            if inicio > hoy:
                inicio = hoy
            if fin > hoy:
                fin = hoy
            return inicio.isoformat(), fin.isoformat(), mes_nombre

    # --- Rangos adicionales ---

    # "últimos N días"
    match = re.search(r'(?:últimos?|ultimos?)\s+(\d+)\s+días?', msg)
    if match:
        dias = int(match.group(1))
        inicio = hoy - timedelta(days=dias)
        return inicio.isoformat(), hoy.isoformat(), f"últimos {dias} días"

    # "desde el lunes"
    for dia_nombre, dia_num in dias_semana.items():
        match = re.search(r'desde\s+(?:el\s+)?' + dia_nombre, msg)
        if match:
            dias_atras = (hoy.weekday() - dia_num) % 7
            fecha = hoy - timedelta(days=dias_atras)
            return fecha.isoformat(), hoy.isoformat(), f"desde el {dia_nombre}"

    return None


def _analizar_transacciones_por_fecha(usuario: Dict[str, Any], mensaje: str) -> str:
    """
    Analiza y formatea las transacciones de un usuario para un rango de fecha dado.
    Retorna un string con el desglose formateado, o None si no detecta fecha.
    """
    resultado = _parsear_fecha_natural(mensaje)
    if not resultado:
        return None

    fecha_inicio, fecha_fin, etiqueta = resultado

    transacciones = database.obtener_transacciones_por_fecha(
        usuario["id"], fecha_inicio, fecha_fin
    )

    if not transacciones:
        return (
            f"📅 **{etiqueta.capitalize()}:**\n\n"
            f"No tienes transacciones registradas para {etiqueta}.\n\n"
            "¿Querés registrar algo? Por ejemplo:\n"
            "• `Gasté $50 en comida`\n"
            "• `Recibí $300 de salario`"
        )

    gastos = [t for t in transacciones if t["tipo"] == "gasto"]
    ingresos = [t for t in transacciones if t["tipo"] == "ingreso"]

    total_gastos = sum(t["cantidad"] for t in gastos)
    total_ingresos = sum(t["cantidad"] for t in ingresos)
    neto = total_ingresos - total_gastos

    # Desglose por categoría
    por_categoria = {}
    for t in gastos:
        cat = t.get("categoria_nombre", "otros") or "otros"
        if cat not in por_categoria:
            por_categoria[cat] = {"total": 0, "cantidad": 0, "transacciones": []}
        por_categoria[cat]["total"] += t["cantidad"]
        por_categoria[cat]["cantidad"] += 1
        por_categoria[cat]["transacciones"].append(t)

    lineas = [f"📅 **Análisis: {etiqueta}**", "━━━━━━━━━━━━━━━━━"]

    # Resumen general
    lineas.append("")
    lineas.append(f"💰 **Ingresos:** ${total_ingresos:.2f} ({len(ingresos)} transacciones)")
    lineas.append(f"💸 **Gastos:** ${total_gastos:.2f} ({len(gastos)} transacciones)")
    lineas.append(f"💵 **Neto:** ${neto:.2f}")
    lineas.append(f"📊 **Total transacciones:** {len(transacciones)}")

    # Desglose de gastos por categoría
    if por_categoria:
        lineas.append("")
        lineas.append("📂 **Gastos por categoría:**")
        for cat, datos in sorted(por_categoria.items(), key=lambda x: x[1]["total"], reverse=True):
            porcentaje = (datos["total"] / total_gastos * 100) if total_gastos > 0 else 0
            barra = _crear_barra_progreso(porcentaje)
            lineas.append(f"  • {cat}: ${datos['total']:.2f} ({datos['cantidad']}x) {barra} {porcentaje:.0f}%")

    # Detalle de gastos
    if gastos:
        lineas.append("")
        lineas.append("💸 **Detalle de gastos:**")
        for t in gastos:
            fecha = str(t.get("fecha", ""))[:10]
            desc = t.get("descripcion", "Sin descripción")
            cat = t.get("categoria_nombre", "")
            cat_str = f" ({cat})" if cat else ""
            lineas.append(f"  📉 ${t['cantidad']:.2f} - {desc}{cat_str} [{fecha}]")

    # Detalle de ingresos
    if ingresos:
        lineas.append("")
        lineas.append("💰 **Detalle de ingresos:**")
        for t in ingresos:
            fecha = str(t.get("fecha", ""))[:10]
            desc = t.get("descripcion", "Sin descripción")
            cat = t.get("categoria_nombre", "")
            cat_str = f" ({cat})" if cat else ""
            lineas.append(f"  📈 ${t['cantidad']:.2f} - {desc}{cat_str} [{fecha}]")

    # Promedio diario si es rango de varios días
    try:
        from datetime import date as _date
        d_inicio = _date.fromisoformat(fecha_inicio)
        d_fin = _date.fromisoformat(fecha_fin)
        dias = (d_fin - d_inicio).days + 1
        if dias > 1:
            lineas.append("")
            lineas.append(f"📊 **Promedio diario ({dias} días):**")
            lineas.append(f"  💸 Gasto promedio: ${total_gastos / dias:.2f}/día")
            lineas.append(f"  💰 Ingreso promedio: ${total_ingresos / dias:.2f}/día")
    except Exception:
        pass

    return "\n".join(lineas)


def _crear_barra_progreso(porcentaje: float, largo: int = 8) -> str:
    """Crea una barra de progreso visual."""
    llenos = int(porcentaje / 100 * largo)
    vacios = largo - llenos
    return "█" * llenos + "░" * vacios