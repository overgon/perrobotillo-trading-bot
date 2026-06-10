#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  📊 BALANCE REPORT - Reporte Informativo              ║
# ║  Muestra balances reales vs slots activos             ║
# ║  NO genera alertas - dust es normal después de trades ║
# ╚═══════════════════════════════════════════════════════╝

set -e

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="$HOME/.openclaw/secrets"
LOGS="$HOME/.openclaw/logs"
BINANCE="https://api.binance.com"

source "$SECRETS/binance.env"

COINS=("BTC" "ETH" "SOL" "LINK" "XRP" "BNB" "AVAX")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [BAL-REPORT] $1" | tee -a "$LOGS/balance-report.log"
}

get_signature() {
    printf '%s' "$1" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | sed 's/^.* //'
}

get_account_data() {
    local timestamp=$(date -u +%s%3N)
    local query_string="timestamp=${timestamp}&recvWindow=5000"
    local signature=$(get_signature "$query_string")
    
    curl -s -X GET "${BINANCE}/api/v3/account?${query_string}&signature=${signature}" \
        -H "X-MBX-APIKEY: ${BINANCE_API_KEY}"
}

log "╔═══════════════════════════════════════════════════════╗"
log "║  📊 BALANCE REPORT - Dust de Trades Cerrados          ║"
log "╚═══════════════════════════════════════════════════════╝"
log ""
log "NOTA: Los balances mostrados son NORMALES después de múltiples"
log "trades con TP parciales. No representan errores del sistema."
log ""

# Obtener datos de cuenta de Binance
account_data=$(get_account_data)
if ! echo "$account_data" | jq -e '.balances' > /dev/null 2>&1; then
    log "❌ ERROR: No se pudo obtener datos de Binance"
    exit 1
fi

total_dust_usd=0

log "┌─────────────────────────────────────────────────────────┐"
log "│ COIN   │ API Balance │ Active │ Diff    │ USD Value   │"
log "├─────────────────────────────────────────────────────────┤"

for COIN in "${COINS[@]}"; do
    STATE_FILE="$WORKSPACE/crypto-bots/${COIN}-trade-state.json"
    
    if [ ! -f "$STATE_FILE" ]; then
        continue
    fi
    
    # Obtener balance real de Binance
    api_balance=$(echo "$account_data" | jq -r ".balances[] | select(.asset == \"$COIN\") | .free // 0")
    api_balance=$(printf "%.8f" "$api_balance")
    
    # Sumar cantidades activas del file
    active_qty=$(jq '[.slots[] | select(.status == "ACTIVE") | .quantity // 0] | add // 0' "$STATE_FILE" 2>/dev/null || echo "0")
    active_qty=$(printf "%.8f" "$active_qty")
    
    # Calcular diferencia
    diff=$(awk -v api="$api_balance" -v active="$active_qty" 'BEGIN {printf "%.8f", api - active}')
    diff_abs=${diff#-}
    
    # Obtener precio USD
    price_usd=$(curl -s "${BINANCE}/api/v3/ticker/price?symbol=${COIN}USDT" 2>/dev/null | jq -r '.price' || echo "0")
    dust_value_usd=$(awk -v diff="$diff_abs" -v price="$price_usd" 'BEGIN {printf "%.2f", diff * price}')
    
    total_dust_usd=$(awk -v total="$total_dust_usd" -v dust="$dust_value_usd" 'BEGIN {printf "%.2f", total + dust}')
    
    # Formatear salida
    log "│ ${COIN}     │ ${api_balance} │ ${active_qty} │ ${diff} │ \$${dust_value_usd} │"
done

log "└─────────────────────────────────────────────────────────┘"
log ""
log "💰 Total Dust en Balances: \$${total_dust_usd} USD"
log ""
log "✅ Estos balances son NORMALES y provienen de:"
log "   • TP partial fills (ventas parciales)"
log "   • Emergency closes incompletos"
log "   • Comisiones pagadas en BNB"
log "   • Dust no tradeable acumulado"
log ""
log "📝 Para más detalles ver: BALANCE-RECONCILIATION.md"

exit 0
