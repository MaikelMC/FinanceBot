"""
ai_client.py - Cliente de IA para el bot de finanzas personales
Usa intent_parser como pipeline unificado: fast-path regex + IA + ejecución.
"""

import logging
from typing import Dict, Any, Optional, Tuple

import database
import intent_parser
from config import AI_PROVIDER
from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)


class AIResponder:
    """Clase para procesar mensajes usando el pipeline de intención unificado."""

    async def responder(self, mensaje: str, usuario: Dict[str, Any]) -> Tuple[str, Optional[dict]]:
        """
        Procesa un mensaje del usuario y retorna (texto, pendiente).

        Pipeline:
        1. intent_parser.analizar_intencion() -> JSON estructurado (fast-path + IA)
        2. Ejecutar acción según la intención detectada
        3. Retornar respuesta al usuario

        Args:
            mensaje: El mensaje del usuario
            usuario: Información del usuario

        Returns:
            Tupla (respuesta en texto, dict de acción pendiente o None).
            Si pendiente no es None, el handler debe ofrecer botones para
            completar la acción (elegir tipo gasto/ingreso o elegir moneda).
        """
        logger.info("Procesando mensaje para %s: %s", usuario.get("nombre", "?"), mensaje[:60])

        try:
            resultado = await intent_parser.analizar_intencion(mensaje, usuario)
        except Exception as e:
            logger.error("Error en intent_parser: %s", e)
            return self._generar_respuesta_error(usuario, "sistema"), None

        intencion = resultado.get("intencion", "general")
        logger.debug("Intención detectada: %s", intencion)

        # --- AYUDA / CONSULTA DEL USUARIO ---
        if intencion == "ayuda_uso":
            return self._procesar_ayuda(resultado, usuario, mensaje), None

        # --- REGISTRAR TRANSACCIÓN ---
        if intencion == "registrar":
            return await self._procesar_registro(resultado, usuario, mensaje)

        # --- CONSULTAR ---
        if intencion == "consultar":
            return self._procesar_consulta(resultado, usuario, mensaje), None

        # --- ANALIZAR POR FECHA ---
        if intencion == "analizar_por_fecha":
            return self._procesar_analisis_fecha(usuario, mensaje), None

        # --- CONFIGURAR PRESUPUESTO ---
        if intencion == "configurar_presupuesto":
            return self._procesar_presupuesto(resultado, usuario, mensaje), None

        # --- CONFIGURAR AHORRO ---
        if intencion == "configurar_ahorro":
            return self._procesar_ahorro(resultado, usuario, mensaje), None

        # --- MODIFICAR ---
        if intencion == "modificar":
            return self._procesar_modificacion(resultado, usuario, mensaje), None

        # --- ELIMINAR ---
        if intencion == "eliminar":
            return self._procesar_eliminacion(resultado, usuario, mensaje), None

        # --- GENERAL / FALLBACK ---
        return self._procesar_general(resultado, usuario, mensaje), None

    # ================================================================
    # PROCESADORES POR INTENCIÓN
    # ================================================================

    def _procesar_ayuda(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa una solicitud de ayuda contextual."""
        tipo_ayuda = resultado.get("tipo_ayuda") or resultado.get("subconsulta")
        try:
            from knowledge import _responder_ayuda_uso, _generar_respuesta_no_entendido
            if tipo_ayuda:
                mensaje_ficticio = self._tipo_ayuda_a_mensaje(tipo_ayuda)
                return _responder_ayuda_uso(mensaje_ficticio)
            return _responder_ayuda_uso(mensaje)
        except Exception as e:
            logger.error("Error generando ayuda: %s", e)
            from knowledge import _generar_respuesta_no_entendido
            return _generar_respuesta_no_entendido(mensaje, usuario)

    def _tipo_ayuda_a_mensaje(self, tipo: str) -> str:
        """Convierte un tipo_ayuda a un mensaje que entienda _responder_ayuda_uso."""
        mapa = {
            "registrar_gasto": "cómo registro un gasto",
            "registrar_ingreso": "cómo registro un ingreso",
            "registrar": "cómo registro un gasto",
            "ver_balance": "cómo veo mi balance",
            "ver_transacciones": "cómo veo mis transacciones",
            "presupuesto": "cómo configuro un presupuesto",
            "ahorro": "cómo creo una meta de ahorro",
            "modificar": "cómo modifico una transacción",
            "eliminar": "cómo elimino una transacción",
            "comandos": "qué comandos tienes",
        }
        return mapa.get(tipo, "cómo funciona el bot")

    async def _procesar_registro(self, resultado: dict, usuario: Dict[str, Any],
                                 mensaje: str) -> Tuple[str, Optional[dict]]:
        """Procesa el registro de una transacción."""
        tipo = resultado.get("tipo")
        cantidad = resultado.get("cantidad")
        descripcion = resultado.get("descripcion") or ""
        moneda_detectada = resultado.get("moneda")

        monedas_usuario = database.obtener_monedas(usuario["id"])

        # Buscar moneda en el resultado de la IA
        moneda_obj = None
        if moneda_detectada and monedas_usuario:
            for m in monedas_usuario:
                if m.get("abreviatura", "").lower() == moneda_detectada.lower():
                    moneda_obj = m
                    break

        # Fallback: detectar la moneda directamente desde el texto del mensaje
        # (evita que "gaste 50 usdt" quede sin moneda y se acumule en la default)
        if moneda_obj is None and monedas_usuario:
            from knowledge import _detectar_moneda_en_texto
            moneda_obj = _detectar_moneda_en_texto(mensaje, monedas_usuario)
            if moneda_obj is None and len(monedas_usuario) == 1:
                moneda_obj = monedas_usuario[0]

        if not cantidad or cantidad <= 0:
            return (
                "❌ No pude entender el monto en tu mensaje.\n\n"
                "Asegurate de incluir un número, por ejemplo:\n"
                "• `Gasté $50 en comida`\n"
                "• `Recibí $300 de salario`"
            ), None

        # Si tiene múltiples monedas y no especificó, pedir que elija
        if moneda_obj is None and len(monedas_usuario) > 1:
            lineas = [
                "💱 **Tienes varias monedas configuradas y no especificaste cuál usar.**",
                "",
                "Elige la moneda para registrar:",
                "",
            ]
            for m in monedas_usuario:
                default = " ⭐" if m.get("es_default") else ""
                lineas.append(f"  {m['simbolo']} {m['nombre']} ({m['abreviatura']}){default}")
            pendiente = {
                "accion": "elegir_moneda",
                "mensaje": mensaje,
                "tipo": tipo,
                "cantidad": cantidad,
                "descripcion": descripcion,
            }
            return "\n".join(lineas), pendiente

        try:
            from knowledge import _procesar_gasto, _procesar_ingreso

            if tipo == "gasto":
                return _procesar_gasto(mensaje, usuario, moneda=moneda_obj), None
            elif tipo == "ingreso":
                return _procesar_ingreso(mensaje, usuario, moneda=moneda_obj), None
            else:
                # No se pudo determinar el tipo, preguntar
                texto = (
                    f"Detecté un monto de **${cantidad:.2f}**{' en ' + descripcion if descripcion else ''}, "
                    f"pero no estoy seguro si es un **gasto** o un **ingreso**.\n\n"
                    f"¿Podrías confirmar con un botón?"
                )
                pendiente = {
                    "accion": "elegir_tipo",
                    "mensaje": mensaje,
                    "tipo": tipo,
                    "cantidad": cantidad,
                    "descripcion": descripcion,
                    "moneda_id": moneda_obj["id"] if moneda_obj else None,
                }
                return texto, pendiente
        except Exception as e:
            logger.error("Error registrando transacción: %s", e)
            return "❌ Ocurrió un error al registrar. Por favor, intenta de nuevo.", None

    def _procesar_consulta(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa una consulta del usuario."""
        subconsulta = resultado.get("subconsulta")

        try:
            from knowledge import (
                _procesar_balance, _procesar_transacciones,
                _procesar_gastos, _procesar_ingresos,
                _procesar_presupuestos, _procesar_categorias,
                _analizar_transacciones_por_fecha,
            )

            if subconsulta == "balance":
                return _procesar_balance(usuario)
            elif subconsulta == "transacciones":
                return _procesar_transacciones(usuario)
            elif subconsulta == "gastos":
                return _procesar_gastos(usuario)
            elif subconsulta == "ingresos":
                return _procesar_ingresos(usuario)
            elif subconsulta == "presupuesto":
                return _procesar_presupuestos(usuario)
            elif subconsulta == "categorias":
                return _procesar_categorias(usuario)
            else:
                # Intentar análisis por fecha si hay contexto temporal
                respuesta_fecha = _analizar_transacciones_por_fecha(usuario, mensaje)
                if respuesta_fecha:
                    return respuesta_fecha
                # Fallback a balance
                return _procesar_balance(usuario)

        except Exception as e:
            logger.error("Error en consulta: %s", e)
            return "❌ Ocurrió un error al consultar tus datos."

    def _procesar_analisis_fecha(self, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa un análisis de transacciones por fecha."""
        try:
            from knowledge import _analizar_transacciones_por_fecha
            respuesta = _analizar_transacciones_por_fecha(usuario, mensaje)
            if respuesta:
                return respuesta
            return "📅 No encontré transacciones para ese período. ¿Quieres registrar algo?"
        except Exception as e:
            logger.error("Error analizando por fecha: %s", e)
            return "❌ Ocurrió un error al analizar tus transacciones."

    def _procesar_presupuesto(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa la configuración de un presupuesto."""
        cantidad = resultado.get("cantidad")
        categoria = resultado.get("categoria") or resultado.get("descripcion") or "general"

        if not cantidad or cantidad <= 0:
            # Intentar extraer con el sistema nativo
            try:
                from knowledge import _generar_respuesta_no_entendido
                return _generar_respuesta_no_entendido(mensaje, usuario)
            except Exception:
                return "❌ No pude entender el monto del presupuesto. Usa: `Mi presupuesto para comida es $500`"

        try:
            tipo_cat = "gastos"
            categorias = database.obtener_categorias(usuario["id"], tipo_cat)
            categoria_id = None
            for cat in categorias:
                if cat["nombre"].lower() == categoria.lower():
                    categoria_id = cat["id"]
                    break
            if not categoria_id:
                cat_info = database.crear_categoria(usuario["id"], categoria, tipo_cat)
                categoria_id = cat_info["id"]

            from datetime import date
            database.crear_presupuesto(
                usuario["id"], categoria_id, cantidad,
                periodo="mensual", fecha_inicio=date.today().isoformat(),
            )
            return f"✅ **Presupuesto configurado:** ${cantidad:.2f} para '{categoria}'"
        except Exception as e:
            logger.error("Error configurando presupuesto: %s", e)
            return "❌ Ocurrió un error al configurar el presupuesto."

    def _procesar_ahorro(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa la configuración de una meta de ahorro."""
        cantidad = resultado.get("cantidad")
        descripcion = resultado.get("descripcion") or "meta general"

        if not cantidad or cantidad <= 0:
            try:
                from knowledge import _generar_respuesta_no_entendido
                return _generar_respuesta_no_entendido(mensaje, usuario)
            except Exception:
                return "❌ No pude entender el monto de la meta. Usa: `Quiero ahorrar $5000 para vacaciones`"

        try:
            database.crear_meta_ahorro(usuario["id"], descripcion, cantidad)
            return f"✅ **Meta de ahorro creada:** ${cantidad:.2f} para '{descripcion}'"
        except Exception as e:
            logger.error("Error creando meta de ahorro: %s", e)
            return "❌ Ocurrió un error al crear la meta de ahorro."

    def _procesar_modificacion(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa una solicitud de modificación."""
        try:
            from knowledge import _procesar_modificar_transaccion

            accion = resultado.get("accion_mod")
            referencia = resultado.get("referencia")
            valor = resultado.get("valor_nuevo")

            mensaje_construido = self._construir_mensaje_mod(accion, referencia, valor, resultado)
            return _procesar_modificar_transaccion(mensaje_construido, usuario)
        except Exception as e:
            logger.error("Error procesando modificación: %s", e)
            return "❌ No pude procesar la modificación. ¿Podrás ser más específico?"

    def _procesar_eliminacion(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa una solicitud de eliminación."""
        try:
            from knowledge import _procesar_eliminar_transaccion
            referencia = resultado.get("referencia", "")
            mensaje_construido = f"eliminar transacción {referencia}" if referencia else mensaje
            return _procesar_eliminar_transaccion(mensaje_construido, usuario)
        except Exception as e:
            logger.error("Error procesando eliminación: %s", e)
            return "❌ No pude procesar la eliminación."

    def _procesar_general(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa un mensaje general (saludos, no entendido, etc.)."""
        # Si la IA generó una respuesta, usarla
        respuesta_ia = resultado.get("respuesta")
        if respuesta_ia:
            return respuesta_ia

        # Fallback: respuesta contextual
        try:
            from knowledge import _generar_respuesta_no_entendido
            return _generar_respuesta_no_entendido(mensaje, usuario)
        except Exception as e:
            logger.error("Error en fallback: %s", e)
            nombre_esc = escape_markdown(usuario.get("nombre", "amigo") or "amigo", version=1)
            return (
                f"👋 ¡Hola {nombre_esc}!\n\n"
                "No entendí completamente tu mensaje. ¿Puedes intentar con algo como?\n"
                "• `Gasté $50 en comida`\n"
                "• `¿Cuánto tengo?`\n"
                "• `Ayuda` para ver todos los comandos"
            )

    def _construir_mensaje_mod(self, accion: str, referencia: str, valor, datos: dict) -> str:
        """Construye un mensaje para el procesador nativo de modificaciones."""
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

        return " ".join(partes)

    def _generar_respuesta_error(self, usuario: Dict[str, Any], tipo_error: str) -> str:
        """Genera una respuesta de error amigable."""
        nombre = escape_markdown(usuario.get("nombre", "amigo") or "amigo", version=1)
        if tipo_error == "IA":
            return (
                f"😔 Disculpa {nombre}, el servicio de IA no está disponible ahora.\n\n"
                "Mientras tanto, puedes usar lenguaje natural directamente:\n\n"
                "• `Gasté $50 en comida` — Registrar gasto\n"
                "• `Recibí $300 de salario` — Registrar ingreso\n"
                "• `¿Cuánto tengo?` — Ver balance\n"
                "• `Ayuda` — Ver comandos\n\n"
                "Intenta de nuevo en unos segundos."
            )
        else:
            return (
                f"⚠️ {nombre}, algo salió mal.\n\n"
                "Intenta con estos comandos:\n"
                "• `Gasté $50 en comida`\n"
                "• `¿Cuánto tengo?`\n"
                "• `Ayuda`\n\n"
                "Si el problema persiste, escribe `/help`."
            )