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

_FAST_PATTERNS = [
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

    # --- REGISTRO: formato corto $X en/para/de Y ---
    (re.compile(r'\$?([\d,.]+)\s+(?:en\s+|para\s+|de\s+)(.+)', re.IGNORECASE),
     lambda m: {"intencion": "registrar", "tipo": None, "cantidad": _parse_float(m.group(1)), "descripcion": m.group(2).strip(), "categoria": None, "confianza": 0.95}),

    # --- CONSULTA: balance/saldo ---
    (re.compile(r'(?:cu[áa]nto\s+(?:tengo|dinero|plata|saldo|gaste|gast[eé]|ingres[eé])|(?:cu[áa]l\s+es\s+(?:mi\s+)?(?:balance|saldo))|ver\s+(?:balance|saldo|resumen))', re.IGNORECASE),
     lambda m: {"intencion": "consultar", "subconsulta": "balance", "confianza": 0.99}),

    # --- CONSULTA: transacciones por fecha (hoy/ayer/este mes) ---
    (re.compile(r'(?:qu[eé]\s+(?:gast[eé]|hice|pas[óo])|(?:ver|mostrar)\s+(?:transacciones|gastos|ingresos|historial))\s+(?:hoy|ayer|anteayer|esta\s+semana|este\s+mes)', re.IGNORECASE),
     lambda m: {"intencion": "analizar_por_fecha", "confianza": 0.99}),

    # --- CONSULTA: "qué gastó hoy?" ---
    (re.compile(r'qu[eé]\s+(?:gast[eé]|compr[eé]|hice)\s+(?:hoy|ayer)', re.IGNORECASE),
     lambda m: {"intencion": "analizar_por_fecha", "confianza": 0.98}),

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
    (re.compile(r'c[oó]mo\s+(?:configurar|poner|crear|hacer)\s+(?:un\s+)?presupuesto', re.IGNORECASE),
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

    # --- ELIMINAR ---
    (re.compile(r'(?:elimina|borra|quita|eliminar|borrar)\s+(?:el|mi|la|ese|esa)?\s*(?:[úu]ltimo\s+)?(?:gasto|ingreso|transacci[óo]n)', re.IGNORECASE),
     lambda m: {"intencion": "eliminar", "confianza": 0.97}),

    # --- CONFIGURAR: presupuesto ---
    (re.compile(r'(?:mi\s+)?presupuesto\s+(?:para|de)\s+(.+?)\s+(?:es|de)\s+\$?([\d,.]+)', re.IGNORECASE),
     lambda m: {"intencion": "configurar_presupuesto", "categoria": m.group(1).strip(), "cantidad": _parse_float(m.group(2)), "confianza": 0.98}),

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
- La respuesta debe ser en español neutro, amigable, con emojis y sin regionalismos.

JSON DE SALIDA:
{
  "intencion": "registrar|consultar|configurar_presupuesto|configurar_ahorro|modificar|eliminar|analizar_por_fecha|ayuda_uso|general",
  "tipo": "gasto|ingreso|null",
  "cantidad": numero | null,
  "descripcion": "texto | null",
  "categoria": "comida|transporte|salario|entretenimiento|servicios|salud|educacion|ropa|hogar|transporte|otros|null",
  "fecha": "YYYY-MM-DD | hoy | ayer | null",
  "moneda": "codigo_moneda | null",
  "accion_mod": "cambiar_tipo|cambiar_monto|cambiar_descripcion|cambiar_categoria|cambiar_fecha|null",
  "referencia": "ultimo_gasto|ultimo_ingreso|monto_X|texto|null",
  "valor_nuevo": "texto | null",
  "es_consulta_ayuda": true | false,
  "tipo_ayuda": "registrar_gasto|registrar_ingreso|ver_balance|ver_transacciones|presupuesto|ahorro|modificar|eliminar|comandos|general|null",
  "respuesta": "Texto amigable de respuesta al usuario"
}"""


def _construir_prompt_usuario(mensaje: str) -> str:
    """Construye el prompt del usuario para la IA."""
    return f"""Analiza el siguiente mensaje financiero y devuelve SOLO el JSON sin explicaciones adicionales.

Mensaje: "{mensaje}"

Recuerda: si el usuario está confundido, pregunta cómo hacer algo, o pide ayuda, usa intencion "ayuda_uso" con es_consulta_ayuda: true."""


# ============================================================
# PARSEO DE RESPUESTA DE IA
# ============================================================

_RESULTADO_VACIO: Dict[str, Any] = {
    "intencion": "general",
    "tipo": None,
    "cantidad": None,
    "descripcion": None,
    "categoria": None,
    "fecha": None,
    "moneda": None,
    "accion_mod": None,
    "referencia": None,
    "valor_nuevo": None,
    "es_consulta_ayuda": False,
    "tipo_ayuda": None,
    "respuesta": None,
    "confianza": 0.0,
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
    "registrar", "consultar", "configurar_presupuesto", "configurar_ahorro",
    "modificar", "eliminar", "analizar_por_fecha", "ayuda_uso", "general",
}

_TIPOS_VALIDOS = {"gasto", "ingreso", None}

_CONSULTAS_VALIDAS = {"balance", "transacciones", "gastos", "ingresos", "presupuesto", "categorias", None}


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

    fecha = datos.get("fecha")
    if fecha and isinstance(fecha, str):
        resultado["fecha"] = fecha.strip()

    moneda = datos.get("moneda")
    if moneda and isinstance(moneda, str):
        resultado["moneda"] = moneda.strip()

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

    return resultado


# ============================================================
# LLAMADA A IA
# ============================================================

async def _call_ai(mensaje: str, usuario: Dict[str, Any]) -> Dict[str, Any]:
    """Llama a la IA (Mistral u Ollama) y retorna el JSON analizado."""
    logger.info("Enviando a IA para %s: %s", usuario.get("nombre", "?"), mensaje[:60])

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
                    {"role": "user", "content": _construir_prompt_usuario(mensaje)},
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
                        {"role": "user", "content": _construir_prompt_usuario(mensaje)},
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