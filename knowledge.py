"""
knowledge.py - Módulo de IA para finanzas personales
Maneja la lógica de IA para preguntas en lenguaje natural relacionadas con finanzas.
"""

import logging
import re
from collections import defaultdict
from typing import Dict, Any, Optional, List

import database
import formato
from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)


def _detectar_moneda_en_texto(texto: str, monedas_usuario: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Detecta si el texto menciona una moneda configurada por el usuario.
    Busca por abreviatura, nombre o símbolo.
    Usa límites de palabra para evitar colisiones por substring
    (ej: "USDT" no debe matchear la abreviatura "USD") y prioriza la
    coincidencia más larga (USDT gana sobre USD, USD gana sobre US).
    Retorna la moneda encontrada o None.
    """
    if not monedas_usuario:
        return None

    texto_lower = texto.lower()
    coincidencias = []

    for moneda in monedas_usuario:
        abreviatura = moneda.get("abreviatura", "").lower().strip()
        nombre = moneda.get("nombre", "").lower().strip()
        simbolo = moneda.get("simbolo", "")

        if abreviatura:
            if re.search(r'(?<![a-z0-9])' + re.escape(abreviatura) + r'(?![a-z0-9])', texto_lower):
                coincidencias.append((len(abreviatura), abreviatura, moneda))
                continue

        if nombre and len(nombre) > 1:
            if re.search(r'(?<![a-z0-9])' + re.escape(nombre) + r's?(?![a-z0-9])', texto_lower):
                coincidencias.append((len(nombre), nombre, moneda))
                continue

        if simbolo and simbolo in texto:
            coincidencias.append((1, simbolo, moneda))

    if not coincidencias:
        return None

    coincidencias.sort(key=lambda x: x[0], reverse=True)
    return coincidencias[0][2]





def _normalizar_texto(texto: str) -> str:
    """Convierte a minúsculas y elimina acentos/diacríticos para comparaciones robustas."""
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).lower()


def _detectar_presupuesto_en_gasto(mensaje: str, usuario: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Detecta si un gasto hace referencia a un presupuesto.

    Busca la etiqueta del presupuesto (nombre o categoría) en el mensaje y
    verifica que aparezca ligada a la palabra "presupuesto" (ej: "del presupuesto
    para barbería"). Devuelve el presupuesto o None.
    """
    if "presupuesto" not in mensaje.lower():
        return None
    presupuestos = database.obtener_presupuestos(usuario["id"])
    if not presupuestos:
        return None

    msg = _normalizar_texto(mensaje)
    presupuestos.sort(key=lambda p: max(
        len(p.get("nombre") or ""), len(p.get("categoria_nombre") or "")), reverse=True)

    for p in presupuestos:
        for etiqueta in [p.get("nombre") or "", p.get("categoria_nombre") or ""]:
            etiqueta = _normalizar_texto(etiqueta)
            if not etiqueta:
                continue
            idx = msg.find(etiqueta)
            if idx >= 0:
                ventana = msg[max(0, idx - 35):idx]
                if "presupuesto" in ventana:
                    return p
    return None


def _procesar_gasto(mensaje: str, usuario: Dict[str, Any], moneda: Optional[Dict[str, Any]] = None,
                    categoria_sugerida: Optional[str] = None,
                    presupuesto: Optional[Dict[str, Any]] = None) -> str:
    """Procesa una transacción de gasto.

    Si se pasa `presupuesto` (flujo guiado del menú), el gasto se registra
    directamente en la categoría de ese presupuesto, sin depender de la
    detección por texto ("del presupuesto para X").
    """
    cantidad = None

    cantidad = _parsear_cantidad(mensaje)

    if not cantidad:
        return "No pude entender la cantidad en tu gasto. ¿Podrías especificar el monto?"

    moneda_id = moneda["id"] if moneda else None

    try:
        # Si el gasto hace referencia a un presupuesto ("del presupuesto para X"),
        # registrarlo en la categoría del presupuesto para descontarlo del mismo.
        if presupuesto is None:
            presupuesto = _detectar_presupuesto_en_gasto(mensaje, usuario)
        # Reutilizar la moneda del presupuesto si el gasto se liga a él y no hay moneda aún
        if moneda_id is None and presupuesto and presupuesto.get("moneda_id"):
            for m in database.obtener_monedas(usuario["id"]):
                if m["id"] == presupuesto["moneda_id"]:
                    moneda = m
                    moneda_id = m["id"]
                    break
        if presupuesto:
            categoria_id = presupuesto["categoria_id"]
            categoria = presupuesto.get("categoria_nombre") or presupuesto.get("nombre") or "otros"
        else:
            categoria, categoria_id = _categorizar_operacion(usuario, mensaje, "gasto", categoria_sugerida)
            if categoria_id is None:
                raise Exception(f"No se pudo crear/asociar la categoría '{categoria}'")

        gastado_antes = presupuesto.get("cantidad_gastada", 0) if presupuesto else 0
        database.agregar_transaccion(usuario["id"], categoria_id, "gasto", cantidad,
                                   mensaje, moneda_id=moneda_id)

        simbolo = moneda.get("simbolo", "$") if moneda else "$"
        nombre_moneda = f" ({moneda['nombre']})" if moneda else ""

        if presupuesto:
            updated = next(
                (p for p in database.obtener_presupuestos(usuario["id"]) if p.get("id") == presupuesto.get("id")),
                None,
            )
            if updated:
                label = presupuesto.get("nombre") or categoria
                planeado = updated.get("cantidad_planejada", 0)
                gastado = updated.get("cantidad_gastada", 0)
                restante = max(planeado - gastado, 0)
                pct = (gastado / planeado * 100) if planeado > 0 else 0
                moneda_b = None
                if updated.get("moneda_id"):
                    for m in database.obtener_monedas(usuario["id"]):
                        if m["id"] == updated["moneda_id"]:
                            moneda_b = m
                            break
                s_b = moneda_b.get("simbolo", "$") if moneda_b else "$"
                abrev_b = moneda_b.get("abreviatura", "") if moneda_b else ""
                texto = (
                    f"{formato.EMOJI_OK} Gasto registrado: **{formato.fmt_moneda(cantidad, abrev=abrev_b)}** "
                    f"del presupuesto de **{label}**\n"
                    f"{formato.EMOJI_PRESUPUESTO} **{label}**: {formato.fmt_moneda(planeado, abrev=abrev_b)} planeado, "
                    f"{formato.fmt_moneda(gastado, abrev=abrev_b)} usado (**{pct:.0f}%**). "
                    f"Te quedan **{formato.fmt_moneda(restante, abrev=abrev_b)}**."
                )
                try:
                    from notificaciones import verificar_alertas_presupuesto
                    prefs = database.obtener_preferencias(usuario["id"])
                    alerta = verificar_alertas_presupuesto(
                        prefs, planeado, gastado_antes, gastado, label,
                        s_b, moneda_b.get("abreviatura", "") if moneda_b else "",
                    )
                    if alerta:
                        texto += "\n\n" + alerta
                except Exception as e:
                    logger.error("Error generando alerta de presupuesto: %s", e)
                return texto
            abrev_b = moneda_b.get("abreviatura", "") if moneda_b else ""
            return (
                f"{formato.EMOJI_OK} Gasto registrado: **{formato.fmt_moneda(cantidad, abrev=abrev_b)}** "
                f"del presupuesto de **{presupuesto.get('nombre') or categoria}**"
            )

        abrev = moneda.get("abreviatura", "") if moneda else ""
        return f"{formato.EMOJI_OK} Gasto registrado: **{formato.fmt_moneda(cantidad, abrev=abrev)}** en **{categoria}**"
    except Exception as e:
        logger.error("Error al procesar gasto: %s", e)
        return f"{formato.EMOJI_ERROR} Ocurrió un error al registrar tu gasto: **{formato.fmt_monto(cantidad)}**. Intenta de nuevo."


def _procesar_ingreso(mensaje: str, usuario: Dict[str, Any], moneda: Optional[Dict[str, Any]] = None,
                      categoria_sugerida: Optional[str] = None) -> str:
    """Procesa una transacción de ingreso."""
    cantidad = None

    cantidad = _parsear_cantidad(mensaje)

    if not cantidad:
        return "No pude entender la cantidad en tu ingreso. ¿Podrías especificar el monto?"

    moneda_id = moneda["id"] if moneda else None

    try:
        categoria, categoria_id = _categorizar_operacion(usuario, mensaje, "ingreso", categoria_sugerida)
        if categoria_id is None:
            raise Exception(f"No se pudo crear/asociar la categoría '{categoria}'")

        database.agregar_transaccion(usuario["id"], categoria_id, "ingreso", cantidad,
                                   mensaje, moneda_id=moneda_id)

        abrev = moneda.get("abreviatura", "") if moneda else ""
        return f"{formato.EMOJI_OK} Ingreso registrado: **{formato.fmt_moneda(cantidad, abrev=abrev)}** de **{categoria}**"
    except Exception as e:
        logger.error("Error al procesar ingreso: %s", e)
        return f"{formato.EMOJI_ERROR} Ocurrió un error al registrar tu ingreso: **{formato.fmt_monto(cantidad)}**. Intenta de nuevo."


def _procesar_balance(usuario: Dict[str, Any]) -> str:
    """Obtiene y muestra el balance del usuario, agrupado por moneda."""
    try:
        balance = database.obtener_balance(usuario["id"])
        por_moneda = balance.get("por_moneda", {})

        lineas = [
            formato.header(formato.EMOJI_BALANCE, f"Balance de {formato.nombre_mes_actual()}"),
            formato.SEPARADOR,
        ]

        if len(por_moneda) > 1 or (len(por_moneda) == 1 and list(por_moneda.keys()) != ["Sin moneda"]):
            for abrev, datos in por_moneda.items():
                neto_m = datos["ingresos"] - datos["gastos"]
                lineas.append("")
                lineas.append(f"**{abrev}**")
                lineas.append(
                    f"{formato.EMOJI_INGRESO} {formato.fmt_moneda(datos['ingresos'])}   "
                    f"{formato.EMOJI_GASTO} {formato.fmt_moneda(datos['gastos'])}   "
                    f"→ **{formato.fmt_moneda(neto_m)}**"
                )
        else:
            lineas.append(f"{formato.EMOJI_INGRESO} Ingresos: ${formato.fmt_monto(balance['ingresos'])}")
            lineas.append(f"{formato.EMOJI_GASTO} Gastos: ${formato.fmt_monto(balance['gastos'])}")
            lineas.append(f"Neto: **${formato.fmt_monto(balance['neto'])}**")

        lineas.append("")
        lineas.append("¿Ver transacciones recientes o configurar un presupuesto?")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error al obtener balance: %s", e)
        return "❌ Ocurrió un error al obtener tu balance. Por favor, inténtalo de nuevo."


def _procesar_transacciones(usuario: Dict[str, Any], limite: int = 10, tipo: Optional[str] = None) -> str:
    """Muestra las transacciones del usuario, opcionalmente filtradas por tipo (gasto/ingreso)."""
    try:
        transacciones = database.obtener_transacciones(usuario["id"], limite, tipo)

        if not transacciones:
            if tipo == "gasto":
                return "📝 No tienes gastos registrados todavía."
            if tipo == "ingreso":
                return "📝 No tienes ingresos registrados todavía."
            return "📝 No tienes transacciones registradas todavía."

        titulo = "Tus transacciones recientes"
        if tipo == "gasto":
            titulo = "Tus gastos recientes"
        elif tipo == "ingreso":
            titulo = "Tus ingresos recientes"

        emoji = {"gasto": formato.EMOJI_GASTO, "ingreso": formato.EMOJI_INGRESO}
        lookup = _moneda_lookup_usuario(usuario)
        lineas = [formato.header("📋", titulo), formato.SEPARADOR]
        for t in transacciones:
            icono = emoji.get(t["tipo"], "🔹")
            tipo_label = "Ingreso" if t["tipo"] == "ingreso" else "Gasto"
            desc = _limpiar_descripcion(t.get("descripcion", "") or "")
            fecha = t.get("fecha", "")[:10]
            mid = t.get("moneda_id")
            moneda = lookup.get(mid) if mid else None
            abrev = moneda.get("abreviatura") if moneda else None
            monto = formato.fmt_moneda(t["cantidad"], abrev=abrev)
            lineas.append(f"{icono} {monto} - {tipo_label}: {desc} ({fecha})")

        total = sum(t["cantidad"] for t in transacciones)
        lineas.append("")
        if tipo:
            label = "Total gastado" if tipo == "gasto" else "Total recibido"
            lineas.append(f"{emoji[tipo]} **{label}:** {formato.fmt_moneda(total)} · {len(transacciones)} registros")
        else:
            lineas.append(f"{formato.EMOJI_INFO} {len(transacciones)} registros")
        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error al obtener transacciones: %s", e)
        return "❌ Ocurrió un error al obtener tus transacciones.\nIntenta de nuevo o escribe /help."


def _procesar_gastos(usuario: Dict[str, Any]) -> str:
    """Muestra solo los gastos del usuario."""
    return _procesar_transacciones(usuario, tipo="gasto")


def _procesar_ingresos(usuario: Dict[str, Any]) -> str:
    """Muestra solo los ingresos del usuario."""
    return _procesar_transacciones(usuario, tipo="ingreso")


def _procesar_presupuestos(usuario: Dict[str, Any]) -> str:
    """Muestra los presupuestos activos del usuario."""
    try:
        presupuestos = database.obtener_presupuestos(usuario["id"])

        if not presupuestos:
            return (
                f"{formato.EMOJI_PRESUPUESTO} No tienes presupuestos configurados.\n"
                "Prueba con: `Mi presupuesto para comida es $500 este mes`"
            )

        monedas_usuario = database.obtener_monedas(usuario["id"])
        moneda_lookup = {m["id"]: m for m in monedas_usuario}

        lineas = [formato.header(formato.EMOJI_PRESUPUESTO, "Tus presupuestos"), formato.SEPARADOR]
        for p in presupuestos:
            cat = p.get("nombre") or p.get("categoria_nombre", "General")
            moneda = moneda_lookup.get(p.get("moneda_id"))
            abrev = moneda.get("abreviatura") if moneda else None
            simbolo = moneda.get("simbolo", "$") if moneda else "$"
            planeado = p["cantidad_planejada"]
            gastado = p["cantidad_gastada"]
            restante = planeado - gastado
            progreso = (gastado / planeado * 100) if planeado > 0 else 0
            periodo = p.get("periodo")
            lineas.append("")
            lineas.append(f"**{cat}**{f' · {periodo}' if periodo else ''}")
            lineas.append(
                f"{formato.barra_progreso(progreso)} {progreso:.0f}% — "
                f"{formato.fmt_moneda(gastado, simbolo=simbolo)} de {formato.fmt_moneda(planeado, abrev=abrev, simbolo=simbolo)}"
            )
            lineas.append(f"Restante: **{formato.fmt_moneda(restante, abrev=abrev)}**")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error al obtener presupuestos: %s", e)
        return "❌ Ocurrió un error al obtener tus presupuestos.\nIntenta de nuevo o escribe /help."


def _moneda_lookup_usuario(usuario: Dict[str, Any]) -> Dict[Any, Dict[str, Any]]:
    """Mapa moneda_id -> moneda del usuario."""
    try:
        return {m["id"]: m for m in database.obtener_monedas(usuario["id"])}
    except Exception:
        return {}


def _formatear_monto(moneda_lookup: Dict[Any, Dict[str, Any]], moneda_id: Optional[int], cantidad: float) -> str:
    """Formatea un monto con símbolo y abreviatura de moneda si existe."""
    m = moneda_lookup.get(moneda_id)
    if m:
        return formato.fmt_moneda(cantidad, abrev=m["abreviatura"], simbolo=m.get("simbolo", "$"))
    return formato.fmt_moneda(cantidad)


def _buscar_presupuesto(usuario: Dict[str, Any], etiqueta: str) -> Optional[Dict[str, Any]]:
    """Busca un presupuesto por nombre/categoría (exacto -> contiene -> fuzzy)."""
    if not etiqueta:
        return None
    presupuestos = database.obtener_presupuestos(usuario["id"])
    if not presupuestos:
        return None
    norm = _normalizar_texto(etiqueta)

    # 1) Exacto por nombre o categoría
    for p in presupuestos:
        if _normalizar_texto(p.get("nombre") or "") == norm:
            return p
        if _normalizar_texto(p.get("categoria_nombre") or "") == norm:
            return p

    # 2) Contención (uno dentro del otro)
    for p in presupuestos:
        for cand in [p.get("nombre") or "", p.get("categoria_nombre") or ""]:
            nc = _normalizar_texto(cand)
            if nc and (norm in nc or nc in norm):
                return p

    # 3) Fuzzy (difflib)
    from difflib import SequenceMatcher
    mejor, mejor_ratio = None, 0.55
    for p in presupuestos:
        for cand in [p.get("nombre") or "", p.get("categoria_nombre") or ""]:
            nc = _normalizar_texto(cand)
            if not nc:
                continue
            ratio = SequenceMatcher(None, nc, norm).ratio()
            if ratio > mejor_ratio:
                mejor, mejor_ratio = p, ratio
    return mejor


def _limpiar_etiqueta_meta(texto: str) -> str:
    """Limpia una referencia a una meta de ahorro.

    Quita la frase "meta de ahorro", monedas ("cup", "usd"...) y artículos
    sobrantes. Ej: "cup para un regalo de mi novia" -> "regalo de mi novia".
    """
    if not texto:
        return ""
    t = texto.strip().strip(' .,;:')
    t = re.sub(r'\b(?:meta\s+de\s+ahorros?|objetivo\s+de\s+ahorro|meta\s+de\s+objetivo|ahorro|meta)\b',
               '', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(?:cup|usd|mlc|mex|eur|money|mn)\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'^\s+', '', t)
    while True:
        t2 = re.sub(r'^(?:a\s+la|a\s+el|al|a|en|para|de\s+la|del|de|por|mi|mis|el|la|los|las|un|una|unos|unas)\s+',
                    '', t, flags=re.IGNORECASE)
        if t2 == t:
            break
        t = t2
    t = re.sub(r'\s+', ' ', t).strip().strip(' .,;:')
    return t


def _buscar_meta(usuario: Dict[str, Any], etiqueta: str) -> Optional[Dict[str, Any]]:
    """Busca una meta de ahorro por nombre (exacto -> contiene -> fuzzy)."""
    if not etiqueta:
        return None
    metas = database.obtener_metas_ahorro(usuario["id"])
    if not metas:
        return None
    norm = _normalizar_texto(etiqueta)

    # 1) Exacto
    for m in metas:
        if _normalizar_texto(m.get("nombre") or "") == norm:
            return m

    # 2) Contención (uno dentro del otro)
    for m in metas:
        nc = _normalizar_texto(m.get("nombre") or "")
        if nc and (norm in nc or nc in norm):
            return m

    # 3) Fuzzy (difflib)
    from difflib import SequenceMatcher
    mejor, mejor_ratio = None, 0.6
    for m in metas:
        nc = _normalizar_texto(m.get("nombre") or "")
        if not nc:
            continue
        ratio = SequenceMatcher(None, nc, norm).ratio()
        if ratio > mejor_ratio:
            mejor, mejor_ratio = m, ratio
    return mejor


def _agregar_dinero_a_meta(meta: Dict[str, Any], cantidad: float) -> str:
    """Suma dinero a una meta ya identificada y devuelve el mensaje de confirmación."""
    database.actualizar_meta_ahorro(meta["id"], cantidad)
    objetivo = meta.get("objetivo", 0) or 0
    nuevo = (meta.get("cantidad_actual", 0) or 0) + cantidad
    progreso = (nuevo / objetivo * 100) if objetivo > 0 else 0
    restante = max(objetivo - nuevo, 0)
    nombre = meta.get("nombre") or "tu meta"
    return (
        f"{formato.EMOJI_OK} **Añadido {formato.fmt_moneda(cantidad)} a tu meta de ahorro** _{nombre}_\n"
        f"{formato.fmt_moneda(nuevo)} / {formato.fmt_moneda(objetivo)} ({progreso:.0f}%)\n"
        f"Restante: **{formato.fmt_moneda(restante)}**"
    )


def _procesar_eliminar_todas_metas(usuario: Dict[str, Any]) -> str:
    """Elimina TODAS las metas de ahorro del usuario."""
    try:
        metas = database.obtener_metas_ahorro(usuario["id"])
        if not metas:
            return "🎯 No tienes metas de ahorro que eliminar."
        borrados = database.eliminar_todas_metas_ahorro(usuario["id"])
        if borrados:
            return f"{formato.EMOJI_ELIMINAR} **Eliminaste todas tus metas de ahorro** ({borrados} eliminadas)."
        return "❌ No pude eliminar las metas de ahorro."
    except Exception as e:
        logger.error("Error eliminando todas las metas de ahorro: %s", e)
        return "❌ Ocurrió un error al eliminar las metas de ahorro."


def _procesar_eliminar_meta(usuario: Dict[str, Any], nombre: str) -> str:
    """Elimina una meta de ahorro por su nombre (exacto -> contiene -> fuzzy)."""
    try:
        nombre = nombre.strip()
        if not nombre:
            return "❌ Dime el nombre de la meta de ahorro a eliminar. Ejemplo: `Elimina la meta de ahorro del carro`"

        meta = _buscar_meta(usuario, nombre)
        if not meta:
            return (
                f"❌ No encontré una meta de ahorro llamada **{nombre}**.\n\n"
                f"{_procesar_metas_ahorro(usuario)}"
            )

        borrados = database.eliminar_meta_ahorro(usuario["id"], meta_id=meta["id"])
        if borrados:
            return f"{formato.EMOJI_ELIMINAR} **Meta de ahorro eliminada:** {meta.get('nombre') or nombre}"
        return f"❌ No pude eliminar la meta de ahorro **{meta.get('nombre') or nombre}**."
    except Exception as e:
        logger.error("Error eliminando meta de ahorro: %s", e)
        return "❌ Ocurrió un error al eliminar la meta de ahorro."


def _procesar_presupuesto_especifico(usuario: Dict[str, Any], etiqueta: str) -> str:
    """Muestra el restante/disponible de un presupuesto concreto."""
    try:
        etiqueta = (etiqueta or "").strip()
        if not etiqueta:
            return "¿De qué presupuesto quieres saber? Dime su nombre (ej: 'comida', 'barbería')."

        p = _buscar_presupuesto(usuario, etiqueta)
        if not p:
            presupuestos = database.obtener_presupuestos(usuario["id"])
            if not presupuestos:
                return (
                    f"{formato.EMOJI_ERROR} No tienes un presupuesto para **{etiqueta}** y todavía no tienes "
                    "ninguno configurado.\n\n"
                    f"Para crearlo: `Mi presupuesto para {etiqueta} es $500`"
                )
            nombres = ", ".join(
                f"'{x.get('nombre') or x.get('categoria_nombre')}'" for x in presupuestos
            )
            return (
                f"{formato.EMOJI_ERROR} No encontré un presupuesto para **{etiqueta}**.\n"
                f"Tus presupuestos actuales: {nombres}.\n\n"
                f"Para crearlo: `Mi presupuesto para {etiqueta} es $500`"
            )

        lookup = _moneda_lookup_usuario(usuario)
        label = p.get("nombre") or p.get("categoria_nombre") or "General"
        planeado = p["cantidad_planejada"]
        gastado = p["cantidad_gastada"]
        restante = max(planeado - gastado, 0)
        pct = (gastado / planeado * 100) if planeado > 0 else 0
        moneda = lookup.get(p.get("moneda_id"))
        abrev = moneda.get("abreviatura") if moneda else None
        simbolo = moneda.get("simbolo", "$") if moneda else "$"
        periodo = p.get("periodo")

        lineas = [f"{formato.EMOJI_PRESUPUESTO} **{label}**{f' · {periodo}' if periodo else ''}"]
        lineas.append(
            f"{formato.barra_progreso(pct)} {pct:.0f}% — "
            f"{formato.fmt_moneda(gastado, simbolo=simbolo)} de {formato.fmt_moneda(planeado, abrev=abrev, simbolo=simbolo)}"
        )
        lineas.append(f"Restante: **{formato.fmt_moneda(restante, abrev=abrev)}**")
        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error en presupuesto específico: %s", e)
        return "❌ Ocurrió un error al consultar tu presupuesto.\nIntenta de nuevo o escribe /help."


def _procesar_mayor_gasto(usuario: Dict[str, Any], mensaje: str) -> str:
    """Muestra el mayor gasto (y top 3) de un período."""
    try:
        from datetime import date as _date
        etiqueta = "hoy"
        resultado_fecha = _parsear_fecha_natural(mensaje)
        if resultado_fecha:
            fecha_inicio, fecha_fin, etiqueta = resultado_fecha
        else:
            f = _date.today().isoformat()
            fecha_inicio = fecha_fin = f

        gastos = database.obtener_transacciones_por_fecha(
            usuario["id"], fecha_inicio, fecha_fin, tipo="gasto"
        )
        if not gastos:
            return f"📅 No registraste gastos para {etiqueta}."

        lookup = _moneda_lookup_usuario(usuario)
        ordenados = sorted(gastos, key=lambda t: t["cantidad"], reverse=True)
        mayor = ordenados[0]

        lineas = [f"{formato.EMOJI_GASTO} **Mayor gasto de {etiqueta}**"]
        lineas.append(
            f"{_formatear_monto(lookup, mayor.get('moneda_id'), mayor['cantidad'])} - "
            f"{mayor.get('descripcion') or 'Sin descripción'}"
        )
        detalle = []
        if mayor.get("categoria_nombre"):
            detalle.append(mayor["categoria_nombre"])
        if mayor.get("fecha"):
            detalle.append(str(mayor["fecha"])[:10])
        if detalle:
            lineas.append(" · ".join(detalle))

        if len(ordenados) > 1:
            lineas.append("")
            lineas.append("**Top 3 gastos**")
            for t in ordenados[:3]:
                lineas.append(
                    f"• {_formatear_monto(lookup, t.get('moneda_id'), t['cantidad'])} - "
                    f"{t.get('descripcion') or 'Sin descripción'} ({t.get('categoria_nombre') or 'otros'})"
                )

        totales: Dict[Any, float] = {}
        for t in gastos:
            mid = t.get("moneda_id")
            totales[mid] = totales.get(mid, 0.0) + t["cantidad"]
        lineas.append("")
        for mid, tot in sorted(totales.items(), key=lambda x: -x[1]):
            lineas.append(f"{formato.EMOJI_GASTO} **Total:** {_formatear_monto(lookup, mid, tot)}")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error en mayor gasto: %s", e)
        return "❌ Ocurrió un error al consultar tus gastos.\nIntenta de nuevo o escribe /help."


def _procesar_gastos_por_presupuestos(usuario: Dict[str, Any], mensaje: str) -> str:
    """Muestra cuánto gastó en un período desglosado por presupuesto + total."""
    try:
        from datetime import date as _date
        etiqueta = "hoy"
        resultado_fecha = _parsear_fecha_natural(mensaje)
        if resultado_fecha:
            fecha_inicio, fecha_fin, etiqueta = resultado_fecha
        else:
            f = _date.today().isoformat()
            fecha_inicio = fecha_fin = f

        gastos = database.obtener_transacciones_por_fecha(
            usuario["id"], fecha_inicio, fecha_fin, tipo="gasto"
        )
        if not gastos:
            return f"📅 No registraste gastos para {etiqueta}."

        lookup = _moneda_lookup_usuario(usuario)
        presupuestos = database.obtener_presupuestos(usuario["id"])

        gasto_por_cat: Dict[Any, float] = {}
        for t in gastos:
            cid = t.get("categoria_id")
            gasto_por_cat[cid] = gasto_por_cat.get(cid, 0.0) + t["cantidad"]

        lineas = [formato.header(formato.EMOJI_PRESUPUESTO, f"Gastos de {etiqueta} en tus presupuestos"), formato.SEPARADOR]

        for p in presupuestos:
            gastado_periodo = gasto_por_cat.get(p["categoria_id"], 0.0)
            if gastado_periodo <= 0:
                continue
            label = p.get("nombre") or p.get("categoria_nombre") or "General"
            planeado = p["cantidad_planejada"]
            gastado_total = p["cantidad_gastada"]
            restante = max(planeado - gastado_total, 0)
            pct = (gastado_total / planeado * 100) if planeado > 0 else 0
            lineas.append("")
            lineas.append(f"**{label}**")
            lineas.append(f"Gastado en {etiqueta}: **{_formatear_monto(lookup, p.get('moneda_id'), gastado_periodo)}**")
            lineas.append(f"Restante: **{_formatear_monto(lookup, p.get('moneda_id'), restante)}** · {pct:.0f}% usado")
            lineas.append(formato.barra_progreso(pct))

        totales: Dict[Any, float] = {}
        for t in gastos:
            mid = t.get("moneda_id")
            totales[mid] = totales.get(mid, 0.0) + t["cantidad"]
        lineas.append("")
        for mid, tot in sorted(totales.items(), key=lambda x: -x[1]):
            lineas.append(f"{formato.EMOJI_GASTO} **Total:** {_formatear_monto(lookup, mid, tot)}")

        con_presupuesto = sum(gasto_por_cat.get(p["categoria_id"], 0.0) for p in presupuestos)
        sin_presupuesto = sum(totales.values()) - con_presupuesto
        if sin_presupuesto > 0.005:
            lineas.append(f"{formato.EMOJI_ADVERTENCIA} Fuera de presupuesto: {_formatear_monto(lookup, None, sin_presupuesto)}")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error en gastos por presupuestos: %s", e)
        return "❌ Ocurrió un error al consultar tus gastos.\nIntenta de nuevo o escribe /help."


def _procesar_gastos_por_fecha(usuario: Dict[str, Any], mensaje: str) -> str:
    """Muestra el total gastado/recibido en un período, por moneda."""
    try:
        from datetime import date as _date
        etiqueta = "hoy"
        resultado_fecha = _parsear_fecha_natural(mensaje)
        if resultado_fecha:
            fecha_inicio, fecha_fin, etiqueta = resultado_fecha
        else:
            f = _date.today().isoformat()
            fecha_inicio = fecha_fin = f

        gastos = database.obtener_transacciones_por_fecha(
            usuario["id"], fecha_inicio, fecha_fin, tipo="gasto"
        )
        ingresos = database.obtener_transacciones_por_fecha(
            usuario["id"], fecha_inicio, fecha_fin, tipo="ingreso"
        )
        if not gastos and not ingresos:
            return f"📅 No tienes movimientos para {etiqueta}."

        lookup = _moneda_lookup_usuario(usuario)
        lineas = [f"📅 **Movimientos de {etiqueta}**"]

        if gastos:
            totales: Dict[Any, float] = {}
            for t in gastos:
                mid = t.get("moneda_id")
                totales[mid] = totales.get(mid, 0.0) + t["cantidad"]
            lineas.append(f"{formato.EMOJI_GASTO} **Total gastado:**")
            for mid, tot in sorted(totales.items(), key=lambda x: -x[1]):
                lineas.append(f"• {_formatear_monto(lookup, mid, tot)}")

        if ingresos:
            totales_in: Dict[Any, float] = {}
            for t in ingresos:
                mid = t.get("moneda_id")
                totales_in[mid] = totales_in.get(mid, 0.0) + t["cantidad"]
            lineas.append(f"{formato.EMOJI_INGRESO} **Total recibido:**")
            for mid, tot in sorted(totales_in.items(), key=lambda x: -x[1]):
                lineas.append(f"• {_formatear_monto(lookup, mid, tot)}")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error en gastos por fecha: %s", e)
        return "❌ Ocurrió un error al consultar tus movimientos.\nIntenta de nuevo o escribe /help."


def _procesar_categorias(usuario: Dict[str, Any]) -> str:
    """Muestra las categorías del usuario."""
    try:
        categorias_gastos = database.obtener_categorias(usuario["id"], "gastos")
        categorias_ingresos = database.obtener_categorias(usuario["id"], "ingresos")
        categorias_ahorros = database.obtener_categorias(usuario["id"], "ahorros")
        categorias_inversiones = database.obtener_categorias(usuario["id"], "inversiones")

        lineas = [formato.header("📋", "Tus categorías"), formato.SEPARADOR]

        if categorias_gastos:
            lineas.append(f"{formato.EMOJI_GASTO} **Gastos**")
            for cat in categorias_gastos:
                lineas.append(f"• {cat['nombre']} - {cat.get('descripcion', '')}")

        if categorias_ingresos:
            lineas.append("")
            lineas.append(f"{formato.EMOJI_INGRESO} **Ingresos**")
            for cat in categorias_ingresos:
                lineas.append(f"• {cat['nombre']} - {cat.get('descripcion', '')}")

        if categorias_ahorros:
            lineas.append("")
            lineas.append("**Ahorros**")
            for cat in categorias_ahorros:
                lineas.append(f"• {cat['nombre']} - {cat.get('descripcion', '')}")

        if categorias_inversiones:
            lineas.append("")
            lineas.append("**Inversiones**")
            for cat in categorias_inversiones:
                lineas.append(f"• {cat['nombre']} - {cat.get('descripcion', '')}")

        if not (categorias_gastos or categorias_ingresos or categorias_ahorros or categorias_inversiones):
            lineas.append("\n📝 No tienes categorías configuradas todavía. ¡Crea algunas para empezar!")

        lineas.append("\n¿Crear una categoría o registrar una transacción?")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error al obtener categorías: %s", e)
        return "❌ Ocurrió un error al obtener tus categorías.\nIntenta de nuevo o escribe /help."


def _procesar_metas_ahorro(usuario: Dict[str, Any]) -> str:
    """Muestra las metas de ahorro del usuario con su progreso."""
    try:
        metas = database.obtener_metas_ahorro(usuario["id"])
        if not metas:
            return "🎯 No tienes metas de ahorro.\n\nUsa: `Quiero ahorrar $5000 para vacaciones`"

        lineas = [formato.header(formato.EMOJI_META, "Tus metas de ahorro"), formato.SEPARADOR]
        for m in metas:
            objetivo = m.get("objetivo", 0)
            actual = m.get("cantidad_actual", 0) or 0
            nombre = m.get("nombre", "Meta")
            progreso = (actual / objetivo * 100) if objetivo > 0 else 0
            restante = objetivo - actual
            lineas.append("")
            lineas.append(f"**{nombre}**")
            lineas.append(f"${formato.fmt_monto(actual)} / ${formato.fmt_monto(objetivo)} ({progreso:.0f}%)")
            lineas.append(f"Restante: **${formato.fmt_monto(restante)}**")
            lineas.append(formato.barra_progreso(progreso))
            if m.get("fecha_meta"):
                lineas.append(f"Meta para: {str(m['fecha_meta'])[:10]}")
        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error al obtener metas de ahorro: %s", e)
        return "❌ Ocurrió un error al obtener tus metas de ahorro.\nIntenta de nuevo o escribe /help."


def _emoji_categoria(nombre: Optional[str]) -> str:
    """Emoji sugerido según el nombre de la categoría."""
    n = (nombre or "").lower()
    mapa = [
        ("comida", "🍔"), ("restaur", "🍽️"), ("cafe", "☕"), ("super", "🛒"), ("mercado", "🛒"),
        ("transporte", "🚕"), ("taxi", "🚕"), ("combust", "⛽"), ("gasolina", "⛽"), ("buses", "🚌"),
        ("salud", "💊"), ("medic", "💊"), ("farmac", "💊"),
        ("educ", "🎓"), ("escuela", "🎒"), ("curso", "📚"),
        ("ropa", "👕"), ("vest", "👗"), ("zapat", "👟"),
        ("hogar", "🏠"), ("casa", "🏠"), ("alquiler", "🏠"), ("luz", "💡"), ("agua", "🚰"), ("internet", "📶"),
        ("telefono", "📱"), ("celular", "📱"),
        ("entreten", "🎬"), ("cine", "🎬"), ("juego", "🎮"), ("suscrip", "📺"),
        ("deporte", "⚽"), ("gym", "🏋️"),
        ("salario", "💼"), ("sueldo", "💼"), ("trabajo", "💼"), ("nómina", "💼"),
        ("negocio", "🏪"), ("venta", "🏪"), ("freelance", "💻"), ("trading", "📈"),
        ("inversion", "📈"), ("ahorro", "🐷"), ("meta", "🎯"),
        ("impuesto", "🧾"), ("servicio", "🔧"), ("pago", "💳"),
        ("fiesta", "🎉"), ("regalo", "🎁"), ("donacion", "🤝"),
    ]
    for clave, emoji in mapa:
        if clave in n:
            return emoji
    return "📦"


def _procesar_resumen_mensual(usuario: Dict[str, Any]) -> str:
    """Muestra un resumen del mes actual: movimientos, top categorías, mayor gasto,
    promedio diario y balance actual."""
    try:
        from datetime import date
        hoy = date.today()
        inicio = hoy.replace(day=1).isoformat()
        fin = hoy.isoformat()

        moneda_lookup = _moneda_lookup_usuario(usuario)
        balance_mes = database.obtener_balance(usuario["id"], fecha_inicio=inicio)
        por_moneda = balance_mes.get("por_moneda", {})

        nombre_mes = {v: k for k, v in MESES_ES.items()}.get(hoy.month, str(hoy.month))
        lineas = [formato.header(formato.EMOJI_PRESUPUESTO, f"Resumen de {nombre_mes}"), formato.SEPARADOR]

        # --- Monedas activas del mes (o fallback "Sin moneda") ---
        monedas_activas = [(abrev, d) for abrev, d in por_moneda.items()]
        if not monedas_activas or (len(monedas_activas) == 1 and monedas_activas[0][0] == "Sin moneda"):
            if not balance_mes.get("ingresos") and not balance_mes.get("gastos"):
                lineas.append("\n😴 Sin movimientos este mes.")
                return "\n".join(lineas)
            monedas_activas = [(
                "Sin moneda",
                {"simbolo": "$", "ingresos": balance_mes.get("ingresos", 0),
                 "gastos": balance_mes.get("gastos", 0), "nombre": "Sin moneda"},
            )]

        def _fmt_cur(abrev: str, d: Dict[str, Any], val: float, signo: bool = False) -> str:
            return formato.fmt_moneda(
                val, abrev=(None if abrev == "Sin moneda" else abrev),
                signo=signo, simbolo=d.get("simbolo", "$"),
            )

        # --- Movimientos del mes (compacto por moneda) ---
        for abrev, d in monedas_activas:
            if d["ingresos"]:
                lineas.append(f"{formato.EMOJI_INGRESO} {_fmt_cur(abrev, d, d['ingresos'])}")
        for abrev, d in monedas_activas:
            if d["gastos"]:
                lineas.append(f"{formato.EMOJI_GASTO} {_fmt_cur(abrev, d, d['gastos'])}")
        neto_linea = " **·** ".join(
            f"**{_fmt_cur(abrev, d, d['ingresos'] - d['gastos'], signo=True)}**"
            for abrev, d in monedas_activas if d["ingresos"] or d["gastos"]
        )
        if neto_linea:
            lineas.append(f"{formato.EMOJI_BALANCE} Neto: {neto_linea}")

        # --- Gastos del mes agrupados por moneda y categoría ---
        gastos_mes = database.obtener_transacciones_por_fecha(usuario["id"], inicio, fin, "gasto")
        por_cat_cur: Dict[str, Dict[str, float]] = {}
        for t in gastos_mes:
            cat = t.get("categoria_nombre") or "Otros"
            mid = t.get("moneda_id")
            m = moneda_lookup.get(mid)
            abrev = m["abreviatura"] if m else "Sin moneda"
            por_cat_cur.setdefault(abrev, {}).setdefault(cat, 0.0)
            por_cat_cur[abrev][cat] += float(t.get("cantidad", 0))

        if por_cat_cur:
            for abrev, cats in por_cat_cur.items():
                total_cur = sum(cats.values())
                if total_cur <= 0:
                    continue
                simbolo_cur = next((d.get("simbolo", "$") for a, d in monedas_activas if a == abrev), "$")
                lineas.append(f"\n**Gastos por categoría{f' ({abrev})' if abrev != 'Sin moneda' else ''}**")
                top = sorted(cats.items(), key=lambda kv: kv[1], reverse=True)[:5]
                for cat, monto in top:
                    pct = monto / total_cur * 100
                    barra = formato.barra_progreso(pct)
                    label = f"{_emoji_categoria(cat)} {cat}"
                    lineas.append(
                        f"{label:<24}{barra} {pct:.0f}% — {simbolo_cur}{formato.fmt_monto(monto)}"
                    )

            # --- Mayor gasto individual del mes ---
            mayor = max(gastos_mes, key=lambda t: float(t.get("cantidad", 0)))
            cat_m = mayor.get("categoria_nombre") or "Otros"
            fecha_m = (mayor.get("fecha") or "")[:10]
            monto_m = _formatear_monto(moneda_lookup, mayor.get("moneda_id"), float(mayor.get("cantidad", 0)))
            lineas.append(
                f"\nMayor gasto: {_emoji_categoria(cat_m)} {cat_m}, {monto_m}"
                + (f" el día {fecha_m[8:10]}" if fecha_m else "")
            )

            # --- Promedio diario de gasto ---
            dias = hoy.day
            if dias > 0:
                promedios = [
                    f"{_fmt_cur(abrev, d, d['gastos'] / dias)}/día"
                    for abrev, d in monedas_activas if d["gastos"] > 0
                ]
                if promedios:
                    lineas.append(f"Promedio diario: {' · '.join(promedios)}")
        else:
            lineas.append("\n📝 Sin gastos registrados este mes.")

        # --- Balance del mes (por defecto el bot consulta el mes en curso) ---
        balance_act = database.obtener_balance(usuario["id"])
        pa = balance_act.get("por_moneda", {})
        lineas.append(f"\n{formato.EMOJI_BALANCE} **Balance del mes:**")
        if pa and not (len(pa) == 1 and "Sin moneda" in pa):
            partes = []
            for abrev, d in pa.items():
                neto = d["ingresos"] - d["gastos"]
                partes.append(
                    f"**{formato.fmt_moneda(neto, abrev=abrev, signo=True, simbolo=d.get('simbolo', '$'))}**"
                )
            lineas.append(" · ".join(partes))
        elif pa:
            neto = balance_act.get("neto", 0)
            lineas.append(f"**{formato.fmt_moneda(neto, signo=True)}**")
        else:
            lineas.append("**$0.00**")

        return "\n".join(lineas)
    except Exception as e:
        logger.error("Error en resumen mensual: %s", e)
        return "❌ Ocurrió un error al generar tu resumen."


# ============================================================
# PARSING DE MÚLTIPLES TRANSACCIONES
# ============================================================

# Palabras que indican separación entre transacciones
SEPARADORES_MENSAJE = re.compile(
    r'\s*(?:'
    r'\by\s+también\b|\by\s+además\b|\by\b'
    r'|\btambién\b|\bademás\b'
    r'|\bluego\b|\bdespués\b|\bdespues\b'
    r'|\bes\s+todo\b|\bes\s+todo\s+lo\s+que\b'
    r'|,\s*;?\s*'
    r')\s*',
    re.IGNORECASE
)


def _normalizar_separador_decimal(num_str: str) -> str:
    """
    Normaliza el separador decimal de un número según el contexto.
    Prioridad: punto (.) = decimal (formato americano/estándar de programación).
    Reglas:
      - "322.45"      -> "322.45"   (punto decimal)
      - "1,234.56"    -> "1234.56"  (coma miles, punto decimal)
      - "322,45"      -> "322.45"   (coma decimal)
      - "1.234,56"    -> "1234.56"  (punto miles, coma decimal)
      - "1,500"       -> "1500"     (coma miles)
      - "1.248.50"    -> "1248.50"  (puntos miles, último decimal)
    """
    if ',' in num_str and '.' in num_str:
        ultima_coma = num_str.rfind(',')
        ultimo_punto = num_str.rfind('.')
        if ultima_coma > ultimo_punto and 1 <= len(num_str) - ultima_coma - 1 <= 2:
            # Formato europeo: "1.234,56" -> coma decimal, puntos miles
            return num_str.replace('.', '').replace(',', '.')
        if ultimo_punto > ultima_coma and 1 <= len(num_str) - ultimo_punto - 1 <= 2:
            # Formato americano: "1,234.56" -> coma miles, punto decimal
            return num_str.replace(',', '')
        return num_str.replace(',', '')
    if ',' in num_str:
        partes = num_str.split(',')
        if 1 <= len(partes[-1]) <= 2:
            # "322,45" -> coma decimal
            return partes[0] + '.' + partes[-1]
        # "1,500" / "1,500,000" -> coma miles
        return num_str.replace(',', '')
    if '.' in num_str:
        partes = num_str.split('.')
        if len(partes) > 2 and 1 <= len(partes[-1]) <= 2 and all(1 <= len(p) <= 3 for p in partes[:-1]):
            # "1.248.50" -> puntos miles, último decimal
            return partes[0] + ''.join(partes[1:-1]) + '.' + partes[-1]
        # "322.45" -> punto decimal (prioridad)
        return num_str
    return num_str


def _parsear_cantidad(texto: str) -> Optional[float]:
    """
    Parser robusto de cantidades monetarias.
    El punto (.) es decimal por prioridad; la coma (,) se interpreta como
    decimal o miles según el contexto.
    Ejemplos: $248.50 → 248.5, 1,500 → 1500, 1,248.50 → 1248.5,
              322.45 → 322.45, 322,45 → 322.45, 1.234,56 → 1234.56
    Retorna float o None si no encuentra número.
    """
    # Eliminar espacios que separan miles: "1 248" -> "1248"
    texto = re.sub(r'(?<=\d)\s(?=\d{3})', '', texto)
    # Normalizar "dólares"/"dolares"/"pesos" a "$"
    texto = re.sub(r'\b(dólares?|dolares?|pesos?|bs?\.?)\b', '$', texto, flags=re.IGNORECASE)
    # Eliminar símbolos de moneda
    texto_limpio = re.sub(r'[\$\€\£\¥\¢]', '', texto)

    # Tomar el candidato numérico más significativo (más largo)
    candidatos = re.findall(r'\d+(?:[.,]\d+)*', texto_limpio)
    if not candidatos:
        return None

    num_str = max(candidatos, key=len)
    try:
        return float(_normalizar_separador_decimal(num_str))
    except ValueError:
        return None


def _esensaje_multi_transaccion(mensaje: str) -> bool:
    """
    Detecta si un mensaje contiene múltiples transacciones.
    Usa múltiples señales: varios montos, conectores temporales, verbos de acción repetidos.
    """
    msg = mensaje.lower()

    # Señal 1: Dos o más montos con símbolo $
    montos_dolar = re.findall(r'\$[\d\.,]+', mensaje)
    if len(montos_dolar) >= 2:
        return True

    # Señal 2: Dos o más números seguidos de contexto monetario (con o sin verbos)
    montos_texto = re.findall(
        r'\d+(?:[.,]\d+)?\s*(?:dólares?|dolares?|pesos?|bs?\.?|en\s|de\s|para\s)',
        msg
    )
    if len(montos_texto) >= 2:
        return True

    # Señal 3: Dos o más números con palabras de contexto entre ellos
    # Ej: "50 taxi 100 comida", "comida 50 transporte 100"
    numeros_con_contexto = re.findall(
        r'\d+(?:[.,]\d+)?\s*\w+',
        msg
    )
    if len(numeros_con_contexto) >= 2:
        return True

    # Señal 4: Números separados por conectores
    # Ej: "50 en taxi. 100 en comida", "50 taxi; 100 comida"
    tiene_dos_numeros = len(re.findall(r'\d+', msg)) >= 2
    tiene_separador = any(s in msg for s in [
        ".", ";", "y", "luego", "después", "despues", "también", "tambien",
        "además", "ademas", "ah y", "por cierto", "de paso",
    ])
    if tiene_dos_numeros and tiene_separador:
        return True

    # Señal 5: Números + conectores temporales que indican secuencia de acciones
    tiene_conector = any(w in msg for w in [
        "luego", "después", "despues", "y también", "y tambien",
        "además", "ademas", "es todo lo que", "es todo"
    ])
    tiene_numero = bool(re.search(r'\d+', msg))
    tiene_verbo_accion = any(w in msg for w in [
        "gasté", "gaste", "compré", "compre", "pagué", "pague",
        "recibí", "recibi", "cobré", "cobro", "gané", "gane",
        "ingresé", "ingrese", "costó", "costo", "perdí", "perdi",
        "me costó", "me costo", "me salió", "me salio", "me cobró", "me cobro",
    ])
    if tiene_conector and tiene_numero and tiene_verbo_accion:
        return True

    return False


def _split_transacciones(mensaje: str) -> List[str]:
    """
    Divide un mensaje en fragmentos, cada uno conteniendo una transacción.
    Maneja conectores naturales: 'y', 'luego', 'después', comas, puntos, etc.
    """
    # Paso 1: Normalizar separadores fuertes a marcador
    msg = mensaje
    for sep in [r'\bluego\b', r'\bdespués\b', r'\bdespues\b', r'\bes\s+todo\b',
                r'\by\s+también\b', r'\by\s+tambien\b', r'\bademás\b', r'\bademas\b',
                r'\bpor\s+cierto\b', r'\bde\s+paso\b', r'\bpor\s+último\b', r'\bpor\s+ultimo\b',
                r'\by\s+otra\s+cosa\b', r'\by\s+una\s+cosa\s+más\b', r'\by\s+una\s+cosa\s+mas\b',
                r'\bah\s*,?\s*y\b']:
        msg = re.sub(sep, ' ||| ', msg, flags=re.IGNORECASE)

    # Paso 2: Separar por marcador fuerte
    fragmentos = [f.strip() for f in re.split(r'\|\|\|', msg) if f.strip()]

    # Paso 3: Separar por puntuación fuerte (punto y coma, dos puntos)
    # NOTA: NO separamos por "." porque el punto es EXCLUSIVAMENTE decimal (234.60)
    fragmentos_puntuacion = []
    for frag in fragmentos:
        partes = re.split(r'[;:]\s*', frag)
        if len(partes) >= 2 and sum(1 for p in partes if re.search(r'[\d.]+', p)) >= 2:
            fragmentos_puntuacion.extend([p.strip() for p in partes if p.strip()])
        else:
            fragmentos_puntuacion.append(frag)
    fragmentos = fragmentos_puntuacion

    # Paso 3b: Separar por "también"/"tambien" (sin "y" delante)
    fragmentos_tambien = []
    for frag in fragmentos:
        partes = re.split(r'\s*también\s+|\s*tambien\s*', frag, flags=re.IGNORECASE)
        if len(partes) >= 2 and sum(1 for p in partes if re.search(r'[\d.]+', p)) >= 2:
            fragmentos_tambien.extend([p.strip() for p in partes if p.strip()])
        else:
            fragmentos_tambien.append(frag)
    fragmentos = fragmentos_tambien

    # Paso 4: Para cada fragmento, intentar separar por comas si hay acción múltiple
    fragmentos_expandidos = []
    for frag in fragmentos:
        # Proteger comas dentro de números decimales (248,50 → 248{COMA}50)
        frag_protegido = re.sub(r'(\d),(\d)', r'\1{COMA}\2', frag)
        partes_coma = re.split(r',\s*', frag_protegido)
        # Restaurar comas protegidas
        partes_coma = [p.replace('{COMA}', ',') for p in partes_coma]
        if len(partes_coma) >= 2 and sum(1 for p in partes_coma if re.search(r'[\d.]+', p)) >= 2:
            fragmentos_expandidos.extend([p.strip() for p in partes_coma if p.strip()])
        else:
            fragmentos_expandidos.append(frag)

    # Paso 5: Separar por "y" + verbo de acción O "y" + número O "y" + contexto monetario
    verbos_accion = [
        "gasté", "gaste", "compré", "compre", "pagué", "pague", "costó", "costo",
        "recibí", "recibi", "cobré", "cobro", "gané", "gane", "ingresé", "ingrese",
        "perdí", "perdi", "pagamos", "compramos", "gastamos", "cobramos", "ganamos",
        "recibimos", "ingresamos", "salí", "salio", "salimos",
        "me costó", "me costo", "me salió", "me salio", "me cobró", "me cobro",
    ]
    verbo_pattern = '|'.join(re.escape(v) for v in verbos_accion)
    resultado = []
    for frag in fragmentos_expandidos:
        # Separar por "y" + verbo
        partes = re.split(
            r'\s+y\s+(?:' + verbo_pattern + r')',
            frag, flags=re.IGNORECASE
        )
        # También separar por "y" + "$" (ej: "comida y $20 de transporte")
        partes_expandidas = []
        for p in partes:
            sub = re.split(r'\s+y\s+\$', p, flags=re.IGNORECASE)
            partes_expandidas.extend(sub)
        # También separar por "y" + número (ej: "50 en taxi y 100 en comida")
        partes_finales = []
        for p in partes_expandidas:
            sub = re.split(r'\s+y\s+(?=[\d.])', p, flags=re.IGNORECASE)
            partes_finales.extend(sub)
        # Separar por "y" + palabra de contexto + número (ej: "taxi 50 y uber 30")
        # Usar lookahead para no consumir la palabra de contexto
        CONTEXT_WORDS = r'(?:taxi|uber|bus|comida|supermercado|restaurante|farmacia|ropa|luz|agua|internet|alquiler|salario|sueldo|bonus|regalo|venta|compra|pago|transporte|servicio|ocio|salud|educación)'
        partes_ctx = []
        for p in partes_finales:
            sub = re.split(r'\s+y\s+(?=' + CONTEXT_WORDS + r'\s+[\d.])', p, flags=re.IGNORECASE)
            partes_ctx.extend(sub)
        resultado.extend([p.strip() for p in partes_ctx if p.strip()])

    # Paso 6: Filtrar fragmentos sin número
    result = [f for f in resultado if re.search(r'[\d.]+', f)]

    # Paso 7: Si un fragmento tiene dos números con palabra de contexto entre ellos,
    # separar por la palabra de contexto (ej: "50 taxi 100 comida" → "50 taxi" + "100 comida")
    CTX = r'(?:taxi|uber|bus|comida|supermercado|restaurante|farmacia|ropa|luz|agua|internet|alquiler|salario|sueldo|bonus|regalo|venta|compra|pago|transporte|servicio|ocio|salud|educación)'
    result_final = []
    for f in result:
        # Buscar patrón: número + palabra_contexto + número (preservando decimales)
        match = re.search(r'([\d.]+)\s+' + CTX + r'\s+([\d.]+)', f, flags=re.IGNORECASE)
        if match:
            # Encontrar el índice donde empieza la palabra de contexto
            ctx_match = re.search(r'\s+' + CTX + r'\s+', f, flags=re.IGNORECASE)
            if ctx_match:
                idx = ctx_match.start()
                primera = f[:idx].strip()
                segunda = f[idx:].strip()
                if primera and re.search(r'[\d.]+', primera):
                    result_final.append(primera)
                if segunda and re.search(r'[\d.]+', segunda):
                    result_final.append(segunda)
                continue
        result_final.append(f)

    return result_final if result_final else [mensaje]


def _detectar_cantidad_en_texto(texto: str) -> Optional[float]:
    """Detecta una cantidad monetaria en un fragmento de texto."""
    return _parsear_cantidad(texto)


def _detectar_tipo_en_texto(texto: str) -> Optional[str]:
    """Detecta si un fragmento describe un gasto o ingreso."""
    t = texto.lower()
    gasto_kw = [
        "gasté", "gaste", "gasto", "gastos", "compré", "compre", "compra", "compras",
        "pagué", "pague", "pago", "pagos", "costó", "costo", "pagar",
        "perdí", "perdi", "pérdida", "perdida",
        "invertí", "inverti", "inversión", "inversion",
        "me costó", "me costo", "me salió", "me salio", "me cobró", "me cobro",
        "le di", "le pagué", "le pague",
    ]
    ingreso_kw = [
        "recibí", "recibi", "ingresé", "ingrese", "cobré", "cobro",
        "gané", "gane", "salario", "sueldo", "ingreso", "ingresos",
        "bonus", "bono", "regalo", "ganancia", "dividendos", "intereses",
        "agrega", "agregar", "remuneración", "herencia",
        "me dieron", "me pagan", "me pagan",
    ]
    if any(re.search(r'\b' + kw + r'\b', t) for kw in gasto_kw):
        return "gasto"
    if any(re.search(r'\b' + kw + r'\b', t) for kw in ingreso_kw):
        return "ingreso"
    return None


_GRUPOS_GASTO = {
    "comida": ["comida", "comer", "almuerzo", "cena", "desayuno", "restaurante",
               "restaurant", "mcdo", "mcdonald", "burger", "pizza", "supermercado",
               "super", "mercado", "almacén", "almacen"],
    "ocio": ["ocio", "entretenimiento", "diversión", "diversion", "juego",
            "juegos", "cinema", "cine", "teatro", "concierto", "música",
            "musica", "netflix", "spotify", "streaming", "cerveza", "cervezas",
            "bar", "birra", "alcohol", "trago", "tragos", "copa", "copas",
            "fiesta", "party", "rumba", "disco"],
    "transporte": ["transporte", "gasolina", "uber", "taxi", "bus", "peaje",
                  "estacionamiento", "parking", "mecánico", "mekaniko",
                  "combustible", "nafta", "garaje"],
    "servicio": ["servicio", "servicios", "luz", "agua", "internet", "teléfono",
                "telefono", "cable", "electricidad"],
    "hogar": ["hogar", "casa", "alquiler", "renta", "hipoteca", "mantenimiento",
             "reparación", "reparacion", "mueble"],
    "salud": ["salud", "médico", "medico", "farmacia", "medicina", "doctor",
             "hospital", "clínica", "clinica", "dentista"],
    "educación": ["educación", "educacion", "curso", "clase", "universidad",
                 "colegio", "escuela", "libro", "libros", "uteniles", "útiles"],
    "ropa": ["ropa", "vestido", "camisa", "pantalón", "zapato", "calzado",
            "tienda"],
    "tecnología": ["tecnología", "tecnologia", "computadora", "celular",
                  "teléfono", "telefono", "electrónica", "electronica", "equipo"],
    "suscripción": ["suscripción", "suscripcion", "mensualidad", "abono"],
}

_GRUPOS_INGRESO = {
    "salario": ["salario", "sueldo", "remuneración", "remuneracion", "pago",
               "nómina", "nomina"],
    "bonus": ["bonus", "bono", "bonificación", "bonificacion", "prima",
             "comisión", "comision"],
    "inversiones": ["inversión", "inversion", "inversiones", "dividendos",
                  "intereses", "bitcoin", "crypto", "staking", "acciones"],
    "regalos": ["regalo", "regalos", "herencia", "donación", "donacion"],
    "ventas": ["venta", "ventas", "vendí", "vendi", "cobro"],
}


def _detectar_categoria_en_texto(texto: str, tipo: str) -> str:
    """Detecta la categoría de un fragmento de texto."""
    t = texto.lower()

    if tipo == "gasto":
        for cat, keywords in _GRUPOS_GASTO.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', t) for kw in keywords):
                return cat

    elif tipo == "ingreso":
        for cat, keywords in _GRUPOS_INGRESO.items():
            if any(re.search(r'\b' + re.escape(kw) + r'\b', t) for kw in keywords):
                return cat

    return "otros"


def _limpiar_nombre_categoria(nombre: Optional[str]) -> str:
    """Limpia un nombre de categoría: sin emojis/símbolos, capitalizado y corto."""
    n = (nombre or "").strip()
    n = re.sub(r'[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9#& ]', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    if not n:
        return ""
    n = n[:40].strip()
    return " ".join(w.capitalize() for w in n.split())


def _grupo_de_nombre(nombre: str, tipo: str) -> Optional[str]:
    """Devuelve el grupo de sinónimos al que pertenece un nombre de categoría."""
    n = _normalizar_texto(nombre)
    mapa = _GRUPOS_GASTO if tipo == "gastos" else _GRUPOS_INGRESO
    for grupo, keywords in mapa.items():
        for kw in keywords:
            if kw in n:
                return grupo
    return None


def _buscar_categoria_existente(usuario: Dict[str, Any], tipo: str, texto: str,
                                candidato: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Busca una categoría existente del usuario que encaje semánticamente con la operación.

    Compara el nombre del candidato, las palabras del texto y el grupo de sinónimos
    para asociar nuevas operaciones a categorías ya creadas."""
    categorias = database.obtener_categorias(usuario["id"], tipo)
    if not categorias:
        return None
    t = _normalizar_texto(texto)
    cand = _normalizar_texto(candidato) if candidato else ""
    grupo_texto = _grupo_de_nombre(t, tipo)
    mejor = None
    mejor_score = 0
    for cat in categorias:
        norm = _normalizar_texto(cat.get("nombre") or "")
        if not norm:
            continue
        score = 0
        if cand and cand == norm:
            score += 4
        elif cand and (cand in norm or norm in cand):
            score += 2
        for p in (p for p in norm.split() if len(p) > 2):
            if p in t:
                score += 2
        grupo_cat = _grupo_de_nombre(norm, tipo)
        if grupo_cat and grupo_cat == grupo_texto:
            score += 2
        if score > mejor_score:
            mejor_score = score
            mejor = cat
    return mejor if mejor_score >= 2 else None


def _categorizar_operacion(usuario: Dict[str, Any], texto: str, tipo: str,
                           candidato_ai: Optional[str] = None) -> tuple:
    """Determina la categoría de una operación.

    Reutiliza una categoría existente si encaja semánticamente; si no, crea una
    nueva con un nombre con sentido (priorizando la sugerencia de la IA)."""
    tipo_cat = "ingresos" if tipo == "ingreso" else "gastos"

    candidato = None
    if candidato_ai and isinstance(candidato_ai, str):
        candidato = _limpiar_nombre_categoria(candidato_ai)
    if not candidato:
        candidato = _limpiar_nombre_categoria(_detectar_categoria_en_texto(texto, tipo))
    if not candidato or candidato == "Otros":
        candidato = "Otros Ingresos" if tipo == "ingreso" else "Otros"

    existente = _buscar_categoria_existente(usuario, tipo_cat, texto, candidato)
    if existente:
        return existente["nombre"], existente["id"]

    try:
        info = database.crear_categoria(usuario["id"], candidato, tipo_cat)
        return candidato, info["id"]
    except Exception as e:
        logger.error("Error creando categoría '%s': %s", candidato, e)
        return candidato, None


def _extraer_descripcion_limpia(texto: str, cantidad_texto: str = "") -> str:
    """Extrae la descripción limpia de un fragmento, removiendo montos, números y verbos."""
    desc = texto
    # Remover el texto del monto si está
    if cantidad_texto:
        desc = desc.replace(cantidad_texto, "")
    # Remover verbos comunes al inicio
    for verb in ["gasté", "gaste", "recibí", "recibi", "compré", "compre",
                 "pagué", "pague", "costó", "costo", "cobré", "cobro",
                 "gané", "gane", "perdí", "perdi", "ingresé", "ingrese",
                 "pagamos", "compramos", "gastamos", "cobramos", "ganamos",
                 "recibimos", "ingresamos", "salimos", "salí", "salio"]:
        if desc.lower().startswith(verb + " "):
            desc = desc[len(verb):].strip()
            break
    # Remover conectores al final (y recibi, y gaste, luego, despues, etc.)
    desc = re.sub(r'\s*,?\s*\by\s+(?:recib[íi]|gast[ée]|compr[ée]|pag[ué]|cobr[éi]|gan[éi]|ingres[éi]|perdí|costó|cobro|salio|salimos)\b.*$', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'\s*,?\s*(?:luego|después|despues|además|ademas)\s+.*$', '', desc, flags=re.IGNORECASE)
    # Remover símbolos de moneda y palabras de moneda
    desc = re.sub(r'[\$\€\£\¥\¢]', '', desc)
    desc = re.sub(r'\b(dólares?|dolares?|pesos?|bs?\.?)\b', '', desc, flags=re.IGNORECASE)
    # Remover números (el monto ya se extrajo)
    desc = re.sub(r'\b\d+(?:[.,]\d+)?\b', '', desc)
    # Remover espacios dobles y puntuación suelta al inicio/final
    desc = re.sub(r'\s+', ' ', desc).strip()
    desc = re.sub(r'^[,;\s]+|[,;\s]+$', '', desc)
    # Limpiar palabras de relleno al inicio
    palabras = desc.split()
    relleno = {"el", "la", "los", "las", "un", "una", "unas", "unos", "de", "del", "en", "por",
               "para", "que", "y", "o", "con", "a", "al", "lo", "le", "se",
               "su", "mis", "tus", "sus", "mi", "tu", "las", "los", "unas", "unos",
               "que", "lo", "q", "he", "hice", "hoy"}
    while palabras and palabras[0].lower() in relleno:
        palabras.pop(0)
    # También limpiar al final
    while palabras and palabras[-1].lower() in relleno:
        palabras.pop()
    return " ".join(palabras).strip() if palabras else ""


def _parsear_multi_transaccion(mensaje: str, usuario: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Parsea un mensaje que puede contener múltiples transacciones.
    Si recibe el usuario, detecta la moneda de cada fragmento.
    Retorna una lista de dicts con: {tipo, cantidad, descripcion, categoria, moneda, moneda_id}
    """
    fragmentos = _split_transacciones(mensaje)

    monedas_usuario = None
    if usuario:
        monedas_usuario = database.obtener_monedas(usuario["id"])

    transacciones = []
    for frag in fragmentos:
        cantidad = _detectar_cantidad_en_texto(frag)
        if cantidad is None or cantidad <= 0:
            continue

        tipo = _detectar_tipo_en_texto(frag)
        if not tipo:
            frag_lower = frag.lower()
            patrones_gasto = ["en ", "para ", "compr", "gast", "pag", "cost",
                             "taxi", "uber", "bus", "comida", "supermercado",
                             "restaurante", "farmacia", "médico", "ropa",
                             "luz", "agua", "internet", "teléfono", "alquiler"]
            if any(w in frag_lower for w in patrones_gasto):
                tipo = "gasto"
            elif re.search(r'\$\s*\d+.*\bde\s+\w', frag_lower):
                tipo = "gasto"
            patrones_ingreso = ["de ", "recib", "cobr", "ingres", "gan",
                               "salario", "sueldo", "bonus", "regalo",
                               "dividendos", "intereses", "venta"]
            if any(w in frag_lower for w in patrones_ingreso):
                tipo = "ingreso"
            else:
                tipo = "gasto"

        categoria = _detectar_categoria_en_texto(frag, tipo)
        descripcion = _extraer_descripcion_limpia(frag)

        moneda = None
        if monedas_usuario:
            moneda = _detectar_moneda_en_texto(frag, monedas_usuario)
            if not moneda and len(monedas_usuario) == 1:
                moneda = monedas_usuario[0]

        transaccion = {
            "tipo": tipo,
            "cantidad": cantidad,
            "descripcion": descripcion or f"Transacción de {formato.fmt_moneda(cantidad)}",
            "categoria": categoria,
        }
        if moneda:
            transaccion["moneda"] = moneda
            transaccion["moneda_id"] = moneda["id"]

        transacciones.append(transaccion)

    return transacciones


def _formatear_preview_transacciones(transacciones: List[Dict[str, Any]]) -> str:
    """Formatea una lista de transacciones como preview para confirmación."""
    if not transacciones:
        return "❌ No pude detectar ninguna transacción en tu mensaje."

    lineas = [formato.header("📋", "Transacciones detectadas"), formato.SEPARADOR]

    for i, t in enumerate(transacciones, 1):
        emoji = formato.EMOJI_INGRESO if t["tipo"] == "ingreso" else formato.EMOJI_GASTO
        label = "Ingreso" if t["tipo"] == "ingreso" else "Gasto"
        desc = t.get("descripcion", "Sin descripción")
        cat = t.get("categoria", "otros")
        moneda = t.get("moneda", {})
        abrev = moneda.get("abreviatura") if moneda else None
        simbolo = moneda.get("simbolo", "$") if moneda else "$"
        monto = formato.fmt_moneda(t["cantidad"], abrev=abrev, simbolo=simbolo)
        lineas.append(f"{emoji} **{i}.** {monto} - {label}: {desc} ({cat})")

    lineas.append(formato.SEPARADOR)

    totales_por_moneda = defaultdict(lambda: {"ingresos": 0.0, "gastos": 0.0, "abrev": None, "simbolo": "$"})
    for t in transacciones:
        moneda = t.get("moneda", {})
        clave = moneda.get("abreviatura") if moneda else "Sin moneda"
        if t["tipo"] == "ingreso":
            totales_por_moneda[clave]["ingresos"] += t["cantidad"]
        else:
            totales_por_moneda[clave]["gastos"] += t["cantidad"]
        totales_por_moneda[clave]["abrev"] = moneda.get("abreviatura") if moneda else None
        totales_por_moneda[clave]["simbolo"] = moneda.get("simbolo", "$") if moneda else "$"

    for clave, datos in totales_por_moneda.items():
        sim = datos.get("simbolo", "$")
        abr = datos.get("abrev")
        if datos["gastos"] > 0:
            lineas.append(f"{formato.EMOJI_GASTO} Total gastos: **{formato.fmt_moneda(datos['gastos'], abrev=abr, simbolo=sim)}**")
        if datos["ingresos"] > 0:
            lineas.append(f"{formato.EMOJI_INGRESO} Total ingresos: **{formato.fmt_moneda(datos['ingresos'], abrev=abr, simbolo=sim)}**")
        neto = datos["ingresos"] - datos["gastos"]
        lineas.append(f"Neto: **{formato.fmt_moneda(neto, abrev=abr, signo=True, simbolo=sim)}**")

    lineas.append("")
    lineas.append("¿Quieres guardar estas transacciones?")

    return "\n".join(lineas)


def _guardar_multi_transacciones(transacciones: List[Dict[str, Any]], usuario: Dict[str, Any]) -> str:
    """Guarda una lista de transacciones en la base de datos."""
    guardadas = 0
    errores = 0

    for t in transacciones:
        try:
            tipo_cat = "ingresos" if t["tipo"] == "ingreso" else "gastos"
            texto_oper = t.get("descripcion") or ""
            categoria, categoria_id = _categorizar_operacion(usuario, texto_oper, t["tipo"], t.get("categoria"))
            if categoria_id is None:
                raise Exception(f"No se pudo crear/asociar la categoría '{categoria}'")

            moneda_id = t.get("moneda_id") or t.get("moneda", {}).get("id")
            database.agregar_transaccion(
                usuario["id"], categoria_id, t["tipo"],
                t["cantidad"], t["descripcion"],
                moneda_id=moneda_id
            )
            guardadas += 1
        except Exception as e:
            logger.error("Error guardando transacción: %s", e)
            errores += 1

    if guardadas == 0:
        return "❌ No pude guardar ninguna transacción. Intenta de nuevo."

    resultado = f"✅ **{guardadas} transacción(es) guardada(s)**"
    if errores > 0:
        resultado += f"\n⚠️ {errores} no se pudieron guardar"

    return resultado


# ============================================================
# FUNCIONES DE MODIFICACIÓN DE TRANSACCIONES
# ============================================================

def _limpiar_descripcion(desc: str) -> str:
    """Elimina prefijos y palabras innecesarias de la descripción."""
    if not desc:
        return ""
    if desc.lower().startswith("gasto: "):
        desc = desc[7:].strip()
    elif desc.lower().startswith("ingreso: "):
        desc = desc[9:].strip()
    # Eliminar palabras verbales al inicio
    for prefijo in ["gasté ", "gaste ", "recibí ", "recibi ", "compré ", "compre ", "pagué ", "pague "]:
        if desc.lower().startswith(prefijo):
            desc = desc[len(prefijo):].strip()
            break
    return desc


def _detectar_modificacion(mensaje: str) -> Dict[str, Any]:
    """
    Detecta qué quiere modificar el usuario y extrae los parámetros.
    Retorna un dict con:
      - accion: "cambiar_tipo" | "cambiar_monto" | "cambiar_descripcion" | "cambiar_categoria" | "cambiar_fecha" | "eliminar" | "desconocido"
      - valor_nuevo: el nuevo valor (si aplica)
      - referencia: texto para buscar la transacción (ej: "último gasto", "$50")
    """
    mensaje_lower = mensaje.lower().strip()
    resultado = {"accion": "desconocido", "valor_nuevo": None, "referencia": None}

    # --- ELIMINAR ---
    if any(w in mensaje_lower for w in ["eliminar", "elimina", "borrar", "borra", "quitar", "quita", "remover", "remueve"]):
        resultado["accion"] = "eliminar"
        resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
        return resultado

    # --- CAMBIAR TIPO (gasto <-> ingreso) ---
    # Patrones amplios: "de gasto a ingreso", "a ingreso", "como ingreso", "que sea ingreso"
    patron_tipo = re.search(
        r'(?:de|desde|que\s+(?:era|fue|es|esta))?\s*(?:gasto|gastos|ingreso|ingresos)'
        r'\s+(?:a|al|para|por|como|que\s+(?:sea|pase|quede|pueda\s+ser))\s*'
        r'(?:un?\s*)?(ingreso|gasto|ingresos|gastos)',
        mensaje_lower
    )
    if patron_tipo:
        nuevo_tipo_raw = patron_tipo.group(1)
        nuevo_tipo = "ingreso" if "ingreso" in nuevo_tipo_raw else "gasto"
        resultado["accion"] = "cambiar_tipo"
        resultado["valor_nuevo"] = nuevo_tipo
        resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
        return resultado

    # Patrones simples: "a ingreso", "a gasto"
    if any(w in mensaje_lower for w in ["a ingreso", "a ingresos", "como ingreso", "tipo ingreso", "que sea ingreso"]):
        resultado["accion"] = "cambiar_tipo"
        resultado["valor_nuevo"] = "ingreso"
        resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
        return resultado

    if any(w in mensaje_lower for w in ["a gasto", "a gastos", "como gasto", "tipo gasto", "que sea gasto"]):
        resultado["accion"] = "cambiar_tipo"
        resultado["valor_nuevo"] = "gasto"
        resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
        return resultado

    # Detectar patrón "de $X a $Y" (referencia = monto viejo)
    patron_de_a = re.search(r'de\s+\$?([\d.,]+)\s+a\s+\$?([\d.,]+)', mensaje_lower)
    if patron_de_a:
        val_viejo = _parsear_cantidad(patron_de_a.group(1))
        val_nuevo = _parsear_cantidad(patron_de_a.group(2))
        if val_viejo and val_nuevo:
            resultado["accion"] = "cambiar_monto"
            resultado["valor_nuevo"] = val_nuevo
            resultado["referencia"] = f"${val_viejo}"
        return resultado

    # --- CAMBIAR MONTO ---
    if any(w in mensaje_lower for w in ["monto", "cantidad", "importe", "precio"]):
        nuevo_monto = _extraer_nuevo_valor(mensaje_lower)
        if nuevo_monto is not None:
            resultado["accion"] = "cambiar_monto"
            resultado["valor_nuevo"] = nuevo_monto
            resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
            return resultado

    # --- CAMBIAR DESCRIPCIÓN ---
    if any(w in mensaje_lower for w in ["descripción", "descripcion", "nombre", "texto", "detalle"]):
        nueva_desc = _extraer_nueva_descripcion(mensaje_lower)
        if nueva_desc:
            resultado["accion"] = "cambiar_descripcion"
            resultado["valor_nuevo"] = nueva_desc
            resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
            return resultado

    # --- CAMBIAR CATEGORÍA ---
    if any(w in mensaje_lower for w in ["categoría", "categoria", "clasificar", "clasificacion"]):
        nueva_cat = _extraer_nueva_categoria(mensaje_lower)
        if nueva_cat:
            resultado["accion"] = "cambiar_categoria"
            resultado["valor_nuevo"] = nueva_cat
            resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
            return resultado

    # --- CAMBIAR FECHA ---
    if any(w in mensaje_lower for w in ["fecha", "día", "dia", "cuándo", "cuando"]):
        nueva_fecha = _extraer_nueva_fecha(mensaje_lower)
        if nueva_fecha:
            resultado["accion"] = "cambiar_fecha"
            resultado["valor_nuevo"] = nueva_fecha
            resultado["referencia"] = _extraer_referencia_transaccion(mensaje_lower)
            return resultado

    return resultado


def _extraer_referencia_transaccion(mensaje_lower: str) -> Optional[str]:
    """
    Extrae una referencia para identificar qué transacción modificar.
    Puede ser: 'último gasto', '$50', 'la de ayer', etc.
    """
    # "el último gasto/ingreso"
    for w in ["último", "ultimo", "ultima", "última", "mas reciente", "más reciente", "reciente"]:
        if w in mensaje_lower:
            if "gasto" in mensaje_lower:
                return "ultimo_gasto"
            if "ingreso" in mensaje_lower:
                return "ultimo_ingreso"
            return "ultimo"

    # "el gasto de $X"
    monto_val = _parsear_cantidad(mensaje_lower)
    if monto_val is not None and ("de" in mensaje_lower or "por" in mensaje_lower):
        return f"${monto_val}"

    # "el gasto/ingreso de ayer/hoy"
    for fecha in ["ayer", "hoy", "anteayer"]:
        if fecha in mensaje_lower:
            if "gasto" in mensaje_lower:
                return f"gasto_{fecha}"
            if "ingreso" in mensaje_lower:
                return f"ingreso_{fecha}"
            return fecha

    # genérico
    if "gasto" in mensaje_lower:
        return "gasto"
    if "ingreso" in mensaje_lower:
        return "ingreso"

    return None


def _extraer_nuevo_valor(mensaje_lower: str) -> Optional[float]:
    """Extrae el nuevo valor/monto del mensaje."""
    return _parsear_cantidad(mensaje_lower)


def _extraer_nueva_descripcion(mensaje_lower: str) -> Optional[str]:
    """Extrae la nueva descripción del mensaje."""
    # "cambia la descripción a X" / "ponle descripción X"
    match = re.search(r'(?:a|como|poner?|ponle?|que diga|que sea)\s+(.+)', mensaje_lower)
    if match:
        desc = match.group(1).strip()
        palabras = desc.split()
        desc_limpia = [p for p in palabras if p not in {
            "el", "la", "los", "las", "un", "una", "de", "del", "por", "para",
            "que", "y", "o", "pero", "también", "tambien",
        } and len(p) > 1]
        return " ".join(desc_limpia) if desc_limpia else None

    return None


def _extraer_nueva_categoria(mensaje_lower: str) -> Optional[str]:
    """Extrae la nueva categoría del mensaje."""
    categorias_conocidas = [
        "comida", "supermercado", "restaurante", "transporte", "gasolina",
        "servicio", "hogar", "salud", "ocio", "educación", "educacion",
        "ropa", "tecnología", "tecnologia", "suscripción", "suscripcion",
        "salario", "bonus", "inversiones", "regalos", "otros",
    ]

    # "a la categoría X" / "en categoría X"
    match = re.search(r'(?:a|en|de|categoría?|categoria?)\s+(?:la\s+)?(?:categoría?\s+)?(\w+)', mensaje_lower)
    if match:
        cat = match.group(1)
        if cat in categorias_conocidas:
            return cat

    # Buscar directamente una categoría conocida
    for cat in categorias_conocidas:
        if cat in mensaje_lower:
            return cat

    return None


def _extraer_nueva_fecha(mensaje_lower: str) -> Optional[str]:
    """Extrae la nueva fecha del mensaje."""
    from datetime import datetime, timedelta

    hoy = datetime.now()

    textos_fecha = {
        "hoy": hoy.strftime("%Y-%m-%d"),
        "ayer": (hoy - timedelta(days=1)).strftime("%Y-%m-%d"),
        "anteayer": (hoy - timedelta(days=2)).strftime("%Y-%m-%d"),
        "el lunes": (hoy - timedelta(days=(hoy.weekday() + 7) % 7 or 7)).strftime("%Y-%m-%d"),
        "el martes": (hoy - timedelta(days=(hoy.weekday() - 1 + 7) % 7 or 7)).strftime("%Y-%m-%d"),
        "el miércoles": (hoy - timedelta(days=(hoy.weekday() - 2 + 7) % 7 or 7)).strftime("%Y-%m-%d"),
        "el jueves": (hoy - timedelta(days=(hoy.weekday() - 3 + 7) % 7 or 7)).strftime("%Y-%m-%d"),
        "el viernes": (hoy - timedelta(days=(hoy.weekday() - 4 + 7) % 7 or 7)).strftime("%Y-%m-%d"),
    }

    for key, fecha in textos_fecha.items():
        if key in mensaje_lower:
            return fecha

    # Buscar formato YYYY-MM-DD
    match = re.search(r'(\d{4}-\d{2}-\d{2})', mensaje_lower)
    if match:
        return match.group(1)

    # Buscar formato DD/MM/YYYY o DD-MM-YYYY
    match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', mensaje_lower)
    if match:
        return f"{match.group(3)}-{match.group(2).zfill(2)}-{match.group(1).zfill(2)}"

    return None


def _buscar_transaccion(usuario: Dict[str, Any], referencia: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Busca una transacción del usuario basándose en una referencia.
    Retorna la transacción encontrada o None.
    """
    if not referencia:
        # Sin referencia: tomar la última transacción
        transacciones = database.obtener_transacciones(usuario["id"], 1)
        return transacciones[0] if transacciones else None

    # "ultimo_gasto"
    if referencia == "ultimo_gasto":
        transacciones = database.obtener_transacciones(usuario["id"], 10, "gasto")
        return transacciones[0] if transacciones else None

    # "ultimo_ingreso"
    if referencia == "ultimo_ingreso":
        transacciones = database.obtener_transacciones(usuario["id"], 10, "ingreso")
        return transacciones[0] if transacciones else None

    # "ultimo" (cualquiera)
    if referencia == "ultimo":
        transacciones = database.obtener_transacciones(usuario["id"], 1)
        return transacciones[0] if transacciones else None

    # "$X" - buscar por monto
    if referencia.startswith("$"):
        monto_str = referencia[1:]
        try:
            monto = float(monto_str)
        except ValueError:
            return None
        transacciones = database.obtener_transacciones(usuario["id"], 50)
        for t in transacciones:
            if abs(t["cantidad"] - monto) < 0.01:
                return t
        return None

    # "gasto_ayer" / "ingreso_ayer" etc
    if "_ayer" in referencia or "_hoy" in referencia:
        partes = referencia.split("_")
        tipo = partes[0] if partes[0] in ("gasto", "ingreso") else None
        fecha_ref = partes[1] if len(partes) > 1 else None

        transacciones = database.obtener_transacciones(usuario["id"], 50, tipo)
        if fecha_ref == "ayer":
            from datetime import datetime, timedelta
            fecha_ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            for t in transacciones:
                if t.get("fecha", "").startswith(fecha_ayer):
                    return t
        elif fecha_ref == "hoy":
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            for t in transacciones:
                if t.get("fecha", "").startswith(fecha_hoy):
                    return t

        return transacciones[0] if transacciones else None

    # "gasto" o "ingreso" genérico
    if referencia in ("gasto", "ingreso"):
        transacciones = database.obtener_transacciones(usuario["id"], 1, referencia)
        return transacciones[0] if transacciones else None

    # "ayer" genérico
    if referencia == "ayer":
        from datetime import datetime, timedelta
        fecha_ayer = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        transacciones = database.obtener_transacciones(usuario["id"], 50)
        for t in transacciones:
            if t.get("fecha", "").startswith(fecha_ayer):
                return t
        return None

    return None


def _procesar_modificar_transaccion(mensaje: str, usuario: Dict[str, Any]) -> str:
    """Procesa una solicitud de modificación de transacción."""
    mod = _detectar_modificacion(mensaje)
    accion = mod["accion"]

    if accion == "desconocido":
        return (
            "🤔 No pude entender qué quieres modificar.\n\n"
            "Puedes hacer cosas como:\n"
            "• 'Cambia el gasto a ingreso'\n"
            "• 'Modifica el monto a $100'\n"
            "• 'Cambia la descripción a almuerzo'\n"
            "• 'Cambia la categoría a transporte'\n"
            "• 'Elimina el último gasto'"
        )

    # Buscar la transacción objetivo
    transaccion = _buscar_transaccion(usuario, mod["referencia"])

    if not transaccion:
        return "❌ No encontré la transacción que quieres modificar. ¿Puedes especificar cuál?"

    tid = transaccion["id"]

    # --- ELIMINAR ---
    if accion == "eliminar":
        confirmado = database.eliminar_transaccion(usuario["id"], tid)
        if confirmado:
            tipo_icono = formato.EMOJI_GASTO if transaccion["tipo"] == "gasto" else formato.EMOJI_INGRESO
            tipo_label = "Gasto" if transaccion["tipo"] == "gasto" else "Ingreso"
            desc = _limpiar_descripcion(transaccion.get("descripcion", "Sin descripción"))
            return (
                f"{formato.EMOJI_ELIMINAR} **Transacción eliminada:**\n"
                f"{tipo_icono} {formato.fmt_moneda(transaccion['cantidad'])} - {tipo_label}: {desc}"
            )
        return f"{formato.EMOJI_ERROR} No pude eliminar la transacción.\nIntenta de nuevo o escribe /help."

    # --- CAMBIAR TIPO ---
    if accion == "cambiar_tipo":
        nuevo_tipo = mod["valor_nuevo"]
        if nuevo_tipo == transaccion["tipo"]:
            return f"ℹ️ La transacción ya es un **{nuevo_tipo}**. No hay cambios necesarios."

        # Buscar o crear categoría del nuevo tipo
        nuevo_tipo_cat = "ingresos" if nuevo_tipo == "ingreso" else "gastos"
        categorias = database.obtener_categorias(usuario["id"], nuevo_tipo_cat)
        nueva_categoria_id = categorias[0]["id"] if categorias else None

        if not nueva_categoria_id:
            cat_info = database.crear_categoria(usuario["id"], "otros", nuevo_tipo_cat)
            nueva_categoria_id = cat_info["id"]

        actualizada = database.actualizar_transaccion(
            usuario["id"], tid,
            tipo=nuevo_tipo,
            categoria_id=nueva_categoria_id
        )

        if actualizada:
            emoji_nuevo = formato.EMOJI_INGRESO if nuevo_tipo == "ingreso" else formato.EMOJI_GASTO
            label_nuevo = "Ingreso" if nuevo_tipo == "ingreso" else "Gasto"
            label_viejo = "Gasto" if nuevo_tipo == "ingreso" else "Ingreso"
            icono_viejo = formato.EMOJI_GASTO if nuevo_tipo == "ingreso" else formato.EMOJI_INGRESO
            desc = _limpiar_descripcion(transaccion.get("descripcion", "Sin descripción"))
            return (
                f"{formato.EMOJI_OK} **Tipo cambiado:**\n"
                f"De: {icono_viejo} {label_viejo}: {desc}\n"
                f"A: {emoji_nuevo} {formato.fmt_moneda(transaccion['cantidad'])} - {label_nuevo}: {desc}"
            )
        return f"{formato.EMOJI_ERROR} No pude cambiar el tipo.\nIntenta de nuevo o escribe /help."

    # --- CAMBIAR MONTO ---
    if accion == "cambiar_monto":
        nuevo_monto = mod["valor_nuevo"]
        if nuevo_monto is None or nuevo_monto <= 0:
            return "❌ El monto nuevo no es válido. Especificá un número positivo."

        actualizada = database.actualizar_transaccion(
            usuario["id"], tid, cantidad=nuevo_monto
        )
        if actualizada:
            return (
                f"{formato.EMOJI_OK} **Monto actualizado:**\n"
                f"De {formato.fmt_moneda(transaccion['cantidad'])} → **{formato.fmt_moneda(nuevo_monto)}**"
            )
        return f"{formato.EMOJI_ERROR} No pude actualizar el monto.\nIntenta de nuevo o escribe /help."

    # --- CAMBIAR DESCRIPCIÓN ---
    if accion == "cambiar_descripcion":
        nueva_desc = mod["valor_nuevo"]
        if not nueva_desc:
            return "❌ No pude entender la nueva descripción. Especificá el texto."

        actualizada = database.actualizar_transaccion(
            usuario["id"], tid, descripcion=nueva_desc
        )
        if actualizada:
            return (
                f"✅ **Descripción actualizada:**\n"
                f"De '{transaccion.get('descripcion', 'Sin descripción')}' → **'{nueva_desc}'**"
            )
        return "❌ No pude actualizar la descripción. Intenta de nuevo."

    # --- CAMBIAR CATEGORÍA ---
    if accion == "cambiar_categoria":
        nueva_cat_nombre = mod["valor_nuevo"]
        if not nueva_cat_nombre:
            return "❌ No pude entender la nueva categoría."

        tipo_cat = "ingresos" if transaccion["tipo"] == "ingreso" else "gastos"
        categorias = database.obtener_categorias(usuario["id"], tipo_cat)

        cat_encontrada = None
        for c in categorias:
            if c["nombre"].lower() == nueva_cat_nombre.lower():
                cat_encontrada = c
                break

        if not cat_encontrada:
            cat_info = database.crear_categoria(usuario["id"], nueva_cat_nombre, tipo_cat)
            cat_encontrada = cat_info

        actualizada = database.actualizar_transaccion(
            usuario["id"], tid, categoria_id=cat_encontrada["id"]
        )
        if actualizada:
            return (
                f"✅ **Categoría cambiada:**\n"
                f"De '{transaccion.get('categoria_nombre', 'Sin categoría')}' → **'{nueva_cat_nombre}'**"
            )
        return "❌ No pude cambiar la categoría. Intenta de nuevo."

    # --- CAMBIAR FECHA ---
    if accion == "cambiar_fecha":
        nueva_fecha = mod["valor_nuevo"]
        if not nueva_fecha:
            return "❌ No pude entender la nueva fecha."

        actualizada = database.actualizar_transaccion(
            usuario["id"], tid, fecha=nueva_fecha
        )
        if actualizada:
            fecha_ant = transaccion.get("fecha", "N/A")[:10]
            return (
                f"✅ **Fecha actualizada:**\n"
                f"De {fecha_ant} → **{nueva_fecha}**"
            )
        return "❌ No pude actualizar la fecha. Intenta de nuevo."

    return "❌ Ocurrió un error al procesar la modificación. Intenta de nuevo."


# ============================================================
# RESPUESTAS CONTEXTUALES CUANDO NO ENTIENDE
# ============================================================

_ACCIONES_FINANCIERAS = [
    "gasté", "gaste", "compré", "compre", "pagué", "pague", "costó", "costo",
    "recibí", "recibi", "cobré", "cobro", "gané", "gane", "ingresé", "ingrese",
    "invertí", "inverti", "ahorré", "ahorre", "pagué", "pague",
    "compramos", "gastamos", "cobramos", "ganamos", "recibimos",
]

_CONSULTAS = [
    "cuánto", "cuanto", "cuántos", "cuantos", "cuál", "cual", "cuáles", "cuales",
    "balance", "saldo", "cuenta", "tengo", "dónde", "donde", "qué tengo",
    "mostrar", "ver", "listar", "resumen", "consulta", "consultar",
]

_CONFIGURACION = [
    "presupuesto", "meta", "ahorro", "ahorrar", "inversión", "inversion",
    "objetivo", "plan", "categoría", "categoria", "configurar", "establecer",
    "definir", "fijar", "asignar",
]

_MODIFICACION = [
    "cambiar", "modificar", "editar", "actualizar", "corregir", "mover",
    "convertir", "eliminar", "borrar", "quitar", "suprimir",
]


def _responder_ayuda_uso(mensaje: str) -> str:
    """Responde con ayuda contextual según lo que el usuario pregunte."""
    m = mensaje.lower()
    nombre = "amigo"

    # Detectar INTENCIÓN de la pregunta (cualquier forma)
    # 1. Registrar gasto
    if any(w in m for w in ["gasto", "gastar", "gasté", "gaste", "compra", "comprar",
                            "compré", "compre", "pago", "pagar", "pagué", "pague"]):
        return "\n".join([
            f"{formato.EMOJI_GASTO} **Cómo registrar un gasto:**",
            "",
            "Escribe un mensaje con tu gasto en lenguaje natural:",
            "",
            "• `Gasté $50 en comida`",
            "• `Compré $30 de ropa`",
            "• `Pagué $100 de luz`",
            "• `$20 en transporte`",
            "• `Gasto $75 en supermercado`",
            "",
            "El bot detecta automáticamente la categoría y el monto.",
            "También puedes registrar varios gastos juntos:",
            "• `$50 en comida y $30 en transporte`",
        ])

    # 2. Registrar ingreso
    if any(w in m for w in ["ingreso", "ingresar", "ingresé", "ingrese",
                            "salario", "cobrar", "cobré", "cobro", "ganar",
                            "gané", "gane", "agrega", "agregar"]):
        return "\n".join([
            "📈 **Cómo registrar un ingreso:**",
            "",
            "Escribe un mensaje con tu ingreso:",
            "",
            "• `Recibí $2000 de salario`",
            "• `Ingresé $500 de trading`",
            "• `Cobré $300 de freelance`",
            "• `Agrega $100 de dividendos`",
            "• `Gané $150 de ventas`",
            "",
            "El bot lo clasifica como ingreso automáticamente.",
        ])

    # 3. Ver balance / saldo
    if any(w in m for w in ["balance", "saldo", "cuánto tengo", "cuanto tengo",
                            "ver dinero", "mi plata", "mi dinero", "mis finanzas"]):
        return "\n".join([
            f"{formato.EMOJI_BALANCE} **Cómo ver tu balance:**",
            "",
            "• `¿Cuánto tengo?` — Balance general",
            "• `¿Cuál es mi saldo?` — Ver saldo actual",
            "• `Ver balance` — Resumen de finanzas",
            "",
            "Te mostrará tus ingresos totales, gastos totales y saldo neto.",
        ])

    # 4. Ver transacciones / historial
    if any(w in m for w in ["transacción", "transaccion", "transacciones", "historial",
                            "movimiento", "movimientos", "ver mis", "listar",
                            "mostrar", "qué hice", "que hice", "últimas"]):
        return "\n".join([
            "📋 **Cómo ver tu historial:**",
            "",
            "• `¿Qué gasté hoy?` — Transacciones de hoy",
            "• `¿Qué hice ayer?` — Transacciones de ayer",
            "• `Ver transacciones` — Últimas transacciones",
            "• `Historial de esta semana` — Resumen semanal",
            "",
            "También puedes filtrar por categoría o fecha.",
        ])

    # 5. Ver gastos por categoría
    if any(w in m for w in ["categoría", "categoria", "categorías", "categorias",
                            "qué categoría", "que categoria"]):
        return "\n".join([
            "🏷️ **Cómo ver categorías:**",
            "",
            "• `¿Cuánto gasté en comida?` — Gastos en comida",
            "• `¿Cuánto gasté en transporte?` — Gastos en transporte",
            "• `¿Qué categorías tengo?` — Ver todas las categorías",
            "",
            "Las categorías se crean automáticamente al registrar transacciones.",
        ])

    # 6. Notificaciones / resumen diario
    if any(w in m for w in ["notificacion", "notificaciones", "resumen diario", "alerta",
                            "alerta de presupuesto", "recordatorio", "hora del resumen", "aviso"]):
        return "\n".join([
            "🔔 **Notificaciones:**",
            "",
            "• **Resumen diario:** todos los días a las **21:30 (hora de Cuba)** recibes "
            "un resumen con tus movimientos de hoy y tu balance.",
            "• **Alertas de presupuesto:** te avisamos al instante cuando un presupuesto "
            "llega al **80%**, se **agota (100%)** o lo **superas (125%)**.",
            "• **Actívalo o desactívalo todo desde:** `/notificaciones`",
            "",
            "Las alertas de presupuesto se envían automáticamente en cada gasto; "
            "el resumen diario solo si lo tienes activado.",
        ])

    # 7. Presupuesto
    if any(w in m for w in ["presupuesto", "budget", "planea", "planifica",
                            "límite", "limite", "tope"]):
        return "\n".join([
            "📊 **Cómo configurar un presupuesto:**",
            "",
            "• `Mi presupuesto para comida es $500 este mes`",
            "• `Presupuesto de transporte $200`",
            "• `Límite de gasto $1000 por mes`",
            "",
            "El bot te avisará cuando estés cerca del límite.",
        ])

    # 8. Ahorro / metas
    if any(w in m for w in ["ahorrar", "ahorro", "meta", "objetivo",
                            "vacaciones", "viaje", "emergencia"]):
        return "\n".join([
            "🎯 **Cómo configurar una meta de ahorro:**",
            "",
            "• `Quiero ahorrar $5000 para vacaciones`",
            "• `Meta de ahorro $3000 para emergencias`",
            "• `Objetivo: ahorrar $10000 este año`",
            "",
            "El bot te mostrará cuánto has ahorrado hacia tu meta.",
        ])

    # 9. Modificar transacción
    if any(w in m for w in ["modificar", "cambiar", "editar", "corregir",
                            "actualizar", "cambio"]):
        return "\n".join([
            "✏️ **Cómo modificar una transacción:**",
            "",
            "• `Cambiar mi último gasto a $75`",
            "• `Modifica la descripción de mi último gasto`",
            "• `Cambia el monto de $100 a $150`",
            "• `Pasa ese gasto a la categoría transporte`",
            "",
            "Puedes modificar monto, descripción, categoría o fecha.",
        ])

    # 10. Eliminar transacción
    if any(w in m for w in ["eliminar", "borrar", "quitar", "suprimir",
                            "delet", "remover"]):
        return "\n".join([
            "🗑️ **Cómo eliminar transacciones:**",
            "",
            "• `Eliminar mi último gasto`",
            "• `Borrar la transacción de $50`",
            "• `Quitar el gasto de comida`",
            "• `/delete` — Borrar todo el historial",
            "",
            "⚠️ Cuidado: eliminar todo el historial es irreversible.",
        ])

    # 11. Comandos generales del bot
    if any(w in m for w in ["comando", "comandos", "qué puedo", "que puedo",
                            "funciones", "opciones", "menú", "menu",
                            "qué hace", "que hace", "para qué sirve",
                            "cómo funciona", "como funciona"]):
        return "\n".join([
            "🤖 **Qué puedo hacer:**",
            "",
            "📝 **Registrar:**",
            "• Gastos: `Gasté $50 en comida`",
            "• Ingresos: `Recibí $2000 de salario`",
            "• Varios: `$50 comida y $30 transporte`",
            "",
            "📊 **Consultar:**",
            "• Balance: `¿Cuánto tengo?`",
            "• Historial: `¿Qué gasté hoy?`",
            "• Categorías: `¿Cuánto en comida?`",
            "",
            "⚙️ **Configurar:**",
            "• Presupuesto: `Mi presupuesto es $500 para comida`",
            "• Metas: `Quiero ahorrar $5000 para vacaciones`",
            "",
            "✏️ **Modificar/Eliminar:**",
            "• Cambiar: `Cambiar mi último gasto a $75`",
            "• Eliminar: `Eliminar mi último gasto`",
            "",
            "📋 **Comandos:**",
            "• `/start` — Iniciar el bot",
            "• `/help` — Ver ayuda completa",
            "• `/user` — Tu información",
            "• `/notificaciones` — Alertas y resumen diario (21:30 hora de Cuba)",
            "• `/delete` — Borrar historial",
        ])

    # 12. Respuesta genérica para preguntas de uso no categorizadas
    return "\n".join([
        "🤖 **Cómo puedo ayudarte:**",
        "",
        "Pregúntame sobre cualquier funcionalidad:",
        "",
        "• ¿Cómo registro un gasto?",
        "• ¿Cómo veo mi balance?",
        "• ¿Cómo pongo un presupuesto?",
        "• ¿Cómo creo una meta de ahorro?",
        "• ¿Cómo modifico una transacción?",
        "• ¿Cómo elimino algo?",
        "• ¿Qué comandos tienes?",
        "",
        "O simplemente escribe tu gasto o ingreso directamente.",
    ])


def _generar_respuesta_no_entendido(mensaje: str, usuario: Dict[str, Any]) -> str:
    """
    Genera una respuesta contextual cuando el bot no entiende el mensaje.
    Analiza parcialmente la intención y guía al usuario con ejemplos específicos.
    """
    msg = mensaje.lower().strip()
    nombre = escape_markdown(usuario.get("nombre", "amigo") or "amigo", version=1)
    mensaje_esc = escape_markdown(mensaje, version=1)

    # Señal 1: Tiene número pero no se detectó transacción
    tiene_numero = bool(re.search(r'\d+', msg))
    # Señal 2: Tiene palabras de acción financiera
    tiene_accion = any(w in msg for w in _ACCIONES_FINANCIERAS)
    # Señal 3: Tiene palabras de consulta
    tiene_consulta = any(w in msg for w in _CONSULTAS)
    # Señal 4: Tiene palabras de configuración
    tiene_config = any(w in msg for w in _CONFIGURACION)
    # Señal 5: Tiene palabras de modificación
    tiene_mod = any(w in msg for w in _MODIFICACION)
    # Señal 6: Saludo
    es_saludo = any(w in msg for w in ["hola", "hi", "hey", "buenas", "buenos", "buen"])

    # --- CASOS ESPECÍFICOS ---

    if es_saludo and len(msg.split()) <= 3:
        return (
            f"¡Hola {nombre}! 👋 ¿En qué te puedo ayudar?\n\n"
            "Puedes:\n"
            f"• {formato.EMOJI_GASTO} Registrar un gasto: `Gasté $50 en comida`\n"
            f"• {formato.EMOJI_INGRESO} Registrar un ingreso: `Recibí $300 de salario`\n"
            f"• {formato.EMOJI_BALANCE} Ver tu balance: `¿Cuánto tengo?`\n"
            "• 📋 Ver transacciones: `¿Qué gasté hoy?`\n"
            f"• {formato.EMOJI_PRESUPUESTO} Configurar presupuesto: `Mi presupuesto es $500 para comida`"
        )

    if tiene_consulta and not tiene_accion:
        return (
            f"🤔 {nombre}, parece que quieres **consultar** algo sobre tus finanzas.\n\n"
            "¿Qué te gustaría saber?\n"
            "• `¿Cuánto tengo?` — Ver balance general\n"
            "• `¿Qué gasté hoy?` — Transacciones de hoy\n"
            "• `¿Qué hice ayer?` — Transacciones de ayer\n"
            "• `¿Cuánto gasté en julio?` — Análisis mensual\n"
            "• `¿Qué gasté esta semana?` — Resumen semanal\n"
            "• `¿Cuánto gasté en comida?` — Gastos por categoría\n"
            "• `¿Cuánto ingresé?` — Ver ingresos\n"
            "• `Del 1 al 10 de julio` — Rango de fechas\n"
            "• `¿Cómo va mi presupuesto?` — Ver presupuestos"
        )

    if tiene_config:
        return (
            f"🤔 {nombre}, veo que quieres **configurar** algo.\n\n"
            "¿Qué necesitas?\n"
            "• `Mi presupuesto para comida es $500 este mes`\n"
            "• `Quiero ahorrar $2000 para vacaciones`\n"
            "• `Crear categoría: Suscripciones`\n"
            "• `Mi meta de ahorro es $5000 para diciembre`"
        )

    if tiene_mod:
        return (
            f"✏️ {nombre}, parece que quieres **modificar** algo.\n\n"
            "¿Qué necesitas cambiar?\n"
            "• `Cambiar el monto de mi último gasto a $75`\n"
            "• `Eliminar mi último gasto`\n"
            "• `Cambiar la categoría de mi último ingreso a bonus`\n"
            "• `Editar mi último gasto: descripción a uber`"
        )

    if tiene_accion and tiene_numero:
        # Intentó registrar algo pero no se entendió
        return (
            f"💡 {nombre}, veo que mencionas un **monto** pero no pude procesar tu registro.\n\n"
            "¿Puedes intentar con este formato?\n"
            "• `Gasté $50 en comida` — Registrar un gasto\n"
            "• `Recibí $300 de salario` — Registrar un ingreso\n"
            "• `Pagué $20 de transporte` — Registrar un pago\n"
            "• `$100 en supermercado` — Formato corto\n\n"
            "También puedes incluir la fecha:\n"
            "• `Gasté $50 en comida ayer`\n"
            "• `Recibí $300 el lunes`"
        )

    if tiene_accion and not tiene_numero:
        return (
            f"💡 {nombre}, mencionas una **acción financiera** pero no veo un monto.\n\n"
            "Para registrar necesito el monto:\n"
            "• `Gasté $50 en comida`\n"
            "• `Recibí $300 de salario`\n"
            "• `$100 de uber`"
        )

    if tiene_numero and not tiene_accion:
        numero = re.search(r'\d+', msg).group()
        return (
            f"💡 {nombre}, veo un **monto** pero no sé qué hacer con él.\n\n"
            "¿Quieres registrarlo?\n"
            f"• `Gasté ${numero} en comida`\n"
            f"• `Recibí ${numero} de salario`\n\n"
            "¿O es parte de una consulta?\n"
            f"• `¿Cuánto gasté en ${numero}?`"
        )

    # --- RESPUESTA GENÉRICA (rediseño 4.8) ---
    return (
        f"🤔 No identifiqué qué necesitas con: _{mensaje_esc}_\n\n"
        "**Prueba con:**\n"
        f"{formato.EMOJI_GASTO} `Gasté $50 en comida`\n"
        f"{formato.EMOJI_BALANCE} `¿Cuánto tengo?`\n"
        f"{formato.EMOJI_META} `Quiero ahorrar $2000`\n\n"
        "O escribe /help para ver todo lo que puedo hacer."
    )


def _procesar_eliminar_presupuesto(usuario: Dict[str, Any], nombre: str) -> str:
    """Elimina un presupuesto por su nombre (o categoría)."""
    try:
        nombre = nombre.strip()
        if not nombre:
            return "❌ Dime el nombre del presupuesto a eliminar."

        # Resolver la categoría si el nombre coincide con una existente
        categoria_id = None
        for cat in database.obtener_categorias(usuario["id"], "gastos"):
            if cat["nombre"].strip().lower() == nombre.lower():
                categoria_id = cat["id"]
                break

        borrados = database.eliminar_presupuesto(usuario["id"], nombre=nombre, categoria_id=categoria_id)
        if borrados:
            return f"{formato.EMOJI_ELIMINAR} **Presupuesto eliminado:** {nombre}"
        return (
            f"❌ No encontré un presupuesto llamado {nombre}.\n"
            "Verifica su nombre con `Ver presupuestos`."
        )
    except Exception as e:
        logger.error("Error eliminando presupuesto: %s", e)
        return "❌ Ocurrió un error al eliminar el presupuesto."


def _procesar_eliminar_transaccion(mensaje: str, usuario: Dict[str, Any]) -> str:
    """Procesa una solicitud de eliminación de transacción."""
    mod = _detectar_modificacion(mensaje)
    referencia = mod.get("referencia")

    transaccion = _buscar_transaccion(usuario, referencia)

    if not transaccion:
        return "❌ No encontré la transacción que quieres eliminar. ¿Puedes especificar cuál?"

    tid = transaccion["id"]
    confirmado = database.eliminar_transaccion(usuario["id"], tid)

    if confirmado:
        tipo_icono = formato.EMOJI_GASTO if transaccion["tipo"] == "gasto" else formato.EMOJI_INGRESO
        tipo_label = "Gasto" if transaccion["tipo"] == "gasto" else "Ingreso"
        desc = _limpiar_descripcion(transaccion.get("descripcion", "Sin descripción"))
        return (
            f"{formato.EMOJI_ELIMINAR} **Transacción eliminada:**\n"
            f"{tipo_icono} {formato.fmt_moneda(transaccion['cantidad'])} - {tipo_label}: {desc}"
        )
    return f"{formato.EMOJI_ERROR} No pude eliminar la transacción.\nIntenta de nuevo o escribe /help."


# ============================================================
# ANÁLISIS DE TRANSACCIONES POR FECHA
# ============================================================

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _parsear_fecha_natural(mensaje: str):
    """
    Parsea referencias de fecha en lenguaje natural.
    Retorna (fecha_inicio, fecha_fin, etiqueta) o None.
    Las fechas son strings 'YYYY-MM-DD'.
    """
    from datetime import date, timedelta

    msg = mensaje.lower().strip()
    hoy = date.today()

    # --- Días relativos ---
    if re.search(r'\bhoy\b', msg):
        f = hoy.isoformat()
        return f, f, "hoy"

    if re.search(r'\bayer\b', msg):
        f = (hoy - timedelta(days=1)).isoformat()
        return f, f, "ayer"

    if re.search(r'\banteayer\b', msg):
        f = (hoy - timedelta(days=2)).isoformat()
        return f, f, "anteayer"

    # "el lunes", "el martes", etc.
    dias_semana = {
        "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
        "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6,
    }
    for dia_nombre, dia_num in dias_semana.items():
        match = re.search(r'\b(el\s+)?' + dia_nombre + r'\b', msg)
        if match:
            dias_atras = (hoy.weekday() - dia_num) % 7
            if dias_atras == 0:
                dias_atras = 7
            fecha = hoy - timedelta(days=dias_atras)
            f = fecha.isoformat()
            return f, f, f"el {dia_nombre}"

    # --- Semanas ---
    if re.search(r'\besta\s+semana\b', msg):
        inicio = hoy - timedelta(days=hoy.weekday())
        return inicio.isoformat(), hoy.isoformat(), "esta semana"

    if re.search(r'\bsemana\s+pasada\b', msg):
        fin = hoy - timedelta(days=hoy.weekday() + 1)
        inicio = fin - timedelta(days=6)
        return inicio.isoformat(), fin.isoformat(), "la semana pasada"

    # --- Meses ---
    if re.search(r'\beste\s+mes\b', msg):
        inicio = hoy.replace(day=1)
        return inicio.isoformat(), hoy.isoformat(), "este mes"

    if re.search(r'\bmes\s+pasado\b', msg):
        primeroeste = hoy.replace(day=1)
        fin = primeroeste - timedelta(days=1)
        inicio = fin.replace(day=1)
        return inicio.isoformat(), fin.isoformat(), "el mes pasado"

    # --- Rangos (PRIMERO que días específicos) ---
    # "del 1 al 10 de julio"
    match = re.search(r'del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+(\w+)', msg)
    if match:
        dia_inicio = int(match.group(1))
        dia_fin = int(match.group(2))
        mes_nombre = match.group(3)
        mes_num = MESES_ES.get(mes_nombre)
        if mes_num:
            anio = hoy.year
            try:
                inicio = date(anio, mes_num, dia_inicio)
                fin = date(anio, mes_num, dia_fin)
                return inicio.isoformat(), fin.isoformat(), f"del {dia_inicio} al {dia_fin} de {mes_nombre}"
            except ValueError:
                pass

    # --- Días específicos ---
    # "el 15 de julio", "15 de julio 2026"
    match = re.search(
        r'(?:el\s+)?(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(?:\s+(\d{4}))?',
        msg
    )
    if match:
        dia = int(match.group(1))
        mes_num = MESES_ES[match.group(2)]
        anio = int(match.group(3)) if match.group(3) else hoy.year
        try:
            fecha = date(anio, mes_num, dia)
            f = fecha.isoformat()
            return f, f, f"{dia} de {match.group(2)} {anio}"
        except ValueError:
            pass

    # "15/07/2026" o "15-07-2026" o "15/07"
    match = re.search(r'(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?', msg)
    if match:
        dia = int(match.group(1))
        mes = int(match.group(2))
        anio = int(match.group(3)) if match.group(3) else hoy.year
        if anio < 100:
            anio += 2000
        try:
            fecha = date(anio, mes, dia)
            f = fecha.isoformat()
            return f, f, f"{dia}/{mes:02d}/{anio}"
        except ValueError:
            pass

    # --- Mes genérico (DESPUÉS de todo lo anterior) ---
    # "en julio", "de julio", "julio 2026", "mes de julio"
    for mes_nombre, mes_num in MESES_ES.items():
        match = re.search(r'(?:en|de|mes\s+de\s+|el\s+mes\s+de\s+)' + mes_nombre + r'(?:\s+(\d{4}))?', msg)
        if match:
            anio = int(match.group(1)) if match.group(1) else hoy.year
            inicio = date(anio, mes_num, 1)
            if mes_num == 12:
                fin = date(anio + 1, 1, 1) - timedelta(days=1)
            else:
                fin = date(anio, mes_num + 1, 1) - timedelta(days=1)
            if inicio > hoy:
                inicio = hoy
            if fin > hoy:
                fin = hoy
            return inicio.isoformat(), fin.isoformat(), f"{mes_nombre} {anio}"

    # Solo nombre de mes: "julio", "junio"
    for mes_nombre, mes_num in MESES_ES.items():
        if re.search(r'\b' + mes_nombre + r'\b', msg):
            anio = hoy.year
            inicio = date(anio, mes_num, 1)
            if mes_num == 12:
                fin = date(anio + 1, 1, 1) - timedelta(days=1)
            else:
                fin = date(anio, mes_num + 1, 1) - timedelta(days=1)
            if inicio > hoy:
                inicio = hoy
            if fin > hoy:
                fin = hoy
            return inicio.isoformat(), fin.isoformat(), mes_nombre

    # --- Rangos adicionales ---

    # "últimos N días"
    match = re.search(r'(?:últimos?|ultimos?)\s+(\d+)\s+días?', msg)
    if match:
        dias = int(match.group(1))
        inicio = hoy - timedelta(days=dias)
        return inicio.isoformat(), hoy.isoformat(), f"últimos {dias} días"

    # "desde el lunes"
    for dia_nombre, dia_num in dias_semana.items():
        match = re.search(r'desde\s+(?:el\s+)?' + dia_nombre, msg)
        if match:
            dias_atras = (hoy.weekday() - dia_num) % 7
            fecha = hoy - timedelta(days=dias_atras)
            return fecha.isoformat(), hoy.isoformat(), f"desde el {dia_nombre}"

    return None


def _analizar_transacciones_por_fecha(usuario: Dict[str, Any], mensaje: str) -> str:
    """
    Analiza y formatea las transacciones de un usuario para un rango de fecha dado.
    Retorna un string con el desglose formateado, o None si no detecta fecha.
    """
    resultado = _parsear_fecha_natural(mensaje)
    if not resultado:
        return None

    fecha_inicio, fecha_fin, etiqueta = resultado

    transacciones = database.obtener_transacciones_por_fecha(
        usuario["id"], fecha_inicio, fecha_fin
    )

    if not transacciones:
        return (
            f"📅 **{etiqueta.capitalize()}:**\n\n"
            f"No tienes transacciones registradas para {etiqueta}.\n\n"
            "¿Quieres registrar algo? Por ejemplo:\n"
            "• `Gasté $50 en comida`\n"
            "• `Recibí $300 de salario`"
        )

    gastos = [t for t in transacciones if t["tipo"] == "gasto"]
    ingresos = [t for t in transacciones if t["tipo"] == "ingreso"]

    total_gastos = sum(t["cantidad"] for t in gastos)
    total_ingresos = sum(t["cantidad"] for t in ingresos)
    neto = total_ingresos - total_gastos

    lookup = _moneda_lookup_usuario(usuario)
    tiene_moneda = any(t.get("moneda_id") for t in transacciones)

    def _totales_por_moneda(trans):
        tot = {}
        for t in trans:
            mid = t.get("moneda_id")
            tot[mid] = tot.get(mid, 0.0) + t["cantidad"]
        return tot

    tot_gastos_m = _totales_por_moneda(gastos)
    tot_ingresos_m = _totales_por_moneda(ingresos)

    # Desglose por categoría
    por_categoria = {}
    for t in gastos:
        cat = t.get("categoria_nombre", "otros") or "otros"
        if cat not in por_categoria:
            por_categoria[cat] = {"total": 0, "cantidad": 0, "transacciones": []}
        por_categoria[cat]["total"] += t["cantidad"]
        por_categoria[cat]["cantidad"] += 1
        por_categoria[cat]["transacciones"].append(t)

    lineas = [f"📅 **Análisis: {etiqueta}**", formato.SEPARADOR]

    # Resumen general
    lineas.append("")
    if tiene_moneda:
        lineas.append(f"{formato.EMOJI_INGRESO} **Ingresos ({len(ingresos)} transacciones):**")
        if tot_ingresos_m:
            for mid, tot in sorted(tot_ingresos_m.items(), key=lambda x: -x[1]):
                lineas.append(f"   {_formatear_monto(lookup, mid, tot)}")
        else:
            lineas.append("   Sin ingresos")
        lineas.append(f"{formato.EMOJI_GASTO} **Gastos ({len(gastos)} transacciones):**")
        if tot_gastos_m:
            for mid, tot in sorted(tot_gastos_m.items(), key=lambda x: -x[1]):
                lineas.append(f"   {_formatear_monto(lookup, mid, tot)}")
        else:
            lineas.append("   Sin gastos")
    else:
        lineas.append(f"{formato.EMOJI_INGRESO} **Ingresos:** {formato.fmt_moneda(total_ingresos)} ({len(ingresos)} transacciones)")
        lineas.append(f"{formato.EMOJI_GASTO} **Gastos:** {formato.fmt_moneda(total_gastos)} ({len(gastos)} transacciones)")
    if not tiene_moneda or (len(tot_gastos_m) <= 1 and len(tot_ingresos_m) <= 1):
        lineas.append(f"Neto: **{formato.fmt_moneda(neto, signo=True)}**")
    lineas.append(f"{formato.EMOJI_INFO} {len(transacciones)} transacciones")

    # Desglose de gastos por categoría
    if por_categoria:
        lineas.append("")
        lineas.append("**Gastos por categoría**")
        for cat, datos in sorted(por_categoria.items(), key=lambda x: x[1]["total"], reverse=True):
            porcentaje = (datos["total"] / total_gastos * 100) if total_gastos > 0 else 0
            barra = formato.barra_progreso(porcentaje)
            lineas.append(f"• {cat}: {formato.fmt_moneda(datos['total'])} ({datos['cantidad']}x) {barra} {porcentaje:.0f}%")

    # Mayor gasto del período
    if gastos:
        mayor = max(gastos, key=lambda t: t["cantidad"])
        lineas.append("")
        lineas.append(
            f"{formato.EMOJI_GASTO} **Mayor gasto:** {_formatear_monto(lookup, mayor.get('moneda_id'), mayor['cantidad'])} - "
            f"{mayor.get('descripcion') or 'Sin descripción'} ({mayor.get('categoria_nombre') or 'otros'})"
        )

    # Detalle de gastos
    if gastos:
        lineas.append("")
        lineas.append("**Detalle de gastos**")
        for t in gastos:
            fecha = str(t.get("fecha", ""))[:10]
            desc = t.get("descripcion", "Sin descripción")
            cat = t.get("categoria_nombre", "")
            cat_str = f" ({cat})" if cat else ""
            lineas.append(f"{formato.EMOJI_GASTO} {_formatear_monto(lookup, t.get('moneda_id'), t['cantidad'])} - {desc}{cat_str} [{fecha}]")

    # Detalle de ingresos
    if ingresos:
        lineas.append("")
        lineas.append("**Detalle de ingresos**")
        for t in ingresos:
            fecha = str(t.get("fecha", ""))[:10]
            desc = t.get("descripcion", "Sin descripción")
            cat = t.get("categoria_nombre", "")
            cat_str = f" ({cat})" if cat else ""
            lineas.append(f"{formato.EMOJI_INGRESO} {_formatear_monto(lookup, t.get('moneda_id'), t['cantidad'])} - {desc}{cat_str} [{fecha}]")

    # Promedio diario si es rango de varios días
    try:
        from datetime import date as _date
        d_inicio = _date.fromisoformat(fecha_inicio)
        d_fin = _date.fromisoformat(fecha_fin)
        dias = (d_fin - d_inicio).days + 1
        if dias > 1:
            lineas.append("")
            lineas.append(f"📊 **Promedio diario ({dias} días)**")
            lineas.append(f"{formato.EMOJI_GASTO} Gasto promedio: {formato.fmt_moneda(total_gastos / dias)}/día")
            lineas.append(f"{formato.EMOJI_INGRESO} Ingreso promedio: {formato.fmt_moneda(total_ingresos / dias)}/día")
    except Exception:
        pass

    return "\n".join(lineas)


def _crear_barra_progreso(porcentaje: float, largo: int = 10) -> str:
    """Crea una barra de progreso visual (delega en formato.barra_progreso)."""
    return formato.barra_progreso(porcentaje, largo)