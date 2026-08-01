"""
ai_client.py - Cliente de IA para el bot de finanzas personales
Usa intent_parser como pipeline unificado: fast-path regex + IA + ejecuci�n.
"""

import logging
from typing import Dict, Any

import database
import intent_parser
from config import AI_PROVIDER

logger = logging.getLogger(__name__)


class AIResponder:
    """Clase para procesar mensajes usando el pipeline de intenci�n unificado."""

    async def responder(self, mensaje: str, usuario: Dict[str, Any]) -> str:
        """
        Procesa un mensaje del usuario y retorna una respuesta.

        Pipeline:
        1. intent_parser.analizar_intencion() -> JSON estructurado (fast-path + IA)
        2. Ejecutar acci�n seg�n la intenci�n detectada
        3. Retornar respuesta al usuario

        Args:
            mensaje: El mensaje del usuario
            usuario: Informaci�n del usuario

        Returns:
            Respuesta en texto para el usuario
        """
        logger.info("Procesando mensaje para %s: %s", usuario.get("nombre", "?"), mensaje[:60])

        try:
            resultado = await intent_parser.analizar_intencion(mensaje, usuario)
        except Exception as e:
            logger.error("Error en intent_parser: %s", e)
            return self._generar_respuesta_error(usuario, "sistema")

        intencion = resultado.get("intencion", "general")
        logger.debug("Intenci�n detectada: %s", intencion)

        # --- AYUDA / CONSULTA DEL USUARIO ---
        if intencion == "ayuda_uso":
            return self._procesar_ayuda(resultado, usuario, mensaje)

        # --- REGISTRAR TRANSACCI�N ---
        if intencion == "registrar":
            return await self._procesar_registro(resultado, usuario, mensaje)

        # --- CONSULTAR ---
        if intencion == "consultar":
            return self._procesar_consulta(resultado, usuario, mensaje)

        # --- ANALIZAR POR FECHA ---
        if intencion == "analizar_por_fecha":
            return self._procesar_analisis_fecha(usuario, mensaje)

        # --- CONFIGURAR PRESUPUESTO ---
        if intencion == "configurar_presupuesto":
            return self._procesar_presupuesto(resultado, usuario, mensaje)

        # --- CONFIGURAR AHORRO ---
        if intencion == "configurar_ahorro":
            return self._procesar_ahorro(resultado, usuario, mensaje)

        # --- MODIFICAR ---
        if intencion == "modificar":
            return self._procesar_modificacion(resultado, usuario, mensaje)

        # --- ELIMINAR ---
        if intencion == "eliminar":
            return self._procesar_eliminacion(resultado, usuario, mensaje)

        # --- GENERAL / FALLBACK ---
        return self._procesar_general(resultado, usuario, mensaje)

    # ================================================================
    # PROCESADORES POR INTENCI�N
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
            "registrar_gasto": "c�mo registro un gasto",
            "registrar_ingreso": "c�mo registro un ingreso",
            "registrar": "c�mo registro un gasto",
            "ver_balance": "c�mo veo mi balance",
            "ver_transacciones": "c�mo veo mis transacciones",
            "presupuesto": "c�mo configuro un presupuesto",
            "ahorro": "c�mo creo una meta de ahorro",
            "modificar": "c�mo modifico una transacci�n",
            "eliminar": "c�mo elimino una transacci�n",
            "comandos": "qu� comandos tienes",
        }
        return mapa.get(tipo, "c�mo funciona el bot")

    async def _procesar_registro(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa el registro de una transacci�n."""
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
                "Asegurate de incluir un n�mero, por ejemplo:\n"
                "• `Gast� $50 en comida`\n"
                "• `Recib� $300 de salario`"
            )

        # Si tiene m�ltiples monedas y no especific�, pedir que elija
        if moneda_obj is None and len(monedas_usuario) > 1:
            lineas = [
                "💱 **Tienes varias monedas configuradas y no especificaste cu�l usar.**",
                "",
                "Por favor, reescribe tu mensaje indicando la moneda:",
                "",
            ]
            for m in monedas_usuario:
                default = " ⭐" if m.get("es_default") else ""
                lineas.append(f"  {m['simbolo']} {m['nombre']} ({m['abreviatura']}){default}")
            lineas.append("")
            lineas.append("Ej: `Gast� $50 en comida USD` o `Gast� $50 en comida en pesos`")
            return "\n".join(lineas)

        try:
            from knowledge import _procesar_gasto, _procesar_ingreso

            if tipo == "gasto":
                return _procesar_gasto(mensaje, usuario, moneda=moneda_obj)
            elif tipo == "ingreso":
                return _procesar_ingreso(mensaje, usuario, moneda=moneda_obj)
            else:
                # No se pudo determinar el tipo, preguntar
                return (
                    f"Detect� un monto de **${cantidad:.2f}**{' en ' + descripcion if descripcion else ''}, "
                    f"pero no estoy seguro si es un **gasto** o un **ingreso**.\n\n"
                    f"�Podr�s confirmarme?\n"
                    f"• Si es un **gasto**: `Gast� ${cantidad:.2f} {descripcion}`\n"
                    f"• Si es un **ingreso**: `Recib� ${cantidad:.2f} {descripcion}`"
                )
        except Exception as e:
            logger.error("Error registrando transacci�n: %s", e)
            return "❌ Ocurri� un error al registrar. Por favor, intent� de nuevo."

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
                # Intentar an�lisis por fecha si hay contexto temporal
                respuesta_fecha = _analizar_transacciones_por_fecha(usuario, mensaje)
                if respuesta_fecha:
                    return respuesta_fecha
                # Fallback a balance
                return _procesar_balance(usuario)

        except Exception as e:
            logger.error("Error en consulta: %s", e)
            return "❌ Ocurri� un error al consultar tus datos."

    def _procesar_analisis_fecha(self, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa un an�lisis de transacciones por fecha."""
        try:
            from knowledge import _analizar_transacciones_por_fecha
            respuesta = _analizar_transacciones_por_fecha(usuario, mensaje)
            if respuesta:
                return respuesta
            return "📅 No encontr� transacciones para ese per�odo. �Quer�s registrar algo?"
        except Exception as e:
            logger.error("Error analizando por fecha: %s", e)
            return "❌ Ocurri� un error al analizar tus transacciones."

    def _procesar_presupuesto(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa la configuraci�n de un presupuesto."""
        cantidad = resultado.get("cantidad")
        categoria = resultado.get("categoria") or resultado.get("descripcion") or "general"

        if not cantidad or cantidad <= 0:
            # Intentar extraer con el sistema nativo
            try:
                from knowledge import _generar_respuesta_no_entendido
                return _generar_respuesta_no_entendido(mensaje, usuario)
            except Exception:
                return "❌ No pude entender el monto del presupuesto. Us�: `Mi presupuesto para comida es $500`"

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

            database.crear_presupuesto(usuario["id"], categoria_id, cantidad)
            return f"✅ **Presupuesto configurado:** ${cantidad:.2f} para '{categoria}'"
        except Exception as e:
            logger.error("Error configurando presupuesto: %s", e)
            return "❌ Ocurri� un error al configurar el presupuesto."

    def _procesar_ahorro(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa la configuraci�n de una meta de ahorro."""
        cantidad = resultado.get("cantidad")
        descripcion = resultado.get("descripcion") or "meta general"

        if not cantidad or cantidad <= 0:
            try:
                from knowledge import _generar_respuesta_no_entendido
                return _generar_respuesta_no_entendido(mensaje, usuario)
            except Exception:
                return "❌ No pude entender el monto de la meta. Us�: `Quiero ahorrar $5000 para vacaciones`"

        try:
            database.crear_meta_ahorro(usuario["id"], descripcion, cantidad)
            return f"✅ **Meta de ahorro creada:** ${cantidad:.2f} para '{descripcion}'"
        except Exception as e:
            logger.error("Error creando meta de ahorro: %s", e)
            return "❌ Ocurri� un error al crear la meta de ahorro."

    def _procesar_modificacion(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa una solicitud de modificaci�n."""
        try:
            from knowledge import _procesar_modificar_transaccion

            accion = resultado.get("accion_mod")
            referencia = resultado.get("referencia")
            valor = resultado.get("valor_nuevo")

            mensaje_construido = self._construir_mensaje_mod(accion, referencia, valor, resultado)
            return _procesar_modificar_transaccion(mensaje_construido, usuario)
        except Exception as e:
            logger.error("Error procesando modificaci�n: %s", e)
            return "❌ No pude procesar la modificaci�n. �Podr�s ser m�s espec�fico?"

    def _procesar_eliminacion(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa una solicitud de eliminaci�n."""
        try:
            from knowledge import _procesar_eliminar_transaccion
            referencia = resultado.get("referencia", "")
            mensaje_construido = f"eliminar transacci�n {referencia}" if referencia else mensaje
            return _procesar_eliminar_transaccion(mensaje_construido, usuario)
        except Exception as e:
            logger.error("Error procesando eliminaci�n: %s", e)
            return "❌ No pude procesar la eliminaci�n."

    def _procesar_general(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa un mensaje general (saludos, no entendido, etc.)."""
        # Si la IA gener� una respuesta, usarla
        respuesta_ia = resultado.get("respuesta")
        if respuesta_ia:
            return respuesta_ia

        # Fallback: respuesta contextual
        try:
            from knowledge import _generar_respuesta_no_entendido
            return _generar_respuesta_no_entendido(mensaje, usuario)
        except Exception as e:
            logger.error("Error en fallback: %s", e)
            return (
                f"👋 �Hola {usuario.get('nombre', 'amigo')}!\n\n"
                "No entend� completamente tu mensaje. �Pod�s intentar con algo como?\n"
                "• `Gast� $50 en comida`\n"
                "• `�Cu�nto tengo?`\n"
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
                partes.append(f"descripci�n a {valor}")
            else:
                partes.append("descripci�n")
        elif accion == "cambiar_categoria":
            if valor:
                partes.append(f"categor�a a {valor}")
            else:
                partes.append("categor�a")
        elif accion == "cambiar_fecha":
            if valor:
                partes.append(f"fecha a {valor}")
            else:
                partes.append("fecha")

        return " ".join(partes)

    def _generar_respuesta_error(self, usuario: Dict[str, Any], tipo_error: str) -> str:
        """Genera una respuesta de error amigable."""
        nombre = usuario.get("nombre", "amigo")
        if tipo_error == "IA":
            return (
                f"😔 Disculpa {nombre}, el servicio de IA no est� disponible ahora.\n\n"
                "Mientras tanto, pod�s usar lenguaje natural directamente:\n\n"
                "• `Gast� $50 en comida` — Registrar gasto\n"
                "• `Recib� $300 de salario` — Registrar ingreso\n"
                "• `�Cu�nto tengo?` — Ver balance\n"
                "• `Ayuda` — Ver comandos\n\n"
                "Intent� de nuevo en unos segundos."
            )
        else:
            return (
                f"⚠️ {nombre}, algo sali� mal.\n\n"
                "Intent� con estos comandos:\n"
                "• `Gast� $50 en comida`\n"
                "• `�Cu�nto tengo?`\n"
                "• `Ayuda`\n\n"
                "Si el problema persiste, escrib� `/help`."
            )