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
INITIAL_CAPITAL=2000.0  # USDT

# ============================================
# FUNCIONES
# ============================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [DRAWDOWN] $1" | tee -a "$LOGS/drawdown-alert.log"
}

# ✅ BUG #9/#10 FIX: Source centralized notify.sh (Markdown, --data-urlencode)
WORKSPACE="$HOME/.openclaw/workspace"
source "$WORKSPACE/crypto-bots/notify.sh" 2>/dev/null || true

get_portfolio_value() {
    # Obtener balance total en USDT
    local response=$(curl -s -H "X-MBX-APIKEY: $BINANCE_API_KEY" \
        "https://api.binance.com/sapi/v1/capital/config/getall?timestamp=$(date +%s000)")
    
    # Sumar todos los balances disponibles + en trading
    local total=0
    
    # Método alternativo: usar account API
    local account=$(curl -s -H "X-MBX-APIKEY: $BINANCE_API_KEY" \
        "https://api.binance.com/api/v3/account?timestamp=$(date +%s000)")
    
    # Extraer balances de USDT y coins
    local usdt_balance=$(echo "$account" | jq -r '.balances[] | select(.asset=="USDT") | .free + .locked' 2>/dev/null || echo "0")
    
    # Obtener precios actuales de las coins
    local coins=("BTC" "ETH" "BNB" "SOL" "ZEC" "XRP" "AVAX")
    local portfolio_value=$usdt_balance
    
    for coin in "${coins[@]}"; do
        local balance=$(echo "$account" | jq -r ".balances[] | select(.asset==\"$coin\") | .free + .locked" 2>/dev/null || echo "0")
        
        if (( $(awk -v b="$balance" 'BEGIN {print (b > 0) ? 1 : 0}') )); then
            # Obtener precio actual
            local price=$(curl -s "https://api.binance.com/api/v3/ticker/price?symbol=${coin}USDT" | jq -r '.price' 2>/dev/null || echo "0")
            local value=$(awk -v b="$balance" -v p="$price" 'BEGIN {printf "%.2f", b * p}')
            portfolio_value=$(awk -v pv="$portfolio_value" -v v="$value" 'BEGIN {printf "%.2f", pv + v}')
        fi
    done
    
    echo "$portfolio_value"
}

calculate_drawdown() {
    local current_value=$1
    local drawdown=$(awk -v ic="$INITIAL_CAPITAL" -v cv="$current_value" 'BEGIN {
        if (ic > 0) {
            dd = ((ic - cv) / ic) * 100
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
current_value=$(get_portfolio_value)
log "Portfolio actual: \$$current_value USDT"

# Calcular drawdown
drawdown=$(calculate_drawdown "$current_value")
log "Drawdown: ${drawdown}%"

# Verificar si supera threshold
if (( $(awk -v dd="$drawdown" -v th="$DRAWDOWN_THRESHOLD" 'BEGIN {print (dd > th) ? 1 : 0}') )); then
    log "⚠️  DRAWDOWN ALERTA: ${drawdown}% > ${DRAWDOWN_THRESHOLD}%"
    
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
    echo "$current_value" > "$WORKSPACE/crypto-bots/.last_drawdown_alert"
    echo "$(date +%s)" >> "$WORKSPACE/crypto-bots/.last_drawdown_alert"
    
else
    log "✅ Drawdown dentro de límites (${drawdown}% < ${DRAWDOWN_THRESHOLD}%)"
fi

log "Verificación completada"
