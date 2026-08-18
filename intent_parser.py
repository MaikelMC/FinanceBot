"""
intent_parser.py - Motor de análisis de intención unificado.
Usa IA como sistema primario y regex como fast-path cache para mensajes predecibles.
"""

import json
import logging
import re
from typing import Any, Dict, Optional

import config

logger = logging.getLogger(__name__)

# Cache simple: hash del mensaje -> resultado del análisis
_INTENT_CACHE: Dict[int, Dict[str, Any]] = {}

# ============================================================
# FAST-PATH: Regex para mensajes ultra-predecibles (>95% certeza)
# ============================================================

def _parse_float(texto: str) -> Optional[float]:
    from knowledge import _parsear_cantidad
    return _parsear_cantidad(texto)


def _subconsulta_gasto_ingreso(texto: str) -> str:
    """Distingue subconsulta: 'gastos', 'ingresos' o 'transacciones'."""
    lower = texto.lower()
    if "gastos" in lower:
        return "gastos"
    if "ingresos" in lower:
        return "ingresos"
    return "transacciones"


def _build_exportar(mensaje: str) -> Dict[str, Any]:
    """Construye el resultado del fast-path para exportación."""
    from exportador import _detectar_formato, mapear_periodo_ia
    return {
        "intencion": "exportar",
        "formato": _detectar_formato(mensaje),
        "fecha": mapear_periodo_ia(None, mensaje),
        "confianza": 0.9,
    }


_FAST_PATTERNS = [
    # --- EXPORTAR ---
    (re.compile(r'^\s*(?:exporta|exportar|descarga|descargar)\b.*', re.IGNORECASE),
     lambda m: _build_exportar(m.string)),
    # --- REGISTRO: gasto explícito ---
    (re.compile(r'(?:gast[ée]?|compr[ée]?|pagu?[ée]?|cost[óo]|invert[ií])\s+\$?([\d,.]+)\s+(?:en\s+|para\s+)?(.+)', re.IGNORECASE),
     lambda m: {"intencion": "registrar", "tipo": "gasto", "cantidad": _parse_float(m.group(1)), "descripcion": m.group(2).strip(), "categoria": None, "confianza": 0.98}),

    # --- REGISTRO: ingreso explícito ---
    (re.compile(r'(?:recib[ií]|ingres[ée]?|cobr[ée]?|gan[ée]?)\s+\$?([\d,.]+)\s+(?:de\s+|como\s+)?(.+)', re.IGNORECASE),
     lambda m: {"intencion": "registrar", "tipo": "ingreso", "cantidad": _parse_float(m.group(1)), "descripcion": m.group(2).strip(), "categoria": None, "confianza": 0.98}),

    # --- CONFIGURAR: ahorro/meta ---
    # Va antes del formato corto para que "quiero ahorrar X para Y" no se interprete como registro
    (re.compile(r'(?:quiero\s+)?ahorrar\s+\$?([\d,.]+)\s+(?:para\s+|de\s+)?(.+)', re.IGNORECASE),
     lambda m: {"intencion": "configurar_ahorro", "cantidad": _parse_float(m.group(1)), "descripcion": m.group(2).strip(), "confianza": 0.96}),

    # --- CONFIGURAR: agregar dinero a una meta de ahorro existente ---
    # "agrega 900 cup a la meta de ahorro del regalo de mi novia", "suma 500 a mi meta del carro"
    (re.compile(r'\b(?:a[ñn]ade|agrega|suma|m[ée]tele|pon(?:le)?)\s+\$?([\d.,]+)\s+([a-z]{2,8}\s+)?(?:a\s+|al\s+|a\s+la\s+)?(?:mi\s+|la\s+|el\s+)?(?:meta\s+de\s+ahorro|meta\s+de\s+ahorros|meta\s+de\s+objetivo|meta\s+|ahorro)\s+(?:de\s+|del\s+|para\s+|en\s+)?(.+)', re.IGNORECASE),
     lambda m: {"intencion": "agregar_ahorro", "cantidad": _parse_float(m.group(1)), "moneda": (m.group(2) or "").strip().lower() or None, "descripcion": m.group(3).strip(), "confianza": 0.97}),

    # --- CONFIGURAR: presupuesto ---
    # Va antes del formato corto de registro para que "presupuesto de 1000 para X"
    # no se interprete como una transacción.
    # Formato: "presupuesto para X es/de $Y" (categoría antes del monto)
    (re.compile(r'(?:mi\s+)?presupuesto\s+(?:para|de)\s+(.+?)\s+(?:es|de)\s+\$?([\d,.]+)', re.IGNORECASE),
     lambda m: {"intencion": "configurar_presupuesto", "categoria": m.group(1).strip(), "nombre": m.group(1).strip(), "cantidad": _parse_float(m.group(2)), "modo_presupuesto": "reemplazar", "confianza": 0.98}),
    # Formato: "presupuesto de $Y [moneda] para/en X" (monto antes de la categoría)
    (re.compile(r'\bpresupuesto\s+(?:de\s+)?\$?([\d.,]+)\s+(?:[a-z]{2,8}\s+)?(?:para|en|de)\s+(.+)', re.IGNORECASE),
     lambda m: {"intencion": "configurar_presupuesto", "categoria": m.group(2).strip(), "nombre": m.group(2).strip(), "cantidad": _parse_float(m.group(1)), "modo_presupuesto": "reemplazar", "confianza": 0.98}),

    # --- REGISTRO: formato corto $X en/para/de Y ---
    (re.compile(r'\$?([\d,.]+)\s+(?:en\s+|para\s+|de\s+)(.+)', re.IGNORECASE),
     lambda m: {"intencion": "registrar", "tipo": None, "cantidad": _parse_float(m.group(1)), "descripcion": m.group(2).strip(), "categoria": None, "confianza": 0.95}),

    # --- CONSULTA: gastos por presupuestos (período) ---
    # "cuánto gasté ayer de mis presupuestos", "cuánto gasté de mis presupuestos esta semana"
    (re.compile(r'cu[áa]nto\s+(?:gast[ée]|gastaste|he\s+gastado)\s+(?:hoy|ayer|anteayer|esta\s+semana|este\s+mes)?\s*(?:de\s+|en\s+)?(?:mis\s+|los\s+)?presupuestos?\b', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "gastos_por_presupuestos", "confianza": 0.98}),

    # --- CONSULTA: cuánto gasté/ingresé + fecha (total del período) ---
    (re.compile(r'cu[áa]nto\s+(?:gast[ée]|gastaste|he\s+gastado|ingres[ée]|recib[ií])\s+(?:en\s+total\s+)?(hoy|ayer|anteayer|esta\s+semana|este\s+mes)', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "gastos_por_fecha", "confianza": 0.98}),

    # --- CONSULTA: presupuesto específico (restante/progreso) ---
    # "cuánto me queda de mi presupuesto para barbería", "cuánto puedo gastar todavía de comida",
    # "me queda de transporte", "cómo voy con mi presupuesto de X", "progreso del presupuesto de X"
    (re.compile(r'(?:me\s+queda|me\s+quedan|cu[áa]nto\s+me\s+queda|cu[áa]nto\s+puedo\s+gastar|restante|disponible)\s+(?:todav[ií]a\s+|a[uú]n\s+)?(?:de\s+|del\s+|para\s+|en\s+|con\s+)?(?:mi\s+|el\s+)?(?:presupuesto\s+(?:de\s+|para\s+|del\s+|en\s+)?)?(.+)', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "presupuesto_especifico", "nombre": m.group(1).strip(), "confianza": 0.97}),
    (re.compile(r'(?:c[oó]mo\s+voy|qu[ée]\s+tal\s+va|progreso|c[oó]mo\s+va)\s+(?:con\s+|con\s+el\s+)?(?:mi\s+|el\s+)?presupuesto\s+(?:de\s+|para\s+)?(.+)', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "presupuesto_especifico", "nombre": m.group(1).strip(), "confianza": 0.97}),

    # --- CONSULTA: mayor gasto (período) ---
    (re.compile(r'(?:cu[áa]l|qu[ée])\s+(?:fue|es)\s+(?:el|mi)?\s*(?:mayor|m[áa]s\s+alto|m[áa]s\s+grande|top)?\s*gasto\b', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "mayor_gasto", "confianza": 0.97}),
    (re.compile(r'(?:mayor|m[áa]s\s+alto|m[áa]s\s+grande|top)\s+gasto\b', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "mayor_gasto", "confianza": 0.97}),
    (re.compile(r'gasto\s+(?:m[áa]s\s+alto|m[áa]s\s+grande|m[áa]s\s+caro|mayor\s+de\s+todos)', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "mayor_gasto", "confianza": 0.97}),

    # --- CONSULTA: transacciones por fecha (hoy/ayer/este mes) ---
    (re.compile(r'(?:qu[eé]\s+(?:gast[eé]|hice|pas[óo])|(?:ver|mostrar)\s+(?:transacciones|gastos|ingresos|historial))\s+(?:hoy|ayer|anteayer|esta\s+semana|este\s+mes)', re.IGNORECASE),
     lambda m: {"intencion": "analizar_por_fecha", "confianza": 0.99}),

    # --- CONSULTA: "qué gastó hoy?" ---
    (re.compile(r'qu[eé]\s+(?:gast[eé]|compr[eé]|hice)\s+(?:hoy|ayer)', re.IGNORECASE),
     lambda m: {"intencion": "analizar_por_fecha", "confianza": 0.98}),

    # --- CONSULTA: metas/ahorros/objetivos ---
    # Va antes de balance/transacciones para que "cuánto tengo ahorrado" no sea balance
    (re.compile(r'(?:ver|mostrar|listar|revisar|consultar)\s+(?:mis\s+)?(?:metas|metas\s+de\s+ahorro|ahorros|objetivos|ahorro)', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "metas", "confianza": 0.99}),
    (re.compile(r'(?:cu[áa]nto\s+(?:llevo|tengo|he|voy)\s+ahorrado|cu[áa]nto\s+he\s+ahorrado|c[oó]mo\s+va(?:n)?\s+(?:mi\s+)?(?:meta|metas|ahorro)|progreso\s+(?:de\s+)?(?:mi\s+)?(?:meta|ahorro))', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "metas", "confianza": 0.99}),

    # --- CONSULTA: balance/saldo ---
    (re.compile(r'(?:cu[áa]nto\s+(?:tengo|dinero|plata|saldo)|(?:cu[áa]l\s+es\s+(?:mi\s+)?(?:balance|saldo))|ver\s+(?:balance|saldo|resumen))', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "balance", "confianza": 0.99}),

    # --- CONSULTA: ver gastos/ingresos/transacciones ---
    (re.compile(r'(?:ver|mostrar|listar|dame)\s+(?:mis\s+)?(?:gastos|ingresos|transacciones|historial|movimientos)', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": _subconsulta_gasto_ingreso(m.group(0)), "confianza": 0.97}),

    # --- AYUDA: comandos/ayuda explícita ---
    (re.compile(r'^(?:ayuda|help|comandos|qu[eé]\s+(?:puedo|hago|ten[ée]s|tenes|comandos)|c[oó]mo\s+(?:funciona|se\s+usa|le\s+hago)|para\s+qu[eé]\s+sirve|no\s+entiendo)', re.IGNORECASE),
     lambda m: {"intencion": "ayuda_uso", "tipo_ayuda": "general", "confianza": 0.99}),

    # --- AYUDA: cómo registar ---
    (re.compile(r'c[oó]mo\s+(?:registrar|registro|agregar|agrego|poner|pongo|anotar)\s+(?:un\s+)?(?:gasto|ingreso|transacci[óo]n)', re.IGNORECASE),
     lambda m: {"intencion": "ayuda_uso", "tipo_ayuda": "registrar", "confianza": 0.99}),

    # --- AYUDA: cómo ver balance/plata/dinero ---
    (re.compile(r'c[oó]mo\s+(?:ver|consultar|saber|veo)\s+(?:mi\s+)?(?:balance|saldo|plata|dinero)', re.IGNORECASE),
     lambda m: {"intencion": "ayuda_uso", "tipo_ayuda": "ver_balance", "confianza": 0.99}),

    # --- AYUDA: cómo ver transacciones ---
    (re.compile(r'c[oó]mo\s+(?:ver|consultar|veo)\s+(?:mis\s+)?(?:transacciones|gastos|ingresos|historial|movimientos)', re.IGNORECASE),
     lambda m: {"intencion": "ayuda_uso", "tipo_ayuda": "ver_transacciones", "confianza": 0.99}),

    # --- AYUDA: qué puedo hacer / para qué sirve ---
    (re.compile(r'(?:qu[eé]\s+(?:puedo\s+hacer|hace\s+el\s+bot)|para\s+qu[eé]\s+(?:sirve|es))', re.IGNORECASE),
     lambda m: {"intencion": "ayuda_uso", "tipo_ayuda": "comandos", "confianza": 0.99}),

    # --- AYUDA: cómo configurar presupuesto ---
    (re.compile(r'c[oó]mo\s+(?:configurar|configuro|poner|pongo|crear|creo|hacer|hago)\s+(?:un\s+)?presupuesto', re.IGNORECASE),
     lambda m: {"intencion": "ayuda_uso", "tipo_ayuda": "presupuesto", "confianza": 0.99}),

    # --- AYUDA: cómo ahorrar/meta ---
    (re.compile(r'c[oó]mo\s+(?:ahorrar|poner|crear|configurar)\s+(?:una\s+)?(?:meta|objetivo|ahorro)', re.IGNORECASE),
     lambda m: {"intencion": "ayuda_uso", "tipo_ayuda": "ahorro", "confianza": 0.99}),

    # --- AYUDA: cómo modificar/eliminar ---
    (re.compile(r'c[oó]mo\s+(?:modificar|cambiar|editar|eliminar|borrar)\s+(?:una\s+)?(?:transacci[óo]n|gasto|ingreso)', re.IGNORECASE),
     lambda m: {"intencion": "ayuda_uso", "tipo_ayuda": "modificar", "confianza": 0.99}),

    # --- MODIFICAR: cambiar tipo ---
    (re.compile(r'(?:cambia|modifica|pasa|convierte)\s+(?:el|mi|ese|la)?\s*(?:gasto|ingreso|transacci[óo]n)\s+(?:a|para|como)\s+(?:un\s+)?(?:gasto|ingreso)', re.IGNORECASE),
     lambda m: {"intencion": "modificar", "accion_mod": "cambiar_tipo", "confianza": 0.96}),

    # --- MODIFICAR: cambiar monto "de $X a $Y" ---
    (re.compile(r'(?:cambia|modifica)\s+(?:el\s+)?(?:monto|cantidad|precio)\s+de\s+\$?([\d,.]+)\s+a\s+\$?([\d,.]+)', re.IGNORECASE),
     lambda m: {"intencion": "modificar", "accion_mod": "cambiar_monto", "valor_nuevo": _parse_float(m.group(2)), "confianza": 0.97}),

    # --- ELIMINAR: meta de ahorro ---
    (re.compile(r'(?:elimina|borra|quita|suprime|eliminar|borrar|quitar|suprimir)\s+(?:la\s+|el\s+|mi\s+|mis\s+)?(?:meta\s+de\s+ahorro|meta\s+de\s+ahorros|objetivo\s+de\s+ahorro|meta|ahorro)\s+(?:de\s+|del\s+|para\s+|en\s+)?(.+)', re.IGNORECASE),
     lambda m: {"intencion": "eliminar", "eliminar_objeto": "meta_ahorro", "categoria": m.group(1).strip(), "confianza": 0.97}),

    # --- ELIMINAR: presupuesto ---
    (re.compile(r'(?:elimina|borra|quita|suprime|eliminar|borrar|quitar|suprimir)\s+(?:el\s+|mi\s+|la\s+)?presupuesto\s+(?:de\s+|para\s+|en\s+)?(.+)', re.IGNORECASE),
     lambda m: {"intencion": "eliminar", "eliminar_objeto": "presupuesto", "categoria": m.group(1).strip(), "confianza": 0.97}),

    # --- ELIMINAR ---
    (re.compile(r'(?:elimina|borra|quita|eliminar|borrar)\s+(?:el|mi|la|ese|esa)?\s*(?:[úu]ltimo\s+)?(?:gasto|ingreso|transacci[óo]n)', re.IGNORECASE),
     lambda m: {"intencion": "eliminar", "confianza": 0.97}),

    # --- ACTUALIZAR: añadir monto a presupuesto existente ---
    (re.compile(r'(?:a[ñn]ade|agrega|suma|aumenta|incrementa)\s+\$?([\d,.]+)\s+(?:al|a|para|en)\s+presupuesto\s+(?:de|para)?\s*(.+)', re.IGNORECASE),
     lambda m: {"intencion": "configurar_presupuesto", "categoria": m.group(2).strip() or "general", "cantidad": _parse_float(m.group(1)), "modo_presupuesto": "sumar", "confianza": 0.97}),

    # --- SALUDO ---
    (re.compile(r'^(?:hola|buenas|buen[oa]s?\s+(?:d[ií]as|tardes|noches)|hey|hi|qu[eé]\s+(?:tal|onda))$', re.IGNORECASE),
     lambda m: {"intencion": "general", "confianza": 0.99}),

    # --- CONSULTA: categorías ---
    (re.compile(r'(?:qu[eé]\s+(?:categor[ií]as|tipos)|(?:ver|mostrar)\s+(?:mis\s+)?categor[ií]as)', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "categorias", "confianza": 0.97}),

    # --- CONSULTA: presupuestos ---
    (re.compile(r'(?:ver|mostrar|c[óo]mo\s+van)\s+(?:mis\s+)?presupuestos', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "presupuesto", "confianza": 0.97}),
]


def _fast_path(mensaje: str) -> Optional[Dict[str, Any]]:
    """Intenta resolver con regex rápido. Retorna dict o None."""
    for pattern, builder in _FAST_PATTERNS:
        match = pattern.search(mensaje.strip())
        if match:
            try:
                return builder(match)
            except Exception:
                continue
    return None


# ============================================================
# PROMPT PARA LA IA
# ============================================================

_SYSTEM_PROMPT = """Eres FinanzasBot, un asistente financiero experto. Tu única tarea es analizar mensajes de usuarios y devolver UN JSON VÁLIDO sin texto adicional.

REGLAS:
- Debes responder EXCLUSIVAMENTE con JSON válido, nada más.
- Si el usuario pregunta cómo hacer algo, muestra dudas o pide orientación, usa intencion "ayuda_uso".
- Detecta cualquier variante de dialecto (argentino, mexicano, venezolano, chileno, colombiano, etc.).
- Para "registrar": si no se puede determinar si es gasto o ingreso, dejar tipo como null.
- La fecha debe ir en formato YYYY-MM-DD cuando sea explícita, o null si no se menciona.
- Para "configurar_presupuesto": si el usuario quiere AÑADIR/SUMAR/AGREGAR un monto a un presupuesto existente (ej: "añade 500 al presupuesto de comida"), usa modo_presupuesto: "sumar". Si lo está definiendo o reemplazando (ej: "mi presupuesto para comida es 500"), usa modo_presupuesto: "reemplazar".
- Para "configurar_presupuesto": el campo "nombre" es el nombre del presupuesto (puede diferir de la categoría). Debe ser una etiqueta CORTA y CONCRETA en español. NUNCA uses pronombres, demostrativos ni referencias ("ello", "eso", "esto", "este", "él", "ella", "lo", "comprarlo", etc.). Si el usuario describe el tema ANTES del monto y tras el monto solo aparece una referencia (ej: "quiero comprarme un cable nuevo para cargar mi teléfono, destinaré un presupuesto de 1000 cup para ello"), el nombre debe ser ESE TEMA, no el pronombre (ej: nombre: "cable de carga", categoria: "otros"). Si el usuario da una etiqueta propia concreta tras el monto (ej: "tengo un presupuesto de 1000 cup para barbería"), copia esa etiqueta en "nombre" (ej: "barbería"), aunque la categoría sea "otros".
- Para "configurar_ahorro": el campo "descripcion" es el OBJETIVO de la meta, una etiqueta CORTA y CONCRETA en español (ej: "vacaciones", "un teléfono nuevo"). NUNCA uses pronombres ni referencias ("eso", "ello", "comprarlo", "lo"). Si tras el monto solo hay una referencia a un tema mencionado antes (ej: "quiero comprarme un teléfono nuevo, voy a ahorrar 5000 para eso"), usa ese tema como descripcion (ej: "teléfono"), no el pronombre.
- Para "agregar_ahorro": el usuario quiere SUMAR/AÑADIR dinero a UNA META DE AHORRO QUE YA EXISTE (ej: "agrega 900 cup a la meta de ahorro del regalo de mi novia", "añade 500 a mi meta del carro", "suma 1000 a mi meta de vacaciones"). Usa "descripcion" para la etiqueta de ESA meta (la parte tras "meta de ahorro de/para", ej: "regalo de mi novia", "el carro") SIN incluir pronombres, monedas ni la frase "meta de ahorro". NO lo uses para crear una meta nueva.
- Para "eliminar": si el usuario quiere borrar un PRESUPUESTO (ej: "elimina el presupuesto de comida"), usa eliminar_objeto: "presupuesto" y categoria: "comida". Para transacciones usa eliminar_objeto: "transaccion". Para una META DE AHORRO (ej: "elimina la meta de ahorro del regalo de mi novia", "borra mi meta del carro"), usa eliminar_objeto: "meta_ahorro" y categoria: la etiqueta de la meta (ej: "regalo de mi novia"). NUNCA uses "presupuesto" ni "transaccion" para metas de ahorro.
- La respuesta debe ser en español neutro, amigable, con emojis y sin regionalismos.
- Cuando el usuario haga una PREGUNTA general o pida un consejo financiero (no una operación de registrar/consultar/configurar), respóndele DIRECTAMENTE y con sustancia en el campo "respuesta" usando intencion "general" o "ayuda_uso". No devuelvas un menú genérico de comandos.
- Para intencion "consultar", usa el campo "subconsulta" para indicar QUÉ quiere ver el usuario:
  * "presupuesto_especifico": pregunta por el restante/disponible/progreso de UN presupuesto concreto (ej: "cuánto me queda de mi presupuesto para barbería", "cuánto puedo gastar todavía de comida", "cómo voy con mi presupuesto de transporte"). Pon la etiqueta textual que usa el usuario (puede ser coloquial) en "nombre" y el período en "fecha" si lo menciona.
  * "mayor_gasto": pregunta cuál fue el gasto más grande/mayor/top de un período (ej: "cuál fue el gasto que más tuve ayer", "el gasto más grande de esta semana"). Pon el período en "fecha" (hoy|ayer|esta semana|este mes|...).
  * "gastos_por_presupuestos": pregunta cuánto gastó en un período en relación a sus presupuestos (ej: "cuánto gasté ayer de mis presupuestos", "cuánto gasté esta semana de mis presupuestos"). Pon el período en "fecha".
  * "gastos_por_fecha": pregunta cuánto gastó o recibió en total en un período (ej: "cuánto gasté en total esta semana", "cuánto ingresé ayer"). Pon el período en "fecha".
  * "balance": pregunta por su saldo/balance/plata actual (ej: "cuánto tengo", "cuál es mi balance").
  * "metas": pregunta por sus METAS DE AHORRO o el progreso de su ahorro (ej: "ver mis ahorros", "revisar mis metas", "cuánto llevo ahorrado", "cómo va mi meta de vacaciones"). NO es un balance ni un presupuesto.
  * "presupuesto": pregunta genérica por sus presupuestos ("ver mis presupuestos").
  * "gastos"/"ingresos"/"transacciones": pedir ver la lista de movimientos.
- Estas consultas de subconsulta NO son ayuda_uso: el usuario pregunta por SUS datos, no por cómo usar el bot. NUNCA inventes cifras en "respuesta" para estas consultas: el sistema calculará los valores reales; deja "respuesta" en null y solo clasifica.
- El campo "fecha" para períodos usa solo palabras: "hoy", "ayer", "anteayer", "esta semana", "este mes" u otro período que mencione el usuario, o null si no menciona ninguno.
- Para "registrar": además de clasificar con "categoria" (usando la lista genérica), escribe en "categoria_sugerida" un NOMBRE CORTO, específico y con sentido en español de la categoría de la operación (ej: "Café", "Farmacia", "Alquiler", "Netflix", "Taxi", "Barbería", "Gimnasio"). Si el usuario menciona su propia etiqueta (ej: "gasté 200 en barbería"), usa esa palabra exacta (ej: "Barbería"). NO uses los nombres genéricos de la lista para "categoria_sugerida", y NO inventes detalles: usa solo lo que indica la descripción. Para el resto de intenciones, deja "categoria_sugerida" en null.
- Para "exportar": el usuario quiere descargar/exportar sus datos (ej: "exporta mis movimientos", "descarga mi mes", "dame el excel de julio"). Pon el período en "fecha" ("todo" si no especifica, "este mes", "últimos 30 días", "2026-07") y el formato en "formato" ("xlsx" o "excel" por defecto, "csv" solo si el usuario lo menciona). NO inventes cifras: el sistema generará el archivo.

JSON DE SALIDA:
{
  "intencion": "registrar|consultar|configurar_presupuesto|configurar_ahorro|agregar_ahorro|modificar|eliminar|analizar_por_fecha|ayuda_uso|general|exportar",
  "subconsulta": "balance|transacciones|gastos|ingresos|presupuesto|presupuesto_especifico|gastos_por_presupuestos|mayor_gasto|gastos_por_fecha|categorias|null",
  "tipo": "gasto|ingreso|null",
  "cantidad": numero | null,
  "descripcion": "texto | null",
  "categoria": "comida|transporte|salario|entretenimiento|servicios|salud|educacion|ropa|hogar|transporte|otros|null",
  "categoria_sugerida": "nombre corto y con sentido de la categoría (solo para 'registrar') | null",
  "nombre": "nombre propio del presupuesto | null",
  "fecha": "YYYY-MM-DD | hoy | ayer | todo | este mes | últimos 30 días | null",
  "moneda": "codigo_moneda | null",
  "accion_mod": "cambiar_tipo|cambiar_monto|cambiar_descripcion|cambiar_categoria|cambiar_fecha|null",
  "referencia": "ultimo_gasto|ultimo_ingreso|monto_X|texto|null",
  "valor_nuevo": "texto | null",
  "modo_presupuesto": "sumar|reemplazar|null",
  "eliminar_objeto": "transaccion|presupuesto|null",
  "es_consulta_ayuda": true | false,
  "tipo_ayuda": "registrar_gasto|registrar_ingreso|ver_balance|ver_transacciones|presupuesto|ahorro|modificar|eliminar|comandos|general|null",
  "formato": "xlsx|csv|null",
  "respuesta": "Texto amigable de respuesta al usuario"
}"""


def _construir_prompt_usuario(mensaje: str, contexto: Optional[str] = None) -> str:
    """Construye el prompt del usuario para la IA."""
    parte_contexto = ""
    if contexto:
        parte_contexto = (
            "\n\nCONTEXTO DEL USUARIO (datos REALES: úsalos para elegir la etiqueta exacta de presupuesto"
            " en 'nombre' cuando el usuario hable de sus presupuestos):\n"
            + contexto
        )
    return f"""Analiza el siguiente mensaje financiero y devuelve SOLO el JSON sin explicaciones adicionales.{parte_contexto}

Mensaje: "{mensaje}"

Recuerda: si el usuario está confundido, pregunta cómo hacer algo, o pide ayuda, usa intencion "ayuda_uso" con es_consulta_ayuda: true."""


def _construir_contexto_usuario(usuario: Dict[str, Any]) -> Optional[str]:
    """Construye el contexto real del usuario (presupuestos y monedas) para la IA."""
    try:
        import database
        uid = usuario.get("id")
        if not uid:
            return None
        presupuestos = database.obtener_presupuestos(uid)
        lineas = []
        if presupuestos:
            nombres = ", ".join(
                (p.get("nombre") or p.get("categoria_nombre") or "sin nombre") for p in presupuestos
            )
            lineas.append("Presupuestos del usuario: " + nombres)
        try:
            monedas = database.obtener_monedas(uid)
            if monedas:
                lineas.append("Monedas: " + ", ".join(m.get("abreviatura", "") for m in monedas))
        except Exception:
            pass
        return "\n".join(lineas) if lineas else None
    except Exception:
        return None


# ============================================================
# PARSEO DE RESPUESTA DE IA
# ============================================================

_RESULTADO_VACIO: Dict[str, Any] = {
    "intencion": "general",
    "subconsulta": None,
    "tipo": None,
    "cantidad": None,
    "descripcion": None,
    "categoria": None,
    "categoria_sugerida": None,
    "fecha": None,
    "moneda": None,
    "accion_mod": None,
    "referencia": None,
    "valor_nuevo": None,
    "es_consulta_ayuda": False,
    "tipo_ayuda": None,
    "respuesta": None,
    "confianza": 0.0,
    "modo_presupuesto": None,
    "eliminar_objeto": None,
    "nombre": None,
    "formato": None,
}


def _extraer_json(texto: str) -> Optional[Dict[str, Any]]:
    """Extrae el primer JSON válido de un texto (robusto ante texto adicional)."""
    # Intentar parse directo
    texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    # Buscar bloque ```json ... ``` o ``` ... ```
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', texto, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Buscar { ... } con regex (último recurso)
    match = re.search(r'\{[\s\S]*\}', texto)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


_INTENCIONES_VALIDAS = {
    "registrar", "consultar", "configurar_presupuesto", "configurar_ahorro", "agregar_ahorro",
    "modificar", "eliminar", "analizar_por_fecha", "ayuda_uso", "general", "exportar",
}

_TIPOS_VALIDOS = {"gasto", "ingreso", None}

_CONSULTAS_VALIDAS = {"balance", "transacciones", "gastos", "ingresos", "presupuesto", "categorias",
                      "presupuesto_especifico", "gastos_por_presupuestos", "mayor_gasto", "gastos_por_fecha",
                      "metas", None}


def _validar_resultado(datos: dict) -> dict:
    """Valida y normaliza el resultado de la IA."""
    resultado = dict(_RESULTADO_VACIO)

    intencion = datos.get("intencion")
    if intencion in _INTENCIONES_VALIDAS:
        resultado["intencion"] = intencion

    if intencion == "consultar":
        sub = datos.get("subconsulta")
        if sub in _CONSULTAS_VALIDAS:
            resultado["subconsulta"] = sub

    tipo = datos.get("tipo")
    if tipo in ("gasto", "ingreso"):
        resultado["tipo"] = tipo

    cantidad = datos.get("cantidad")
    if cantidad is not None:
        if isinstance(cantidad, str):
            from knowledge import _parsear_cantidad
            cantidad_parsed = _parsear_cantidad(cantidad)
            if cantidad_parsed is not None:
                resultado["cantidad"] = cantidad_parsed
        else:
            try:
                resultado["cantidad"] = float(cantidad)
            except (ValueError, TypeError):
                pass

    descripcion = datos.get("descripcion")
    if descripcion and isinstance(descripcion, str):
        resultado["descripcion"] = descripcion.strip()

    categoria = datos.get("categoria")
    if categoria and isinstance(categoria, str):
        resultado["categoria"] = categoria.strip()

    categoria_sugerida = datos.get("categoria_sugerida")
    if categoria_sugerida and isinstance(categoria_sugerida, str):
        resultado["categoria_sugerida"] = categoria_sugerida.strip()

    nombre = datos.get("nombre")
    if nombre and isinstance(nombre, str):
        resultado["nombre"] = nombre.strip()

    fecha = datos.get("fecha")
    if fecha and isinstance(fecha, str):
        resultado["fecha"] = fecha.strip()

    moneda = datos.get("moneda")
    if moneda and isinstance(moneda, str):
        resultado["moneda"] = moneda.strip()

    formato = datos.get("formato")
    if formato and isinstance(formato, str):
        fmt = formato.strip().lower()
        if "csv" in fmt:
            resultado["formato"] = "csv"
        elif "xls" in fmt or "excel" in fmt:
            resultado["formato"] = "xlsx"

    accion_mod = datos.get("accion_mod")
    if accion_mod in ("cambiar_tipo", "cambiar_monto", "cambiar_descripcion", "cambiar_categoria", "cambiar_fecha"):
        resultado["accion_mod"] = accion_mod

    referencia = datos.get("referencia")
    if referencia and isinstance(referencia, str):
        resultado["referencia"] = referencia.strip()

    valor_nuevo = datos.get("valor_nuevo")
    if valor_nuevo is not None:
        resultado["valor_nuevo"] = str(valor_nuevo)

    es_ayuda = datos.get("es_consulta_ayuda")
    if es_ayuda is True:
        resultado["es_consulta_ayuda"] = True
        resultado["intencion"] = "ayuda_uso"

    tipo_ayuda = datos.get("tipo_ayuda")
    if tipo_ayuda and isinstance(tipo_ayuda, str):
        resultado["tipo_ayuda"] = tipo_ayuda

    respuesta = datos.get("respuesta")
    if respuesta and isinstance(respuesta, str):
        resultado["respuesta"] = respuesta.strip()

    modo_presupuesto = datos.get("modo_presupuesto")
    if modo_presupuesto in ("sumar", "reemplazar"):
        resultado["modo_presupuesto"] = modo_presupuesto

    eliminar_objeto = datos.get("eliminar_objeto")
    if eliminar_objeto in ("transaccion", "presupuesto", "meta_ahorro"):
        resultado["eliminar_objeto"] = eliminar_objeto

    return resultado


# ============================================================
# LLAMADA A IA
# ============================================================

async def _call_ai(mensaje: str, usuario: Dict[str, Any]) -> Dict[str, Any]:
    """Llama a la IA (Mistral u Ollama) y retorna el JSON analizado."""
    logger.info("Enviando a IA para %s: %s", usuario.get("nombre", "?"), mensaje[:60])

    contexto = _construir_contexto_usuario(usuario)
    user_content = _construir_prompt_usuario(mensaje, contexto)

    # Intentar Mistral
    if config.AI_PROVIDER == "mistral" and config.MISTRAL_API_KEY:
        try:
            try:
                from mistralai import Mistral
            except ImportError:
                from mistralai.client import Mistral
            client = Mistral(api_key=config.MISTRAL_API_KEY)

            import asyncio
            chat_response = await asyncio.to_thread(
                client.chat.complete,
                model=config.MISTRAL_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                max_tokens=500,
            )

            texto = chat_response.choices[0].message.content
            datos = _extraer_json(texto)

            if datos:
                return _validar_resultado(datos)

            logger.warning("No se pudo extraer JSON de respuesta Mistral: %s", texto[:200])

        except Exception as e:
            logger.error("Error llamando a Mistral: %s", e)

    # Intentar Ollama como fallback
    if config.AI_PROVIDER == "ollama" or (config.AI_PROVIDER == "mistral" and not config.MISTRAL_API_KEY):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": config.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1},
                }
                async with session.post(
                    f"{config.OLLAMA_BASE_URL}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    data = await resp.json()
                    texto = data.get("message", {}).get("content", "")

            datos = _extraer_json(texto)
            if datos:
                return _validar_resultado(datos)

            logger.warning("No se pudo extraer JSON de respuesta Ollama: %s", texto[:200])

        except Exception as e:
            logger.error("Error llamando a Ollama: %s", e)

    # Si todo falla, retornar vacío
    return dict(_RESULTADO_VACIO)


# ============================================================
# API PÚBLICA
# ============================================================

async def analizar_intencion(mensaje: str, usuario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analiza la intención de un mensaje del usuario.

    Pipeline:
    1. Fast-path regex (alta confianza, cero costo, ~80% de los mensajes)
    2. IA (Mistral u Ollama, para el ~20% restante)
    3. Cache de resultados para evitar re-llamadas

    Args:
        mensaje: Texto del mensaje del usuario
        usuario: Dict con datos del usuario

    Returns:
        Dict con la intención analizada y parámetros extraídos
    """
    mensaje = mensaje.strip()
    if not mensaje:
        return dict(_RESULTADO_VACIO)

    # 1. Fast-path regex
    resultado = _fast_path(mensaje)
    if resultado:
        logger.debug("Fast-path match para: %s -> %s", mensaje[:40], resultado.get("intencion"))
        return resultado

    # 2. Cache (evita llamadas repetidas a IA para el mismo mensaje)
    cache_key = hash(mensaje.lower())
    if cache_key in _INTENT_CACHE:
        logger.debug("Cache hit para: %s", mensaje[:40])
        return _INTENT_CACHE[cache_key]

    # 3. IA
    resultado = await _call_ai(mensaje, usuario)
    _INTENT_CACHE[cache_key] = resultado
    return resultado


def limpiar_cache():
    """Limpia el cache de intenciones (útil para tests)."""
    _INTENT_CACHE.clear()