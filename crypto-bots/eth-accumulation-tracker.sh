#!/bin/bash
# ════════════════════════════════════════════════════════
# 🎯 ETH ACCUMULATION TRACKER - SEGUIMIENTO DE PROGRESO
# ════════════════════════════════════════════════════════
# Monitorea progreso hacia 0.44 ETH y notifica hitos
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
SECRETS="/home/overgon/.openclaw/secrets"
CONFIG_FILE="$WORKSPACE/crypto-bots/eth-accumulation-config.env"
LOG_FILE="/home/overgon/.openclaw/logs/eth-accumulation.log"
PROGRESS_FILE="$WORKSPACE/crypto-bots/eth-accumulation-progress.json"

# Cargar configuración
source "$CONFIG_FILE"

# ════════════════════════════════════════════════════════
# 🔧 FUNCIONES
# ════════════════════════════════════════════════════════

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_telegram() {
    local message="$1"
    local config_file="$HOME/.openclaw/openclaw.json"
    
    if [ -f "$config_file" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_file" 2>/dev/null)
        if [ -n "$bot_token" ] && [ "$bot_token" != "null" ]; then
            curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
                -H "Content-Type: application/json" \
                -d "{\"chat_id\":\"7543955537\",\"text\":\"$message\",\"parse_mode\":\"Markdown\"}" > /dev/null
        fi
    fi
}

get_eth_balance() {
    source "$SECRETS/binance.env"
    
    local timestamp=$(($(date +%s) * 1000))
    local recvWindow=5000
    local queryString="timestamp=$timestamp&recvWindow=$recvWindow"
    local signature=$(echo -n "$queryString" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}')
    
    local balance=$(curl -s "https://api.binance.com/api/v3/account?$queryString&signature=$signature" \
        -H "X-MBX-APIKEY: $BINANCE_API_KEY")
    
    local eth_balance=$(echo "$balance" | jq -r '.balances[] | select(.asset=="ETH") | .free')
    [ -z "$eth_balance" ] || [ "$eth_balance" = "null" ] && eth_balance="0"
    
    echo "$eth_balance"
}

get_eth_price() {
    local price=$(curl -s "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT" | jq -r '.price')
    [ -z "$price" ] || [ "$price" = "null" ] && price="0"
    echo "$price"
}

# ════════════════════════════════════════════════════════
# 📊 CALCULAR PROGRESO
# ════════════════════════════════════════════════════════

log "╔═══════════════════════════════════════════════════════╗"
log "║  🎯 ETH ACCUMULATION - ACTUALIZACIÓN DE PROGRESO    ║"
log "╚═══════════════════════════════════════════════════════╝"

# Obtener balance actual
ETH_CURRENT=$(get_eth_balance)
ETH_PRICE=$(get_eth_price)

# Calcular progreso
ETH_MISSING=$(echo "scale=4; $ETH_TARGET_AMOUNT - $ETH_CURRENT" | bc)
ETH_MISSING_USDT=$(echo "scale=2; $ETH_MISSING * $ETH_PRICE" | bc)
ETH_ACCUMULATED=$(echo "scale=4; $ETH_CURRENT - $ETH_ACCUMULATION_START_AMOUNT" | bc)
PROGRESS_PERCENT=$(echo "scale=2; ($ETH_CURRENT - $ETH_ACCUMULATION_START_AMOUNT) * 100 / ($ETH_TARGET_AMOUNT - $ETH_ACCUMULATION_START_AMOUNT)" | bc)

log ""
log "=== PROGRESO ACTUAL ==="
log "ETH Actual: $ETH_CURRENT"
log "ETH Objetivo: $ETH_TARGET_AMOUNT"
log "ETH Acumulado: $ETH_ACCUMULATED (+${PROGRESS_PERCENT}%)"
log "Falta: $ETH_MISSING ETH (~\$${ETH_MISSING_USDT} USDT)"
log "Precio ETH: \$${ETH_PRICE} USDT"

# ════════════════════════════════════════════════════════
# 🎯 VERIFICAR HITOS
# ════════════════════════════════════════════════════════

# Leer último progreso
LAST_PROGRESS="0"
if [ -f "$PROGRESS_FILE" ]; then
    LAST_PROGRESS=$(jq -r '.progress_percent // 0' "$PROGRESS_FILE" 2>/dev/null)
fi

# Verificar si alcanzó nuevo hito (cada 25%)
HITO_25=$(echo "$PROGRESS_PERCENT >= 25 && $LAST_PROGRESS < 25" | bc)
HITO_50=$(echo "$PROGRESS_PERCENT >= 50 && $LAST_PROGRESS < 50" | bc)
HITO_75=$(echo "$PROGRESS_PERCENT >= 75 && $LAST_PROGRESS < 75" | bc)
HITO_90=$(echo "$PROGRESS_PERCENT >= 90 && $LAST_PROGRESS < 90" | bc)
HITO_100=$(echo "$PROGRESS_PERCENT >= 100" | bc)

# ════════════════════════════════════════════════════════
# 📢 ENVIAR NOTIFICACIONES
# ════════════════════════════════════════════════════════

if [ "$HITO_25" -eq 1 ]; then
    log "🎉 HITO ALCANZADO: 25% del objetivo!"
    send_telegram "🎉 *ETH ACCUMULATION - 25% COMPLETADO*

📊 Progreso: 25%
💰 ETH Acumulado: $ETH_ACCUMULATED
🎯 Objetivo: $ETH_TARGET_AMOUNT ETH
💵 Valor: \$$(echo "scale=2; $ETH_CURRENT * $ETH_PRICE" | bc) USDT

¡Seguí así, jefe! 🐕🚀"
elif [ "$HITO_50" -eq 1 ]; then
    log "🎉 HITO ALCANZADO: 50% del objetivo!"
    send_telegram "🎉 *ETH ACCUMULATION - 50% COMPLETADO*

📊 Progreso: 50% (MITAD DEL CAMINO!)
💰 ETH Acumulado: $ETH_ACCUMULATED
🎯 Objetivo: $ETH_TARGET_AMOUNT ETH
💵 Valor: \$$(echo "scale=2; $ETH_CURRENT * $ETH_PRICE" | bc) USDT

¡Excelente progreso! 🐕💪"
elif [ "$HITO_75" -eq 1 ]; then
    log "🎉 HITO ALCANZADO: 75% del objetivo!"
    send_telegram "🎉 *ETH ACCUMULATION - 75% COMPLETADO*

📊 Progreso: 75% (CASI LO LOGRAMOS!)
💰 ETH Acumulado: $ETH_ACCUMULATED
🎯 Objetivo: $ETH_TARGET_AMOUNT ETH
💵 Valor: \$$(echo "scale=2; $ETH_CURRENT * $ETH_PRICE" | bc) USDT

¡Falta poco! 🐕🔥"
elif [ "$HITO_90" -eq 1 ]; then
    log "🎉 HITO ALCANZADO: 90% del objetivo!"
    send_telegram "🎉 *ETH ACCUMULATION - 90% COMPLETADO*

📊 Progreso: 90% (¡YA CASI!)
💰 ETH Acumulado: $ETH_ACCUMULATED
🎯 Objetivo: $ETH_TARGET_AMOUNT ETH
💵 Valor: \$$(echo "scale=2; $ETH_CURRENT * $ETH_PRICE" | bc) USDT

¡Recta final! 🐕💨"
elif [ "$HITO_100" -eq 1 ]; then
    log "🎉🎉🎉 OBJETIVO ALCANZADO: 0.44 ETH COMPLETOS!"
    send_telegram "🎉🎉🎉 *ETH ACCUMULATION - OBJETIVO ALCANZADO!*

🏆 *¡0.44 ETH COMPLETADOS!* 🏆

📊 Progreso: 100%
💰 ETH Total: $ETH_CURRENT
🎯 Objetivo: $ETH_TARGET_AMOUNT ETH
💵 Valor: \$$(echo "scale=2; $ETH_CURRENT * $ETH_PRICE" | bc) USDT

¡Felicidades jefe! Perrobotillo cumplió la misión 🐕🏆🚀

*¿Próximo objetivo?* 👀"
fi

# ════════════════════════════════════════════════════════
# 💾 GUARDAR PROGRESO
# ════════════════════════════════════════════════════════

cat > "$PROGRESS_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "eth_current": "$ETH_CURRENT",
    "eth_target": "$ETH_TARGET_AMOUNT",
    "eth_accumulated": "$ETH_ACCUMULATED",
    "eth_missing": "$ETH_MISSING",
    "eth_missing_usdt": "$ETH_MISSING_USDT",
    "eth_price": "$ETH_PRICE",
    "progress_percent": "$PROGRESS_PERCENT",
    "start_amount": "$ETH_ACCUMULATION_START_AMOUNT",
    "start_date": "$ETH_ACCUMULATION_START_DATE"
}
EOF

log ""
log "✅ Progreso guardado en $PROGRESS_FILE"
log ""

# ════════════════════════════════════════════════════════
# 📊 SALIDA RESUMEN
# ════════════════════════════════════════════════════════

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  📊 PROGRESO ETH ACCUMULATION                        ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "  Actual: $ETH_CURRENT ETH"
echo "  Objetivo: $ETH_TARGET_AMOUNT ETH"
echo "  Progreso: ${PROGRESS_PERCENT}%"
echo "  Falta: $ETH_MISSING ETH (\$${ETH_MISSING_USDT} USDT)"
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ ACTUALIZACIÓN COMPLETADA                         ║"
echo "╚═══════════════════════════════════════════════════════╝"
