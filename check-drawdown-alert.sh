#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║   DRAWDOWN ALERT - PERROBOTILLO                    ║
# ║  Envía alerta Telegram si drawdown > 5%              ║
# ╚═══════════════════════════════════════════════════════╝

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="$HOME/.openclaw/secrets"
LOGS="$HOME/.openclaw/logs"

source "$SECRETS/binance.env"
# ✅ BUG #6 FIX: telegram.env no existe; notify.sh lee token de openclaw.json

# ============================================
# CONFIGURACIÓN
# ============================================

DRAWDOWN_THRESHOLD=5.0  # Alerta si drawdown > 5%
PEAK_FILE="$WORKSPACE/crypto-bots/portfolio-peak.json"  # Track peak portfolio value

# ============================================
# FUNCIONES
# ============================================

# ✅ BUG #9/#10 FIX: Source centralized notify.sh BEFORE log() definition.
# notify.sh ALSO defines log() — it writes to STDOUT (no >&2 redirect).
# If sourced AFTER our log(), our stderr-logging get_drawdown_log() gets
# overridden, and log() inside calculate_drawdown() writes to stdout,
# polluting the drawdown=$(...) capture with log text → false alert triggers.
WORKSPACE="$HOME/.openclaw/workspace"
source "$WORKSPACE/crypto-bots/notify.sh" 2>/dev/null || true

log() {
    # ✅ FIX: stderr to avoid polluting stdout captured by $(calculate_drawdown)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [DRAWDOWN] $1" | tee -a "$LOGS/drawdown-alert.log" >&2
}

get_portfolio_value() {
    # ✅ FIX: Use real API key (not $BINANCE_API_KEY), recvWindow=60000 for timestamp tolerance
    local timestamp=$(date +%s)000
    local recvWindow=60000
    local query="timestamp=${timestamp}&recvWindow=${recvWindow}"
    local signature=$(printf '%s' "$query" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}')

    local account=$(curl -s --max-time 15 -H "X-MBX-APIKEY: $BINANCE_API_KEY" \
        "https://api.binance.com/api/v3/account?${query}&signature=${signature}")

    # Check if API call succeeded
    local account_error=$(echo "$account" | jq -r '.code // empty' 2>/dev/null)
    if [ -n "$account_error" ] && [ "$account_error" != "null" ]; then
        log "⚠️ Binance API error: $account_error"
        echo "$account_error"
        return 1
    fi

    # Extraer balances de USDT y coins
    local usdt_balance=$(echo "$account" | jq -r '.balances[] | select(.asset=="USDT") | .free + .locked' 2>/dev/null || echo "0")

    local coins=("BTC" "ETH" "BNB" "SOL" "LINK" "XRP" "AVAX" "ZEC")
    # ✅ FIX (2026-10-28): Added LINK to coins array. Bot trades 8 coins per
    # per-coin-config.env (all ENABLED=true), but LINK was missing here, causing
    # portfolio value to be undercounted by ~$38 USDT and drawdown to be
    # inflated. This was the root cause of the "inconsistent" drawdown alert.
    local portfolio_value=$usdt_balance

    for coin in "${coins[@]}"; do
        local balance=$(echo "$account" | jq -r ".balances[] | select(.asset==\"$coin\") | .free + .locked" 2>/dev/null || echo "0")

        if (( $(awk -v b="$balance" 'BEGIN {print (b > 0) ? 1 : 0}') )); then
            local price=$(curl -s "https://api.binance.com/api/v3/ticker/price?symbol=${coin}USDT" | jq -r '.price' 2>/dev/null || echo "0")
            local value=$(awk -v b="$balance" -v p="$price" 'BEGIN {printf "%.2f", b * p}')
            portfolio_value=$(awk -v pv="$portfolio_value" -v v="$value" 'BEGIN {printf "%.2f", pv + v}')
        fi
    done

    echo "$portfolio_value"
}

calculate_drawdown() {
    # ✅ FIX (2026-10-18): Track peak portfolio value instead of hardcoded INITIAL_CAPITAL.
    # Previously used INITIAL_CAPITAL=2000, but portfolio grew to ~$4000+, making
    # drawdown always negative (profit) → alert NEVER fired even on -92% drawdown.
    # Now: peak stored in portfolio-peak.json; drawdown = ((peak - current) / peak) * 100.
    local current_value=$1
    # NOTE: peak_value is global — needed by main() for logging after function returns
    peak_value=0
    
    # Read or initialize peak
    if [ -f "$PEAK_FILE" ]; then
        peak_value=$(jq -r '.peak_value // 0' "$PEAK_FILE" 2>/dev/null || echo "0")
    else
        peak_value=0
    fi
    
    # Initialize or update peak
    if (( $(awk -v p="$peak_value" -v c="$current_value" 'BEGIN {print (c > p) ? 1 : 0}') )); then
        peak_value="$current_value"
        python3 -c "import json; json.dump({'peak_value': float('$current_value'), 'updated_at': '$(date -Iseconds)'}, open('$PEAK_FILE', 'w'), indent=2)" 2>/dev/null || true
        log "📈 Nuevo peak portfolio: \$$current_value (state file actualizado)"
    fi
    
    # Calculate drawdown from peak
    local drawdown=$(awk -v pv="$peak_value" -v cv="$current_value" 'BEGIN {
        if (pv > 0) {
            dd = ((pv - cv) / pv) * 100
            printf "%.2f", dd
        } else {
            print "0"
        }
    }')
    echo "$drawdown"
}

# ============================================
# MAIN
# ============================================

log "Verificando drawdown..."

# Obtener valor actual del portfolio
current_value=$(get_portfolio_value 2>/dev/null)

# ✅ FIX: Check for API errors (not just "0")
# API errors now return the error code string (e.g., "-1021") instead of "0"
if [ "$current_value" = "0" ] || echo "$current_value" | grep -q "^-10"; then
    log "⚠️ API Binance falló (posible IP no whitelisteada o error API). Saltando verificación."
    exit 0
fi

# ✅ FIX: Validate numeric before logging
if ! echo "$current_value" | grep -qE '^[0-9]+\.?[0-9]*$'; then
    log "⚠️ Portfolio value no es numérico: $current_value. Saltando verificación."
    exit 0
fi

log "Portfolio actual: \$$current_value USDT"

# Calcular drawdown
drawdown=$(calculate_drawdown "$current_value")
log "Drawdown: ${drawdown}%"

# Verificar si supera threshold
if (( $(awk -v dd="$drawdown" -v th="$DRAWDOWN_THRESHOLD" 'BEGIN {print (dd > th) ? 1 : 0}') )); then
    log "⚠️  DRAWDOWN ALERTA: ${drawdown}% > ${DRAWDOWN_THRESHOLD}%"
    
    # ✅ DEDUP: Only notify once per day for drawdown
    _dd_dedup="$WORKSPACE/crypto-bots/.last_drawdown_alert"
    if [ -f "$_dd_dedup" ]; then
        _dd_last=$(tail -1 "$_dd_dedup" 2>/dev/null || echo 0)
        _dd_now=$(date +%s)
        _dd_diff=$((_dd_now - _dd_last))
        if [ "$_dd_diff" -lt 86400 ]; then
            log "✅ Drawdown alert dedup: already notified today (last: ${_dd_diff}s ago)"
            exit 0
        fi
    fi

    # Enviar alerta Telegram
    message="🚨 **ALERTA DE DRAWDOWN** 🚨

 **Perrobotillo Trading Bot**

💰 Portfolio Actual: \$$current_value USDT
📉 Drawdown: **${drawdown}%**
⚠️  Threshold: ${DRAWDOWN_THRESHOLD}%

⚡ **⚡ Acción Recomendada:**
• Revisar trades activos
• Considerar reducir position size
• Monitorear de cerca

_Jefe, es momento de estar atento_ 🐕"

    notify "DRAWDOWN" "$message"

    log "✅ Alerta enviada a Telegram"

    # Guardar estado de alerta (para no spamear)
    echo "$current_value" > "$_dd_dedup"
    echo "$_dd_now" >> "$_dd_dedup"
    
else
    # ✅ FIX (2026-10-28): peak_value is set in subshell by calculate_drawdown,
    # so it doesn't propagate to this scope. Re-read from peak file.
    peak_value=$(jq -r '.peak_value // 0' "$PEAK_FILE" 2>/dev/null || echo "0")
    log "✅ Drawdown dentro de límites (${drawdown}% < ${DRAWDOWN_THRESHOLD}%) — Peak: $peak_value USDT"
fi

log "Verificación completada"
