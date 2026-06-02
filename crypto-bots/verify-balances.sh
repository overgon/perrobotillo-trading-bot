#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🔄 VERIFY BALANCES - SYNC CHECK AUTOMÁTICO           ║
# ║  Verifica que trade-state files = Binance API         ║
# ╚═══════════════════════════════════════════════════════╝

set -e

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="$HOME/.openclaw/secrets"
LOGS="$HOME/.openclaw/logs"
BINANCE="https://api.binance.com"

source "$SECRETS/binance.env"

COINS=("BTC" "ETH" "SOL" "LINK" "XRP" "BNB" "AVAX")
THRESHOLD=0.001  # 0.1% de diferencia máxima permitida

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [VERIFY-BAL] $1" | tee -a "$LOGS/verify-balances.log"
}

send_telegram() {
    local message="$1"
    local config_file="$HOME/.openclaw/openclaw.json"
    if [ -f "$config_file" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_file" 2>/dev/null)
        [ -n "$bot_token" ] && [ "$bot_token" != "null" ] && \
            curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
                -H "Content-Type: application/json" \
                -d "{\"chat_id\":\"7543955537\",\"text\":\"$message\",\"parse_mode\":\"HTML\"}" > /dev/null
    fi
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
log "║  🔄 VERIFY BALANCES - SYNC CHECK                      ║"
log "╚═══════════════════════════════════════════════════════╝"

# Obtener datos de cuenta de Binance
account_data=$(get_account_data)
if ! echo "$account_data" | jq -e '.balances' > /dev/null 2>&1; then
    log "❌ ERROR: No se pudo obtener datos de Binance"
    exit 1
fi

discrepancies=()

for COIN in "${COINS[@]}"; do
    STATE_FILE="$WORKSPACE/crypto-bots/${COIN}-trade-state.json"
    
    if [ ! -f "$STATE_FILE" ]; then
        log "⚠️  ${COIN}: No state file, skipping..."
        continue
    fi
    
    # Obtener balance real de Binance
    api_balance=$(echo "$account_data" | jq -r ".balances[] | select(.asset == \"$COIN\") | .free // 0")
    api_balance=$(echo "$api_balance" | awk '{printf "%.8f", $1}')
    
    if [ "$api_balance" = "null" ] || [ -z "$api_balance" ]; then
        api_balance="0.00000000"
    fi
    
    # Sumar cantidades activas del file
    active_qty=$(jq '[.slots[] | select(.status == "ACTIVE") | .quantity // 0] | add // 0' "$STATE_FILE" 2>/dev/null || echo "0")
    active_qty=$(echo "$active_qty" | awk '{printf "%.8f", $1}')
    
    # Calcular diferencia absoluta
    diff=$(awk -v api="$api_balance" -v active="$active_qty" 'BEGIN {printf "%.8f", api - active}')
    diff_abs=${diff#-}  # Valor absoluto
    
    log "${COIN}: API=${api_balance}, File=${active_qty}, Diff=${diff}"
    
    # Verificar si diferencia > threshold
    if (( $(echo "$diff_abs > $THRESHOLD" | bc -l) )); then
        log "  🔴 DISCREPANCIA DETECTADA: ${diff}"
        discrepancies+=("${COIN}: API=${api_balance}, File=${active_qty}, Diff=${diff}")
    else
        log "  ✅ OK (diff=${diff})"
    fi
done

# Reportar discrepancias
if [ ${#discrepancies[@]} -gt 0 ]; then
    message="⚠️ <b>BALANCE DISCREPANCY DETECTED</b>\n\n"
    
    for d in "${discrepancies[@]}"; do
        message+="${d}\n"
    done
    
    message+="\n<b>Acción requerida:</b>\n"
    message+="1. Revisar trade-history.json para trades cerrados\n"
    message+="2. Ejecutar sync-state-with-binance.sh si es necesario\n"
    message+="3. Verificar si hubo ventas manuales externas\n"
    
    send_telegram "$message"
    log "✅ Alerta enviada"
    exit 1  # Exit with error para que el cron loguee el fallo
else
    log "✅ Todas las coins sincronizadas"
    exit 0
fi
