"""
handlers.py - Handlers para el bot de finanzas personales
Maneja comandos y mensajes en lenguaje natural para gestión financiera.
"""

import logging
import os
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

import config
import database
import exportador
import formato
from formato import md_a_html
import knowledge
import ai_client
import changelog
import notificaciones
import menus
import metricas
import validators
from config import IMAGES_DIR, ADMIN_USER_ID

logger = logging.getLogger(__name__)

# Monedas comunes para el botón de agregar moneda (auto-completar)
MONEDAS_PRESET = {
    "usd": {"nombre": "Dólar estadounidense", "simbolo": "$", "abreviatura": "USD"},
    "eur": {"nombre": "Euro", "simbolo": "€", "abreviatura": "EUR"},
    "usdt": {"nombre": "USDT", "simbolo": "₮", "abreviatura": "USDT"},
    "cup": {"nombre": "Peso cubano", "simbolo": "$", "abreviatura": "CUP"},
}


def _formatear_notificacion(ultima_vista: Optional[str]) -> Optional[str]:
    """Construye el mensaje de notificación solo con la última versión disponible."""
    if ultima_vista == changelog.VERSION_ACTUAL:
        return None

    data = changelog.CHANGELOG.get(changelog.VERSION_ACTUAL)
    if not data:
        return None

    lineas = [f"**v{changelog.VERSION_ACTUAL}** - {data['titulo']}"]
    for mejora in data.get("mejoras", []):
        lineas.append(f"• {mejora}")
    lineas.append("")
    lineas.append("Escribe /help para ver todos los comandos.")

    return "\n".join(lineas)


def _crear_teclado_principal() -> InlineKeyboardMarkup:
    """Botones principales de navegación (menú principal inline)."""
    return menus.teclado_principal()


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


def _crear_botones_moneda_presets() -> InlineKeyboardMarkup:
    """Crea los botones de monedas comunes para agregar sin escribir."""
    botones = [
        [
            InlineKeyboardButton("🇺🇸 USD · Dólar", callback_data="moneda_preset_usd"),
            InlineKeyboardButton("🇪🇺 EUR · Euro", callback_data="moneda_preset_eur"),
        ],
        [
            InlineKeyboardButton("🪙 USDT · Tether", callback_data="moneda_preset_usdt"),
            InlineKeyboardButton("🇨🇺 CUP · Peso cubano", callback_data="moneda_preset_cup"),
        ],
        [
            InlineKeyboardButton("✍️ Otra moneda", callback_data="moneda_manual"),
            InlineKeyboardButton("❌ Cancelar", callback_data="moneda_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(botones)


def _crear_botones_pendiente(pendiente: dict, usuario_id: int) -> Optional[InlineKeyboardMarkup]:
    """Crea los botones para completar una transacción pendiente (tipo o moneda)."""
    accion = pendiente.get("accion")
    if accion == "elegir_tipo":
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📉 Es un gasto", callback_data="tipo_gasto"),
                InlineKeyboardButton("📈 Es un ingreso", callback_data="tipo_ingreso"),
            ],
            [InlineKeyboardButton("❌ Cancelar", callback_data="pendiente_cancel")],
        ])
    if accion in ("elegir_moneda", "elegir_moneda_presupuesto"):
        filas = []
        for m in database.obtener_monedas(usuario_id):
            filas.append([
                InlineKeyboardButton(
                    f"{m['simbolo']} {m['nombre']} ({m['abreviatura']})",
                    callback_data=f"moneda_confirmar_{m['id']}",
                )
            ])
        filas.append([InlineKeyboardButton("❌ Cancelar", callback_data="pendiente_cancel")])
        return InlineKeyboardMarkup(filas)
    if accion in ("confirmar_gasto_excedido", "confirmar_gasto_balance"):
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Sí, continuar", callback_data="conf_exc_si"),
                InlineKeyboardButton("❌ Cancelar", callback_data="pendiente_cancel"),
            ],
        ])
    if accion == "ver_todas":
        tipo = pendiente.get("tipo") or "all"
        etiqueta = "📂 Ver todas las transacciones"
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(etiqueta, callback_data=f"ver_todas:{tipo}")],
        ])
    return None


def _completar_pendiente(pendiente: dict, tipo: str, usuario: dict,
                         moneda: Optional[dict] = None) -> str:
    """Completa el registro de una transacción pendiente usando el mensaje original."""
    mensaje = pendiente.get("mensaje", "")
    moneda_obj = moneda
    if moneda_obj is None:
        moneda_id = pendiente.get("moneda_id")
        if moneda_id:
            for m in database.obtener_monedas(usuario["id"]):
                if m["id"] == moneda_id:
                    moneda_obj = m
                    break
    if tipo == "ingreso":
        return knowledge._procesar_ingreso(mensaje, usuario, moneda=moneda_obj)
    texto, _pend = knowledge._procesar_gasto(mensaje, usuario, moneda=moneda_obj, forzar=True)
    return texto


def _completar_pendiente_presupuesto(pendiente: dict, moneda: dict, usuario: dict) -> str:
    """Completa la configuración de un presupuesto pendiente con la moneda elegida."""
    resultado = {
        "cantidad": pendiente.get("cantidad"),
        "categoria": pendiente.get("categoria"),
        "nombre": pendiente.get("nombre"),
        "modo_presupuesto": pendiente.get("modo"),
    }
    respuesta, pend = ai_client.AIResponder()._procesar_presupuesto(
        resultado, usuario, pendiente.get("mensaje", ""), moneda=moneda
    )
    return respuesta


def _texto_nuevo_usuario(user, total: int) -> str:
    username = f"@{user.username}" if getattr(user, "username", None) else "sin @username"
    nombre = escape_markdown(user.first_name or "amigo", version=1)
    return (
        f"🆕 **Nuevo usuario en el bot**\n"
        f"👤 {nombre} ({username})\n"
        f"🆔 id: `{user.id}`\n"
        f"👥 Total registrados: {total}"
    )


async def _avisar_admin_nuevo_usuario(context: ContextTypes.DEFAULT_TYPE, user) -> None:
    """Notifica al admin el registro de un usuario nuevo."""
    if not ADMIN_USER_ID:
        return
    try:
        total = database.contar_usuarios()
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=_texto_nuevo_usuario(user, total),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"No se pudo notificar nuevo usuario {user.id}: {e}")


def _es_usuario_nuevo(user) -> bool:
    try:
        return database.obtener_usuario(user.id) is None
    except Exception as e:
        logger.warning(f"No se pudo verificar usuario existente {user.id}: {e}")
        return False


async def _registrar_usuario(context: ContextTypes.DEFAULT_TYPE, user):
    """Obtiene o crea el usuario y avisa al admin si es la primera vez que usa el bot."""
    es_nuevo = _es_usuario_nuevo(user)
    usuario = database.obtener_o_crear_usuario(user.id, user.first_name or "amigo")
    if es_nuevo:
        await _avisar_admin_nuevo_usuario(context, user)
    return usuario


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start."""
    try:
        user = update.effective_user
        nombre_mostrar = escape_markdown(user.first_name or "amigo", version=1)

        context.user_data["telegram_user_id"] = user.id
        es_nuevo = _es_usuario_nuevo(user)
        usuario = await _registrar_usuario(context, user)
        context.user_data["usuario_id"] = usuario["id"]

        estadisticas = database.contar_transacciones(usuario["id"])

        mensaje = (
            f"👋 Hola {nombre_mostrar}, soy **FinanzasBot**.\n\n"
            f"{formato.EMOJI_PRESUPUESTO} **Actividad registrada**\n"
            f"{formato.SEPARADOR}\n"
            f"{formato.EMOJI_GASTO} {estadisticas.get('gastos', 0)} gastos · "
            f"{formato.EMOJI_INGRESO} {estadisticas.get('ingresos', 0)} ingresos · "
            f"{estadisticas.get('total', 0)} en total\n\n"
            "**Qué puedes hacer:**\n"
            "• Registrar: `Gasté $50 en comida`\n"
            "• Consultar: `¿Cuánto tengo?`\n"
            "• Presupuestar: `Mi presupuesto para comida es $500`\n"
            "• Metas: `Quiero ahorrar $5000 para vacaciones`\n\n"
            "Usa /help para ver todos los comandos.\n\n"
            "👇 **Elige una opción abajo o escríbeme en lenguaje natural:**"
        )

        # El aviso de migración de teclado se muestra UNA sola vez: solo a
        # usuarios que ya usaban el bot antes de los botones inline. Los nuevos
        # y los ya migrados no lo ven nunca más.
        migrado = bool(int(usuario.get("teclado_migrado", 0) or 0))
        if not es_nuevo and not migrado:
            await update.message.reply_text(
                "🧭 Te cambié el teclado: ahora navegas con botones.",
                reply_markup=ReplyKeyboardRemove(),
            )
            database.marcar_teclado_migrado(usuario["id"])
        elif es_nuevo:
            database.marcar_teclado_migrado(usuario["id"])

        await update.message.reply_text(
            mensaje, parse_mode="Markdown", reply_markup=_crear_teclado_principal()
        )
    except Exception as e:
        logger.error("Error en /start: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error. Intenta de nuevo con /start.")


async def _manejar_ctx_presupuesto(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   mensaje: str, usuario: dict, usuario_id: int) -> bool:
    """Procesa el texto escrito cuando hay un presupuesto activo en el flujo del menú.

    El gasto se registra asociado al presupuesto seleccionado (resta de su
    categoría). Retorna True si consumió el mensaje.
    """
    ctx = context.user_data.get("presupuesto_ctx") or {}
    presupuesto = next(
        (p for p in database.obtener_presupuestos(usuario_id) if p.get("id") == ctx.get("id")),
        None,
    )
    if not presupuesto:
        context.user_data.pop("presupuesto_ctx", None)
        return False
    msg = update.message or update.edited_message

    if mensaje.strip().lower() in ("cancelar", "cancel", "no"):
        context.user_data.pop("presupuesto_ctx", None)
        await msg.reply_text("❌ Operación cancelada.", parse_mode="Markdown",
                             reply_markup=_crear_teclado_principal())
        return True

    # Si no parece un gasto (sin monto o un ingreso/consulta), liberar el contexto.
    monto_ctx, _err_monto = validators.validar_monto(mensaje)
    if not monto_ctx:
        context.user_data.pop("presupuesto_ctx", None)
        return False
    m = mensaje.lower()
    if any(palabra in m for palabra in ("recib", "ingreso", "salario", "sueldo",
                                        "cobr", "deposit", "cuánt", "cuant", "tengo",
                                        "balance", "resumen", "hola", "gracias", "ayuda")):
        context.user_data.pop("presupuesto_ctx", None)
        return False

    texto, pendiente = knowledge._procesar_gasto(mensaje, usuario, presupuesto=presupuesto)
    context.user_data.pop("presupuesto_ctx", None)
    if pendiente and pendiente.get("accion") == "confirmar_gasto_excedido":
        context.user_data["transaccion_pendiente"] = pendiente
        botones = _crear_botones_pendiente(pendiente, usuario_id)
        await msg.reply_text(
            md_a_html(texto),
            parse_mode="HTML",
            reply_markup=botones or _crear_teclado_principal(),
        )
    else:
        await msg.reply_text(md_a_html(texto), parse_mode="HTML", reply_markup=_crear_teclado_principal())
    return True


async def _manejar_ctx_meta(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            mensaje: str, usuario: dict, usuario_id: int) -> bool:
    """Procesa el texto escrito cuando hay una meta activa en el flujo del menú
    ("Agregar dinero a una meta"). Suma el monto a esa meta.
    """
    ctx = context.user_data.get("meta_ctx") or {}
    meta = next(
        (mt for mt in database.obtener_metas_ahorro(usuario_id) if mt.get("id") == ctx.get("id")),
        None,
    )
    if not meta:
        context.user_data.pop("meta_ctx", None)
        return False
    msg = update.message or update.edited_message

    if mensaje.strip().lower() in ("cancelar", "cancel", "no"):
        context.user_data.pop("meta_ctx", None)
        await msg.reply_text("❌ Operación cancelada.", parse_mode="Markdown",
                             reply_markup=_crear_teclado_principal())
        return True

    cantidad, err_monto = validators.validar_monto(mensaje)
    if err_monto:
        nombre = meta.get("nombre", "tu meta")
        await msg.reply_text(
            f"💵 {err_monto}\n"
            f"Ej: `agrega 500` o simplemente `500` para la meta **{nombre}**.",
            parse_mode="Markdown",
        )
        return True

    texto = knowledge._agregar_dinero_a_meta(meta, cantidad)
    context.user_data.pop("meta_ctx", None)
    await msg.reply_text(texto, parse_mode="Markdown", reply_markup=_crear_teclado_principal())
    return True


async def _responder_seguro(msg, texto: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Envía una respuesta al usuario de forma resiliente.

    Estrategia de 3 niveles para evitar que el usuario vea ``**`` o errores
    crudos:
    1. ``parse_mode="Markdown"`` (formato habitual del bot).
    2. Si Telegram lo rechaza (Markdown inválido), convierte a HTML con
       ``md_a_html`` y reintenta (el ``**`` se renderiza en negrita).
    3. Si todo falla, texto plano.
    """
    try:
        await msg.reply_text(texto, parse_mode="Markdown", reply_markup=reply_markup)
        return
    except Exception:
        pass
    try:
        await msg.reply_text(md_a_html(texto), parse_mode="HTML", reply_markup=reply_markup)
        return
    except Exception:
        pass
    try:
        await msg.reply_text(texto, reply_markup=reply_markup)
    except Exception:
        logger.error("No se pudo enviar la respuesta al usuario")


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
        context.user_data["usuario_id"] = (await _registrar_usuario(context, user))["id"]

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

    # --- Catch-up de resumen diario pendiente (Render free tier) ---
    try:
        await notificaciones.enviar_resumen_pendiente(context, msg.chat_id, usuario)
    except Exception as e:
        logger.error("Error en catch-up de resumen diario: %s", e)
    # --- Fin catch-up ---

    # --- Flujo de soporte: capturar el reporte del usuario ---
    if context.user_data.get("esperando_soporte"):
        context.user_data.pop("esperando_soporte", None)
        if mensaje.strip().lower() in ("cancelar", "cancel", "no"):
            await msg.reply_text("❌ Reporte cancelado.", reply_markup=_crear_teclado_principal())
            return
        await _enviar_ticket(context, msg, user, mensaje)
        return

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

    # --- Contexto de flujo del menú: presupuesto o meta seleccionada ---
    if context.user_data.get("presupuesto_ctx"):
        if await _manejar_ctx_presupuesto(update, context, mensaje, usuario, usuario_id):
            return
    if context.user_data.get("meta_ctx"):
        if await _manejar_ctx_meta(update, context, mensaje, usuario, usuario_id):
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
        respuesta, pendiente = await ai_client.AIResponder().responder(mensaje, usuario)
        reply_markup = _crear_teclado_principal()
        if pendiente:
            context.user_data["transaccion_pendiente"] = pendiente
            botones_pendiente = _crear_botones_pendiente(pendiente, usuario_id)
            if botones_pendiente:
                reply_markup = botones_pendiente

        # Exportación por lenguaje natural: enviar el archivo directamente
        if pendiente and pendiente.get("accion") == "exportar":
            context.user_data.pop("transaccion_pendiente", None)
            await msg.reply_text(respuesta, parse_mode="Markdown", reply_markup=_crear_teclado_principal())
            await _enviar_exportacion(msg, context, usuario,
                                      pendiente.get("formato"), pendiente.get("periodo"))
            return

        await _responder_seguro(msg, respuesta, reply_markup)
    except Exception as e:
        logger.error("Error procesando mensaje de %s: %s", user.first_name, e)
        await _responder_seguro(
            msg,
            "⚠️ Ups, algo salió mal al procesar tu mensaje.\n\n"
            "Intenta con estos comandos:\n"
            "• `Gasté $50 en comida`\n"
            "• `¿Cuánto tengo?`\n"
            "• `¿Qué gasté hoy?`\n\n"
            "Si el problema persiste, escribe `/help`.",
            _crear_teclado_principal(),
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
            context.user_data["usuario_id"] = (await _registrar_usuario(context, user))["id"]
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
                neto_m = datos["ingresos"] - datos["gastos"]
                balance_text += (
                    f"{abrev}  {formato.EMOJI_INGRESO} {formato.fmt_moneda(datos['ingresos'], simbolo=simbolo)}  "
                    f"{formato.EMOJI_GASTO} {formato.fmt_moneda(datos['gastos'], simbolo=simbolo)}  "
                    f"→ **{formato.fmt_moneda(neto_m, simbolo=simbolo)}**\n"
                )
        else:
            balance_text = (
                f"{formato.EMOJI_INGRESO} {formato.fmt_moneda(balance['ingresos'])}\n"
                f"{formato.EMOJI_GASTO} {formato.fmt_moneda(balance['gastos'])}\n"
                f"Neto: **{formato.fmt_moneda(balance['neto'])}**"
            )

        mensaje = (
            f"👤 **{escape_markdown(user.first_name or 'Usuario', version=1)}** · `ID {user.id}`\n\n"
            f"{formato.EMOJI_BALANCE} **Balance de {formato.nombre_mes_actual()}**\n{formato.SEPARADOR}\n{balance_text}\n"
            f"\n📁 {len(categorias)} categorías · {formato.EMOJI_MONEDA} {len(monedas)} monedas · "
            f"{len(transacciones)} transacciones"
        )
        await update.message.reply_text(mensaje, parse_mode="Markdown")
    except Exception as e:
        logger.error("Error en /user: %s", e)
        await update.message.reply_text("❌ Ocurrió un error al obtener tu información.\nIntenta de nuevo o escribe /help.")


async def consultar_comandos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /help."""
    try:
        mensaje = menus.TEXTO_HELP
        await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=_crear_teclado_principal())
    except Exception as e:
        logger.error("Error en /help: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al mostrar la ayuda.")


def _obtener_usuario_contexto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Garantiza el usuario en context.user_data y lo retorna."""
    user = update.effective_user
    if "usuario_id" not in context.user_data:
        es_nuevo = _es_usuario_nuevo(user)
        context.user_data["telegram_user_id"] = user.id
        context.user_data["usuario_id"] = database.obtener_o_crear_usuario(user.id, user.first_name or "amigo")["id"]
        if es_nuevo:
            app = getattr(context, "application", None)
            if app is not None:
                app.create_task(_avisar_admin_nuevo_usuario(context, user))
    usuario_id = context.user_data["usuario_id"]
    usuario = database.obtener_usuario(user.id) or {"id": usuario_id, "nombre": user.first_name or "amigo"}
    return usuario


async def consultar_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /categorias."""
    try:
        usuario = _obtener_usuario_contexto(update, context)
        texto = knowledge._procesar_categorias(usuario)
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=_crear_teclado_principal())
    except Exception as e:
        logger.error("Error en /categorias: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al obtener tus categorías.")


async def consultar_gastos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /gastos."""
    try:
        usuario = _obtener_usuario_contexto(update, context)
        texto = knowledge._procesar_gastos(usuario)
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=_crear_teclado_principal())
    except Exception as e:
        logger.error("Error en /gastos: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al obtener tus gastos.")


async def consultar_ingresos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /ingresos."""
    try:
        usuario = _obtener_usuario_contexto(update, context)
        texto = knowledge._procesar_ingresos(usuario)
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=_crear_teclado_principal())
    except Exception as e:
        logger.error("Error en /ingresos: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al obtener tus ingresos.")


async def consultar_metas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /metas."""
    try:
        usuario = _obtener_usuario_contexto(update, context)
        texto = knowledge._procesar_metas_ahorro(usuario)
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=_crear_teclado_principal())
    except Exception as e:
        logger.error("Error en /metas: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al obtener tus metas de ahorro.")


async def consultar_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /resumen (resumen del mes actual)."""
    try:
        usuario = _obtener_usuario_contexto(update, context)
        texto = knowledge._procesar_resumen_mensual(usuario)
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=_crear_teclado_principal())
    except Exception as e:
        logger.error("Error en /resumen: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al generar tu resumen.")


async def consultar_gastos_hormiga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /gastos_hormiga."""
    try:
        usuario = _obtener_usuario_contexto(update, context)
        texto = knowledge._procesar_gastos_hormiga(usuario)
        await update.message.reply_text(md_a_html(texto), parse_mode="HTML", reply_markup=_crear_teclado_principal())
    except Exception as e:
        logger.error("Error en /gastos_hormiga: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al obtener tus gastos hormiga.")


async def configurar_gastos_hormiga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /config_hormiga."""
    try:
        usuario = _obtener_usuario_contexto(update, context)
        args = context.args or []
        mensaje = " ".join(args) if args else "mostrar"
        texto = knowledge._procesar_config_gastos_hormiga(usuario, mensaje)
        await update.message.reply_text(md_a_html(texto), parse_mode="HTML", reply_markup=_crear_teclado_principal())
    except Exception as e:
        logger.error("Error en /config_hormiga: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al configurar los gastos hormiga.")


def _parsear_args_exportacion(args: list) -> tuple:
    """Interpreta los argumentos de /exportar: (formato, periodo)."""
    formato = "xlsx"
    periodo = "todo"
    valores_periodo = {"todo", "mes", "30", "30d", "mensual"}
    for arg in args:
        a = arg.strip().lower()
        if a in ("xlsx", "excel", "csv"):
            formato = a if a != "excel" else "xlsx"
        elif a in valores_periodo:
            periodo = "mes" if a in ("mes", "mensual") else ("30" if a in ("30", "30d") else "todo")
        elif len(a) == 7 and a[4] == "-" and a[:4].isdigit() and a[5:].isdigit():
            periodo = a
    return formato, periodo


async def _enviar_exportacion(msg, context: ContextTypes.DEFAULT_TYPE, usuario: dict,
                              formato: Optional[str] = "xlsx", periodo: Optional[str] = "todo") -> None:
    """Genera la exportación (XLSX/CSV) y la envía como documento(s)."""
    rutas = []
    try:
        formato = (formato or "xlsx").lower()
        periodo = (periodo or "todo").lower()
        label, inicio, fin = exportador._resolver_periodo(periodo)

        if inicio:
            transacciones = database.obtener_transacciones_por_fecha(usuario["id"], inicio, fin)
            balance = database.obtener_balance(usuario["id"], fecha_inicio=inicio)
        else:
            transacciones = database.obtener_transacciones(usuario["id"], limite=exportador.MAX_TRANSACCIONES)
            balance = database.obtener_balance(usuario["id"], fecha_inicio="0000-01-01")

        monedas = database.obtener_monedas(usuario["id"])
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        if formato == "csv":
            rutas = exportador.generar_csv_partes(usuario["id"], label, transacciones, monedas, str(IMAGES_DIR))
            for ruta in rutas:
                with open(ruta, "rb") as f:
                    await context.bot.send_document(
                        chat_id=msg.chat_id,
                        document=f,
                        filename=os.path.basename(ruta),
                    )
        else:
            ruta = exportador.generar_xlsx(
                usuario["id"], usuario.get("nombre") or "", label, balance,
                transacciones, monedas, str(IMAGES_DIR),
            )
            rutas = [ruta]
            with open(ruta, "rb") as f:
                await context.bot.send_document(
                    chat_id=msg.chat_id,
                    document=f,
                    filename=os.path.basename(ruta),
                )
    except Exception as e:
        logger.error("Error generando exportación para %s: %s", usuario.get("id"), e)
        await context.bot.send_message(
            chat_id=msg.chat_id,
            text="❌ No pude generar tu exportación. Intenta de nuevo en un momento.",
            reply_markup=_crear_teclado_principal(),
        )
    finally:
        for ruta in rutas:
            try:
                os.remove(ruta)
            except OSError:
                pass


async def exportar_datos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /exportar (exporta datos a Excel/CSV)."""
    try:
        usuario = _obtener_usuario_contexto(update, context)
        args = context.args or []
        if args:
            formato, periodo = _parsear_args_exportacion(args)
            await update.message.reply_text("📤 **Generando tu exportación...**", parse_mode="Markdown")
            await _enviar_exportacion(update.message, context, usuario, formato, periodo)
            return
        botones = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Excel (.xlsx)", callback_data="exp_fmt_xlsx"),
                InlineKeyboardButton("📄 CSV", callback_data="exp_fmt_csv"),
            ],
            [InlineKeyboardButton("❌ Cancelar", callback_data="exp_cancel")],
        ])
        await update.message.reply_text(
            "📤 **¿En qué formato quieres exportar tus datos?**",
            parse_mode="Markdown",
            reply_markup=botones,
        )
    except Exception as e:
        logger.error("Error en /exportar: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al procesar tu solicitud.")


async def eliminar_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pide confirmación antes de borrar todo el historial."""
    try:
        botones_confirm = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Sí, borrar todo", callback_data="delete_confirm"),
                InlineKeyboardButton("❌ Cancelar", callback_data="delete_cancel"),
            ],
        ])
        await update.message.reply_text(
            "⚠️ **¿Estás seguro?**\n\n"
            "Se eliminarán **TODAS** tus transacciones y tu balance quedará en $0.00.\n"
            "Esta acción no se puede deshacer.",
            parse_mode="Markdown",
            reply_markup=botones_confirm,
        )
    except Exception as e:
        logger.error("Error en /delete: %s", e)
        await update.message.reply_text("⚠️ Ocurrió un error al procesar la solicitud.")


# ============================================================
# NOTIFICACIONES (/notificaciones)
# ============================================================

def _crear_menu_notificaciones(prefs: dict):
    """Compone el texto y los botones del menú de notificaciones."""
    resumen = prefs.get("resumen_diario", False)
    a80 = prefs.get("alerta_80", True)
    a100 = prefs.get("alerta_100", True)
    a125 = prefs.get("alerta_125", True)
    hora = config.HORA_RESUMEN_DEFAULT
    zona = config.DEFAULT_TIMEZONE

    texto = (
        f"{formato.EMOJI_NOTIFICACION} **Notificaciones**\n"
        f"{formato.SEPARADOR}\n"
        f"Resumen diario: **{'activado' if resumen else 'desactivado'}** — {hora} (hora de Cuba)\n"
        f"Alertas de presupuesto: "
        f"{'✅' if a80 else '⬜'} 80% · {'✅' if a100 else '⬜'} 100% · {'✅' if a125 else '⬜'} 125%\n\n"
        "_Las alertas avisan al cruzar cada umbral. El resumen llega una vez al día._"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛑 Desactivar resumen diario" if resumen else "✅ Activar resumen diario",
                callback_data="notif_resumen",
            ),
        ],
        [
            InlineKeyboardButton(f"{'✅' if a80 else '⬜'} 80%", callback_data="notif_alerta_80"),
            InlineKeyboardButton(f"{'✅' if a100 else '⬜'} 100%", callback_data="notif_alerta_100"),
            InlineKeyboardButton(f"{'✅' if a125 else '⬜'} 125%", callback_data="notif_alerta_125"),
        ],
        [
            InlineKeyboardButton("🔙 Volver a Más opciones", callback_data="menu_mas"),
            InlineKeyboardButton("❌ Cerrar", callback_data="notif_close"),
        ],
    ])
    return texto, kb


async def configurar_notificaciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /notificaciones."""
    try:
        usuario = _obtener_usuario_contexto(update, context)
        prefs = database.obtener_preferencias(usuario["id"])
        texto, kb = _crear_menu_notificaciones(prefs)
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        logger.error("Error en /notificaciones: %s", e)
        await update.message.reply_text(
            "⚠️ Ocurrió un error al mostrar la configuración de notificaciones."
        )


# ============================================================
# COMANDO /anuncio - Envío de anuncios a todos los usuarios
# ============================================================

async def ver_metricas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /metricas (solo admin): estado del bot en tiempo real."""
    user = update.effective_user
    if not ADMIN_USER_ID or user.id != ADMIN_USER_ID:
        await update.message.reply_text("🔒 Este comando es solo para el administrador.")
        return

    try:
        total_usuarios = database.contar_usuarios()
    except Exception as e:
        logger.error("Error contando usuarios para /metricas: %s", e)
        total_usuarios = "?"
    procesados, bloqueados = metricas.mensajes()
    texto = (
        "📊 **MÉTRICAS DEL BOT**\n"
        f"⏱️ Uptime: {metricas.uptime_str()}\n"
        f"🗄️ Backend: {config.DB_BACKEND} | Versión: v{changelog.VERSION_ACTUAL}\n"
        "\n👥 Usuarios registrados: " + str(total_usuarios) +
        f"\n🟢 Activos ahora (5 min): {metricas.activos(300)}" +
        f"\n🕐 Activos última hora: {metricas.activos(3600)}" +
        f"\n\n💬 Mensajes procesados: {procesados}" +
        f"\n🚫 Bloqueados por flood: {bloqueados}" +
        f"\n💸 Transacciones hoy: {metricas.transacciones_hoy()}" +
        f"\n❌ Errores última hora: {metricas.errores_ultima_hora()}"
    )
    await update.message.reply_text(texto, parse_mode="Markdown")


async def _enviar_ticket(context: ContextTypes.DEFAULT_TYPE, msg, user, texto: str) -> None:
    """Envía un ticket de soporte al admin y confirma al usuario."""
    tid = datetime.now().strftime("%Y%m%d-%H%M")
    username = f"@{user.username}" if user.username else "sin username"
    ticket = (
        f"🎫 **TICKET DE SOPORTE** `{tid}`\n"
        f"👤 De: {user.first_name or 'Usuario'} ({username} | id: `{user.id}`)\n"
        f"💬 Reporte:\n{texto[:1500]}"
    )
    try:
        await context.bot.send_message(ADMIN_USER_ID, ticket, parse_mode="Markdown")
    except Exception as e:
        logger.error("No se pudo enviar ticket de soporte al admin: %s", e)
        await msg.reply_text(
            "❌ No pude entregar tu reporte en este momento. Intenta más tarde."
        )
        return
    await msg.reply_text(
        "✅ **¡Reporte enviado!**\n"
        "El administrador recibió tu ticket y te contactará si necesita más detalles.",
        parse_mode="Markdown",
        reply_markup=_crear_teclado_principal(),
    )


async def soporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /soporte: crea un ticket de reporte que llega al admin.

    Uso: /soporte <texto>  o  /soporte (y luego escribir el reporte).
    """
    user = update.effective_user
    msg = update.message
    if not ADMIN_USER_ID:
        await msg.reply_text("⚠️ El soporte no está disponible ahora. Intenta más tarde.")
        return

    texto_directo = " ".join(context.args).strip() if context.args else ""
    if texto_directo:
        await _enviar_ticket(context, msg, user, texto_directo)
        return

    context.user_data["esperando_soporte"] = True
    await msg.reply_text(
        "🎫 **Soporte**\n\n"
        "Cuéntame qué ocurrió en tu próximo mensaje "
        "(mientras más detalle, mejor).\n\n"
        "Escribe *cancelar* para salir sin enviar nada.",
        parse_mode="Markdown",
    )


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
# GESTIÓN DE MONEDAS
# ============================================================

async def _manejar_flujo_moneda(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 mensaje: str, usuario: dict):
    """Maneja el flujo conversacional de agregar moneda (3 pasos)."""
    paso = context.user_data.get("agregando_moneda_paso")
    datos = context.user_data.get("agregando_moneda_datos", {})

    if mensaje.lower() in ("cancelar", "❌ cancelar"):
        context.user_data.pop("agregando_moneda_paso", None)
        context.user_data.pop("agregando_moneda_datos", None)
        await update.message.reply_text("❌ Agregación cancelada.", reply_markup=_crear_teclado_principal())
        return

    if paso == 1:
        datos["nombre"] = mensaje.strip().title()
        context.user_data["agregando_moneda_paso"] = 2
        context.user_data["agregando_moneda_datos"] = datos
        await update.message.reply_text(
            f"✅ Nombre: **{datos['nombre']}**\n\n¿Cuál es el símbolo? (ej: $, €, ₿, £)",
            parse_mode="Markdown",
        )

    elif paso == 2:
        datos["simbolo"] = mensaje.strip()
        context.user_data["agregando_moneda_paso"] = 3
        context.user_data["agregando_moneda_datos"] = datos
        await update.message.reply_text(
            f"✅ Símbolo: **{datos['simbolo']}**\n\n¿Cuál es la abreviatura? (ej: USD, EUR, CUP)",
            parse_mode="Markdown",
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
            parse_mode="Markdown", reply_markup=_crear_teclado_principal(),
        )


# ============================================================
# CALLBACKS DE MONEDAS (InlineKeyboard)
# ============================================================

async def _responder_editando(query, texto: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Reemplaza el mensaje del botón por la respuesta final (evita llenar el chat).
    Si el mensaje ya no existe o no se puede editar, envía uno nuevo como respaldo."""
    if reply_markup is None:
        reply_markup = InlineKeyboardMarkup([])
    try:
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=reply_markup)
    except BadRequest as e:
        if "not modified" in str(e).lower():
            return
        try:
            await query.message.reply_text(texto, parse_mode="Markdown",
                                           reply_markup=_crear_teclado_principal())
        except Exception:
            pass
    except Exception:
        try:
            await query.message.reply_text(texto, parse_mode="Markdown",
                                           reply_markup=_crear_teclado_principal())
        except Exception:
            pass

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones inline."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        # Cualquier fallo al responder el callback (timeout de red, rate limit,
        # "Query is too old" u otro) NO debe matar el handler: el usuario debe
        # recibir igualmente la respuesta del menú (vía edit/send_message).
        logger.warning("query.answer() falló (se continúa el procesamiento): %s", e)

    try:
        user = update.effective_user
        usuario = await _registrar_usuario(context, user)
        usuario_id = usuario["id"]

        # --- Navegación guiada por menús (botones inline) ---
        if query.data.startswith("menu_"):
            if await menus.procesar_callback(query.data, query, context, usuario, usuario_id):
                return

        botones = _crear_teclado_principal()

        if query.data == "accion_balance":
            balance = database.obtener_balance(usuario_id)
            por_moneda = balance.get("por_moneda", {})

            lineas = [f"{formato.EMOJI_BALANCE} **Balance de {formato.nombre_mes_actual()}**", formato.SEPARADOR]
            if len(por_moneda) > 1 or (len(por_moneda) == 1 and list(por_moneda.keys()) != ["Sin moneda"]):
                for abrev, datos in por_moneda.items():
                    simbolo = datos.get("simbolo", "$")
                    neto_m = datos["ingresos"] - datos["gastos"]
                    lineas.append("")
                    lineas.append(f"**{abrev}**")
                    lineas.append(
                        f"{formato.EMOJI_INGRESO} {formato.fmt_moneda(datos['ingresos'], simbolo=simbolo)}   "
                        f"{formato.EMOJI_GASTO} {formato.fmt_moneda(datos['gastos'], simbolo=simbolo)}   "
                        f"→ **{formato.fmt_moneda(neto_m, simbolo=simbolo)}**"
                    )
            else:
                lineas.append(f"{formato.EMOJI_INGRESO} Ingresos: {formato.fmt_moneda(balance['ingresos'])}")
                lineas.append(f"{formato.EMOJI_GASTO} Gastos: {formato.fmt_moneda(balance['gastos'])}")
                lineas.append(f"Neto: **{formato.fmt_moneda(balance['neto'])}**")

            lineas.append("")
            lineas.append("¿Ver transacciones recientes o configurar un presupuesto?")
            mensaje = "\n".join(lineas)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=md_a_html(mensaje),
                parse_mode="HTML",
                reply_markup=botones,
            )

        elif query.data == "accion_transacciones":
            transacciones = database.obtener_transacciones(usuario_id, 5)
            if not transacciones:
                mensaje = "📝 No tienes transacciones registradas aún."
            else:
                mensaje = f"📝 **Tus últimas transacciones**\n{formato.SEPARADOR}\n\n"
                for t in transacciones:
                    tipo_icono = formato.EMOJI_INGRESO if t["tipo"] == "ingreso" else formato.EMOJI_GASTO
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
                    mensaje += f"{tipo_icono} {formato.fmt_moneda(t['cantidad'])} - {tipo_label}: {desc} ({fecha})\n"
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=md_a_html(mensaje),
                parse_mode="HTML",
                reply_markup=botones,
            )

        # === CALLBACKS DE MÚLTIPLES TRANSACCIONES ===
        elif query.data == "multi_confirm":
            transacciones_pendientes = context.user_data.get("multi_transacciones", [])
            if not transacciones_pendientes:
                await _responder_editando(query, "⚠️ No hay transacciones pendientes para guardar.")
                return
            resultado = knowledge._guardar_multi_transacciones(transacciones_pendientes, usuario)
            context.user_data.pop("multi_transacciones", None)
            await _responder_editando(query, resultado)

        elif query.data == "multi_cancel":
            context.user_data.pop("multi_transacciones", None)
            await _responder_editando(query, "❌ Transacciones canceladas. No se guardó nada.")

        elif query.data.startswith("multi_remove_"):
            idx = int(query.data.split("_")[-1])
            transacciones_pendientes = context.user_data.get("multi_transacciones", [])
            if 0 <= idx < len(transacciones_pendientes):
                eliminada = transacciones_pendientes.pop(idx)
                context.user_data["multi_transacciones"] = transacciones_pendientes

                if not transacciones_pendientes:
                    await _responder_editando(query, "❌ No quedan transacciones. Proceso cancelado.")
                    return

                preview = knowledge._formatear_preview_transacciones(transacciones_pendientes)
                botones_multi = _crear_botones_multi_transacciones(len(transacciones_pendientes))
                texto = (
                    f"🗑️ Eliminada: {formato.fmt_moneda(eliminada['cantidad'])} - "
                    f"{eliminada.get('descripcion', '')}\n\n{preview}"
                )
                await _responder_editando(query, texto, botones_multi)

        elif query.data.startswith("multi_edit_"):
            idx = int(query.data.split("_")[-1])
            transacciones_pendientes = context.user_data.get("multi_transacciones", [])
            if 0 <= idx < len(transacciones_pendientes):
                t = transacciones_pendientes[idx]
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=(
                        f"✏️ **Editando transacción {idx+1}:**\n"
                        f"{formato.EMOJI_INGRESO if t['tipo'] == 'ingreso' else formato.EMOJI_GASTO} "
                        f"{formato.fmt_moneda(t['cantidad'])} - {t.get('descripcion', '')}\n\n"
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
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    "➕ **Agregar moneda**\n\n"
                    "Elige una moneda común o agrégala manualmente:"
                ),
                parse_mode="Markdown",
                reply_markup=_crear_botones_moneda_presets(),
            )

        elif query.data.startswith("moneda_preset_"):
            clave = query.data.replace("moneda_preset_", "")
            preset = MONEDAS_PRESET.get(clave)
            if not preset:
                await _responder_editando(query, "❌ Opción inválida.")
                return
            monedas = database.obtener_monedas(usuario_id)
            existente = next(
                (m for m in monedas if m["abreviatura"].lower() == preset["abreviatura"].lower()),
                None,
            )
            if existente:
                await _responder_editando(
                    query,
                    f"📝 Ya tienes **{existente['nombre']} ({existente['abreviatura']})** "
                    f"en tus monedas.",
                )
                return
            database.crear_moneda(usuario_id, preset["nombre"], preset["simbolo"], preset["abreviatura"])
            await _responder_editando(
                query,
                f"✅ Moneda agregada: **{preset['simbolo']} {preset['nombre']} "
                f"({preset['abreviatura']})**.",
            )

        elif query.data == "moneda_manual":
            context.user_data["agregando_moneda_paso"] = 1
            context.user_data["agregando_moneda_datos"] = {}
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    "✍️ **Agregar moneda manualmente**\n\n"
                    "¿Cómo se llama la moneda?\n"
                    "(ej: Euro, Peso cubano, USDT)\n\n"
                    "Escribe `cancelar` para salir."
                ),
                parse_mode="Markdown",
            )

        elif query.data == "moneda_cancel":
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Operación cancelada.",
                reply_markup=_crear_teclado_principal(),
            )

        elif query.data == "monedaeliminar_menu":
            monedas = database.obtener_monedas(usuario_id)
            if not monedas:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="📝 No tienes monedas para eliminar.",
                )
                return
            filas = []
            for m in monedas:
                if m.get("es_default"):
                    continue
                filas.append([
                    InlineKeyboardButton(
                        f"{m['simbolo']} {m['nombre']} ({m['abreviatura']})",
                        callback_data=f"moneda_eliminar_{m['id']}",
                    )
                ])
            filas.append([InlineKeyboardButton("❌ Cancelar", callback_data="moneda_cancel")])
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    "🗑️ **Elige la moneda a eliminar:**\n\n"
                    "La moneda predeterminada no aparece porque no se puede eliminar."
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(filas),
            )

        elif query.data.startswith("moneda_eliminar_"):
            moneda_id_str = query.data.replace("moneda_eliminar_", "")
            monedas = database.obtener_monedas(usuario_id)
            moneda = next((m for m in monedas if str(m["id"]) == moneda_id_str), None)
            if not moneda:
                await _responder_editando(query, "❌ Esa moneda ya no existe.")
                return
            if moneda.get("es_default"):
                await _responder_editando(
                    query,
                    "⚠️ No puedes eliminar la moneda predeterminada.\n"
                    "Primero cambia la predeterminada a otra moneda.",
                )
                return
            database.eliminar_moneda(usuario_id, int(moneda_id_str))
            await _responder_editando(
                query,
                f"🗑️ Moneda eliminada: **{moneda['simbolo']} {moneda['nombre']} "
                f"({moneda['abreviatura']})**.",
            )

        elif query.data == "moneda_default_menu":
            monedas = database.obtener_monedas(usuario_id)
            if len(monedas) < 2:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="📝 Necesitas al menos 2 monedas para cambiar la predeterminada.",
                )
                return
            filas = []
            for m in monedas:
                if m.get("es_default"):
                    continue
                filas.append([
                    InlineKeyboardButton(
                        f"{m['simbolo']} {m['nombre']} ({m['abreviatura']})",
                        callback_data=f"moneda_default_{m['id']}",
                    )
                ])
            filas.append([InlineKeyboardButton("❌ Cancelar", callback_data="moneda_cancel")])
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⭐ **Elige la nueva moneda predeterminada:**",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(filas),
            )

        elif query.data.startswith("moneda_default_"):
            moneda_id_str = query.data.replace("moneda_default_", "")
            monedas = database.obtener_monedas(usuario_id)
            moneda = next((m for m in monedas if str(m["id"]) == moneda_id_str), None)
            if not moneda:
                await _responder_editando(query, "❌ Esa moneda ya no existe.")
                return
            database.establecer_moneda_default(usuario_id, int(moneda_id_str))
            await _responder_editando(
                query,
                f"⭐ **{moneda['nombre']} ({moneda['abreviatura']})** es ahora "
                f"tu moneda predeterminada.",
            )

        elif query.data.startswith("moneda_info_"):
            moneda_id_str = query.data.split("_")[-1]
            monedas = database.obtener_monedas(usuario_id)
            moneda = next((m for m in monedas if str(m["id"]) == moneda_id_str), None)
            if moneda:
                default = " ⭐ predeterminada" if moneda.get("es_default") else ""
                await _responder_editando(
                    query,
                    f"💱 **{moneda['nombre']}**\n\n"
                    f"  Símbolo: {moneda['simbolo']}\n"
                    f"  Abreviatura: {moneda['abreviatura']}{default}",
                )

        # === CALLBACKS DE TRANSACCIÓN PENDIENTE ===
        elif query.data in ("tipo_gasto", "tipo_ingreso"):
            pendiente = context.user_data.get("transaccion_pendiente")
            if not pendiente or pendiente.get("accion") != "elegir_tipo":
                await _responder_editando(query, "No hay ninguna transacción pendiente.")
                return
            tipo = "gasto" if query.data == "tipo_gasto" else "ingreso"
            try:
                texto = _completar_pendiente(pendiente, tipo, usuario)
            except Exception as e:
                logger.error("Error completando transacción pendiente: %s", e)
                texto = "❌ Ocurrió un error al registrar. Por favor, intenta de nuevo."
            context.user_data.pop("transaccion_pendiente", None)
            await _responder_editando(query, texto)

        elif query.data == "conf_exc_si":
            pendiente = context.user_data.get("transaccion_pendiente")
            if not pendiente or pendiente.get("accion") not in (
                "confirmar_gasto_excedido", "confirmar_gasto_balance"
            ):
                await _responder_editando(query, "No hay ninguna confirmación pendiente.")
                return
            presupuesto_id = pendiente.get("presupuesto_id")
            moneda_id = pendiente.get("moneda_id")
            presupuesto = None
            if presupuesto_id:
                presupuesto = next(
                    (p for p in database.obtener_presupuestos(usuario_id) if p["id"] == presupuesto_id),
                    None,
                )
            moneda = None
            if moneda_id:
                for m in database.obtener_monedas(usuario_id):
                    if m["id"] == moneda_id:
                        moneda = m
                        break
            try:
                texto, _ = knowledge._procesar_gasto(
                    pendiente.get("mensaje", ""), usuario,
                    moneda=moneda, presupuesto=presupuesto, forzar=True,
                )
            except Exception as e:
                logger.error("Error confirmando gasto excedido: %s", e)
                texto = "❌ Ocurrió un error al registrar. Por favor, intenta de nuevo."
            context.user_data.pop("transaccion_pendiente", None)
            await _responder_editando(query, texto)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="👇 Elige una opción o escríbeme en lenguaje natural:",
                reply_markup=_crear_teclado_principal(),
            )

        elif query.data.startswith("moneda_confirmar_"):
            moneda_id_str = query.data.replace("moneda_confirmar_", "")
            pendiente = context.user_data.get("transaccion_pendiente")
            if not pendiente or pendiente.get("accion") not in ("elegir_moneda", "elegir_moneda_presupuesto"):
                await _responder_editando(query, "No hay ninguna acción pendiente.")
                return
            monedas = database.obtener_monedas(usuario_id)
            moneda = next((m for m in monedas if str(m["id"]) == moneda_id_str), None)
            if not moneda:
                await _responder_editando(query, "❌ Esa moneda ya no existe.")
                return
            try:
                if pendiente.get("accion") == "elegir_moneda_presupuesto":
                    texto = _completar_pendiente_presupuesto(pendiente, moneda, usuario)
                else:
                    tipo = pendiente.get("tipo")
                    texto = _completar_pendiente(pendiente, tipo or "gasto", usuario, moneda=moneda)
            except Exception as e:
                logger.error("Error completando acción pendiente: %s", e)
                texto = "❌ Ocurrió un error. Por favor, intenta de nuevo."
            context.user_data.pop("transaccion_pendiente", None)
            await _responder_editando(query, texto)

        elif query.data == "pendiente_cancel":
            context.user_data.pop("transaccion_pendiente", None)
            await _responder_editando(query, "❌ Registro cancelado.")

        # === CALLBACKS DE ELIMINAR HISTORIAL (/delete) ===
        elif query.data == "delete_confirm":
            eliminadas = database.eliminar_transacciones(usuario_id)
            await _responder_editando(
                query,
                f"🗑️ **Historial eliminado.** Se borraron **{eliminadas}** transacciones.\n\n"
                f"Tu balance ahora está en $0.00.",
            )

        elif query.data == "delete_cancel":
            await _responder_editando(query, "❌ Operación cancelada.")

        # === CALLBACKS DE NOTIFICACIONES ===
        elif query.data == "notif_resumen":
            prefs = database.obtener_preferencias(usuario_id)
            database.guardar_preferencias(usuario_id, resumen_diario=not prefs.get("resumen_diario", False))
            texto, kb = _crear_menu_notificaciones(database.obtener_preferencias(usuario_id))
            await _responder_editando(query, texto, kb)

        elif query.data == "notif_menu":
            texto, kb = _crear_menu_notificaciones(database.obtener_preferencias(usuario_id))
            await _responder_editando(query, texto, kb)

        elif query.data == "notif_close":
            await _responder_editando(query, "🔔 Configuración de notificaciones cerrada.")

        elif query.data.startswith("notif_alerta_"):
            umbral = query.data.replace("notif_alerta_", "")
            clave = f"alerta_{umbral}"
            prefs = database.obtener_preferencias(usuario_id)
            database.guardar_preferencias(usuario_id, **{clave: not prefs.get(clave, True)})
            texto, kb = _crear_menu_notificaciones(database.obtener_preferencias(usuario_id))
            await _responder_editando(query, texto, kb)

        # === CALLBACKS DE ANUNCIO ===
        elif query.data == "anuncio_enviar":
            # Verificar que sea el admin
            if user.id != ADMIN_USER_ID:
                await _responder_editando(query, "🚫 No tienes permiso para realizar esta acción.")
                return

            mensaje_anuncio = context.user_data.pop("anuncio_pendiente", None)
            if not mensaje_anuncio:
                await _responder_editando(query, "⚠️ No hay anuncio pendiente para enviar.")
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

            await _responder_editando(
                query,
                f"✅ Anuncio enviado a **{enviados}** usuarios." + (f"\n⚠️ {fallidos} no pudieron recibirlo." if fallidos else ""),
            )

        elif query.data == "anuncio_cancelar":
            context.user_data.pop("anuncio_pendiente", None)
            await _responder_editando(query, "❌ Anuncio cancelado.")

        # === CALLBACKS DE EXPORTACIÓN ===
        elif query.data in ("exp_fmt_xlsx", "exp_fmt_csv"):
            exp_formato = "xlsx" if query.data == "exp_fmt_xlsx" else "csv"
            context.user_data["exp_formato"] = exp_formato
            etiqueta = "Excel (.xlsx)" if exp_formato == "xlsx" else "CSV"
            botones_periodo = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗓 Todo el historial", callback_data="exp_per_todo")],
                [InlineKeyboardButton("🗓 Este mes", callback_data="exp_per_mes")],
                [InlineKeyboardButton("🗓 Últimos 30 días", callback_data="exp_per_30")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="exp_cancel")],
            ])
            await _responder_editando(
                query,
                f"📤 Formato elegido: **{etiqueta}**\n\n¿Qué período quieres exportar?",
                botones_periodo,
            )

        elif query.data in ("exp_per_todo", "exp_per_mes", "exp_per_30"):
            exp_formato = context.user_data.get("exp_formato", "xlsx")
            periodo = {"exp_per_todo": "todo", "exp_per_mes": "mes", "exp_per_30": "30"}[query.data]
            context.user_data.pop("exp_formato", None)
            await _responder_editando(
                query,
                "📤 **Generando tu exportación...**\n\nPuede tardar unos segundos.",
            )
            await _enviar_exportacion(query.message, context, usuario, exp_formato, periodo)

        elif query.data == "exp_cancel":
            context.user_data.pop("exp_formato", None)
            await _responder_editando(query, "❌ Exportación cancelada.")

        # === CALLBACKS DE "VER TODAS" LAS TRANSACCIONES ===
        elif query.data.startswith("ver_todas"):
            context.user_data.pop("transaccion_pendiente", None)
            partes = query.data.split(":", 1)
            tipo_cb = partes[1] if len(partes) > 1 else "all"
            tipo_filtro = {"all": None, "gasto": "gasto", "ingreso": "ingreso"}.get(tipo_cb, None)
            texto = knowledge._procesar_transacciones_todas(usuario, tipo_filtro)
            await _responder_seguro(query.message, texto, reply_markup=_crear_teclado_principal())

    except Exception as e:
        logger.error("Error en callback query: %s", e)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⚠️ Ocurrió un error al procesar tu solicitud. Intenta de nuevo.",
            reply_markup=_crear_teclado_principal(),
        )