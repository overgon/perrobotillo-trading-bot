#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  ⚠️  EARLY WARNING SL ALERT - PREVENIR SL HITS                              ║
# ║  Notifica cuando trade está al 80% de distancia al SL                        ║
# ║  Uso: early-warning-alert.sh                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${WORKSPACE:-$SCRIPT_DIR/..}"

LOG_FILE="$WORKSPACE/logs/early-warning-alert.log"
WARNING_THRESHOLD=0.80  # 80% de distancia al SL

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE" 2>/dev/null || true
}

send_telegram() {
    local message="$1"
    # Usar notify.sh centralizado si existe
    if [ -f "$WORKSPACE/crypto-bots/notify.sh" ]; then
        source "$WORKSPACE/crypto-bots/notify.sh"
        notify "EARLY_WARNING" "$message"
    fi
}

# Load state files
COINS=("BTC" "ETH" "BNB" "SOL" "ZEC" "XRP" "AVAX")

log "║  ⚠️ EARLY WARNING SL CHECK                            ║"

warnings=()
for coin in "${COINS[@]}"; do
    state_file="$WORKSPACE/crypto-bots/${coin}-trade-state.json"
    if [ ! -f "$state_file" ]; then
        continue
    fi

    active_slots=$(jq -r '.slots[] | select(.status == "ACTIVE") | "\(.slotId)|\(.entryPrice)|\(.stopLoss // .sl // 0)"' "$state_file" 2>/dev/null || echo "")
    if [ -z "$active_slots" ]; then
        continue
    fi

    while IFS='|' read -r slot_id entry_price sl; do
        if [ -z "$sl" ] || [ "$sl" = "null" ]; then
            log "  ⚠️  Slot ${slot_id}: No SL definido, skipping..."
            continue
        fi

        # Get current price from Binance
        current_price=$(curl -s "https://api.binance.com/api/v3/ticker/price?symbol=${coin}USDT" | jq -r '.price // "0"' 2>/dev/null || echo "0")

        if [ "$current_price" = "0" ]; then
            log "  ⚠️  Slot ${slot_id}: Current price unavailable"
            continue
        fi

        # Calculate distance to SL
        # For long positions: distance = (entry - current) / (entry - sl)
        # If current == sl, distance = 1.0 (100%)
        # If current == entry, distance = 0.0 (0%)
        distance_pct=$(awk "BEGIN {
            denom = $entry_price - $sl
            if (denom == 0) { print 0 }
            else { print ($entry_price - $current_price) / denom }
        }" 2>/dev/null || echo "0")

        # Check if in warning zone (80-99%)
        in_warning=$(awk "BEGIN {print ($distance_pct >= $WARNING_THRESHOLD && $distance_pct < 1.0) ? 1 : 0}" 2>/dev/null || echo "0")
        if [ "$in_warning" = "1" ]; then
            distance_pct_display=$(awk "BEGIN {printf \"%.1f\", $distance_pct * 100}")
            log "⚠️ ${coin} Slot ${slot_id}: ${distance_pct_display}% al SL"
            warnings+=("${coin} Slot ${slot_id}: ${distance_pct_display}% al SL")
        fi

        # Check if already crossed SL (>100%)
        crossed=$(awk "BEGIN {print ($distance_pct >= 1.0) ? 1 : 0}" 2>/dev/null || echo "0")
        if [ "$crossed" = "1" ]; then
            log "🔴 ${coin} Slot ${slot_id}: SL CRUZADO - Considerar emergency close"
            warnings+=("🔴 ${coin} Slot ${slot_id}: SL CRUZADO")
        fi
    done <<< "$active_slots"
done

# Send alert if there are warnings
if [ ${#warnings[@]} -gt 0 ]; then
    message="⚠️ **SLOTS EN RIESGO**\n"
    for w in "${warnings[@]}"; do
        message+="${w}\n"
    done
    message+="\n80-99%: trailing stop | 100%+: emergency close 🐕"
    send_telegram "$message"
    log "✅ Alerta enviada"
else
    log "✅ No hay slots en zona de riesgo"
fi
