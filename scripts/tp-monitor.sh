#!/bin/bash
# ════════════════════════════════════════════════════════
# 🎯 TP MONITOR - MONITOREO EN TIEMPO REAL DE TP 100%
# ════════════════════════════════════════════════════════
# Detecta cuando un slot llega a TP/SL y ejecuta INMEDIATO
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

WORKSPACE="$HOME/.openclaw/workspace"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$HOME/.openclaw/logs/tp-monitor.log"
BINANCE="https://api.binance.com"

source "$HOME/.openclaw/secrets/binance.env"

# ════════════════════════════════════════════════════════
# 🔧 FUNCIONES
# ════════════════════════════════════════════════════════

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

get_current_price() {
    local symbol="$1"
    local price=$(curl -s "$BINANCE/api/v3/ticker/price?symbol=${symbol}USDT" | jq -r '.price')
    echo "$price"
}

check_and_close_tp() {
    local coin="$1"
    local state_file="$WORKSPACE/crypto-bots/${coin}-trade-state.json"
    local current_price=$(get_current_price "$coin")
    
    if [ ! -f "$state_file" ]; then
        return
    fi
    
    # Ejecutar Python script para verificar y cerrar TPs/SL
    python3 "$SCRIPT_DIR/check-tp.py" "$coin" "$current_price" "$state_file" "$LOG_FILE"
}

# ════════════════════════════════════════════════════════
# 🎯 MONITOREO EN TIEMPO REAL
# ════════════════════════════════════════════════════════

log "╔═══════════════════════════════════════════════════════╗"
log "║  🎯 TP MONITOR - INICIANDO MONITOREO                ║"
log "╚═══════════════════════════════════════════════════════╝"
log ""

COINS=("BTC" "ETH" "BNB" "SOL" "LINK" "XRP" "AVAX")

while true; do
    log "=== Escaneando TPs ==="
    
    for coin in "${COINS[@]}"; do
        check_and_close_tp "$coin"
    done
    
    log ""
    sleep 30
done
