"""
handlers.py - Handlers para el bot de finanzas personales
Maneja comandos y mensajes en lenguaje natural para gestión financiera.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

import database
import knowledge
import ai_client
import changelog
from config import IMAGES_DIR, ADMIN_USER_ID

logger = logging.getLogger(__name__)

# === PALABRAS CLAVE PARA FINANZAS ===

REGISTRAR_KEYWORDS = [
    # Verbos de gasto
    "gasté", "gaste", "compré", "compre", "pagué", "pague",
    "costó", "costo", "invertí", "inverti",
    # Verbos de ingreso
    "recibí", "recibi", "ingresé", "ingrese", "cobré", "cobro",
    "gané", "gane", "agrega", "agregar",
    # Nombres de transacción (noun forms — IMPORTANT: "gasto" here ensures
    # "mi gasto de $50" is detected as registration, not consultation)
    "gasto", "gastos", "ingreso", "ingresos", "compra", "compras",
    "pago", "pagos", "inversión", "inversion",
    # Acciones genéricas
    "registrar", "registra", "agregar", "añadir", "guardar",
    # Categorías con monto implícito
    "salario", "bonifica", "remuner", "pension", "alquiler", "alquile",
    "renta", "rent", "hipoteca", "servicio", "transporte",
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
    "dame", "historial", "cuánto", "cuanto", "qué", "que",
    "cuales", "cuáles", "dónde", "donde", "cuántos",
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
    from datetime import timedelta
    hoy = datetime.now()
    textos_fecha = {
        "hoy": hoy.strftime("%Y-%m-%d"),
        "ayer": (hoy - timedelta(days=1)).strftime("%Y-%m-%d"),
        "anteayer": (hoy - timedelta(days=2)).strftime("%Y-%m-%d"),
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

    # Pregunta sobre uso del bot ("cómo", "qué puedo", "para qué sirve", etc.)
    # PRIORIDAD MÁXIMA — detectar ANTES de todo lo demás
    PATRONES_AYUDA = [
        r'\bcomo\s+(?:se\s+|lo\s+)?(?:hago|agrego|registro|gasto|ingreso|consulto|ver|veo|activo|configuro|elimino|borro|cambio|modifico|ahorro|presupuest)',
        r'\bcomo\s+(?:se\s+)?(?:hace|funciona|uso|trabaja|puedo)',
        r'\bpara\s+qu[eé]\s+(?:sirve|es|sirve\s+el)',
        r'\bqu[eé]\s+(?:puedo|hago|se|hace|funciona)',
        r'\bens\w*ame',
        r'\bexpl[ií]came',
        r'\bquiero\s+saber\s+como',
        r'\bc[oó]mo\s+(?:registro|agrego|gasto|consulto|veo|ahorro|activo|configuro|elimino|cambio|pongo|puedo)',
        r'\bqu[eé]\s+hace\s+el\s+bot',
        r'\bcomo\s+le\s+hago\s+para',
        r'\bcomo\s+se\s+(?:hace|usa|trabaja|configura)',
        r'\bpara\s+qu[eé]\s+es\s+(?:el\s+)?bot',
        r'\bqu[eé]\s+puedo\s+(?:hacer|hago)',
        r'\bquiero\s+saber\s+(?:que|hago|como)',
        r'\bens\w*ame\s+(?:a\s+)?(?:usar|configurar|modificar|eliminar|registrar)',
    ]
    es_pregunta_ayuda = any(re.search(p, texto_lower) for p in PATRONES_AYUDA)

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

    # Detectar preguntas de uso del bot → respuesta ayuda contextual
    if es_pregunta_ayuda:
        return "ayuda_uso"

    # Detectar configuración de presupuesto/ahorro ANTES de análisis por fecha
    # (porque "Mi presupuesto para comida es $500 este mes" tiene "este mes" pero es configuración)
    if es_registro:
        if any(kw in texto_lower for kw in PRESUPUESTO_KEYWORDS):
            return "configurar_presupuesto"
        if any(kw in texto_lower for kw in AHORRO_KEYWORDS):
            return "configurar_ahorro"

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
        tiene_contexto_financiero = es_consulta or any(w in texto_lower for w in [
            "gasto", "gastos", "ingreso", "ingresos", "transacci", "movimient",
            "cuánto", "cuanto", "qué", "que", "cuales", "cuáles", "dónde", "donde",
            "comí", "comi", "gasté", "gaste", "recibí", "recibi", "pagué", "pague",
            "compr", "cobr", "gananc", "balance", "resumen", "historial",
        ])
        if tiene_contexto_financiero:
            # Si hay verbo de registro + cantidad, es REGISTRO con fecha, no consulta
            TIPOS_VERBOS = ["gasté", "gaste", "compré", "compre", "pagué", "pague",
                           "recibí", "recibi", "ingresé", "ingrese", "cobré", "cobro",
                           "gané", "gane", "invertí", "inverti"]
            tiene_verbo_registro = any(re.search(r'\b' + v + r'\b', texto_lower) for v in TIPOS_VERBOS)
            tiene_cantidad = bool(re.search(r'\d+(?:[.,]\d+)?', texto_lower))
            if tiene_verbo_registro and tiene_cantidad:
                return "registrar_transaccion"
            return "analizar_por_fecha"

    # Detectar consultas ANTES del registro para que "cuánto gasto" sea consulta
    # PERO: si hay verbo de registro + cantidad, es REGISTRO, no consulta
    TIPOS_VERBOS_REGISTRO = ["gasté", "gaste", "compré", "compre", "pagué", "pague",
                             "recibí", "recibi", "ingresé", "ingrese", "cobré", "cobro",
                             "gané", "gane", "invertí", "inverti", "costó", "costo"]
    tiene_verbo_registro = any(re.search(r'\b' + v + r'\b', texto_lower) for v in TIPOS_VERBOS_REGISTRO)
    tiene_cantidad = bool(re.search(r'\d+(?:[.,]\d+)?', texto_lower))
    # "ingreso de 248.58 en mi saldo Qvapay" → nombre de transacción + cantidad = registro
    tiene_nombre_transaccion = any(kw in texto_lower for kw in ["ingreso", "ingresos", "gasto", "gastos",
                                                                  "compra", "compras", "pago", "pagos"])

    if tiene_verbo_registro and tiene_cantidad:
        return "registrar_transaccion"
    if tiene_nombre_transaccion and tiene_cantidad:
        return "registrar_transaccion"

    if es_consulta or "como" in texto_lower or "cual" in texto_lower:
        if any(w in texto_lower for w in ["balance", "saldo", "resumen"]):
            return "consultar_balance"
        if any(w in texto_lower for w in ["categoria", "categoria"]):
            return "consultar_categorias"
        if any(w in texto_lower for w in ["presupuesto", "presupuestos", "budget"]):
            return "consultar_presupuesto"
        if any(w in texto_lower for w in ["ahorro", "ahorros", "meta de ahorro"]):
            return "consultar_ahorro"
        # "cuánto gasto" / "qué gasté" = consulta, NO registro
        if any(w in texto_lower for w in ["cuánto", "cuanto", "qué", "que", "cuales", "cuáles"]):
            if "gasto" in texto_lower or "gastos" in texto_lower or "gasté" in texto_lower or "gaste" in texto_lower:
                return "consultar_gastos"
            if "ingreso" in texto_lower or "ingresos" in texto_lower:
                return "consultar_ingresos"
        # "ver gastos" / "mostrar gastos" = consulta
        if any(w in texto_lower for w in ["ver", "mostrar", "mostrarme", "muestra", "muestrame", "listar", "dame"]):
            if "gasto" in texto_lower or "gastos" in texto_lower:
                return "consultar_gastos"
            if "ingreso" in texto_lower or "ingresos" in texto_lower:
                return "consultar_ingresos"
        if any(w in texto_lower for w in ["transacci", "historial", "movimient", "operacion", "registro"]):
            return "consultar_transacciones"

    # Fallback: presupuesto/ahorro sin verbo de registro explícito
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

    tipo = None

    # Keywords de gasto (usan word boundaries para evitar falsos positivos como "gestión")
    GASTO_KEYWORDS = [
        "gasté", "gaste", "gasto", "gastos", "compré", "compre", "compra", "compras",
        "pagué", "pague", "pago", "pagos", "costó", "costo", "pagar", "invertí", "inverti",
        "inversión", "inversion", "invierto",
    ]
    # Keywords de ingreso
    INGRESO_KEYWORDS = [
        "recibí", "recibi", "ingresé", "ingrese", "ingreso", "ingresos",
        "salario", "sueldo", "cobré", "cobro", "cobrar", "cobrado",
        "gané", "gane", "bonus", "bono", "bonificación", "bonificacion",
        "regalo", "dividendos", "intereses", "remuneración", "remuneracion",
        "herencia", "ventas", "facturé", "facture", "facturado",
    ]
    # "agrega"/"agregar" es exclusivo de ingreso cuando no hay keyword de gasto explícito
    AGREGAR_KEYWORDS = ["agrega", "agregar", "añadir", "sumar", "guardar"]

    tiene_gasto_explicito = any(re.search(r'\b' + kw + r'\b', texto_lower) for kw in GASTO_KEYWORDS)
    tiene_ingreso_explicito = any(re.search(r'\b' + kw + r'\b', texto_lower) for kw in INGRESO_KEYWORDS)
    tiene_agregar = any(re.search(r'\b' + kw + r'\b', texto_lower) for kw in AGREGAR_KEYWORDS)

    if tiene_gasto_explicito:
        tipo = "gasto"
    elif tiene_ingreso_explicito:
        tipo = "ingreso"
    elif tiene_agregar:
        tipo = "ingreso"
    else:
        # Fallback ampliado: indicadores de contexto
        GASTO_CONTEXTO = [
            "en ", "para ", "de ", "por ", "sobre ",
            "comida", "transporte", "gasolina", "supermercado", "servicio",
            "alquiler", "renta", "luz", "agua", "internet", "teléfono",
            "ropa", "zapatos", "médico", "farmacia", "doctor",
            "Netflix", "Spotify", "Netflix", "uber", "taxi",
        ]
        INGRESO_CONTEXTO = [
            "de salario", "de pago", "de inversión", "de trading",
            "de dividendos", "de intereses", "de regalo", "de venta",
            "de alquiler", "de renta", "de comisión",
        ]
        if any(w in texto_lower for w in GASTO_CONTEXTO):
            tipo = "gasto"
        elif any(w in texto_lower for w in INGRESO_CONTEXTO):
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start."""
    try:
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
            nueva = knowledge._parsear_multi_transaccion(mensaje)
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
        transacciones = knowledge._parsear_multi_transaccion(mensaje)
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
            f"👤 **Usuario:** {user.first_name}\n"
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


async def _procesar_transaccion_finanzas(fecha, tipo, cantidad, descripcion):
    """Procesa una transacción financiera."""
    return f"✅ Transacción registrada: ${cantidad:.2f} en '{descripcion}'"


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