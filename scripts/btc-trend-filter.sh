#!/bin/bash
# ════════════════════════════════════════════════════════
# 🛡️ BTC TREND FILTER - FIX #2 PARA LINK
# ════════════════════════════════════════════════════════
# Verifica si BTC está en uptrend/downtrend
# Para evitar operar LINK cuando BTC está cayendo
# ════════════════════════════════════════════════════════

WORKSPACE="$HOME/.openclaw/workspace"
LOGS="$HOME/.openclaw/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGS/btc-trend-filter.log"
}

# ════════════════════════════════════════════════════════
# VERIFICAR TENDENCIA DE BTC
# ════════════════════════════════════════════════════════

check_btc_trend() {
    log "╔═══════════════════════════════════════════════════════╗"
    log "║  🛡️ BTC TREND FILTER                                   ║"
    log "╚═══════════════════════════════════════════════════════╝"
    
    # Obtener precio actual de BTC y SMA50 desde Binance
    local url="https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    btc_price=$(curl -s "$url" | jq -r '.price' 2>/dev/null)
    
    if [ -z "$btc_price" ] || [ "$btc_price" == "null" ]; then
        log "❌ Error obteniendo precio de BTC"
        echo "UNKNOWN"
        return 1
    fi
    
    log "💰 BTC Precio Actual: \$${btc_price}"
    
    # Calcular SMA50 (50 velas 4h = ~8 días)
    local sma_url="https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=50"
    
    # Usar Python para calcular SMA50 (más confiable que jq)
    sma50=$(curl -s "$sma_url" | python3 -c "
import sys, json
data = json.load(sys.stdin)
closes = [float(candle[4]) for candle in data]
print(f'{sum(closes) / len(closes):.2f}')
" 2>/dev/null)
    
    if [ -z "$sma50" ] || [ "$sma50" == "null" ] || [ -z "$(echo $sma50 | grep -E '^[0-9]+\.?[0-9]*$')" ]; then
        log "❌ Error calculando SMA50"
        echo "UNKNOWN"
        return 1
    fi
    
    log "📊 BTC SMA50 (4h): \$${sma50}"
    
    # Calcular porcentaje de diferencia
    pct_diff=$(echo "scale=4; ($btc_price - $sma50) / $sma50 * 100" | bc 2>/dev/null)
    
    log "📈 BTC vs SMA50: ${pct_diff}%"
    
    # Determinar tendencia
    # Downtrend fuerte: BTC < SMA50 * 0.97 (3% debajo)
    # Downtrend moderado: BTC < SMA50 * 0.95 (5% debajo)
    # Uptrend: BTC > SMA50 * 1.02 (2% arriba)
    # Lateral: resto
    
    threshold_downtrend="-3.0"
    threshold_uptrend="2.0"
    
    if (( $(echo "$pct_diff < $threshold_downtrend" | bc -l) )); then
        trend="DOWNTREND_STRONG"
        action="DISABLE"  # No operar LINK
        log "🔴 Tendencia: $trend (${pct_diff}%)"
        log "🚫 Acción: DISABLE (no operar LINK)"
        
    elif (( $(echo "$pct_diff < 0" | bc -l) )); then
        trend="DOWNTREND_WEAK"
        action="REDUCE"  # Reducir posición 50%
        log "🟠 Tendencia: $trend (${pct_diff}%)"
        log "⚠️ Acción: REDUCE (50% posición)"
        
    elif (( $(echo "$pct_diff > $threshold_uptrend" | bc -l) )); then
        trend="UPTREND"
        action="NORMAL"  # Operar normal
        log "🟢 Tendencia: $trend (${pct_diff}%)"
        log "✅ Acción: NORMAL (operar normal)"
        
    else
        trend="LATERAL"
        action="NORMAL"  # Operar normal pero con cuidado
        log "⚪ Tendencia: $trend (${pct_diff}%)"
        log "✅ Acción: NORMAL (operar normal)"
    fi
    
    log "╔═══════════════════════════════════════════════════════╗"
    
    # Output para ser usado en otros scripts
    echo "$action|$trend|$pct_diff"
}

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

result=$(check_btc_trend)
echo "$result"

# Parsear resultado si se necesita
action=$(echo "$result" | cut -d'|' -f1)
trend=$(echo "$result" | cut -d'|' -f2)
pct=$(echo "$result" | cut -d'|' -f3)

log ""
log "📋 RESUMEN PARA SCRIPT PADRE:"
log "  Action: $action"
log "  Trend: $trend"
log "  BTC vs SMA50: ${pct}%"
log ""
log "Uso en crypto-trade-moneda-v3-slots.sh:"
log "  result=\$(./scripts/btc-trend-filter.sh)"
log "  action=\$(echo \$result | cut -d'|' -f1)"
log "  if [ \"\$action\" == \"DISABLE\" ]; then"
log "      # No operar LINK"
log "  elif [ \"\$action\" == \"REDUCE\" ]; then"
log "      # Reducir posición 50%"
log "  fi"
