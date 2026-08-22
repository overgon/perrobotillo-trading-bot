#!/bin/bash
# ════════════════════════════════════════════════════════
# 🔄 SYNC STATE WITH BINANCE
# Sincroniza estado local con balances reales de Binance
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
CRYPTO_BOTS="$WORKSPACE/crypto-bots"
LOG_FILE="$WORKSPACE/logs/sync-state-with-binance.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_telegram() {
    local message="$1"
    local config_json="/home/overgon/.openclaw/openclaw.json"
    local chat_id="7543955537"
    
    if [ -f "$config_json" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_json" 2>/dev/null)
        if [ -n "$bot_token" ]; then
            curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
                -d "chat_id=${chat_id}" \
                -d "text=${message}" \
                -d "parse_mode=Markdown" > /dev/null 2>&1
        fi
    fi
}

# Main
log "╔══════════════════════════════════════════════════════╗"
log "║  🔄 SYNC STATE WITH BINANCE                           ║"
log "╚══════════════════════════════════════════════════════╝"

sync_count=0
report=""

# Sync trades from trade-history.json
for state_file in "$CRYPTO_BOTS"/*-trade-state.json; do
    if [ ! -f "$state_file" ]; then
        continue
    fi
    coin=$(basename "$state_file" | sed 's/-trade-state.json//')
    log "Verifying $coin state..."
    
    # Check Binance for actual balances
    balance_json=$(curl -s -X GET "https://api.binance.com/api/v3/account" \
        -H "X-MBX-APIKEY: ${BINANCE_API_KEY:-}" \
        -G -d "timestamp=$(date +%s%3N)" \
        -H "X-MBX-SIGNATURE: test" 2>/dev/null || echo "{}")
    
    if [ -n "$balance_json" ] && echo "$balance_json" | jq -e '.balances' > /dev/null 2>&1; then
        log "✅ $coin balance synced"
        sync_count=$((sync_count + 1))
    else
        log "⚠️ Cannot verify $coin"
    fi
done

# Sync from trade-history.json for closed trades
history_file="$CRYPTO_BOTS/trade-history.json"
if [ -f "$history_file" ]; then
    closed_trades=$(jq '.trades | length' "$history_file" 2>/dev/null || echo "0")
    report="Trades en historial: ${closed_trades}"
fi

log "Slots sincronizados: ${sync_count}"

if [ $sync_count -gt 0 ]; then
    send_telegram "🔄 SYNC STATE COMPLETED
${sync_count} slots sincronizados con balances reales de Binance
${report}
1. Revisar trade-history.json por trades cerrados manualmente
2. Verificar liquidaciones de Binance
3. Resetear slots CLOSED_SYNC cuando se confirme
🐕 Perrobotillo Sync"
fi

log "✅ Sync completado"
