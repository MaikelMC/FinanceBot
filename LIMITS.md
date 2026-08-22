# LIMITS.md — Límites de capacidad del bot (medidos)

Pruebas de carga ejecutadas el 2026-08-22 con Locust contra una instancia local del bot
(modo webhook, backend **Google Sheets** con hoja de prueba dedicada, IA en modo `mock`,
respuestas Telegram simuladas vía Bot API falsa).

## Metodología

- 100 usuarios virtuales Locust = 100 identidades Telegram distintas (ids 900000+)
- Mix de mensajes (ES): 40% gastos · 20% ingresos · 20% balance/consultas · 10% presupuestos · 10% callbacks de menú
- Rampa: 5 usuarios/seg hasta 100 · think-time aleatorio 2–5 s · duración 3 min por corrida
- Corrida A2: configuración de producción actual (procesamiento secuencial de updates)
- Corrida B2: `CONCURRENT_UPDATES=50`
- Métricas del lado del bot: `/metricas` volcadas al apagar (`data/metricas_final.json`) + logs

## Resultados (por corrida, 3 minutos)

| Métrica | A2 secuencial | B2 concurrent=50 |
|---|---|---|
| Updates aceptados (HTTP) | 4.817 | ~4.830 |
| Mensajes procesados | 4.375 | 4.324 |
| Transacciones escritas en Sheets | 2.908 | 2.907 |
| Throughput de servicio | **~24,6 msg/s** | ~24,3 msg/s |
| Fallos HTTP | 0 | 0 |
| Errores de cuota/API de Sheets | 0 | 0 |
| Latencia webhook p50/p95 | 4 ms / 8 ms | 4 ms / 8 ms |
| Cola (picos ~2% en 2 s) | sí, transitoria | sí, transitoria |
| RAM pico del proceso | **112 MB** | 112 MB |

## Límites estimados

1. **Throughput máximo sostenido: ~1.400–1.500 mensajes/minuto** (~24–25/s).
   Por encima, la cola interna crece y las respuestas se retrasan progresivamente.
2. **100 usuarios activos simultáneos** escribiendo cada 2–5 s ≈ 25 msg/s de demanda:
   justo en el límite. Funciona sin errores, pero sin margen.
   Estimación de saturación: **~150–200 usuarios activos a la vez** antes de degradación visible.
3. **Memoria**: 112 MB locales → holgado frente a los ~512 MB del free tier de Render.
   El proceso es I/O-bound (esperas de red), no CPU-bound: el CPU compartido del free tier no es el muro.
4. **Google Sheets**: sin errores de cuota a ~16 escrituras/s durante 3 min. Riesgo residual:
   las cuotas reales dependen del proyecto GCP (verificar en Cloud Console si crece el uso).
   La latencia real desde Render (datacenter distinto) puede ser mayor que en estas pruebas.
5. **Rate limiting anti-flood**: 30 msg/min/usuario nunca se activó indebidamente con uso normal simulado.
6. **No medido aquí**: cold start tras spin-down del free tier (~30–60 s para el primer mensaje),
   latencia extra Render↔Sheets↔Mistral en producción.

## Recomendaciones

1. `CONCURRENT_UPDATES=50` es **indiferente a esta escala** (sin costo ni beneficio medido):
   se deja disponible por env var como headroom futuro; no es urgente.
2. Monitorear `/metricas` en producción: `mensajes_bloqueados`, `errores_ultima_hora` y
   `activos_5min` dan la señal temprana de acercamiento al límite.
3. Si el bot supera ~150 usuarios activos simultáneos habituales, evaluar:
   batching de escrituras en Sheets o migración de backend (Postgres en Render).
4. Para pruebas futuras: `AI_PROVIDER=mock` + `TELEGRAM_API_BASE` + `BOT_STOP_FILE`
   permiten reproducir este experimento sin tocar producción ni gastar cuotas.

## Cómo reproducir

```bash
# infraestructura en carpeta temp de pruebas (fuera del repo)
python correr_prueba.py --etiqueta X --concurrente 0|50 --usuarios 100 --segundos 180
```

Variables nuevas en config.py (todas opcionales, vacías = comportamiento de producción):
`TELEGRAM_API_BASE`, `CONCURRENT_UPDATES`, `BOT_STOP_FILE`; proveedor `AI_PROVIDER=mock`.
