# 🏆 Versión Premium - FinanzasBot

Funciones avanzadas previstas para la **versión de pago**. Aportan el mayor valor a los usuarios pero requieren más trabajo de desarrollo.

> **Estado:** planificadas, no implementadas. Estas funcionalidades quedan reservadas para la versión premium.

---

## Comandos premium propuestos

### 🔍 `/buscar`
Busca transacciones por palabra clave o texto en la descripción.

- Ejemplo: `/buscar almuerzo` devuelve todas las transacciones que contengan "almuerzo".
- Soporte de filtros combinados: `/buscar comida hoy`, `/buscar salario mes`.
- Muestra cantidad, tipo, categoría, fecha y moneda de cada resultado.

**Esfuerzo:** bajo-medio (requiere agregar búsqueda por texto en ambos backends y UI de resultados).

---

### 📈 `/top`
Top 5 categorías de gasto del mes (o de un período elegido) con montos y porcentajes.

- Ejemplo: `/top`, `/top este mes`, `/top ayer`.
- Gráfico de barras con bloques (como los presupuestos).
- Posible extensión: comparativa vs el mes anterior.

**Esfuerzo:** medio (agregación por categoría + filtros de fecha, reutilizable desde `/resumen`).

---

### 📤 `/exportar`
Exporta todas las transacciones del usuario a un archivo **CSV** descargable.

- Columnas: fecha, tipo, cantidad, descripción, categoría, moneda.
- Se envía como documento de Telegram (`send_document`).
- Opciones futuras: exportar a Excel (XLSX) o solo un período.

**Esfuerzo:** medio (generación de archivo + descarga, más soporte para ambos backends).

---

### 🎯 `/meta`
Aporta dinero a una meta de ahorro y consulta su progreso.

- Ejemplo: `/meta 500` agrega $500 a la meta más próxima; si hay varias, el usuario elige con botones.
- `/meta` muestra el progreso actual de todas las metas.
- Al completar una meta, el bot felicita al usuario.
- Base de datos ya soporta `actualizar_meta_ahorro`.

**Esfuerzo:** medio (UI de selección de metas + validaciones).

---

## Funciones premium adicionales (roadmap)

### 🔁 Transacciones recurrentes / recordatorios
Registrar gastos periódicos (suscripciones, alquiler, servicios) y que el bot los registre automáticamente cada período o te recuerde pagarlos.

**Esfuerzo:** alto (requiere nuevo esquema de datos y un sistema de recordatorios/agendado).

---

### 🚨 Alertas inteligentes
- Aviso cuando una categoría supera el X% de su presupuesto.
- Aviso de balance bajo o en negativo.
- Notificaciones proactivas de metas alcanzadas.

**Esfuerzo:** medio-alto (lógica de umbrales + envío proactivo de mensajes).

---

### 📊 Estadísticas avanzadas
- Comparativas entre períodos (mes vs mes anterior).
- Tasa de ahorro, promedio diario de gasto, pronóstico de fin de mes.
- Distribución de gastos por moneda y por categoría.

**Esfuerzo:** alto (nuevo módulo de análisis + más lógica de agregación).

---

### 🧠 Asesor financiero con IA
Aprovechar el pipeline de IA existente para dar consejos personalizados:

- "¿En qué me estoy gastando demasiado este mes?"
- "¿Cuánto puedo ahorrar por mes según mis gastos actuales?"
- Recomendaciones de presupuesto por categoría.

**Esfuerzo:** alto (requiere prompts dedicados y análisis contextual del historial).

---

## Notas técnicas

- Todas las funciones deben funcionar con ambos backends (SQLite y Google Sheets).
- Los comandos premium deben registrarse en el menú de Telegram (`set_my_commands`) solo para usuarios con licencia activa.
- Gating: revisar en `handle_message`/`handle_callback_query` si el usuario tiene versión premium antes de ejecutar funciones premium.
