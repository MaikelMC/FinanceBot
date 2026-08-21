"""
validators.py - Validaciones robustas de entradas de usuario.

Funciones reutilizables para montos, descripciones y fechas:
- Montos: numéricos y positivos; acepta "50", "50.50", "50,50", "$50", "50 USD";
  rechaza "-50", "abc", "0" (usa knowledge._parsear_cantidad como base).
- Descripciones: no vacías, máximo DESCRIPCION_MAX caracteres (se trunca).
- Fechas: reales (strptime rechaza "2024-13-01", "2024-02-30") y, para
  transacciones, no futuras (las metas de ahorro sí permiten futuras).

Todas retornan una tupla (valor_valido, mensaje_error): exactamente uno es None.
"""

import math
import re
from datetime import datetime, date, timezone
from typing import Optional, Tuple, Union

# ============================================================
# MENSAJES DE ERROR
# ============================================================

MSG_MONTO_INVALIDO = "❌ Monto inválido. Usa un formato como: $50 o 100.50"
MSG_DESCRIPCION_VACIA = "❌ La descripción no puede estar vacía."
MSG_FECHA_INVALIDA = '❌ Fecha inválida: "{fecha}". Usa el formato AAAA-MM-DD (ej: 2026-08-19).'
MSG_FECHA_FUTURA = "❌ La fecha no puede ser futura."

DESCRIPCION_MAX = 200

FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")

# Signo negativo: guion/es seguido de dígito, NO precedido de otro dígito
# (así "2026-08-19" no se marca como negativo, pero "-50" y "$-50" sí).
_NEGATIVO_RE = re.compile(r"(?<!\d)-+\s*\d")


# ============================================================
# MONTOS
# ============================================================

def validar_monto_valor(cantidad: Union[float, int, str, None]) -> Tuple[Optional[float], Optional[str]]:
    """Valida un monto ya numérico o parseable simple (ej: del JSON de la IA).

    Debe ser finito y estrictamente positivo. Retorna (monto, None) o
    (None, MSG_MONTO_INVALIDO).
    """
    if isinstance(cantidad, str):
        # Rechazar negativos explícitos ANTES de parsear ("-50" se parsearía como 50)
        if _NEGATIVO_RE.search(cantidad):
            return None, MSG_MONTO_INVALIDO
        from knowledge import _parsear_cantidad
        cantidad = _parsear_cantidad(cantidad)
    try:
        monto = float(cantidad)
    except (TypeError, ValueError):
        return None, MSG_MONTO_INVALIDO
    if not math.isfinite(monto) or monto <= 0:
        return None, MSG_MONTO_INVALIDO
    return monto, None


def validar_monto(texto: Union[str, None]) -> Tuple[Optional[float], Optional[str]]:
    """Parsea y valida un monto escrito por el usuario.

    Base: knowledge._parsear_cantidad + validación de signo positivo.
    Retorna (monto, None) o (None, MSG_MONTO_INVALIDO).
    """
    texto_limpio = str(texto or "").strip()
    if not texto_limpio:
        return None, MSG_MONTO_INVALIDO
    # Rechazar negativos explícitos ANTES de parsear ("-50" se parsearía como 50)
    if _NEGATIVO_RE.search(texto_limpio):
        return None, MSG_MONTO_INVALIDO
    from knowledge import _parsear_cantidad  # lazy: evita importación circular
    monto = _parsear_cantidad(texto_limpio)
    return validar_monto_valor(monto)


# ============================================================
# DESCRIPCIONES
# ============================================================

def validar_descripcion(descripcion: Union[str, None], max_len: int = DESCRIPCION_MAX) -> Tuple[Optional[str], Optional[str]]:
    """Valida una descripción: sin vacíos/solo espacios y limitada a max_len.

    Si excede max_len se TRUNCA (no se rechaza). Retorna (texto, None) o
    (None, MSG_DESCRIPCION_VACIA).
    """
    texto = str(descripcion or "").strip()
    if not texto:
        return None, MSG_DESCRIPCION_VACIA
    if len(texto) > max_len:
        texto = texto[:max_len].rstrip()
    return texto, None


# ============================================================
# FECHAS
# ============================================================

def validar_fecha(fecha_str: Union[str, None], permitir_futura: bool = False,
                  formatos: Tuple[str, ...] = FORMATOS_FECHA) -> Tuple[Optional[date], Optional[str]]:
    """Valida que sea una fecha REAL con datetime.strptime.

    - "2024-13-01" (mes 13) y "2024-02-30" (día inexistente) se rechazan.
    - Transacciones: no se permiten fechas futuras (permitir_futura=False).
    - Metas de ahorro: pasar permitir_futura=True.
    Formatos aceptados: AAAA-MM-DD, DD/MM/AAAA, DD-MM-AAAA.
    """
    fecha_str = str(fecha_str or "").strip()
    fecha = None
    for fmt in formatos:
        try:
            fecha = datetime.strptime(fecha_str, fmt).date()
            break
        except ValueError:
            continue
    if fecha is None:
        return None, MSG_FECHA_INVALIDA.format(fecha=fecha_str[:30])
    if not permitir_futura and fecha > datetime.now(timezone.utc).date():
        return None, MSG_FECHA_FUTURA
    return fecha, None
