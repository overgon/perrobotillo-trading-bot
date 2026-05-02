#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🤖 AUTO-RESET CLOSED SLOTS - HEALTH BOT              ║
# ║  Revisa y resetea slots cerrados (CLOSED_TRAILING)    ║
# ║  Ejecutar cada 5-15 minutos via cron                  ║
# ╚═══════════════════════════════════════════════════════╝

WORKSPACE="/home/overgon/.openclaw/workspace"
LOG_FILE="/home/overgon/.openclaw/logs/auto-reset-slots.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

reset_closed_slot() {
    local state_file="$1"
    local slot_id="$2"
    local symbol="$3"
    
    log "🔄 Reseteando ${symbol} slot ${slot_id}..."
    
    local temp_file="/tmp/${symbol}-slot${slot_id}-reset.json"
    local slot_index=$((slot_id - 1))
    
    jq ".slots[$slot_index] |= . + {
        status: \"READY\",
        type: null,
        orderId: null,
        entryPrice: null,
        quantity: null,
        usdtSpent: null,
        feeBuy: null,
        totalCost: null,
        stopLoss: null,
        tp1: null,
        tp2: null,
        tp3: null,
        tp1Done: false,
        tp2Done: false,
        tp3Done: false,
        highestPrice: null,
        trailingStop: null,
        timestamp: null
    }" "$state_file" > "$temp_file" && mv "$temp_file" "$state_file"
    
    log "  ✅ ${symbol} slot ${slot_id} reseteado a READY"
}

check_and_reset() {
    local symbol="$1"
    local state_file="${WORKSPACE}/crypto-bots/${symbol}-trade-state.json"
    
    if [ ! -f "$state_file" ]; then
        log "⚠️ ${symbol}: State file no encontrado"
        return
    fi
    
    # Buscar slots CLOSED_TRAILING
    local closed_slots=$(jq -r '.slots[] | select(.status == "CLOSED_TRAILING") | .slotId' "$state_file")
    
    if [ -n "$closed_slots" ]; then
        for slot_id in $closed_slots; do
            reset_closed_slot "$state_file" "$slot_id" "$symbol"
        done
    fi
}

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

log "╔═══════════════════════════════════════════════════════╗"
log "║  🔍 Health Check: Buscando slots cerrados...         ║"
log "╚═══════════════════════════════════════════════════════╝"

COINS=("BTC" "ETH" "BNB" "SOL" "LINK" "XRP" "AVAX")
reset_count=0

for coin in "${COINS[@]}"; do
    state_file="${WORKSPACE}/crypto-bots/${coin}-trade-state.json"
    
    if [ -f "$state_file" ]; then
        closed_count=$(jq '[.slots[] | select(.status == "CLOSED_TRAILING")] | length' "$state_file")
        
        if [ "$closed_count" -gt 0 ]; then
            log "🔴 ${coin}: ${closed_count} slot(s) cerrado(s)"
            check_and_reset "$coin"
            ((reset_count++))
        else
            log "🟢 ${coin}: Todos los slots OK"
        fi
    else
        log "⚠️ ${coin}: State file no encontrado"
    fi
done

log ""
log "✅ Health check completado: ${reset_count} moneda(s) procesada(s)"
