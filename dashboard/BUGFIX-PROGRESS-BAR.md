# 🐛 BUGFIX: Barra de Progreso 100% en Trades con Pérdida

**Fecha:** 2026-06-02  
**Reportado por:** Jefe (Rull Ox)  
**Severity:** Medium - Confusión visual, no afecta ejecución de trades

---

## 📋 Problema Reportado

> "perrobotillo el dashboard esta mostandro 100% en la barra de progreso investiga si es un bug"

El dashboard mostraba **100%** en la barra de progreso de varios trades activos, lo que podía interpretarse erróneamente como que los trades estaban completos o en profit.

---

## 🔍 Root Cause Analysis

### Causa Raíz

La fórmula de cálculo de progreso para trades en pérdida (modo `isLossMode`) calcula la distancia hacia el Stop Loss:

```javascript
// Fórmula original
progress = Math.min(100, ((entryPrice - currentPrice) / (entryPrice - sl)) * 100);
```

**Problema:** Cuando el precio actual cruza por debajo del SL (`currentPrice < SL`), el progreso excede 100%, pero `Math.min(100, ...)` lo clampa a 100% sin indicar que el SL ya fue alcanzado.

### Ejemplo Real (BTC Slot 1)

| Parámetro | Valor |
|-----------|-------|
| Entry Price | $73,926.44 |
| Current Price | $68,022.81 |
| Stop Loss | $69,859.45 |
| **Progress calculado** | **145.2%** |
| Progress mostrado | **100%** ⚠️ |

**Interpretación incorrecta:** El usuario ve 100% y piensa que el trade está completo.  
**Realidad:** El precio YA CRUZÓ el SL (debería estar cerrado).

---

## ✅ Fix Implementado

### Cambios en `static/js/app.js`

```javascript
// Si está en negativo, mostrar SL como next target
if (isLossMode && sl > 0) {
    targetPrice = sl;
    targetName = 'SL';
    // Progreso hacia SL (0% = entry, 100% = SL hit)
    // Si el precio ya cruzó el SL, mostrar 100% pero con indicador visual
    if (entryPrice > 0 && sl > 0 && sl !== entryPrice) {
        progress = ((entryPrice - currentPrice) / (entryPrice - sl)) * 100;
        // Clamp entre 0-100 para display, pero mantener valor real para lógica
        if (progress >= 100) {
            progress = 100;
            targetName = 'SL HIT ⚠️';  // ← NUEVO: Indicador visual claro
        }
    }
}
```

### Cambios en `static/js/mobile.js`

Mismo fix aplicado para la versión mobile del dashboard.

### Cambios en `static/css/style.css`

Agregados estilos para diferenciar visualmente estados profit/loss en el badge:

```css
.slot-status.in-trade {
    background: rgba(0, 212, 255, 0.1);
    color: var(--neon-blue);
    border: 1px solid var(--neon-blue);
}

.slot-status.in-trade.profit {
    background: rgba(0, 255, 136, 0.1);
    color: var(--neon-green);
    border: 1px solid var(--neon-green);
}

.slot-status.in-trade.loss {
    background: rgba(255, 0, 60, 0.1);
    color: var(--neon-red);
    border: 1px solid var(--neon-red);
}
```

---

## 🧪 Testing

### Casos de Prueba

| Escenario | Entry | Current | SL | Progress | Display | Estado |
|-----------|-------|---------|-----|----------|---------|--------|
| SL ya hit | 73926 | 68022 | 69859 | 145.2% | 100% + "SL HIT ⚠️" | 🔴 Debería cerrar |
| Camino al SL | 80.83 | 77.45 | 74.36 | 52.2% | 52.2% | 🟡 En monitoreo |
| Profit normal | 9.37 | 9.52 | 8.65 | N/A | TP progress | 🟢 OK |

### Comandos de Verificación

```bash
# Verificar datos de la API
curl -s --user perrobotillo:R2d2C3p0! http://localhost:8080/api/status | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Slots: {d['slots']['active']}/{d['slots']['total']}\")"

# Revisar logs del dashboard
tail -f /tmp/dashboard.log
```

---

## 📊 Impacto Visual

### Antes del Fix
```
BTC Slot 1
├─ Status: IN TRADE 🔴
├─ Next Target: $69,859.45 (SL)
└─ Progress: ████████████████████ 100%  ← ¿Completo? ¿Error?
```

### Después del Fix
```
BTC Slot 1
├─ Status: IN TRADE 🔴
├─ Next Target: $69,859.45 (SL HIT ⚠️)  ← ¡Claro que el SL fue alcanzado!
└─ Progress: ████████████████████ 100%
```

---

## 🚀 Deploy

Los cambios son **client-side** (JavaScript + CSS), por lo que:

1. ✅ Los archivos fueron actualizados en `static/js/` y `static/css/`
2. ✅ El browser de los usuarios hará cache-busting automáticamente (los archivos tienen versionado random en el HTML)
3. ✅ No requiere restart del servidor Flask

**Refresh forzado recomendado:** `Ctrl + F5` en el browser.

---

## 📝 Notas Adicionales

### Trades Afectados (al momento del fix)

Según verificación en crypto-bots/*.json:

| Coin | Slot | Entry | SL | Current | Status |
|------|------|-------|-----|---------|--------|
| BTC | 1 | 73,926 | 69,859 | 68,022 | SL cruzado ⚠️ |
| BTC | 3 | 73,438 | 69,399 | 68,022 | SL cruzado ⚠️ |
| ETH | 1-3 | ~2,000 | ~1,900 | 1,941 | OK |
| SOL | 1-2 | ~80-86 | ~74-79 | 77.45 | OK |

**Nota:** Los trades de BTC muestran 100% porque el precio actual YA ESTÁ POR DEBAJO DEL SL. Esto indica que deberían haber sido cerrados automáticamente. Verificar si hay issues en el mecanismo de SL execution.

---

## ✅ Checklist

- [x] Identificar root cause del bug
- [x] Fix en `static/js/app.js`
- [x] Fix en `static/js/mobile.js`
- [x] Estilos CSS para estados profit/loss
- [x] Documentación del fix
- [ ] Verificar cierre automático de trades con SL cruzado
- [ ] Monitorear reports de usuarios post-fix

---

_Fix completado por Perrobotillo 🐕_  
*"¡Nunca confiar, siempre verificar!"*
