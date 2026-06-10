# CHEATSHEET.md - Cambios Junio 10, 2026

## 🎯 Resumen de Actualización

### ✅ Agregados (NUEVOS)

1. **Sección: Circuit Breaker y Auto-Heal**
   - `global-circuit-breaker.sh` - Protección contra pérdidas catastróficas
   - `slot-healbot.py` - Reparación automática de slots
   - `update-circuit-breaker-countdown.py` - Status dashboard (optimizado)

2. **Sección: Optimización Junio 2026**
   - Explicación del ahorro de LLM (~1,560 llamadas/mes)
   - Cero uso de LLM para tareas automáticas

3. **ML Validator**
   - Integrado en auto-adjust-strategy.sh
   - Override con >80% confianza

4. **Archivos clave actualizados**
   - global-pause-flag.json
   - dashboard-circuit-breaker-status.json
   - ml/market-predictions.json

5. **Logs nuevos**
   - auto-heal.log
   - auto-adjust.log (con ML validation)

### ❌ Removidos/Optimizados

1. **Circuit Breaker Cron**
   - Antes: Cada hora (cron job)
   - Ahora: On-demand (trigger cuando se activa/desactiva)

2. **ML Validator Path**
   - Antes: Buscaba en `lib/ml-market-validator.sh` (error)
   - Ahora: `${SCRIPT_DIR}/ml-market-validator.sh` (correcto)

3. **Auto-Adjust Strategy**
   - Restaurado al crontab (se había perdido en edición anterior)
   - Fix: ML validator path corregido

### 📊 Tabla de Cron Jobs Actualizada

- Total: ~27 cron jobs activos
- Columna "Uso LLM" agregada
- Circuit breaker removido de la lista
- Slot healbot agregado (*/10 * * * *)

### 🔄 Estadísticas Actualizadas

- Fecha: Junio 10, 2026 (antes Mayo 11, 2026)
- Portfolio: ~$500 USDT (FASE 1 v2.1)
- Estrategia: BEAR (auto-adjust 8 AM)
- Circuit Breaker: Activo
- Optimización LLM: Destacada

### 📝 Comandos Rápidos Agregados

```bash
# Circuit Breaker status
cat dashboard-circuit-breaker-status.json | jq .

# Global pause flag
cat global-pause-flag.json 2>/dev/null || echo "No active"

# ML predictions
cat ml/market-predictions.json | jq '.predictions.BTC'
```

---

## 📈 Impacto de la Optimización

| Métrica | Antes | Después | Ahorro |
|---------|-------|---------|--------|
| Ejecuciones CB/día | 24 (cron) | 0 (on-demand) | 100% |
| Uso Ollama/mes | ~1,560 llamadas | 0 | $0.00 |
| CPU/RAM CB | Python cada hora | Solo on-demand | Mínimo |
| Healbot | N/A | Python cada 10 min | Sin LLM |

---

## 🔍 Verificación

```bash
# Ver crontab actual
crontab -l | grep -E "slot-healbot|auto-adjust"

# Debe mostrar:
# */10 * * * * run-slot-healbot.sh
# 0 */6 * * * auto-adjust-strategy.sh
```

---

_Generado por Perrobotillo 🐕_  
*"¡Nunca confiar, siempre verificar!"*
