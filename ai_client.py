"""
ai_client.py - Cliente de IA para el bot de finanzas personales
Implementa conexión con Ollama y Mistral AI para procesamiento avanzado de lenguaje natural.
"""

import asyncio
import logging
from typing import Dict, Any

from mistralai.client import Mistral

import config

logger = logging.getLogger(__name__)


class AIResponder:
    """Clase para responder a las consultas de IA del usuario."""

    def __init__(self):
        self.mistral_client = None
        self._initialize_clients()

    def _initialize_clients(self):
        """Inicializa los clientes IA disponibles."""
        if config.AI_PROVIDER == "mistral" and config.MISTRAL_API_KEY:
            try:
                self.mistral_client = Mistral(api_key=config.MISTRAL_API_KEY)
                logger.info("Cliente Mistral AI inicializado.")
            except Exception as e:
                logger.error("Error inicializando cliente Mistral AI: %s", e)
                self.mistral_client = None

    async def responder(self, mensaje: str, usuario: Dict[str, Any]) -> str:
        """
        Procesa un mensaje del usuario usando IA y retorna una respuesta.

        Args:
            mensaje: El mensaje del usuario
            usuario: Información del usuario

        Returns:
            Respuesta generada por IA
        """
        logger.info("Procesando con IA para %s: %s", usuario["nombre"], mensaje)

        mensaje_lower = mensaje.lower().strip()

        # Palabras clave de modificación y eliminación (prioridad máxima)
        MOD_KEYWORDS = [
            "cambiar", "cambia", "modificar", "modifica", "editar", "edita",
            "actualizar", "actualiza", "corregir", "corrije", "mover", "mueve",
            "pasar", "pasa", "convertir", "convierte", "cambio", "modificalo",
        ]
        DEL_KEYWORDS = [
            "eliminar", "elimina", "borrar", "borra", "quitar", "quita",
            "remover", "remueve", "suprimir", "delet",
        ]
        MOD_TARGETS = [
            "transacción", "transaccion", "gasto", "ingreso", "registro",
            "movimiento", "tipo", "monto", "cantidad", "descripción",
            "descripcion", "categoría", "categoria", "fecha",
        ]

        es_modificacion = any(kw in mensaje_lower for kw in MOD_KEYWORDS)
        es_eliminacion = any(kw in mensaje_lower for kw in DEL_KEYWORDS)
        tiene_objetivo = any(t in mensaje_lower for t in MOD_TARGETS)

        # Si es modificación/eliminación con objetivo claro, procesar directamente
        if (es_modificacion or es_eliminacion) and tiene_objetivo:
            try:
                from knowledge import _procesar_modificar_transaccion, _procesar_eliminar_transaccion
                if es_eliminacion:
                    return _procesar_eliminar_transaccion(mensaje, usuario)
                return _procesar_modificar_transaccion(mensaje, usuario)
            except Exception as e:
                logger.error("Error procesando modificación nativa: %s", e)

        # Detección de saludo: solo si el mensaje ES un saludo (no lo contiene)
        es_solo_saludo = mensaje_lower in [
            "hola", "hi", "hey", "buenas", "buenas tardes",
            "buenos días", "buenas noches", "buen dia", "buenas dias",
        ] or mensaje_lower.startswith(("hola ", "hi ", "hey ", "buenas ", "buenos "))

        if es_solo_saludo:
            return self._generar_respuesta_fallback(mensaje, usuario)

        try:
            respuesta_nativa = self._procesar_con_regex_nativo(mensaje, usuario)

            if respuesta_nativa and not respuesta_nativa.startswith("👋 Hola!"):
                return respuesta_nativa

            if self.mistral_client and config.AI_PROVIDER == "mistral":
                try:
                    return await self._consultar_mistral(mensaje, usuario)
                except Exception as e:
                    logger.error("Error consultando Mistral AI: %s", e)
                    return self._generar_respuesta_error(usuario, "IA")

            return self._generar_respuesta_fallback(mensaje, usuario)

        except Exception as e:
            logger.error("Error inesperado procesando mensaje: %s", e)
            return self._generar_respuesta_error(usuario, "sistema")

    def _procesar_con_regex_nativo(self, mensaje: str, usuario: Dict[str, Any]) -> str:
        """
        Procesa el mensaje usando el sistema regex-based nativo.

        Returns:
            Respuesta procesada o None si no es posible
        """
        from handlers import _detectar_intencion, _parsear_transaccion

        intent = _detectar_intencion(mensaje)

        if intent == "ayuda_uso":
            try:
                from knowledge import _responder_ayuda_uso
                return _responder_ayuda_uso(mensaje)
            except Exception as e:
                logger.error("Error generando ayuda contextual: %s", e)

        if intent == "registrar_transaccion":
            categoria_tipo, cantidad, descripcion, fecha = _parsear_transaccion(mensaje)

            if not cantidad or cantidad <= 0:
                return None

            try:
                from knowledge import _procesar_gasto, _procesar_ingreso
                if categoria_tipo and "gasto" in str(categoria_tipo):
                    return _procesar_gasto(mensaje, usuario)
                elif categoria_tipo and "ingreso" in str(categoria_tipo):
                    return _procesar_ingreso(mensaje, usuario)
                else:
                    # Fallback: detectar tipo directamente del mensaje
                    texto_lower = mensaje.lower()
                    gasto_kw = ["gasté", "gaste", "compré", "compre", "pagué", "pague",
                                "costó", "costo", "gasto", "compra", "pago"]
                    ingreso_kw = ["recibí", "recibi", "ingresé", "ingrese", "cobré", "cobro",
                                  "gané", "gane", "ingreso", "salario", "sueldo", "bonus",
                                  "agrega", "agregar"]
                    if any(kw in texto_lower for kw in gasto_kw):
                        return _procesar_gasto(mensaje, usuario)
                    elif any(kw in texto_lower for kw in ingreso_kw):
                        return _procesar_ingreso(mensaje, usuario)
                    else:
                        # Sin tipo detectable, registrar como gasto por defecto
                        return _procesar_gasto(mensaje, usuario)
            except Exception as e:
                logger.error("Error procesando con regex nativo: %s", e)

        elif intent == "modificar_transaccion":
            try:
                from knowledge import _procesar_modificar_transaccion
                return _procesar_modificar_transaccion(mensaje, usuario)
            except Exception as e:
                logger.error("Error procesando modificación con regex: %s", e)

        elif intent == "eliminar_transaccion":
            try:
                from knowledge import _procesar_eliminar_transaccion
                return _procesar_eliminar_transaccion(mensaje, usuario)
            except Exception as e:
                logger.error("Error procesando eliminación con regex: %s", e)

        elif intent == "consultar_balance":
            try:
                from knowledge import _procesar_balance
                respuesta = _procesar_balance(usuario)
                return respuesta
            except Exception as e:
                logger.error("Error consultando balance con regex: %s", e)

        elif intent == "consultar_transacciones":
            try:
                from knowledge import _procesar_transacciones
                respuesta = _procesar_transacciones(usuario)
                return respuesta
            except Exception as e:
                logger.error("Error consultando transacciones con regex: %s", e)

        elif intent == "consultar_gastos":
            try:
                from knowledge import _procesar_gastos
                respuesta = _procesar_gastos(usuario)
                return respuesta
            except Exception as e:
                logger.error("Error consultando gastos con regex: %s", e)

        elif intent == "consultar_ingresos":
            try:
                from knowledge import _procesar_ingresos
                respuesta = _procesar_ingresos(usuario)
                return respuesta
            except Exception as e:
                logger.error("Error consultando ingresos con regex: %s", e)

        elif intent == "analizar_por_fecha":
            try:
                from knowledge import _analizar_transacciones_por_fecha
                respuesta = _analizar_transacciones_por_fecha(usuario, mensaje)
                if respuesta:
                    return respuesta
            except Exception as e:
                logger.error("Error analizando por fecha con regex: %s", e)

        elif intent == "consultar_presupuesto":
            try:
                from knowledge import _procesar_presupuestos
                respuesta = _procesar_presupuestos(usuario)
                return respuesta
            except Exception as e:
                logger.error("Error consultando presupuestos con regex: %s", e)

        return None

    async def _consultar_mistral(self, mensaje: str, usuario: Dict[str, Any]) -> str:
        """Consulta Mistral AI con un prompt mejorado."""
        system_prompt = config.get_system_prompt()

        # Obtener transacciones recientes para contexto
        try:
            from knowledge import _procesar_transacciones
            transacciones_texto = _procesar_transacciones(usuario, limite=10)
        except Exception:
            transacciones_texto = "No hay transacciones recientes disponibles."

        # Construir prompt detallado
        prompt = f"""
El usuario '{usuario['nombre']}' está solicitando ayuda financiera personal.
Su ID de Telegram es: {usuario.get('telegram_user_id', 'desconocido')}.

TRANSACCIONES RECIENTES DEL USUARIO:
{transacciones_texto}

Mensaje del usuario: "{mensaje}"

Por favor, analiza el mensaje e indica:
1. Intención: 'registrar_gasto', 'registrar_ingreso', 'consultar_balance', 'consultar_transacciones', 'consultar_gastos', 'consultar_ingresos', 'consultar_presupuesto', 'configurar_presupuesto', 'configurar_ahorro', 'configurar_categoria', 'modificar_transaccion', 'eliminar_transaccion', 'analizar_por_fecha', 'general'
2. Si es modificación/eliminación:
   - ACCION_MOD: 'cambiar_tipo' | 'cambiar_monto' | 'cambiar_descripcion' | 'cambiar_categoria' | 'cambiar_fecha' | 'eliminar'
   - REFERENCIA: cómo identificar la transacción (ej: "ultimo_gasto", "monto_50", "gasto_ayer")
   - VALOR_NUEVO: el nuevo valor (si aplica)
3. Cantidad: Si es una transacción nueva, extrae el monto numérico (sin $ ni separadores de miles)
4. Categoría: Para gastos: 'comida', 'transporte', 'servicio', 'hogar', 'ocio', 'salud', 'otros'
   Para ingresos: 'salario', 'bonus', 'inversiones', 'regalos', 'otros'
5. Descripción: Extrae la descripción de la transacción
6. Fecha: Extrae la fecha si está mencionada (solo YYYY-MM-DD)

Responde en este formato exacto:
INTENTION: [intención]
ACCION_MOD: [acción de modificación o null]
REFERENCIA: [referencia de transacción o null]
VALOR_NUEVO: [nuevo valor o null]
CANTIDAD: [monto_numérico_o_null]
CATEGORIA: [categoria_o_null]
DESCRIPCION: [descripcion_o_null]
FECHA: [fecha_o_null]

Si no puedes entender la intención, usa 'general'.
Si no puedes extraer una cantidad numérica, usa 'null'.
Si no puedes determinar una categoría, usa 'null'.
"""

        try:
            chat_response: ChatCompletionResponse = await asyncio.to_thread(
                self.mistral_client.chat.complete,
                model=config.MISTRAL_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )

            respuesta_ia = chat_response.choices[0].message.content
            return self._procesar_respuesta_mistral(respuesta_ia, usuario)

        except Exception as e:
            logger.error("Error consultando Mistral: %s", e)
            return "Disculpa, estoy experimentando problemas técnicos con la IA. Por favor, intenta de nuevo más tarde."

    def _procesar_respuesta_mistral(self, respuesta_ia: str, usuario: Dict[str, Any]) -> str:
        """Procesa la respuesta de Mistral AI."""
        try:
            # Intentar parsear la respuesta estructurada
            lines = respuesta_ia.strip().split('\n')
            datos = {}

            for linea in lines:
                if ':' in linea:
                    clave, valor = linea.split(':', 1)
                    clave = clave.strip().upper()
                    valor = valor.strip()

                    if clave in ['INTENTION', 'CANTIDAD', 'CATEGORIA', 'DESCRIPCION', 'FECHA',
                                 'ACCION_MOD', 'REFERENCIA', 'VALOR_NUEVO']:
                        datos[clave] = valor if valor.lower() != 'null' else None

            # --- MODIFICACIÓN / ELIMINACIÓN ---
            if datos.get('INTENTION') == 'modificar_transaccion':
                from knowledge import _procesar_modificar_transaccion
                # Construir mensaje rico para el procesador nativo
                accion = datos.get('ACCION_MOD', '')
                referencia = datos.get('REFERENCIA', '')
                valor = datos.get('VALOR_NUEVO', '')
                mensaje_construido = self._construir_mensaje_modificacion(accion, referencia, valor, datos)
                return _procesar_modificar_transaccion(mensaje_construido, usuario)

            if datos.get('INTENTION') == 'eliminar_transaccion':
                from knowledge import _procesar_eliminar_transaccion
                referencia = datos.get('REFERENCIA', '')
                accion = datos.get('ACCION_MOD', 'eliminar')
                mensaje_construido = f"eliminar transacción {referencia or ''}"
                return _procesar_eliminar_transaccion(mensaje_construido, usuario)

            # --- REGISTRO ---
            if datos.get('INTENTION') == 'registrar_gasto' and datos.get('CANTIDAD'):
                from knowledge import _procesar_gasto
                return _procesar_gasto(f"Gasté ${datos['CANTIDAD']} en {datos['DESCRIPCION'] or 'otros'}", usuario)

            elif datos.get('INTENTION') == 'registrar_ingreso' and datos.get('CANTIDAD'):
                from knowledge import _procesar_ingreso
                return _procesar_ingreso(f"Recibí ${datos['CANTIDAD']} de {datos['DESCRIPCION'] or 'otros'}", usuario)

            # --- CONSULTAS ---
            elif datos.get('INTENTION') == 'consultar_balance':
                from knowledge import _procesar_balance
                return _procesar_balance(usuario)

            elif datos.get('INTENTION') == 'consultar_transacciones':
                from knowledge import _procesar_transacciones
                return _procesar_transacciones(usuario)

            elif datos.get('INTENTION') == 'consultar_gastos':
                from knowledge import _procesar_gastos
                return _procesar_gastos(usuario)

            elif datos.get('INTENTION') == 'consultar_ingresos':
                from knowledge import _procesar_ingresos
                return _procesar_ingresos(usuario)

            elif datos.get('INTENTION') == 'consultar_presupuesto':
                from knowledge import _procesar_presupuestos
                return _procesar_presupuestos(usuario)

            # --- ANÁLISIS POR FECHA ---
            elif datos.get('INTENTION') == 'analizar_por_fecha':
                from knowledge import _analizar_transacciones_por_fecha
                respuesta = _analizar_transacciones_por_fecha(usuario, mensaje)
                if respuesta:
                    return respuesta

            # --- NO ENTENDIÓ (general) ---
            elif datos.get('INTENTION') == 'general' or not datos.get('INTENTION'):
                from knowledge import _generar_respuesta_no_entendido
                return _generar_respuesta_no_entendido(datos.get('DESCRIPCION', '') or '', usuario)

            return respuesta_ia

        except Exception as e:
            logger.error("Error procesando respuesta de Mistral: %s", e)
            return respuesta_ia

    def _construir_mensaje_modificacion(self, accion: Optional[str], referencia: Optional[str],
                                         valor: Optional[str], datos: Dict) -> str:
        """Construye un mensaje de modificación comprensible para el procesador nativo."""
        partes = ["modificar"]

        if referencia:
            partes.append(referencia)

        if accion == "cambiar_tipo":
            if valor:
                partes.append(f"a {valor}")
            else:
                partes.append("tipo")
        elif accion == "cambiar_monto":
            if valor:
                partes.append(f"monto a ${valor}")
            else:
                partes.append("monto")
        elif accion == "cambiar_descripcion":
            if valor:
                partes.append(f"descripción a {valor}")
            else:
                partes.append("descripción")
        elif accion == "cambiar_categoria":
            if valor:
                partes.append(f"categoría a {valor}")
            else:
                partes.append("categoría")
        elif accion == "cambiar_fecha":
            if valor:
                partes.append(f"fecha a {valor}")
            else:
                partes.append("fecha")
        elif accion == "eliminar":
            partes = ["eliminar transacción"]
            if referencia:
                partes.append(referencia)

        return " ".join(partes)

    def _generar_respuesta_error(self, usuario: Dict[str, Any], tipo_error: str) -> str:
        """Genera una respuesta de error amigable con guía específica."""
        nombre = usuario.get("nombre", "amigo")
        if tipo_error == "IA":
            return (
                f"😔 Disculpa {nombre}, el servicio de IA no está disponible ahora mismo.\n\n"
                "Mientras tanto, puedes usar **lenguaje natural** directamente:\n\n"
                "• 💸 `Gasté $50 en comida` —Registrar gasto\n"
                "• 💰 `Recibí $300 de salario` — Registrar ingreso\n"
                "• 📊 `¿Cuánto tengo?` — Ver balance\n"
                "• 📋 `¿Qué gasté hoy?` — Ver transacciones\n"
                "• ⚙️ `Mi presupuesto es $500 para comida` — Configurar\n\n"
                "Intenta de nuevo en unos segundos si quieres usar la IA."
            )
        else:
            return (
                f"⚠️ {nombre}, algo salió mal.\n\n"
                "Intenta con estos comandos:\n"
                "• `Gasté $50 en comida`\n"
                "• `¿Cuánto tengo?`\n"
                "• `¿Qué gasté hoy?`\n\n"
                "Si el problema persiste, escribe `/help` para ver todos los comandos."
            )

    def _generar_respuesta_fallback(self, mensaje: str, usuario: Dict[str, Any]) -> str:
        """Genera una respuesta de fallback cuando IA no está disponible."""
        from knowledge import _generar_respuesta_no_entendido

        mensaje_lower = mensaje.lower()
        nombre = usuario.get("nombre", "amigo")

        # Saludos y ayuda: respuestas específicas
        if any(word in mensaje_lower for word in ["ayuda", "help", "comandos"]):
            return "\n".join([
                "🤖 **COMANDOS DE FINANZAS BOT:**",
                "",
                "📝 **Registrar:**",
                "• `Gasté $50 en comida` —Registrar gasto",
                "• `Recibí $300 de salario` — Registrar ingreso",
                "• `$20 en transporte` — Formato corto",
                "• `Pagué $100 de alquiler` — Pago registrado",
                "",
                "📊 **Consultar:**",
                "• `¿Cuánto tengo?` — Balance general",
                "• `¿Qué gasté hoy?` — Transacciones recientes",
                "• `¿Cuánto gasté en comida?` — Por categoría",
                "• `¿Cuánto ingresé?` — Ver ingresos",
                "",
                "⚙️ **Configurar:**",
                "• `Mi presupuesto es $500 para comida`",
                "• `Quiero ahorrar $2000 para vacaciones`",
                "",
                "✏️ **Modificar:**",
                "• `Cambiar mi último gasto a $75`",
                "• `Eliminar mi último gasto`",
                "",
                "📋 **Comandos del bot:**",
                "• /start — Iniciar el bot",
                "• /user — Ver tu información",
                "• /help — Ver esta ayuda",
            ])

        # Todo lo demás: respuesta contextual inteligente
        return _generar_respuesta_no_entendido(mensaje, usuario)