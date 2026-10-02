# 🐕 WATCHDOG GRID TRADING - Guía de Operación

## 📋 Resumen del Sistema

El **Watchdog Grid** es un sistema automático de monitoreo, reparación y optimización del Grid Trading Bot.

---

## ⚙️ Configuración Actual

### Cron Jobs Activos

| Job | Schedule | Descripción |
|-----|----------|-------------|
| **watchdog-grid** | `*/10 * * * *` | Monitoreo y auto-reparación cada 10 min |
| **update-grid-status-5min** | `*/5 * * * *` | Refresh dashboard cada 5 min |
| **daily-report-9am** | `0 9 * * *` | Reporte diario 9 AM |
| **heartbeat-memory-search** | `0 0,6,12,18 * * *` | Memory search 4x/día |
| **update-grid-status** | `0 * * * *` | Update hourly (legacy) |

### Umbrales de Decisión

```bash
MAX_ORDERS_AGE_HOURS=2          # Si órdenes >2h sin update → reiniciar
PORTFOLIO_THRESHOLD=5.0         # % desbalance para trigger rebalanceo
DASHBOARD_MAX_AGE_MIN=30        # Si dashboard >30min → forzar refresh
MIN_USDT_FOR_REBALANCE=100      # Mínimo USDT para rebalancear
```

---

## 🔍 ¿Qué Hace el Watchdog?

### Chequeos Automáticos (cada 10 min)

1. **✅ Proceso grid-trading-bot** → ¿Está corriendo?
2. **✅ Órdenes activas** → ¿Hay órdenes en el grid? ¿Actualizadas?
3. **✅ Portfolio balance** → ¿Dentro de threshold (5%)?
4. **✅ Dashboard fresco** → ¿Actualizado en últimos 30 min?

### Acciones Automáticas

| Problema Detectado | Acción del Watchdog |
|-------------------|---------------------|
| Proceso caído | 🔄 Reinicia grid bots |
| Sin órdenes (>2h) | 🔄 Reinicia grid bots |
| Portfolio desbalanceado (>5%) | 📊 Rebalancea (DRY RUN) |
| Dashboard desactualizado (>30min) | 📈 Actualiza dashboard |

### Notificaciones

El Watchdog **SOLO notifica al Jefe** cuando:
- ✅ Acciones significativas completadas (resumen)
- 🚨 Falla crítica que requiere atención manual

**NO notifica** cuando:
- ✅ Todo operativo (silencio = todo bien)

---

## 🛠️ Comandos Manuales

### Ver Status del Watchdog

```bash
# Último estado
cat /home/overgon/.openclaw/workspace/logs/watchdog-state.json

# Log completo
tail -50 /home/overgon/.openclaw/workspace/logs/watchdog-grid.log

# Ejecutar manualmente
/home/overgon/.openclaw/workspace/scripts/watchdog-grid.sh
```

### Reiniciar Grid Bots Manualmente

```bash
cd /home/overgon/.openclaw/workspace/crypto-bots
pkill -f "grid-trading-bot.py"
sleep 2
nohup python3 grid-trading-bot.py > ../logs/grid-trading.log 2>&1 &
```

### Rebalancear Portfolio (LIVE)

```bash
# DRY RUN (seguro, solo simulación)
python3 scripts/portfolio-rebalance.py --rebalance --dry-run

# LIVE (trades reales - usar con precaución)
python3 scripts/portfolio-rebalance.py --rebalance --live
```

### Forzar Actualización Dashboard

```bash
python3 scripts/update-grid-status.py
```

---

## 📊 Archivos Clave

| Archivo | Propósito |
|---------|-----------|
| `scripts/watchdog-grid.sh` | Script principal del watchdog |
| `logs/watchdog-grid.log` | Log de ejecuciones |
| `logs/watchdog-state.json` | Estado último chequeo |
| `dashboard/grid-status.json` | Status del grid (dashboard) |
| `logs/portfolio-rebalance.log` | Log de rebalanceos |

---

## 🎯 Estrategia de Decisión

### Prioridad de Acciones

1. **CRÍTICO:** Reiniciar bots si están caídos
2. **ALTO:** Rebalancear portfolio si >5% desviación
3. **MEDIO:** Actualizar dashboard si >30min

### Lógica de Rebalanceo

```
IF USDT_disponible >= $100 AND desviación > 5%:
    → Ejecutar rebalance (DRY RUN en watchdog)
ELSE:
    → Skip rebalance (log solo)
```

**Nota:** El watchdog usa **DRY RUN** por defecto para seguridad. Para rebalanceo LIVE, ejecutar manualmente con `--live`.

---

## 🚨 Troubleshooting

### Grid Bots No Inician

```bash
# Verificar logs
tail -100 /home/overgon/.openclaw/workspace/logs/grid-trading.log

# Verificar proceso
ps aux | grep grid-trading-bot

# Verificar credenciales
cat $HOME/.openclaw/secrets/binance.env | head -3
```

### Rebalanceo Falla

```bash
# Verificar USDT disponible
python3 scripts/portfolio-rebalance.py --status

# Verificar log
tail -50 /home/overgon/.openclaw/workspace/logs/portfolio-rebalance.log
```

### Dashboard No Actualiza

```bash
# Forzar update manual
python3 scripts/update-grid-status.py

# Verificar archivo
cat /home/overgon/.openclaw/workspace/dashboard/grid-status.json | python3 -m json.tool
```

---

## 📈 Métricas de Salud

### Estado Ideal

- ✅ Proceso grid-trading-bot corriendo
- ✅ Órdenes activas > 0
- ✅ Dashboard actualizado < 5 min
- ✅ Portfolio dentro de threshold (±5%)
- ✅ USDT disponible > $100

### Alertas Automáticas

El watchdog enviará Telegram si:
- ❌ Reinicio de bots falla repetidamente
- ❌ Rebalanceo falla por error de API
- ❌ Múltiples issues detectados simultáneamente

---

## 🔄 Historial de Acciones

```bash
# Ver acciones tomadas hoy
grep "ACTION:" /home/overgon/.openclaw/workspace/logs/watchdog-grid.log | tail -20

# Ver cantidad de acciones
cat /home/overgon/.openclaw/workspace/logs/watchdog-state.json | jq '.actions_today'
```

---

_Última actualización: 2026-06-16_  
_🐕 Perrobotillo Trading Bot - FASE 1 v2.1_
