#!/bin/bash
# TP Monitor - monitoreo loop
WORKSPACE="$HOME/.openclaw/workspace"
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
LOG_FILE="$HOME/.openclaw/logs/tp-monitor.log"
BINANCE="https://api.binance.com"

source "$HOME/.openclaw/secrets/binance.env"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

get_current_price() {
    local symbol="$1"
    local price
    price=$(curl -s "$BINANCE/api/v3/ticker/price?symbol=${symbol}USDT" | jq -r '.price // empty')
    if [ -n "$price" ] && [ "$price" != "null" ]; then
        echo "$price"
    fi
}

check_and_close_tp() {
    local coin="$1"
    local current_price="$2"
    local state_file="$WORKSPACE/crypto-bots/${coin}-trade-state.json"

    if [ ! -f "$state_file" ]; then
        return
    fi

    python3 "$SCRIPT_DIR/check-tp.py" "$coin" "$current_price" "$state_file" "$LOG_FILE" >/dev/null 2>&1 || true
}

main() {
    log "DEBUG: Entrando a main()"
    log "=== TP Monitor iniciado ==="
    COINS=(BTC ETH BNB SOL LINK XRP AVAX)

    while true; do
        log "DEBUG: Iniciando ciclo de escaneo"
        for coin in "${COINS[@]}"; do
            current_price=$(get_current_price "$coin")
            log "DEBUG: $coin precio=$current_price"
            if [ -n "$current_price" ]; then
                check_and_close_tp "$coin" "$current_price"
            fi
        done
        sleep 30
    done
}

main
