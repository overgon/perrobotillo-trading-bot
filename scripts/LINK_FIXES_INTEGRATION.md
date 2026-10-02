# 🔧 LINK Strategy Fixes - Guía de Integración

## 📋 Fixes Implementados

### Fix #1: Dynamic SL Based on ATR
**Script:** `/workspace/scripts/link-dynamic-sl.sh`

**Qué hace:**
- Calcula ATR (Average True Range) de LINK en velas 4h
- SL dinámico = ATR × 2.5 (ajustable)
- Límites: 4.0% (mín) - 9.0% (máx)

**Beneficio:**
- Evita falsos SL en días volátiles
- Win rate improvement esperado: +10-15%

---

### Fix #2: BTC Trend Filter  
**Script:** `/workspace/scripts/btc-trend-filter.sh`

**Qué hace:**
- Calcula SMA50 de BTC (velas 4h)
- Compara precio actual vs SMA50
- Retorna acción basada en tendencia:
  - **DISABLE**: BTC < SMA50 × 0.97 (downtrend fuerte) → No operar LINK
  - **REDUCE**: BTC < SMA50 × 0.95 (downtrend débil) → 50% posición
  - **NORMAL**: BTC > SMA50 × 0.97 → Operar normal

**Beneficio:**
- Evita losses durante correcciones de BTC
- Profit factor improvement esperado: +20-30%

---

## 🚀 Cómo Integrar en Producción

### Opción A: Integración Manual (Recomendada para testing)

#### Paso 1: Probar scripts individualmente

```bash
# Test Dynamic SL
bash /home/overgon/.openclaw/workspace/scripts/link-dynamic-sl.sh
# Output: 6.25 (SL dinámico calculado)

# Test BTC Trend Filter
bash /home/overgon/.openclaw/workspace/scripts/btc-trend-filter.sh
# Output: REDUCE|DOWNTREND_WEAK|-1.88%
```

#### Paso 2: Aplicar parámetros manualmente

Editar `crypto-trade-moneda-v3-slots.sh` línea ~118:

```bash
# ANTES (fijo)
["LINK"]="7.0"

# DESPUÉS (dinámico - actualizar antes de cada trade)
dynamic_sl=$(bash /home/overgon/.openclaw/workspace/scripts/link-dynamic-sl.sh)
# Ejemplo: ["LINK"]="6.25"
```

#### Paso 3: Verificar BTC trend antes de operar LINK

```bash
# Antes de abrir trade de LINK
result=$(bash /home/overgon/.openclaw/workspace/scripts/btc-trend-filter.sh)
action=$(echo $result | cut -d'|' -f1)

if [ "$action" == "DISABLE" ]; then
    echo "🚫 BTC en downtrend fuerte - NO operar LINK"
    exit 0
elif [ "$action" == "REDUCE" ]; then
    echo "⚠️ BTC débil - Reducir posición LINK 50%"
    TRADE_POSITION_PERCENT=20  # En lugar de 40
fi
```

---

### Opción B: Integración Automática (Producción)

Agregar al inicio de `crypto-trade-moneda-v3-slots.sh`:

```bash
# ════════════════════════════════════════════════════════
# 🔧 LINK DYNAMIC FIXES (2026-05-31)
# ════════════════════════════════════════════════════════

if [ "$SYMBOL" == "LINK" ]; then
    # Fix #1: Dynamic SL
    LINK_DYNAMIC_SL=$(bash "$WORKSPACE/scripts/link-dynamic-sl.sh" 2>/dev/null | tail -1)
    if [ -n "$LINK_DYNAMIC_SL" ]; then
        STOP_LOSS_BY_COIN["LINK"]="$LINK_DYNAMIC_SL"
        log "🔧 LINK Dynamic SL aplicado: ${LINK_DYNAMIC_SL}%"
    fi
    
    # Fix #2: BTC Trend Filter
    BTC_RESULT=$(bash "$WORKSPACE/scripts/btc-trend-filter.sh" 2>/dev/null | tail -1)
    BTC_ACTION=$(echo "$BTC_RESULT" | cut -d'|' -f1)
    
    if [ "$BTC_ACTION" == "DISABLE" ]; then
        log "🚫 BTC Trend Filter: DISABLE LINK trading"
        exit 0  # No operar LINK hoy
    elif [ "$BTC_ACTION" == "REDUCE" ]; then
        log "⚠️ BTC Trend Filter: REDUCE LINK position 50%"
        NORMAL_TRADE_PERCENT=$((NORMAL_TRADE_PERCENT / 2))
    fi
fi
```

---

## 📊 Monitoreo Post-Implementación

### Daily Checks:

```bash
# Ver logs del día
tail -100 /home/overgon/.openclaw/logs/link-dynamic-sl.log
tail -100 /home/overgon/.openclaw/logs/btc-trend-filter.log

# Contar trades de LINK
grep "LINK.*Slot" /home/overgon/.openclaw/logs/trade-LINK.log | wc -l

# Ver win rate del día
grep "TP\|SL" /home/overgon/.openclaw/logs/trade-LINK.log | \
  grep "$(date +%Y-%m-%d)" | \
  awk '{print $0}' | wc -l
```

### Weekly Review:

1. **Win Rate Comparison**
   - Before fixes: 34.83%
   - Target after fixes: 50%+
   - Actual this week: ___%

2. **P&L Comparison**
   - Before fixes: -$40.50/month
   - Target after fixes: +$20+/month
   - Actual this week: $___

3. **BTC Filter Effectiveness**
   - Days DISABLED: ___
   - Days REDUCED: ___
   - Days NORMAL: ___
   - Losses avoided (est): $___

---

## 🎯 Métricas de Éxito

| Métrica | Baseline | Target (2 semanas) | Stretch (1 mes) |
|---------|----------|-------------------|-----------------|
| Win Rate | 34.83% | 45% | 55% |
| P&L Mensual | -$40.50 | +$10 | +$30 |
| Profit Factor | 0.60 | 1.0 | 1.3 |
| Max Drawdown | ~40% | <30% | <20% |
| Días positivos/mes | ~12 | 18 | 22 |

---

## ⚠️ Troubleshooting

### Problema: Dynamic SL da valores extremos

**Solución:**
```bash
# Revisar ATR calculation
curl -s "https://api.binance.com/api/v3/klines?symbol=LINKUSDT&interval=4h&limit=20" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for candle in data[-5:]:
    high, low, close = float(candle[2]), float(candle[3]), float(candle[4])
    tr = max(high-low, abs(high-close), abs(low-close))
    print(f'ATR contrib: {tr/close*100:.2f}%')
"
```

### Problema: BTC Filter siempre dice DISABLE

**Causa:** BTC en corrección prolongada

**Solución:**
- Ajustar threshold de -3% a -5%
- O desactivar filter temporalmente si se pierden muchas oportunidades

```bash
# En btc-trend-filter.sh, línea ~70
threshold_downtrend="-5.0"  # Antes: -3.0
```

### Problema: Scripts lentos (>5 segundos)

**Causa:** API calls a Binance

**Solución:**
- Cachear resultados por 1 hora
- Usar datos locales si están disponibles

```bash
# Agregar cache
CACHE_FILE="/tmp/btc_trend_cache.json"
if [ -f "$CACHE_FILE" ] && [ $(find $CACHE_FILE -mmin -60 | wc -l) -eq 1 ]; then
    cat "$CACHE_FILE"
    exit 0
fi
```

---

## 📝 Notas Importantes

1. **Testing primero**: Probar en dry-run 3-5 días antes de production
2. **Monitoreo diario**: Revisar logs cada día la primera semana
3. **Ajuste fino**: Los thresholds (2.5x ATR, -3% BTC) pueden necesitar ajuste
4. **Backup**: Mantener config anterior por si hay que revertir
5. **Documentar**: Loggear todos los cambios y resultados

---

## 🔄 Rollback Plan

Si los fixes no funcionan después de 1 semana:

```bash
# 1. Desactivar Dynamic SL
# En crypto-trade-moneda-v3-slots.sh línea 118:
["LINK"]="7.0"  # Volver a fijo

# 2. Desactivar BTC Filter
# Comentar líneas de integración en script principal

# 3. Monitorear 1 semana
# Comparar performance vs versión con fixes
```

---

🐕 Perrobotillo Trading Bot  
*"¡Nunca confiar, siempre verificar!"*

*Última actualización: 2026-05-31 14:50 CST*
