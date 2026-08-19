"""
menus.py - Navegación guiada con botones inline.

Menú principal con 7 secciones (Balance, Presupuestos, Ahorros, Monedas,
Transacciones, Ayuda, Más opciones) y flujos completos por botón.
La IA / lenguaje natural sigue disponible en todo momento: los botones que
necesitan datos lanzan un prompt con un ejemplo para que el usuario escriba.
"""

import logging
from typing import Dict, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

import database
import formato
import knowledge

logger = logging.getLogger(__name__)

# ============================================================
# CALLBACKS
# ============================================================
CB_INICIO = "menu_inicio"
CB_BALANCE = "menu_balance"
CB_PRESUP = "menu_presupuestos"
CB_AHORROS = "menu_ahorros"
CB_MONEDAS = "menu_monedas"
CB_TRANS = "menu_transacciones"
CB_AYUDA = "menu_ayuda"
CB_MAS = "menu_mas"

# Sub-acciones
CB_BALANCE_GASTOS = "menu_balance_gastos"
CB_BALANCE_INGRESOS = "menu_balance_ingresos"

CB_PRESUP_QUEDAN = "menu_presupuestos_quedan"
CB_PRESUP_GASTOS_POR = "menu_presupuestos_gastos_por"
CB_PRESUP_NUEVO = "menu_presupuestos_nuevo"
CB_PRESUP_SEL = "menu_presupuesto_sel_"

CB_AHORROS_CREAR = "menu_ahorros_crear"
CB_AHORROS_AGREGAR = "menu_ahorros_agregar"
CB_AHORROS_ELIMINAR = "menu_ahorros_eliminar"
CB_AHORROS_ELIM_TODAS = "menu_ahorros_eliminar_todas"
CB_AHORRO_ADD = "menu_ahorro_add_"
CB_AHORRO_DEL = "menu_ahorro_del_"
CB_AHORRO_DEL_CONF = "menu_ahorro_del_confirm_"
CB_AHORRO_DEL_ALL_CONF = "menu_ahorro_del_all_confirm"

CB_TRANS_GASTOS = "menu_transacciones_gastos"
CB_TRANS_INGRESOS = "menu_transacciones_ingresos"
CB_TRANS_GASTO = "menu_transacciones_gasto"
CB_TRANS_INGRESO = "menu_transacciones_ingreso"

CB_AYUDA_REGISTRAR = "menu_ayuda_registrar"
CB_AYUDA_BALANCE = "menu_ayuda_balance"
CB_AYUDA_PRESUP = "menu_ayuda_presupuesto"
CB_AYUDA_AHORRO = "menu_ayuda_ahorro"
CB_AYUDA_COMANDOS = "menu_ayuda_comandos"

CB_MAS_NOTIF = "menu_mas_notificaciones"
CB_MAS_EXPORTAR = "menu_mas_exportar"
CB_MAS_RESUMEN = "menu_mas_resumen"
CB_MAS_BORRAR = "menu_mas_borrar"
CB_DELETE_CONF = "menu_delete_confirm"
CB_DELETE_CANCEL = "menu_delete_cancel"


def _kb(filas) -> InlineKeyboardMarkup:
    """Construye un InlineKeyboardMarkup a partir de filas [(etiqueta, callback)]."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=cb) for label, cb in fila]
        for fila in filas
    ])


def _con_botones(texto: str, filas, volver: str = CB_INICIO, inicio: bool = True) -> Tuple[str, InlineKeyboardMarkup]:
    """Adjunta botones de navegación (Volver + Inicio) a un texto."""
    filas = [list(f) for f in filas]
    pie = [("🔙 Volver", volver)]
    if inicio:
        pie.append(("🏠 Inicio", CB_INICIO))
    filas.append(pie)
    return texto, _kb(filas)


# ============================================================
# MENÚ PRINCIPAL
# ============================================================

def teclado_principal() -> InlineKeyboardMarkup:
    """Los 7 botones principales."""
    return _kb([
        [("💰 Balance", CB_BALANCE), ("📊 Presupuestos", CB_PRESUP)],
        [("🎯 Ahorros", CB_AHORROS), ("💱 Monedas", CB_MONEDAS)],
        [("📋 Transacciones", CB_TRANS), ("❓ Ayuda", CB_AYUDA)],
        [("⚙️ Más opciones", CB_MAS)],
    ])


def menu_inicio() -> Tuple[str, InlineKeyboardMarkup]:
    """Pantalla principal."""
    texto = (
        f"🏠 **Menú principal**\n{formato.SEPARADOR}\n"
        "Elige una sección con los botones para navegar guiado, "
        "o escríbeme directamente en lenguaje natural "
        "(ej: `gasté $50 en comida`).\n\n"
        "🤖 La IA está siempre disponible."
    )
    return texto, teclado_principal()


# ============================================================
# SECCIONES
# ============================================================

def menu_balance(usuario: dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Balance del mes + acciones (sin botón 'Ver': el contenido va directo)."""
    return _con_botones(
        knowledge._procesar_balance(usuario),
        [
            [("📉 Ver gastos", CB_BALANCE_GASTOS), ("📈 Ver ingresos", CB_BALANCE_INGRESOS)],
        ],
    )


def menu_presupuestos(usuario: dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Presupuestos actuales + acciones."""
    return _con_botones(
        knowledge._procesar_presupuestos(usuario),
        [
            [("🔄 Restante de un presupuesto", CB_PRESUP_QUEDAN)],
            [("📉 Gastos por presupuestos", CB_PRESUP_GASTOS_POR)],
            [("➕ Crear presupuesto", CB_PRESUP_NUEVO)],
        ],
    )


def menu_ahorros(usuario: dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Metas de ahorro actuales + acciones."""
    return _con_botones(
        knowledge._procesar_metas_ahorro(usuario),
        [
            [("➕ Crear meta", CB_AHORROS_CREAR)],
            [("💵 Agregar dinero a una meta", CB_AHORROS_AGREGAR)],
            [("🗑️ Eliminar una meta", CB_AHORROS_ELIMINAR)],
            [("🧹 Eliminar todas las metas", CB_AHORROS_ELIM_TODAS)],
        ],
    )


def _texto_monedas(usuario: dict) -> str:
    monedas = database.obtener_monedas(usuario["id"])
    if not monedas:
        return f"💱 **Tus monedas:**\n\n📝 Aún no tienes monedas configuradas."
    lineas = [f"{formato.EMOJI_MONEDA} **Tus monedas**", formato.SEPARADOR]
    for m in monedas:
        default = " ⭐ predeterminada" if m.get("es_default") else ""
        lineas.append(f"  {m['simbolo']} {m['nombre']} ({m['abreviatura']}){default}")
    return "\n".join(lineas)


def menu_monedas(usuario: dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Monedas actuales + acciones."""
    return _con_botones(
        _texto_monedas(usuario),
        [
            [("➕ Agregar moneda", "moneda_agregar")],
            [("🗑️ Eliminar moneda", "monedaeliminar_menu")],
            [("⭐ Predeterminada", "moneda_default_menu")],
        ],
    )


def menu_transacciones(usuario: dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Últimas transacciones + acciones."""
    return _con_botones(
        knowledge._procesar_transacciones(usuario),
        [
            [("📉 Ver gastos", CB_TRANS_GASTOS), ("📈 Ver ingresos", CB_TRANS_INGRESOS)],
            [("➕ Registrar gasto", CB_TRANS_GASTO)],
            [("➕ Registrar ingreso", CB_TRANS_INGRESO)],
        ],
    )


def menu_ayuda() -> Tuple[str, InlineKeyboardMarkup]:
    return _con_botones(
        f"❓ **Ayuda**\n{formato.SEPARADOR}\n¿Sobre qué necesitas orientación?",
        [
            [("✏️ Registrar gasto/ingreso", CB_AYUDA_REGISTRAR)],
            [("💰 Ver balance", CB_AYUDA_BALANCE)],
            [("📊 Crear presupuesto", CB_AYUDA_PRESUP)],
            [("🎯 Crear metas", CB_AYUDA_AHORRO)],
            [("📚 Todos los comandos", CB_AYUDA_COMANDOS)],
        ],
    )


def menu_mas() -> Tuple[str, InlineKeyboardMarkup]:
    return _con_botones(
        f"⚙️ **Más opciones**\n{formato.SEPARADOR}\nOtras herramientas:",
        [
            [("🔔 Notificaciones", CB_MAS_NOTIF)],
            [("📤 Exportar", CB_MAS_EXPORTAR)],
            [("📅 Resumen del mes", CB_MAS_RESUMEN)],
            [("🗑️ Borrar historial", CB_MAS_BORRAR)],
        ],
    )


# ============================================================
# SUB-SELECCIONES
# ============================================================

def menu_presupuestos_quedan(usuario: dict) -> Tuple[str, InlineKeyboardMarkup]:
    presupuestos = database.obtener_presupuestos(usuario["id"])
    if not presupuestos:
        return (
            f"📊 No tienes presupuestos configurados.\n\n"
            "Crea uno con: `Mi presupuesto para comida es $500`",
            teclado_principal(),
        )
    filas = [[(f"{p.get('nombre') or p.get('categoria_nombre', '?')}", f"{CB_PRESUP_SEL}{p['id']}")] for p in presupuestos]
    return _con_botones(
        f"📊 **¿De cuál presupuesto quieres ver el restante?**\n{formato.SEPARADOR}",
        filas,
        volver=CB_PRESUP,
    )


def menu_ahorros_agregar(usuario: dict) -> Tuple[str, InlineKeyboardMarkup]:
    metas = database.obtener_metas_ahorro(usuario["id"])
    if not metas:
        return (
            f"🎯 No tienes metas de ahorro.\n\n"
            "Crea una con: `Quiero ahorrar $5000 para vacaciones`",
            teclado_principal(),
        )
    filas = [[(m["nombre"], f"{CB_AHORRO_ADD}{m['id']}")] for m in metas]
    return _con_botones(
        f"💵 **¿A qué meta quieres agregar dinero?**\n{formato.SEPARADOR}",
        filas,
        volver=CB_AHORROS,
    )


def menu_ahorros_eliminar(usuario: dict) -> Tuple[str, InlineKeyboardMarkup]:
    metas = database.obtener_metas_ahorro(usuario["id"])
    if not metas:
        return (
            f"🎯 No tienes metas de ahorro que eliminar.",
            teclado_principal(),
        )
    filas = [[(m["nombre"], f"{CB_AHORRO_DEL}{m['id']}")] for m in metas]
    return _con_botones(
        f"🗑️ **¿Cuál meta quieres eliminar?**\n{formato.SEPARADOR}",
        filas,
        volver=CB_AHORROS,
    )


def _confirmar_eliminar_meta(usuario: dict, meta_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    meta = next(
        (m for m in database.obtener_metas_ahorro(usuario["id"]) if m["id"] == meta_id),
        None,
    )
    if not meta:
        return menu_ahorros()
    nombre = meta.get("nombre", "Meta")
    return _con_botones(
        f"{formato.EMOJI_ADVERTENCIA} **¿Eliminar la meta de ahorro** _{nombre}_ **?**",
        [[("✅ Sí, eliminar", f"{CB_AHORRO_DEL_CONF}{meta_id}")]],
        volver=CB_AHORROS,
        inicio=False,
    )


def _confirmar_eliminar_todas_metas() -> Tuple[str, InlineKeyboardMarkup]:
    return _con_botones(
        f"{formato.EMOJI_ADVERTENCIA} **¿Eliminar TODAS tus metas de ahorro?**\n"
        "Esta acción no se puede deshacer.",
        [[("✅ Sí, eliminar todas", CB_AHORRO_DEL_ALL_CONF)]],
        volver=CB_AHORROS,
        inicio=False,
    )


def _confirmar_borrar_historial() -> Tuple[str, InlineKeyboardMarkup]:
    return _con_botones(
        f"{formato.EMOJI_ADVERTENCIA} **¿Borrar TODO tu historial de transacciones?**\n"
        "Se eliminarán todas tus transacciones y el balance quedará en $0.00.\n"
        "Esta acción no se puede deshacer.",
        [[("✅ Sí, borrar todo", CB_DELETE_CONF)]],
        volver=CB_MAS,
        inicio=False,
    )


# ============================================================
# PROMPTS DE LENGUAJE NATURAL
# ============================================================

def _prompt(texto: str, volver: str) -> Tuple[str, InlineKeyboardMarkup]:
    return texto, _kb([[("🔙 Volver", volver)]])


def prompt_presupuesto_nuevo() -> Tuple[str, InlineKeyboardMarkup]:
    return _prompt(
        f"📊 **Configura tu presupuesto**\n\n"
        "Envíame el monto y la categoría, por ejemplo:\n"
        "`Mi presupuesto para comida es $500 este mes`\n\n"
        "También puedo sumar a uno existente:\n"
        "`Añade 200 al presupuesto de comida`",
        CB_PRESUP,
    )


def prompt_ahorro_crear() -> Tuple[str, InlineKeyboardMarkup]:
    return _prompt(
        f"🎯 **Crea tu meta de ahorro**\n\n"
        "Envíame el objetivo, por ejemplo:\n"
        "`Quiero ahorrar $5000 para vacaciones`",
        CB_AHORROS,
    )


def prompt_ahorro_agregar(meta: dict) -> Tuple[str, InlineKeyboardMarkup]:
    nombre = meta.get("nombre", "tu meta")
    return _prompt(
        f"💵 **Agregar dinero a la meta _{nombre}_**\n\n"
        f"Envíame el monto, por ejemplo:\n"
        f"`Agrega 500 a la meta de ahorro {nombre}`",
        CB_AHORROS,
    )


def prompt_transaccion_gasto() -> Tuple[str, InlineKeyboardMarkup]:
    return _prompt(
        f"📉 **Registrar un gasto**\n\n"
        "Envíame la descripción, por ejemplo:\n"
        "`Gasté $50 en comida`",
        CB_TRANS,
    )


def prompt_transaccion_ingreso() -> Tuple[str, InlineKeyboardMarkup]:
    return _prompt(
        f"📈 **Registrar un ingreso**\n\n"
        "Envíame la descripción, por ejemplo:\n"
        "`Recibí $200 de salario`",
        CB_TRANS,
    )


# ============================================================
# TEXTO DE AYUDA COMPLETO (/help)
# ============================================================

TEXTO_HELP = (
    "🤖 **Comandos disponibles:**\n\n"
    "• `/start` - Iniciar/Reiniciar el bot\n"
    "• `/user` - Ver información de usuario\n"
    "• `/resumen` - Resumen del mes actual\n"
    "• `/categorias` - Ver tus categorías financieras\n"
    "• `/gastos` - Ver tus últimos gastos\n"
    "• `/ingresos` - Ver tus últimos ingresos\n"
    "• `/metas` - Ver tus metas de ahorro\n"
    "• `/notificaciones` - Alertas de presupuesto y resumen diario (21:30 hora de Cuba)\n"
    "• `/exportar` - Exporta tus datos a Excel/CSV (ej: `/exportar csv 2026-07`)\n"
    "• `/help` - Ver esta ayuda\n"
    "• `/delete` - Borrar todo el historial de transacciones\n\n"
    "📝 **Ejemplos de lenguaje natural:**\n"
    "• 'Gasté $50 en comida para el desayuno'\n"
    "• 'Recibí $2000 de salario'\n"
    "• 'Mi presupuesto para comida es $500 este mes'\n"
    "• 'Quiero ahorrar $5000 para unas vacaciones'\n"
    "• '¿Cuál es mi balance actual?'\n"
    "• 'Exporta mis datos del mes'\n\n"
    "✏️ **Modificar datos:**\n"
    "• 'Cambia el gasto de $50 a ingreso'\n"
    "• 'Modifica la descripción de mi último gasto'\n"
    "• 'Cambia el monto de $100 a $150'\n"
    "• 'Elimina la transacción de $30'\n"
    "• 'Pasa ese gasto a la categoría transporte'"
)


def _texto_ayuda_uso(mensaje_ia: str) -> str:
    try:
        return knowledge._responder_ayuda_uso(mensaje_ia)
    except Exception as e:
        logger.error("Error generando ayuda: %s", e)
        return TEXTO_HELP


# ============================================================
# DISPATCHER DE CALLBACKS
# ============================================================

def _render(data: str, usuario: dict) -> Optional[Tuple[str, InlineKeyboardMarkup]]:
    """Calcula (texto, botones) para un callback de menú. None si no es de menú."""
    # Navegación
    if data == CB_INICIO:
        return menu_inicio()
    if data == CB_BALANCE:
        return menu_balance(usuario)
    if data == CB_PRESUP:
        return menu_presupuestos(usuario)
    if data == CB_AHORROS:
        return menu_ahorros(usuario)
    if data == CB_MONEDAS:
        return menu_monedas(usuario)
    if data == CB_TRANS:
        return menu_transacciones(usuario)
    if data == CB_AYUDA:
        return menu_ayuda()
    if data == CB_MAS:
        return menu_mas()

    # Balance
    if data == CB_BALANCE_GASTOS:
        return _con_botones(knowledge._procesar_gastos(usuario), [], volver=CB_BALANCE)
    if data == CB_BALANCE_INGRESOS:
        return _con_botones(knowledge._procesar_ingresos(usuario), [], volver=CB_BALANCE)

    # Presupuestos
    if data == CB_PRESUP_QUEDAN:
        return menu_presupuestos_quedan(usuario)
    if data == CB_PRESUP_GASTOS_POR:
        texto = knowledge._procesar_gastos_por_presupuestos(usuario, "cuánto gasté de mis presupuestos")
        return _con_botones(texto, [], volver=CB_PRESUP)
    if data == CB_PRESUP_NUEVO:
        return prompt_presupuesto_nuevo()
    if data.startswith(CB_PRESUP_SEL):
        try:
            pid = int(data[len(CB_PRESUP_SEL):])
            p = next((x for x in database.obtener_presupuestos(usuario["id"]) if x["id"] == pid), None)
            nombre = (p.get("nombre") or p.get("categoria_nombre")) if p else None
            if not nombre:
                return menu_presupuestos_quedan(usuario)
            texto = knowledge._procesar_presupuesto_especifico(usuario, nombre)
        except Exception as e:
            logger.error("Error en presupuesto específico: %s", e)
            texto = "❌ Ocurrió un error al consultar el presupuesto."
        return _con_botones(texto, [], volver=CB_PRESUP)

    # Ahorros
    if data == CB_AHORROS_CREAR:
        return prompt_ahorro_crear()
    if data == CB_AHORROS_AGREGAR:
        return menu_ahorros_agregar(usuario)
    if data == CB_AHORROS_ELIMINAR:
        return menu_ahorros_eliminar(usuario)
    if data == CB_AHORROS_ELIM_TODAS:
        return _confirmar_eliminar_todas_metas()
    if data.startswith(CB_AHORRO_ADD):
        try:
            mid = int(data[len(CB_AHORRO_ADD):])
            meta = next((m for m in database.obtener_metas_ahorro(usuario["id"]) if m["id"] == mid), None)
            if not meta:
                return menu_ahorros_agregar(usuario)
            return prompt_ahorro_agregar(meta)
        except Exception:
            return menu_ahorros_agregar(usuario)
    if data == CB_AHORRO_DEL_ALL_CONF:
        texto = knowledge._procesar_eliminar_todas_metas(usuario)
        return _con_botones(texto, [], volver=CB_AHORROS)
    if data.startswith(CB_AHORRO_DEL_CONF):
        try:
            mid = int(data[len(CB_AHORRO_DEL_CONF):])
            meta = next((m for m in database.obtener_metas_ahorro(usuario["id"]) if m["id"] == mid), None)
            nombre = meta.get("nombre", "") if meta else ""
            texto = knowledge._procesar_eliminar_meta(usuario, nombre)
        except Exception as e:
            logger.error("Error eliminando meta: %s", e)
            texto = "❌ Ocurrió un error al eliminar la meta."
        return _con_botones(texto, [], volver=CB_AHORROS)
    if data.startswith(CB_AHORRO_DEL):
        try:
            mid = int(data[len(CB_AHORRO_DEL):])
            return _confirmar_eliminar_meta(usuario, mid)
        except Exception:
            return menu_ahorros_eliminar(usuario)

    # Transacciones
    if data == CB_TRANS_GASTOS:
        return _con_botones(knowledge._procesar_gastos(usuario), [], volver=CB_TRANS)
    if data == CB_TRANS_INGRESOS:
        return _con_botones(knowledge._procesar_ingresos(usuario), [], volver=CB_TRANS)
    if data == CB_TRANS_GASTO:
        return prompt_transaccion_gasto()
    if data == CB_TRANS_INGRESO:
        return prompt_transaccion_ingreso()

    # Ayuda
    if data == CB_AYUDA_REGISTRAR:
        return _con_botones(_texto_ayuda_uso("cómo registro un gasto"), [], volver=CB_AYUDA)
    if data == CB_AYUDA_BALANCE:
        return _con_botones(_texto_ayuda_uso("cómo veo mi balance"), [], volver=CB_AYUDA)
    if data == CB_AYUDA_PRESUP:
        return _con_botones(_texto_ayuda_uso("cómo configuro un presupuesto"), [], volver=CB_AYUDA)
    if data == CB_AYUDA_AHORRO:
        return _con_botones(_texto_ayuda_uso("cómo creo una meta de ahorro"), [], volver=CB_AYUDA)
    if data == CB_AYUDA_COMANDOS:
        return _con_botones(TEXTO_HELP, [], volver=CB_AYUDA)

    # Más opciones
    if data == CB_MAS_NOTIF:
        try:
            from handlers import _crear_menu_notificaciones
            prefs = database.obtener_preferencias(usuario["id"])
            return _crear_menu_notificaciones(prefs)
        except Exception as e:
            logger.error("Error abriendo notificaciones: %s", e)
            return _con_botones("❌ Ocurrió un error al abrir notificaciones.", [], volver=CB_MAS)
    if data == CB_MAS_EXPORTAR:
        return (
            "📤 **¿En qué formato quieres exportar tus datos?**",
            _kb([
                [("📊 Excel (.xlsx)", "exp_fmt_xlsx"), ("📄 CSV", "exp_fmt_csv")],
                [("🔙 Volver", CB_MAS)],
            ]),
        )
    if data == CB_MAS_RESUMEN:
        return _con_botones(knowledge._procesar_resumen_mensual(usuario), [], volver=CB_MAS)
    if data == CB_MAS_BORRAR:
        return _confirmar_borrar_historial()
    if data == CB_DELETE_CONF:
        eliminadas = database.eliminar_transacciones(usuario["id"])
        texto = f"🗑️ **Historial eliminado.** Se borraron **{eliminadas}** transacciones.\n\nTu balance ahora está en $0.00."
        return _con_botones(texto, [], volver=CB_MAS)
    if data == CB_DELETE_CANCEL:
        return _con_botones("❌ Operación cancelada.", [], volver=CB_MAS)

    return None


async def _editar(query, texto: str, kb: InlineKeyboardMarkup) -> None:
    """Edita el mensaje del botón con el nuevo contenido (fallback: mensaje nuevo)."""
    if kb is None:
        kb = InlineKeyboardMarkup([])
    try:
        await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=kb)
    except BadRequest as e:
        if "not modified" in str(e).lower():
            return
        try:
            await query.message.reply_text(texto, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass
    except Exception:
        try:
            await query.message.reply_text(texto, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass


async def procesar_callback(data: str, query, context, usuario: dict, usuario_id: int) -> bool:
    """Maneja un callback de menú. Retorna True si lo procesó."""
    try:
        render = _render(data, usuario)
        if render is None:
            return False
        texto, kb = render
        await _editar(query, texto, kb)
        return True
    except Exception as e:
        logger.error("Error en callback de menú %s: %s", data, e)
        try:
            from handlers import _crear_teclado_principal
            await query.edit_message_text(
                "⚠️ Ocurrió un error al procesar la opción. Intenta de nuevo.",
                parse_mode="Markdown",
                reply_markup=_crear_teclado_principal(),
            )
        except Exception:
            pass
        return True
