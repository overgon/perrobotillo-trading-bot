# 🔧 Dynamic SL & BTC Filter - Guía Universal

## 📋 Fixes Implementados (PARA TODAS LAS MONEDAS)

### Fix #1: Dynamic SL Based on ATR
**Script:** `/workspace/scripts/dynamic-sl.sh`

**Qué hace:**
- Calcula ATR (Average True Range) de CUALQUIER moneda en velas 4h
- SL dinámico = ATR × multiplier (ajustado por volatilidad de cada moneda)
- Límites: 2.5% (mín) - 10.0% (máx)

**Multipliers por moneda:**
| Moneda | Multiplier | SL Típico | Volatilidad |
|--------|------------|-----------|-------------|
| BTC | 2.0× | 3-5% | Baja |
| BNB | 2.0× | 3-5% | Baja |
| ETH | 2.2× | 4-6% | Media |
| XRP | 2.2× | 4-6% | Media |
| LINK | 2.5× | 5-8% | Alta |
| SOL | 2.8× | 6-9% | Alta |
| AVAX | 2.8× | 6-9% | Alta |

**Beneficio:**
- Evita falsos SL en días volátiles
- Win rate improvement esperado: +10-15%
- **Aplica para:** TODAS las monedas

---

### Fix #2: BTC Trend Filter
**Script:** `/workspace/scripts/btc-trend-filter.sh`

**Qué hace:**
- Calcula SMA50 de BTC (velas 4h)
- Compara precio actual vs SMA50
- Decide si operar altcoins:
  - 🔴 **DISABLE**: BTC < SMA50 × 0.97 → No operar altcoins
  - 🟠 **REDUCE**: BTC entre 0.97-1.0 → 50% posición
  - 🟢 **NORMAL**: BTC > SMA50 × 0.97 → Operar normal

**Beneficio:**
- Evita losses durante correcciones de BTC
- Profit factor improvement esperado: +20-30%
- **Aplica para:** Especialmente altcoins (SOL, LINK, AVAX, XRP)

---

## 🚀 Cómo Usar

### Testing manual:

```bash
# Ver SL dinámico para cualquier moneda
bash /workspace/scripts/dynamic-sl.sh BTC
# Output: 3.85 (SL recomendado para BTC)

bash /workspace/scripts/dynamic-sl.sh SOL
# Output: 7.20 (SL recomendado para SOL)

bash /workspace/scripts/dynamic-sl.sh LINK
# Output: 6.25 (SL recomendado para LINK)

# Ver status BTC
bash /workspace/scripts/btc-trend-filter.sh  
# Output: REDUCE|DOWNTREND_WEAK|-1.88%
```

---

## 📊 Impacto Esperado por Moneda

| Coin | WR Actual | WR Target | P&L Actual | P&L Target | Priority |
|------|-----------|-----------|------------|------------|----------|
| BTC | 50% | 55% | +$2.75 | +$4 | ⚪ Baja |
| ETH | 48% | 55% | +$8.50 | +$12 | 🟡 Media |
| BNB | 96% | 97% | +$131 | +$140 | ⚪ Baja (ya funciona) |
| SOL | 60% | 70% | +$40 | +$55 | 🟡 Media |
| **LINK** | **34%** | **50%** | **-$40** | **+$20** | 🔴 **ALTA** |
| XRP | 72% | 75% | +$40 | +$48 | 🟢 Funciona bien |
| AVAX | 71% | 75% | +$42 | +$52 | 🟢 Funciona bien |

**Total portfolio improvement:** +$50-70/mes estimado

---

## 💡 Por qué LINK es prioridad ALTA:

1. **Única moneda con P&L negativo** (-$40.50/mes)
2. **Win rate más bajo** (34.83% vs 60-96% otras)
3. **Mayor volatilidad** → más afectada por SL fijo
4. **Alta correlación con BTC** (beta 1.5) → BTC filter crítico

Pero los fixes benefician a **TODAS**, especialmente:
- SOL y AVAX (alta volatilidad)
- ETH (volatilidad media-alta)

---

## 🎯 Implementación Recomendada

### Fase 1 (Inmediata): LINK
- Implementar fixes para LINK primero
- Monitorear 3-5 días
- Validar mejora de 34% → 45%+ WR

### Fase 2 (Semana 2): SOL, AVAX
- Extender fixes a monedas de alta volatilidad
- Esperar mejora de 60% → 70% WR

### Fase 3 (Semana 3): ETH, XRP
- Extender a volatilidad media
- Fine-tuning general

### Fase 4 (Semana 4): BTC, BNB
- Solo si hay beneficio claro
- BNB probablemente no necesita (96% WR ya)

---

## 📝 Integración en crypto-trade-moneda-v3-slots.sh

```bash
# ════════════════════════════════════════════════════════
# 🔧 DYNAMIC FIXES (2026-05-31) - PARA TODAS LAS MONEDAS
# ════════════════════════════════════════════════════════

# Fix #1: Dynamic SL
dynamic_sl=$(bash "$WORKSPACE/scripts/dynamic-sl.sh" "$SYMBOL" 2>/dev/null | tail -1)
if [ -n "$dynamic_sl" ]; then
    STOP_LOSS_BY_COIN["$SYMBOL"]="$dynamic_sl"
    log "🔧 $SYMBOL Dynamic SL: ${dynamic_sl}%"
fi

# Fix #2: BTC Trend Filter (solo para altcoins)
if [ "$SYMBOL" != "BTC" ] && [ "$SYMBOL" != "BNB" ]; then
    btc_result=$(bash "$WORKSPACE/scripts/btc-trend-filter.sh" 2>/dev/null | tail -1)
    btc_action=$(echo "$btc_result" | cut -d'|' -f1)
    
    if [ "$btc_action" == "DISABLE" ]; then
        log "🚫 BTC Filter: DISABLE $SYMBOL trading"
        exit 0
    elif [ "$btc_action" == "REDUCE" ]; then
        log "⚠️ BTC Filter: REDUCE $SYMBOL position 50%"
        NORMAL_TRADE_PERCENT=$((NORMAL_TRADE_PERCENT / 2))
    fi
fi
```

---

## 📊 Monitoreo

```bash
# Ver SL dinámico actual por moneda
for coin in BTC ETH BNB SOL LINK XRP AVAX; do
    sl=$(bash /workspace/scripts/dynamic-sl.sh $coin 2>/dev/null | tail -1)
    echo "$coin: ${sl}%"
done

# Output esperado:
# BTC: 3.85%
# ETH: 5.12%
# BNB: 4.20%
# SOL: 7.45%
# LINK: 6.25%
# XRP: 4.80%
# AVAX: 7.90%
```

---

🐕 Perrobotillo Trading Bot  
*"¡Nunca confiar, siempre verificar!"*

*Actualizado: 2026-05-31 14:52 CST*
