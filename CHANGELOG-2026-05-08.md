# 🐕 CHANGELOG - 2026-05-08

**Perrobotillo Trading Bot - Session Log**

---

## 📊 RESUMEN DEL DÍA

| Métrica | Valor |
|---------|-------|
| **Trades Totales** | 48 |
| **Win Rate** | 100% 🏆 |
| **Net P&L** | +$145.95 USDT |
| **Bugs Arreglados** | 10 ✅ |
| **Features Nuevas** | 8 ✅ |
| **Tests Creados** | 3 ✅ |

---

## 🐛 BUGS CRÍTICOS ARREGLADOS

### **1. 24H P&L Siempre en $0** ❌→✅

**Problema:**
```python
# ANTES (BUG):
pnl = data.get('pnl', 0)  # Campo incorrecto
```

**Solución:**
```python
# AHORA (FIX):
pnl = data.get('netProfitUSDT', 0)  # Campo correcto
```

**Impacto:** Dashboard ahora muestra 24H P&L real ($2.76)

**Archivos:**
- `dashboard/app.py` - Función `get_daily_pnl()`

---

### **2. TP1/TP2/TP3 P&L Vacío en Histórico** ❌→✅

**Problema:**
```bash
# ANTES (BUG):
log_trade_to_history "$slot_id" "TP2" "$entry" "$current_price" "$sell_qty" "$pnl"
#                                                    ↑
#                                         $pnl estaba VACÍO
```

**Causa:** El P&L se calculaba 12 líneas DESPUÉS de llamar a `log_trade_to_history()`

**Solución:**
```bash
# AHORA (FIX):
local pnl=$(awk -v e="$entry" -v x="$current_price" -v q="$sell_qty" -v f="$fee_buy" 'BEGIN {...}')
log_trade_to_history "$slot_id" "TP2" "$entry" "$current_price" "$sell_qty" "$pnl"
#                                                    ↑
#                                         $pnl ahora calculado ✅
```

**Impacto:** Todos los trades futuros guardan P&L correctamente

**Archivos:**
- `crypto-trade-moneda-v3-slots.sh` - TP1, TP2, TP3 sections

---

### **3. SL (Stop Loss) No Guardaba en Histórico** ❌→✅

**Problema:**
```bash
# ANTES (BUG):
update_pnl_after_close "$slot_id" "SL" ...
# ❌ NO llamaba a log_trade_to_history()
```

**Solución:**
```bash
# AHORA (FIX):
local pnl=$(awk -v e="$entry" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {...}')
log_trade_to_history "$slot_id" "SL" "$entry" "$exit_price" "$quantity" "$pnl"
update_pnl_after_close "$slot_id" "SL" ...
```

**Impacto:** SL ahora se guarda automáticamente en trade-history.json

**Archivos:**
- `crypto-trade-moneda-v3-slots.sh` - Línea ~1282

---

### **4. TRAILING Stop No Guardaba en Histórico** ❌→✅

**Problema:**
```bash
# ANTES (BUG):
update_pnl_after_close "$slot_id" "TRAILING" ...
# ❌ NO llamaba a log_trade_to_history()
```

**Solución:**
```bash
# AHORA (FIX):
local pnl=$(awk -v e="$entry" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {...}')
log_trade_to_history "$slot_id" "TRAILING" "$entry" "$exit_price" "$quantity" "$pnl"
update_pnl_after_close "$slot_id" "TRAILING" ...
```

**Impacto:** TRAILING ahora se guarda automáticamente

**Archivos:**
- `crypto-trade-moneda-v3-slots.sh` - Línea ~1328

---

### **5. TP3 Insufficient Balance (BUG-042)** ❌→✅

**Problema:**
```bash
# ANTES (BUG):
sell_qty=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.20}')
# Intentaba vender 20% pero quedaba 30% después de TP1+TP2
# Binance rechazaba: "Account has insufficient balance"
```

**Causa:** TP1 vendió 35%, TP2 vendió 30%, queda 35%. TP3 intentaba vender 20% (incorrecto).

**Solución:**
```bash
# AHORA (FIX):
if [ "$tp2_done" = "true" ]; then
    # TP1 + TP2 completados → vender 30% restante (deja 5% acumulado)
    sell_qty=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.30}')
else
    # Solo TP1 completado → vender 65% restante (deja 5% acumulado)
    sell_qty=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.65}')
fi
```

**Impacto:** TP3 ya no falla, slots se cierran correctamente

**Archivos:**
- `crypto-trade-moneda-v3-slots.sh` - Línea ~1217
- `crypto-bots/test-tp3-fix.sh` - Test de verificación

---

### **6. Trade IDs Desordenados** ❌→✅

**Problema:**
```
Orden incorrecto: 43, 42, 41... 3, 2, 1, 44, 45, 46, 47, 48 ❌
```

**Solución:**
```python
# Reordenar por ID descendente (48 → 1)
history['trades'] = sorted(history['trades'], key=lambda x: x['id'], reverse=True)
```

**Impacto:** Dashboard muestra trades más recientes primero

**Archivos:**
- `crypto-bots/trade-history.json` - Reordenado manualmente

---

### **7. Timestamps Incorrectos en Trades** ❌→✅

**Problema:**
```
AVAX Slot 1 TP1:
  Entrada: May 7, 00:06
  TP1 Hit: May 8, 09:56
  Timestamp guardado: May 7 ❌ (debería ser May 8)
```

**Solución:**
- Corregido manualmente en trade-history.json
- Script usa `date -Iseconds` correctamente (hora de cierre)

**Impacto:** Timestamps ahora reflejan hora de cierre, no de entrada

**Archivos:**
- `crypto-bots/trade-history.json` - Corregido

---

### **8. Dashboard No Mostraba Avatar** ❌→✅

**Problema:**
```html
<!-- ANTES (BUG): -->
<div class="logo-icon">🐕</div>
<!-- Solo emoji, no avatar real -->
```

**Solución:**
```html
<!-- AHORA (FIX): -->
<div class="logo-icon">
    <img src="/static/avatars/perrobotillo-avatar.webp" alt="Perrobotillo" class="avatar-img">
</div>
```

**Impacto:** Dashboard muestra avatar cyberpunk oficial

**Archivos:**
- `dashboard/templates/index.html`
- `dashboard/templates/mobile.html`
- `dashboard/static/avatars/perrobotillo-avatar.webp`
- `dashboard/static/css/style.css`
- `dashboard/static/css/mobile.css`

---

### **9. Favicon No Aparecía en Navegadores** ❌→✅

**Problema:**
```
WebP no es soportado como favicon en Firefox, Safari, DuckDuckGo
```

**Solución:**
```html
<!-- AHORA (FIX): Múltiples formatos -->
<link rel="icon" sizes="32x32" href="favicon-32x32.png">
<link rel="icon" sizes="16x16" href="favicon-16x16.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="shortcut icon" href="favicon.ico">
```

**Formatos generados:**
- favicon-32x32.png (Firefox, Chrome)
- favicon-16x16.png (Fallback)
- favicon.ico (IE, Edge, DuckDuckGo)
- apple-touch-icon.png (iOS Safari)

**Archivos:**
- `dashboard/static/avatars/favicon-32x32.png`
- `dashboard/static/avatars/favicon-16x16.png`
- `dashboard/static/avatars/favicon.ico`
- `dashboard/static/avatars/apple-touch-icon.png`
- `dashboard/templates/index.html`
- `dashboard/templates/mobile.html`

---

### **10. 11 Trades Faltantes en Histórico** ❌→✅

**Problema:**
```
Notificaciones de Telegram salieron, pero trades NO se guardaron:
- SOL TP2 x2 (11:33 AM)
- LINK TP1 (11:34 AM)
- AVAX TP2 x2 (11:36 AM)
```

**Causa:** Bug de `log_trade_to_history()` con P&L vacío

**Solución:**
- Recuperados manualmente
- Fix aplicado para trades futuros

**Archivos:**
- `crypto-bots/trade-history.json` - 11 trades agregados

---

## 🎯 FEATURES NUEVAS IMPLEMENTADAS

### **1. SCALPING MODE para Mercado Lateral** 🎯

**Descripción:**
Nuevo tipo de cierre rápido para mercado lateral (target 1.0%, SL 2.5%)

**Configuración:**
```bash
SCALPING_ENABLED=true
SCALP_TARGET_PERCENT="1.0"
SCALP_SL_PERCENT="2.5"
SCALP_MIN_PROFIT="$0.50"
```

**Activación:**
- Automática cuando `MARKET_MODE = "LATERAL"`
- Solo para slots nuevos (< 1h, sin TP1 done)
- Cierra 100% de la posición rápidamente

**Close Type:** `SCALP`

**Archivos:**
- `crypto-trade-moneda-v3-slots.sh` - FASE 0: SCALPING MODE
- `crypto-bots/auto-adjust-strategy.sh` - Config scalping
- `crypto-bots/test-scalping.sh` - Test de verificación

---

### **2. Cash Register Sound en TP Hits** 🔊

**Descripción:**
Sonido de caja registradora cuando barra de progreso llega al 100%

**Implementación:**
```javascript
// Detecta cuando progreso llega al 100%
if (progress >= 99.5 && lastProgress < 99.5) {
    playCashRegister();  // 🔊 ¡DIN DIN DIN! 💰
}
```

**Características:**
- Sonido: cash-register.wav (335KB)
- Volumen: 70%
- No spamea: una vez por TP hit
- Trackea por: coin-slotId-targetName

**Archivos:**
- `dashboard/static/sounds/cash-register.wav`
- `dashboard/templates/index.html` - Audio element
- `dashboard/static/js/app.js` - playCashRegister() + detección
- `dashboard/templates/test-sound.html` - Página de test

---

### **3. P&L por Moneda (24H)** 📊

**Descripción:**
Muestra P&L individual por cada moneda (BTC, ETH, BNB, SOL, LINK, XRP, AVAX)

**Backend:**
```python
def get_daily_pnl():
    # Retorna (total, pnl_by_coin)
    pnl_by_coin = {
        'BTC': 1.36,
        'ETH': 1.40,
        'BNB': 0.00,
        ...
    }
```

**Frontend:**
- Desktop: Grid 7 columnas
- Móvil: Grid 3x3 responsive
- Colores: Verde (profit), Rojo (loss)

**Archivos:**
- `dashboard/app.py` - get_daily_pnl()
- `dashboard/templates/index.html` - pnl-by-coin-container
- `dashboard/templates/mobile.html` - pnl-by-coin-container
- `dashboard/static/js/app.js` - updatePnlByCoin()
- `dashboard/static/js/mobile.js` - updatePnlByCoin()
- `dashboard/static/css/style.css` - Estilos P&L by coin
- `dashboard/static/css/mobile.css` - Estilos móvil

---

### **4. Avatar Cyberpunk en Dashboard** 🎨

**Descripción:**
Reemplazo de emoji 🐕 por avatar oficial de Perrobotillo

**Características:**
- Formato: WebP (50KB)
- Tamaño: 80x80px (desktop), 40x40px (móvil)
- Efecto: Glow neón azul
- Animación: Pulse (2s)

**Archivos:**
- `dashboard/static/avatars/perrobotillo-avatar.webp`
- `dashboard/templates/index.html`
- `dashboard/templates/mobile.html`
- `dashboard/static/css/style.css` - .avatar-img (80px)
- `dashboard/static/css/mobile.css` - .avatar-img (40px)

---

### **5. Favicon Multi-Formato** 🖼️

**Descripción:**
Avatar en pestaña del navegador (todos los formatos)

**Formatos:**
- favicon-32x32.png (Firefox, Chrome)
- favicon-16x16.png (Fallback universal)
- favicon.ico (IE, Edge, DuckDuckGo)
- apple-touch-icon.png (iOS Safari, 180x180)

**Archivos:**
- `dashboard/static/avatars/favicon-32x32.png`
- `dashboard/static/avatars/favicon-16x16.png`
- `dashboard/static/avatars/favicon.ico`
- `dashboard/static/avatars/apple-touch-icon.png`
- `dashboard/templates/index.html` - Todos los <link>
- `dashboard/templates/mobile.html` - Todos los <link>

---

### **6. Trade History Ordenamiento** 🔢

**Descripción:**
IDs cronológicos (1=viejo, n=reciente) + Dashboard muestra descendente

**Orden en archivo:**
```
ID 1 → ID 2 → ID 3 → ... → ID 48
(viejo)                (reciente)
```

**Orden en dashboard:**
```
ID 48 → ID 47 → ... → ID 1
(reciente)           (viejo)
```

**Archivos:**
- `crypto-bots/trade-history.json` - Ordenado cronológicamente
- `dashboard/static/js/app.js` - sortedTrades.reverse()

---

### **7. Test de Scalping** 🧪

**Descripción:**
Script para verificar implementación de scalping

**Test:**
```bash
./test-scalping.sh
```

**Verifica:**
- ✅ SCALP detection funciona
- ✅ P&L calculation funciona
- ✅ log_trade_to_history() integrado
- ✅ Telegram notification lista
- ✅ CLOSED_SCALP status implementado

**Archivos:**
- `crypto-bots/test-scalping.sh`

---

### **8. Test de TP3 Fix** 🧪

**Descripción:**
Script para verificar fix de BUG-042

**Test:**
```bash
./test-tp3-fix.sh
```

**Verifica:**
- ✅ TP1+TP2 done → TP3 vende 30% ($6.65 >= $5)
- ✅ Solo TP1 done → TP3 vende 65% ($14.41 >= $5)
- ✅ 5% acumulado se queda en Binance
- ✅ Binance acepta ambas órdenes

**Archivos:**
- `crypto-bots/test-tp3-fix.sh`

---

## 📁 ARCHIVOS MODIFICADOS

### **Core Trading:**
- `crypto-trade-moneda-v3-slots.sh` - Fixes TP1/TP2/TP3/SL/TRAILING + SCALPING
- `crypto-bots/auto-adjust-strategy.sh` - Config scalping
- `crypto-bots/trade-history.json` - Trades recuperados + ordenados

### **Dashboard:**
- `dashboard/app.py` - P&L fix + test-sound route
- `dashboard/templates/index.html` - Avatar + favicon + sound
- `dashboard/templates/mobile.html` - Avatar + favicon + sound
- `dashboard/templates/test-sound.html` - Test page
- `dashboard/static/js/app.js` - Cash register + P&L by coin
- `dashboard/static/js/mobile.js` - P&L by coin
- `dashboard/static/css/style.css` - Avatar + P&L styles
- `dashboard/static/css/mobile.css` - Avatar + P&L styles

### **Assets:**
- `dashboard/static/avatars/perrobotillo-avatar.webp` - Avatar oficial
- `dashboard/static/avatars/favicon-32x32.png` - Favicon 32px
- `dashboard/static/avatars/favicon-16x16.png` - Favicon 16px
- `dashboard/static/avatars/favicon.ico` - Favicon multi-size
- `dashboard/static/avatars/apple-touch-icon.png` - iOS icon
- `dashboard/static/sounds/cash-register.wav` - Sound effect

### **Tests:**
- `crypto-bots/test-scalping.sh` - Scalping test
- `crypto-bots/test-tp3-fix.sh` - TP3 fix test

---

## 📊 ESTADÍSTICAS FINALES

### **Trades:**
```
Total: 48
Win Rate: 100% 🏆
Net P&L: +$145.95 USDT

Por Coin:
- LINK: 9 trades | +$81.18
- SOL: 10 trades | +$15.06
- AVAX: 10 trades | +$10.71
- XRP: 5 trades | +$10.47
- BNB: 5 trades | +$9.72
- BTC: 4 trades | +$6.91
- ETH: 3 trades | +$1.69
```

### **Sistema:**
```
Cron Jobs: 24 activos
Dashboard: Online (ngrok)
Scalping Mode: ACTIVO (LATERAL)
Auto-Adjust: Cada 6 horas (00:00, 06:00, 12:00, 18:00)
```

---

## 🎯 LECCIONES APRENDIDAS

### **1. Calcular P&L ANTES de guardar:**
```bash
# MAL:
log_trade_to_history ... "$pnl"  # $pnl vacío
local pnl=$(awk ...)             # Muy tarde

# BIEN:
local pnl=$(awk ...)             # Primero
log_trade_to_history ... "$pnl"  # Después
```

### **2. TP3 cálculo correcto:**
```bash
# Después de TP1 (35%) + TP2 (30%):
# Queda 35%, TP3 vende 30% (deja 5% acumulado)
# NO 20% como estaba antes
```

### **3. Múltiples formatos para compatibilidad:**
```html
<!-- Un solo formato NO es suficiente -->
<!-- Usar todos los formatos para todos los navegadores -->
```

### **4. Audio requiere interacción del usuario:**
```javascript
// Los navegadores bloquean autoplay
// Requiere user interaction first
// O test page con botón explícito
```

---

## 🚀 PRÓXIMOS PASOS

### **Para Mañana:**
- [ ] Revisar 5% acumulado (¿vale la pena?)
- [ ] Emergency stop global (opcional)
- [ ] Monitorear scalping en producción

### **Monitoreo Continuo:**
- [ ] Verificar próximos TP hits (log fix)
- [ ] Verificar scalping se activa en LATERAL
- [ ] Daily report 9 AM

---

## 📝 NOTAS IMPORTANTES

### **Seguridad:**
- ✅ Secrets en .gitignore
- ✅ API keys rotadas (Mayo 4)
- ✅ Dashboard con auth (overgon)

### **Independencia de OpenClaw:**
- ✅ Trading bot: 90% independiente (cron + API direct)
- ✅ Dashboard: 100% independiente (Flask + ngrok)
- ✅ Alertas: 100% independientes (lib/send-telegram.sh)
- ⚠️ Chat: Depende de OpenClaw/Ollama

### **Backup:**
- ✅ trade-history-PRE-DYNAMIC-2026-05-04.json.backup
- ✅ Daily snapshots en memory/

---

**Documentado por:** Perrobotillo 🐕
**Fecha:** 2026-05-08 17:45 CST
**Versión:** FASE 1 v2.1 + Dynamic Strategy + Scalping
