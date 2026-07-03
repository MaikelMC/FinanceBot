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

        if intent == "registrar_transaccion":
            categoria_tipo, cantidad, descripcion, fecha = _parsear_transaccion(mensaje)

            if not cantidad or cantidad <= 0:
                return None

            if categoria_tipo:
                try:
                    from handlers import _procesar_transaccion_finanzas
                    respuesta = asyncio.run(_procesar_transaccion_finanzas(fecha, "gasto", cantidad, descripcion))
                    return respuesta
                except Exception as e:
                    logger.error("Error procesando con regex nativo: %s", e)

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

        # Construir prompt detallado
        prompt = f"""
El usuario '{usuario['nombre']}' está solicitando ayuda financiera personal.
Su ID de Telegram es: {usuario.get('telegram_user_id', 'desconocido')}.

Mensaje del usuario: "{mensaje}"

Por favor, analiza el mensaje e indica:
1. Intención: 'registrar_gasto', 'registrar_ingreso', 'consultar_balance', 'consultar_transacciones', 'consultar_gastos', 'consultar_ingresos', 'consultar_presupuesto', 'configurar_presupuesto', 'configurar_ahorro', 'configurar_categoria', 'general'
2. Cantidad: Si es una transacción, extrae el monto numérico (sin $ ni separadores de miles)
3. Categoría: Para gastos: 'comida', 'transporte', 'servicio', 'hogar', 'ocio', 'salud', 'otros'
   Para ingresos: 'salario', 'bonus', 'inversiones', 'regalos', 'otros'
4. Descripción: Extrae la descripción de la transacción
5. Fecha: Extrae la fecha si está mencionada (solo YYYY-MM-DD)

Responde en este formato exacto:
INTENTION: [intención]
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
            return "Disculpá, estoy experimentando problemas técnicos con la IA. Por favor, intenta de nuevo más tarde."

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

                    if clave in ['INTENTION', 'CANTIDAD', 'CATEGORIA', 'DESCRIPCION', 'FECHA']:
                        datos[clave] = valor if valor.lower() != 'null' else None

            # Redirigir al sistema nativo basado en la intención
            if datos.get('INTENTION') == 'registrar_gasto' and datos.get('CANTIDAD'):
                from knowledge import _procesar_gasto
                return _procesar_gasto(f"Gasté ${datos['CANTIDAD']} en {datos['DESCRIPCION'] or 'otros'}", usuario)

            elif datos.get('INTENTION') == 'registrar_ingreso' and datos.get('CANTIDAD'):
                from knowledge import _procesar_ingreso
                return _procesar_ingreso(f"Recibí ${datos['CANTIDAD']} de {datos['DESCRIPCION'] or 'otros'}", usuario)

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

            return respuesta_ia

        except Exception as e:
            logger.error("Error procesando respuesta de Mistral: %s", e)
            return respuesta_ia

    def _generar_respuesta_error(self, usuario: Dict[str, Any], tipo_error: str) -> str:
        """Genera una respuesta de error amigable."""
        nombre = usuario.get("nombre", "amigo")
        if tipo_error == "IA":
            return (
                f"😔 Lo siento {nombre}, estoy teniendo problemas con el servicio de IA en este momento.\n\n"
                "💡 **Alternativas:**\n"
                "• Usá comandos en inglés: 'gasté $50 en comida', 'balance', 'presupuesto'\n"
                "• Intentá nuevamente en unos segundos\n"
                "• Usá `/help` para ver los comandos disponibles"
            )
        else:
            return (
                f"⚠️ Ocurrió un error inesperado, {nombre}.\n\n"
                "Por favor intentá de nuevo o usá `/help` para ver los comandos disponibles."
            )

    def _generar_respuesta_fallback(self, mensaje: str, usuario: Dict[str, Any]) -> str:
        """Genera una respuesta de fallback cuando IA no está disponible."""
        from database import contar_transacciones, obtener_usuario

        mensaje_lower = mensaje.lower()
        nombre = usuario.get("nombre", "amigo")
        telegram_user_id = usuario.get("telegram_user_id", 0)

        try:
            db_user = obtener_usuario(telegram_user_id)
            usuario_id = db_user["id"] if db_user else 0
            estadisticas = contar_transacciones(usuario_id)
        except Exception:
            estadisticas = {"total": 0, "gastos": 0, "ingresos": 0}

        if any(word in mensaje_lower for word in ["hola", "hi", "buenas", "buenas tardes", "buenos días", "buenas noches"]):
            return (
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
            ])

        return (
            f"👋 Hola {nombre}! No entendí completamente tu mensaje: \"{mensaje}\".\n\n"
            "¿Podrías ser más específico? Por ejemplo:\n"
            "• 'Gasté $50 en comida' para registrar un gasto\n"
            "• 'Mi presupuesto es $300 para el mes' para configurar un presupuesto\n"
            "• '¿Cuál es mi balance?' para consultar tu saldo\n"
            "¿Cómo puedo ayudarte mejor?"
        )