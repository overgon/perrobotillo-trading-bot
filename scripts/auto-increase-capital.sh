#!/bin/bash
# ════════════════════════════════════════════════════════
# 💰 AUTO-INCREASE CAPITAL - AUMENTO AUTOMÁTICO DE CAPITAL
# ════════════════════════════════════════════════════════
# Ajusta automáticamente el position size según win rate
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

WORKSPACE="$HOME/.openclaw/workspace"
CONFIG_FILE="$WORKSPACE/config/capital-config.sh"
LOG_FILE="$HOME/.openclaw/logs/auto-increase-capital.log"
PROGRESS_FILE="$WORKSPACE/crypto-bots/capital-increase-progress.json"
TRADE_HISTORY="$WORKSPACE/crypto-bots/trade-history.json"

# ════════════════════════════════════════════════════════
# ⚙️ CONFIGURACIÓN
# ════════════════════════════════════════════════════════

# Position size actual y objetivo
CURRENT_POSITION=$(grep "POSITION_PERCENT=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "20")
MIN_POSITION=20
MAX_POSITION=25  # ⚠️ NO superar 25% con capital < $3000
INCREMENT_STEP=2  # Aumentar de 2 en 2%

# Umbrales de win rate
WINRATE_EXCELLENT=95  # Subir position
WINRATE_GOOD=80       # Mantener position
WINRATE_BAD=70        # Bajar position

# Capital mínimo para aumentar
MIN_CAPITAL_FOR_INCREASE=1500  # USDT (ajustado para capital actual ~$2000)

# ════════════════════════════════════════════════════════
# 🔧 FUNCIONES
# ════════════════════════════════════════════════════════

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

get_current_position() {
    grep "TRADE_POSITION_PERCENT=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2 | awk '{print $1}' | tr -d '"' || echo "20"
}

get_win_rate() {
    if [ -f "$TRADE_HISTORY" ]; then
        python3 << ENDPYTHON
import json
with open('$TRADE_HISTORY', 'r') as f:
    data = json.load(f)
total = data.get('totalTrades', 0)
wins = data.get('totalWins', 0)
if total > 0:
    print(round((wins / total) * 100, 2))
else:
    print(0)
ENDPYTHON
    else
        echo "0"
    fi
}

get_total_capital() {
    python3 << ENDPYTHON
import requests
import hmac, hashlib, time
import json
import os

# Leer API keys
with open('$HOME/.openclaw/secrets/binance.env', 'r') as f:
    for line in f:
        if line.startswith('BINANCE_API_KEY'):
            api_key = line.split('=')[1].strip()
        elif line.startswith('BINANCE_API_SECRET'):
            api_secret = line.split('=')[1].strip()

timestamp = int(time.time() * 1000)
signature = hmac.new(api_secret.encode(), f'timestamp={timestamp}'.encode(), hashlib.sha256).hexdigest()
headers = {'X-MBX-APIKEY': api_key}
params = {'timestamp': timestamp, 'signature': signature}

response = requests.get('https://api.binance.com/api/v3/account', headers=headers, params=params)
account = response.json()

usdt_total = 0
for balance in account['balances']:
    if balance['asset'] == 'USDT':
        usdt_total = float(balance['free']) + float(balance['locked'])
        break

# Sumar capital invertido en trades activos
coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
invested = 0
for coin in coins:
    file = f'$HOME/.openclaw/workspace/crypto-bots/{coin}-trade-state.json'
    if os.path.exists(file):
        with open(file, 'r') as f:
            data = json.load(f)
        for slot in data.get('slots', []):
            if slot.get('status') == 'ACTIVE':
                invested += slot.get('usdtSpent', 0)

print(round(usdt_total + invested, 2))
ENDPYTHON
}

update_config() {
    local new_position=$1
    
    # Actualizar POSITION_PERCENT en capital-config.sh
    sed -i "s/POSITION_PERCENT=\"[0-9]*\"/POSITION_PERCENT=\"$new_position\"/" "$CONFIG_FILE"
    
    # Actualizar dynamic-config.env también
    local dynamic_config="$WORKSPACE/crypto-bots/dynamic-config.env"
    if [ -f "$dynamic_config" ]; then
        sed -i "s/export POSITION_SIZE=[0-9]*/export POSITION_SIZE=$new_position/" "$dynamic_config"
    fi
    
    log "✅ Position size actualizado: ${new_position}%"
}

send_telegram() {
    local message="$1"
    # ✅ FIX: Source centralized notify.sh from Perrobotillo to avoid malformed JSON
    local notify_script="$HOME/.openclaw/workspace/crypto-bots/notify.sh"
    if [ -f "$notify_script" ]; then
        source "$notify_script"
        notify "AUTO_CAPITAL_INC" "$message"
        return $?
    fi
    # Fallback direct con --data-urlencode (evita quoting doble)
    local config_file="$HOME/.openclaw/openclaw.json"
    
    if [ -f "$config_file" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_file" 2>/dev/null)
        if [ -n "$bot_token" ] && [ "$bot_token" != "null" ]; then
            curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
                -d "chat_id=7543955537" \
                --data-urlencode "text=${message}" \
                -d "parse_mode=Markdown" > /dev/null
        fi
    fi
}

save_progress() {
    local position=$1
    local winrate=$2
    local capital=$3
    local action=$4
    
    cat > "$PROGRESS_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "position_size": $position,
    "win_rate": $winrate,
    "total_capital": $capital,
    "last_action": "$action",
    "history": [
        {"date": "$(date +%Y-%m-%d)", "position": $position, "winrate": $winrate, "action": "$action"}
    ]
}
EOF
}

# ════════════════════════════════════════════════════════
# 📊 ANÁLISIS AUTOMÁTICO
# ════════════════════════════════════════════════════════

log "╔═══════════════════════════════════════════════════════╗"
log "║  💰 AUTO-INCREASE CAPITAL - ANÁLISIS                 ║"
log "╚═══════════════════════════════════════════════════════╝"

# Obtener métricas actuales
CURRENT_POSITION=$(get_current_position)
WINRATE=$(get_win_rate)
TOTAL_CAPITAL=$(get_total_capital)

log ""
log "=== MÉTRICAS ACTUALES ==="
log "Position Size: ${CURRENT_POSITION}%"
log "Win Rate: ${WINRATE}%"
log "Capital Total: \$${TOTAL_CAPITAL} USDT"
log ""

# Determinar acción
ACTION="MAINTAIN"
NEW_POSITION=$CURRENT_POSITION

# Verificar capital mínimo
if (( $(echo "$TOTAL_CAPITAL < $MIN_CAPITAL_FOR_INCREASE" | bc -l) )); then
    log "⚠️  Capital insuficiente para aumentar (< \$${MIN_CAPITAL_FOR_INCREASE})"
    log "   Capital actual: \$${TOTAL_CAPITAL}"
    ACTION="WAIT_CAPITAL"
elif (( $(echo "$WINRATE >= $WINRATE_EXCELLENT" | bc -l) )); then
    # Win rate excelente → Subir position
    if [ $CURRENT_POSITION -lt $MAX_POSITION ]; then
        NEW_POSITION=$((CURRENT_POSITION + INCREMENT_STEP))
        if [ $NEW_POSITION -gt $MAX_POSITION ]; then
            NEW_POSITION=$MAX_POSITION
        fi
        ACTION="INCREASE"
        log "✅ Win Rate excelente (${WINRATE}%) → Aumentar position"
    else
        log "✅ Win Rate excelente pero position ya está en máximo (${MAX_POSITION}%)"
        ACTION="MAINTAIN"
    fi
elif (( $(echo "$WINRATE >= $WINRATE_GOOD" | bc -l) )); then
    # Win rate bueno → Mantener position
    log "✅ Win Rate bueno (${WINRATE}%) → Mantener position"
    ACTION="MAINTAIN"
elif (( $(echo "$WINRATE >= $WINRATE_BAD" | bc -l) )); then
    # Win rate regular → Mantener pero monitorear
    log "⚠️  Win Rate regular (${WINRATE}%) → Mantener y monitorear"
    ACTION="MONITOR"
else
    # Win rate malo → Bajar position
    if [ $CURRENT_POSITION -gt $MIN_POSITION ]; then
        NEW_POSITION=$((CURRENT_POSITION - INCREMENT_STEP))
        if [ $NEW_POSITION -lt $MIN_POSITION ]; then
            NEW_POSITION=$MIN_POSITION
        fi
        ACTION="DECREASE"
        log "❌ Win Rate bajo (${WINRATE}%) → Reducir position"
    else
        log "❌ Win Rate bajo pero position ya está en mínimo (${MIN_POSITION}%)"
        ACTION="MAINTAIN"
    fi
fi

log ""
log "=== DECISIÓN ==="
log "Acción: ${ACTION}"
log "Position actual: ${CURRENT_POSITION}%"
log "Position nuevo: ${NEW_POSITION}%"
log ""

# ════════════════════════════════════════════════════════
# 🎯 EJECUTAR CAMBIO
# ════════════════════════════════════════════════════════

case $ACTION in
    "INCREASE")
        log "🔄 Ejecutando aumento de position size..."
        update_config $NEW_POSITION

        send_telegram "💰 CAPITAL UP - ${NEW_POSITION}% position
WR: ${WINRATE}% | Capital: \$${TOTAL_CAPITAL} USDT
${CURRENT_POSITION}% → ${NEW_POSITION}% (+${INCREMENT_STEP}%) ✅"
        ;;
    
    "DECREASE")
        log "🔄 Ejecutando reducción de position size..."
        update_config $NEW_POSITION

        send_telegram "📉 CAPITAL DOWN - ${NEW_POSITION}% position
WR: ${WINRATE}% | Capital: \$${TOTAL_CAPITAL} USDT
${CURRENT_POSITION}% → ${NEW_POSITION}% (-${INCREMENT_STEP}%) ⚠️"
        ;;
    
    "WAIT_CAPITAL")
        log "⏳ Esperando más capital para aumentar..."

        if [ ! -f "$PROGRESS_FILE" ]; then
            send_telegram "⏳ ESPERANDO CAPITAL
\$${TOTAL_CAPITAL} USDT (faltan \$$(echo "$MIN_CAPITAL_FOR_INCREASE - $TOTAL_CAPITAL" | bc) para \$${MIN_CAPITAL_FOR_INCREASE}) 🐕"
        fi
        ;;
    
    "MAINTAIN"|"MONITOR")
        log "✅ Manteniendo position size actual"
        ;;
esac

# ════════════════════════════════════════════════════════
# 💾 GUARDAR PROGRESO
# ════════════════════════════════════════════════════════

save_progress $NEW_POSITION $WINRATE $TOTAL_CAPITAL $ACTION

log ""
log "✅ Progreso guardado en $PROGRESS_FILE"
log ""

# ════════════════════════════════════════════════════════
# 📋 RESUMEN FINAL
# ════════════════════════════════════════════════════════

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  📋 RESUMEN FINAL                                     ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "  Position Size: ${NEW_POSITION}%"
echo "  Win Rate: ${WINRATE}%"
echo "  Capital Total: \$${TOTAL_CAPITAL} USDT"
echo "  Acción: ${ACTION}"
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ ANÁLISIS COMPLETADO                               ║"
echo "╚═══════════════════════════════════════════════════════╝"
