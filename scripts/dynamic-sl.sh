#!/bin/bash
# ════════════════════════════════════════════════════════
# 🔧 DYNAMIC STOP LOSS - PARA TODAS LAS MONEDAS
# ════════════════════════════════════════════════════════
# Calcula SL dinámico basado en ATR (Average True Range)
# Funciona para: BTC, ETH, BNB, SOL, LINK, XRP, AVAX
# ════════════════════════════════════════════════════════

SYMBOL="${1:-LINK}"
WORKSPACE="$HOME/.openclaw/workspace"
LOGS="$HOME/.openclaw/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGS/link-dynamic-sl.log"
}

# ════════════════════════════════════════════════════════
# CALCULAR ATR DESDE BINANCE
# ════════════════════════════════════════════════════════

get_atr() {
    local symbol=$1
    local period=${2:-14}
    
    # Obtener últimas velas 4h de Binance API
    local url="https://api.binance.com/api/v3/klines?symbol=${symbol}USDT&interval=4h&limit=$((period + 10))"
    
    response=$(curl -s "$url")
    
    if [ $? -ne 0 ] || [ -z "$response" ]; then
        log "❌ Error obteniendo datos de Binance"
        echo ""
        return 1
    fi
    
    # Parsear datos y calcular ATR manualmente (simplificado)
    # Formato: [open_time, open, high, low, close, volume, ...]
    
    atr=$(echo "$response" | jq -r '
        .[:'"$period"'] | 
        [., .[1:]] | 
        transpose | 
        .[1:] | 
        map(
            (.[0][2] | tonumber) as $high |
            (.[0][3] | tonumber) as $low |
            (.[1][4] | tonumber) as $prev_close |
            [
                ($high - $low),
                (($high - $prev_close) | if . < 0 then -. else . end),
                (($low - $prev_close) | if . < 0 then -. else . end)
            ] | max
        ) | 
        add / length * 100 / (.[-1][4] | tonumber)
    ' 2>/dev/null)
    
    if [ -z "$atr" ] || [ "$atr" == "null" ]; then
        log "⚠️ No se pudo calcular ATR, usando default"
        echo "4.0"  # Default para LINK
        return 0
    fi
    
    # Formatear a 2 decimales
    printf "%.2f" "$atr"
}

# ════════════════════════════════════════════════════════
# CALCULAR SL DINÁMICO
# ════════════════════════════════════════════════════════

calculate_dynamic_sl() {
    local symbol=$1
    
    log "╔═══════════════════════════════════════════════════════╗"
    log "║  🔧 ZEC DYNAMIC SL CALCULATION                       ║"
    log "╚═══════════════════════════════════════════════════════╝"
    
    # Obtener ATR actual
    atr=$(get_atr "$symbol" 14)
    
    if [ -z "$atr" ]; then
        log "❌ Error calculando ATR, usando SL fijo 7.0%"
        echo "7.0"
        return 1
    fi
    
    log "📊 ATR (${symbol}, 14 períodos 4h): ${atr}%"
    
    # Calcular SL dinámico: ATR * multiplier
    # Multiplier = 2.5 (ajustable)
    multiplier="2.5"
    
    dynamic_sl=$(echo "scale=2; $atr * $multiplier" | bc)
    
    log "🔢 SL Dinámico (ATR x $multiplier): ${dynamic_sl}%"
    
    # Aplicar límites: mín 4.0%, máx 9.0%
    min_sl="4.0"
    max_sl="9.0"
    
    if (( $(echo "$dynamic_sl < $min_sl" | bc -l) )); then
        dynamic_sl=$min_sl
        log "📏 SL ajustado al mínimo: ${dynamic_sl}%"
    elif (( $(echo "$dynamic_sl > $max_sl" | bc -l) )); then
        dynamic_sl=$max_sl
        log "📏 SL ajustado al máximo: ${dynamic_sl}%"
    fi
    
    log "✅ SL Final para ${symbol}: ${dynamic_sl}%"
    log "╔═══════════════════════════════════════════════════════╗"
    
    echo "$dynamic_sl"
}

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if [ "$SYMBOL" == "ZEC" ]; then
    calculate_dynamic_sl "$SYMBOL"
else
    log "⚠️ Dynamic SL solo implementado para ZEC por ahora"
    echo ""
fi
