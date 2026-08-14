"""
handlers.py - Handlers para el bot de finanzas personales
Maneja comandos y mensajes en lenguaje natural para gestión financiera.
"""

import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

import database
import knowledge
import ai_client
import changelog
from config import IMAGES_DIR, ADMIN_USER_ID

logger = logging.getLogger(__name__)

# Textos exactos de los botones del teclado persistente
BTN_BALANCE = "💰 Balance"
BTN_TRANSACCIONES = "📋 Transacciones"
BTN_PRESUPUESTOS = "📊 Presupuestos"
BTN_MONEDAS = "💱 Monedas"
TECLADO_BUTTONS = {BTN_BALANCE, BTN_TRANSACCIONES, BTN_PRESUPUESTOS, BTN_MONEDAS}


def _formatear_notificacion(ultima_vista: Optional[str]) -> Optional[str]:
    """Construye el mensaje de notificación con las versiones no vistas por el usuario."""
    versiones_a_mostrar = []
    for ver, data in changelog.CHANGELOG.items():
        if ultima_vista is None or str(ver) > str(ultima_vista):
            versiones_a_mostrar.append((ver, data))

    if not versiones_a_mostrar:
        return None

    versiones_a_mostrar.sort(key=lambda x: x[0], reverse=True)

    lineas = []
    for ver, data in versiones_a_mostrar:
        emoji = data.get("emoji", "📢")
        lineas.append(f"{emoji} *v{ver}* - {data['titulo']}")
        for mejora in data.get("mejoras", []):
            lineas.append(f"  • {mejora}")
        lineas.append("")

    lineas.append("Escribí /help para ver todos los comandos.")

    return "\n".join(lineas)


def _crear_teclado_permanente():
    """Crea el teclado persistente con botones de acciones frecuentes."""
    keyboard = [
        [BTN_BALANCE, BTN_TRANSACCIONES],
        [BTN_PRESUPUESTOS, BTN_MONEDAS],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


def _formatear_moneda_para_display(moneda: dict) -> str:
    """Formatea una moneda para mostrar en el menú."""
    default = " ⭐" if moneda.get("es_default") else ""
    return f"{moneda['simbolo']} {moneda['nombre']} ({moneda['abreviatura']}){default}"


def _crear_botones_monedasInlineKeyboard(monedas: list) -> InlineKeyboardMarkup:
    """Crea los InlineKeyboard para el menú de monedas."""
    botones = []
    for m in monedas:
        label = f"{'⭐ ' if m.get('es_default') else ''}{m['nombre']} ({m['abreviatura']})"
        botones.append([InlineKeyboardButton(label, callback_data=f"moneda_info_{m['id']}")])
    botones.append([
        InlineKeyboardButton("➕ Agregar", callback_data="moneda_agregar"),
        InlineKeyboardButton("🗑️ Eliminar", callback_data="monedaeliminar_menu"),
    ])
    botones.append([
        InlineKeyboardButton("⭐ Predeterminada", callback_data="moneda_default_menu"),
])
    return InlineKeyboardMarkup(botones)


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start."""
    try:
        user = update.effective_user
        nombre_mostrar = escape_markdown(user.first_name or "amigo", version=1)

        context.user_data["telegram_user_id"] = user.id
        usuario = database.obtener_o_crear_usuario(user.id, user.first_name or "amigo")
        context.user_data["usuario_id"] = usuario["id"]

        estadisticas = database.contar_transacciones(usuario["id"])

        mensaje = (
            f"¡Hola {nombre_mostrar}! 👋 Soy **FinanzasBot**, tu asistente financiero personal.\n\n"
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

        botones = _crear_teclado_permanente()
        await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=botones)
    except Exception as e:
        logger.error("Error en /start: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error. Intenta de nuevo con /start.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto en lenguaje natural."""
    user = update.effective_user
    # Soportar mensajes normales y mensajes editados
    msg = update.message or update.edited_message
    if not msg or not msg.text:
        return
    mensaje = msg.text

    if "usuario_id" not in context.user_data:
        context.user_data["telegram_user_id"] = user.id
        context.user_data["usuario_id"] = database.obtener_o_crear_usuario(user.id, user.first_name)["id"]

    usuario_id = context.user_data["usuario_id"]
    usuario = database.obtener_usuario(user.id) or {"id": usuario_id, "nombre": user.first_name}

    # --- Notificación de actualización ---
    try:
        ultima_vista = database.obtener_ultima_version_vista(usuario_id)
        if ultima_vista != changelog.VERSION_ACTUAL:
            mensaje_update = _formatear_notificacion(ultima_vista)
            if mensaje_update:
                await msg.reply_text(mensaje_update, parse_mode="Markdown")
            database.registrar_notificacion(usuario_id, changelog.VERSION_ACTUAL)
    except Exception as e:
        logger.error("Error verificando notificación: %s", e)
    # --- Fin notificación ---

    # Verificar si el usuario está editando una transacción multi
    if "editando_multi_idx" in context.user_data:
        idx = context.user_data.pop("editando_multi_idx")
        transacciones_pendientes = context.user_data.get("multi_transacciones", [])
        if 0 <= idx < len(transacciones_pendientes):
            original = transacciones_pendientes[idx]
            tipo_original = original.get("tipo", "gasto")
            # Parsear la nueva transacción
            nueva = knowledge._parsear_multi_transaccion(mensaje, usuario)
            if nueva:
                # Preservar el tipo de la transacción original
                nueva[0]["tipo"] = tipo_original
                transacciones_pendientes[idx] = nueva[0]
                context.user_data["multi_transacciones"] = transacciones_pendientes
                preview = knowledge._formatear_preview_transacciones(transacciones_pendientes)
                botones_multi = _crear_botones_multi_transacciones(len(transacciones_pendientes))
                await msg.reply_text(
                    f"✅ Transacción #{idx+1} actualizada.\n\n{preview}",
                    parse_mode="Markdown",
                    reply_markup=botones_multi,
                )
                return
            else:
                await msg.reply_text(
                    "❌ No pude entender la transacción. Intenta de nuevo con un formato como:\n"
                    "`$50 en comida`\n`Recibí $200 de salario`",
                    parse_mode="Markdown",
                )
                return

    # --- Flujo conversacional: agregar moneda ---
    if context.user_data.get("agregando_moneda_paso"):
        await _manejar_flujo_moneda(update, context, mensaje, usuario)
        return

    # --- Flujo conversacional: eliminar moneda ---
    if context.user_data.get("eliminando_moneda"):
        await _manejar_eliminar_moneda(update, context, mensaje, usuario)
        return

    # --- Flujo conversacional: moneda default ---
    if context.user_data.get("cambiando_default_moneda"):
        await _manejar_cambiar_default(update, context, mensaje, usuario)
        return

    # --- Manejo de botones del teclado persistente ---
    if mensaje in TECLADO_BUTTONS:
        await _manejar_boton_teclado(update, context, mensaje, usuario)
        return

    # Detectar múltiples transacciones en lenguaje natural
    if knowledge._esensaje_multi_transaccion(mensaje):
        transacciones = knowledge._parsear_multi_transaccion(mensaje, usuario)
        if len(transacciones) >= 2:
            context.user_data["multi_transacciones"] = transacciones
            preview = knowledge._formatear_preview_transacciones(transacciones)
            botones_multi = _crear_botones_multi_transacciones(len(transacciones))
            await msg.reply_text(
                preview,
                parse_mode="Markdown",
                reply_markup=botones_multi,
            )
            return

    # Flujo normal: una sola transacción o consulta
    try:
        respuesta = await ai_client.AIResponder().responder(mensaje, usuario)
        botones = _crear_teclado_permanente()
        await msg.reply_text(respuesta, parse_mode="Markdown", reply_markup=botones)
    except Exception as e:
        logger.error("Error procesando mensaje de %s: %s", user.first_name, e)
        botones = _crear_teclado_permanente()
        await msg.reply_text(
            "⚠️ Ups, algo salió mal al procesar tu mensaje.\n\n"
            "Intenta con estos comandos:\n"
            "• `Gasté $50 en comida`\n"
            "• `¿Cuánto tengo?`\n"
            "• `¿Qué gasté hoy?`\n\n"
            "Si el problema persiste, escribe `/help`.",
            parse_mode="Markdown",
            reply_markup=botones,
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja errores del bot."""
    logger.error("Error en update %s: %s", update, context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Lo siento, ocurrió un error inesperado. Por favor intenta de nuevo."
        )


async def consultar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /user."""
    try:
        user = update.effective_user
        usuario_id = context.user_data.get("usuario_id")
        if not usuario_id:
            context.user_data["telegram_user_id"] = user.id
            context.user_data["usuario_id"] = database.obtener_o_crear_usuario(user.id, user.first_name)["id"]
            usuario_id = context.user_data["usuario_id"]

        balance = database.obtener_balance(usuario_id)
        transacciones = database.obtener_transacciones(usuario_id, 5)
        categorias = database.obtener_categorias(usuario_id)
        monedas = database.obtener_monedas(usuario_id)
        por_moneda = balance.get("por_moneda", {})

        balance_text = ""
        if len(por_moneda) > 1 or (len(por_moneda) == 1 and list(por_moneda.keys()) != ["Sin moneda"]):
            for abrev, datos in por_moneda.items():
                simbolo = datos.get("simbolo", "$")
                nombre = datos.get("nombre", abrev)
                neto_m = datos["ingresos"] - datos["gastos"]
                balance_text += f"  {simbolo} {nombre} ({abrev}): +{simbolo}{datos['ingresos']:.2f} / -{simbolo}{datos['gastos']:.2f} = {simbolo}{neto_m:.2f}\n"
        else:
            balance_text = f"  Ingresos: ${balance['ingresos']:.2f}\n  Gastos: ${balance['gastos']:.2f}\n  Neto: ${balance['neto']:.2f}\n"

        mensaje = (
            f"👤 **Usuario:** {escape_markdown(user.first_name or 'Usuario', version=1)}\n"
            f"🆔 **ID:** `{user.id}`\n\n"
            f"💰 **Balance:**\n{balance_text}\n"
            f"📁 **Categorías:** {len(categorias)}\n"
            f"💱 **Monedas:** {len(monedas)}\n"
            f"📝 **Transacciones recientes:** {len(transacciones)}"
        )
        await update.message.reply_text(mensaje, parse_mode="Markdown")
    except Exception as e:
        logger.error("Error en /user: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al obtener tu información.")


async def consultar_comandos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /help."""
    try:
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
    except Exception as e:
        logger.error("Error en /help: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al mostrar la ayuda.")


async def eliminar_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /delete para borrar todo el historial."""
    try:
        user = update.effective_user

        if "usuario_id" not in context.user_data:
            context.user_data["telegram_user_id"] = user.id
            context.user_data["usuario_id"] = database.obtener_o_crear_usuario(user.id, user.first_name)["id"]

        usuario_id = context.user_data["usuario_id"]
        eliminadas = database.eliminar_transacciones(usuario_id)

        botones = _crear_botones_rapidos()
        mensaje = f"🗑️ **Historial eliminado.** Se borraron **{eliminadas}** transacciones.\n\nTu balance ahora está en $0.00."
        await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=botones)
    except Exception as e:
        logger.error("Error en /delete: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al eliminar el historial.")


# ============================================================
# COMANDO /anuncio - Envío de anuncios a todos los usuarios
# ============================================================

async def anuncio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /anuncio para enviar mensajes a todos los usuarios."""
    try:
        user = update.effective_user

        # Solo el admin puede usar este comando
        if user.id != ADMIN_USER_ID:
            await update.message.reply_text("🚫 No tienes permiso para usar este comando.")
            return

        # Verificar que haya mensaje
        if not context.args:
            await update.message.reply_text(
                "Uso: `/anuncio Tu mensaje aquí`\n\n"
                "Ejemplo: `/anuncio Mañana hay mantenimiento de 10 a 10:30`",
                parse_mode="Markdown",
            )
            return

        mensaje_anuncio = " ".join(context.args)
        total_usuarios = database.contar_usuarios()

        # Guardar en context para el preview
        context.user_data["anuncio_pendiente"] = mensaje_anuncio

        # Mostrar preview con botones
        preview = (
            f"📢 **Vista previa del anuncio:**\n\n"
            f"{mensaje_anuncio}\n\n"
            f"👥 Enviado a: **{total_usuarios}** usuarios"
        )

        botones = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Enviar", callback_data="anuncio_enviar"),
                InlineKeyboardButton("❌ Cancelar", callback_data="anuncio_cancelar"),
            ]
        ])

        await update.message.reply_text(preview, parse_mode="Markdown", reply_markup=botones)
    except Exception as e:
        logger.error("Error en /anuncio: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al procesar el anuncio.")


# ============================================================
# BOTONES DEL TECLADO PERSISTENTE
# ============================================================

async def _manejar_boton_teclado(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  mensaje: str, usuario: dict):
    """Maneja los taps en los botones del teclado persistente."""
    usuario_id = context.user_data["usuario_id"]
    botones = _crear_teclado_permanente()

    if mensaje == BTN_BALANCE:
        balance = database.obtener_balance(usuario_id)
        monedas = database.obtener_monedas(usuario_id)
        por_moneda = balance.get("por_moneda", {})

        lineas = ["💰 **Tu balance actual:**\n"]

        if len(por_moneda) > 1 or (len(por_moneda) == 1 and list(por_moneda.keys()) != ["Sin moneda"]):
            # Mostrar balance por moneda
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
            # Sin monedas configuradas, mostrar balance simple
            lineas.append(f"  📈 Ingresos: ${balance['ingresos']:.2f}")
            lineas.append(f"  📉 Gastos: ${balance['gastos']:.2f}")
            lineas.append(f"  💵 Neto: ${balance['neto']:.2f}")

        texto = "\n".join(lineas)
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=botones)

    elif mensaje == BTN_TRANSACCIONES:
        transacciones = database.obtener_transacciones(usuario_id, 5)
        if not transacciones:
            texto = "📝 No tienes transacciones registradas aún."
        else:
            lineas = ["📝 **Tus últimas transacciones:**\n"]
            for t in transacciones:
                icono = "📈" if t["tipo"] == "ingreso" else "📉"
                label = "Ingreso" if t["tipo"] == "ingreso" else "Gasto"
                fecha = t.get("fecha", "N/A")[:10]
                desc = knowledge._limpiar_descripcion(t.get("descripcion", ""))
                lineas.append(f"{icono} ${t['cantidad']:.2f} - {label}: {desc} ({fecha})")
            texto = "\n".join(lineas)
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=botones)

    elif mensaje == BTN_PRESUPUESTOS:
        presupuestos = database.obtener_presupuestos(usuario_id)
        if not presupuestos:
            texto = "📊 No tienes presupuestos configurados.\n\nUsa: `Mi presupuesto para comida es $500 este mes`"
        else:
            lineas = ["📊 **Tus presupuestos:**\n"]
            for p in presupuestos:
                cat = p.get("categoria_nombre", "General")
                planeado = p["cantidad_planejada"]
                gastado = p["cantidad_gastada"]
                restante = planeado - gastado
                progreso = (gastado / planeado * 100) if planeado > 0 else 0
                barra = "█" * int(progreso / 10) + "░" * (10 - int(progreso / 10))
                lineas.append(f"📌 **{cat}**")
                lineas.append(f"   ${gastado:.2f} / ${planeado:.2f} ({progreso:.0f}%)")
                lineas.append(f"   Restante: ${restante:.2f}")
                lineas.append(f"   {barra}")
            texto = "\n".join(lineas)
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=botones)

    elif mensaje == BTN_MONEDAS:
        await _mostrar_menu_monedas(update, context, usuario_id)


# ============================================================
# GESTIÓN DE MONEDAS
# ============================================================

async def _mostrar_menu_monedas(update: Update, context: ContextTypes.DEFAULT_TYPE, usuario_id: int):
    """Muestra el menú de monedas con InlineKeyboard."""
    monedas = database.obtener_monedas(usuario_id)
    botones = _crear_teclado_permanente()

    if not monedas:
        texto = (
            "💱 **Tus monedas:**\n\n"
            "📝 Aún no tienes monedas configuradas.\n\n"
            "Toca **➕ Agregar** para crear tu primera moneda."
        )
    else:
        lineas = ["💱 **Tus monedas:**\n━━━━━━━━━━━━━━━━━"]
        for m in monedas:
            default = " ⭐ predeterminada" if m.get("es_default") else ""
            lineas.append(f"  {m['simbolo']} {m['nombre']} ({m['abreviatura']}){default}")
        texto = "\n".join(lineas)

    kb_inline = _crear_botones_monedasInlineKeyboard(monedas)
    await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=kb_inline)


async def _manejar_flujo_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 mensaje: str, usuario: dict):
    """Maneja el flujo conversacional de agregar moneda (3 pasos)."""
    paso = context.user_data.get("agregando_moneda_paso")
    datos = context.user_data.get("agregando_moneda_datos", {})
    botones = _crear_teclado_permanente()

    if mensaje.lower() in ("cancelar", "❌ cancelar"):
        context.user_data.pop("agregando_moneda_paso", None)
        context.user_data.pop("agregando_moneda_datos", None)
        await update.message.reply_text("❌ Agregación cancelada.", reply_markup=botones)
        return

    if paso == 1:
        datos["nombre"] = mensaje.strip().title()
        context.user_data["agregando_moneda_paso"] = 2
        context.user_data["agregando_moneda_datos"] = datos
        await update.message.reply_text(
            f"✅ Nombre: **{datos['nombre']}**\n\n¿Cuál es el símbolo? (ej: $, €, ₿, £)",
            parse_mode="Markdown", reply_markup=botones,
        )

    elif paso == 2:
        datos["simbolo"] = mensaje.strip()
        context.user_data["agregando_moneda_paso"] = 3
        context.user_data["agregando_moneda_datos"] = datos
        await update.message.reply_text(
            f"✅ Símbolo: **{datos['simbolo']}**\n\n¿Cuál es la abreviatura? (ej: USD, EUR, CUP)",
            parse_mode="Markdown", reply_markup=botones,
        )

    elif paso == 3:
        datos["abreviatura"] = mensaje.strip().upper()
        usuario_id = context.user_data["usuario_id"]
        monedas_existentes = database.obtener_monedas(usuario_id)
        es_default = len(monedas_existentes) == 0

        moneda = database.crear_moneda(
            usuario_id, datos["nombre"], datos["simbolo"], datos["abreviatura"], es_default
        )
        context.user_data.pop("agregando_moneda_paso", None)
        context.user_data.pop("agregando_moneda_datos", None)

        default_text = " ⭐ (predeterminada)" if es_default else ""
        await update.message.reply_text(
            f"✅ **Moneda creada!**\n\n"
            f"  {moneda['simbolo']} {moneda['nombre']} ({moneda['abreviatura']}){default_text}",
            parse_mode="Markdown", reply_markup=botones,
        )


async def _manejar_eliminar_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                     mensaje: str, usuario: dict):
    """Maneja la eliminación de monedas por selección numérica."""
    botones = _crear_teclado_permanente()
    usuario_id = context.user_data["usuario_id"]
    monedas = database.obtener_monedas(usuario_id)

    if mensaje.lower() in ("cancelar", "❌ cancelar", "salir"):
        context.user_data.pop("eliminando_moneda", None)
        await update.message.reply_text("❌ Eliminación cancelada.", reply_markup=botones)
        return

    try:
        idx = int(mensaje.strip()) - 1
        if 0 <= idx < len(monedas):
            m = monedas[idx]
            if m.get("es_default"):
                await update.message.reply_text(
                    "⚠️ No puedes eliminar la moneda predeterminada.\n"
                    "Primero cambia la predeterminada a otra moneda.",
                    reply_markup=botones,
                )
            else:
                database.eliminar_moneda(usuario_id, m["id"])
                await update.message.reply_text(
                    f"🗑️ Moneda eliminada: {m['simbolo']} {m['nombre']} ({m['abreviatura']})",
                    reply_markup=botones,
                )
        else:
            await update.message.reply_text("❌ Número fuera de rango. Intenta de nuevo.", reply_markup=botones)
            return
    except ValueError:
        await update.message.reply_text("❌ Envía el número de la moneda a eliminar.", reply_markup=botones)
        return

    context.user_data.pop("eliminando_moneda", None)


async def _manejar_cambiar_default(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                     mensaje: str, usuario: dict):
    """Maneja el cambio de moneda predeterminada por selección numérica."""
    botones = _crear_teclado_permanente()
    usuario_id = context.user_data["usuario_id"]
    monedas = database.obtener_monedas(usuario_id)

    if mensaje.lower() in ("cancelar", "❌ cancelar", "salir"):
        context.user_data.pop("cambiando_default_moneda", None)
        await update.message.reply_text("❌ Cancelado.", reply_markup=botones)
        return

    try:
        idx = int(mensaje.strip()) - 1
        if 0 <= idx < len(monedas):
            m = monedas[idx]
            database.establecer_moneda_default(usuario_id, m["id"])
            context.user_data.pop("cambiando_default_moneda", None)
            await update.message.reply_text(
                f"⭐ **{m['nombre']} ({m['abreviatura']})** es ahora tu moneda predeterminada.",
                parse_mode="Markdown", reply_markup=botones,
            )
        else:
            await update.message.reply_text("❌ Número fuera de rango. Intenta de nuevo.", reply_markup=botones)
            return
    except ValueError:
        await update.message.reply_text("❌ Envía el número de la moneda.", reply_markup=botones)
        return


# ============================================================
# CALLBACKS DE MONEDAS (InlineKeyboard)
# ============================================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones inline."""
    query = update.callback_query
    await query.answer()

    try:
        user = update.effective_user
        usuario = database.obtener_usuario(user.id)
        if not usuario:
            usuario = database.obtener_o_crear_usuario(user.id, user.first_name)
        usuario_id = usuario["id"]

        botones = _crear_botones_rapidos()

        if query.data == "accion_balance":
            balance = database.obtener_balance(usuario_id)
            por_moneda = balance.get("por_moneda", {})

            lineas = ["💰 **Tu balance actual:**\n"]
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
                lineas.append(f"  📈 Ingresos: ${balance['ingresos']:.2f}")
                lineas.append(f"  📉 Gastos: ${balance['gastos']:.2f}")
                lineas.append(f"  💵 Neto: ${balance['neto']:.2f}")

            mensaje = "\n".join(lineas)
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

        # === CALLBACKS DE MONEDAS ===
        elif query.data == "moneda_agregar":
            context.user_data["agregando_moneda_paso"] = 1
            context.user_data["agregando_moneda_datos"] = {}
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    "➕ **Agregar moneda**\n\n"
                    "¿Cómo se llama la moneda?\n"
                    "(ej: Euro, Peso cubano, USDT)\n\n"
                    "Escribe `cancelar` para salir."
                ),
                parse_mode="Markdown",
            )

        elif query.data == "monedaeliminar_menu":
            monedas = database.obtener_monedas(usuario_id)
            if not monedas:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="📝 No tienes monedas para eliminar.",
                )
                return
            lineas = ["🗑️ **Elige la moneda a eliminar:**\n"]
            for i, m in enumerate(monedas, 1):
                default = " ⭐" if m.get("es_default") else ""
                lineas.append(f"  {i}. {m['simbolo']} {m['nombre']} ({m['abreviatura']}){default}")
            lineas.append("\nEnvía el número de la moneda a eliminar.")
            lineas.append("Escribe `cancelar` para salir.")
            context.user_data["eliminando_moneda"] = True
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="\n".join(lineas),
                parse_mode="Markdown",
            )

        elif query.data == "moneda_default_menu":
            monedas = database.obtener_monedas(usuario_id)
            if len(monedas) < 2:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="📝 Necesitas al menos 2 monedas para cambiar la predeterminada.",
                )
                return
            lineas = ["⭐ **Elige la moneda predeterminada:**\n"]
            for i, m in enumerate(monedas, 1):
                default = " (actual)" if m.get("es_default") else ""
                lineas.append(f"  {i}. {m['simbolo']} {m['nombre']} ({m['abreviatura']}){default}")
            lineas.append("\nEnvía el número de la moneda.")
            lineas.append("Escribe `cancelar` para salir.")
            context.user_data["cambiando_default_moneda"] = True
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="\n".join(lineas),
                parse_mode="Markdown",
            )

        elif query.data.startswith("moneda_info_"):
            moneda_id = int(query.data.split("_")[-1])
            monedas = database.obtener_monedas(usuario_id)
            moneda = next((m for m in monedas if m["id"] == moneda_id), None)
            if moneda:
                default = " ⭐ predeterminada" if moneda.get("es_default") else ""
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=(
                        f"💱 **{moneda['nombre']}**\n\n"
                        f"  Símbolo: {moneda['simbolo']}\n"
                        f"  Abreviatura: {moneda['abreviatura']}{default}"
                    ),
                    parse_mode="Markdown",
                )

        # === CALLBACKS DE ANUNCIO ===
        elif query.data == "anuncio_enviar":
            # Verificar que sea el admin
            if user.id != ADMIN_USER_ID:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="🚫 No tienes permiso para realizar esta acción.",
                )
                return

            mensaje_anuncio = context.user_data.pop("anuncio_pendiente", None)
            if not mensaje_anuncio:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="⚠️ No hay anuncio pendiente para enviar.",
                )
                return

            # Enviar a todos los usuarios
            usuarios = database.obtener_todos_los_usuarios()
            enviados = 0
            fallidos = 0
            for u in usuarios:
                try:
                    await context.bot.send_message(
                        chat_id=u["telegram_user_id"],
                        text=f"📢 **Anuncio:**\n\n{mensaje_anuncio}",
                        parse_mode="Markdown",
                    )
                    enviados += 1
                except Exception as e:
                    logger.warning("No se pudo enviar anuncio a %s: %s", u.get("nombre", "?"), e)
                    fallidos += 1

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"✅ Anuncio enviado a **{enviados}** usuarios." + (f"\n⚠️ {fallidos} no pudieron recibirllo." if fallidos else ""),
                parse_mode="Markdown",
            )

        elif query.data == "anuncio_cancelar":
            context.user_data.pop("anuncio_pendiente", None)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Anuncio cancelado.",
            )

    except Exception as e:
        logger.error("Error en callback query: %s", e)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⚠️ Ocurrió un error al procesar tu solicitud. Intenta de nuevo.",
            reply_markup=_crear_botones_rapidos(),
        )