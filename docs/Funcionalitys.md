# 💰 Personal Finance Bot — Todo lo que puedes hacer

Tu bot de finanzas personales en Telegram. Escríbele como si le hablaras a un amigo y él se encarga del resto. Sin formularios, sin apps complicadas.

---

## 💬 Habla, no rellenes

Escribe en tus palabras y el bot te entiende:

- **"Gasté 50 en comida"** → lo registra automáticamente.
- **"Recibí 2000 de salario"** → lo guarda como ingreso.
- **"Compré 30 de ropa"** → detecta el monto y la categoría solos.

Olvídate de formularios: escribe natural y listo. La IA está siempre disponible, incluso dentro del menú de botones.

---

## ✨ Registro de gastos e ingresos

- Registra **gastos e ingresos** con un solo mensaje.
- El bot **crea la categoría automáticamente** (comida, transporte, ropa, salario...).
- Te confirma todo con **fecha, monto y moneda**.
- Entiende montos en todos los formatos: `$248.50`, `1.500`, `50 usd`, `500 cup`.
- **Seguro por diseño:** solo acepta montos positivos (`-50`, `0` o texto sin número son rechazados con un aviso claro), valida las fechas y recorta descripciones largas.

---

## 🧾 Multi-transacciones (una frase, varios movimientos)

- **"50 en comida y 30 en taxi"** → el bot detecta **las dos** operaciones.
- Te muestra una **vista previa** con botones para **editar, quitar o guardar** cada una antes de confirmar.
- Ideal para cuando llega el delivery con varias compras juntas. 😄

---

## 🎯 Presupuestos que te cuidan

- **Crea presupuestos** con nombre propio: *"mi presupuesto para barbería es $500"*.
- **Añade más** cuando quieras: *"añade 500 al presupuesto de barbería"*.
- El bot te muestra una **barra de progreso**: cuánto has gastado y cuánto te queda.
- **Pregunta por uno en específico**: *"¿cuánto me queda de transporte?"* → respuesta al instante.
- Cuando gastas en un presupuesto, el bot te **descuenta y te dice el restante** sin que tengas que pedirlo.
- **Gasto ligado a presupuesto:** si dices *"gasté 500 del presupuesto para barbería"*, se descuenta de ese presupuesto y tu respuesta muestra cuánto llevas y cuánto queda.
- **Sin duplicados:** redefinir o repetir un nombre de presupuesto lo actualiza, no crea otro.
- **Ligado a tu balance real:** no puedes fijar un presupuesto mayor al dinero disponible en su moneda (y la suma de todos tus presupuestos de una moneda tampoco lo excede). Si el monto no cabe, el bot te dice cuánto balance tienes, cuánto ya comprometiste y cuánto te queda libre.
- Desde el menú también puedes **restar un gasto directo de un presupuesto** (elige uno → *"Restar gasto"* → escribe el monto).

---

## 🐜 Gastos hormiga bajo la lupa

Son esos pequeños y recurrentes gastos que se esconden a fin de mes: cafés, snacks, recargas, transporte, suscripciones... El bot los detecta y te los muestra.

- **Detección automática** por 3 reglas:
  1. **Monto:** por debajo de un umbral que tú configuras (por defecto $5 USD, con conversión automática a la moneda del gasto).
  2. **Categoría:** café, snacks, transporte, suscripciones, comida rápida, recargas de teléfono y bebidas.
  3. **Frecuencia:** cuando se repiten varias veces a la semana.
- **Etiquetas inteligentes:** interpreta la descripción para asignar la categoría correcta ("me recargue el teléfono" → **recarga**, no "comida").
- **Reporte claro:** resumen de tus hormigas del período con porcentaje sobre tus gastos, umbral por moneda y fechas; acceso directo desde el botón **🐜 Gastos Hormiga** del menú o con `/gastos_hormiga`.
- **`/config_hormiga`** para ajustar todo:
  - Umbral y su moneda: *`/config_hormiga umbral 10`* o *`umbral 100 cup`*.
  - Frecuencia mínima por semana: *`frecuencia 5`*.
  - Notificaciones de hormiga on/off: *`/config_hormiga notificaciones off`*.
- La **alerta** solo se dispara cuando se acumulan varios hormigas en la misma semana (no molesta en cada gasto pequeño).

---

## 💱 Múltiples monedas, cero líos

- Maneja todas tus monedas: **CUP, USD, USDT, EUR y más**.
- Escribe el monto con la moneda: *"50 usd en ropa"* o *"500 cup en comida"*.
- **Agrega monedas** con botones rápidos (USD, EUR, USDT, CUP) o escribe la tuya.
- **Elige tu moneda predeterminada** y **elimina** las que ya no uses.
- Si ya tienes un presupuesto con moneda definida, el bot **la reutiliza solo** — no te vuelve a preguntar.
- Cuando falta aclarar la moneda, el bot te la **pide con botones** para registrar en un toque.
- Tus **saldos se agrupan por moneda**, todo claro y separado.

---

## 📊 Consultas en tus palabras

- **"¿Cuánto tengo?"** → balance del **mes en curso** (ingresos, gastos y neto por moneda). El balance se **resetea solo cada mes**, sin borrar tu historial.
- **"Ver mis gastos"** / **"ver mis ingresos"** → listas de tus últimos movimientos.
- **"Ver todas mis transacciones"** → tu historial completo, agrupado por mes (o desde el botón **📂 Ver todas**).
- **"Ver presupuestos"** → progreso de todos tus presupuestos.
- **"Ver categorías"** → tus categorías organizadas por tipo.
- **"Ver mis metas"** / **"cuánto llevo ahorrado"** → tus metas de ahorro.
- **Resumen del mes** (`/resumen` o desde Más opciones) → lo que pasó con tu dinero este mes, de un vistazo.

---

## 📅 Análisis por fechas

- **"¿Qué gasté hoy?"** → tus gastos de hoy resumidos.
- **"Ver transacciones de esta semana"**, **"este mes"**, **"los últimos 7 días"** → análisis completo.
- Cada análisis incluye **totales por moneda, categorías destacadas y tu mayor gasto** del período.
- Entiende fechas naturales: **hoy, ayer, esta semana, este mes, hace N días/meses**.

---

## 🔥 Tus estadísticas al detalle

- **"¿Cuál fue mi mayor gasto ayer?"** → el más grande + el top 3 + el total.
- **"¿Cuánto gasté ayer de mis presupuestos?"** → desglose por presupuesto y total.
- **"¿Cuánto gasté esta semana?"** → totales por moneda al instante.
- *"¿Cuánto puedo gastar todavía de comida?"* → también responde a vocabulario libre.

---

## 🐷 Metas de ahorro

- **Crea metas**: *"quiero ahorrar 2000 para vacaciones"* (usa el propósito real, no "eso" ni "ello").
- Sigue el **progreso** (lo que llevas vs. tu objetivo) y tu **fecha meta**.
- **Agrega dinero** a una meta existente: *"agrega 900 cup a la meta del regalo de mi novia"*.
- **Elimina metas** por nombre (busca con coincidencias parciales/fuzzy) o **todas de una vez**: *"elimina todas mis metas"* — siempre con confirmación.
- Desde el menú puedes **crear, agregar o eliminar** metas con botones; al elegir una meta basta con escribir el monto (ej: `500`).

---

## ✏️ Edita y corrige sin complicaciones

- **"Cambia el monto del último gasto a 200"** → lo corrige al vuelo.
- **"Cambia el tipo de X a ingreso"** → re-clasifica.
- **"Cambia la fecha del último gasto"** → también valida que la fecha exista y no sea futura.
- **"Borra el último gasto"** / **"elimina el presupuesto de comida"** → adiós al error.
- **"Elimina la meta de ahorro del regalo de mi novia"** → borra la meta, no se confunde con el presupuesto.
- Escribe **"cancelar"** en cualquier flujo para salir sin aplicar el cambio.

---

## 🖱️ Menú guiado: todo a un toque

- **Menú principal de 8 secciones:** 💰 Balance, 📊 Presupuestos, 🎯 Ahorros, 💱 Monedas, 📋 Transacciones, 🐜 Gastos Hormiga, ❓ Ayuda y ⚙️ Más opciones.
- Cada sección muestra **su contenido directamente** y debajo sus acciones, con botón **Volver**.
- **Más opciones:** 🔔 Notificaciones, 📤 Exportar, 📅 Resumen del mes, 🗑️ Borrar historial y 🎫 Soporte.
- Las acciones que necesitan datos (crear presupuesto/meta, agregar dinero, registrar gasto/ingreso) te lanzan un **ejemplo en lenguaje natural** para que escribas el valor.
- Los flujos **recuerdan lo que seleccionaste**: elige un presupuesto o una meta y escribe solo el monto; el bot lo asocia al elemento elegido.
- Botones inline para elegir moneda, confirmar borrados, editar multi-transacciones y volver — todo **sin reenviar mensajes**.

---

## 📤 Tus datos, exportados y en orden

- **`/exportar`** → tu historial en **Excel (.xlsx)** o **CSV**, con hoja de **resumen**, **movimientos** y **gastos por categoría**.
- **Elige el período:** todo el historial, este mes o los últimos 30 días (o por mes exacto: `/exportar xlsx 2026-07`).
- Con lenguaje natural: *"exporta mis datos del mes"*, *"descarga mi historial"*.
- Si hay demasiados movimientos, se **dividen automáticamente** en varias partes para respetar los límites de Excel.
- **Ver todas tus transacciones:** historial completo agrupado por mes, desde el menú o con *"ver todas mis transacciones"*.
- **🗑️ Borra tu historial:** comando `/delete` o Más opciones → Borrar historial, siempre pidiendo **confirmación** antes de borrar todo.

---

## 🔔 Avisos que te cuidan el bolsillo

- **Alertas de presupuesto en tiempo real:** cuando un presupuesto llega al **80%**, se **agota (100%)** o lo **superas (125%)**, el bot te avisa justo en el momento del gasto. Nada de sorpresas a fin de mes.
- **Resumen diario automático:** cada día a las **21:30 (hora de Cuba)**, el bot te envía lo que pasó con tu dinero: movimientos de hoy y tu balance por moneda.
- **Control total:** activa o desactiva cada aviso (80%, 100%, 125% y el resumen diario) desde `/notificaciones` o Menú → Más opciones → Notificaciones.
- **Sin excusas para perderte el resumen:** si el bot estaba dormido a la hora señalada, te envía el resumen apenas vuelvas a escribir.

---

## 🎫 Soporte y contacto directo

- **`/soporte`** abre un menú para elegir cómo contactar al administrador:
  - 📤 **Enviar reporte:** cuentas el problema y le llega un **ticket identificado** (tu nombre, usuario e id) al admin.
  - 💬 **Escribir al admin directo:** abre su chat de Telegram personal con un toque (si está habilitado).
- También puedes enviar un reporte rápido: **`/soporte se me congela el bot`**.
- Así de fácil: **"cancelar"** cierra el flujo sin enviar nada.

---

## 🛡️ Validaciones que te protegen

- Montos solo positivos; fechas existentes y no futuras; descripciones recortadas automáticamente a 200 caracteres.
- **Anti-flood:** si escribes demasiado rápido, el bot te avisa *"Demasiadas solicitudes. Intenta de nuevo en N segundos"*. `/start` y `/help` nunca se bloquean.
- Alertas y acciones siempre con **confirmación** antes de eliminar.

---

## ⌨️ Todos los comandos de un vistazo

| Comando | Qué hace |
|---|---|
| `/start` | Iniciar o reiniciar el bot y ver tu balance |
| `/resumen` | Resumen del mes actual |
| `/categorias` | Ver tus categorías financieras |
| `/gastos` | Ver tus últimos gastos |
| `/ingresos` | Ver tus últimos ingresos |
| `/metas` | Ver tus metas de ahorro |
| `/gastos_hormiga` | Ver tus gastos hormiga |
| `/config_hormiga` | Configurar la detección de gastos hormiga (umbral, frecuencia, avisos) |
| `/notificaciones` | Alertas de presupuesto y resumen diario |
| `/exportar` | Exportar tus datos a Excel/CSV |
| `/user` | Ver tu información de usuario |
| `/delete` | Borrar todo el historial (con confirmación) |
| `/soporte` | Reportar un problema o escribir al admin |
| `/help` | Ver todos los comandos y ejemplos de uso |

Escribe `/` en el chat para ver el menú de comandos con sus descripciones.

---

## 🔑 Solo para el administrador

- **`/anuncio <texto>`** → envía un mensaje a todos los usuarios del bot.
- **`/metricas`** → usuarios registrados, activos ahora y en la última hora, mensajes procesados/bloqueados, transacciones del día, errores recientes y uptime.
- El bot registra su actividad en `data/logs/finanzas.log` con rotación automática.

---

## ❓ Ayuda siempre a mano

- Pregunta *"¿cómo registro un gasto?"* y el bot te explica.
- Comando `/help` con todos los comandos y ejemplos.
- Cada versión nueva **te avisa sus novedades** con un mensaje automático.

---

## 🏁 Empezar es gratis y rápido

1. Abre el bot en Telegram.
2. Envía `/start`.
3. Escribe tu primer mensaje: **"gasté 100 en comida"**.

Tu dinero, en orden, desde el primer día. 🚀