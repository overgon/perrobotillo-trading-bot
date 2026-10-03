#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🚨 EMERGENCY CLOSE - SLOTS CON SL CRUZADO            ║
# ║  Cierra forzosamente slots donde current_price < SL   ║
# ╚═══════════════════════════════════════════════════════╝

set -e

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="$HOME/.openclaw/secrets"
LOGS="$HOME/.openclaw/logs"
BINANCE="https://api.binance.com"

source "$SECRETS/binance.env"

# ============================================
# 🔧 CONFIGURACIÓN
# ============================================

COINS=("BTC" "ETH" "SOL" "ZEC" "XRP" "BNB" "AVAX")

# ============================================
# 🔧 FUNCIONES DE LOGGING
# ============================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [EMERGENCY-SL] $1" | tee -a "$LOGS/emergency-close-sl-crossed.log"
}

# ✅ Consolidado: usar notify.sh centralizado en lugar de send_telegram duplicada
source "$WORKSPACE/crypto-bots/notify.sh" 2>/dev/null || true

# ============================================
# 🛡️ FUNCIONES DE BINANCE
# ============================================

get_signature() {
    echo -n "$1" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}'
}

get_current_price() {
    local symbol="$1"
    local price=$(curl -s "${BINANCE}/api/v3/ticker/price?symbol=${symbol}USDT" 2>/dev/null | jq -r '.price')
    echo "$price"
}

place_market_sell() {
    local symbol="$1"
    local quantity="$2"
    
    # Reintentar hasta 3 veces por temas de timestamp
    local attempt=1
    local max_attempts=3
    
    while [ $attempt -le $max_attempts ]; do
        # Obtener timestamp fresco justo antes de enviar
        local timestamp=$(date -u +%s%3N)
        local query_string="symbol=${symbol}&side=SELL&type=MARKET&quantity=${quantity}&timestamp=${timestamp}&recvWindow=5000"
        local signature=$(get_signature "$query_string")
        
        log "     Intento ${attempt}/${max_attempts}..."
        
        local result=$(curl -s -X POST "${BINANCE}/api/v3/order" \
            -H "X-MBX-APIKEY: ${BINANCE_API_KEY}" \
            -d "${query_string}&signature=${signature}")
        
        local status=$(echo "$result" | jq -r '.status // "ERROR"')
        local code=$(echo "$result" | jq -r '.code // 0')
        
        # Si éxito, retornar inmediatamente
        if [ "$status" = "FILLED" ] || [ "$status" = "PARTIALLY_FILLED" ]; then
            echo "$result"
            return 0
        fi
        
        # Si es error de timestamp (-1021), reintentar con nuevo timestamp
        if [ "$code" = "-1021" ] && [ $attempt -lt $max_attempts ]; then
            log "     Timestamp error, reintentando..."
            sleep 1
            attempt=$((attempt + 1))
            continue
        fi
        
        # Si es otro error o último intento, retornar resultado
        echo "$result"
        return 0
    done
    
    echo '{"status":"ERROR","msg":"Max retries exceeded"}'
}

# ============================================
# 🎯 MAIN - VERIFICAR Y CERRAR SLOTS
# ============================================

log "╔═══════════════════════════════════════════════════════╗"
log "║  🚨 EMERGENCY CLOSE - SL CRUZADO                      ║"
log "╚═══════════════════════════════════════════════════════╝"

closed_count=0
total_pnl=0
report=""

for COIN in "${COINS[@]}"; do
    STATE_FILE="$WORKSPACE/crypto-bots/${COIN}-trade-state.json"
    
    if [ ! -f "$STATE_FILE" ]; then
        log "⚠️  ${COIN}: No state file found, skipping..."
        continue
    fi
    
    log "🔍 Revisando ${COIN}..."
    
    # Leer slots activos
    active_slots=$(jq -c '.slots[] | select(.status == "ACTIVE")' "$STATE_FILE" 2>/dev/null)
    
    if [ -z "$active_slots" ] || [ "$active_slots" = "" ]; then
        log "  ✅ ${COIN}: No active slots"
        continue
    fi
    
    # Obtener precio actual
    current_price=$(get_current_price "$COIN")
    log "  💰 ${COIN} current price: \$${current_price}"
    
    # Revisar cada slot activo
    while IFS= read -r slot; do
        [ -z "$slot" ] && continue
        
        slot_id=$(echo "$slot" | jq -r '.slotId')
        entry_price=$(echo "$slot" | jq -r '.entryPrice')
        sl=$(echo "$slot" | jq -r '.stopLoss')
        quantity=$(echo "$slot" | jq -r '.quantity')
        tp1_done=$(echo "$slot" | jq -r '.tp1Done')
        
        if [ -z "$sl" ] || [ "$sl" = "null" ] || [ "$sl" = "0" ]; then
            log "  ⚠️  Slot ${slot_id}: No SL definido, skipping..."
            continue
        fi
        
        # Calcular si SL está cruzado
        sl_crossed=$(echo "$current_price <= $sl" | bc -l)
        
        if [ "$sl_crossed" -eq 1 ]; then
            log "  🔴 SLOT ${slot_id} - SL CRUZADO! (\$${current_price} <= \$${sl})"
            
            # Calcular distancia al SL (%)
            dist_pct=$(echo "scale=2; ((${entry_price} - ${current_price}) / (${entry_price} - ${sl})) * 100" | bc)
            log "     Distancia al SL: ${dist_pct}%"
            
            # Ejecutar cierre de emergencia
            log "     🚨 Ejecutando market sell de ${quantity} ${COIN}..."
            
            sell_result=$(place_market_sell "${COIN}USDT" "$quantity")
            
            # Verificar resultado
            sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"')
            error_msg=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
            
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
                
                log "     ✅ CERRADO: Exit=\$${exit_price}, P&L=\$${pnl}"
                
                # Actualizar estado del slot
                tmp_file=$(mktemp)
                jq --argjson sid "$slot_id" '
                    .slots = [.slots[] | if .slotId == $sid then .status = "CLOSED_SL_EMERGENCY" else . end]
                ' "$STATE_FILE" > "$tmp_file" && mv "$tmp_file" "$STATE_FILE"
                
                # Agregar al reporte
                pnl_icon="🔴"
                report+="${pnl_icon} <b>${COIN} Slot ${slot_id}</b>\n"
                report+="   Entry: \$${entry_price} → Exit: \$${exit_price}\n"
                report+="   SL: \$${sl} (cruzado ${dist_pct}%)\n"
                report+="   P&L: \$${pnl}\n\n"
                
                closed_count=$((closed_count + 1))
                total_pnl=$(awk -v t="$total_pnl" -v p="$pnl" 'BEGIN {printf "%.8f", t + p}')
                
                # Pequeño delay entre orders
                sleep 1
            else
                log "     ❌ ERROR al cerrar: $sell_result ($error_msg)"
                report+="❌ <b>${COIN} Slot ${slot_id}</b>: ERROR - $error_msg\n\n"
            fi
        else
            log "  🟢 Slot ${slot_id}: OK (SL no cruzado)"
        fi
    done <<< "$active_slots"
done

# ============================================
# 📊 REPORTE FINAL
# ============================================

log "╔═══════════════════════════════════════════════════════╗"
log "║  REPORTE FINAL                                        ║"
log "╚═══════════════════════════════════════════════════════╝"
log "Slots cerrados: ${closed_count}"
log "P&L Total: \$${total_pnl}"

# Enviar Telegram
if [ $closed_count -gt 0 ]; then
    total_pnl_fmt=$(awk -v p="$total_pnl" 'BEGIN {printf "%.2f", p}')
    pnl_icon="🔴"
    
    notify "EMERGENCY_CLOSE_SL" "🚨 **EMERGENCY CLOSE - SL CRUZADO**

Se cerraron ${closed_count} slots con Stop Loss cruzado:

${report}
**📊 Resumen:**
• Slots cerrados: ${closed_count}
• P&L Total: ${pnl_icon} \$${total_pnl_fmt}
• Razón: Prevención de mayores pérdidas

⚠️ Los slots se marcaron como CLOSED_SL_EMERGENCY para no re-entrar automáticamente.

_Generated by Perrobotillo Emergency System_ 🐕"
fi

log "✅ Emergency close completado"
