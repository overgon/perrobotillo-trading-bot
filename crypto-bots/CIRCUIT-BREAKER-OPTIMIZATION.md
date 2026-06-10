# Circuit Breaker Dashboard - Optimización 2026-06-10

## 🎯 Problema Original
- El countdown del circuit breaker NUNCA funcionó en el dashboard principal
- Solo existía en `test-circuit-breaker.html` (archivo de prueba aislado)
- Había un cron job actualizando el JSON cada 5 min (luego 1 hora) innecesariamente

## ✅ Solución Implementada (Opción B)

### Cambios Realizados:

1. **Eliminado cron job del circuit breaker**
   - Antes: `0 * * * *` (cada hora)
   - Ahora: **On-demand** (solo cuando se activa/desactiva)

2. **Simplificado `update-circuit-breaker-countdown.py`**
   - Removido: Countdown, progreso, tiempo restante
   - Mantenido: Status básico (activo/inactivo, causa, pérdidas)
   - El dashboard hace el countdown en el navegador si es necesario

3. **Modificado `global-circuit-breaker.sh`**
   - Ahora actualiza `dashboard-circuit-breaker-status.json` **on-demand** cuando:
     - ✅ Se activa un circuit breaker (cualquier regla)
     - ✅ Expira el pause y se reanuda trading
   - Trigger automático desde el bot de trading

4. **Dashboard funciona correctamente**
   - Lee el status JSON via `/api/status` endpoint
   - Aplica "emergency mode" visual cuando CB está activo
   - Muestra slots como "PAUSED (CB)" 🟠 en modo emergencia

## 📊 Impacto

| Métrica | Antes | Después | Ahorro |
|---------|-------|---------|--------|
| Ejecuciones/día | 24 (cada hora) | **0** | 100% |
| Uso de Ollama | ~1,560 llamadas/mes | **0** | $0.00 |
| CPU/RAM | Python cada hora | Solo on-demand | Mínimo |

## 🔍 ¿Cómo Funciona Ahora?

### Cuando NO hay circuit breaker:
```
Dashboard → Lee JSON → Muestra "Trading Normal"
(Sin ejecuciones de fondo, sin cron, sin uso de recursos)
```

### Cuando SE ACTIVA circuit breaker:
```
Bot Trading → global-circuit-breaker.sh → Detecta losses
    ↓
Crea global-pause-flag.json
    ↓
Actualiza dashboard-circuit-breaker-status.json (on-demand)
    ↓
Dashboard → Próximo refresh → Muestra "🔴 CIRCUIT BREAKER ON"
```

### Cuando EXPIRA circuit breaker:
```
global-circuit-breaker.sh → Verifica pause expirado
    ↓
Elimina global-pause-flag.json
    ↓
Actualiza dashboard-circuit-breaker-status.json → "Trading Reanudado"
    ↓
Dashboard → Próximo refresh → Vuelve a normal
```

## 🛡️ Seguridad

El dashboard **SÍ respeta** el circuit breaker:
- Slots muestran "PAUSED (CB)" 🟠 cuando está activo
- Solo permite operaciones de gestión (SL/TP/Emergency Close)
- Bloquea nuevas entradas y DCA

## 📝 Archivos Modificados

1. `/home/overgon/.openclaw/workspace/crypto-bots/global-circuit-breaker.sh`
   - Agregado: Actualización on-demand del dashboard status
   
2. `/home/overgon/.openclaw/workspace/crypto-bots/update-circuit-breaker-countdown.py`
   - Simplificado: Sin countdown, solo status básico
   
3. Crontab del sistema
   - Removido: Circuit breaker update cron

## ✅ Verificación Final

```bash
# Verificar que no hay cron del circuit breaker
crontab -l | grep circuit-breaker  # Debe estar vacío

# Verificar status actual
cat /home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json

# Probar activación manual (simular CB)
echo '{"pause_until":"2026-06-11 11:00:00","triggered_by":"test","losses_24h":4}' > /home/overgon/.openclaw/workspace/crypto-bots/global-pause-flag.json
/home/overgon/.openclaw/workspace/crypto-bots/update-circuit-breaker-countdown.py
cat /home/overgon/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json
rm /home/overgon/.openclaw/workspace/crypto-bots/global-pause-flag.json
```

---
_Optimizado por Perrobotillo 🐕 - 2026-06-10_
