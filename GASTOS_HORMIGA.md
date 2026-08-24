# Gastos Hormiga — Spec de referencia (pendiente de implementación)

> Fuente: `INSTRUCTIVO COMPLETO DE GASTOS HORMIGA.pdf` (v1.0, 13 páginas).
> Estado: **documentado, NO implementado**. El instructivo asume una arquitectura
> vieja; las secciones "Adaptación v2.14" indican dónde encaja en el código actual.

## Objetivo
Detectar **gastos hormiga**: pequeños gastos recurrentes que individualmente parecen
insignificantes pero se acumulan (café, snacks, transporte corto, suscripciones,
comida rápida).

## Valores por defecto (por usuario)
- Umbral monetario: **$5.00 USD** (gastos ≤ este monto son candidatos).
- Frecuencia mínima: **3 veces/semana** en la misma categoría.
- Categorías auto: `café,snacks,transporte,suscripciones,comida rápida`.
- Moneda base del umbral: **USD**.
- Notificaciones: **activadas**.

## Criterios de detección (multicriterio)
1. **Monto** ≤ umbral (con conversión multi-moneda usando factores estáticos).
2. **Categoría** en la lista activa, o match por keywords.
3. **Frecuencia** (opcional, más costoso): ≥ `frecuencia_minima` en últimos 7 días.

### Factores de conversión (estáticos, del instructivo)
```
USD 1.0 | EUR 1.08 | CUP 0.0417 | MLC 1.0
MXN 0.058 | COP 0.00025 | ARS 0.0011 | CLP 0.0011
```

### Keywords por categoría (default)
- café: café, cafe, starbucks, coffee, capuchino
- snacks: snack, galleta, chocolate, dulce, golosina
- transporte: taxi, uber, didi, cabify, bici, moto, bus
- suscripciones: netflix, spotify, youtube premium, amazon prime
- comida rápida: mcdonalds, burger king, pizza, hamburguesa, delivery

## Persistencia
Dos tablas (en Sheets: `config_gastos_hormiga`, `gastos_hormiga`; en SQLite: igual):

`config_gastos_hormiga`: id, usuario_id, umbral_base, umbral_moneda,
frecuencia_minima, categorias_auto, notificaciones_activas, created_at, updated_at.

`gastos_hormiga`: id, transaccion_id, usuario_id, categoria, monto, moneda_id,
fecha, detectado_en, es_recurrente.

Funciones DB: `obtener_config_gastos_hormiga` (default si no existe),
`guardar_config_gastos_hormiga`, `registrar_gasto_hormiga`,
`obtener_gastos_hormiga(usuario_id, dias=30)`,
`obtener_estadisticas_gastos_hormiga(usuario_id, dias=30)`.

## Comandos
- `/gastos_hormiga` → reporte: total, nº transacciones, por categoría, sugerencia de ahorro.
- `/config_hormiga [umbral N MONEDA | categorías a,b,c | mostrar]` → config personalizada.

## Adaptación a la arquitectura actual (v2.14)
- **DB**: el instructivo edita `database_gsheets.py` directo. Hoy hay proxy `database.py`
  → `database_sqlite.py` / `database_gsheets.py` con 16 funciones públicas idénticas.
  Añadir las 5 funciones en AMBOS backends y exportarlas en `database.py`.
  Esquema: `crear_tablas()` en sqlite debe crear las 2 tablas; gsheets debe crearlas
  en `_ensure_sheets()`.
- **Lógica**: `detectar_gasto_hormiga` / `_es_gasto_hormiga_por_frecuencia` van en
  `knowledge.py`. El hook de detección debe dispararse tras registrar un gasto
  (en `_procesar_gasto` de knowledge.py y en la ruta EN de `handlers.py`).
- **Comandos**: registrar en `main.py` (`COMANDOS_MENU` + `CommandHandler`) y en
  `handlers.py`. Respetar el patrón actual de `reply_markup` inline (no ReplyKeyboard).
- **Menú**: el instructivo usa `teclado_principal()` de 6 botones. Hoy `menus.py` es
  builder puro de 7 secciones con `procesar_callback`. Añadir sección "🐜 Gastos Hormiga"
  como botón del `teclado_principal()` (7→8) y su `menu_gastos_hormiga` en `menus.py`
  + dispatcher en `procesar_callback`.
- **Notificación**: al detectar gasto hormiga, anexar 💡 al mensaje de confirmación del
  gasto (o al resumen), respetando `notificaciones_activas` del usuario.
- **Conversión de moneda**: los factores del instructivo son estáticos; hoy el bot ya
  tiene `monedas`/tasas. Evaluar usar tasas reales en vez de constantes hardcodeadas.

## Flujo de ejemplo (esperado)
```
U: Gasté $3 en café
Bot: 🐜 Gasto registrado: $3.00 en café
     💡 ¡Gasto hormiga detectado! Este pequeño gasto puede sumar mucho.

U: /gastos_hormiga
Bot: 🐜 Tus gastos hormiga (últimos 30 días)
     💰 Total: $45.20 | 📋 15 transacciones
     📊 Por categoría: • café: $22.50 (8) • transporte: $15.00 (5)
     💡 Sugerencia: Podrías ahorrar $36.16/mes reduciendo un 80%.
```

## Archivos a modificar (mapeo v2.14)
- `database.py` + `database_sqlite.py` + `database_gsheets.py` → tablas + 5 funciones.
- `knowledge.py` → lógica de detección + handlers de reporte/config + hook en `_procesar_gasto`.
- `handlers.py` → `consultar_gastos_hormiga`, `configurar_gastos_hormiga`, callback.
- `menus.py` → sección 🐜 + `procesar_callback` entry.
- `main.py` → `COMANDOS_MENU` + registro de handlers.
