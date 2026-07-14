# 🚨 BUG CRÍTICO: Auto-Reset de Slots Fallido al Tocar SL

**Fecha:** 2026-06-23 23:16 CST  
**Reportado por:** Perrobotillo 🐕  
**Prioridad:** 🔴 ALTA  
**Sistema:** Perrobotillo Trading Bot v2.1 - Slots Trading

---

## Descripción

Los slots que tocan Stop Loss no se están reseteando automáticamente a estado READY. El dashboard muestra **'SL HIT'** con alertas 🚨 y **Distance to SL: 100%**, pero los slots permanecen en estado 'IN TRADE' en lugar de cerrarse y pasar a READY.

---

## Evidencia Detectada (2026-06-23 23:12 CST)

### Slots Afectados:

| Moneda | Slot | Entry Price | Current Price | P&L | Status Dashboard | Status API |
|--------|------|-------------|---------------|-----|------------------|------------|
| ETH | 1 | $1748.58 | $1671.15 | -$0.21 (-4.43%) | 🔴 SL HIT | 🟢 ACTIVE |
| ETH | 2 | $1748.45 | $1671.15 | -$0.04 (-4.42%) | 🔴 SL HIT | 🟢 ACTIVE |
| SOL | 1 | $74.05 | $69.75 | -$0.39 (-5.81%) | 🔴 SL HIT | 🟢 ACTIVE |
| SOL | 2 | $73.89 | $69.75 | -$0.12 (-5.60%) | 🔴 SL HIT | 🟢 ACTIVE |

**Total pérdidas sin resetear:** ~$0.76 USDT  
**Slots bloqueados:** 4/21 (19% del capacity)

---

## Comportamiento Esperado

Cuando un slot toca SL:
1. ✅ La posición debe cerrarse automáticamente en Binance
2. ✅ El slot debe pasar a estado READY inmediatamente
3. ✅ El P&L debe registrarse en el historial
4. ✅ El dashboard debe mostrar slot disponible para nueva entrada

---

## Comportamiento Actual

1. ✅ La posición se cierra en Binance (SL HIT confirmado en dashboard)
2. ❌ El slot NO pasa a READY (permanece IN TRADE)
3. ⚠️ El P&L se registra pero el slot queda 'zombie'
4. ❌ El dashboard muestra inconsistencia entre UI y API (`/api/status`)

---

## Posibles Causas

- Bug en el script de auto-reset después de SL
- Problema de sincronización entre Binance API y estado local
- El webhook de cierre por SL no está triggerando el reset
- Race condition entre el bot principal y el watchdog
- Estado en memoria no se persiste después del SL

---

## Impacto Operativo

- **Slots bloqueados:** 4/21 (19% del capacity perdido)
- **Capital inmovilizado:** No puede reutilizarse para nuevas entradas
- **Risk:** Si el mercado rebota, perdemos oportunidades de entrada
- **Data integrity:** API status vs Dashboard visual mismatch
- **Daily loss tracking:** Puede estar subestimado si los slots no se cuentan como cerrados

---

## Pasos para Reproducir

1. Abrir posición LONG en slot con TP1/TP2/TP3 y SL definido
2. Esperar que el precio de mercado toque el Stop Loss
3. Verificar dashboard visual: muestra 'SL HIT' 🚨 y Distance to SL: 100%
4. Verificar API `/api/status`: slot sigue mostrando ACTIVE
5. Verificar archivo de estado del slot: no se actualiza a READY
6. Slot queda bloqueado indefinidamente sin reset automático

---

## Slots Afectados en Este Incidente

### ETH Slot 1
- Entry: $1748.58
- SL Triggered: ~$1671.15
- P&L: -$0.21 USDT
- Status: IN TRADE (debería ser READY)

### ETH Slot 2
- Entry: $1748.45
- SL Triggered: ~$1671.15
- P&L: -$0.04 USDT
- Status: IN TRADE (debería ser READY)

### SOL Slot 1
- Entry: $74.05
- SL Triggered: ~$69.75
- P&L: -$0.39 USDT
- Status: IN TRADE (debería ser READY)

### SOL Slot 2
- Entry: $73.89
- SL Triggered: ~$69.75
- P&L: -$0.12 USDT
- Status: IN TRADE (debería ser READY)

---

## Archivos para Investigar

```bash
# Scripts relevantes
/home/overgon/.openclaw/workspace/scripts/crypto-trade-moneda-v3-slots.sh
/home/overgon/.openclaw/workspace/scripts/update-grid-status.py
/home/overgon/.openclaw/workspace/scripts/watchdog-grid.sh

# Logs
/home/overgon/.openclaw/workspace/logs/grid-trading.log
/home/overgon/.openclaw/workspace/logs/bot-main.log
/home/overgon/.openclaw/workspace/crypto-bots/logs/auto-trade.log

# Estado actual
/home/overgon/.openclaw/workspace/state/*.json
```

---

## Workaround Temporal (Manual)

Mientras se fixea el bug, el Jefe puede:

1. **Identificar slots con SL HIT** en el dashboard
2. **Reset manual** vía comando o interfaz (si existe)
3. **Verificar** que el slot pase a READY
4. **Monitorear** que nuevas posiciones funcionen normal

---

## Fix Sugerido

1. Agregar chequeo periódico de posiciones cerradas por SL en Binance API
2. Comparar con estado local de slots
3. Si posición no existe en Binance pero slot sigue ACTIVE → forzar reset a READY
4. Loggear el evento como "AUTO_RESET_BY_SL"
5. Notificar al Jefe via Telegram si hay auto-reset

---

## Adjuntos

- Screenshot del dashboard (Telegram message #6920, 2026-06-23 23:12 CST)
- Muestra ETH y SOL slots con "SL HIT" 🚨🚨🚨
- Distance to SL: 100% en todos los casos

---

## Link para Crear Issue en GitHub

```
https://github.com/overgon/perrobotillo-sync/issues/new
```

**Copiar este contenido completo en el issue.**

---

**Estado:** 📝 Documentado, pendiente de crear issue en GitHub  
**Auth requerida:** gh auth login (GitHub CLI no autenticado)
