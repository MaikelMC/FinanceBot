# Rediseño de mensajes — FinanzasBot

Sistema de diseño para los mensajes del bot. No es "cambiar emojis", es fijar reglas
que apliques en `knowledge.py`, `handlers.py` y `changelog.py` para que **todos** los
mensajes salgan consistentes, sin que dependa de quién escribió esa función.

---

## 0. Diagnóstico del catálogo actual

Problemas concretos en `MENSAJES.md`:

1. **Emoji sin función semántica.** `💰`, `💵`, `💸`, `📊` se usan indistintamente para
   lo mismo (dinero) según qué función lo escribió. Un usuario no puede aprender "qué
   significa cada emoji" porque no significa nada fijo.
2. **Negrita inconsistente en densidad.** Algunos mensajes negritean todo (`**Presupuesto 'comida'**`),
   otros no negritean nada. Eso hace que la negrita deje de comunicar jerarquía.
3. **Sin separador de miles.** `$5000.00` en vez de `$5,000.00`. En cifras de 4+ dígitos
   se vuelve difícil de leer de un vistazo — esto es lo primero que delata una salida "cruda".
4. **Separador `━━━━━━━━━━━━━━━━━` de 17 caracteres.** En pantalla de móvil (6-8 líneas visibles)
   ocupa una línea completa y no aporta información, solo ruido visual.
5. **Estructura no predecible.** Cada tipo de mensaje (balance, presupuesto, resumen) tiene
   su propio orden de secciones. El usuario no desarrolla un modelo mental de "dónde está el dato X".
6. **Tono inconsistente.** Mensajes de error van de `⚠️ Ocurrió un error` (seco) a
   `😔 Disculpa Ana, el servicio de IA no está disponible ahora` (informal). No hay un registro fijo.
7. **Bullets duplicando el emoji del título.** `📈 **Ingresos**` seguido de líneas con `📈` de nuevo
   por cada ítem — repetición sin aportar jerarquía.

---

## 1. Principios del nuevo sistema

1. **Un emoji = un significado, siempre.** Tabla fija en la sección 2. Si dos mensajes hablan
   de gasto, usan el mismo emoji — no hay variantes "de estilo".
2. **Jerarquía de 3 niveles, nunca más:** título (negrita + emoji) → separador corto → cuerpo.
   El cuerpo no vuelve a repetir el emoji del título en cada línea.
3. **Separador corto y fijo:** `┈┈┈┈┈┈┈┈┈┈` (10 caracteres) en vez de 17. Se usa solo cuando
   hay ≥2 secciones en el mismo mensaje; para respuestas de una sola sección, no hace falta.
4. **Números siempre con separador de miles y 2 decimales:** `$5,000.00`, nunca `$5000.00`.
5. **Negrita solo en datos accionables**: montos, nombres de categoría/presupuesto/moneda,
   porcentajes clave. Nunca en frases completas ni en conectores.
6. **Tono directo, sin relleno emocional.** Fuera `😔 Disculpa Ana`, `¡Cuidado!`, exclamaciones
   decorativas. El bot informa, no consuela.
7. **CTA (llamada a la acción) al final, en una sola línea, sin negrita.** No mezclada con datos.

---

## 2. Sistema de emojis semántico (tabla cerrada)

| Emoji | Significado único | Reemplaza a |
|---|---|---|
| 📈 | Ingreso | `💰` (cuando significaba ingreso) |
| 📉 | Gasto | `💸`, `💳` |
| 💰 | Balance / dinero general (solo en títulos de balance) | `💵` |
| 📊 | Presupuesto / estadística / resumen | — |
| 🎯 | Meta de ahorro | — |
| 💱 | Moneda | — |
| 🔔 | Notificación / alerta de sistema | — |
| ⚠️ | Advertencia (umbral, límite cerca) | `🚨`, `⛔` (unificar severidad con texto, no con más emojis) |
| ✅ | Confirmación de acción exitosa | — |
| ❌ | Error o cancelación | — |
| ℹ️ | Información neutra (sin acción) | — |
| 🗑️ | Eliminación | — |

**Regla de severidad sin multiplicar emojis:** para alertas de presupuesto (80/100/125%),
el emoji es siempre `⚠️`; la severidad se comunica con la palabra (`cerca del límite`,
`agotado`, `excedido`), no con `🚨`/`⛔` distintos. Esto es más elegante y más fácil de mantener.

**Categorías de gasto:** mantén el mapa de emojis por categoría (🍔 comida, 🚕 transporte, etc.)
— eso sí aporta información real y no lo toques.

---

## 3. Componentes reutilizables

Piensa los mensajes como composición de 4 bloques. Te doy el helper en Python para
implementarlo una sola vez y usarlo en todo `knowledge.py`.

```python
# formato.py — helpers de presentación, usar en knowledge.py y handlers.py

SEPARADOR = "┈┈┈┈┈┈┈┈┈┈"

def fmt_monto(valor: float) -> str:
    """5000.0 -> '5,000.00'"""
    return f"{valor:,.2f}"

def fmt_moneda(valor: float, abrev: str | None = None, signo: bool = False) -> str:
    """1650.0, 'USD' -> '$1,650.00 (USD)'"""
    prefijo = "+" if signo and valor >= 0 else ("-" if signo and valor < 0 else "")
    cuerpo = f"{prefijo}${fmt_monto(abs(valor)) if signo else fmt_monto(valor)}"
    return f"{cuerpo} ({abrev})" if abrev else cuerpo

def header(emoji: str, titulo: str) -> str:
    """Título de sección: un único emoji, mayúsculas solo si es encabezado de mensaje completo."""
    return f"{emoji} **{titulo}**"

def barra_progreso(pct: float, largo: int = 10) -> str:
    pct = max(0, min(100, pct))
    llenos = round((pct / 100) * largo)
    return "`" + "█" * llenos + "░" * (largo - llenos) + "`"

def bloque(titulo_con_emoji: str, lineas: list[str], separador: bool = True) -> str:
    partes = [titulo_con_emoji]
    if separador:
        partes.append(SEPARADOR)
    partes.extend(lineas)
    return "\n".join(partes)
```

Con esto, **cualquier** mensaje del bot se arma igual: `header()` + (`SEPARADOR` si hay
más de una sección) + líneas de datos + CTA opcional en texto plano al final.

---

## 4. Rediseño mensaje por mensaje

### 4.1 `/start` — Bienvenida

**Antes:**
```
¡Hola Ana! 👋 Soy **FinanzasBot**, tu asistente financiero personal.

📊 Tengo **12 transacciones** registradas:
  💸 Gastos: 8
  💰 Ingresos: 4

🏦 **Qué puedo ayudarte hoy:**
• Registrar un gasto o ingreso (ej: "Gasté $50 en comida para el desayuno")
...
```

**Después:**
```
👋 Hola Ana, soy **FinanzasBot**.

📊 **Actividad registrada**
┈┈┈┈┈┈┈┈┈┈
📉 8 gastos · 📈 4 ingresos · 12 en total

**Qué puedes hacer:**
• Registrar: `Gasté $50 en comida`
• Consultar: `¿Cuánto tengo?`
• Presupuestar: `Mi presupuesto para comida es $500`
• Metas: `Quiero ahorrar $5000 para vacaciones`

Usa /help para ver todos los comandos.
```
Cambios: se elimina `🏦` (no está en la tabla semántica), se comprime la lista de bullets
descriptivos a los 4 casos de uso reales con ejemplo ejecutable en `código`, y se corta el
"aquí puedes también..." largo por un cierre de una línea.

---

### 4.2 `/user` — Info de usuario (multi-moneda)

**Antes:**
```
👤 **Usuario:** Ana
🆔 **ID:** `123456789`

💰 **Balance:**
  💱 $ Dolar (USD): +$2000.00 / -$350.00 = $1650.00
  💱 $ Peso cubano (CUP): +$5000.00 / -$1200.00 = $3800.00
📁 **Categorías:** 8
💱 **Monedas:** 2
📝 **Transacciones recientes:** 12
```

**Después:**
```
👤 **Ana** · `ID 123456789`

💰 **Balance**
┈┈┈┈┈┈┈┈┈┈
USD  📈 $2,000.00  📉 $350.00  → **$1,650.00**
CUP  📈 $5,000.00  📉 $1,200.00  → **$3,800.00**

📁 8 categorías · 💱 2 monedas · 12 transacciones
```
Cambios: la línea de identidad se colapsa en una sola (nombre + ID en `código`, no dos negritas
separadas). El balance por moneda pasa a formato tabular alineado por abreviatura de moneda
en vez de repetir `💱 $ nombre (ABREV):` tres veces — se lee como tabla incluso sin tablas reales
de Markdown. Los metadatos (categorías/monedas/transacciones) se agrupan en una sola línea final
en vez de tres líneas con negrita cada una — son datos secundarios, no necesitan el mismo peso visual.

---

### 4.3 Balance (consulta natural, multi-moneda)

**Antes:**
```
💰 **TU BALANCE FINANCIERO ACTUAL**
━━━━━━━━━━━━━━━━━
**$ Dolar (USD)**
  📈 Ingresos: $2000.00
  📉 Gastos: $350.00
  💵 Neto: $1650.00

**$ Peso cubano (CUP)**
  📈 Ingresos: $5000.00
  📉 Gastos: $1200.00
  💵 Neto: $3800.00

¿Necesitas detalles sobre transacciones recientes o quieres configurar un presupuesto?
```

**Después:**
```
💰 **Balance actual**
┈┈┈┈┈┈┈┈┈┈
**USD**
📈 $2,000.00   📉 $350.00   💵 **$1,650.00**

**CUP**
📈 $5,000.00   📉 $1,200.00   💵 **$3,800.00**

¿Ver transacciones recientes o configurar un presupuesto?
```
Título en Title Case, no en mayúsculas sostenidas (las mayúsculas sostenidas leen como grito
en un chat). Cada moneda es un mini-bloque de una línea de datos, con el neto en negrita porque
es el único número accionable ahí.

---

### 4.4 Presupuestos (listado)

**Antes:**
```
📋 **TUS PRESUPUESTOS**
━━━━━━━━━━━━━━━━━
📌 **comida**
   Presupuesto: $500.00 (CUP)
   Gastado: $320.00 (CUP) (64%)
   Restante: $180.00 (CUP)
   ██████░░░░
   Periodo: mensual
```

**Después:**
```
📊 **Tus presupuestos**
┈┈┈┈┈┈┈┈┈┈
**Comida** · mensual
`██████░░░░` 64% — $320.00 de $500.00 (CUP)
Restante: **$180.00**
```
Se elimina la palabra "Presupuesto:" repetida como etiqueta (ya está en el título del bloque
`📊 Tus presupuestos`), se fusiona gastado+total en una sola línea con la barra, y el
periodo pasa a ir junto al nombre en vez de ser la última línea (dato de bajo valor, no
necesita su propia línea).

---

### 4.5 Alertas de presupuesto (umbral cruzado)

**Antes:**
```
⚠️ **Presupuesto 'comida'** al 80%: $400.00 (CUP) de $500.00 (CUP). ¡Cuidado!
🚨 **Presupuesto 'comida'** agotado: $500.00 (CUP) de $500.00 (CUP).
⛔ **Presupuesto 'comida'** excedido: $625.00 (CUP) de $500.00 (CUP) (125%).
```

**Después:**
```
⚠️ **Comida** cerca del límite: $400.00 de $500.00 (CUP) — 80%
⚠️ **Comida** agotado: $500.00 de $500.00 (CUP)
⚠️ **Comida** excedido: $625.00 de $500.00 (CUP) — 125%
```
Un solo emoji para las tres severidades (ver sección 2): la palabra ya distingue la gravedad,
y usar tres emojis distintos para "el mismo tipo de evento" es ruido, no información. Además
quita el `¡Cuidado!` (relleno emocional, sección 1.6) y el nombre de presupuesto deja de ir
entre comillas simples (`'comida'`) — la negrita ya lo distingue, las comillas son redundantes.

---

### 4.6 Resumen mensual

**Antes:**
```
📊 **RESUMEN DE AGOSTO**
━━━━━━━━━━━━━━━━━
💵 **MOVIMIENTOS DEL MES**
💰 Ingresos: $5000.00 (CUP) · $200.00 (USD)
💸 Gastos: $1200.00 (CUP)
💵 Neto: +$3800.00 (CUP) · +$200.00 (USD)

🔥 **MAYORES GASTOS**
💱 CUP: total $1200.00
🍔 Comida: $420.00 · 35%
   `███░░░░░░░` 35%
🚕 Transporte: $300.00 · 25%
   `██░░░░░░░░` 25%

📌 **Mayor gasto:** 🍔 Comida — $420.00 (CUP) (el 17)
📈 **Promedio diario de gasto**
   $38.71 (CUP)/día (17 días del mes)

💵 **BALANCE ACTUAL**
   +$3800.00 (CUP) · +$200.00 (USD)
```

**Después:**
```
📊 **Resumen de agosto**
┈┈┈┈┈┈┈┈┈┈
📈 $5,000.00 (CUP) · $200.00 (USD)
📉 $1,200.00 (CUP)
💵 Neto: **+$3,800.00 (CUP)** · **+$200.00 (USD)**

**Gastos por categoría (CUP)**
🍔 Comida       `███░░░░░░░` 35% — $420.00
🚕 Transporte   `██░░░░░░░░` 25% — $300.00

Mayor gasto: 🍔 Comida, $420.00 (CUP) el día 17
Promedio diario: $38.71 (CUP)

💰 Balance: **+$3,800.00 (CUP)** · **+$200.00 (USD)**
```
Título en mayúsculas sostenidas eliminado. Se quita el subtítulo redundante `💵 MOVIMIENTOS DEL MES`
(ya lo dice el título del mensaje). La tabla de categorías se alinea con espacios para que la
barra y el porcentaje queden en columna — en monospace (Markdown de Telegram usa fuente
proporcional fuera de `código`, así que **solo dentro de backticks se alinea de verdad**;
por eso la barra va en backticks y el nombre de categoría se rellena con espacios antes del backtick).

---

### 4.7 `/notificaciones` — Configuración

**Antes:**
```
🔔 **Configuración de notificaciones**
━━━━━━━━━━━━━━━━━
✅ Resumen diario: **Activado**
🕐 Hora del resumen: **21:30** (hora de Cuba)
━━━━━━━━━━━━━━━━━
⚙️ **Alertas de presupuesto:**
✅ 80% · ✅ 100% · ⬜ 125%

_El resumen diario llega todos los días a las 21:30 hora de Cuba. Las alertas avisan cuando un presupuesto cruza el umbral._
```

**Después:**
```
🔔 **Notificaciones**
┈┈┈┈┈┈┈┈┈┈
Resumen diario: **activado** — 21:30 (hora de Cuba)
Alertas de presupuesto: ✅ 80% · ✅ 100% · ⬜ 125%

_Las alertas avisan al cruzar cada umbral. El resumen llega una vez al día._
```
Dos separadores en el mismo mensaje se reducen a uno (regla 1.3: separador solo cuando hay
≥2 secciones — aquí realmente hay una sola sección de config, no dos). Se quita `🕐` y `⚙️`
(no están en la tabla semántica, no aportaban nada que el texto no dijera ya).

---

### 4.8 Fallback / "no entendido" (mensaje genérico)

**Antes:** (ver catálogo, sección 12 — el bloque de 20 líneas con 4 categorías y emojis repetidos)

**Después:**
```
🤔 No identifiqué qué necesitas con: _"tu mensaje"_

**Prueba con:**
📉 `Gasté $50 en comida`
📊 `¿Cuánto tengo?`
🎯 `Quiero ahorrar $2000`

O escribe /help para ver todo lo que puedo hacer.
```
Antes el fallback mostraba 4 categorías completas con 3 ejemplos cada una (12 líneas de
ejemplos) — es la peor experiencia posible cuando el usuario ya está confundido: más texto,
no menos. El rediseño da 3 ejemplos (uno por acción más común) y delega el resto a `/help`,
que es donde debe vivir el catálogo completo.

---

## 5. Reglas de redacción (aplican a todo mensaje nuevo que escribas)

1. Título: `{emoji} **{Título en minúsculas excepto inicial}**` — nunca `MAYÚSCULAS SOSTENIDAS`.
2. Si el mensaje tiene una sola sección de datos, **no** lleva `SEPARADOR`.
3. Los números siempre pasan por `fmt_moneda()` / `fmt_monto()` — nunca se concatenan a mano.
4. Nombres de presupuesto/categoría/moneda van en negrita, **sin comillas**.
5. Las preguntas de cierre (CTA) van solas, en texto plano, al final, sin emoji delante.
6. Mensajes de error: `❌ {qué falló}.` en una línea. Si hay una acción de recuperación,
   segunda línea sin negrita: `Intenta de nuevo o escribe /help.`
7. Nunca dos emojis distintos para el mismo concepto en el mismo mensaje (p. ej. `💰` y `💵`
   ambos como "dinero" en el mismo texto).

---

## 6. Checklist de migración

1. Crear `formato.py` con los helpers de la sección 3 (o añadirlos a `knowledge.py` si preferís
   no crear módulo nuevo).
2. Sustituir cada `f"${valor:.2f}"` por `fmt_moneda(...)` — buscar con
   `grep -rn '\.2f' knowledge.py handlers.py` para localizarlos todos.
3. Sustituir `"━━━━━━━━━━━━━━━━━"` por `formato.SEPARADOR`, y quitarlo donde el mensaje
   tenga una sola sección (regla 5.2).
4. Pasar el mapa de emojis de la sección 2 como constantes (`EMOJI_INGRESO = "📈"`, etc.)
   y reemplazar los literales sueltos — evita que vuelva a divergir con el tiempo.
5. Priorizar el rediseño en este orden de impacto: `/start`, balance, presupuestos,
   alertas de presupuesto, resumen mensual (son los mensajes de mayor frecuencia de uso).
6. Correr `test_parsing_bugs.py` después — los tests no validan formato de texto, pero
   confirman que no rompiste lógica al tocar las funciones de `knowledge.py`.
