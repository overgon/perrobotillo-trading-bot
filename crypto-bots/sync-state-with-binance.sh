#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🔄 SYNC STATE WITH BINANCE - ACTUALIZAR TRADE STATES ║
# ║  Compara balances reales vs trade-state files         ║
# ╚═══════════════════════════════════════════════════════╝

set -e

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="$HOME/.openclaw/secrets"
LOGS="$HOME/.openclaw/logs"
BINANCE="https://api.binance.com"

source "$SECRETS/binance.env"

COINS=("BTC" "ETH" "SOL" "LINK" "XRP" "BNB" "AVAX")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SYNC] $1" | tee -a "$LOGS/sync-state.log"
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
    echo -n "$1" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}'
}

get_account_data() {
    local timestamp=$(date -u +%s%3N)
    local query_string="timestamp=${timestamp}&recvWindow=5000"
    local signature=$(get_signature "$query_string")
    
    curl -s -X GET "${BINANCE}/api/v3/account?${query_string}&signature=${signature}" \
        -H "X-MBX-APIKEY: ${BINANCE_API_KEY}"
}

get_current_price() {
    local symbol="$1"
    curl -s "${BINANCE}/api/v3/ticker/price?symbol=${symbol}USDT" 2>/dev/null | jq -r '.price'
}

log "╔═══════════════════════════════════════════════════════╗"
log "║  🔄 SYNC STATE WITH BINANCE                           ║"
log "╚═══════════════════════════════════════════════════════╝"

# Obtener datos de cuenta de Binance
account_data=$(get_account_data)
if ! echo "$account_data" | jq -e '.balances' > /dev/null 2>&1; then
    log "❌ ERROR: No se pudo obtener datos de Binance"
    log "Response: ${account_data:0:200}"
    exit 1
fi

sync_count=0
report=""

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
    
    log "🔍 ${COIN}: API Balance = ${api_balance}"
    
    # Leer slots activos del state file
    active_slots=$(jq -c '.slots[] | select(.status == "ACTIVE")' "$STATE_FILE" 2>/dev/null || echo "")
    
    if [ -z "$active_slots" ]; then
        log "  ✅ ${COIN}: No active slots"
        continue
    fi
    
    # Sumar cantidades activas
    total_active_qty=$(jq -s '[.[].quantity // 0] | add // 0' <<< "$(echo "$active_slots" | tr '\n' ' ')" 2>/dev/null || echo "0")
    total_active_qty=$(echo "$total_active_qty" | awk '{printf "%.8f", $1}')
    
    log "  Active Qty en files: ${total_active_qty}"
    
    # Calcular diferencia
    diff=$(awk -v api="$api_balance" -v active="$total_active_qty" 'BEGIN {printf "%.8f", api - active}')
    
    log "  Diferencia: ${diff}"
    
    # Si hay discrepancia significativa (> 0.0001), investigar
    if (( $(echo "${diff#-} > 0.0001" | bc -l) )); then
        log "  ⚠️  DISCREPANCIA DETECTADA (API > files): ${diff}"
        # Esto puede ser TP partial fill o dust no registrado
        report+="🟡 <b>${COIN}</b>: API tiene +${diff} vs files (posible TP partial o dust)\n"
        
    elif (( $(echo "${diff#-} < -0.0001" | bc -l) )); then
        log "  🔴 DISCREPANCIA CRÍTICA (files > API): ${diff}"
        # Los files dicen que hay más de lo que realmente existe
        
        # Marcar slots como CLOSED_SYNC hasta cuadrar
        while IFS= read -r slot; do
            [ -z "$slot" ] && continue
            
            slot_id=$(echo "$slot" | jq -r '.slotId')
            qty=$(echo "$slot" | jq -r '.quantity // 0')
            
            log "    Marcando Slot ${slot_id} (${qty} ${COIN}) como CLOSED_SYNC"
            
            # Actualizar estado
            tmp_file=$(mktemp)
            jq --argjson sid "$slot_id" '
                .slots = [.slots[] | if .slotId == $sid then .status = "CLOSED_SYNC" else . end]
            ' "$STATE_FILE" > "$tmp_file" && mv "$tmp_file" "$STATE_FILE"
            
            sync_count=$((sync_count + 1))
            report+="🔴 <b>${COIN} Slot ${slot_id}</b>: Cerrado por sync (${qty} ${COIN})\n"
            
        done <<< "$active_slots"
    else
        log "  ✅ ${COIN}: Balances sincronizados"
    fi
done

# ============================================
# 📊 REPORTE FINAL
# ============================================

log "╔═══════════════════════════════════════════════════════╗"
log "║  REPORTE FINAL                                        ║"
log "╚═══════════════════════════════════════════════════════╝"
log "Slots sincronizados: ${sync_count}"

if [ $sync_count -gt 0 ]; then
    send_telegram "🔄 <b>SYNC STATE COMPLETED</b>

Se sincronizaron ${sync_count} slots con balances reales de Binance:

${report}
<b>Acciones requeridas:</b>
1. Revisar trade-history.json para trades cerrados manualmente
2. Verificar si hubo liquidaciones de Binance
3. Resetear slots CLOSED_SYNC cuando se confirme el status

_Generated by Perrobotillo Sync System_ 🐕"
fi

log "✅ Sync completado"
