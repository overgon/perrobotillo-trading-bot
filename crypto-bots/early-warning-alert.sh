#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  ⚠️ EARLY WARNING SL ALERT - PREVENIR SL HITS         ║
# ║  Notifica cuando trade está al 80% de distancia al SL ║
# ╚═══════════════════════════════════════════════════════╝

set -e

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="$HOME/.openclaw/secrets"
LOGS="$HOME/.openclaw/logs"
BINANCE="https://api.binance.com"

source "$SECRETS/binance.env"

COINS=("BTC" "ETH" "SOL" "LINK" "XRP" "BNB" "AVAX")
WARNING_THRESHOLD=0.80  # 80% de distancia al SL

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [EARLY-WARNING] $1" | tee -a "$LOGS/early-warning.log"
}

notify() {
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

get_current_price() {
    local symbol="$1"
    curl -s "${BINANCE}/api/v3/ticker/price?symbol=${symbol}USDT" 2>/dev/null | jq -r '.price'
}

log "╔═══════════════════════════════════════════════════════╗"
log "║  ⚠️ EARLY WARNING SL CHECK                            ║"
log "╚═══════════════════════════════════════════════════════╝"

warnings=()

for COIN in "${COINS[@]}"; do
    STATE_FILE="$WORKSPACE/crypto-bots/${COIN}-trade-state.json"
    
    if [ ! -f "$STATE_FILE" ]; then
        continue
    fi
    
    # Obtener slots activos
    active_slots=$(jq -c '.slots[] | select(.status == "ACTIVE")' "$STATE_FILE" 2>/dev/null || echo "")
    
    if [ -z "$active_slots" ]; then
        continue
    fi
    
    # Obtener precio actual
    current_price=$(get_current_price "$COIN")
    
    while IFS= read -r slot; do
        [ -z "$slot" ] && continue
        
        slot_id=$(echo "$slot" | jq -r '.slotId')
        entry_price=$(echo "$slot" | jq -r '.entryPrice')
        sl=$(echo "$slot" | jq -r '.stopLoss')
        
        if [ -z "$sl" ] || [ "$sl" = "null" ] || [ "$sl" = "0" ]; then
            continue
        fi
        
        # Calcular distancia al SL (0% = entry, 100% = SL hit)
        if (( $(echo "$entry_price > $sl" | bc -l) )); then
            # LONG position
            distance_pct=$(echo "scale=4; (${entry_price} - ${current_price}) / (${entry_price} - ${sl})" | bc)
        else
            # SHORT position (no deberia haber, pero por si acaso)
            distance_pct=$(echo "scale=4; (${current_price} - ${entry_price}) / (${sl} - ${entry_price})" | bc)
        fi
        
        # Verificar si está en zona de warning (80-99%)
        if (( $(echo "$distance_pct >= $WARNING_THRESHOLD && $distance_pct < 1.0" | bc -l) )); then
            distance_pct_display=$(echo "scale=1; $distance_pct * 100" | bc)
            
            log "⚠️ ${COIN} Slot ${slot_id}: {distance_pct_display}% al SL"
            
            warnings+=("${COIN} Slot ${slot_id}: ${distance_pct_display}% al SL")
        fi
        
        # Verificar si YA cruzó SL (>100%)
        if (( $(echo "$distance_pct >= 1.0" | bc -l) )); then
            log "🔴 ${COIN} Slot ${slot_id}: SL CRUZADO - Considerar emergency close"
            warnings+=("🔴 ${COIN} Slot ${slot_id}: SL CRUZADO")
        fi
        
    done <<< "$active_slots"
done

# Enviar alerta si hay warnings
if [ ${#warnings[@]} -gt 0 ]; then
    message="⚠️ <b>EARLY WARNING - SLOTS EN RIESGO</b>\n\n"
    
    for w in "${warnings[@]}"; do
        message+="${w}\n"
    done
    
    message+="\n<b>Acción recomendada:</b>\n"
    message+="• 80-99%: Monitorear de cerca, considerar trailing stop\n"
    message+="• 100%+: Emergency close inmediato\n"
    
    notify "$message"
    log "✅ Alerta enviada"
else
    log "✅ No hay slots en zona de riesgo"
fi
