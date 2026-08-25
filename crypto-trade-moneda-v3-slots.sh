#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🤖 CRYPTO TRADE BOT V3 - MULTI-SLOT SYSTEM           ║
# ║  Soporta hasta 3 trades simultáneos por moneda        ║
# ╚═══════════════════════════════════════════════════════╝
#
# Uso:
#   $0 <SYMBOL>
#
# Ejemplos:
#   ./crypto-trade-moneda-v3-slots.sh BTC
#   ./crypto-trade-moneda-v3-slots.sh ETH
#
# Variables que consume (por orden de carga):
#  - secrets/binance.env -> BINANCE_API_KEY / BINANCE_API_SECRET
#  - config/capital-config.sh -> estrategia 20/80 (opcional)
#  - crypto-bots/dynamic-config.env -> TPs/SL/mode generado por auto-adjust (opcional)
#
# Comportamiento principal:
#  - Carga configs y ejecuta execute_cycle()
#  - Ante errores no críticos retorna 0; fallos relevantes detienen el flujo
#    por condiciones específicas, no por set -e global
#
# Archivos asociados:
#  - crypto-bots/<SYMBOL>-trade-state.json -> estado de slots
#  - crypto-bots/trade-history.json       -> histórico global
#  - crypto-bots/global-circuit-breaker.sh -> pause global cross-moneda
#  - crypto-bots/per-coin-config.env      -> parámetros por moneda (TP/SL/slots/ML)
#  - ml/ml-drawdown-check.sh              -> risk check por moneda
#

# BUG-041 FIX: set -e causa exit prematuro cuando auto_reset_slots retorna 1
# set -e  # REMOVIDO - funciones pueden retornar 1 normalmente sin ser error fatal
set +e

# ════════════════════════════════════════════════════════
# 📌 BOOTSTRAP Y VALIDACIONES INICIALES
# ════════════════════════════════════════════════════════

required_binaries=(curl jq awk date)
for b in "${required_binaries[@]}"; do
    command -v "$b" >/dev/null 2>&1 || { echo "❌ Requiere '$b'"; exit 127; }
done

SYMBOL="${1:-}"
SYMBOL="${SYMBOL^^}"

if [ -z "$SYMBOL" ]; then
    echo "❌ Uso: $0 <SYMBOL> (ej: BTC, ETH, BNB, SOL, LINK, XRP)"
    exit 1
fi

case "$SYMBOL" in
    BTC|ETH|BNB|SOL|LINK|XRP|AVAX) ;;
    *) echo "❌ SYMBOL no soportado: $SYMBOL"; exit 1 ;;
esac

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="/home/...rets"
LOGS="$HOME/.openclaw/logs"
BINANCE="https://api.binance.com"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX_SLOTS=3

# Cargar notify.sh una sola vez
if [ -f "$WORKSPACE/crypto-bots/notify.sh" ]; then
    # shellcheck source=/dev/null
    source "$WORKSPACE/crypto-bots/notify.sh"
fi

# Cargar configs dinámicas si existen (auto-adjust / ML)
if [ -f "$WORKSPACE/crypto-bots/dynamic-config.env" ]; then
    # shellcheck source=/dev/null
    source "$WORKSPACE/crypto-bots/dynamic-config.env"
fi

# Per-coin overrides
if [ -f "$WORKSPACE/crypto-bots/per-coin-config.env" ]; then
    # shellcheck source=/dev/null
    source "$WORKSPACE/crypto-bots/per-coin-config.env"
    eval "COIN_TP1=\${${SYMBOL}_TP1:-$TP1}"
    eval "COIN_TP2=\${${SYMBOL}_TP2:-$TP2}"
    eval "COIN_TP3=\${${SYMBOL}_TP3:-$TP3}"
    eval "COIN_STOP_LOSS=\${${SYMBOL}_STOP_LOSS:-$STOP_LOSS}"
    eval "COIN_POSITION_SIZE=\${${SYMBOL}_POSITION_SIZE:-$POSITION_SIZE}"
    eval "COIN_MAX_SLOTS=\${${SYMBOL}_MAX_SLOTS:-$MAX_SLOTS}"
    eval "COIN_ML_MIN_CONFIDENCE=\${${SYMBOL}_ML_MIN_CONFIDENCE:-50}"
    eval "COIN_ENABLED=\${${SYMBOL}_ENABLED:-true}"
    export TP1_PERCENT="$COIN_TP1"
    export TP2_PERCENT="$COIN_TP2"
    export TP3_PERCENT="$COIN_TP3"
    export STOP_LOSS_PERCENT="$COIN_STOP_LOSS"
    export POSITION_SIZE="$COIN_POSITION_SIZE"
    export MAX_SLOTS="$COIN_MAX_SLOTS"
    export ML_MIN_CONFIDENCE="$COIN_ML_MIN_CONFIDENCE"
    export SYMBOL_ENABLED="$COIN_ENABLED"
fi

STATE_FILE="$WORKSPACE/crypto-bots/${SYMBOL}-trade-state.json"
DAILY_PNL_FILE="$WORKSPACE/crypto-bots/${SYMBOL}-daily-pnl.json"
BOT_FILE="$WORKSPACE/crypto-bots/${SYMBOL}-bot.json"

# 🔒 Instance lock per symbol
LOCK_FILE="$WORKSPACE/crypto-bots/.${SYMBOL}-trading.lock"
mkdir -p "$(dirname "$LOCK_FILE")" 2>/dev/null || true
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "🔒 Lock activo para $SYMBOL (.${SYMBOL}-trading.lock) — otro ciclo en curso; saliendo."
    exit 0
fi

log "📌 CONFIG PER-COIN $SYMBOL: TP1=${TP1_PERCENT}% TP2=${TP2_PERCENT}% TP3=${TP3_PERCENT}% SL=${STOP_LOSS_PERCENT}% SIZE=${POSITION_SIZE}% MAX_SLOTS=$MAX_SLOTS ML_MIN=$ML_MIN_CONFIDENCE% ENABLED=$SYMBOL_ENABLED"

# ============================================
# 🔧 FUNCIONES DE LOGGING
# ============================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$SYMBOL] $1" | tee -a "$LOGS/trade-${SYMBOL}.log"
}

log_debug() {
    :
}

register_capital_move() {
    local coin="$1"
    local type="$2"
    local usdt_amount="$3"
    local quantity="$4"
    local price="$5"
    local order_id="$6"
    local note="$7"
    local balance_after="${8:-}"
    python3 /tmp/capital_helper.py "$coin" "$type" "$usdt_amount" "$quantity" "$price" "$order_id" "$note" "$balance_after" >/dev/null 2>&1 || true
}

# ============================================
# 📜 HISTORICAL TRADE LOGGING
# ============================================

HISTORY_FILE="$WORKSPACE/crypto-bots/trade-history.json"

init_trade_history() {
    if [ ! -f "$HISTORY_FILE" ]; then
        cat > "$HISTORY_FILE" << EOF
{
  "version": "2.0",
  "created": "$(date -Iseconds)",
  "updatedAt": "$(date -Iseconds)",
  "totalTrades": 0,
  "totalWins": 0,
  "totalLosses": 0,
  "totalProfitUSDT": 0,
  "totalLossUSDT": 0,
  "netPnLUSDT": 0,
  "winRate": 0,
  "bySymbol": {},
  "byDay": {},
  "trades": []
}
EOF
        return
    fi

    jq '. + {updatedAt: now | todate}' "$HISTORY_FILE" > "${HISTORY_FILE}.tmp" && mv "${HISTORY_FILE}.tmp" "$HISTORY_FILE" 2>/dev/null || true
    ensure_history_indices
}

ensure_history_indices() {
    if [ ! -f "$HISTORY_FILE" ]; then
        return
    fi

    local needs_update=0
    needs_update=$(jq -r '
      (if .version then 0 else 1 end) +
      (if .updatedAt then 0 else 1 end) +
      (if .bySymbol then 0 else 1 end) +
      (if .byDay then 0 else 1 end)
    ' "$HISTORY_FILE" 2>/dev/null)

    if [ "$needs_update" != "0" ]; then
        local tmp="/tmp/history_index_$$.json"
        jq '
          .version = (.version // "2.0") |
          .updatedAt = (.updatedAt // now | todate) |
          .bySymbol = (.bySymbol // {}) |
          .byDay = (.byDay // {}) |
          .trades = (.trades // [])
        ' "$HISTORY_FILE" > "$tmp" && mv "$tmp" "$HISTORY_FILE"
    fi
}

rebuild_history_indices() {
    [ -f "$HISTORY_FILE" ] || return 0
    ensure_history_indices
    local tmp="/tmp/history_rebuild_$$.json"
    jq '
      .bySymbol = (.trades | group_by(.symbol) | map({(.[0].symbol): {trades: length, wins: [.[] | select(.pnlUSDT+0 > 0)] | length, netPnL: ([.[].pnlUSDT] | add // 0)}}) | add // {}) |
      .byDay = (.trades | group_by(.timestamp | split("T")[0]) | map({(.[0].timestamp | split("T")[0]): {trades: length, wins: [.[] | select(.pnlUSDT+0 > 0)] | length, netPnL: ([.[].pnlUSDT] | add // 0)}}) | add // {})
    ' "$HISTORY_FILE" > "$tmp" && mv "$tmp" "$HISTORY_FILE"
}

adapter_slot_trade_to_log_trade() {
    local source="${1:-BOT}"
    local order_id="${2:-}"
    local close_type="${3:-MANUAL}"
    local entry_price="${4:-0}"
    local exit_price="${5:-0}"
    local quantity="${6:-0}"
    local pnl="${7:-0}"
    local strategy="${8:-LIQUIDATE}"
    local executed_by="${9:-MANUAL}"
    local raw_response_size="${10:-0}"
    local account_snapshot="${11:-{}}"
    local evidence="${12:-}"

    if [ "$(echo "$pnl < 0" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
        local fee_override=$(echo "$quantity * $exit_price * 0.001" | bc -l 2>/dev/null || echo 0)
    else
        local fee_override=0
    fi

    log_trade_to_history "0" "$close_type" "$entry_price" "$exit_price" "$quantity" "$pnl" \
        "$source" "$order_id" "$raw_response_size" "$strategy" "$executed_by" "$$" "$account_snapshot" "$evidence"
}

log_trade_to_history() {
    local slot_id="$1"
    local close_type="$2"
    # ✅ FIX: Normalize close_type to always have CLOSED_ prefix
    # This prevents duplicates where bot logs "CLOSED_SL" and notify.sh logs "SL"
    case "$close_type" in
        CLOSED_*) ;;  # Already has prefix
        SL) close_type="CLOSED_SL" ;;
        TP1) close_type="CLOSED_TP1" ;;
        TP2) close_type="CLOSED_TP2" ;;
        TP3) close_type="CLOSED_TP3" ;;
        SCALP) close_type="CLOSED_SCALP" ;;
        TRAILING) close_type="CLOSED_TRAILING" ;;
        MANUAL) close_type="CLOSED_MANUAL" ;;
    esac
    local entry_price="$3"
    local exit_price="$4"
    local quantity="$5"
    local pnl="$6"
    local order_id="${order_id:-}"
    local source="${source:-BOT}"
    local reason="${reason:-}"

    if [ ! -f "$HISTORY_FILE" ]; then
        log "⚠️ HISTORY_FILE no existe, no se puede loggear trade"
        return 0
    fi

    "$WORKSPACE/scripts/log_trade_to_history.py" "$slot_id" "$close_type" "$entry_price" "$exit_price" "$quantity" "$pnl" "$order_id" "$source" "$reason"
}

# ============================================
# 🛡️ ZERO TRUST - VALIDACIONES
# ============================================

check_binance_system_status() {
    # Verificar si Binance está en mantenimiento
    # API: https://api.binance.com/sapi/v1/system/status
    # status: 0 = normal, 1 = mantenimiento
    
    local status_response=$(curl -s --max-time 5 "https://api.binance.com/sapi/v1/system/status" 2>/dev/null)
    local status=$(echo "$status_response" | jq -r '.status // 0')
    local msg=$(echo "$status_response" | jq -r '.msg // "unknown"')
    
    if [ "$status" = "1" ]; then
        log "⚠️ BINANCE EN MANTENIMIENTO: $msg"
        log "  Pausando trading hasta próximo cycle"
        return 1  # Indica que hay mantenimiento
    elif [ "$status" = "0" ]; then
        log "✅ Binance Status: NORMAL"
        return 0  # Todo normal
    else
        log "⚠️ No se pudo verificar status de Binance (status=$status)"
        log "  Continuando con precaución"
        return 0  # Continuar por defecto si no se puede verificar
    fi
}

get_signature() {
    echo -n "$1" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}'
}

get_balance() {
    local symbol="$1"

    if [ -z "${BINANCE_API_KEY:-}" ] || [ -z "${BINANCE_API_SECRET:-}" ]; then
        local secrets_file="$HOME/.openclaw/secrets/binance.env"
        if [ -f "$secrets_file" ]; then
            # shellcheck source=/dev/null
            source "$secrets_file"
        fi
    fi

    if [ -z "${BINANCE_API_KEY:-}" ] || [ -z "${BINANCE_API_SECRET:-}" ]; then
        log_debug "⚠️ Balance API error: credenciales no cargadas"
        echo "0"
        return
    fi

    local timestamp=$(date -u +%s%3N)
    local query_string="timestamp=${timestamp}&recvWindow=60000"
    local signature=$(get_signature "$query_string")
    local result=$(curl -s -w "\n%{http_code}" -X GET "${BINANCE}/api/v3/account?${query_string}&signature=${signature}" -H "X-MBX-APIKEY: ${BINANCE_API_KEY}")
    local http_code=$(echo "$result" | tail -1)
    local body=$(echo "$result" | head -n -1)

    if [ "$http_code" != "200" ]; then
        log_debug "⚠️ Balance API error: HTTP $http_code"
        echo "0"
        return
    fi

    local balance=$(echo "$body" | jq -r ".balances[] | select(.asset == \"$symbol\") | .free // \"0\"")
    [ -z "$balance" ] && balance="0"
    echo "$balance"
}

get_portfolio_value() {
    local usdt=$(get_balance "USDT")
    usdt=$(printf '%s' "$usdt" | tr -d '[:space:]')
    if ! printf '%s' "$usdt" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
        echo "0"
        return
    fi
    local total=$(printf '%.2f' "$usdt")

    for coin in BNB SOL AVAX LINK XRP; do
        local balance=$(get_balance "$coin")
        balance=$(printf '%s' "$balance" | tr -d '[:space:]')
        if ! printf '%s' "$balance" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
            continue
        fi
        awk -v b="$balance" 'BEGIN {exit (b <= 0) ? 1 : 0}' || continue
        local price
        price=$(curl -sf "${BINANCE}/api/v3/ticker/price?symbol=${coin}USDT" | jq -r '.price // empty' 2>/dev/null || true)
        [ -n "$price" ] || continue
        price=$(printf '%s' "$price" | tr -d '[:space:]' | tr -d ',')
        printf '%s' "$price" | grep -qE '^[0-9]+(\.[0-9]+)?$' || continue
        local value
        value=$(awk -v b="$balance" -v p="$price" 'BEGIN {printf "%.2f", b * p}')
        total=$(awk -v t="$total" -v v="$value" 'BEGIN {printf "%.2f", t + v}')
    done

    printf '%s' "$total"
}

format_quantity() {
    local symbol="$1" quantity="$2"
    
    # Validate quantity
    [ -z "$quantity" ] || [ "$quantity" = "0" ] && { echo "0"; return; }
    
    # Get stepSize from Binance with timeout and fallback
    local stepSize=""
    local retry=0
    while [ -z "$stepSize" ] && [ $retry -lt 3 ]; do
        stepSize=$(curl -s -m 5 "${BINANCE}/api/v3/exchangeInfo?symbol=${symbol}USDT" 2>/dev/null | jq -r '.symbols[0].filters[] | select(.filterType == "LOT_SIZE") | .stepSize')
        retry=$((retry + 1))
        [ -z "$stepSize" ] || [ "$stepSize" = "null" ] && sleep 0.5
    done
    
    # Fallback stepSize if API fails
    [ -z "$stepSize" ] || [ "$stepSize" = "null" ] && {
        # Common fallbacks by symbol
        case "$symbol" in
            LINK|SOL|AVAX) stepSize="0.01000000" ;;
            BNB) stepSize="0.00100000" ;;
            XRP) stepSize="0.10000000" ;;
            BTC) stepSize="0.00001000" ;;
            ETH) stepSize="0.00010000" ;;
            *) stepSize="0.00001000" ;;
        esac
    }
    
    # Calculate decimals from stepSize
    local decimals=5
    if [[ "$stepSize" == "0.00000100" ]]; then
        decimals=6
    elif [[ "$stepSize" == "0.00010000" ]]; then
        decimals=4
    elif [[ "$stepSize" == "0.00100000" ]]; then
        decimals=3
    elif [[ "$stepSize" == "0.01000000" ]]; then
        decimals=2
    elif [[ "$stepSize" == "0.10000000" ]]; then
        decimals=1
    elif [[ "$stepSize" == "1.00000000" ]]; then
        decimals=0
    fi
    
    # BUG-043 FIX: Round quantity to stepSize (not just format decimals)
    # XRP has stepSize=0.1, so 14.59427 must become 14.6 (multiple of 0.1)
    if [ "$decimals" -lt 5 ]; then
        # Round to stepSize multiple
        local step_value=$(echo "$stepSize" | sed 's/^0*//' | sed 's/\.$//')
        quantity=$(awk -v q="$quantity" -v s="$stepSize" 'BEGIN {printf "%.8f", int(q/s+0.5)*s}')
    fi
    
    # Format with proper decimals and ensure leading zero
    local formatted=$(printf "%.${decimals}f" "$quantity" 2>/dev/null)
    [ -z "$formatted" ] && formatted="0.00000000"
    
    echo "$formatted" | sed 's/^\./0./'
}

# ============================================
# 📊 MULTI-SLOT MANAGEMENT
# ============================================

init_slots() {
    if [ ! -f "$STATE_FILE" ]; then
        log "📁 Creando state file con ${MAX_SLOTS} slots..."
        cat > "$STATE_FILE" << EOF
{
  "symbol": "$SYMBOL",
  "maxSlots": $MAX_SLOTS,
  "slots": [
    {"slotId": 1, "status": "READY", "type": "NONE", "orderId": null, "entryPrice": null, "quantity": null, "usdtSpent": null, "stopLoss": null, "tp1": null, "tp2": null, "tp3": null, "tp1Done": false, "tp2Done": false, "tp3Done": false, "tp1Pct": 0.35, "tp2Pct": 0.30, "tp3Pct": 0.30, "timestamp": null},
    {"slotId": 2, "status": "READY", "type": "NONE", "orderId": null, "entryPrice": null, "quantity": null, "usdtSpent": null, "stopLoss": null, "tp1": null, "tp2": null, "tp3": null, "tp1Done": false, "tp2Done": false, "tp3Done": false, "tp1Pct": 0.35, "tp2Pct": 0.30, "tp3Pct": 0.30, "timestamp": null},
    {"slotId": 3, "status": "READY", "type": "NONE", "orderId": null, "entryPrice": null, "quantity": null, "usdtSpent": null, "stopLoss": null, "tp1": null, "tp2": null, "tp3": null, "tp1Done": false, "tp2Done": false, "tp3Done": false, "tp1Pct": 0.35, "tp2Pct": 0.30, "tp3Pct": 0.30, "timestamp": null}
  ],
  "lastUpdated": "$(date -Iseconds)"
}
EOF
    fi
}

get_available_slot() {
    # 🛑 FIX: Verificar GLOBAL PAUSE FLAG antes de abrir NUEVOS trades
    # PERMITIR gestión de trades activos (TP/SL) incluso con pause flag
    GLOBAL_PAUSE_FILE="${WORKSPACE}/crypto-bots/global-pause-flag.json"
    if [ -f "$GLOBAL_PAUSE_FILE" ]; then
        local pause_until=$(jq -r '.pause_until // null' "$GLOBAL_PAUSE_FILE" 2>/dev/null)
        if [ "$pause_until" != "null" ]; then
            local pause_epoch=$(date -d "$pause_until" +%s 2>/dev/null || echo 0)
            local now_epoch=$(date +%s)
            if [ $now_epoch -lt $pause_epoch ]; then
                local remaining_mins=$(( (pause_epoch - now_epoch) / 60 ))
                log "🛑 PAUSE FLAG ACTIVO - No abrir NUEVOS trades (restan ${remaining_mins} min)"
                log "   Trigger: $(jq -r '.triggered_by // "unknown"' "$GLOBAL_PAUSE_FILE")"
                log "   ⚠️  Trades activos SIGUEN gestionándose (TP/SL sí se ejecutan)"
                # 🛑 FIX: Retornar 0 para indicar NO slot disponible (evita abrir nuevos trades)
                echo "0"
                return
            else
                log "✅ Pause flag expirado, reanudando trading"
                # Limpiar pause flag expirado
                echo '{}' > "$GLOBAL_PAUSE_FILE"
            fi
        fi
    fi
    
    local slot_id=$(jq -r '.slots[] | select(.status == "READY") | .slotId' "$STATE_FILE" | head -1)
    echo "${slot_id:-0}"
}

get_active_slots_count() {
    local count
    count=$(jq '[.slots[] | select(.status == "ACTIVE")] | length' "$STATE_FILE" 2>/dev/null) || true
    if [[ "$count" =~ ^[0-9]+$ ]]; then
        echo "$count"
    else
        echo "0"
    fi
}

get_slot_data() {
    local slot_id="$1"
    jq ".slots[] | select(.slotId == $slot_id)" "$STATE_FILE"
}

update_slot_status() {
    local slot_id="$1"
    local status="$2"
    local json_file="$STATE_FILE"
    
    jq --argjson sid "$slot_id" --arg status "$status" --arg updated "$(date -Iseconds)" \
       '.slots = [.slots[] | if .slotId == $sid then .status = $status else . end] | .lastUpdated = $updated' \
       "$json_file" > /tmp/state_$$.json && mv /tmp/state_$$.json "$json_file"
}

update_slot_field() {
    local slot_id="$1"
    local field="$2"
    local value="$3"
    local json_file="$STATE_FILE"

    [ -z "$slot_id" ] && { log "❌ update_slot_field: slot_id vacío"; return 1; }
    [ -z "$field" ] && { log "❌ update_slot_field: field vacío"; return 1; }

    # Nono resetear campos de trade activo sin antes cerrar
    if [ "$field" = "status" ] && [ "$value" = "READY" ]; then
        local current_status=$(jq -r ".slots[] | select(.slotId == $slot_id) | .status" "$json_file" 2>/dev/null || echo "UNKNOWN")
        if [ "$current_status" != "CLOSED_SCALP" ] && [ "$current_status" != "CLOSED_SL" ] && [ "$current_status" != "CLOSED_TP" ] && [ "$current_status" != "CLOSED_TP2" ] && [ "$current_status" != "CLOSED_TP3" ] && [ "$current_status" != "CLOSED_TRAILING" ]; then
            log "❌ update_slot_field: bloqueado reset a READY desde status=$current_status para slot=$slot_id"
            return 1
        fi
    fi

    log "DEBUG: update_slot_field slot=$slot_id field=$field value=$value"

    # Determinar tipo de valor
    local jq_update=""
    local jq_type=""

    # Booleanos
    if [ "$value" = "true" ] || [ "$value" = "false" ]; then
        jq_update='.slots = [.slots[] | if (.slotId | tostring) == $sid then .[$field] = ($val == "true") else . end]'
        jq_type="BOOLEAN"
        log "  → Tipo: BOOLEAN"
    # Numbers: digits, dots, signs and e/E scientific
    elif echo "$value" | grep -qE '^-?[0-9]+\.?[0-9]*([eE][+-]?[0-9]+)?$'; then
        jq_update='.slots = [.slots[] | if (.slotId | tostring) == $sid then .[$field] = ($val | tonumber) else . end]'
        jq_type="NUMERIC"
        log "  → Tipo: NUMERIC"
    else
        jq_update='.slots = [.slots[] | if (.slotId | tostring) == $sid then .[$field] = $val else . end]'
        jq_type="STRING"
        log "  → Tipo: STRING"
    fi

    # Ejecutar jq
    if jq --arg sid "$slot_id" --arg field "$field" --arg val "$value" \
       "$jq_update" \
       "$json_file" > /tmp/state_$$.json 2>/tmp/jq_error_$$.txt; then
        mv /tmp/state_$$.json "$json_file"
        log "  ✅ Slot $slot_id actualizado: $field = $value"
    else
        local jq_error=$(cat /tmp/jq_error_$$.txt 2>/dev/null || echo "unknown jq error")
        log "  ❌ jq falló en update_slot_field: slot=$slot_id field=$field value=$value - $jq_error"
        rm -f /tmp/state_$$.json /tmp/jq_error_$$.txt
        return 1
    fi

    rm -f /tmp/jq_error_$$.txt
    return 0
}

# ============================================
# 💰 FUNCIONES DE EJECUCIÓN
# ============================================

# ============================================
# 💰 ACTUALIZAR PnL DESPUÉS DE CIERRE
# ============================================

update_pnl_after_close() {
    local slot_id="$1"
    local close_type="$2"  # TP1, TP2, TP3, SL
    local entry_price="$3"
    local exit_price="$4"
    local quantity="$5"
    local fee_usd="$6"
    
    init_daily_pnl
    
    # Calcular PnL
    local pnl=$(awk -v e="$entry_price" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" \
        'BEGIN { 
            if (e > 0) {
                pnl = ((x - e) * q) - f
                printf "%.8f", pnl
            } else {
                print "0"
            }
        }')
    
    # LOG TO HISTORY (NEW)
    log_trade_to_history "$slot_id" "$close_type" "$entry_price" "$exit_price" "$quantity" "$pnl"
    
    # Leer PnL actual
    local current_pnl=$(jq -r '.netProfitUSDT // 0' "$DAILY_PNL_FILE")
    local current_trades=$(jq -r '.trades // 0' "$DAILY_PNL_FILE")
    local current_wins=$(jq -r '.wins // 0' "$DAILY_PNL_FILE")
    local current_losses=$(jq -r '.losses // 0' "$DAILY_PNL_FILE")
    local current_profit=$(jq -r '.profitUSDT // 0' "$DAILY_PNL_FILE")
    local current_loss=$(jq -r '.lossUSDT // 0' "$DAILY_PNL_FILE")
    
    # Actualizar contadores
    local new_trades=$((current_trades + 1))
    local new_pnl=$(awk -v c="$current_pnl" -v p="$pnl" 'BEGIN {printf "%.8f", c + p}')
    
    # Determinar si fue win o loss
    local is_win=$(awk -v p="$pnl" 'BEGIN {print (p > 0) ? 1 : 0}')
    local new_wins=$current_wins
    local new_losses=$current_losses
    local new_profit=$current_profit
    local new_loss=$current_loss
    
    if [ "$is_win" = "1" ]; then
        new_wins=$((current_wins + 1))
        new_profit=$(awk -v c="$current_profit" -v p="$pnl" 'BEGIN {printf "%.8f", c + p}')
        log "  💰 Trade WIN: +\$${pnl}"
    else
        new_losses=$((current_losses + 1))
        new_loss=$(awk -v c="$current_loss" -v p="$pnl" 'BEGIN {printf "%.8f", c + p}')  # pnl es negativo
        log "  🛑 Trade LOSS: \$${pnl}"
    fi
    
    # Escribir actualizado
    local today=$(date +%Y-%m-%d)
    cat > "$DAILY_PNL_FILE" << EOF
{
  "symbol": "$SYMBOL",
  "date": "$today",
  "trades": $new_trades,
  "wins": $new_wins,
  "losses": $new_losses,
  "profitUSDT": $new_profit,
  "lossUSDT": $new_loss,
  "netProfitUSDT": $new_pnl,
  "winRate": $(awk -v w="$new_wins" -v t="$new_trades" 'BEGIN {if (t > 0) printf "%.2f", (w/t)*100; else print "0"}'),
  "lastUpdated": "$(date -Iseconds)"
}
EOF
    
    log "  📊 PnL actualizado: Trades=$new_trades, Wins=$new_wins, Net=\$$new_pnl"
}


init_daily_pnl() {
    local today=$(date +%Y-%m-%d)
    if [ ! -f "$DAILY_PNL_FILE" ]; then
        echo "{\"date\":\"$today\",\"pnl\":0,\"trades\":0,\"win\":0,\"loss\":0,\"loss_amount\":0}" > "$DAILY_PNL_FILE"
    else
        local file_date=$(jq -r '.date' "$DAILY_PNL_FILE")
        [ "$file_date" != "$today" ] && echo "{\"date\":\"$today\",\"pnl\":0,\"trades\":0,\"win\":0,\"loss\":0,\"loss_amount\":0}" > "$DAILY_PNL_FILE"
    fi
}

check_daily_limit() {
    init_daily_pnl
    local daily_loss=$(jq -r '.loss // 0' "$DAILY_PNL_FILE")
    local portfolio_value=$(get_portfolio_value)
    [ -z "$portfolio_value" ] || ! echo "$portfolio_value" | grep -qE '^[0-9]+(\.[0-9]+)?$' && portfolio_value=0

    if [ "$portfolio_value" = "0" ]; then
        log "❌ VALIDACIÓN FALLIDA: Portfolio = \\$0 (cálculo incorrecto)"
        log "  Abortando check de límite diario para evitar falso positivo"
        log "  🛡️ BUG-052 PREVENIDO: Límite diario cancelado por datos incompletos"
        return 0  # No abortar trading, solo saltar el check de límite
    fi

: "${MAX_DAILY_LOSS_PERCENT:=3}"
    local max_loss=$(echo "scale=2; $portfolio_value * $MAX_DAILY_LOSS_PERCENT / 100" | bc)
    
    # VALIDACIÓN 2: Portfolio mínimo razonable (> $50)
    if (( $(awk -v p="$portfolio_value" 'BEGIN {print (p < 50) ? 1 : 0}') )); then
        log "⚠️ VALIDACIÓN FALLIDA: Portfolio = \$$portfolio_value (< \$50 mínimo)"
        log "  Abortando check de límite diario (portfolio demasiado bajo)"
        return 0  # No abortar trading, solo saltar el check de límite
    fi
    
    # VALIDACIÓN 3: Verificar snapshot para calcular pérdida
    local snapshot_file="$WORKSPACE/portfolio-snapshot.json"
    if [ ! -f "$snapshot_file" ]; then
        log "⚠️ VALIDACIÓN FALLIDA: No hay snapshot de ayer"
        log "  No se puede calcular pérdida diaria sin referencia"
        log "  Abortando check de límite diario"
        return 0  # No abortar trading, solo saltar el check de límite
    fi
    
    # ============================================
    # ✅ VALIDACIONES APROBADAS - PROCEDER
    # ============================================
    
    # Check si ya se envió alerta hoy
    local alert_file="$WORKSPACE/crypto-bots/.daily_limit_alert_sent"
    local today=$(date +%Y-%m-%d)
    local last_alert=""
    [ -f "$alert_file" ] && last_alert=$(cat "$alert_file")
    
    # Check si emergency close ya se ejecutó hoy
    local emergency_file="$WORKSPACE/crypto-bots/.emergency_close_sent"
    local last_emergency=""
    [ -f "$emergency_file" ] && last_emergency=$(cat "$emergency_file")
    
    if (( $(awk -v p="$portfolio_value" -v d="$daily_loss" 'BEGIN {print (d >= p * '"$MAX_DAILY_LOSS_PERCENT"' / 100) ? 1 : 0}') )); then
        log "❌ Límite diario alcanzado (\$${daily_loss} / \$${max_loss})"
        
        # Ejecutar emergency close UNA VEZ por día
        if [ "$last_emergency" != "$today" ]; then
            log "🚨 Ejecutando emergency_close_all()..."
            "$WORKSPACE/emergency-close-all.sh" &
            echo "$today" > "$emergency_file"
            log "✅ Emergency close iniciado (una vez por día)"
        else
            log "⏭️ Emergency close ya se ejecutó hoy, skip"
        fi
        
        # Solo enviar alerta UNA VEZ por día
        if [ "$last_alert" != "$today" ]; then
            notify "DAILY_LIMIT|$SYMBOL" "⚠️ LÍMITE DIARIO - $SYMBOL

Pérdida: \$${daily_loss} | Límite (3% de \$${portfolio_value}): \$${max_loss}

Emergency close ejecutado. Trading detenido hasta mañana. 🛡️"
            echo "$today" > "$alert_file"
            log "✅ Alerta de límite diario enviada (una vez por día)"
        else
            log "⏭️ Alerta de límite diario ya enviada hoy, skip"
        fi
        return 1
    fi
    return 0
}

place_buy_order_market() {
    local symbol="$1" quantity="$2"
    
    # Generar timestamp inmediatamente antes de usar
    local timestamp=$(date -u +%s%3N)
    local query_string="symbol=${symbol}USDT&side=BUY&type=MARKET&quantity=${quantity}&timestamp=${timestamp}&recvWindow=20000"
    local signature=$(get_signature "$query_string")
    
    # Ejecutar con timeout de 15 segundos y retry
    # Timeout extendido + retry logic
    local max_retries=2
    local attempt=0
    local result=""
    local http_code=""
    
    while [ $attempt -le $max_retries ]; do
    local result=$(curl -s -m 15 -w "\n%{http_code}" -X POST "${BINANCE}/api/v3/order?${query_string}&signature=${signature}" -H "X-MBX-APIKEY: ${BINANCE_API_KEY}")
        http_code=$(echo "$result" | tail -1)
        
        # Si HTTP 200 o error de Binance (no de red), salir del loop
        if [ "$http_code" = "200" ] || [ "$http_code" = "403" ] || [ "$http_code" = "429" ]; then
            break
        fi
        
        # HTTP 000 o error de red → retry
        attempt=$((attempt + 1))
        if [ $attempt -le $max_retries ]; then
            log "⚠️  Retry $attempt/$max_retries (HTTP $http_code)..."
            sleep 1
        fi
    done
    
    local http_code=$(echo "$result" | tail -1)
    local body=$(echo "$result" | head -n -1)
    
    # Log error si hay problema de HTTP
    if [ "$http_code" != "200" ]; then
        log "❌ Binance API HTTP error: $http_code (after $attempt retries)"
        echo "{"code":"-9999","msg":"HTTP error $http_code"}"
        return
    fi
    
    echo "$body"
}

place_sell_order_market() {
    local symbol="$1" quantity="$2"
    # FIX: recortar cantidad para evitar 'too much precision' de Binance
    quantity=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q}')
    # Generate timestamp immediately before use
    local timestamp=$(date -u +%s%3N)
    local query_string="symbol=${symbol}USDT&side=SELL&type=MARKET&quantity=${quantity}&timestamp=${timestamp}&recvWindow=20000"
    local signature=$(get_signature "$query_string")
    local result=$(curl -s -m 3 -X POST "${BINANCE}/api/v3/order?${query_string}&signature=${signature}" -H "X-MBX-APIKEY: ${BINANCE_API_KEY}")
    echo "$result"
}

# ============================================
# 📈 EXECUTE LONG (MULTI-SLOT)
# ============================================

execute_long() {
    local slot_id="$1"
    local position_percent="$2"
    
    log "📈 Slot $slot_id: Ejecutando LONG con ${position_percent}% posición"
    
    # ════════════════════════════════════════════════════
    # 🧠 ML VALIDATOR - Pre-Trade Validation (Jesse AI Style)
    # ════════════════════════════════════════════════════
    
    ML_VALIDATOR="$WORKSPACE/ml/ml_validator_wrapper.py"
    PYTHON_VENV="$WORKSPACE/venv/bin/python3"
    local ml_approved="N/A"
    local ml_confidence="N/A"
    local ml_position="N/A"
    local ml_reason="N/A"
    local ml_signal="N/A"
    
    if [ -f "$ML_VALIDATOR" ]; then
        log "🧠 ML Validator: Consultando validación pre-trade (Jesse AI Pipeline)..."
        
        # Ejecutar validator con venv y capturar resultado
        ml_result=$($PYTHON_VENV "$ML_VALIDATOR" "$SYMBOL" "LONG" "NORMAL" 2>&1)
        ml_exit_code=$?
        
        log "📝 ML Exit code: $ml_exit_code"
        
        # Normalizar salida eliminando separadores decorativos del wrapper ML
        ml_result=$(echo "$ml_result" | sed 's/=\+\s*$//' | tr -d '\r')
        
        ml_approved=$(echo "$ml_result" | grep -oE 'Aprobado:[[:space:]]*(✅|❌|YES|NO|true|false)' | sed -E 's/.*Aprobado:[[:space:]]*//' | head -n1)
        ml_confidence=$(echo "$ml_result" | grep -oE 'Confianza:[[:space:]]*[0-9]+(\.[0-9]+)?%' | sed -E 's/.*Confianza:[[:space:]]*([0-9]+(\.[0-9]+)?)%/\1/' | head -n1)
        ml_signal=$(echo "$ml_result" | grep -oE 'Señal ML:[[:space:]]*(WAIT|LONG|SHORT)' | sed -E 's/.*Señal ML:[[:space:]]*//' | head -n1)
        ml_position=$(echo "$ml_result" | grep -oE 'size:[[:space:]]*[0-9]+(\.[0-9]+)?%' | sed -E 's/.*size:[[:space:]]*//;s/%//' | head -n1)
        ml_reason=$(echo "$ml_result" | grep -oE 'Razón:[[:space:]].+' | sed -E 's/.*Razón:[[:space:]]*//' | head -n1)
        
        log "🔍 ML Parseado: approved='${ml_approved:-N/A}', confidence='${ml_confidence:-N/A}%', signal='${ml_signal:-N/A}'"
        log "🔍 ML Position size: ${ml_position:-N/A}%, Razón: ${ml_reason:-N/A}"
        
        # Si ML rechaza el trade, skippear
        if [ -z "$ml_approved" ] || [ "$ml_approved" = "N/A" ] || [ "$ml_approved" = "None" ]; then
            ml_approved="❌"
        fi
        
        # 🐕 FIX: Per-coin enable/disable + ML confidence threshold
        if [ "${SYMBOL_ENABLED:-true}" = "false" ]; then
            log "❌ TRADING DESHABILITADO para $SYMBOL en per-coin-config.env"
            return 1
        fi
        
        if [ -n "$ml_confidence" ] && [ "$ml_confidence" != "N/A" ]; then
            if [ "$(printf '%s\n' "$ml_confidence < $ML_MIN_CONFIDENCE" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
                log "❌ ML confidence $ml_confidence% < $ML_MIN_CONFIDENCE% mínimo para $SYMBOL"
                return 1
            fi
        fi
        
        if [ "$ml_approved" = "❌" ] || [ "$ml_approved" = "NO" ]; then
            log "❌ ML Validator RECHAZÓ el trade"
            log "   Señal: ${ml_signal:-N/A}"
            log "   Confianza: ${ml_confidence:-N/A}%"
            log "   Razón: ${ml_reason:-No se pudo parsear respuesta ML}"
            
            # Log a archivo de rechazos
            echo "$(date -Iseconds),$SYMBOL,LONG,${ml_signal:-N/A},${ml_confidence:-0},${ml_reason:-parse_failed}" >> "$WORKSPACE/logs/ml-rejections.csv"
            
            return 1
        fi
        
        # Si ML aprueba, exigir valores numéricos válidos
        if ! printf '%s' "${ml_confidence:-0}" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
            log "❌ ML Validator RECHAZÓ el trade"
            log "   Confianza inválida: '${ml_confidence:-N/A}'"
            return 1
        fi
        
        # Si ML aprueba pero sugiere menor posición, ajustar
        if [ -n "$ml_position" ] && [ "$ml_position" != "N/A" ] && [ "$ml_position" -lt "$position_percent" ] 2>/dev/null; then
            log "⚠️ ML sugiere reducir posición: ${position_percent}% → ${ml_position}%"
            position_percent="$ml_position"
        fi
        
        log "✅ ML Validator APROBÓ trade (${ml_signal}, ${ml_confidence}% confianza, ${position_percent}% position)"
    else
        log "⚠️ ML Validator no encontrado en $ML_VALIDATOR, continuando sin validación"
    fi

    check_daily_limit || return 1

    usdt_balance=$(get_balance "USDT")
    usdt_balance=$(printf '%s' "$usdt_balance" | tr -d '[:space:]')
    if ! printf '%s' "$usdt_balance" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
        log "⚠️ Balance USDT con formato no numérico: '$usdt_balance'"
        return 1
    fi
    [ -z "$usdt_balance" ] || [ "$usdt_balance" = "0" ] && { log "⚠️ USDT balance no disponible"; return 1; }

    price=$(curl -s "${BINANCE}/api/v3/ticker/price?symbol=${SYMBOL}USDT" 2>/dev/null | jq -r '.price')
    price=$(printf '%s' "$price" | tr -d '[:space:]')
    if ! printf '%s' "$price" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
        log "⚠️ Precio con formato no numérico: '$price'"
        return 1
    fi
    [ -z "$price" ] || [ "$price" = "0" ] && { log "⚠️ Precio no disponible"; return 1; }

    order_value=$(awk -v bal="$usdt_balance" -v pct="${position_percent:-10}" 'BEGIN {printf "%.2f", bal * pct / 100}')
    if (( $(awk -v val="$order_value" -v min="10" 'BEGIN {print (val < min) ? 1 : 0}') )); then
        log "⚠️ ${position_percent:-10}% = \$${order_value} < \$10 mínimo"
        if (( $(awk -v bal="$usdt_balance" -v min="10" 'BEGIN {print (bal < min) ? 1 : 0}') )); then
            log "❌ Balance insuficiente para trade mínimo (\$${usdt_balance} < \$10)"
            return 1
        fi
        log "💡 Usando 100% del balance (\$${usdt_balance}) en vez de ${position_percent:-10}%"
        order_value="$usdt_balance"
    fi

    quantity=$(awk -v val="$order_value" -v p="$price" 'BEGIN {printf "%.8f", val / p}')
    [ -z "$quantity" ] || [ "$quantity" = "0.00000000" ] && { log "⚠️ Cantidad calculada inválida"; return 1; }
    quantity=$(format_quantity "$SYMBOL" "$quantity")

    tp1=$(echo "scale=8; $price * (1 + $TP1_PERCENT / 100)" | bc)
    tp2=$(echo "scale=8; $price * (1 + $TP2_PERCENT / 100)" | bc)
    tp3=$(echo "scale=8; $price * (1 + $TP3_PERCENT / 100)" | bc)
    sl=$(echo "scale=8; $price * (1 - $STOP_LOSS_PERCENT / 100)" | bc)

    log "💰 DEBUG: Balance USDT free: \$${usdt_balance} | Order value: \$${order_value} | Quantity: $quantity @ \$${price} | Slot $slot_id de $MAX_SLOTS"

    # Ejecutar compra y capturar resultado
    local buy_result
    buy_result=$(place_buy_order_market "$SYMBOL" "$quantity")
    local buy_status
    buy_status=$(printf '%s' "$buy_result" | jq -r '.status // empty')
    local order_id
    order_id=$(printf '%s' "$buy_result" | jq -r '.orderId // empty')
    local fill_price
    local _raw_price
    _raw_price=$(printf '%s' "$buy_result" | jq -r '.price // empty')
    if [ -n "$_raw_price" ] && [ "$_raw_price" != "0" ] && [ "$_raw_price" != "0.00000000" ]; then
        fill_price="$_raw_price"
    else
        fill_price=$(printf '%s' "$buy_result" | jq -r '.fills[0].price // empty')
    fi
    if [ -z "$fill_price" ]; then
        local cum_qty
        local first_qty
        cum_qty=$(printf '%s' "$buy_result" | jq -r '.cummulativeQuoteQty // empty')
        first_qty=$(printf '%s' "$buy_result" | jq -r '.fills[0].qty // empty')
        if [ -n "$cum_qty" ] && [ -n "$first_qty" ] && [ "$(printf '%s' "$first_qty" | tr -d '[:space:]')" != "0" ]; then
            fill_price=$(awk -v c="$cum_qty" -v q="$first_qty" 'BEGIN {printf "%.8f", c / q}')
        fi
    fi
    [ -z "$fill_price" ] && fill_price="$price"
    local usdt_spent
    usdt_spent=$(printf '%s' "$buy_result" | jq -r '.cummulativeQuoteQty // empty')
    local fee_buy
    fee_buy=$(printf '%s' "$buy_result" | jq -r '.fills[0].commission // empty')
    local total_cost
    total_cost=$(printf '%s' "$buy_result" | jq -r '.fills[0].qty // empty')
    
    if [ "$buy_status" = "NEW" ] || [ "$buy_status" = "FILLED" ]; then

        # Actualizar slot
        update_slot_field "$slot_id" "status" "ACTIVE"
        update_slot_field "$slot_id" "side" '"LONG"'
        update_slot_field "$slot_id" "strategy" '"SLOT_V3"'
        update_slot_field "$slot_id" "type" '"LONG"'
        update_slot_field "$slot_id" "orderId" "$order_id"
        update_slot_field "$slot_id" "entryPrice" "$fill_price"
        update_slot_field "$slot_id" "quantity" "$quantity"
        update_slot_field "$slot_id" "usdtSpent" "$usdt_spent"
        update_slot_field "$slot_id" "feeBuy" "$fee_buy"
        update_slot_field "$slot_id" "totalCost" "$total_cost"
        update_slot_field "$slot_id" "stopLoss" "$sl"
        update_slot_field "$slot_id" "tp1" "$tp1"
        update_slot_field "$slot_id" "tp2" "$tp2"
        update_slot_field "$slot_id" "tp3" "$tp3"
        update_slot_field "$slot_id" "timestamp" "\"$(date -Iseconds)\""
        
        # BUG-038 FIX: Notificación de apertura con ML Decision
        log "  📱 DEBUG: Preparando notificación de apertura con ML info..."
        
        # Construir sección de ML
        local ml_section=""
        if [ "$ml_approved" = "✅" ] || [ "$ml_approved" = "SÍ" ] || [ "$ml_approved" = "SI" ]; then
            ml_section="🧠 ML Validator: ✅ APROBADO
   Confianza: ${ml_confidence}% | Riesgo: ${ml_risk}
   Razón: $ml_reason"
        elif [ "$ml_approved" = "❌" ] || [ "$ml_approved" = "NO" ]; then
            ml_section="🧠 ML Validator: ❌ RECHAZADO
   Confianza: ${ml_confidence}%
   Razón: $ml_reason"
        else
            ml_section="🧠 ML Validator: ⚠️ No disponible (trade sin validación)"
        fi
        
        
        # Formato limpio para notificación
        local _fee_display="0.00"
        [ -n "$fee_buy" ] && _fee_display="$fee_buy"

        local open_msg="🟢 LONG V3 SLOT $slot_id - $SYMBOL [$CURRENT_MODE]
📦 Slot: $slot_id / $MAX_SLOTS
💰 Entry: $fill_price | Qty: $quantity BTC
💸 Costo: $usdt_spent | Fee: $_fee_display
🎯 TPs:
   TP1: $tp1 (+${TP1_PERCENT}%)
   TP2: $tp2 (+${TP2_PERCENT}%)
   TP3: $tp3 (+${TP3_PERCENT}%)
🛡️ SL: $sl (-${STOP_LOSS_PERCENT}%)
$ml_section
🚀 Trade activo - Monitoreando TPs... 🕵️"
        
        notify "OPEN|LONG|$SYMBOL|$slot_id" "$open_msg"
        log "  📱 DEBUG: Notificación de apertura enviada por notify"
        log "✅ Slot $slot_id LONG abierto: Order $order_id"
        register_capital_move "$SYMBOL" "BUY" "$usdt_spent" "$quantity" "$fill_price" "$order_id" "OPEN Slot $slot_id"
        return 0
    else
        local error=$(echo "$buy_result" | jq -r '.msg // "Unknown error"')
        log "❌ Error compra Slot $slot_id: $error"
        return 1
    fi
}

# ============================================
# 🎯 CHECK TP/SL POR SLOT
# ============================================

check_slot_tp_sl() {
    local slot_id="$1"
    local slot_data=$(get_slot_data "$slot_id")
    local status=$(echo "$slot_data" | jq -r '.status')
    
    [ "$status" != "ACTIVE" ] && return 0
    
    local type=$(echo "$slot_data" | jq -r '.type' | tr -d '"')
    local entry=$(echo "$slot_data" | jq -r '.entryPrice')
    local quantity=$(echo "$slot_data" | jq -r '.quantity')
    local tp1=$(echo "$slot_data" | jq -r '.tp1')
    local tp2=$(echo "$slot_data" | jq -r '.tp2')
    local tp3=$(echo "$slot_data" | jq -r '.tp3')
    local sl=$(echo "$slot_data" | jq -r '.stopLoss')
    local tp1_done=$(echo "$slot_data" | jq -r '.tp1Done')
    local tp2_done=$(echo "$slot_data" | jq -r '.tp2Done')
    local tp3_done=$(echo "$slot_data" | jq -r '.tp3Done')
    
    local current_price=$(curl -s "${BINANCE}/api/v3/ticker/price?symbol=${SYMBOL}USDT" 2>/dev/null | jq -r '.price')
    
    log_debug "  Slot $slot_id: Current=\$${current_price} | TP1=\$${tp1} | SL=\$${sl}"
    
    # 🎯 FASE 0: SCALPING MODE (solo mercado lateral)
    if [ "$SCALPING_ENABLED" = "true" ] && [ "$CURRENT_MODE" = "LATERAL" ]; then
        # Solo para slots NUEVOS (< 1 hora) sin TP1 done
        if [ "$tp1_done" = "false" ]; then
            local scalp_target=$(echo "scale=8; $entry * (1 + $SCALP_TARGET_PERCENT / 100)" | bc)
            local scalp_sl=$(echo "scale=8; $entry * (1 - $SCALP_SL_PERCENT / 100)" | bc)
            
            # Check SCALP TP
            if (( $(echo "$current_price >= $scalp_target" | bc -l) )); then
                log "🎯 Slot $slot_id SCALP HIT: \$${current_price} >= \$${scalp_target}"
                
                # Vender 100% para scalping
                local sell_result=$(place_sell_order_market "$SYMBOL" "$quantity")
                log "  Resultado venta SCALP: $sell_result"
                local sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"')
                
                if [ "$sell_status" = "FILLED" ]; then
                    log "  ✅ SCALP ejecutado exitosamente - Slot cerrado"
                    update_slot_status "$slot_id" "CLOSED_SCALP"
                    
                    # Calcular PnL
                    local exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0')
                    local fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0')
                    local fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
                    local fee_usd=$fee_bnb
                    if [ "$fee_asset" = "BNB" ]; then
                        fee_usd=$(awk -v b="$fee_bnb" -v p="$exit_price" 'BEGIN {printf "%.8f", b * p}')
                    fi
                    
                    # Calcular PnL ANTES de guardar
                    local pnl=$(awk -v e="$entry" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                    
                    # LOG TRADE TO HISTORY
                    log_trade_to_history "$slot_id" "CLOSED_SCALP" "$entry" "$exit_price" "$quantity" "$pnl"
                    # 🐕 FIX persistencia SCALP si log_trade_to_history falló
                    local scalp_history_check
                    scalp_history_check=$(jq --arg sy "$SYMBOL" --argjson sid "$slot_id" --arg ct "CLOSED_SCALP" '[.trades[] | select(.symbol==$sy and .slotId==$sid and .closeType==$ct)] | length' "$HISTORY_FILE" 2>/dev/null || echo 0)
                    if [ "$scalp_history_check" = "0" ]; then
                        log "  ⚠️ log_trade_to_history no persistió CLOSED_SCALP; reintento forzado"
                        sleep 1
                        log_trade_to_history "$slot_id" "CLOSED_SCALP" "$entry" "$exit_price" "$quantity" "$pnl"
                        scalp_history_check=$(jq --arg sy "$SYMBOL" --argjson sid "$slot_id" --arg ct "CLOSED_SCALP" '[.trades[] | select(.symbol==$sy and .slotId==$sid and .closeType==$ct)] | length' "$HISTORY_FILE" 2>/dev/null || echo 0)
                        if [ "$scalp_history_check" = "0" ]; then
                            log "  ❌ SEGURIDAD: history no persistió CLOSED_SCALP tras reintento; abortando cierre para evitar pérdida de datos"
                            return 1
                        fi
                    fi
                    
                    # Actualizar PnL diario
                    update_pnl_after_close "$slot_id" "SCALP" "$entry" "$exit_price" "$quantity" "$fee_usd"
                    
                    # PnL para notificación
                    local pnl_display=$(awk -v p="$pnl" 'BEGIN {printf "%.2f", p}')
                    local pnl_icon="🟢"
                    [ $(echo "$pnl < 0" | bc -l) -eq 1 ] && pnl_icon="🔴"
                    
                    # Enviar Telegram TP2 con nota de scalping
                    notify "SCALP_TP_HIT|$SYMBOL|$slot_id" "${pnl_icon} SCALP HIT - $SYMBOL 🎯

Slot: $slot_id / $MAX_SLOTS
Exit: \$${exit_price}
PnL: \$${pnl_display}
Target: ${SCALP_TARGET_PERCENT}%

✅ Ganancia rápida en mercado lateral 🚀"
                    
                    return 0  # Slot cerrado
                fi
            fi
            
            # Check SCALP SL (más tight)
            if (( $(echo "$current_price <= $scalp_sl" | bc -l) )); then
                log "🛑 Slot $slot_id SCALP SL HIT: \$${current_price} <= \$${scalp_sl}"
                # El SL normal se encargará después
            fi
        fi
    fi
    
    # FASE 1: Verificar trailing stop primero (antes de TP/SL)
    if [ "$TRAILING_STOP_ENABLED" = "true" ]; then
        local trailing_active=$(echo "$slot_data" | jq -r '.trailingStop // false')
        if [ "$trailing_active" = "true" ]; then
            local highest_price=$(echo "$slot_data" | jq -r '.highestPrice // 'null'')
            
            # 🎯 TRAILING STOP DINÁMICO CON ATR (Jesse AI Style)
            # Obtener trailing stop desde cache (calculado por trailing-stop-atr.py)
            local trailing_percent
            
            if [ "$tp2_done" = "true" ]; then
                # Después de TP2, usar ATR dinámico
                CACHE_FILE="$WORKSPACE/cache/trailing_stop_${SYMBOL}.json"
                if [ -f "$CACHE_FILE" ]; then
                    trailing_percent=$(jq -r '.trailing_stop_percent' "$CACHE_FILE" 2>/dev/null)
                    if [ -z "$trailing_percent" ] || [ "$trailing_percent" = "null" ]; then
                        trailing_percent="2.5"  # Fallback
                    fi
                    log "🎯 Trailing stop ATR para $SYMBOL: ${trailing_percent}% (TP2 done)"
                else
                    trailing_percent="2.5"  # Default si no hay cache
                fi
            else
                # Antes de TP2, trailing más tight
                trailing_percent="0.2"
            fi
            
            if [ "$highest_price" != "null" ]; then
                local trailing_stop_level=$(echo "scale=8; $highest_price * (1 - $trailing_percent / 100)" | bc)
                if (( $(echo "$current_price <= $trailing_stop_level" | bc -l) )); then
                    log "🛡️ Slot $slot_id: TRAILING STOP HIT - \$${current_price} <= \$${trailing_stop_level} (${trailing_percent}%)"
                    execute_trailing_stop "$slot_id" "$quantity"
                    return 0  # Slot cerrado, salir
                fi
            fi
        fi
    fi
    
    if [ "$type" = "LONG" ]; then
        # Check TP1 - 35% exit (MODO ACUMULACIÓN: 5% se queda)
        if [ "$tp1_done" = "false" ] && (( $(echo "$current_price >= $tp1" | bc -l) )); then
            log "✅ Slot $slot_id TP1 HIT: \$${current_price} >= \$${tp1}"
            log "  Cantidad original: $quantity"
            
            # Calcular 35% para TP1 (5% se acumula)
            local sell_qty=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.35}')
            local sell_value=$(awk -v q="$sell_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
            
            # BUG-FIX: Si 35% es menor a $10, calcular cantidad para vender mínimo $10
            # Binance requiere mínimo ~$5-10 USDT por orden (NOTIONAL filter)
            local MIN_SELL_VALUE=10
            if (( $(awk -v v="$sell_value" -v m="$MIN_SELL_VALUE" 'BEGIN {print (v < m) ? 1 : 0}') )); then
                log "  ⚠️ 35% = \$${sell_value} < \$${MIN_SELL_VALUE} mínimo de Binance"
                
                # Calcular cantidad necesaria para vender $10 USDT
                sell_qty=$(awk -v min="$MIN_SELL_VALUE" -v p="$current_price" 'BEGIN {printf "%.8f", min / p}')
                sell_value=$(awk -v q="$sell_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
                log "  🎯 Ajustado para vender mínimo \$${MIN_SELL_VALUE}: $sell_qty ($SYMBOL)"
                
                # Verificar si la cantidad ajustada excede lo disponible en el slot
                local max_sellable=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.95}')  # Máximo 95% (5% se acumula)
                if (( $(awk -v adj="$sell_qty" -v max="$max_sellable" 'BEGIN {print (adj > max) ? 1 : 0}') )); then
                    log "  ⚠️ Cantidad ajustada ($sell_qty) > 95% del slot ($max_sellable)"
                    log "  💡 Vendiendo 95% máximo del slot (5% se acumula)"
                    sell_qty="$max_sellable"
                    sell_value=$(awk -v q="$sell_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
                fi
                
                # Si aún es < $5, notificar pero intentar vender de todos modos
                if (( $(awk -v v="$sell_value" -v m="5" 'BEGIN {print (v < m) ? 1 : 0}') )); then
                    log "  ⚠️ WARNING: \$${sell_value} sigue < \$5 mínimo - Binance podría rechazar"
                else
                    log "  ✅ \$${sell_value} >= \$5 - Debería ejecutar"
                fi
            fi
            
            log "  Cantidad para vender: $sell_qty (valor: \$${sell_value})"
            local sell_qty_fmt=$(format_quantity "$SYMBOL" "$sell_qty")
            log "  Cantidad formateada: $sell_qty_fmt"
            local sell_result=$(place_sell_order_market "$SYMBOL" "$sell_qty_fmt")
            log "  Resultado venta: $sell_result"
            local sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"')
            if [ "$sell_status" = "FILLED" ]; then
                log "  ✅ TP1 ejecutado exitosamente ($sell_qty_fmt)"
                    register_capital_move "$SYMBOL" "TP1" "$sell_value" "$sell_qty" "$current_price" "$sell_order_id" "TP1 Slot $slot_id"
                
                # Calcular PnL ANTES de guardar en histórico
                local pnl=$(awk -v e="$entry" -v x="$current_price" -v q="$sell_qty" -v f="$fee_buy" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                
                # LOG TRADE TO HISTORY
                log_trade_to_history "$slot_id" "CLOSED_TP1" "$entry" "$current_price" "$sell_qty" "$pnl"
                
                # 🐕 FIX persistencia TP1 si log_trade_to_history falló
                if [ "$(jq -r --arg sy "$SYMBOL" --argjson sid "$slot_id" '[.trades[] | select(.symbol==$sy and .slotId==$sid and .closeType=="CLOSED_TP1")] | length' "$HISTORY_FILE" 2>/dev/null || echo 0)" = "0" ]; then
                    log "  ⚠️ log_trade_to_history no persistió CLOSED_TP1; reintento forzado"
                    TP1_HIST=1
                    capture_account_snapshot
                    build_trade_evidence "TP1"
                    log_trade_to_history "$slot_id" "CLOSED_TP1" "$entry" "$current_price" "$sell_qty" "$pnl"
                fi
                
                # 🐕 FIX: Actualizar quantity restante después de TP1
                local remaining_qty=$(awk -v orig="$quantity" -v sold="$sell_qty" 'BEGIN {printf "%.8f", orig - sold}')
                log "  🔄 Quantity: $quantity - $sell_qty = $remaining_qty (restante)"
                update_slot_field "$slot_id" "quantity" "$remaining_qty"
                
                # Marcar TP1 como completado
                log "  ✅ TP1 marcado como completado"
                update_slot_field "$slot_id" "tp1Done" "true"
                
                # FASE 1: TRAILING STOP - Mover SL a breakeven después de TP1
                if [ "$TRAILING_STOP_ENABLED" = "true" ]; then
                    local breakeven_sl=$(echo "scale=8; $entry * 1.002" | bc)  # Entry + 0.2%
                    log "  🛡️ TP1 done - Moviendo SL a breakeven: \$${breakeven_sl}"
                    update_slot_field "$slot_id" "stopLoss" "$breakeven_sl"
                    update_slot_field "$slot_id" "trailingStop" "true"
                    log "  ✅ Trailing stop activado (breakeven)"
                fi
                
                # 🔄 MODO RECICLAJE: Después de TP1, slot pasa a READY para nueva entrada
                if [ "$SLOT_RECYCLING_ENABLED" = "true" ]; then
                    log "  🔄 MODO RECICLAJE: Slot #$slot_id listo para reingresar en próximos ciclos"
                    log "  🔄 TP1 cerrado → Se evaluará nueva entrada tras el próximo autorefresh"
                    update_slot_field "$slot_id" "tp1Done" "false"
                    update_slot_field "$slot_id" "tp2Done" "false"
                    update_slot_field "$slot_id" "tp3Done" "false"
                    update_slot_field "$slot_id" "status" "READY"
                    update_slot_field "$slot_id" "type" "NONE"
                    update_slot_field "$slot_id" "orderId" "null"
                    update_slot_field "$slot_id" "entryPrice" "null"
                    update_slot_field "$slot_id" "quantity" "null"
                    update_slot_field "$slot_id" "usdtSpent" "null"
                    update_slot_field "$slot_id" "feeBuy" "null"
                    update_slot_field "$slot_id" "totalCost" "null"
                    update_slot_field "$slot_id" "stopLoss" "null"
                    update_slot_field "$slot_id" "tp1" "null"
                    update_slot_field "$slot_id" "tp2" "null"
                    update_slot_field "$slot_id" "tp3" "null"
                    update_slot_field "$slot_id" "highestPrice" "null"
                    update_slot_field "$slot_id" "trailingStop" "null"
                    update_slot_field "$slot_id" "timestamp" "null"

                    notify "TP1_HIT|$SYMBOL|$slot_id" "✅ TP1 HIT - $SYMBOL [35%] 🎯
Slot: $slot_id / $MAX_SLOTS
Exit: \$${current_price}
Qty: $sell_qty_fmt (35%)
PnL: \$${pnl}
🔄 MODO RECICLAJE ACTIVADO
El slot buscará nueva entrada 🚀"
                else
                    # Slot existente o reciclaje desactivado -> mantener estrategia
                    local pnl_partial=$(awk -v e="$entry" -v x="$current_price" -v q="$sell_qty" -v f="$fee_buy" 'BEGIN {printf "%.2f", ((x - e) * q) - f}')
                    notify "TP1_HIT|$SYMBOL|$slot_id" "✅ TP1 - $SYMBOL
Slot: $slot_id / $MAX_SLOTS
Exit: \$${current_price}
Vendido: $sell_qty_fmt
PnL parcial: \$${pnl_partial}
Queda para TP3 🎯
Quedan 65% para TP2/TP3 🎯"
                fi
            else
                local error=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
                log "  ❌ TP1 venta falló: $error"
                notify "TP1_FAIL|$SYMBOL|$slot_id" "⚠️ TP1 FALLÓ - $SYMBOL
Slot: $slot_id
Error: $error
El slot sigue activo y reintentará en próximos ciclos."
            fi
        fi
        
        # Check TP2 - 30% exit (solo si TP1 ya se ejecutó)
        if [ "$tp1_done" = "true" ] && [ "$tp2_done" = "false" ] && (( $(echo "$current_price >= $tp2" | bc -l) )); then
            log "✅ Slot $slot_id TP2 HIT: \$${current_price} >= \$${tp2}"
            # Calcular 30% del original (BUG-034 FIX: usar quantity del slot, NO balance total)
            local sell_qty=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.30}')
            local sell_value=$(awk -v q="$sell_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
            
            # BUG-FIX: Si 30% es menor a $10, calcular cantidad para vender mínimo $10
            local MIN_SELL_VALUE=10
            if (( $(awk -v v="$sell_value" -v m="$MIN_SELL_VALUE" 'BEGIN {print (v < m) ? 1 : 0}') )); then
                log "  ⚠️ 30% = \$${sell_value} < \$${MIN_SELL_VALUE} mínimo de Binance"
                
                # Calcular restante del slot (65% después de TP1 35%)
                local remaining_qty=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.65}')
                local remaining_value=$(awk -v q="$remaining_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
                
                # Si el restante alcanza para $10, vender el restante completo
                if (( $(awk -v r="$remaining_value" -v m="$MIN_SELL_VALUE" 'BEGIN {print (r >= m) ? 1 : 0}') )); then
                    log "  💰 Restante del slot: $remaining_qty = \$${remaining_value} (>= \$${MIN_SELL_VALUE})"
                    sell_qty="$remaining_qty"
                    sell_value="$remaining_value"
                else
                    # Calcular cantidad para $10 (aunque exceda el slot)
                    sell_qty=$(awk -v min="$MIN_SELL_VALUE" -v p="$current_price" 'BEGIN {printf "%.8f", min / p}')
                    sell_value=$(awk -v q="$sell_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
                    log "  🎯 Ajustado para vender \$${MIN_SELL_VALUE}: $sell_qty"
                    
                    # Si excede lo disponible, vender todo el restante
                    if (( $(awk -v adj="$sell_qty" -v rem="$remaining_qty" 'BEGIN {print (adj > rem) ? 1 : 0}') )); then
                        log "  ⚠️ Cantidad > restante - Vendiendo TODO el slot"
                        sell_qty="$remaining_qty"
                        sell_value=$(awk -v q="$sell_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
                    fi
                fi
            fi
            
            log "  TP2: Vendiendo $sell_qty (valor: \$${sell_value})"
            local sell_qty_fmt=$(format_quantity "$SYMBOL" "$sell_qty")
            local sell_result=$(place_sell_order_market "$SYMBOL" "$sell_qty_fmt")
            log "  Resultado venta TP2: $sell_result"
            local sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"')
            if [ "$sell_status" = "FILLED" ]; then
                log "  ✅ TP2 ejecutado exitosamente ($sell_qty_fmt)"
                    register_capital_move "$SYMBOL" "TP2" "$sell_value" "$sell_qty" "$current_price" "$sell_order_id" "TP2 Slot $slot_id"
                
                # Calcular PnL ANTES de guardar en histórico
                local pnl=$(awk -v e="$entry" -v x="$current_price" -v q="$sell_qty" -v f="$fee_buy" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                
                # LOG TRADE TO HISTORY
                log_trade_to_history "$slot_id" "CLOSED_TP2" "$entry" "$current_price" "$sell_qty" "$pnl"
                # 🐕 FIX persistencia TP2 si log_trade_to_history falló
                local tp2_history_check
                tp2_history_check=$(jq --arg sy "$SYMBOL" --argjson sid "$slot_id" --arg ct "CLOSED_TP2" '[.trades[] | select(.symbol==$sy and .slotId==$sid and .closeType==$ct)] | length' "$HISTORY_FILE" 2>/dev/null || echo 0)
                if [ "$tp2_history_check" = "0" ]; then
                    log "  ⚠️ log_trade_to_history no persistió CLOSED_TP2; reintento forzado"
                    sleep 1
                    log_trade_to_history "$slot_id" "CLOSED_TP2" "$entry" "$current_price" "$sell_qty" "$pnl"
                    tp2_history_check=$(jq --arg sy "$SYMBOL" --argjson sid "$slot_id" --arg ct "CLOSED_TP2" '[.trades[] | select(.symbol==$sy and .slotId==$sid and .closeType==$ct)] | length' "$HISTORY_FILE" 2>/dev/null || echo 0)
                    if [ "$tp2_history_check" = "0" ]; then
                        log "  ❌ SEGURIDAD: history no persistió CLOSED_TP2 tras reintento; abortando cierre para evitar pérdida de datos"
                        return 1
                    fi
                fi

                # 🐕 FIX: Actualizar quantity restante después de TP2
                local remaining_qty=$(awk -v orig="$quantity" -v sold="$sell_qty" 'BEGIN {printf "%.8f", orig - sold}')
                log "  🔄 Quantity: $quantity - $sell_qty = $remaining_qty (restante)"
                update_slot_field "$slot_id" "quantity" "$remaining_qty"
                
                # Marcar TP2 como completado
                log "  ✅ TP2 marcado como completado"
                update_slot_field "$slot_id" "tp2Done" "true"
                
                # FASE 1: TRAILING STOP - Activar trailing stop ATR después de TP2
                if [ "$TRAILING_STOP_ENABLED" = "true" ]; then
                    log "  🛡️ TP2 done - Activando trailing stop ATR dinámico"
                    update_slot_field "$slot_id" "trailingStop" "true"
                    
                    # Obtener trailing stop recomendado desde cache
                    CACHE_FILE="$WORKSPACE/cache/trailing_stop_${SYMBOL}.json"
                    if [ -f "$CACHE_FILE" ]; then
                        trailing_percent=$(jq -r '.trailing_stop_percent' "$CACHE_FILE" 2>/dev/null)
                        if [ -n "$trailing_percent" ] && [ "$trailing_percent" != "null" ]; then
                            log "  🎯 Trailing stop ATR: ${trailing_percent}% para $SYMBOL"
                        else
                            trailing_percent="2.5"
                        fi
                    else
                        trailing_percent="2.5"  # Default
                    fi
                    update_slot_field "$slot_id" "trailingPercent" "$trailing_percent"
                    log "  ✅ Trailing stop ATR activado (${trailing_percent}%)"
                fi
                
                # Calcular PnL parcial para notificación
                local pnl_partial=$(awk -v e="$entry" -v x="$current_price" -v q="$sell_qty" -v f="$fee_buy" 'BEGIN {printf "%.2f", ((x - e) * q) - f}')
                
                # BUG-036 FIX: Enviar Telegram TP2
                log "  📱 DEBUG: Preparando notificación TP2..."
                notify "TP2_HIT|$SYMBOL|$slot_id" "$(printf '✅ TP2 - %s\nSlot: %d / %d\nExit: $%s\nVendido: %s\nPnL parcial: $%.2f\nQueda para TP3 🎯' "$SYMBOL" "$slot_id" "$MAX_SLOTS" "$current_price" "$sell_qty_fmt" "$pnl_partial")"
                log "  📱 DEBUG: notify TP2 completado"
            else
                local error=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
                log "  ❌ TP2 venta falló: $error"
                
                # BUG-036 FIX: Notificar incluso si falla por NOTIONAL
                if echo "$error" | grep -q "NOTIONAL\|minimum"; then
                    log "  📱 Enviando notificación de falla NOTIONAL TP2..."
                    
                    # BUG-047 FIX: Cerrar slot si resto < $5 (evitar loop infinito)
                    local remaining_qty=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.65}')
                    local remaining_value=$(awk -v q="$remaining_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
                    
                    if (( $(echo "$remaining_value < 5" | bc -l) )); then
                        # Resto < $5 - CERRAR SLOT PARA EVITAR BUG-047
                        update_slot_field "$slot_id" "status" "CLOSED_TP2"
                        log "  ⚠️ Resto < \$5 (${remaining_value}) - Slot marcado como CLOSED_TP2"
                        log "  💡 Resto se queda como 'dust' en Binance (convertible a BNB)"
                        
                        notify "TP2_FAIL|$SYMBOL|$slot_id|BUG-047" "⚠️ TP2 FALLÓ - $SYMBOL [BUG-047 FIX]

Slot: $slot_id
Error: $error
Razón: Valor < \$5 mínimo de Binance
Resto: \$${remaining_value} (< \$5)

✅ Slot cerrado automáticamente
💡 Resto se queda como 'dust' (convertible a BNB)

🛡️ Auto-Heal v2.0"
                    else
                        # Resto >= $5 - mantener slot activo
                        notify "TP2_FAIL|$SYMBOL|$slot_id" "⚠️ TP2 FALLÓ - $SYMBOL

Slot: $slot_id
Error: $error
Razón: Valor < \$5 mínimo de Binance
ACUMULADO: 5% se queda HODL 📈

El slot permanece activo."
                    fi
                fi
            fi
        fi
        
        # Check TP3 - CIERRE TOTAL (TP1 done, TP3 pendiente, precio cruza TP3)
        # Nota: TP2 puede haber fallado por NOTIONAL, permitimos TP3 directo
        if [ "$tp1_done" = "true" ] && [ "$tp3_done" = "false" ] && (( $(echo "$current_price >= $tp3" | bc -l) )); then
            log "✅ Slot $slot_id TP3 HIT: \$${current_price} >= \$${tp3}"
            
            # BUG-042 FIX: Calcular cantidad RESTANTE real después de TP1 + TP2
            # TP1 vendió 35%, TP2 vendió 30%, queda 35%
            # TP3 vende 30% (el 5% restante se queda como acumulado)
            local tp2_done=$(echo "$slot_data" | jq -r '.tp2Done')
            local sell_qty
            
            if [ "$tp2_done" = "true" ]; then
                # TP1 + TP2 completados → vender 30% restante (deja 5% acumulado)
                sell_qty=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.30}')
                log "  📊 TP1+TP2 done → Vendiendo 30% restante (5% se queda acumulado)"
            else
                # Solo TP1 completado → vender 65% restante (deja 5% acumulado)
                sell_qty=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.65}')
                log "  📊 Solo TP1 done → Vendiendo 65% restante (5% se queda acumulado)"
            fi
            
            local sell_value=$(awk -v q="$sell_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
            
            # BUG-042 FIX: Si valor es < $5, usar get_balance() para vender 100% del restante
            # Similar a BUG-033 pero para TP3 - incluye el 5% acumulado
            if (( $(awk -v v="$sell_value" -v m="5" 'BEGIN {print (v < m) ? 1 : 0}') )); then
                log "  ⚠️ TP3 valor \$${sell_value} < \$5 mínimo de Binance"
                log "  🎯 BUG-042: Usando get_balance() para vender 100% del restante (incluye 5% acumulado)"
                
                # Obtener balance real de Binance (incluye el 5% acumulado)
                local timestamp=$(($(date +%s) * 1000))
                local recvWindow=5000
                local queryString="timestamp=$timestamp&recvWindow=$recvWindow"
                local signature=$(echo -n "$queryString" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}')
                local balance_response=$(curl -s "$BINANCE/api/v3/account?$queryString&signature=$signature" -H "X-MBX-APIKEY: $BINANCE_API_KEY")
                local balance=$(echo "$balance_response" | jq -r ".balances[] | select(.asset==\"$SYMBOL\") | .free" 2>/dev/null)
                
                if [ -n "$balance" ] && [ "$balance" != "0" ] && [ "$balance" != "0.00000000" ]; then
                    sell_qty="$balance"
                    sell_value=$(awk -v q="$sell_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
                    log "  💰 Balance real: $sell_qty ($SYMBOL) = \$${sell_value}"
                    
                    # Verificar si aún es < $5
                    if (( $(awk -v v="$sell_value" -v m="5" 'BEGIN {print (v < m) ? 1 : 0}') )); then
                        log "  ⚠️ Aún < \$5 (\$${sell_value}). Vendiendo todo de todos modos para cerrar slot."
                    fi
                else
                    log "  ⚠️ No se pudo obtener balance, usando 65% del slot"
                    sell_qty=$(awk -v q="$quantity" 'BEGIN {printf "%.8f", q * 0.65}')
                    sell_value=$(awk -v q="$sell_qty" -v p="$current_price" 'BEGIN {printf "%.2f", q * p}')
                fi
            fi
            
            log "  TP3: Vendiendo $sell_qty (valor: \$${sell_value}) - CIERRE TOTAL (5% se queda acumulado)"
            local sell_qty_fmt=$(format_quantity "$SYMBOL" "$sell_qty")
            local sell_result=$(place_sell_order_market "$SYMBOL" "$sell_qty_fmt")
            log "  Resultado venta TP3: $sell_result"
            local sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"')
            if [ "$sell_status" = "FILLED" ]; then
                log "  ✅ TP3 ejecutado exitosamente ($sell_qty_fmt) - CIERRE TOTAL 📈"
                    register_capital_move "$SYMBOL" "TP3" "$sell_value" "$sell_qty" "$current_price" "$sell_order_id" "TP3 Slot $slot_id CIERRE TOTAL"
                
                # Calcular PnL ANTES de guardar en histórico
                local pnl=$(awk -v e="$entry" -v x="$current_price" -v q="$quantity" -v f="$fee_buy" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                
                # LOG TRADE TO HISTORY
                log_trade_to_history "$slot_id" "CLOSED_TP3" "$entry" "$current_price" "$quantity" "$pnl"
                # 🐕 FIX persistencia TP3 si log_trade_to_history falló
                local tp3_history_check
                tp3_history_check=$(jq --arg sy "$SYMBOL" --argjson sid "$slot_id" --arg ct "CLOSED_TP3" '[.trades[] | select(.symbol==$sy and .slotId==$sid and .closeType==$ct)] | length' "$HISTORY_FILE" 2>/dev/null || echo 0)
                if [ "$tp3_history_check" = "0" ]; then
                    log "  ⚠️ log_trade_to_history no persistió CLOSED_TP3; reintento forzado"
                    sleep 1
                    log_trade_to_history "$slot_id" "CLOSED_TP3" "$entry" "$current_price" "$quantity" "$pnl"
                    tp3_history_check=$(jq --arg sy "$SYMBOL" --argjson sid "$slot_id" --arg ct "CLOSED_TP3" '[.trades[] | select(.symbol==$sy and .slotId==$sid and .closeType==$ct)] | length' "$HISTORY_FILE" 2>/dev/null || echo 0)
                    if [ "$tp3_history_check" = "0" ]; then
                        log "  ❌ SEGURIDAD: history no persistió CLOSED_TP3 tras reintento; abortando cierre para evitar pérdida de datos"
                        return 1
                    fi
                fi
                
                # 🐕 FIX: Actualizar quantity a 0 (o el 5% acumulado) después de TP3
                # En modo acumulación, 5% se queda en Binance, pero el slot se cierra
                local remaining_qty=$(awk -v orig="$quantity" 'BEGIN {printf "%.8f", orig * 0.05}')
                log "  🔄 Quantity restante (5% acumulado): $remaining_qty"
                # NO actualizamos quantity porque el slot se cierra, pero lo logueamos para tracking
                
                # Marcar slot como cerrado
                update_slot_field "$slot_id" "status" "CLOSED_TP3"
                log "  ✅ Slot cerrado - TP3 completado (5% acumulado en Binance)"
                
                # Marcar TP3 como completado
                log "  ✅ TP3 marcado como completado"
                update_slot_field "$slot_id" "tp3Done" "true"
                
                # Resetear contador de fallos TP3 tras éxito
                update_slot_field "$slot_id" "tp3FailCount" "0"
                
                # Actualizar PnL
                local exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0')
                local fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0')
                local fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
                local fee_usd=$fee_bnb
                if [ "$fee_asset" = "BNB" ]; then
                    fee_usd=$(awk -v b="$fee_bnb" -v p="$current_price" 'BEGIN {printf "%.8f", b * p}')
                fi
                update_pnl_after_close "$slot_id" "TP3" "$entry" "$exit_price" "$quantity" "$fee_usd"
                log "  📱 DEBUG: Después de update_pnl, antes de send_telegram" "$entry" "$exit_price" "$quantity" "$fee_usd"
                
                # Calcular PnL total para notificación
                local pnl_total=$(awk -v e="$entry" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {printf "%.2f", ((x - e) * q) - f}')
                local pnl_icon="🟢"
                [ $(echo "$pnl_total > 0" | bc -l) -eq 1 ] || pnl_icon="🔴"
                
                # BUG-036 FIX: Enviar Telegram TP3
                log "  📱 DEBUG: Preparando notificación TP3..."
                log "  📱 DEBUG: pnl_icon=$pnl_icon, exit_price=$exit_price, sell_qty_fmt=$sell_qty_fmt"
                
                # BUG-042 FIX: Determinar porcentaje vendido
                local tp3_percentage="30%"
                local tp3_note="CIERRE TOTAL"
                local acumulado_note="✅ 5% de la posición SE QUEDA en Binance (acumulado)\n💰 Vendido: 95% | Acumulado: 5%"
                
                # Si TP2 no se ejecutó, TP3 vende más
                if [ "$tp2_done" != "true" ]; then
                    tp3_percentage="65%"
                    tp3_note="CIERRE TOTAL (sin TP2)"
                    acumulado_note="✅ 5% de la posición SE QUEDA en Binance (acumulado)\n💰 Vendido: 95% | Acumulado: 5% (TP2 skip)"
                fi
                
                local tp3_msg="🎯 TP3 - $SYMBOL [Cierre total]
Slot: $slot_id / $MAX_SLOTS
Exit: \$${exit_price}
Vendido: $sell_qty_fmt
PnL: \$${pnl_total}
Mantiene 5% acumulado 📈"

                notify "TP3_HIT|$SYMBOL|$slot_id" "$tp3_msg"
                log "  📱 DEBUG: notify completado TP3"
            else
                local error=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
                log "  ❌ TP3 venta falló: $error"
                
                # 🐕 FIX: Cierre inmediato si es insufficient balance
                if echo "$error" | grep -qi "insufficient\|NOTIONAL\|minimum"; then
                    log "  ⚠️ TP3 falló por balance insuficiente - CERRANDO SLOT FORZADO"
                    # Intentar vender TODO el balance restante una última vez
                    local timestamp=$(($(date +%s) * 1000))
                    local recvWindow=5000
                    local queryString="timestamp=$timestamp&recvWindow=$recvWindow"
                    local signature=$(echo -n "$queryString" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}')
                    local balance_response=$(curl -s "$BINANCE/api/v3/account?$queryString&signature=$signature" -H "X-MBX-APIKEY: $BINANCE_API_KEY")
                    local balance=$(echo "$balance_response" | jq -r ".balances[] | select(.asset==\"$SYMBOL\") | .free" 2>/dev/null)
                    
                    local forced_close_success=false
                    if [ -n "$balance" ] && [ "$balance" != "0" ] && [ "$balance" != "0.00000000" ]; then
                        local final_sell_qty=$(format_quantity "$SYMBOL" "$balance")
                        local final_sell_result=$(place_sell_order_market "$SYMBOL" "$final_sell_qty")
                        local final_sell_status=$(echo "$final_sell_result" | jq -r '.status // "ERROR"')
                        
                        if [ "$final_sell_status" = "FILLED" ]; then
                            log "  ✅ Venta final forzada exitosa: $final_sell_qty"
                            local final_exit=$(echo "$final_sell_result" | jq -r '.fills[0].price // 0')
                            local final_fee=$(echo "$final_sell_result" | jq -r '.fills[0].commission // 0')
                            local final_fee_asset=$(echo "$final_sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
                            local final_fee_usd=$final_fee
                            if [ "$final_fee_asset" = "BNB" ]; then
                                final_fee_usd=$(awk -v b="$final_fee" -v p="$final_exit" 'BEGIN {printf "%.8f", b * p}')
                            fi
                            local final_pnl=$(awk -v e="$entry" -v x="$final_exit" -v q="$quantity" -v f="$final_fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                            log_trade_to_history "$slot_id" "CLOSED_TP3" "$entry" "$final_exit" "$quantity" "$final_pnl"
                            update_slot_field "$slot_id" "status" "CLOSED_TP3"
                            update_slot_field "$slot_id" "tp3Done" "true"
                            notify "TP3_HIT|$SYMBOL|$slot_id|FORCED" "🎯 TP3 - $SYMBOL [Cierre forzado]
Slot: $slot_id / $MAX_SLOTS
Exit: \$$final_exit
Vendido: $final_sell_qty
PnL: \$$(awk -v p="$final_pnl" 'BEGIN {printf "%.2f", p}')
✅ Cierre forzado por balance insuficiente"
                            forced_close_success=true
                        fi
                    fi
                    
                    if [ "$forced_close_success" = "false" ]; then
                        log "  ⚠️ No se pudo vender balance final - Cerrando como insuficiente"
                        local approx_pnl=$(awk -v e="$entry" -v x="$current_price" -v q="$quantity" -v f="$fee_buy" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                        log_trade_to_history "$slot_id" "CLOSED_TP3_INSUFFICIENT" "$entry" "$current_price" "$quantity" "$approx_pnl"
                        update_slot_field "$slot_id" "status" "CLOSED_TP3_INSUFFICIENT"
                        update_slot_field "$slot_id" "tp3Done" "true"
                        notify "TP3_FAIL|$SYMBOL|$slot_id|FORCED_CLOSE" "⚠️ TP3 - $SYMBOL [Cierre forzado]
Slot: $slot_id / $MAX_SLOTS
Error: $error
Razón: Balance insuficiente en el primer fallo
✅ Slot cerrado - dust queda en Binance
📝 Registrado en history como CLOSED_TP3_INSUFFICIENT"
                    fi
                    
                    update_slot_field "$slot_id" "tp3FailCount" "0"
                    return 0
                fi
                
                # 🐕 FIX: Contador de fallos TP3 + cierre forzado tras 3 intentos
                local current_tp3_fails=$(echo "$slot_data" | jq -r '.tp3FailCount // 0')
                local new_tp3_fails=$((current_tp3_fails + 1))
                update_slot_field "$slot_id" "tp3FailCount" "$new_tp3_fails"
                log "  ⚠️ TP3 fallo #$new_tp3_fails/$slot_id"
                
                if [ "$new_tp3_fails" -ge 3 ]; then
                    log "  🛑 TP3 falló 3 veces - CERRANDO SLOT FORZADO"
                    
                    # Intentar vender TODO el balance restante una última vez
                    local timestamp=$(($(date +%s) * 1000))
                    local recvWindow=5000
                    local queryString="timestamp=$timestamp&recvWindow=$recvWindow"
                    local signature=$(echo -n "$queryString" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}')
                    local balance_response=$(curl -s "$BINANCE/api/v3/account?$queryString&signature=$signature" -H "X-MBX-APIKEY: $BINANCE_API_KEY")
                    local balance=$(echo "$balance_response" | jq -r ".balances[] | select(.asset==\"$SYMBOL\") | .free" 2>/dev/null)
                    
                    local forced_close_success=false
                    if [ -n "$balance" ] && [ "$balance" != "0" ] && [ "$balance" != "0.00000000" ]; then
                        local final_sell_qty=$(format_quantity "$SYMBOL" "$balance")
                        local final_sell_result=$(place_sell_order_market "$SYMBOL" "$final_sell_qty")
                        local final_sell_status=$(echo "$final_sell_result" | jq -r '.status // "ERROR"')
                        
                        if [ "$final_sell_status" = "FILLED" ]; then
                            log "  ✅ Venta final forzada exitosa: $final_sell_qty"
                            local final_exit=$(echo "$final_sell_result" | jq -r '.fills[0].price // 0')
                            local final_fee=$(echo "$final_sell_result" | jq -r '.fills[0].commission // 0')
                            local final_fee_asset=$(echo "$final_sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
                            local final_fee_usd=$final_fee
                            if [ "$final_fee_asset" = "BNB" ]; then
                                final_fee_usd=$(awk -v b="$final_fee" -v p="$final_exit" 'BEGIN {printf "%.8f", b * p}')
                            fi
                            local final_pnl=$(awk -v e="$entry" -v x="$final_exit" -v q="$quantity" -v f="$final_fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                            log_trade_to_history "$slot_id" "CLOSED_TP3" "$entry" "$final_exit" "$quantity" "$final_pnl"
                            update_slot_field "$slot_id" "status" "CLOSED_TP3"
                            update_slot_field "$slot_id" "tp3Done" "true"
                            notify "TP3_HIT|$SYMBOL|$slot_id|FORCED" "🎯 TP3 - $SYMBOL [Cierre forzado]
Slot: $slot_id / $MAX_SLOTS
Exit: \$$final_exit
Vendido: $final_sell_qty
PnL: \$$(awk -v p="$final_pnl" 'BEGIN {printf "%.2f", p}')
✅ Cierre forzado tras 3 fallos"
                            forced_close_success=true
                        fi
                    fi
                    
                    if [ "$forced_close_success" = "false" ]; then
                        log "  ⚠️ No se pudo vender balance final - Cerrando como insuficiente"
                        # Registrar en history con PnL aproximado usando precio actual
                        local approx_pnl=$(awk -v e="$entry" -v x="$current_price" -v q="$quantity" -v f="$fee_buy" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                        log_trade_to_history "$slot_id" "CLOSED_TP3_INSUFFICIENT" "$entry" "$current_price" "$quantity" "$approx_pnl"
                        update_slot_field "$slot_id" "status" "CLOSED_TP3_INSUFFICIENT"
                        update_slot_field "$slot_id" "tp3Done" "true"
                        notify "TP3_FAIL|$SYMBOL|$slot_id|FORCED_CLOSE" "⚠️ TP3 - $SYMBOL [Cierre forzado]
Slot: $slot_id / $MAX_SLOTS
Error: $error
Razón: 3 fallos consecutivos
✅ Slot cerrado - dust queda en Binance
📝 Registrado en history como CLOSED_TP3_INSUFFICIENT"
                    fi
                    
                    # Resetear contador tras cierre forzado
                    update_slot_field "$slot_id" "tp3FailCount" "0"
                    return 0
                fi
                
                # BUG-036 FIX: Notificar incluso si falla por NOTIONAL
                if echo "$error" | grep -q "NOTIONAL\\|minimum"; then
                    log "  📱 Enviando notificación de fallo NOTIONAL TP3 (#$new_tp3_fails)..."
                    notify "TP3_FAIL|$SYMBOL|$slot_id|NOTIONAL" "⚠️ TP3 FALLÓ - $SYMBOL

Slot: $slot_id
Error: $error
Razón: Valor < \$5 mínimo de Binance
ACUMULADO: 5% se queda HODL 📈

🔧 BUG-042: El slot permanece ACTIVE. Próximo cycle intentará vender todo el balance (incluye 5% acumulado)."
                fi
            fi
        fi
        
        # Check SL - Stop Loss (cierra 100%)
        if (( $(echo "$current_price <= $sl" | bc -l) )); then
            log "🛑 Slot $slot_id SL HIT: \$${current_price} <= \$${sl}"
            local sell_result=$(place_sell_order_market "$SYMBOL" "$quantity")
            log "  Resultado venta SL: $sell_result"
            local sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"')
            if [ "$sell_status" = "FILLED" ]; then
                log "  ✅ SL ejecutado exitosamente - Slot cerrado"
        register_capital_move "$SYMBOL" "SL" "$sell_value" "$sell_qty" "$current_price" "$sell_order_id" "SL Slot $slot_id"
                update_slot_status "$slot_id" "CLOSED_SL"
                
                # Actualizar PnL
                local exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0')
                local fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0')
                local fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
                local fee_usd=$fee_bnb
                if [ "$fee_asset" = "BNB" ]; then
                    fee_usd=$(awk -v b="$fee_bnb" -v p="$current_price" 'BEGIN {printf "%.8f", b * p}')
                fi
                
                # Calcular PnL ANTES de guardar en histórico
                local pnl=$(awk -v e="$entry" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                
                # LOG TRADE TO HISTORY
                log_trade_to_history "$slot_id" "CLOSED_SL" "$entry" "$exit_price" "$quantity" "$pnl"

                # ✅ Verificación final de persistencia antes de continuar
                local history_check=$(jq --arg sy "$SYMBOL" --argjson sid "$slot_id" --arg ct "CLOSED_SL" '[.trades[] | select(.symbol==$sy and .slotId==$sid and .closeType==$ct)] | length' "$HISTORY_FILE" 2>/dev/null || echo 0)
                if [ "${history_check:-0}" = "0" ]; then
                    log "  ❌ SEGURIDAD: history no persistió CLOSED_SL tras reintento; abortando cierre para evitar pérdida de datos"
                    return 1
                fi
                
                # Marcar SL como ejecutado
                log "  🛑 SL ejecutado"
                update_slot_field "$slot_id" "status" "CLOSED_SL"
                
                # Actualizar PnL diario
                update_pnl_after_close "$slot_id" "SL" "$entry" "$exit_price" "$quantity" "$fee_usd"
                
                # Calcular PnL para notificación
                local pnl_display=$(awk -v p="$pnl" 'BEGIN {printf "%.2f", p}')
                local pnl_icon="🔴"
                [ $(echo "$pnl > 0" | bc -l) -eq 1 ] && pnl_icon="🟢"
                
                # Enviar Telegram
                notify "SL_HIT|$SYMBOL|$slot_id" "${pnl_icon} SL - $SYMBOL

Slot: $slot_id / $MAX_SLOTS
Exit: \$${exit_price}
PnL: \$${pnl_display}

Slot disponible 🔄"
                
            else
                local error=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
                log "  ❌ SL venta falló: $error"
            fi
        fi
    fi
    
    log_debug "  ✅ Slot $slot_id check completado"
}

# ============================================
# 🛡️ EJECUTAR TRAILING STOP
# ============================================

execute_trailing_stop() {
    local slot_id="$1"
    local quantity="$2"
    local slot_data=$(get_slot_data "$slot_id")
    local entry=$(echo "$slot_data" | jq -r '.entryPrice')
    local tp1_done=$(echo "$slot_data" | jq -r '.tp1Done')
    local tp2_done=$(echo "$slot_data" | jq -r '.tp2Done')
    
    # Ejecutar venta
    local sell_result=$(place_sell_order_market "$SYMBOL" "$quantity")
    log "  Resultado venta trailing: $sell_result"
    local sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"')

    if [ "$sell_status" = "FILLED" ]; then

        # Calcular PnL antes de update de estado para armar la alerta
        local exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0')
        local fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0')
        local fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
        local fee_usd=$fee_bnb
        if [ "$fee_asset" = "BNB" ]; then
            fee_usd=$(awk -v b="$fee_bnb" -v p="$exit_price" 'BEGIN {printf "%.8f", b * p}')
        fi
        local trailing_pnl=$(awk -v e="$entry" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
        local trailing_exit_display=$(awk -v p="$exit_price" 'BEGIN {printf "%.2f", p}')
        local trailing_pnl_display=$(awk -v p="$trailing_pnl" 'BEGIN {printf "%.2f", p}')
        local trailing_pnl_icon="🟢"
        [ $(echo "$trailing_pnl > 0" | bc -l) -eq 1 ] || trailing_pnl_icon="🔴"

        notify "TRAILING_STOP|$SYMBOL|$slot_id|PRECHECK_OK" "${trailing_pnl_icon} TRAILING STOP - $SYMBOL

    Slot: $slot_id / $MAX_SLOTS
    Exit: \$${trailing_exit_display}
    PnL: \$${trailing_pnl_display}
    Razón: $reason

    ✅ Ganancias aseguradas 🛡️"
        log "  ✅ Trailing stop ejecutado exitosamente - Slot cerrado"
            register_capital_move "$SYMBOL" "TRAILING" "$sell_value" "$sell_qty" "$current_price" "$sell_order_id" "Trailing stop Slot $slot_id"
        update_slot_status "$slot_id" "CLOSED_TRAILING"
        
        # LOG TRADE TO HISTORY
        log_trade_to_history "$slot_id" "CLOSED_TRAILING" "$entry" "$exit_price" "$quantity" "$pnl"
        # 🐕 FIX persistencia TRAILING si log_trade_to_history falló
        local trailing_history_check
        trailing_history_check=$(jq --arg sy "$SYMBOL" --argjson sid "$slot_id" --arg ct "CLOSED_TRAILING" '[.trades[] | select(.symbol==$sy and .slotId==$sid and .closeType==$ct)] | length' "$HISTORY_FILE" 2>/dev/null || echo 0)
        if [ "$trailing_history_check" = "0" ]; then
            log "  ⚠️ log_trade_to_history no persistió CLOSED_TRAILING; reintento forzado"
            sleep 1
            log_trade_to_history "$slot_id" "CLOSED_TRAILING" "$entry" "$exit_price" "$quantity" "$pnl"
            trailing_history_check=$(jq --arg sy "$SYMBOL" --argjson sid "$slot_id" --arg ct "CLOSED_TRAILING" '[.trades[] | select(.symbol==$sy and .slotId==$sid and .closeType==$ct)] | length' "$HISTORY_FILE" 2>/dev/null || echo 0)
            if [ "$trailing_history_check" = "0" ]; then
                log "  ❌ SEGURIDAD: history no persistió CLOSED_TRAILING tras reintento; abortando cierre para evitar pérdida de datos"
                return 1
            fi
        fi
        
        # Actualizar PnL
        local exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0')
        local fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0')
        local fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
        local fee_usd=$fee_bnb
        if [ "$fee_asset" = "BNB" ]; then
            fee_usd=$(awk -v b="$fee_bnb" -v p="$exit_price" 'BEGIN {printf "%.8f", b * p}')
        fi
        
        # Calcular PnL ANTES de guardar en histórico
        local pnl=$(awk -v e="$entry" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
        
        # LOG TRADE TO HISTORY
        log_trade_to_history "$slot_id" "CLOSED_TRAILING" "$entry" "$exit_price" "$quantity" "$pnl"
        
        # Actualizar PnL diario
        update_pnl_after_close "$slot_id" "TRAILING" "$entry" "$exit_price" "$quantity" "$fee_usd"
        
        # Calcular PnL para notificación
        local pnl_display=$(awk -v p="$pnl" 'BEGIN {printf "%.2f", p}')
        local pnl_icon="🟢"
        [ $(echo "$pnl < 0" | bc -l) -eq 1 ] && pnl_icon="🔴"
        
        # Determinar razón del cierre
        local reason
        if [ "$tp2_done" = "true" ]; then
            reason="TP2 + Trailing 2%"
        else
            reason="TP1 + Breakeven"
        fi
        
        # Enviar Telegram
        notify "TRAILING_STOP|$SYMBOL|$slot_id" "${pnl_icon} TRAILING STOP - $SYMBOL

Slot: $slot_id / $MAX_SLOTS
Exit: \$${exit_price}
PnL: \$${pnl_display}
Razón: $reason

✅ Ganancias aseguradas 🛡️"
    else
        local error=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
        log "  ❌ Trailing stop venta falló: $error"
    fi
}

# ============================================
# 🛡️ FASE 1: CHECK TRAILING STOPS
# ============================================

check_trailing_stops() {
    if [ "$TRAILING_STOP_ENABLED" != "true" ]; then
        return 0
    fi
    
    for slot_id in $(seq 1 $MAX_SLOTS); do
        local slot_index=$((slot_id - 1))
        local status=$(jq -r ".slots[$slot_index].status" "$STATE_FILE")
        
        # Solo verificar slots ACTIVE con trailing stop habilitado
        [ "$status" != "ACTIVE" ] && continue
        
        local trailing_active=$(jq -r ".slots[$slot_index].trailingStop // false" "$STATE_FILE")
        [ "$trailing_active" != "true" ] && continue
        
        local entry=$(jq -r ".slots[$slot_index].entryPrice" "$STATE_FILE")
        local quantity=$(jq -r ".slots[$slot_index].quantity" "$STATE_FILE")
        local tp1_done=$(jq -r ".slots[$slot_index].tp1Done" "$STATE_FILE")
        local tp2_done=$(jq -r ".slots[$slot_index].tp2Done" "$STATE_FILE")
        
        # Obtener precio actual
        local current_price=$(curl -s "${BINANCE}/api/v3/ticker/price?symbol=${SYMBOL}USDT" 2>/dev/null | jq -r '.price // 0')
        [ "$current_price" = "0" ] && continue
        
        # Determinar trailing percent (TP1=breakeven, TP2=2%)
        local trailing_percent
        if [ "$tp2_done" = "true" ]; then
            trailing_percent="2.0"  # Después de TP2: trailing 2%
        else
            trailing_percent="0.2"  # Después de TP1: breakeven (0.2% sobre entry)
        fi
        
        # Actualizar highest price si es necesario
        local highest_price=$(jq -r ".slots[$slot_index].highestPrice // $entry" "$STATE_FILE")
        if (( $(echo "$current_price > $highest_price" | bc -l) )); then
            jq ".slots[$slot_index].highestPrice = $current_price" "$STATE_FILE" > /tmp/state_$$.json && mv /tmp/state_$$.json "$STATE_FILE"
            highest_price=$current_price
            log_debug "  📈 Slot $slot_id: Nuevo highest price \$${highest_price}"
        fi
        
        # Calcular trailing stop level
        local trailing_stop_level=$(echo "scale=8; $highest_price * (1 - $trailing_percent / 100)" | bc)
        
        # Verificar si el precio actual cruzó el trailing stop
        if (( $(echo "$current_price <= $trailing_stop_level" | bc -l) )); then
            log "🛡️ Slot $slot_id: TRAILING STOP HIT - \$${current_price} <= \$${trailing_stop_level}"
            execute_trailing_stop "$slot_id" "$quantity"
        fi
    done
}

# ============================================
# 🎯 MAIN EXECUTION
# ============================================

# ============================================
# 🔄 AUTO-RESET - RESETEAR SLOTS CERRADOS (MEJORADO)
# ============================================

auto_reset_slots() {
    local reset_count=0
    local current_time=$(date +%s)
    local reset_threshold_hours=2  # Resetear slots cerrados por más de 2 horas
    
    # Revisar cada slot individualmente
    for slot_id in $(seq 1 $MAX_SLOTS); do
        local slot_status=$(jq -r ".slots[$((slot_id-1))].status" "$STATE_FILE")
        
        # Solo resetear slots CLOSED_SL o CLOSED_TP (no READY o ACTIVE)
        if [[ "$slot_status" == "CLOSED_SL" || "$slot_status" == "CLOSED_TP" || "$slot_status" == "CLOSED_TP3" || "$slot_status" == "CLOSED_SCALP" || "$slot_status" == "CLOSED_TRAILING" || "$slot_status" == "CLOSED_TP3_INSUFFICIENT" ]]; then
            local slot_timestamp=$(jq -r ".slots[$((slot_id-1))].timestamp" "$STATE_FILE" | tr -d '"')
            
            # Convertir timestamp a epoch (manejar formato ISO 8601)
            local slot_epoch=$(date -d "$slot_timestamp" +%s 2>/dev/null || echo "0")
            
            if [ "$slot_epoch" != "0" ]; then
                local hours_closed=$(( (current_time - slot_epoch) / 3600 ))
                
                # Si el slot lleva cerrado más de X horas, resetearlo
                if [ "$hours_closed" -ge "$reset_threshold_hours" ]; then
                    log "🔄 AUTO-RESET INDIVIDUAL: Slot $slot_id cerrado por ${hours_closed}h"
                    
                    # Resetear solo este slot
                    jq ".slots[$((slot_id-1))] |= . + {
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
                    }" "$STATE_FILE" > /tmp/${SYMBOL}-slot${slot_id}.json
                    mv /tmp/${SYMBOL}-slot${slot_id}.json "$STATE_FILE"
                    
                    log "  ✅ Slot $slot_id reseteado a READY (cerrado por ${hours_closed}h)"
                    ((reset_count++))
                fi
            fi
        fi
    done
    
    # También resetear si TODOS los slots están cerrados (caso original)
    local active_count=$(get_active_slots_count || echo 0)
    local closed_count=$(jq '[.slots[] | select(.status | startswith("CLOSED"))] | length' "$STATE_FILE" || echo 0)
    
    if [ "$active_count" -eq 0 ] && [ "$closed_count" -eq "$MAX_SLOTS" ]; then
        log "🔄 AUTO-RESET: Todos los slots cerrados ($closed_count/$MAX_SLOTS)"
        log "  Reseteando todos los slots a READY..."
        
        jq '.slots = [.slots[] | . + {
            status: "READY",
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
        }]' "$STATE_FILE" > /tmp/${SYMBOL}-reset.json
        mv /tmp/${SYMBOL}-reset.json "$STATE_FILE"
        
        log "  ✅ Todos los slots reseteados a READY"
        return 0
    fi
    
    if [ "$reset_count" -gt 0 ]; then
        log "  ✅ Total slots reseteados: $reset_count"
        return 0
    fi
    
    return 1
}

# ============================================
# 📊 SHOW TRADE HISTORY
# ============================================

show_trade_history() {
    if [ ! -f "$HISTORY_FILE" ]; then
        echo "❌ No hay histórico de trades registrado"
        return 1
    fi
    
    local total_trades=$(jq -r '.totalTrades' "$HISTORY_FILE")
    local total_wins=$(jq -r '.totalWins' "$HISTORY_FILE")
    local total_losses=$(jq -r '.totalLosses' "$HISTORY_FILE")
    local win_rate=$(jq -r '.winRate' "$HISTORY_FILE")
    local total_profit=$(jq -r '.totalProfitUSDT' "$HISTORY_FILE")
    local total_loss=$(jq -r '.totalLossUSDT' "$HISTORY_FILE")
    local net_pnl=$(jq -r '.netPnLUSDT' "$HISTORY_FILE")
    
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║  📊 HISTÓRICO DE TRADING - TODAS LAS MONEDAS          ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo ""
    echo "📈 ESTADÍSTICAS GLOBALES"
    echo "  Total Trades: $total_trades"
    echo "  Wins: $total_wins | Losses: $total_losses"
    echo "  Win Rate: ${win_rate}%"
    echo "  Profit Total: +\$${total_profit}"
    echo "  Loss Total: \$${total_loss}"
    echo "  Net PnL: \$${net_pnl}"
    echo ""
    echo "📜 ÚLTIMOS 10 TRADES"
    echo "─────────────────────────────────────────────────────────"
    printf "%-4s %-6s %-6s %-8s %-10s %-10s\n" "ID" "Coin" "Tipo" "PnL" "Cierre" "Fecha"
    echo "─────────────────────────────────────────────────────────"
    
    jq -r '.trades | sort_by(-.id) | .[0:10] | .[] | "\(.id)\t\(.symbol)\t\(.type)\t\(.pnlUSDT)\t\(.closeType)\t\(.timestamp | split("T")[0])"' "$HISTORY_FILE" | \
    while IFS=$'\t' read -r id symbol type pnl closeType timestamp; do
        local pnl_num=$(echo "$pnl" | tr -d '+')
        local pnl_icon="🔴"
        if awk -v p="$pnl_num" 'BEGIN {exit !(p > 0)}'; then
            pnl_icon="🟢"
        fi
        printf "%-4s %-6s %-6s ${pnl_icon} %-10s %-10s %-10s\n" "$id" "$symbol" "$type" "$pnl" "$closeType" "$timestamp"
    done
    
    echo "─────────────────────────────────────────────────────────"
}

# ============================================
# 🎯 MAIN EXECUTION
# ============================================

# Check for history command
if [ "$1" = "--history" ] || [ "$1" = "-h" ]; then
    show_trade_history
    exit 0
fi

execute_cycle() {
    if [ -z "${BINANCE_API_KEY:-}" ] || [ -z "${BINANCE_API_SECRET:-}" ]; then
        local secrets_file="$HOME/.openclaw/secrets/binance.env"
        if [ -f "$secrets_file" ]; then
            source "$secrets_file"
        fi
    fi
    log "╔═══════════════════════════════════════════════════════╗"
    log "║  🤖 CRYPTO TRADE BOT V3 - $SYMBOL [MULTI-SLOT]           ║"
    log "╚═══════════════════════════════════════════════════════╝"

    # ════════════════════════════════════════════════════════
    # 🛑 GLOBAL CIRCUIT BREAKER - OPTIMIZADO 2026-06-01
    # SKIP CYCLE: pause global activo, no se abren nuevas entradas
    # ════════════════════════════════════════════════════════
    # Verifica losses globales (todas las monedas) antes de operar
    # Evita desastres como May 16 (11 losses en 48h)
    
    GLOBAL_CB_SCRIPT="${WORKSPACE}/crypto-bots/global-circuit-breaker.sh"
    if [ -x "$GLOBAL_CB_SCRIPT" ]; then
        global_status=$(bash "$GLOBAL_CB_SCRIPT" 2>&1)
        global_result=$?
        
        if [ $global_result -ne 0 ]; then
            # Extraer tipo de pausa y tiempo restante
            pause_type=$(echo "$global_status" | cut -d'|' -f1)
            pause_reason=$(echo "$global_status" | cut -d'|' -f2)
            
            log "🛑🛑 GLOBAL CIRCUIT BREAKER: $pause_type - $pause_reason"
            
            # Notificar solo si es la primera vez que se activa
            CB_NOTIFY_FILE="${WORKSPACE}/crypto-bots/cb-last-notify.txt"
            last_notify=$(cat "$CB_NOTIFY_FILE" 2>/dev/null || echo 0)
            current_hour=$(date +%s)
            hours_since_notify=$(( (current_hour - last_notify) / 3600 ))
            
            if [ "$hours_since_notify" -ge 4 ]; then
                notify "GLOBAL_CB|ACTIVATED|${pause_type}" "🛑 GLOBAL CIRCUIT BREAKER ACTIVADO

⚠️ $pause_type

📊 Razón: $pause_reason

🛡️ El bot se detuvo automáticamente para proteger el capital.

⏰ Reanudará cuando las condiciones mejoren.

_Jefe, el bot está en pausa global._ 🐕" 2>/dev/null || true
                
                date +%s > "$CB_NOTIFY_FILE"
            fi
            
            return 0  # Saltar este cycle
        fi
    fi
    
    # ════════════════════════════════════════════════════════
    # 🛑 CHECK INDIVIDUAL SL TRACKING - PREVENT DOUBLE-CHECK
    # SKIP CYCLE:SL reciente < 60 min, esperar enfriamiento
    # ════════════════════════════════════════════════════════
    # Verificar SI ESTA MONEDA tiene SL reciente antes de entrar
    # Esto previene entradas como XRP Jun 02 00:06 (entró 11 min después de SL)
    
    SL_TRACKING_FILE="${WORKSPACE}/crypto-bots/${SYMBOL}-sl-tracking.json"
    if [ -f "$SL_TRACKING_FILE" ]; then
        consecutive_sl=$(jq -r '.consecutive_sl // 0' "$SL_TRACKING_FILE")
        last_sl_time=$(jq -r '.last_sl_time // null' "$SL_TRACKING_FILE")
        
        if [ "$consecutive_sl" -gt 0 ] && [ "$last_sl_time" != "null" ]; then
            # Verificar cuándo fue el último SL
            last_sl_epoch=$(date -d "$last_sl_time" +%s 2>/dev/null || echo 0)
            now_epoch=$(date +%s)
            minutes_since_sl=$(( (now_epoch - last_sl_epoch) / 60 ))
            
            if [ $minutes_since_sl -lt 60 ]; then
                log "⚠️ ${SYMBOL}: SL hace ${minutes_since_sl} minutos - Esperar 60 min mínimo (FIX 2026-06-02)"
                return 0  # Saltar entrada por ahora
            fi
        fi
    fi
    
    # ============================================
    # 🛡️ CHECK SYSTEM STATUS (BINANCE MAINTENANCE)
    # SKIP CYCLE: Binance en mantenimiento
    # ============================================
    check_binance_system_status || {
        log "⚠️ Binance en mantenimiento, saltando este cycle"
        return 0
    }
    
    init_slots
    
    # AUTO-RESET: Resetear slots si todos están cerrados
    auto_reset_slots
    
    # Check active slots
    local active_count=$(get_active_slots_count)
    log "📊 Slots activos: $active_count / $MAX_SLOTS"
    
    # Check each active slot for TP/SL
    for slot_id in $(seq 1 $MAX_SLOTS); do
        check_slot_tp_sl "$slot_id"
    done
    
    # Cargar configuración de mercado si existe
    MARKET_MODE_CONF="${WORKSPACE}/crypto-bots/market-mode.conf"
    if [ -f "$MARKET_MODE_CONF" ]; then
        MARKET_MODE=$(grep '^MARKET_MODE=' "$MARKET_MODE_CONF" | cut -d'=' -f2 | tr -d '"' | xargs)
        MCONF_TP1=$(grep '^TP1=' "$MARKET_MODE_CONF" | tail -n 1 | cut -d'=' -f2 | xargs)
        MCONF_TP2=$(grep '^TP2=' "$MARKET_MODE_CONF" | tail -n 1 | cut -d'=' -f2 | xargs)
        MCONF_TP3=$(grep '^TP3=' "$MARKET_MODE_CONF" | tail -n 1 | cut -d'=' -f2 | xargs)
        MCONF_POSITION=$(grep '^POSITION_SIZE=' "$MARKET_MODE_CONF" | tail -n 1 | cut -d'=' -f2 | xargs)

        # Per-coin overrides: highest precedence
        COIN_TP1=$(grep "^${SYMBOL}_TP1=" "$MARKET_MODE_CONF" | tail -n 1 | cut -d'=' -f2 | xargs)
        COIN_TP2=$(grep "^${SYMBOL}_TP2=" "$MARKET_MODE_CONF" | tail -n 1 | cut -d'=' -f2 | xargs)
        COIN_TP3=$(grep "^${SYMBOL}_TP3=" "$MARKET_MODE_CONF" | tail -n 1 | cut -d'=' -f2 | xargs)
        COIN_SL=$(grep "^${SYMBOL}_SL=" "$MARKET_MODE_CONF" | tail -n 1 | cut -d'=' -f2 | xargs)
        COIN_POSITION_SIZE=$(grep "^${SYMBOL}_POSITION_SIZE=" "$MARKET_MODE_CONF" | tail -n 1 | cut -d'=' -f2 | xargs)
        [ -n "$COIN_TP1" ] && MCONF_TP1="$COIN_TP1"
        [ -n "$COIN_TP2" ] && MCONF_TP2="$COIN_TP2"
        [ -n "$COIN_TP3" ] && MCONF_TP3="$COIN_TP3"
        [ -n "$COIN_SL" ] && MCONF_SL="$COIN_SL"
        [ -n "$COIN_POSITION_SIZE" ] && MCONF_POSITION="$COIN_POSITION_SIZE"

        case "$MARKET_MODE" in
            BULL|BULLISH|LATERAL_BULL)
                NORMAL_TRADE_PERCENT=${NORMAL_TRADE_PERCENT:-20}
                AGGRESSIVE_TRADE_PERCENT=${AGGRESSIVE_TRADE_PERCENT:-40}
                NORMAL_TP1=${NORMAL_TP1:-1.5}
                NORMAL_TP2=${NORMAL_TP2:-3.0}
                NORMAL_TP3=${NORMAL_TP3:-5.0}
                AGGRESSIVE_TP1=${AGGRESSIVE_TP1:-2.0}
                AGGRESSIVE_TP2=${AGGRESSIVE_TP2:-4.0}
                AGGRESSIVE_TP3=${AGGRESSIVE_TP3:-6.0}
                ;;
            BEAR|BEARISH|LATERAL_BEAR)
                NORMAL_TRADE_PERCENT=${NORMAL_TRADE_PERCENT:-10}
                AGGRESSIVE_TRADE_PERCENT=${AGGRESSIVE_TRADE_PERCENT:-20}
                NORMAL_TP1=${NORMAL_TP1:-1.8}
                NORMAL_TP2=${NORMAL_TP2:-3.5}
                NORMAL_TP3=${NORMAL_TP3:-5.5}
                AGGRESSIVE_TP1=${AGGRESSIVE_TP1:-2.2}
                AGGRESSIVE_TP2=${AGGRESSIVE_TP2:-4.5}
                AGGRESSIVE_TP3=${AGGRESSIVE_TP3:-6.5}
                ;;
            LATERAL|NEUTRAL)
                NORMAL_TRADE_PERCENT=${NORMAL_TRADE_PERCENT:-15}
                AGGRESSIVE_TRADE_PERCENT=${AGGRESSIVE_TRADE_PERCENT:-30}
                NORMAL_TP1=${NORMAL_TP1:-1.2}
                NORMAL_TP2=${NORMAL_TP2:-2.5}
                NORMAL_TP3=${NORMAL_TP3:-4.0}
                AGGRESSIVE_TP1=${AGGRESSIVE_TP1:-2.0}
                AGGRESSIVE_TP2=${AGGRESSIVE_TP2:-4.0}
                AGGRESSIVE_TP3=${AGGRESSIVE_TP3:-6.0}
                ;;
            *)
                NORMAL_TRADE_PERCENT=${NORMAL_TRADE_PERCENT:-15}
                AGGRESSIVE_TRADE_PERCENT=${AGGRESSIVE_TRADE_PERCENT:-30}
                NORMAL_TP1=${NORMAL_TP1:-1.8}
                NORMAL_TP2=${NORMAL_TP2:-3.5}
                NORMAL_TP3=${NORMAL_TP3:-5.5}
                AGGRESSIVE_TP1=${AGGRESSIVE_TP1:-2.2}
                AGGRESSIVE_TP2=${AGGRESSIVE_TP2:-4.5}
                AGGRESSIVE_TP3=${AGGRESSIVE_TP3:-6.5}
                ;;
        esac
        
        if [ -n "$MCONF_POSITION" ]; then
            NORMAL_TRADE_PERCENT="$MCONF_POSITION"
            AGGRESSIVE_TRADE_PERCENT="$MCONF_POSITION"
        fi
        
        log "🧠 Market mode: $MARKET_MODE (TPs: $MCONF_TP1/$MCONF_TP2/$MCONF_TP3)"

        # Aplicar overrides del market-mode.conf si existen
        if [ -n "$MCONF_TP1" ] && [ -n "$MCONF_TP2" ] && [ -n "$MCONF_TP3" ]; then
            NORMAL_TP1="$MCONF_TP1"
            NORMAL_TP2="$MCONF_TP2"
            NORMAL_TP3="$MCONF_TP3"
            AGGRESSIVE_TP1="$MCONF_TP1"
            AGGRESSIVE_TP2="$MCONF_TP2"
            AGGRESSIVE_TP3="$MCONF_TP3"
        fi

        # Leer SL desde market-mode.conf si está definido
        MCONF_SL=$(grep '^SL=' "$MARKET_MODE_CONF" | cut -d'=' -f2 | xargs)
        if [ -n "$MCONF_SL" ]; then
            STOP_LOSS_PERCENT="$MCONF_SL"
        fi
    fi

    # Restaurar overrides por moneda después de market-mode.conf
    eval "COIN_TP1=\${${SYMBOL}_TP1}"
    eval "COIN_TP2=\${${SYMBOL}_TP2}"
    eval "COIN_TP3=\${${SYMBOL}_TP3}"
    eval "COIN_SL=\${${SYMBOL}_STOP_LOSS}"
    eval "COIN_POSITION_SIZE=\${${SYMBOL}_POSITION_SIZE}"
    if [ -n "$COIN_TP1" ]; then NORMAL_TP1="$COIN_TP1"; AGGRESSIVE_TP1="$COIN_TP1"; TP1_PERCENT="$COIN_TP1"; fi
    if [ -n "$COIN_TP2" ]; then NORMAL_TP2="$COIN_TP2"; AGGRESSIVE_TP2="$COIN_TP2"; TP2_PERCENT="$COIN_TP2"; fi
    if [ -n "$COIN_TP3" ]; then NORMAL_TP3="$COIN_TP3"; AGGRESSIVE_TP3="$COIN_TP3"; TP3_PERCENT="$COIN_TP3"; fi
    if [ -n "$COIN_SL" ]; then STOP_LOSS_PERCENT="$COIN_SL"; fi
    if [ -n "$COIN_POSITION_SIZE" ]; then NORMAL_TRADE_PERCENT="$COIN_POSITION_SIZE"; AGGRESSIVE_TRADE_PERCENT="$COIN_POSITION_SIZE"; TRADE_PERCENT="$COIN_POSITION_SIZE"; fi

    # Detectar modo y obtener STOP LOSS por coin
    local current_hour=$(date -u +%H | sed 's/^0//')
    
    # Obtener STOP LOSS específico para esta coin
    if [ -n "${STOP_LOSS_BY_COIN[$SYMBOL]}" ]; then
        STOP_LOSS_PERCENT="${STOP_LOSS_BY_COIN[$SYMBOL]}"
    else
        STOP_LOSS_PERCENT="2.5"  # Default reducido para mejorar riesgo/beneficio
    fi
    
    # Detectar modo (AGGRESSIVE/NORMAL) para TP y trade size
    if echo "$TRADING_HOURS_OPTIMAL" | grep -qw "$current_hour"; then
        TRADE_PERCENT=$AGGRESSIVE_TRADE_PERCENT
        TP1_PERCENT=$AGGRESSIVE_TP1
        TP2_PERCENT=$AGGRESSIVE_TP2
        TP3_PERCENT=$AGGRESSIVE_TP3
        CURRENT_MODE="AGGRESSIVE"
    else
        TRADE_PERCENT=$NORMAL_TRADE_PERCENT
        TP1_PERCENT=$NORMAL_TP1
        TP2_PERCENT=$NORMAL_TP2
        TP3_PERCENT=$NORMAL_TP3
        CURRENT_MODE="NORMAL"
    fi
    
    log "⏰ Modo: $CURRENT_MODE (${current_hour} UTC) | SL=${STOP_LOSS_PERCENT}% (por coin) | TP: ${TP1_PERCENT}%/${TP2_PERCENT}%/${TP3_PERCENT}%"
    
    # ════════════════════════════════════════════════════════
    # 🧠 ML POSITION SIZE OPTIMIZATION
    # ════════════════════════════════════════════════════════
    
    ML_POSITION_SCRIPT="${WORKSPACE}/ml/ml-position-size.sh"
    if [ -x "$ML_POSITION_SCRIPT" ]; then
        log "🧠 ML: Consultando position size optimizer..."
        ML_POSITION_SIZE=$(bash "$ML_POSITION_SCRIPT" "$SYMBOL" 2>/dev/null)
        
        if [ -n "$ML_POSITION_SIZE" ] && [ "$ML_POSITION_SIZE" != "40" ]; then
            log "🧠 ML: Position size recomendado: ${ML_POSITION_SIZE}%"
            
            # Aplicar ML position size (respetando límites 15-50%)
            if [ "$ML_POSITION_SIZE" -ge 15 ] && [ "$ML_POSITION_SIZE" -le 50 ]; then
                TRADE_PERCENT=$ML_POSITION_SIZE
                log "✅ ML override aplicado: TRADE_PERCENT=${TRADE_PERCENT}%"
            else
                log "⚠️ ML position size fuera de rango (${ML_POSITION_SIZE}%), usando default 40%"
            fi
        else
            log "🧠 ML: Usando position size default (40%)"
        fi
    else
        log "⚠️ ML position size script no disponible"
    fi
    
    # ════════════════════════════════════════════════════════
    # 🛡️ ML DRAWDOWN RISK CHECK
    # ════════════════════════════════════════════════════════
    
    ML_DRAWDOWN_SCRIPT="${WORKSPACE}/ml/ml-drawdown-check.sh"
    if [ -x "$ML_DRAWDOWN_SCRIPT" ]; then
        log "🛡️ ML: Consultando drawdown risk checker..."
        ML_RISK_RESULT=$(bash "$ML_DRAWDOWN_SCRIPT" "$SYMBOL" 2>/dev/null)
        
        if [ -n "$ML_RISK_RESULT" ]; then
            ML_RISK_LEVEL=$(echo "$ML_RISK_RESULT" | cut -d'|' -f1)
            ML_RISK_ACTION=$(echo "$ML_RISK_RESULT" | cut -d'|' -f2)
            ML_RISK_POSITION=$(echo "$ML_RISK_RESULT" | cut -d'|' -f3)
            ML_RISK_MSG=$(echo "$ML_RISK_RESULT" | cut -d'|' -f4)
            
            log "🛡️ ML: Riesgo=${ML_RISK_LEVEL} | Acción=${ML_RISK_ACTION} | Position=${ML_RISK_POSITION}%"
            log "🛡️ ML: ${ML_RISK_MSG}"
            
            # ════════════════════════════════════════════════════════
            # 🛑 CHECK PAUSE STATE - Evitar spam de notificaciones
            # ════════════════════════════════════════════════════════
            PAUSE_FLAG_FILE="${WORKSPACE}/crypto-bots/${SYMBOL}-ml-pause-flag.json"
            GLOBAL_PAUSE_FLAG="${WORKSPACE}/crypto-bots/ml-global-pause-flag.json"
            
            if [ "$ML_RISK_ACTION" = "PAUSE" ]; then
                # Verificar si ya notificamos esta pausa (global)
                ALREADY_PAUSED=false
                
                # Check 1: Flag global (primera moneda en pausar)
                if [ -f "$GLOBAL_PAUSE_FLAG" ]; then
                    global_timestamp=$(jq -r '.timestamp // ""' "$GLOBAL_PAUSE_FLAG" 2>/dev/null)
                    global_risk_level=$(jq -r '.risk_level // "HIGH_RISK"' "$GLOBAL_PAUSE_FLAG" 2>/dev/null)
                    
                    # Si el risk level es el mismo (HIGH_RISK) y fue en las últimas 12 horas, no notificar
                    # No comparamos mensaje porque puede variar ligeramente entre coins
                    if [ "$global_risk_level" = "HIGH_RISK" ]; then
                        # Verificar timestamp (12 horas en segundos)
                        global_epoch=$(date -d "$global_timestamp" +%s 2>/dev/null || echo 0)
                        now_epoch=$(date +%s)
                        diff_hours=$(( (now_epoch - global_epoch) / 3600 ))
                        
                        if [ $diff_hours -lt 12 ]; then
                            ALREADY_PAUSED=true
                            log "🛑 ML: Pausa global ya notificada (hace ${diff_hours}h), silenciando $SYMBOL"
                        fi
                    fi
                fi
                
                # Check 2: Flag individual (si ya esta moneda había pausado antes con mismo motivo)
                if [ "$ALREADY_PAUSED" = false ] && [ -f "$PAUSE_FLAG_FILE" ]; then
                    last_pause=$(jq -r '.last_pause // ""' "$PAUSE_FLAG_FILE" 2>/dev/null)
                    
                    # Verificar si fue en las últimas 2 horas (misma racha de pérdidas)
                    if [ -n "$last_pause" ]; then
                        last_epoch=$(date -d "$last_pause" +%s 2>/dev/null || echo 0)
                        now_epoch=$(date +%s)
                        diff_minutes=$(( (now_epoch - last_epoch) / 60 ))
                        
                        if [ $diff_minutes -lt 120 ]; then
                            ALREADY_PAUSED=true
                            log "🛑 ML: Pausa individual reciente (${diff_minutes}min), silenciando $SYMBOL"
                        fi
                    fi
                fi
                
                if [ "$ALREADY_PAUSED" = false ]; then
                    log "🛑 ML: Riesgo ALTO - Pausando trading para $SYMBOL"
                    notify "ML_PAUSE|$SYMBOL|HIGH_RISK" "🛑 TRADING PAUSADO - $SYMBOL

🛡️ ML Risk Detector: Riesgo ALTO
${ML_RISK_MSG}

Se recomienda esperar condiciones mejores. 🐕"
                    
                    # Guardar flag individual
                    echo "{\"last_pause\": \"$(date -Iseconds)\", \"pause_msg\": \"$ML_RISK_MSG\", \"risk_level\": \"HIGH_RISK\"}" > "$PAUSE_FLAG_FILE"
                    
                    # Guardar flag global (primera notificación)
                    if [ ! -f "$GLOBAL_PAUSE_FLAG" ]; then
                        echo "{\"timestamp\": \"$(date -Iseconds)\", \"pause_msg\": \"$ML_RISK_MSG\", \"first_coin\": \"$SYMBOL\", \"risk_level\": \"HIGH_RISK\"}" > "$GLOBAL_PAUSE_FLAG"
                        log "🛑 ML: Flag global creado por $SYMBOL"
                    fi
                fi
                
                return 1  # No operar
            else
                # ML permite operar (LOW_RISK o MEDIUM_RISK con REDUCE)
                # Limpiar flags si existen
                if [ -f "$PAUSE_FLAG_FILE" ]; then
                    rm -f "$PAUSE_FLAG_FILE"
                    log "✅ ML: Pausa individual removida para $SYMBOL"
                fi
                
                # Si todas las monedas están operando, limpiar flag global
                OPERATING_COUNT=0
                for coin in BNB SOL AVAX LINK XRP; do
                    if [ ! -f "${WORKSPACE}/crypto-bots/${coin}-ml-pause-flag.json" ]; then
                        OPERATING_COUNT=$((OPERATING_COUNT + 1))
                    fi
                done
                
                if [ $OPERATING_COUNT -eq 7 ] && [ -f "$GLOBAL_PAUSE_FLAG" ]; then
                    rm -f "$GLOBAL_PAUSE_FLAG"
                    log "✅ ML: Todas las monedas operando, flag global removido"
                    
                    # Notificar reanudación
                    send_telegram "✅ TRADING REANUDADO

🛡️ ML Risk Detector: Riesgo bajo
Todas las monedas pueden operar normalmente.

🚀 Bot operativo - Monitoreando TPs..." 2>/dev/null || true
                fi
                
                if [ "$ML_RISK_ACTION" = "REDUCE" ]; then
                    log "⚠️ ML: Riesgo MEDIO - Reduciendo position size"
                    if [ "$ML_RISK_POSITION" -lt "$TRADE_PERCENT" ]; then
                        TRADE_PERCENT=$ML_RISK_POSITION
                        log "✅ Risk override aplicado: TRADE_PERCENT=${TRADE_PERCENT}%"
                    fi
                else
                    log "✅ ML: Riesgo BAJO - Operando normal"
                fi
            fi
        fi
    else
        log "⚠️ ML drawdown script no disponible"
    fi
    
    # FASE 1: Verificar TRAILING STOP en slots activos
    check_trailing_stops
    
    # ════════════════════════════════════════════════════════
    # 🛑 CHECK CONSECUTIVE SL HITS - PAUSE AFTER 2 LOSSES
    # SKIP CYCLE: pausa por racha de SL activa por tiempo definido
    # ════════════════════════════════════════════════════════
    SL_TRACKING_FILE="${WORKSPACE}/crypto-bots/${SYMBOL}-sl-tracking.json"
    
    # Inicializar archivo si no existe
    if [ ! -f "$SL_TRACKING_FILE" ]; then
        echo '{"consecutive_sl":0,"last_sl_time":null,"pause_until":null,"total_sl_today":0}' > "$SL_TRACKING_FILE"
    fi
    
    # Leer estado actual
    local consecutive_sl=$(jq -r '.consecutive_sl // 0' "$SL_TRACKING_FILE" 2>/dev/null)
    local pause_until=$(jq -r '.pause_until // null' "$SL_TRACKING_FILE" 2>/dev/null)
    
    # Verificar si estamos en pausa
    if [ "$pause_until" != "null" ]; then
        local now_epoch=$(date +%s)
        local pause_epoch=$(date -d "$pause_until" +%s 2>/dev/null || echo 0)
        
        if [ $now_epoch -lt $pause_epoch ]; then
            local remaining_mins=$(( (pause_epoch - now_epoch) / 60 ))
            log "🛑 PAUSE ACTIVO: $SYMBOL después de $consecutive_sl SL hits consecutivos"
            log "   ⏰ Reanudar en: ${remaining_mins} minutos ($pause_until)"
            return 0  # Saltar este cycle
        else
            # Pausa terminó, resetear contadores
            log "✅ PAUSE TERMINADO: $SYMBOL reanudando operaciones"
            echo '{"consecutive_sl":0,"last_sl_time":null,"pause_until":null,"total_sl_today":0}' > "$SL_TRACKING_FILE"
            consecutive_sl=0
        fi
    fi
    
    # Check si tenemos 2+ SL hits consecutivos → PAUSE 4 horas
    if [ "$consecutive_sl" -ge 2 ]; then
        local pause_until_time=$(date -d '+4 hours' '+%Y-%m-%d %H:%M:%S')
        
        jq -n --arg pause "$pause_until_time" --argjson sl "$consecutive_sl" \
            '{consecutive_sl: $sl, last_sl_time: now, pause_until: $pause, total_sl_today: .total_sl_today // 0}' \
            > "$SL_TRACKING_FILE"
        
        log "🛑🛑 PAUSE FORZADO: $SYMBOL después de $consecutive_sl SL hits consecutivos"
        log "   ⏸️ Pausa de 4 horas hasta: $pause_until_time"
        
        # Notificar por Telegram
        send_telegram "🛑 PAUSE AUTOMÁTICO - $SYMBOL

⚠️ $consecutive_sl Stop Loss hits consecutivos

📊 Estadísticas:
• Último SL: hace pocos minutos
• Pausa: 4 horas
• Reanudar: $pause_until_time

🛡️ Protección activada para evitar más pérdidas.

_Jefe, el bot se detuvo automáticamente._ 🐕" 2>/dev/null || true
        
        return 0  # Saltar este cycle
    fi
    
    # ════════════════════════════════════════════════════════
    # 📊 DYNAMIC POSITION SIZE BASED ON SL HITS
    # ════════════════════════════════════════════════════════
    if [ "$consecutive_sl" -eq 1 ]; then
        # Después de 1 SL, reducir position size a 30%
        local original_percent=$TRADE_PERCENT
        TRADE_PERCENT=30
        log "⚠️ Position size reducido: $original_percent% → ${TRADE_PERCENT}% (1 SL reciente)"
    fi
    
    # Check if we can open new trades
    if [ "$active_count" -ge "$MAX_SLOTS" ]; then
        log "⏸️ Máximo de slots alcanzado ($active_count / $MAX_SLOTS)"
        return 0
    fi
    
    # 🐕 FIX: Per-coin enable/disable check
    if [ "${SYMBOL_ENABLED:-true}" = "false" ]; then
        log "❌ TRADING DESHABILITADO para $SYMBOL en per-coin-config.env"
        return 0
    fi
    
    # Get available slot
    local available_slot=$(get_available_slot)
    [ "$available_slot" = "0" ] && return 0
    
    # DEBUG: Log variables antes de ejecutar
    log "🔍 DEBUG: TRADE_PERCENT=$TRADE_PERCENT | NORMAL_TRADE_PERCENT=$NORMAL_TRADE_PERCENT | AGGRESSIVE_TRADE_PERCENT=$AGGRESSIVE_TRADE_PERCENT"
    
    # Simple signal logic (puede expandirse con TA)
    local signal="LONG"  # Por defecto para testing
    
    if [ "$signal" = "LONG" ]; then
        log "📈 Ejecutando execute_long slot=$available_slot con TRADE_PERCENT=$TRADE_PERCENT"
        execute_long "$available_slot" "$TRADE_PERCENT"
    fi
    
    log "✅ Ciclo completado"
}

# Run
execute_cycle
