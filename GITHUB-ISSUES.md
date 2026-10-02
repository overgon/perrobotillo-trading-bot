# 📋 GitHub Issues - Perrobotillo Trading Bot

## Issues Creados - 2026-05-30

### ✅ Issue #1: Sistema de Sonidos TP/SL

**Título:** `🔔 [FEATURE] Sistema de Sonidos para TP Hits y Stop Loss`

**Descripción:**
Se implementó un sistema de notificaciones sonoras para el dashboard que reproduce:
- 💰 Caja registradora cuando un slot alcanza TP (TP1/TP2/TP3)
- 🛑 Sonido "loser" cuando un slot toca el Stop Loss

**Archivos Modificados:**
- `dashboard/static/js/app.js` - Lógica de sonidos + audio unlock
- `dashboard/static/sounds/stop-loss.mp3` - Nuevo archivo de audio
- `dashboard/templates/index.html` - Elementos audio HTML5

**Características:**
- Detección automática cada 5 segundos vía `tp-notifications.json`
- Notificaciones visuales en esquina superior derecha
- Audio unlock con primer click del usuario (browser policy)
- Prevención de reproducción múltiple (Set en memoria)

**Testing:**
- ✅ TP HIT → Caja registradora
- ✅ STOP LOSS → Sonido loser
- ✅ Sin reproducción duplicada
- ✅ Compatible con Chrome/Firefox/Edge

---

### ⚠️ Issue #2: LOT_SIZE Filter Failure

**Título:** `🐛 [BUG] Ventas TP fallan por LOT_SIZE incorrecto`

**Descripción:**
Las ventas automáticas de TP están fallando con error `-1013: Filter failure: LOT_SIZE` porque las cantidades no respetan el stepSize de Binance.

**Síntomas:**
```
❌ TP2 venta falló: 
{"code":-1013,"msg":"Filter failure: LOT_SIZE"}
```

**Caso Documentado:**
- LINK Slot 3 TP2
- Cantidad enviada: 1.92400000 (INVÁLIDO)
- StepSize LINK: 0.01 (solo 2 decimales)
- Cantidad correcta: 1.92 (VÁLIDO)

**Root Cause:**
La función `format_quantity()` existe pero posiblemente no se está aplicando en el flujo de ventas TP.

**Workaround Aplicado:**
Venta manual con cantidad formateada correctamente.

**Fix Pendiente:**
- Revisar que TODAS las ventas usen `format_quantity()`
- Agregar validación pre-envío
- Loggear cantidad raw vs formateada

**Coins Afectadas:**
Todas, pero cada una tiene diferente stepSize:
- LINK: 0.01 (2 decimales)
- SOL: 0.01 (2 decimales)
- BTC: 0.00001 (5 decimales)
- ETH: 0.0001 (4 decimales)
- etc.

---

### 🔧 Issue #3: TypeError en Dashboard

**Título:** `🐛 [FIX] TypeError: can't access property "catch"`

**Descripción:**
Error en consola del navegador al reproducir sonidos.

**Error:**
```
TypeError: can't access property "catch", n() is undefined
    at index.js:1:1108
```

**Causa:**
`audio.play()` retorna `undefined` en algunos navegadores cuando el audio está bloqueado.

**Fix Aplicado:**
```javascript
const playPromise = cashRegisterSound.play();
if (playPromise) {
    playPromise.then(...).catch(...);
}
```

**Estado:** ✅ Resuelto permanentemente

---

## 📊 Resumen:

| Issue | Tipo | Estado | Prioridad |
|-------|------|--------|-----------|
| #1 Sonidos TP/SL | Feature | ✅ Completado | Alta |
| #2 LOT_SIZE Bug | Bug | ⚠️ Workaround | Crítica |
| #3 TypeError | Bug | ✅ Fixeado | Media |

## 🔗 Links a Archivos:

- Cambios completos: `CHANGES.md`
- Bugfix LOT_SIZE: `BUGFIX-LOT-SIZE.md`
- Este archivo: `GITHUB-ISSUES.md`

---

**Nota:** Estos documentos sirven como referencia para crear los issues reales en GitHub cuando sea necesario.
