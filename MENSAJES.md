# 📨 Mensajes de salida del bot — Catálogo

Referencia de **todos los mensajes de texto** que FinanzasBot envía al usuario, su estructura y cuándo aparecen.

> **Formato:** todos los mensajes se envían con `parse_mode="Markdown"` (Markdown v1 de Telegram): `**negrita**`, `*negrita*` (equivalente), `` `código` ``, `_cursiva_`. Los ejemplos muestran valores realistas (`$50.00`) en lugar de variables.
>
> **Diseño v2.12 (`REDISENO MENSAJES.md`):** emojis semánticos de tabla cerrada (📈 ingreso, 📉 gasto, 💰 balance, 📊 presupuesto/estadística, 🎯 meta, 💱 moneda, 🔔 notificación, ⚠️ advertencia, ✅ OK, ❌ error, ℹ️ info, 🗑️ eliminar), montos con separador de miles (`$1,500.00`), separador corto `┈┈┈┈┈┈┈┈┈┈` solo en mensajes multi-sección, títulos Title Case y nombres en negrita sin comillas.

---

## Índice

1. [Comandos](#1-comandos)
2. [Menús y botones](#2-menús-y-botones)
3. [Registro de transacciones](#3-registro-de-transacciones)
4. [Consultas](#4-consultas)
5. [Presupuestos](#5-presupuestos)
6. [Resumen mensual](#6-resumen-mensual)
7. [Notificaciones](#7-notificaciones)
8. [Exportación de datos](#8-exportación-de-datos)
9. [Modificar / eliminar transacciones](#9-modificar--eliminar-transacciones)
10. [Metas de ahorro](#10-metas-de-ahorro)
11. [Ayuda "cómo…"](#11-ayuda-cómo)
12. [Mensajes de "no entendido" y errores](#12-mensajes-de-no-entendido-y-errores)
13. [Menú de comandos de Telegram](#13-menú-de-comandos-de-telegram)
14. [Notas de estilo y erratas detectadas](#14-notas-de-estilo-y-erratas-detectadas)

---

## 1. Comandos

### `/start` — Bienvenida
Aparece al iniciar el bot. Quita el teclado persistente y muestra el **menú principal** con 7 botones inline: 💰 Balance, 📊 Presupuestos, 🎯 Ahorros, 💱 Monedas, 📋 Transacciones, ❓ Ayuda y ⚙️ Más opciones.

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

👇 Elige una opción abajo o escríbeme en lenguaje natural:
```
Con un aviso previo: `🧭 Te cambié el teclado: ahora navegas con botones.`

Error: `⚠️ Ocurrió un error. Intenta de nuevo con /start.`

### `/help` — Comandos disponibles

```
🤖 **Comandos disponibles:**

• `/start` - Iniciar/Reiniciar el bot
• `/user` - Ver información de usuario
• `/resumen` - Resumen del mes actual
• `/categorias` - Ver tus categorías financieras
• `/gastos` - Ver tus últimos gastos
• `/ingresos` - Ver tus últimos ingresos
• `/metas` - Ver tus metas de ahorro
• `/notificaciones` - Alertas de presupuesto y resumen diario (21:30 hora de Cuba)
• `/exportar` - Exporta tus datos a Excel/CSV (ej: `/exportar csv 2026-07`)
• `/help` - Ver esta ayuda
• `/delete` - Borrar todo el historial de transacciones

📝 **Ejemplos de lenguaje natural:**
• 'Gasté $50 en comida para el desayuno'
• 'Recibí $2000 de salario'
• 'Mi presupuesto para comida es $500 este mes'
• 'Quiero ahorrar $5000 para unas vacaciones'
• '¿Cuál es mi balance actual?'
• 'Exporta mis datos del mes'

✏️ **Modificar datos:**
• 'Cambia el gasto de $50 a ingreso'
• 'Modifica la descripción de mi último gasto'
• 'Cambia el monto de $100 a $150'
• 'Elimina la transacción de $30'
• 'Pasa ese gasto a la categoría transporte'
```

Error: `⚠️ Ocurrió un error al mostrar la ayuda.`

### `/user` — Información de usuario

```
👤 **Ana** · `ID 123456789`

💰 **Balance de agosto 2026**
┈┈┈┈┈┈┈┈┈┈
USD  📈 $2,000.00  📉 $350.00  → **$1,650.00**
CUP  📈 $5,000.00  📉 $1,200.00  → **$3,800.00**

📁 8 categorías · 💱 2 monedas · 12 transacciones
```

Con una sola moneda:

```
💰 **Balance de agosto 2026**
┈┈┈┈┈┈┈┈┈┈
📈 $2,000.00
📉 $350.00
Neto: **$1,650.00**
```

Error: `⚠️ Ocurrió un error al obtener tu información.`

### `/resumen`
Envía el **resumen mensual** (sección 6).

Errores:
- `⚠️ Ocurrió un error al generar tu resumen.`

### `/categorias`, `/gastos`, `/ingresos`, `/metas`
Envían las secciones de consulta correspondientes (sección 4 y 10). Errores:
- `⚠️ Ocurrió un error al obtener tus categorías.`
- `⚠️ Ocurrió un error al obtener tus gastos.`
- `⚠️ Ocurrió un error al obtener tus ingresos.`
- `⚠️ Ocurrió un error al obtener tus metas de ahorro.`

### `/notificaciones` — Menú de notificaciones
Botones inline: `🛑/✅ Resumen diario`, `80%`, `100%`, `125%`, `❌ Cerrar`.

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

- Al cerrar: `🔔 Configuración de notificaciones cerrada.`
- Error: `⚠️ Ocurrió un error al mostrar la configuración de notificaciones.`

### `/exportar` — Exportación (sección 8)
Sin argumentos → menú de formato:

```
📤 **¿En qué formato quieres exportar tus datos?**
```

Botones: `📊 Excel (.xlsx)`, `📄 CSV`, `❌ Cancelar`.

Con argumentos (ej. `/exportar csv 2026-07`): `📤 **Generando tu exportación...**`

### `/delete` — Borrar historial
Confirmación con botones `✅ Sí, borrar todo` / `❌ Cancelar`:

```
⚠️ **¿Estás seguro?**

Se eliminarán **TODAS** tus transacciones y tu balance quedará en $0.00.
Esta acción no se puede deshacer.
```

Confirmado: `🗑️ **Historial eliminado.** Se borraron **12** transacciones.` + salto + `Tu balance ahora está en $0.00.`

### `/anuncio` (solo admin)
- Sin permiso: `🚫 No tienes permiso para usar este comando.`
- Sin argumentos:
  ```
  Uso: `/anuncio Tu mensaje aquí`

  Ejemplo: `/anuncio Mañana hay mantenimiento de 10 a 10:30`
  ```
- Vista previa (botones `✅ Enviar` / `❌ Cancelar`):
  ```
  📢 **Vista previa del anuncio:**

  Mañana hay mantenimiento de 10 a 10:30

  👥 Enviado a: **3** usuarios
  ```
- A cada usuario: `📢 **Anuncio:**` + salto + `Mañana hay mantenimiento de 10 a 10:30`
- Confirmación al admin: `✅ Anuncio enviado a **3** usuarios.` (y `\n⚠️ 1 no pudieron recibirlo.` si hubo fallos)
- Cancelado: `❌ Anuncio cancelado.`

---

## 2. Menús y botones

### Menú principal (inline)
7 botones que acompañan todas las respuestas:

```
[💰 Balance] [📊 Presupuestos]
[🎯 Ahorros] [💱 Monedas]
[📋 Transacciones] [❓ Ayuda]
[⚙️ Más opciones]
```

### Navegación por secciones
- Cada sección abre un menú con sus acciones y cierra con `[🔙 Volver]` y `[🏠 Inicio]`.
- Las consultas se responden al instante en el mismo mensaje; las acciones con datos lanzan un **prompt de lenguaje natural** con un ejemplo (ej: `` `Mi presupuesto para comida es $500` ``).
- Al terminar una acción por lenguaje natural, el bot muestra los **7 botones principales**.

### Secciones y acciones
Cada sección muestra **su contenido directamente** al abrir (sin botón "Ver"): el balance del mes, tus presupuestos, tus metas, tus monedas y tus últimas transacciones aparecen en el mensaje junto con las acciones.

**💰 Balance:** balance del mes + `Ver gastos` · `Ver ingresos`.

**📊 Presupuestos:** presupuestos actuales + `Restante de un presupuesto` (elige cuál) · `Gastos por presupuestos` · `Crear presupuesto` (prompt NL).

**🎯 Ahorros:** metas actuales + `Crear meta` (prompt NL) · `Agregar dinero a una meta` (elige cuál → prompt NL) · `Eliminar una meta` (elige cuál → confirmar) · `Eliminar todas las metas` (confirmar).

**💱 Monedas:** monedas actuales + `Agregar moneda` · `Eliminar moneda` · `Predeterminada`.

**📋 Transacciones:** últimas transacciones + `Ver gastos` · `Ver ingresos` · `Registrar gasto` (prompt NL) · `Registrar ingreso` (prompt NL).

**❓ Ayuda:** `Registrar gasto/ingreso` · `Ver balance` · `Crear presupuesto` · `Crear metas` · `Todos los comandos`.

**⚙️ Más opciones:** `Notificaciones` · `Exportar` · `Resumen del mes` · `Borrar historial`.

### Respuestas de las secciones de balance/presupuestos

**💰 Balance:** `💰 **Balance de {mes}**` + el bloque de balance (sección 4).

**📋 Transacciones:**
- Vacío: `📝 No tienes transacciones registradas aún.`
- Con datos: `📝 **Tus últimas transacciones:**` + una línea por movimiento:
  `📉 $50.00 - Gasto: almuerzo (2026-08-17)`

**📊 Presupuestos:**
- Vacío: `📊 No tienes presupuestos configurados.` + salto + ``Usa: `Mi presupuesto para comida es $500 este mes` ``
- Con datos: bloque de la sección 5.

### Menú de monedas
Sin monedas:

```
💱 **Tus monedas:**

📝 Aún no tienes monedas configuradas.

Toca **➕ Agregar** para crear tu primera moneda.
```

Con monedas:

```
💱 **Tus monedas:**
━━━━━━━━━━━━━━━━━
  $ Dolar (USD) ⭐ predeterminada
  $ Peso cubano (CUP)
```

Botones: `➕ Agregar` · `🗑️ Eliminar` · `⭐ Predeterminada`.

**Agregar moneda (flujo en 3 pasos):**
- Paso 1: `✅ Nombre: **Dolar**` + salto + `¿Cuál es el símbolo? (ej: $, €, ₿, £)`
- Paso 2: `✅ Símbolo: **$**` + salto + `¿Cuál es la abreviatura? (ej: USD, EUR, CUP)`
- Éxito: `✅ **Moneda creada!**` + salto + `  $ Dolar (USD) ⭐ (predeterminada)`
- Cancelar: `❌ Agregación cancelada.`

**Presets** (`➕ Agregar` → menú): `🇺🇸 USD · Dólar` · `🇪🇺 EUR · Euro` · `🪙 USDT · Tether` · `🇨🇺 CUP · Peso cubano` · `✍️ Otra moneda` · `❌ Cancelar`
- Ya existe: `📝 Ya tienes **Dólar (USD)** en tus monedas.`
- Agregada: `✅ Moneda agregada: **$ Dólar (USD)**.`

**Manual:** `✍️ **Agregar moneda manualmente**` + salto + `¿Cómo se llama la moneda?` + salto + `(ej: Euro, Peso cubano, USDT)` + salto + ``Escribe `cancelar` para salir.``

**Eliminar moneda:** `🗑️ **Elige la moneda a eliminar:**` + salto + `La moneda predeterminada no aparece porque no se puede eliminar.`
- Sin monedas: `📝 No tienes monedas para eliminar.`
- Eliminada: `🗑️ Moneda eliminada: **$ Dolar (USD)**.`
- No permitido: `⚠️ No puedes eliminar la moneda predeterminada.` + salto + `Primero cambia la predeterminada a otra moneda.`
- No existe: `❌ Esa moneda ya no existe.`

**Cambiar predeterminada:** `⭐ **Elige la nueva moneda predeterminada:**`
- Menos de 2 monedas: `📝 Necesitas al menos 2 monedas para cambiar la predeterminada.`
- Hecho: `⭐ **USD** es ahora tu moneda predeterminada.`

**Info de moneda:** `💱 **Dolar**` + salto + `  Símbolo: $` + `  Abreviatura: USD` + ` ⭐ predeterminada` (si aplica)

### Botones de pendiente (cuando hay que confirmar)
- Tipo de transacción: `📉 Es un gasto` · `📈 Es un ingreso` · `❌ Cancelar`
- Elegir moneda: una fila por moneda (`$ Peso cubano (CUP)` → confirmar) + `❌ Cancelar`
- Cancelar: `❌ Registro cancelado.`

### Botones de transacciones múltiples
`✅ Guardar todo` · `✏️ Editar #1` … · `🗑️ Quitar #1` … · `❌ Cancelar`
- Canceladas: `❌ Transacciones canceladas. No se guardó nada.`
- Quitar una: `🗑️ Eliminada: $50.00 - almuerzo` + salto + `{preview}` + botones restantes
- Sin pendientes: `❌ No quedan transacciones. Proceso cancelado.`
- Editar una: `✏️ **Editando transacción 2:**` + salto + `📉 $50.00 - almuerzo` + salto + `Envíame la transacción corregida, por ejemplo:` + salto + `• \`$50 en comida\`` + salto + `• \`Recibí $200 de salario\`` + salto + `La reemplazaré en la lista.`
- Actualizada: `✅ Transacción #2 actualizada.` + salto + `{preview}`

---

## 3. Registro de transacciones

### Gasto normal
`✅ Gasto registrado: $50.00 (Peso Cubano) en 'Comida'`

Con moneda: `(Peso Cubano)` es el nombre de la moneda. Sin moneda: solo `$50.00`.

Error de parseo: `No pude entender la cantidad en tu gasto. ¿Podrías especificar el monto?`
Error general: `❌ Ocurrió un error al registrar tu gasto: 50.00. Por favor, inténtalo de nuevo.`

### Gasto ligado a un presupuesto
`✅ Gasto registrado: $500.00 (Peso Cubano) del presupuesto de 'barbería'` + salto + `📊 Presupuesto 'barbería': $1000.00 (CUP) planeado, $500.00 (CUP) usado (50%). Te quedan $500.00 (CUP).`

Si el gasto cruza un umbral, se anexa con doble salto la alerta correspondiente (sección 7).

### Ingreso
`✅ Ingreso registrado: $2000.00 (Peso Cubano) de 'Salario'`

Error de parseo: `No pude entender la cantidad en tu ingreso. ¿Podrías especificar el monto?`
Error general: `❌ Ocurrió un error al registrar tu ingreso: 2000.00. Por favor, inténtalo de nuevo.`

### Registro con varias monedas (no especificó cuál)
```
💱 **Tienes varias monedas configuradas y no especificaste cuál usar.**

Elige la moneda para registrar:

  $ Peso cubano (CUP) ⭐
  $ Dolar (USD)
```

### Monto sin tipo claro
`Detecté un monto de **$50.00** en comida, pero no estoy seguro si es un **gasto** o un **ingreso**.` + salto + `¿Podrías confirmar con un botón?`

### Sin monto entendible
```
❌ No pude entender el monto en tu mensaje.

Asegúrate de incluir un número, por ejemplo:
• `Gasté $50 en comida`
• `Recibí $300 de salario`
```

### Transacciones múltiples
Preview:

```
📋 **Transacciones detectadas**
┈┈┈┈┈┈┈┈┈┈
📉 **1.** $50.00 - Gasto: comida (Comida)
📈 **2.** $30.00 - Ingreso: reembolso (Otros)
┈┈┈┈┈┈┈┈┈┈
📉 Total gastos: **$50.00**
📈 Total ingresos: **$30.00**
Neto: **-$20.00**

¿Quieres guardar estas transacciones?
```

- Error: `❌ No pude detectar ninguna transacción en tu mensaje.`
- Guardadas: `✅ **2 transacción(es) guardada(s)**` (+ `\n⚠️ 1 no se pudieron guardar` si hubo errores)
- Todas fallidas: `❌ No pude guardar ninguna transacción. Intenta de nuevo.`

---

## 4. Consultas

### Balance
```
💰 **Balance de agosto 2026**
┈┈┈┈┈┈┈┈┈┈
```

Varias monedas (una por moneda, formato tabular):

```
**USD**
📈 $2,000.00   📉 $350.00   → **$1,650.00**

**CUP**
📈 $5,000.00   📉 $1,200.00   → **$3,800.00**

¿Ver transacciones recientes o configurar un presupuesto?
```

Moneda única:

```
💰 **Balance de agosto 2026**
┈┈┈┈┈┈┈┈┈┈
📈 Ingresos: $2,000.00
📉 Gastos: $350.00
Neto: **$1,650.00**

¿Ver transacciones recientes o configurar un presupuesto?
```

Error: `❌ Ocurrió un error al obtener tu balance. Por favor, inténtalo de nuevo.`

### Transacciones / gastos / ingresos
```
📋 **Tus gastos recientes**
┈┈┈┈┈┈┈┈┈┈
📉 $50.00 - Gasto: almuerzo (2026-08-17)
📉 $30.00 - Gasto: transporte (2026-08-16)

📉 **Total gastado:** $80.00 · 2 registros
```

Sin filtro de tipo, el cierre es `ℹ️ N registros` (sin total). Vacío (según tipo): `📝 No tienes gastos registrados todavía.` · `📝 No tienes ingresos registrados todavía.` · `📝 No tienes transacciones registradas todavía.`
Error: `❌ Ocurrió un error al obtener tus transacciones.` + salto + `Intenta de nuevo o escribe /help.`

### Mayor gasto (día / semana / mes)
```
📉 **Mayor gasto de hoy**
$120.00 (CUP) - supermercado
Supermercado · 2026-08-17

**Top 3 gastos**
• $120.00 (CUP) - supermercado (Supermercado)
• $80.00 (CUP) - almuerzo (Comida)
• $35.00 (CUP) - taxi (Transporte)

📉 **Total:** $235.00 (CUP)
```

Vacío: `📅 No registraste gastos para hoy.`
Error: `❌ Ocurrió un error al consultar tus gastos.`

### Movimientos por fecha
```
📅 **Movimientos de ayer**
📉 **Total gastado:**
• $235.00 (CUP)

📈 **Total recibido:**
• $500.00 (CUP)
```

Vacío: `📅 No tienes movimientos para ayer.`
Error: `❌ Ocurrió un error al consultar tus movimientos.`

### Presupuestos (ver todos)
```
📊 **Tus presupuestos**
┈┈┈┈┈┈┈┈┈┈

**Comida** · mensual
`██████░░░░` 64% — $320.00 de $500.00 (CUP)
Restante: **$180.00 (CUP)**
```

Vacío: `📊 No tienes presupuestos configurados.` + salto + `Prueba con: ` + `` `Mi presupuesto para comida es $500 este mes` ``
Error: `❌ Ocurrió un error al obtener tus presupuestos.`

### Presupuesto específico (restante/progreso)
```
📊 **Comida** · mensual
`██████░░░░` 64% — $320.00 de $500.00 (CUP)
Restante: **$180.00 (CUP)**
```

- Sin nombre: `¿De qué presupuesto quieres saber? Dime su nombre (ej: 'comida', 'barbería').`
- No existe y no hay ninguno: `❌ No tienes un presupuesto para 'barbería' y todavía no tienes ninguno configurado.` + salto + ``Para crearlo: `Mi presupuesto para barbería es $500` ``
- No existe pero hay otros: `❌ No encontré un presupuesto para 'barbería'.` + salto + `Tus presupuestos actuales: 'comida', 'transporte'.` + salto + ``Para crearlo: `Mi presupuesto para barbería es $500` ``
- Error: `❌ Ocurrió un error al consultar tu presupuesto.`

### Gastos del período en tus presupuestos
```
📊 **Gastos de ayer en tus presupuestos**
┈┈┈┈┈┈┈┈┈┈

**barbería**
Gastado en ayer: **$120.00 (CUP)**
Restante: **$180.00 (CUP)** · 40% usado
`████░░░░░░`

📉 **Total:** $120.00 (CUP)
```

Vacío: `📅 No registraste gastos para ayer.` · Error: `❌ Ocurrió un error al consultar tus gastos.`

### Categorías
```
📋 **Tus categorías**
┈┈┈┈┈┈┈┈┈┈
📉 **Gastos**
• Comida - Alimentación diaria
• Transporte - Desplazamientos

📈 **Ingresos**
• Salario - Nómina mensual

¿Crear una categoría o registrar una transacción?
```
Vacío: `📝 No tienes categorías configuradas todavía. ¡Crea algunas para empezar!`
Error: `❌ Ocurrió un error al obtener tus categorías. Por favor, inténtalo de nuevo.`

### Análisis por fecha (rango)
```
📅 **Análisis: esta semana**
┈┈┈┈┈┈┈┈┈┈

📈 **Ingresos (2 transacciones):**
   $2000.00 (CUP)
📉 **Gastos (5 transacciones):**
   $350.00 (CUP)
Neto: **+$1,650.00**
ℹ️ 7 transacciones

**Gastos por categoría**
• Comida: $180.00 (3x) `██████░░░░` 62%
• Transporte: $170.00 (2x) `████░░░░░░` 38%

📉 **Mayor gasto:** $120.00 (CUP) - supermercado (Supermercado)

**Detalle de gastos**
📉 $120.00 (CUP) - supermercado (Supermercado) [2026-08-17]

**Detalle de ingresos**
📈 $2000.00 (CUP) - salario (Salario) [2026-08-15]
```

Vacío: `📅 **Esta semana:**` + salto + `No tienes transacciones registradas para esta semana.` + salto + `¿Quieres registrar algo? Por ejemplo:` + salto + `• \`Gasté $50 en comida\`` + salto + `• \`Recibí $300 de salario\``

---

## 5. Presupuestos

### Crear presupuesto
`✅ **Presupuesto configurado:** $500.00 (CUP) para comida`

### Añadir monto (modo "sumar")
`✅ **Añadido $100.00 (CUP) al presupuesto de comida.**` + salto + `📊 Total disponible: $600.00 (CUP)`

Si se forzó la moneda del presupuesto (el usuario escribió una moneda distinta):
`\n💡 Se aplicó en la moneda del presupuesto (CUP).`

### Pedir moneda (varias monedas)
```
💱 **Tienes varias monedas configuradas y no especificaste cuál usar para el presupuesto.**

Elige la moneda:

  $ Peso cubano (CUP) ⭐
  $ Dolar (USD)
```

### Monto inválido
`❌ No pude entender el monto del presupuesto. Usa: \`Mi presupuesto para comida es $500\``

### ⚠️ Rechazo por balance (v2.11)
Cuando el presupuesto excede el balance libre de su moneda (regla individual + acumulativa):

```
❌ **No puedes configurar un presupuesto de $300.00 (USD).**

Tu balance del mes en **USD** es **$200.00** y ya tienes **$50.00** en otros presupuestos, así que solo te quedan **$150.00** libres.

Ajusta el monto o registra más ingresos primero.
```

### Eliminar presupuesto
- Eliminado: `🗑️ **Presupuesto eliminado:** comida`
- Sin nombre: `❌ Dime el nombre del presupuesto a eliminar.`
- No encontrado: `❌ No encontré un presupuesto llamado comida.` + salto + ``Verifica su nombre con `Ver presupuestos` ``
- Error: `❌ Ocurrió un error al eliminar el presupuesto.`

---

## 6. Resumen mensual

Estructura completa:

```
📊 **Resumen de agosto**
┈┈┈┈┈┈┈┈┈┈

📈 $5,000.00 (CUP)
📉 $1,200.00 (CUP)
💰 Neto: **+$3,800.00 (CUP)** · **+$200.00 (USD)**

**Gastos por categoría (CUP)**
🍔 Comida                    `██████░░░░` 35% — $420.00
🚕 Transporte                `███░░░░░░░` 25% — $300.00

Mayor gasto: 🍔 Comida, $420.00 (CUP) el día 17
Promedio diario: $38.71 (CUP)/día

💰 **Balance del mes:**
**+$3,800.00 (CUP)** · **+$200.00 (USD)**
```

**Sin movimientos en el mes:**
```
📊 **Resumen de agosto**
┈┈┈┈┈┈┈┈┈┈

😴 Sin movimientos este mes.
```

**Sin gastos (pero con movimientos):** en lugar de la sección de gastos aparece `📝 Sin gastos registrados este mes.`

**Balance del mes según el caso:**
- Varias monedas: `💰 **Balance del mes:**` + `**+$3,800.00 (CUP)** · **-$50.00 (USD)**` (con signo y abreviatura)
- Solo "Sin moneda": `**+$3,800.00**`
- Sin monedas: `**$0.00**`

> **Emojis por categoría** en "Gastos por categoría": 🍔 comida · 🍽️ restaurante · ☕ café · 🛒 supermercado · 🚕 transporte/taxi · ⛽ gasolina · 🚌 bus · 💊 salud · 🎓 educación · 👕 ropa · 🏠 hogar · 💡 luz · 🚰 agua · 📶 internet · 📱 teléfono · 🎬 cine/entretenimiento · 🎮 juego · 📺 suscripciones · ⚽ deporte · 🏋️ gym · 💼 salario · 🏪 negocio · 💻 freelance · 📈 trading · 🐷 ahorro · 🎯 meta · 🧾 impuestos · 🔧 servicio · 💳 pagos · 🎉 fiesta · 🎁 regalo · 🤝 donación; default 📦.

Error: `❌ Ocurrió un error al generar tu resumen.`

---

## 7. Notificaciones

### Alertas de presupuesto (se anexan al mensaje del gasto)
Se disparan solo cuando el presupuesto **cruza** el umbral con ese gasto y la alerta está activa. Un único emoji ⚠️ para las tres severidades (la palabra distingue la gravedad).

- **80%:** `⚠️ **Comida** cerca del límite: $400.00 de $500.00 (CUP) — 80%`
- **100% (agotado):** `⚠️ **Comida** agotado: $500.00 de $500.00 (CUP)`
- **125% (excedido):** `⚠️ **Comida** excedido: $625.00 de $500.00 (CUP) — 125%`

Varias alertas cruzadas en el mismo gasto se unen con salto de línea.

### Resumen diario (todos los días 21:30 hora de Cuba)
```
📊 **Resumen diario**
📅 17/08/2026
┈┈┈┈┈┈┈┈┈┈
📉 Gastos: $120.00 (CUP)
📈 Ingresos: $500.00 (CUP)
📋 3 movimiento(s) registrado(s).

💰 Balance del mes: **+$3,800.00 (CUP)**
```

Sin movimientos:
```
📊 **Resumen diario**
📅 17/08/2026
┈┈┈┈┈┈┈┈┈┈
😴 Sin movimientos hoy.

💰 Balance del mes: **+$3,800.00 (CUP)**
```

Sin gastos/ingresos se muestra `📉 Gastos: $0.00` / `📈 Ingresos: $0.00`. Con una sola moneda "Sin moneda": `💰 Balance del mes: **+$3,800.00**`. Sin monedas: `💰 Balance del mes: **+$0.00**`.

Error interno (solo log, no se envía al usuario): `📊 No pude generar tu resumen diario.` + salto + `Intenta de nuevo o escribe /help.`

---

## 8. Exportación de datos

Flujo `/exportar`:
1. `📤 **¿En qué formato quieres exportar tus datos?**` → botones Excel/CSV
2. `📤 Formato elegido: **Excel (.xlsx)**` + salto + `¿Qué período quieres exportar?` → botones `🗓 Todo el historial` · `🗓 Este mes` · `🗓 Últimos 30 días` · `❌ Cancelar`
3. `📤 **Generando tu exportación...**` + salto + `Puede tardar unos segundos.` → se envía el archivo `.xlsx` o `.csv`

Lenguaje natural: `📤 Voy a exportar tus datos en **Excel (.xlsx)**.` + salto + `Dame un segundo mientras genero el archivo...`

Errores:
- `❌ No pude generar tu exportación. Intenta de nuevo en un momento.`
- `⚠️ Ocurrió un error al procesar tu solicitud.`
- Cancelado: `❌ Exportación cancelada.`

> El contenido (hojas Resumen / Movimientos / Gastos por categoría, o CSV paginado) viaja como **documento**, no como mensaje de texto.

---

## 9. Modificar / eliminar transacciones

### No entendió qué modificar
```
🤔 No pude entender qué quieres modificar.

Puedes hacer cosas como:
• 'Cambia el gasto a ingreso'
• 'Modifica el monto a $100'
• 'Cambia la descripción a almuerzo'
• 'Cambia la categoría a transporte'
• 'Elimina el último gasto'
```

### Cambiar tipo
```
✅ **Tipo cambiado:**
De: 📉 Gasto: $50.00 - almuerzo
A: 📈 $50.00 - Ingreso: almuerzo
```
- Ya es ese tipo: `ℹ️ La transacción ya es un **gasto**. No hay cambios necesarios.`
- No encontrada: `❌ No encontré la transacción que quieres modificar. ¿Puedes especificar cuál?`

### Cambiar monto
```
✅ **Monto actualizado:**
De $50.00 → **$75.00**
```
- Inválido: `❌ El monto nuevo no es válido. Especificá un número positivo.`

### Cambiar descripción
```
✅ **Descripción actualizada:**
De 'almuerzo' → **'almuerzo con amigos'**
```

### Cambiar categoría
```
✅ **Categoría cambiada:**
De 'Comida' → **'Restaurante'**
```

### Cambiar fecha
```
✅ **Fecha actualizada:**
De 2026-08-17 → **2026-08-18**
```

### Eliminar transacción
```
🗑️ **Transacción eliminada:**
📉 $50.00 - Gasto: almuerzo
```

Errores comunes: `❌ No pude actualizar el monto. Intenta de nuevo.` · `❌ No pude cambiar el tipo. Intenta de nuevo.` · `❌ Ocurrió un error al procesar la modificación. Intenta de nuevo.`

---

## 10. Metas de ahorro

```
🎯 **Tus metas de ahorro**
┈┈┈┈┈┈┈┈┈┈

**Vacaciones**
$1,200.00 / $5,000.00 (24%)
Restante: **$3,800.00**
`██░░░░░░░░`
Meta para: 2026-12-31
```

Vacío: `🎯 No tienes metas de ahorro.` + salto + ``Usa: `Quiero ahorrar $5000 para vacaciones` ``
Creada: `✅ **Meta de ahorro creada:** $5,000.00 para vacaciones`
Error: `❌ Ocurrió un error al obtener tus metas de ahorro.` · `❌ Ocurrió un error al crear la meta de ahorro.`

---

## 11. Ayuda "cómo…"

### 📉 Registrar un gasto
```
📉 **Cómo registrar un gasto:**

Escribe un mensaje con tu gasto en lenguaje natural:

• `Gasté $50 en comida`
• `Compré $30 de ropa`
• `Pagué $100 de luz`
• `$20 en transporte`
• `Gasto $75 en supermercado`

El bot detecta automáticamente la categoría y el monto.
También puedes registrar varios gastos juntos:
• `$50 en comida y $30 en transporte`
```

### 📈 Registrar un ingreso
```
📈 **Cómo registrar un ingreso:**

Escribe un mensaje con tu ingreso:

• `Recibí $2000 de salario`
• `Ingresé $500 de trading`
• `Cobré $300 de freelance`
• `Agrega $100 de dividendos`
• `Gané $150 de ventas`

El bot lo clasifica como ingreso automáticamente.
```

### 💰 Ver balance
```
💰 **Cómo ver tu balance:**

• `¿Cuánto tengo?` — Balance general
• `¿Cuál es mi saldo?` — Ver saldo actual
• `Ver balance` — Resumen de finanzas

Te mostrará tus ingresos totales, gastos totales y saldo neto.
```

### 📋 Ver historial
```
📋 **Cómo ver tu historial:**

• `¿Qué gasté hoy?` — Transacciones de hoy
• `¿Qué hice ayer?` — Transacciones de ayer
• `Ver transacciones` — Últimas transacciones
• `Historial de esta semana` — Resumen semanal

También puedes filtrar por categoría o fecha.
```

### 🏷️ Ver categorías
```
🏷️ **Cómo ver categorías:**

• `¿Cuánto gasté en comida?` — Gastos en comida
• `¿Cuánto gasté en transporte?` — Gastos en transporte
• `¿Qué categorías tengo?` — Ver todas las categorías

Las categorías se crean automáticamente al registrar transacciones.
```

### 🔔 Notificaciones
```
🔔 **Notificaciones:**

• **Resumen diario:** todos los días a las **21:30 (hora de Cuba)** recibes un resumen con tus movimientos de hoy y tu balance.
• **Alertas de presupuesto:** te avisamos al instante cuando un presupuesto llega al **80%**, se **agota (100%)** o lo **superas (125%)**.
• **Actívalo o desactívalo todo desde:** `/notificaciones`

Las alertas de presupuesto se envían automáticamente en cada gasto; el resumen diario solo si lo tienes activado.
```

### 📊 Configurar presupuesto
```
📊 **Cómo configurar un presupuesto:**

• `Mi presupuesto para comida es $500 este mes`
• `Presupuesto de transporte $200`
• `Límite de gasto $1000 por mes`

El bot te avisará cuando estés cerca del límite.
```

### 🎯 Meta de ahorro
```
🎯 **Cómo configurar una meta de ahorro:**

• `Quiero ahorrar $5000 para vacaciones`
• `Meta de ahorro $3000 para emergencias`
• `Objetivo: ahorrar $10000 este año`

El bot te mostrará cuánto has ahorrado hacia tu meta.
```

### ✏️ Modificar transacción
```
✏️ **Cómo modificar una transacción:**

• `Cambiar mi último gasto a $75`
• `Modifica la descripción de mi último gasto`
• `Cambia el monto de $100 a $150`
• `Pasa ese gasto a la categoría transporte`

Puedes modificar monto, descripción, categoría o fecha.
```

### 🗑️ Eliminar transacciones
```
🗑️ **Cómo eliminar transacciones:**

• `Eliminar mi último gasto`
• `Borrar la transacción de $50`
• `Quitar el gasto de comida`
• `/delete` — Borrar todo el historial

⚠️ Cuidado: eliminar todo el historial es irreversible.
```

### 🤖 Qué puedo hacer (general)
```
🤖 **Qué puedo hacer:**

📝 **Registrar:**
• Gastos: `Gasté $50 en comida`
• Ingresos: `Recibí $2000 de salario`
• Varios: `$50 comida y $30 transporte`

📊 **Consultar:**
• Balance: `¿Cuánto tengo?`
• Historial: `¿Qué gasté hoy?`
• Categorías: `¿Cuánto en comida?`

⚙️ **Configurar:**
• Presupuesto: `Mi presupuesto es $500 para comida`
• Metas: `Quiero ahorrar $5000 para vacaciones`

✏️ **Modificar/Eliminar:**
• Cambiar: `Cambiar mi último gasto a $75`
• Eliminar: `Eliminar mi último gasto`

📋 **Comandos:**
• `/start` — Iniciar el bot
• `/help` — Ver ayuda completa
• `/user` — Tu información
• `/notificaciones` — Alertas y resumen diario (21:30 hora de Cuba)
• `/delete` — Borrar historial
```

### 🤖 Respuesta genérica de ayuda
```
🤖 **Cómo puedo ayudarte:**

Pregúntame sobre cualquier funcionalidad:

• ¿Cómo registro un gasto?
• ¿Cómo veo mi balance?
• ¿Cómo pongo un presupuesto?
• ¿Cómo creo una meta de ahorro?
• ¿Cómo modifico una transacción?
• ¿Cómo elimino algo?
• ¿Qué comandos tienes?

O simplemente escribe tu gasto o ingreso directamente.
```

---

## 12. Mensajes de "no entendido" y errores

### Saludo
```
¡Hola Ana! 👋 ¿En qué te puedo ayudar?

Puedes:
• 📉 Registrar un gasto: `Gasté $50 en comida`
• 📈 Registrar un ingreso: `Recibí $300 de salario`
• 💰 Ver tu balance: `¿Cuánto tengo?`
• 📋 Ver transacciones: `¿Qué gasté hoy?`
• 📊 Configurar presupuesto: `Mi presupuesto es $500 para comida`
```

### Intención de consulta
```
🤔 Ana, parece que quieres **consultar** algo sobre tus finanzas.

¿Qué te gustaría saber?
• `¿Cuánto tengo?` — Ver balance general
• `¿Qué gasté hoy?` — Transacciones de hoy
• `¿Qué hice ayer?` — Transacciones de ayer
• `¿Cuánto gasté en julio?` — Análisis mensual
• `¿Qué gasté esta semana?` — Resumen semanal
• `¿Cuánto gasté en comida?` — Gastos por categoría
• `¿Cuánto ingresé?` — Ver ingresos
• `Del 1 al 10 de julio` — Rango de fechas
• `¿Cómo va mi presupuesto?` — Ver presupuestos
```

### Intención de configuración
```
⚙️ Ana, veo que quieres **configurar** algo.

¿Qué necesitas?
• `Mi presupuesto para comida es $500 este mes`
• `Quiero ahorrar $2000 para vacaciones`
• `Crear categoría: Suscripciones`
• `Mi meta de ahorro es $5000 para diciembre`
```

### Intención de modificación
```
✏️ Ana, parece que quieres **modificar** algo.

¿Qué necesitas cambiar?
• `Cambiar el monto de mi último gasto a $75`
• `Eliminar mi último gasto`
• `Cambiar la categoría de mi último ingreso a bonus`
• `Editar mi último gasto: descripción a uber`
```

### Acción con monto
```
💡 Ana, veo que mencionas un **monto** pero no pude procesar tu registro.

¿Puedes intentar con este formato?
• `Gasté $50 en comida` — Registrar un gasto
• `Recibí $300 de salario` — Registrar un ingreso
• `Pagué $20 de transporte` — Registrar un pago
• `$100 en supermercado` — Formato corto

También puedes incluir la fecha:
• `Gasté $50 en comida ayer`
• `Recibí $300 el lunes`
```

### Acción sin monto
```
💡 Ana, mencionas una **acción financiera** pero no veo un monto.

Para registrar necesito el monto:
• `Gasté $50 en comida`
• `Recibí $300 de salario`
• `$100 de uber`
```

### Monto sin acción
```
💡 Ana, veo un **monto** pero no sé qué hacer con él.

¿Quieres registrarlo?
• `Gasté $50 en comida`
• `Recibí $50 de salario`

¿O es parte de una consulta?
• `¿Cuánto gasté en $50?`
```

### Respuesta genérica (fallback final)
```
🤔 No identifiqué qué necesitas con: _"tu mensaje"_

**Prueba con:**
📉 `Gasté $50 en comida`
💰 `¿Cuánto tengo?`
🎯 `Quiero ahorrar $2000`

O escribe /help para ver todo lo que puedo hacer.
```

### Errores del sistema / IA no disponible

IA caída:
```
😔 Disculpa Ana, el servicio de IA no está disponible ahora.

Mientras tanto, puedes usar lenguaje natural directamente:

• `Gasté $50 en comida` — Registrar gasto
• `Recibí $300 de salario` — Registrar ingreso
• `¿Cuánto tengo?` — Ver balance
• `Ayuda` — Ver comandos

Intenta de nuevo en unos segundos.
```

Error de sistema:
```
⚠️ Ana, algo salió mal.

Intenta con estos comandos:
• `Gasté $50 en comida`
• `¿Cuánto tengo?`
• `Ayuda`

Si el problema persiste, escribe `/help`.
```

Error general del handler de mensajes:
```
⚠️ Ups, algo salió mal al procesar tu mensaje.

Intenta con estos comandos:
• `Gasté $50 en comida`
• `¿Cuánto tengo?`
• `¿Qué gasté hoy?`

Si el problema persiste, escribe `/help`.
```

`error_handler`: `Lo siento, ocurrió un error inesperado. Por favor intenta de nuevo.`

---

## 13. Menú de comandos de Telegram

Comandos sugeridos al escribir `/` (registrados con `set_my_commands`):

| Comando | Descripción |
|---|---|
| `/start` | Iniciar o reiniciar el bot y ver tu balance |
| `/resumen` | Resumen del mes actual |
| `/categorias` | Ver tus categorías financieras |
| `/gastos` | Ver tus últimos gastos |
| `/ingresos` | Ver tus últimos ingresos |
| `/metas` | Ver tus metas de ahorro |
| `/notificaciones` | Alertas de presupuesto y resumen diario |
| `/exportar` | Exporta tus datos a Excel/CSV |
| `/help` | Ver todos los comandos y ejemplos de uso |
| `/user` | Ver tu información de usuario |
| `/delete` | Borrar todo el historial de transacciones |

---

## 14. Notas de estilo — correcciones aplicadas

### Rediseño v2.12 (`REDISENO MENSAJES.md`)
Aplicado sobre todos los mensajes de uso frecuente (`/start`, `/user`, balance, presupuestos, alertas, resumen mensual, resumen diario, fallback):

1. **Emojis semánticos de tabla cerrada:** 📈 ingreso, 📉 gasto, 💰 balance/dinero (solo en títulos), 📊 presupuesto/estadística, 🎯 meta, 💱 moneda, 🔔 notificación, ⚠️ advertencia (único para las 3 severidades de alerta), ✅ OK, ❌ error, ℹ️ info, 🗑️ eliminar. Se eliminaron 💸, 💵, 🚨, ⛔, 🏦, ⚙️ y los duplicados de emoji en el cuerpo.
2. **Montos con separador de miles** vía `formato.fmt_moneda()` (`$1,500.00`) — nunca se concatenan a mano (`.2f`).
3. **Separador corto** `┈┈┈┈┈┈┈┈┈┈` (`formato.SEPARADOR`) reemplaza `━━━━━━━━━━━━━━━━━`, y solo en mensajes multi-sección.
4. **Títulos Title Case** (`Balance de agosto 2026`, `Resumen diario`) en vez de MAYÚSCULAS SOSTENIDAS.
5. **Nombres en negrita sin comillas** (`**Comida**`, no `'comida'`); negrita solo en datos accionables (montos, nombres).
6. **Barras de progreso en backticks** con `round()` (`formato.barra_progreso`, 10 segmentos), y la abreviatura de moneda solo en el total de presupuesto.
7. **Fallback genérico** reducido a 3 ejemplos + derivación a `/help`.

### Balance por mes (v2.13)
1. **El balance consultado es del mes en curso:** `obtener_balance()` filtra por el primer día del mes actual (`inicio_mes_actual()`), así se "resetea" solo al cambiar de mes, sin borrar el historial.
2. **El período queda explícito** en el encabezado: `💰 **Balance de agosto 2026**` (botón, `/user`, consultas NL, resumen mensual y resumen diario).
3. **Presupuestos v2.11:** la validación del tope usa el balance del mes en curso (`Tu balance del mes en **USD** es ...`).
4. **Histórico intacto y consultable:** para todo el historial se pasa `fecha_inicio="0000-01-01"` (exportación `/exportar todo`); el resto del pasado se ve con `/resumen`, análisis por fecha y `/exportar`.

### Correcciones previas (v2.11.1)

Correcciones de estilo y ortografía aplicadas al código para unificar los mensajes:

1. **Negrita unificada:** todos los mensajes usan ahora `**negrita**`. Se cambiaron de `*negrita*` (asterisco simple) el resumen mensual, las alertas de presupuesto, el resumen diario, la bienvenida `/start`, el menú `/notificaciones` y el encabezado del changelog (`*v2.x*`).
2. **Barras de progreso unificadas a 10 segmentos:** `_crear_barra_progreso` ahora usa `largo=10` por defecto (antes 8) y todos los puntos que construían la barra manualmente (`█`/`░`) usan el helper: "Ver presupuestos", "Metas de ahorro" y el teclado de presupuestos.
3. **Erratas corregidas:**
   - `recibirllo` → `recibirlo` (confirmación de `/anuncio`)
   - `Asegurate` → `Asegúrate`
   - `todavia` → `todavía` (gastos/ingresos/transacciones vacíos)
   - `Ocurrio` → `Ocurrió` (transacciones y presupuestos)
   - `—Registrar un gasto` → `— Registrar un gasto` (espacio tras el em-dash)
4. **Código muerto eliminado:** `_formatear_moneda_para_display` en `handlers.py`.
5. **Resumen diario:** el balance por moneda usa ahora el mismo formato que el resto del bot: `💰 Balance del mes: **+$3,800.00 (CUP)**` (símbolo + abreviatura, con signo), en lugar de `💵 Balance actual: +$3800.00 (CUP)`.