"""
handlers.py - Handlers para el bot de finanzas personales
Maneja comandos y mensajes en lenguaje natural para gestión financiera.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database
import knowledge
import ai_client
from config import IMAGES_DIR

logger = logging.getLogger(__name__)

# === PALABRAS CLAVE PARA FINANZAS ===

REGISTRAR_KEYWORDS = [
    "gasté", "gaste", "compré", "compre", "pagué", "pague",
    "recibí", "recibi", "ingresé", "ingrese", "transferir",
    "registrar", "registra", "agregar", "añadir", "guardar",
    "compra", "pago", "cost", "salario", "bonifica",
    "remuner", "pension", "pollo", "alquile", "rent", "hipoteca",
]

PRESUPUESTO_KEYWORDS = [
    "presupuesto", "budget", "planear", "planificar", "limit", "limite",
    "fijar", "establecer", "asignar", "monto",
]

AHORRO_KEYWORDS = [
    "ahorrar", "ahorro", "meta", "objetivo", "guardar dinero",
    "invertir", "inversión", "guardar",
]

CONSULTAR_KEYWORDS = [
    "consultar", "ver", "balance", "saldo", "resumen", "estado",
    "listar", "mostrar", "mostrarme", "muestra", "muestrame",
    "dame", "historial",
]

CATEGORIA_KEYWORDS = [
    "categoria", "categoría", "tipo", "tipo de", "clase",
]

MODIFICAR_KEYWORDS = [
    "modificar", "modifica", "cambiar", "cambia", "editar", "edita",
    "actualizar", "actualiza", "corregir", "corrije", "rectificar",
    "mover", "mueve", "pasar", "pasa", "convertir", "convierte",
]

ELIMINAR_KEYWORDS = [
    "eliminar", "elimina", "borrar", "borra", "quitar", "quita",
    "remover", "remueve", "suprimir", "suprime", "delet",
]

# === NÚMEROS EN TEXTO ===

NUMEROS = {
    "un": 1, "una": 1, "uno": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "veinte": 20, "treinta": 30,
}

# Palabras de relleno para limpiar búsquedas
PALABRAS_RELLENO = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "al", "con", "por", "para", "que",
    "y", "o", "ni", "pero", "también", "tambien",
    "porfa", "por favor", "please", "gracias",
    "me", "te", "le", "nos", "se",
    "quiero", "necesito", "dame", "ponme", "poner",
    "llevar", "llevo", "comprar", "pedir",
    "así", "asi", "nomás", "no mas",
    "rapido", "rápido", "ya", "ahora",
    "más", "mas", "extra", "adicional",
    "también", "tambien", "además", "ademas",
}


def _limpiar_palabra(palabra: str) -> str:
    """Elimina tildes y caracteres especiales."""
    palabra = palabra.replace("á", "a").replace("é", "e").replace("í", "i")
    palabra = palabra.replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    return palabra


def _extraer_numero_y_limpiar(texto: str) -> tuple[float, str]:
    """
    Extrae un número del texto y retorna (número, texto_limpio_sin_número).
    Ejemplos:
        "$50 " → (50.0, "")
        "50 USD " → (50.0, "USD ")
        "quinientos " → (500.0, "")
    """
    texto_original = texto

    # Limpiar símbolos de moneda
    texto_limpio = re.sub(r'[\$\€\£\¥\¢]', '', texto)
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()

    # Buscar número escrito
    for word, num in NUMEROS.items():
        if re.search(rf'\b{word}\b', texto_limpio):
            limpio = re.sub(rf'\b{word}\b', '', texto_limpio).strip()
            limpio = re.sub(r'\s+', ' ', limpio).strip()
            try:
                return float(num), limpio
            except ValueError:
                pass

    # Buscar número digitado (incluir decimales)
    match = re.search(r'(\d+(?:\.\d+)?)', texto_limpio)
    if match:
        num = float(match.group(1))
        limpio = texto_limpio[match.end():].strip()
        return num, limpio

    return 0.0, texto_limpio


def _extraer_fecha(texto: str) -> Optional[str]:
    """Intenta extraer una fecha del texto."""
    textos_fecha = {
        "hoy": datetime.now().strftime("%Y-%m-%d"),
        "ayer": (datetime.now().replace(day=1)).strftime("%Y-%m-%d"),  # Simplificado
        "este mes": datetime.now().strftime("%Y-%m-%d"),
        "este mes": datetime.now().strftime("%Y-%m-%d"),
    }

    for key, fecha in textos_fecha.items():
        if key in texto.lower():
            return fecha

    return None


def _detectar_intencion(texto: str) -> str:
    """Detecta la intencion del mensaje en el contexto financiero."""
    texto_lower = texto.lower().strip()
    es_consulta = any(kw in texto_lower for kw in CONSULTAR_KEYWORDS)
    es_registro = any(kw in texto_lower for kw in REGISTRAR_KEYWORDS)
    es_modificacion = any(kw in texto_lower for kw in MODIFICAR_KEYWORDS)
    es_eliminacion = any(kw in texto_lower for kw in ELIMINAR_KEYWORDS)

    # Detectar eliminación de transacción específica
    if es_eliminacion:
        if any(w in texto_lower for w in ["transacción", "transaccion", "gasto", "ingreso", "registro", "movimiento"]):
            return "eliminar_transaccion"

    # Detectar modificación de transacción
    if es_modificacion:
        if any(w in texto_lower for w in ["transacción", "transaccion", "gasto", "ingreso", "registro", "movimiento"]):
            return "modificar_transaccion"
        if any(w in texto_lower for w in ["a ingreso", "a gasto", "tipo", "categoría", "categoria", "monto", "cantidad", "descripción", "descripcion", "fecha"]):
            return "modificar_transaccion"

    # Detectar análisis por fecha (prioridad alta)
    FECHA_KEYWORDS = [
        "hoy", "ayer", "anteayer", "esta semana", "semana pasada",
        "este mes", "mes pasado", "últimos", "ultimos", "desde",
    ]
    MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    es_fecha = any(kw in texto_lower for kw in FECHA_KEYWORDS)
    es_fecha = es_fecha or any(m in texto_lower for m in MESES)
    es_fecha = es_fecha or bool(re.search(r'\b(el\s+)?(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)\b', texto_lower))
    es_fecha = es_fecha or bool(re.search(r'\d{1,2}[/\-]\d{1,2}', texto_lower))
    es_fecha = es_fecha or bool(re.search(r'del\s+\d{1,2}\s+al\s+\d{1,2}', texto_lower))

    if es_fecha and (es_consulta or es_registro or es_fecha):
        # Verificar que hay indicio de consulta (no solo "ayer" aislado sin contexto financiero)
        tiene_contexto_financiero = es_consulta or any(w in texto_lower for w in [
            "gasto", "gastos", "ingreso", "ingresos", "transacci", "movimient",
            "cuánto", "cuanto", "qué", "que", "cuales", "cuáles", "dónde", "donde",
            "comí", "comi", "gasté", "gaste", "recibí", "recibi", "pagué", "pague",
            "compr", "cobr", "gananc", "balance", "resumen", "historial",
        ])
        if tiene_contexto_financiero:
            return "analizar_por_fecha"

    if es_consulta or "como" in texto_lower or "cual" in texto_lower:
        if any(w in texto_lower for w in ["balance", "saldo", "resumen"]):
            return "consultar_balance"
        if any(w in texto_lower for w in ["categoria", "categoria"]):
            return "consultar_categorias"
        if any(w in texto_lower for w in ["presupuesto", "presupuestos", "budget"]):
            return "consultar_presupuesto"
        if any(w in texto_lower for w in ["ahorro", "ahorros", "meta de ahorro"]):
            return "consultar_ahorro"
        if "gasto" in texto_lower or "gastos" in texto_lower:
            if not es_registro:
                return "consultar_gastos"
        if "ingreso" in texto_lower or "ingresos" in texto_lower:
            if not es_registro:
                return "consultar_ingresos"
        if any(w in texto_lower for w in ["transacci", "historial", "movimient", "operacion", "registro"]):
            return "consultar_transacciones"

    if any(kw in texto_lower for kw in PRESUPUESTO_KEYWORDS):
        return "configurar_presupuesto"

    if any(kw in texto_lower for kw in AHORRO_KEYWORDS):
        return "configurar_ahorro"

    if es_registro:
        return "registrar_transaccion"

    if "hola" in texto_lower or "start" in texto_lower:
        return "start"

    return "general"


def _parsear_transaccion(texto: str) -> tuple[Optional[str], Optional[float], Optional[str], Optional[str]]:
    """
    Parsea un texto de transacción financiera.
    Retorna (categoria_tipo, cantidad, descripcion, fecha).
    """
    texto_lower = texto.lower().strip()

    # Identificar tipo por palabras clave
    tipo = None
    if any(kw in texto_lower for kw in ["gast", "compra", "pago", "cost"]):
        tipo = "gasto"
    elif any(kw in texto_lower for kw in ["ingress", "salario", "ingreso", "recib"]):
        tipo = "ingreso"

    # Extraer cantidad
    from knowledge import _parsear_cantidad
    cantidad = _parsear_cantidad(texto_lower)

    # Extraer descripción (texto después del número)
    descripcion = ""
    if cantidad:
        # Buscar el número original en el texto para extraer la descripción después
        patron_num = re.search(r'\d+(?:[.,]\d+)?', texto_lower)
        if patron_num:
            descripcion = texto_lower[patron_num.end():].strip()
        else:
            descripcion = texto_lower
    else:
        descripcion = texto_lower

    # Limpiar descripción
    if descripcion:
        palabras = descripcion.split()
        descripcion_limpia = [p for p in palabras if p not in PALABRAS_RELLENO and len(p) > 2]
        descripcion = " ".join(descripcion_limpia)

    # Determinar categoria_tipo (gastos/ingresos/ahorros/inversiones)
    categoria_tipo = None
    if any(kw in descripcion for kw in ["comida", "supermercado", "restaurant", "desayuno", "almuerzo", "cena"]):
        categoria_tipo = "gastos"
    elif any(kw in descripcion for kw in ["salario", "remuneración", "pago", "bonus", "bonificación"]):
        categoria_tipo = "ingresos"
    elif any(kw in descripcion for kw in ["ahorro", "meta", "objetivo"]):
        categoria_tipo = "ahorros"
    elif any(kw in descripcion for kw in ["inversión", "inversion", "acciones", "bitcoin", "crypto"]):
        categoria_tipo = "inversiones"
    else:
        if tipo == "gasto":
            categoria_tipo = "gastos"
        elif tipo == "ingreso":
            categoria_tipo = "ingresos"

    # Extraer fecha
    fecha = _extraer_fecha(texto_lower)

    return categoria_tipo, cantidad, descripcion, fecha


def _crear_botones_rapidos() -> InlineKeyboardMarkup:
    """Crea el teclado inline con botones de acciones rápidas."""
    botones = [
        [
            InlineKeyboardButton("💰 Consultar balance", callback_data="accion_balance"),
            InlineKeyboardButton("📋 Ver transacciones", callback_data="accion_transacciones"),
        ],
    ]
    return InlineKeyboardMarkup(botones)


def _crear_botones_multi_transacciones(cantidad: int) -> InlineKeyboardMarkup:
    """Crea botones de confirmación para múltiples transacciones."""
    botones = [
        [
            InlineKeyboardButton("✅ Guardar todo", callback_data="multi_confirm"),
            InlineKeyboardButton("❌ Cancelar", callback_data="multi_cancel"),
        ],
    ]
    for i in range(cantidad):
        botones.append([
            InlineKeyboardButton(f"✏️ Editar #{i+1}", callback_data=f"multi_edit_{i}"),
            InlineKeyboardButton(f"🗑️ Quitar #{i+1}", callback_data=f"multi_remove_{i}"),
        ])
    return InlineKeyboardMarkup(botones)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones inline."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    usuario = database.obtener_usuario(user.id)
    if not usuario:
        usuario = database.obtener_o_crear_usuario(user.id, user.first_name)
    usuario_id = usuario["id"]

    botones = _crear_botones_rapidos()

    if query.data == "accion_balance":
        balance = database.obtener_balance(usuario_id)
        mensaje = (
            f"💰 **Tu balance actual:**\n\n"
            f"  📈 Ingresos: ${balance['ingresos']:.2f}\n"
            f"  📉 Gastos: ${balance['gastos']:.2f}\n"
            f"  💵 Neto: ${balance['neto']:.2f}"
        )
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=mensaje,
            parse_mode="Markdown",
            reply_markup=botones,
        )

    elif query.data == "accion_transacciones":
        transacciones = database.obtener_transacciones(usuario_id, 5)
        if not transacciones:
            mensaje = "📝 No tienes transacciones registradas aún."
        else:
            mensaje = "📝 **Tus últimas transacciones:**\n\n"
            for t in transacciones:
                tipo_icono = "📈" if t["tipo"] == "ingreso" else "📉"
                tipo_label = "Ingreso" if t["tipo"] == "ingreso" else "Gasto"
                fecha = t.get("fecha", "N/A")[:10]
                desc = t.get("descripcion", "Sin descripción")
                if desc.lower().startswith("gasto: "):
                    desc = desc[7:].strip()
                elif desc.lower().startswith("ingreso: "):
                    desc = desc[9:].strip()
                for pv in ["gasté ", "gaste ", "recibí ", "recibi ", "compré ", "compre ", "pagué ", "pague "]:
                    if desc.lower().startswith(pv):
                        desc = desc[len(pv):].strip()
                        break
                mensaje += f"{tipo_icono} ${t['cantidad']:.2f} - {tipo_label}: {desc} ({fecha})\n"
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=mensaje,
            parse_mode="Markdown",
            reply_markup=botones,
        )

    # === CALLBACKS DE MÚLTIPLES TRANSACCIONES ===
    elif query.data == "multi_confirm":
        transacciones_pendientes = context.user_data.get("multi_transacciones", [])
        if not transacciones_pendientes:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⚠️ No hay transacciones pendientes para guardar.",
            )
            return
        resultado = knowledge._guardar_multi_transacciones(transacciones_pendientes, usuario)
        context.user_data.pop("multi_transacciones", None)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=resultado,
            parse_mode="Markdown",
            reply_markup=botones,
        )

    elif query.data == "multi_cancel":
        context.user_data.pop("multi_transacciones", None)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Transacciones canceladas. No se guardó nada.",
            reply_markup=botones,
        )

    elif query.data.startswith("multi_remove_"):
        idx = int(query.data.split("_")[-1])
        transacciones_pendientes = context.user_data.get("multi_transacciones", [])
        if 0 <= idx < len(transacciones_pendientes):
            eliminada = transacciones_pendientes.pop(idx)
            context.user_data["multi_transacciones"] = transacciones_pendientes

            if not transacciones_pendientes:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="❌ No quedan transacciones. Proceso cancelado.",
                    reply_markup=botones,
                )
                return

            # Regenerar preview
            preview = knowledge._formatear_preview_transacciones(transacciones_pendientes)
            botones_multi = _crear_botones_multi_transacciones(len(transacciones_pendientes))
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"🗑️ Eliminada: ${eliminada['cantidad']:.2f} - {eliminada.get('descripcion', '')}\n\n{preview}",
                parse_mode="Markdown",
                reply_markup=botones_multi,
            )

    elif query.data.startswith("multi_edit_"):
        idx = int(query.data.split("_")[-1])
        transacciones_pendientes = context.user_data.get("multi_transacciones", [])
        if 0 <= idx < len(transacciones_pendientes):
            t = transacciones_pendientes[idx]
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"✏️ **Editando transacción {idx+1}:**\n"
                    f"{'📈' if t['tipo'] == 'ingreso' else '📉'} ${t['cantidad']:.2f} - {t.get('descripcion', '')}\n\n"
                    f"Envíame la transacción corregida, por ejemplo:\n"
                    f"• `$50 en comida`\n"
                    f"• `Recibí $200 de salario`\n\n"
                    f"La reemplazaré en la lista."
                ),
                parse_mode="Markdown",
            )
            context.user_data["editando_multi_idx"] = idx


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start."""
    user = update.effective_user
    nombre = user.first_name if user.first_name else "amigo"

    context.user_data["telegram_user_id"] = user.id
    usuario = database.obtener_o_crear_usuario(user.id, nombre)
    context.user_data["usuario_id"] = usuario["id"]

    estadisticas = database.contar_transacciones(usuario["id"])

    mensaje = (
        f"¡Hola {nombre}! 👋 Soy **FinanzasBot**, tu asistente financiero personal.\n\n"
        f"📊 Tengo **{estadisticas.get('total', 0)} transacciones** registradas:\n"
        f"  💸 Gastos: {estadisticas.get('gastos', 0)}\n"
        f"  💰 Ingresos: {estadisticas.get('ingresos', 0)}\n\n"
        f"🏦 *Qué puedo ayudarte hoy:*\n"
        f"• Registrar un gasto o ingreso (ej: \"Gasté $50 en comida para el desayuno\")\n"
        f"• Configurar presupuestos por categoría\n"
        f"• Hacer un seguimiento de metas de ahorro e inversión\n"
        f"• Consultar tu balance y transacciones recientes\n"
        f"• Ver tus categorías financieras\n"
    )

    botones = _crear_botones_rapidos()
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=botones)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto en lenguaje natural."""
    user = update.effective_user
    mensaje = update.message.text

    if "usuario_id" not in context.user_data:
        context.user_data["telegram_user_id"] = user.id
        context.user_data["usuario_id"] = database.obtener_o_crear_usuario(user.id, user.first_name)["id"]

    usuario_id = context.user_data["usuario_id"]
    usuario = database.obtener_usuario(user.id) or {"id": usuario_id, "nombre": user.first_name}

    # Verificar si el usuario está editando una transacción multi
    if "editando_multi_idx" in context.user_data:
        idx = context.user_data.pop("editando_multi_idx")
        transacciones_pendientes = context.user_data.get("multi_transacciones", [])
        if 0 <= idx < len(transacciones_pendientes):
            original = transacciones_pendientes[idx]
            tipo_original = original.get("tipo", "gasto")
            # Parsear la nueva transacción
            nueva = knowledge._parsear_multi_transaccion(mensaje)
            if nueva:
                # Preservar el tipo de la transacción original
                nueva[0]["tipo"] = tipo_original
                transacciones_pendientes[idx] = nueva[0]
                context.user_data["multi_transacciones"] = transacciones_pendientes
                preview = knowledge._formatear_preview_transacciones(transacciones_pendientes)
                botones_multi = _crear_botones_multi_transacciones(len(transacciones_pendientes))
                await update.message.reply_text(
                    f"✅ Transacción #{idx+1} actualizada.\n\n{preview}",
                    parse_mode="Markdown",
                    reply_markup=botones_multi,
                )
                return
            else:
                await update.message.reply_text(
                    "❌ No pude entender la transacción. Intenta de nuevo con un formato como:\n"
                    "`$50 en comida`\n`Recibí $200 de salario`",
                    parse_mode="Markdown",
                )
                return

    # Detectar múltiples transacciones en lenguaje natural
    if knowledge._esensaje_multi_transaccion(mensaje):
        transacciones = knowledge._parsear_multi_transaccion(mensaje)
        if len(transacciones) >= 2:
            context.user_data["multi_transacciones"] = transacciones
            preview = knowledge._formatear_preview_transacciones(transacciones)
            botones_multi = _crear_botones_multi_transacciones(len(transacciones))
            await update.message.reply_text(
                preview,
                parse_mode="Markdown",
                reply_markup=botones_multi,
            )
            return

    # Flujo normal: una sola transacción o consulta
    respuesta = await ai_client.AIResponder().responder(mensaje, usuario)
    botones = _crear_botones_rapidos()
    await update.message.reply_text(respuesta, parse_mode="Markdown", reply_markup=botones)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja errores del bot."""
    logger.error("Error en update %s: %s", update, context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Lo siento, ocurrió un error inesperado. Por favor intenta de nuevo."
        )


async def consultar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /user."""
    user = update.effective_user
    usuario_id = context.user_data.get("usuario_id")
    if not usuario_id:
        context.user_data["telegram_user_id"] = user.id
        context.user_data["usuario_id"] = database.obtener_o_crear_usuario(user.id, user.first_name)["id"]
        usuario_id = context.user_data["usuario_id"]

    balance = database.obtener_balance(usuario_id)
    transacciones = database.obtener_transacciones(usuario_id, 5)
    categorias = database.obtener_categorias(usuario_id)

    mensaje = (
        f"👤 **Usuario:** {user.first_name}\n"
        f"🆔 **ID:** `{user.id}`\n\n"
        f"💰 **Balance:**\n"
        f"  Ingresos: ${balance['ingresos']:.2f}\n"
        f"  Gastos: ${balance['gastos']:.2f}\n"
        f"  Neto: ${balance['neto']:.2f}\n\n"
        f"📁 **Categorías:** {len(categorias)}\n"
        f"📝 **Transacciones recientes:** {len(transacciones)}"
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def consultar_comandos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /help."""
    mensaje = (
        "🤖 **Comandos disponibles:**\n\n"
        "• `/start` - Iniciar/Reiniciar el bot\n"
        "• `/user` - Ver información de usuario\n"
        "• `/help` - Ver esta ayuda\n"
        "• `/delete` - Borrar todo el historial de transacciones\n\n"
        "📝 **Ejemplos de lenguaje natural:**\n"
        "• 'Gasté $50 en comida para el desayuno'\n"
        "• 'Recibí $2000 de salario'\n"
        "• 'Mi presupuesto para comida es $500 este mes'\n"
        "• 'Quiero ahorrar $5000 para unas vacaciones'\n"
        "• '¿Cuál es mi balance actual?'\n\n"
        "✏️ **Modificar datos:**\n"
        "• 'Cambia el gasto de $50 a ingreso'\n"
        "• 'Modifica la descripción de mi último gasto'\n"
        "• 'Cambia el monto de $100 a $150'\n"
        "• 'Elimina la transacción de $30'\n"
        "• 'Pasa ese gasto a la categoría transporte'"
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def eliminar_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /delete para borrar todo el historial."""
    user = update.effective_user

    if "usuario_id" not in context.user_data:
        context.user_data["telegram_user_id"] = user.id
        context.user_data["usuario_id"] = database.obtener_o_crear_usuario(user.id, user.first_name)["id"]

    usuario_id = context.user_data["usuario_id"]
    eliminadas = database.eliminar_transacciones(usuario_id)

    botones = _crear_botones_rapidos()
    mensaje = f"🗑️ **Historial eliminado.** Se borraron **{eliminadas}** transacciones.\n\nTu balance ahora está en $0.00."
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=botones)


async def _procesar_transaccion_finanzas(fecha, tipo, cantidad, descripcion):
    """Procesa una transacción financiera."""
    return f"✅ Transacción registrada: ${cantidad:.2f} en '{descripcion}'"