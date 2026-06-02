#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🚨 EMERGENCY CLOSE - AVAX SLOTS                      ║
# ║  Cierra los 3 slots de AVAX con SL cruzado            ║
# ╚═══════════════════════════════════════════════════════╝

set -e

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="$HOME/.openclaw/secrets"
LOGS="$HOME/.openclaw/logs"
BINANCE="https://api.binance.com"

source "$SECRETS/binance.env"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [AVAX-EMERGENCY] $1" | tee -a "$LOGS/avax-emergency-close.log"
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

get_current_price() {
    curl -s "${BINANCE}/api/v3/ticker/price?symbol=AVAXUSDT" 2>/dev/null | jq -r '.price'
}

place_market_sell() {
    local quantity="$1"
    local attempt=1
    local max_attempts=3
    
    while [ $attempt -le $max_attempts ]; do
        local timestamp=$(date -u +%s%3N)
        local query_string="symbol=AVAXUSDT&side=SELL&type=MARKET&quantity=${quantity}&timestamp=${timestamp}&recvWindow=5000"
        local signature=$(get_signature "$query_string")
        
        log "  Intento ${attempt}/${max_attempts}..."
        
        local result=$(curl -s -X POST "${BINANCE}/api/v3/order" \
            -H "X-MBX-APIKEY: ${BINANCE_API_KEY}" \
            -d "${query_string}&signature=${signature}")
        
        local status=$(echo "$result" | jq -r '.status // "ERROR"')
        
        if [ "$status" = "FILLED" ] || [ "$status" = "PARTIALLY_FILLED" ]; then
            echo "$result"
            return 0
        fi
        
        local code=$(echo "$result" | jq -r '.code // 0')
        if [ "$code" = "-1021" ] && [ $attempt -lt $max_attempts ]; then
            log "  Timestamp error, reintentando..."
            sleep 1
            attempt=$((attempt + 1))
            continue
        fi
        
        echo "$result"
        return 0
    done
    
    echo '{"status":"ERROR","msg":"Max retries exceeded"}'
}

# ============================================
# MAIN
# ============================================

log "╔═══════════════════════════════════════════════════════╗"
log "║  🚨 EMERGENCY CLOSE - AVAX                            ║"
log "╚═══════════════════════════════════════════════════════╝"

STATE_FILE="$WORKSPACE/crypto-bots/AVAX-trade-state.json"

if [ ! -f "$STATE_FILE" ]; then
    log "❌ ERROR: No se encuentra AVAX-trade-state.json"
    exit 1
fi

# Obtener precio actual
current_price=$(get_current_price)
log "💰 AVAX current price: \$${current_price}"

# Leer slots activos
active_slots=$(jq -c '.slots[] | select(.status == "ACTIVE")' "$STATE_FILE")

closed_count=0
total_pnl=0
report=""

while IFS= read -r slot; do
    [ -z "$slot" ] && continue
    
    slot_id=$(echo "$slot" | jq -r '.slotId')
    entry_price=$(echo "$slot" | jq -r '.entryPrice')
    sl=$(echo "$slot" | jq -r '.stopLoss')
    quantity=$(echo "$slot" | jq -r '.quantity')
    
    log "\n🔍 AVAX Slot ${slot_id}:"
    log "   Entry: \$${entry_price} | SL: \$${sl} | Qty: ${quantity}"
    
    # Verificar si SL está cruzado
    sl_crossed=$(echo "$current_price <= $sl" | bc -l)
    
    if [ "$sl_crossed" -eq 1 ]; then
        log "   🔴 SL CRUZADO - Ejecutando cierre..."
        
        # Ejecutar venta
        sell_result=$(place_market_sell "$quantity")
        sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"')
        
        if [ "$sell_status" = "FILLED" ] || [ "$sell_status" = "PARTIALLY_FILLED" ]; then
            exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0')
            fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0')
            fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
            
            # Calcular fee en USDT
            fee_usd=$fee_bnb
            if [ "$fee_asset" = "BNB" ]; then
                fee_usd=$(awk -v b="$fee_bnb" -v p="$exit_price" 'BEGIN {printf "%.8f", b * p}')
            fi
            
            # Calcular P&L
            pnl=$(awk -v e="$entry_price" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
            
            log "   ✅ CERRADO: Exit=\$${exit_price}, P&L=\$${pnl}"
            
            # Actualizar estado del slot
            tmp_file=$(mktemp)
            jq --argjson sid "$slot_id" --arg exit "$exit_price" --arg pnl "$pnl" '
                .slots = [.slots[] | if .slotId == $sid then 
                    .status = "CLOSED_SL_EMERGENCY" | 
                    .exitPrice = ($exit | tonumber) |
                    .pnlUSDT = ($pnl | tonumber)
                else . end]
            ' "$STATE_FILE" > "$tmp_file" && mv "$tmp_file" "$STATE_FILE"
            
            pnl_icon="🔴"
            report+="${pnl_icon} <b>AVAX Slot ${slot_id}</b>\n"
            report+="   Entry: \$${entry_price} → Exit: \$${exit_price}\n"
            report+="   P&L: \$${pnl}\n\n"
            
            closed_count=$((closed_count + 1))
            total_pnl=$(awk -v t="$total_pnl" -v p="$pnl" 'BEGIN {printf "%.8f", t + p}')
            
            sleep 1
        else
            error_msg=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
            log "   ❌ ERROR: $error_msg"
            report+="❌ <b>AVAX Slot ${slot_id}</b>: ERROR - $error_msg\n\n"
        fi
    else
        log "   🟢 SL no cruzado"
    fi
    
done <<< "$active_slots"

# ============================================
# REPORTE FINAL
# ============================================

log "\n╔═══════════════════════════════════════════════════════╗"
log "║  REPORTE FINAL                                        ║"
log "╚═══════════════════════════════════════════════════════╝"
log "Slots cerrados: ${closed_count}"
log "P&L Total: \$${total_pnl}"

if [ $closed_count -gt 0 ]; then
    total_pnl_fmt=$(awk -v p="$total_pnl" 'BEGIN {printf "%.2f", p}')
    
    send_telegram "🚨 <b>AVAX EMERGENCY CLOSE COMPLETED</b>

Se cerraron ${closed_count} slots de AVAX con SL cruzado:

${report}
<b>📊 Resumen:</b>
• Slots cerrados: ${closed_count}
• P&L Total: 🔴 \$${total_pnl_fmt}
• Razón: Prevención de mayores pérdidas (SL cruzado >100%)

⚠️ Los slots se marcaron como CLOSED_SL_EMERGENCY.

_Generated by Perrobotillo Emergency System_ 🐕"
fi

log "✅ Emergency close de AVAX completado"
