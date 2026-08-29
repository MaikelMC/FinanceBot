"""
ai_client.py - Cliente de IA para el bot de finanzas personales
Usa intent_parser como pipeline unificado: fast-path regex + IA + ejecución.
"""

import logging
import re
from typing import Dict, Any, Optional, Tuple

import database
import formato
import intent_parser
from config import AI_PROVIDER
from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)


# --- Normalización del nombre del presupuesto -------------------------------
# Evita que pronombres/referencias ("ello", "eso", "comprarlo"...) se registren
# como nombre. Si tras el monto solo hay una referencia al tema mencionado antes,
# se usa la heurística _extraer_tema_presupuesto.

_NOMBRES_PROHIBIDOS = {
    "ello", "eso", "esto", "este", "esta", "estos", "estas", "esos", "esas",
    "aquel", "aquella", "aquello", "aquellos", "aquellas", "él", "ella",
    "ellos", "ellas", "lo", "los", "las", "le", "les", "me", "nos", "se",
    "os", "lo mismo", "eso mismo", "ello mismo", "esto mismo", "comprarlo",
    "comprarla", "comprarlos", "comprarlas", "comprar", "hacerlo", "hacerla",
    "hacerlos", "hacerlas", "conseguirlo", "conseguirla", "conseguirlos",
    "tenerlo", "tenerla", "usarlo", "usarla", "adquirirlo", "adquirirla",
    "lo que quiero", "lo que necesito",
}

_NOMBRES_PROHIBIDOS_PREFIJOS = (
    "para ", "comprar ", "comprarme ", "comprarlo ", "comprarla ",
    "destinar ", "destinaré ", "gastar ", "gastarlo ", "hacer ", "hacerlo ",
    "voy a ", "quiero ", "necesito ", "conseguir ", "adquirir ", "tener ",
    "poner ", "reservar ", "asignar ",
)

# Proposito -> sustantivo ("cable para cargar" -> "cable de carga")
_PROPOSITO_NOUNS = {
    "cargar": "carga",
    "pagar": "pago",
    "viajar": "viaje",
    "estudiar": "estudios",
    "reparar": "reparación",
    "arreglar": "arreglo",
    "alquilar": "alquiler",
    "cocinar": "cocina",
    "limpiar": "limpieza",
    "ahorrar": "ahorro",
    "invertir": "inversión",
    "mejorar": "mejora",
    "actualizar": "actualización",
    "renovar": "renovación",
    "comprar": "compra",
    "celebrar": "celebración",
    "entrenar": "entrenamiento",
}

# Verbos/frases introductorias que se descartan al buscar el tema de un presupuesto
_VERBOS_INICIO_TOPICO = (
    "quiero", "quisiera", "quería", "me gustaría", "necesito", "necesitaria",
    "necesitaría", "voy a", "vamos a", "vamos", "tengo que", "tengo",
    "pensaba", "pienso", "estoy pensando en", "pensando en", "quiero comprarme",
    "comprarme", "comprar", "adquirir", "conseguir", "obtener", "destinar",
    "destinaré", "asignar", "reservar", "apartar", "poner", "dejar", "ahorrar",
    "estoy ahorrando", "estoy ahorrando para", "pensé", "estoy pensando",
    "necesito comprar", "quiero comprar", "arreglar", "reparar",
)

_PALABRAS_STOP_TOPICO = {
    "para", "que", "con", "sin", "por", "a", "de", "en", "como", "mi", "mis",
    "tu", "tus", "sus", "su", "un", "una", "unos", "unas", "el", "la", "los",
    "las", "y", "o", "pero", "esto", "eso", "ello", "este", "esta", "todo",
    "toda", "todos", "todas", "nuevo", "nueva", "nuevos", "nuevas", "compra",
    "comprar", "comprarme", "quiero", "también", "tambien", "ademas", "además",
    "lo", "al", "del", "si", "no", "tengo", "poder", "pueda", "puedo", "ser",
    "estar", "está", "es", "les", "lo",
}


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
            texto = self._procesar_consulta(resultado, usuario, mensaje)
            pend = resultado.get("_pendiente_consulta")
            return texto, pend

        # --- ANALIZAR POR FECHA ---
        if intencion == "analizar_por_fecha":
            return self._procesar_analisis_fecha(usuario, mensaje), None

        # --- CONFIGURAR PRESUPUESTO ---
        if intencion == "configurar_presupuesto":
            return self._procesar_presupuesto(resultado, usuario, mensaje)

        # --- CONFIGURAR AHORRO ---
        if intencion == "configurar_ahorro":
            return self._procesar_ahorro(resultado, usuario, mensaje), None

        # --- AGREGAR A META DE AHORRO EXISTENTE ---
        if intencion == "agregar_ahorro":
            return self._procesar_agregar_ahorro(resultado, usuario, mensaje), None

        # --- MODIFICAR ---
        if intencion == "modificar":
            return self._procesar_modificacion(resultado, usuario, mensaje), None

        # --- ELIMINAR ---
        if intencion == "eliminar":
            return self._procesar_eliminacion(resultado, usuario, mensaje), None

        # --- EXPORTAR ---
        if intencion == "exportar":
            return self._procesar_exportar(resultado, usuario, mensaje)

        # --- GENERAL / FALLBACK ---
        return self._procesar_general(resultado, usuario, mensaje), None

    # ================================================================
    # PROCESADORES POR INTENCIÓN
    # ================================================================

    def _procesar_ayuda(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa una solicitud de ayuda o una pregunta del usuario."""
        # Si la IA generó una respuesta contextual, usarla (preguntas/consejos).
        respuesta_ia = resultado.get("respuesta")
        if respuesta_ia:
            return respuesta_ia

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
            "notificaciones": "cómo funcionan las notificaciones y el resumen diario",
            "comandos": "qué comandos tienes",
        }
        return mapa.get(tipo, "cómo funciona el bot")

    async def _procesar_registro(self, resultado: dict, usuario: Dict[str, Any],
                                 mensaje: str, forzar: bool = False) -> Tuple[str, Optional[dict]]:
        """Procesa el registro de una transacción."""
        tipo = resultado.get("tipo")
        cantidad = resultado.get("cantidad")
        descripcion = resultado.get("descripcion") or ""
        moneda_detectada = resultado.get("moneda")

        from knowledge import _normalizar_texto
        monedas_usuario = database.obtener_monedas(usuario["id"])

        # Buscar moneda en el resultado de la IA (abreviatura, nombre o símbolo)
        moneda_obj = None
        if moneda_detectada and monedas_usuario:
            token = (moneda_detectada or "").strip()
            t_norm = _normalizar_texto(token)
            for m in monedas_usuario:
                if (m.get("abreviatura", "").lower() == token.lower()
                        or _normalizar_texto(m.get("nombre", "")) == t_norm
                        or m.get("simbolo", "") == token):
                    moneda_obj = m
                    break

        # Fallback 1: detectar la moneda directamente desde el texto del mensaje
        # (evita que "gaste 50 usdt" quede sin moneda y se acumule en la default)
        if moneda_obj is None and monedas_usuario:
            try:
                from knowledge import _detectar_moneda_en_texto
                moneda_obj = _detectar_moneda_en_texto(mensaje, monedas_usuario)
            except Exception as e:
                logger.error("Error detectando moneda en texto: %s", e)

        # Fallback 2: si sigue sin moneda, usar la predeterminada (o la única).
        # Así los mensajes sin moneda explícita se registran directamente en
        # lugar de pedir que el usuario elija y perder la transacción.
        if moneda_obj is None and monedas_usuario:
            def_moneda = next((m for m in monedas_usuario if m.get("es_default")), None)
            if def_moneda is not None:
                moneda_obj = def_moneda
            elif len(monedas_usuario) == 1:
                moneda_obj = monedas_usuario[0]

        if not cantidad or cantidad <= 0:
            return (
                "❌ No pude entender el monto en tu mensaje.\n\n"
                "Asegúrate de incluir un número, por ejemplo:\n"
                "• `Gasté $50 en comida`\n"
                "• `Recibí $300 de salario`"
            ), None

        # Si la transacción referencia un presupuesto existente con moneda configurada,
        # reutilizar esa moneda en vez de preguntar de nuevo al usuario.
        if moneda_obj is None and len(monedas_usuario) > 1:
            try:
                from knowledge import _detectar_presupuesto_en_gasto
                presupuesto = _detectar_presupuesto_en_gasto(mensaje, usuario)
                if presupuesto and presupuesto.get("moneda_id"):
                    moneda_obj = next(
                        (m for m in monedas_usuario if m["id"] == presupuesto["moneda_id"]), None
                    )
            except Exception as e:
                logger.error("Error detectando presupuesto en gasto: %s", e)

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
            categoria_sugerida = resultado.get("categoria_sugerida")

            if tipo == "gasto":
                return _procesar_gasto(mensaje, usuario, moneda=moneda_obj,
                                       categoria_sugerida=categoria_sugerida, forzar=forzar)
            elif tipo == "ingreso":
                return _procesar_ingreso(mensaje, usuario, moneda=moneda_obj, categoria_sugerida=categoria_sugerida), None
            else:
                # No se pudo determinar el tipo, preguntar
                texto = (
                    f"Detecté un monto de **{formato.fmt_moneda(cantidad)}**"
                    f"{' en ' + descripcion if descripcion else ''}, "
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

    def _procesar_exportar(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> tuple:
        """Procesa una solicitud de exportación de datos (XLSX/CSV)."""
        try:
            from exportador import _detectar_formato, mapear_periodo_ia
        except Exception:
            _detectar_formato, mapear_periodo_ia = None, None
        formato = resultado.get("formato")
        if not formato and _detectar_formato:
            formato = _detectar_formato(mensaje)
        formato = formato or "xlsx"
        periodo = mapear_periodo_ia(resultado.get("fecha"), mensaje) if mapear_periodo_ia else "todo"
        etiqueta = {
            "xlsx": "Excel (.xlsx)",
            "csv": "CSV",
        }.get(formato, "Excel (.xlsx)")
        return (
            f"📤 Voy a exportar tus datos en **{etiqueta}**.\n\n"
            "Dame un segundo mientras genero el archivo..."
        ), {"accion": "exportar", "formato": formato, "periodo": periodo}

    def _procesar_consulta(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa una consulta del usuario."""
        subconsulta = resultado.get("subconsulta")

        try:
            from datetime import date, timedelta

            from intent_parser import _extraer_dias_periodo
            from knowledge import (
                _procesar_balance, _procesar_transacciones,
                _procesar_gastos, _procesar_ingresos,
                _procesar_presupuestos, _procesar_categorias,
                _analizar_transacciones_por_fecha,
                _procesar_presupuesto_especifico, _procesar_mayor_gasto,
                _procesar_gastos_por_presupuestos, _procesar_gastos_por_fecha,
                _procesar_metas_ahorro, _procesar_gastos_hormiga,
            )

            dias, etiqueta, explicito = _extraer_dias_periodo(mensaje)
            hoy = date.today()
            fecha_fin = hoy.isoformat()
            fecha_inicio = (hoy - timedelta(days=max(dias - 1, 0))).isoformat()
            # Solo filtrar por fecha si el usuario mencionó un período explícito,
            # para no cambiar el comportamiento de "ver mis gastos" (sin fecha).
            pf_inicio = fecha_inicio if explicito else None
            pf_fin = fecha_fin if explicito else None

            if subconsulta == "balance":
                return _procesar_balance(usuario)
            elif subconsulta == "transacciones":
                texto = _procesar_transacciones(usuario, fecha_inicio=pf_inicio,
                                                fecha_fin=pf_fin, periodo_label=etiqueta if explicito else None)
                self._marcar_ver_todas(resultado, usuario, None)
                return texto
            elif subconsulta == "gastos":
                texto = _procesar_gastos(usuario, fecha_inicio=pf_inicio,
                                         fecha_fin=pf_fin, periodo_label=etiqueta if explicito else None)
                self._marcar_ver_todas(resultado, usuario, "gasto")
                return texto
            elif subconsulta == "ingresos":
                texto = _procesar_ingresos(usuario, fecha_inicio=pf_inicio,
                                           fecha_fin=pf_fin, periodo_label=etiqueta if explicito else None)
                self._marcar_ver_todas(resultado, usuario, "ingreso")
                return texto
            elif subconsulta == "gastos_hormiga":
                return _procesar_gastos_hormiga(usuario, dias=dias, etiqueta=etiqueta)
            elif subconsulta == "presupuesto":
                return _procesar_presupuestos(usuario)
            elif subconsulta == "categorias":
                return _procesar_categorias(usuario)
            elif subconsulta == "presupuesto_especifico":
                return _procesar_presupuesto_especifico(usuario, resultado.get("nombre"))
            elif subconsulta == "mayor_gasto":
                return _procesar_mayor_gasto(usuario, mensaje)
            elif subconsulta == "gastos_por_presupuestos":
                return _procesar_gastos_por_presupuestos(usuario, mensaje)
            elif subconsulta == "gastos_por_fecha":
                return _procesar_gastos_por_fecha(usuario, mensaje)
            elif subconsulta == "metas":
                return _procesar_metas_ahorro(usuario)
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

    def _marcar_ver_todas(self, resultado: dict, usuario: Dict[str, Any], tipo: Optional[str]) -> None:
        """Marca en `resultado` que la vista debe ofrecer el botón 'Ver todas' si hay
        más de 10 transacciones (el reporte solo muestra las últimas 10)."""
        try:
            total = len(database.obtener_transacciones(usuario["id"], 100000, tipo))
        except Exception:
            total = 0
        if total > 10:
            resultado["_pendiente_consulta"] = {"accion": "ver_todas", "tipo": tipo}

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

    def _procesar_presupuesto(self, resultado: dict, usuario: Dict[str, Any], mensaje: str,
                              moneda: Optional[Dict[str, Any]] = None) -> Tuple[str, Optional[dict]]:
        """Procesa la configuración o actualización de un presupuesto."""
        cantidad = resultado.get("cantidad")
        categoria = (resultado.get("categoria") or resultado.get("descripcion") or "general").strip()
        nombre = (
            resultado.get("nombre")
            or self._extraer_nombre_presupuesto(mensaje)
            or resultado.get("descripcion")
            or resultado.get("categoria")
            or "general"
        ).strip()

        # Guarda: si el nombre es un pronombre/referencia ("ello", "eso", ...),
        # re-derivar con la etiqueta tras el monto o el tema mencionado antes.
        if not self._nombre_presupuesto_valido(nombre):
            nombre = (
                self._extraer_nombre_presupuesto(mensaje)
                or self._extraer_tema_presupuesto(mensaje)
                or resultado.get("descripcion")
                or resultado.get("categoria")
                or "general"
            ).strip()

        if not cantidad or cantidad <= 0:
            # Intentar extraer con el sistema nativo
            try:
                from knowledge import _generar_respuesta_no_entendido
                return _generar_respuesta_no_entendido(mensaje, usuario), None
            except Exception:
                return "❌ No pude entender el monto del presupuesto. Usa: `Mi presupuesto para comida es $500`", None

        modo = resultado.get("modo_presupuesto") or self._detectar_modo_presupuesto(mensaje)

        # --- Moneda: detectar desde IA o texto; si hay varias y no especifica, pedir elegir ---
        monedas_usuario = database.obtener_monedas(usuario["id"])
        moneda_obj = moneda
        if moneda_obj is None and monedas_usuario:
            moneda_detectada = resultado.get("moneda")
            if moneda_detectada:
                for m in monedas_usuario:
                    if m.get("abreviatura", "").lower() == moneda_detectada.lower():
                        moneda_obj = m
                        break
        if moneda_obj is None and monedas_usuario:
            from knowledge import _detectar_moneda_en_texto
            moneda_obj = _detectar_moneda_en_texto(mensaje, monedas_usuario)
            if moneda_obj is None and len(monedas_usuario) == 1:
                moneda_obj = monedas_usuario[0]

        # Localizar el presupuesto existente que se vería afectado (por nombre o categoría),
        # igual que database.guardar_presupuesto.
        presupuestos_previos = database.obtener_presupuestos(usuario["id"])
        target = None
        for p in presupuestos_previos:
            p_nombre = (p.get("nombre") or "").strip().lower()
            if nombre and p_nombre and p_nombre == nombre.lower():
                target = p
                break
        if target is None:
            for p in presupuestos_previos:
                p_cat = (p.get("categoria_nombre") or "").strip().lower()
                if p_cat and p_cat == categoria.lower():
                    target = p
                    break

        aviso_moneda = False
        # En modo "sumar", el aumento se aplica SIEMPRE en la moneda del presupuesto existente
        # (evita mezclar CUP + USD en un mismo presupuesto).
        if modo == "sumar" and target and target.get("moneda_id"):
            moneda_presup = next((m for m in monedas_usuario if m["id"] == target["moneda_id"]), None)
            if moneda_presup:
                if moneda_obj and moneda_obj["id"] != target["moneda_id"]:
                    aviso_moneda = True
                moneda_obj = moneda_presup

        if moneda_obj is None and len(monedas_usuario) > 1:
            # Reutilizar la moneda del presupuesto existente (mismo nombre o categoría) si ya tiene una
            if target and target.get("moneda_id"):
                moneda_obj = next((m for m in monedas_usuario if m["id"] == target["moneda_id"]), None)

        if moneda_obj is None and len(monedas_usuario) > 1:
            lineas = [
                "💱 **Tienes varias monedas configuradas y no especificaste cuál usar para el presupuesto.**",
                "",
                "Elige la moneda:",
                "",
            ]
            for m in monedas_usuario:
                default = " ⭐" if m.get("es_default") else ""
                lineas.append(f"  {m['simbolo']} {m['nombre']} ({m['abreviatura']}){default}")
            pendiente = {
                "accion": "elegir_moneda_presupuesto",
                "mensaje": mensaje,
                "cantidad": cantidad,
                "categoria": categoria,
                "nombre": nombre,
                "modo": modo,
            }
            return "\n".join(lineas), pendiente

        # Total final del presupuesto tras la operación (para validarlo contra el balance)
        total_objetivo = cantidad
        if modo == "sumar" and target:
            total_objetivo = target["cantidad_planejada"] + cantidad

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

            moneda_id = moneda_obj["id"] if moneda_obj else None

            # Validación: el presupuesto no puede exceder el balance libre de su moneda
            # (individual + acumulativo: suma de todos los presupuestos de la moneda <= balance).
            if moneda_obj:
                disponible = self._balance_disponible_moneda(usuario, moneda_obj["id"])
                if disponible is not None:
                    comprometido = self._presupuestos_comprometidos_moneda(
                        usuario, moneda_obj["id"], excluir_id=target["id"] if target else None
                    )
                    libre = disponible - comprometido
                    if total_objetivo - libre > 0.005:
                        simbolo = moneda_obj.get("simbolo", "$")
                        abrev = moneda_obj["abreviatura"]
                        return (
                            f"❌ **No puedes configurar un presupuesto de "
                            f"{formato.fmt_moneda(total_objetivo, abrev=abrev, simbolo=simbolo)}.**\n\n"
                            f"Tu balance del mes en **{abrev}** es **{formato.fmt_moneda(disponible, abrev=abrev, simbolo=simbolo)}** "
                            f"y ya tienes **{formato.fmt_moneda(comprometido, abrev=abrev, simbolo=simbolo)}** "
                            f"en otros presupuestos, así que solo te quedan "
                            f"**{formato.fmt_moneda(max(libre, 0), abrev=abrev, simbolo=simbolo)}** libres.\n\n"
                            "Ajusta el monto o registra más ingresos primero."
                        ), None

            presupuesto = database.guardar_presupuesto(usuario["id"], categoria_id, cantidad, modo, nombre=nombre, moneda_id=moneda_id)
            total = presupuesto.get("cantidad_planejada", cantidad)
            label = presupuesto.get("nombre") or categoria
            simbolo = moneda_obj.get("simbolo", "$") if moneda_obj else "$"
            abrev = moneda_obj["abreviatura"] if moneda_obj else None

            if modo == "sumar":
                aviso = f"\n💡 Se aplicó en la moneda del presupuesto ({moneda_obj['abreviatura']})." if aviso_moneda else ""
                return (
                    f"{formato.EMOJI_OK} **Añadido {formato.fmt_moneda(cantidad, abrev=abrev, simbolo=simbolo)} "
                    f"al presupuesto de {label}.**\n"
                    f"{formato.EMOJI_PRESUPUESTO} Total disponible: {formato.fmt_moneda(total, abrev=abrev, simbolo=simbolo)}{aviso}"
                ), None
            return (
                f"{formato.EMOJI_OK} **Presupuesto configurado:** "
                f"{formato.fmt_moneda(total, abrev=abrev, simbolo=simbolo)} para {label}"
            ), None
        except Exception as e:
            logger.error("Error configurando presupuesto: %s", e)
            return "❌ Ocurrió un error al configurar el presupuesto.", None

    def _balance_disponible_moneda(self, usuario: Dict[str, Any], moneda_id: int) -> Optional[float]:
        """Balance neto del mes en curso en la moneda indicada (None si no se puede calcular)."""
        try:
            balance = database.obtener_balance(usuario["id"])
            monedas = database.obtener_monedas(usuario["id"])
            m = next((x for x in monedas if x["id"] == moneda_id), None)
            if not m:
                return None
            info = balance.get("por_moneda", {}).get(m["abreviatura"])
            if not info:
                return 0.0
            return info["ingresos"] - info["gastos"]
        except Exception:
            return None

    def _presupuestos_comprometidos_moneda(self, usuario: Dict[str, Any], moneda_id: int,
                                           excluir_id: Optional[int] = None) -> float:
        """Suma de los montos planeados de todos los presupuestos en la moneda (opcionalmente excluyendo uno)."""
        try:
            return sum(
                p.get("cantidad_planejada", 0.0) or 0.0
                for p in database.obtener_presupuestos(usuario["id"])
                if p.get("moneda_id") == moneda_id and p.get("id") != excluir_id
            )
        except Exception:
            return 0.0

    @staticmethod
    def _extraer_nombre_presupuesto(mensaje: str) -> Optional[str]:
        """Extrae el nombre del presupuesto desde el texto del usuario.

        Busca la etiqueta real tras el monto (ej: "...de 1000 cup para barbería").
        Si lo capturado es una referencia/pronón ("ello", "eso", "comprarlo"),
        devuelve None para que el flujo use la heurística de tema.
        """
        m = re.search(
            r'presupuesto\s+(?:de\s+)?\$?[\d][\d.,]*\s*(?:\S{1,14}\s+)?\b(?:para|en|de)\s+(.+)',
            mensaje, re.IGNORECASE
        )
        if m:
            nombre = m.group(1).strip().strip(' .,;:')
            nombre = re.sub(r'^(?:el|la|un|una|este|esta|los|las)\s+', '', nombre, flags=re.IGNORECASE)
            nombre = re.sub(r'\s+', ' ', nombre).strip()
            if AIResponder._nombre_presupuesto_valido(nombre):
                return nombre
        return None

    @staticmethod
    def _nombre_presupuesto_valido(nombre: Optional[str]) -> bool:
        """True si el nombre es una etiqueta concreta (no pronombre/referencia)."""
        if not nombre:
            return False
        n = nombre.strip()
        if len(n) < 3:
            return False
        nl = n.lower()
        if nl in _NOMBRES_PROHIBIDOS:
            return False
        return not any(nl.startswith(pre) for pre in _NOMBRES_PROHIBIDOS_PREFIJOS)

    @staticmethod
    def _extraer_tema_presupuesto(mensaje: str) -> Optional[str]:
        """Extrae el TEMA real del presupuesto cuando tras el monto solo hay una
        referencia ("para ello", "para eso") que apunta al tema mencionado antes.

        Ej: "quiero comprarme un cable nuevo para cargar mi teléfono, destinaré un
        presupuesto de 1000 cup para ello" -> "cable de carga".
        """
        if not mensaje:
            return None
        texto = mensaje.lower()

        # 1. Recortar en la cláusula del presupuesto (el tema está antes)
        pos = None
        for kw in ("presupuesto", "destinaré", "destinar", "reservar", "asignar",
                   "apartar", "estoy ahorrando", "pensado en", "pensé"):
            i = texto.find(kw)
            if i != -1 and (pos is None or i < pos):
                pos = i
        if pos is not None:
            texto = texto[:pos]
        texto = texto.split(",")[0].strip()

        # 2. Quitar verbos/frases introductorias (repetidamente)
        cambiado = True
        while cambiado:
            cambiado = False
            for v in _VERBOS_INICIO_TOPICO:
                if texto.startswith(v + " ") or texto == v:
                    texto = texto[len(v):].strip()
                    cambiado = True
                    break

        # 3. Quitar artículos, posesivos y adjetivos de relleno
        texto = re.sub(r'\b(?:un|una|unos|unas|el|la|los|las|mi|mis|tu|tus|su|sus|'
                       r'nuestro|nuestra|nuestros|nuestras)\s+', ' ', texto)
        texto = re.sub(r'\b(?:nuevo|nueva|nuevos|nuevas|barato|barata|caro|cara|'
                       r'pequeño|pequeña|grande|bueno|buena|buen|mejor)\s+', ' ', texto)

        # 4. Sustantivo cabeza (primer token significativo)
        tokens = re.findall(r'[a-záéíóúñü]{2,}', texto)
        head = next((t for t in tokens if t not in _PALABRAS_STOP_TOPICO), None)
        if not head:
            return None

        # 5. Propósito tras "para": derivar una etiqueta compuesta
        m = re.search(r'\bpara\b', texto)
        if m:
            resto = re.findall(r'[a-záéíóúñü]+', texto[m.end():])
            while resto and resto[0] in ("el", "la", "los", "las", "mi", "mis",
                                         "tu", "tus", "su", "sus", "un", "una",
                                         "unos", "unas"):
                resto.pop(0)
            if resto:
                p = resto[0]
                if p == head:
                    return _PROPOSITO_NOUNS.get(p, head)
                if p in _PROPOSITO_NOUNS:
                    return f"{head} de {_PROPOSITO_NOUNS[p]}"
                if re.match(r'^[a-záéíóúñü]{3,}(?:ar|er|ir)$', p):
                    for t in resto[1:]:
                        if t not in _PALABRAS_STOP_TOPICO and len(t) >= 4:
                            return f"{head} de {t}" if t != head else head
                    return head
                if p not in _PALABRAS_STOP_TOPICO and len(p) >= 4 and p != head:
                    return f"{head} de {p}"
        return head

    @staticmethod
    def _extraer_proposito_ahorro(mensaje: str) -> Optional[str]:
        """Extrae el OBJETIVO de una meta de ahorro (lo que va tras 'para').

        Ej: "quiero ahorrar 5000 para vacaciones" -> "vacaciones".
        Si tras "para" solo hay una referencia ("eso", "ello"), intenta el tema
        mencionado antes del monto.
        """
        if not mensaje:
            return None
        m = re.search(r'\bpara\s+(.+)', mensaje, re.IGNORECASE)
        if not m:
            return None
        prop = m.group(1).strip().strip(' .,;:')
        prop = re.sub(r'^(?:el|la|un|una|unos|unas|mi|mis|este|esta|los|las|eso|ello)\s+',
                      '', prop, flags=re.IGNORECASE)
        prop = re.sub(r'\s+', ' ', prop).strip()
        prop = re.split(r'[,;:]', prop)[0].strip()
        if AIResponder._nombre_presupuesto_valido(prop):
            return prop
        return AIResponder._extraer_tema_presupuesto(mensaje)

    @staticmethod
    def _detectar_modo_presupuesto(mensaje: str) -> str:
        """Detecta si el mensaje pide sumar o reemplazar un presupuesto (fallback sin IA)."""
        if re.search(r'\b(?:a[ñn]ade|agrega|suma|aumenta|incrementa|mete|pon[eí])\b', mensaje, re.IGNORECASE):
            return "sumar"
        return "reemplazar"

    def _procesar_ahorro(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Procesa la configuración de una meta de ahorro."""
        cantidad = resultado.get("cantidad")
        descripcion = (resultado.get("descripcion") or "").strip()

        # Guarda: si el objetivo es un pronombre/referencia ("eso", "ello"...),
        # re-derivar con el propósito tras "para" o el tema mencionado antes.
        if not AIResponder._nombre_presupuesto_valido(descripcion):
            descripcion = (
                AIResponder._extraer_proposito_ahorro(mensaje)
                or AIResponder._extraer_tema_presupuesto(mensaje)
                or "meta general"
            )

        # Limpieza: quitar monedas ("cup", "usd") y frases sobrantes de la etiqueta,
        # ej: "cup para un regalo de mi novia" -> "regalo de mi novia".
        try:
            from knowledge import _limpiar_etiqueta_meta
            limpia = _limpiar_etiqueta_meta(descripcion)
            if limpia:
                descripcion = limpia
        except Exception:
            pass

        if not cantidad or cantidad <= 0:
            try:
                from knowledge import _generar_respuesta_no_entendido
                return _generar_respuesta_no_entendido(mensaje, usuario)
            except Exception:
                return "❌ No pude entender el monto de la meta. Usa: `Quiero ahorrar $5000 para vacaciones`"

        try:
            database.crear_meta_ahorro(usuario["id"], descripcion, cantidad)
            return f"{formato.EMOJI_OK} **Meta de ahorro creada:** {formato.fmt_moneda(cantidad)} para {descripcion}"
        except Exception as e:
            logger.error("Error creando meta de ahorro: %s", e)
            return "❌ Ocurrió un error al crear la meta de ahorro."

    def _procesar_agregar_ahorro(self, resultado: dict, usuario: Dict[str, Any], mensaje: str) -> str:
        """Agrega dinero a una meta de ahorro EXISTENTE (no crea una nueva)."""
        cantidad = resultado.get("cantidad")

        if not cantidad or cantidad <= 0:
            try:
                from knowledge import _generar_respuesta_no_entendido
                return _generar_respuesta_no_entendido(mensaje, usuario)
            except Exception:
                return "❌ No pude entender el monto a agregar. Usa: `Agrega 500 a mi meta de ahorro del carro`"

        try:
            from knowledge import _buscar_meta, _limpiar_etiqueta_meta
            etiqueta = _limpiar_etiqueta_meta(resultado.get("descripcion") or "")
            if not etiqueta:
                etiqueta = (
                    AIResponder._extraer_proposito_ahorro(mensaje)
                    or AIResponder._extraer_tema_presupuesto(mensaje)
                    or ""
                )
                etiqueta = _limpiar_etiqueta_meta(etiqueta)

            meta = _buscar_meta(usuario, etiqueta) if etiqueta else None
            if meta:
                database.actualizar_meta_ahorro(meta["id"], cantidad)
                objetivo = meta.get("objetivo", 0) or 0
                nuevo = (meta.get("cantidad_actual", 0) or 0) + cantidad
                progreso = (nuevo / objetivo * 100) if objetivo > 0 else 0
                restante = max(objetivo - nuevo, 0)
                nombre = meta.get("nombre") or etiqueta
                return (
                    f"{formato.EMOJI_OK} **Añadido {formato.fmt_moneda(cantidad)} a tu meta de ahorro** "
                    f"_{nombre}_\n"
                    f"{formato.fmt_moneda(nuevo)} / {formato.fmt_moneda(objetivo)} ({progreso:.0f}%)\n"
                    f"Restante: **{formato.fmt_moneda(restante)}**"
                )

            # No existe una meta con ese nombre: informar con las metas actuales.
            from knowledge import _procesar_metas_ahorro
            if etiqueta:
                return (
                    f"❌ No encontré una meta de ahorro llamada **{etiqueta}**.\n\n"
                    f"{_procesar_metas_ahorro(usuario)}"
                )
            return (
                "❌ No pude identificar a qué meta de ahorro quieres agregar dinero.\n\n"
                f"{_procesar_metas_ahorro(usuario)}"
            )
        except Exception as e:
            logger.error("Error agregando a meta de ahorro: %s", e)
            return "❌ Ocurrió un error al agregar dinero a la meta de ahorro."

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
        """Procesa una solicitud de eliminación (transacción, presupuesto o meta de ahorro)."""
        try:
            eliminar_objeto = resultado.get("eliminar_objeto")
            # Meta de ahorro: SIEMPRE primero (antes que presupuesto/transacción)
            if eliminar_objeto == "meta_ahorro" or re.search(r'\b(?:meta\s+de\s+ahorro|meta\s+de\s+ahorros|objetivo\s+de\s+ahorro|ahorro)\b', mensaje, re.IGNORECASE):
                from knowledge import _procesar_eliminar_todas_metas, _procesar_eliminar_meta
                # "elimina TODAS mis metas" -> borrado masivo
                if resultado.get("eliminar_todas") or re.search(r'\b(?:todas?|todos?)\b', mensaje, re.IGNORECASE):
                    return _procesar_eliminar_todas_metas(usuario)
                nombre = (
                    resultado.get("categoria")
                    or resultado.get("referencia")
                    or resultado.get("descripcion")
                    or ""
                )
                return _procesar_eliminar_meta(usuario, nombre)

            if eliminar_objeto == "presupuesto" or re.search(r'\bpresupuesto\b', mensaje, re.IGNORECASE):
                nombre = resultado.get("categoria") or resultado.get("referencia") or resultado.get("descripcion")
                if not nombre:
                    return "Para eliminar un presupuesto dime su nombre. Por ejemplo: `Elimina el presupuesto de comida`"
                from knowledge import _procesar_eliminar_presupuesto
                return _procesar_eliminar_presupuesto(usuario, nombre)

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