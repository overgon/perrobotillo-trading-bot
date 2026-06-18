#!/bin/bash
# ════════════════════════════════════════════════════════
# 🤖 AUTO CAPITAL MANAGER - GESTIÓN AUTOMÁTICA DE CAPITAL
# ════════════════════════════════════════════════════════
# El bot analiza capital y decide position size óptimo
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

WORKSPACE="$HOME/.openclaw/workspace"
CONFIG_FILE="$WORKSPACE/config/capital-config.sh"
LOG_FILE="$HOME/.openclaw/logs/auto-capital-manager.log"
PROGRESS_FILE="$WORKSPACE/crypto-bots/capital-manager-progress.json"
TRADE_HISTORY="$WORKSPACE/crypto-bots/trade-history.json"

# ════════════════════════════════════════════════════════
# ⚙️ CONFIGURACIÓN INTELIGENTE
# ════════════════════════════════════════════════════════

# Rangos de capital vs position size recomendado
# El bot decide automáticamente según capital total

# Umbrales de win rate
WINRATE_EXCELLENT=95  # Mantener o subir ligeramente
WINRATE_GOOD=85       # Mantener
WINRATE_REGULAR=75    # Reducir ligeramente
WINRATE_BAD=70        # Reducir urgentemente

# ════════════════════════════════════════════════════════
# 🔧 FUNCIONES
# ════════════════════════════════════════════════════════

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

get_current_position() {
    local pos=$(grep "TRADE_POSITION_PERCENT=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2 | awk '{print $1}' | tr -d '"' | tr -d '#')
    # Si está vacío o es inválido, usar default 15
    if [ -z "$pos" ] || ! [[ "$pos" =~ ^[0-9]+$ ]]; then
        echo "15"
    else
        echo "$pos"
    fi
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

get_usdt_balance() {
    # Obtener SOLO el balance disponible en USDT (no el portfolio total)
    python3 << ENDPYTHON 2>/dev/null || echo "0"
import requests
import hmac, hashlib, time
import json

try:
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

    # Obtener account balance
    response = requests.get('https://api.binance.com/api/v3/account', headers=headers, params=params)
    account = response.json()

    # Buscar SOLO USDT disponible (free + locked)
    usdt_balance = 0
    for balance in account['balances']:
        if balance['asset'] == 'USDT':
            usdt_balance = float(balance['free']) + float(balance['locked'])
            break

    print(round(usdt_balance, 2))
except Exception as e:
    print("0")
ENDPYTHON
}

calculate_optimal_position() {
    local capital=$1
    local winrate=$2
    
    python3 << ENDPYTHON
capital = $capital
winrate = $winrate

# Reglas inteligentes del bot:
# 1. Capital < $1000 → Position 15% (conservador)
# 2. Capital $1000-$2000 → Position 20-25% (moderado)
# 3. Capital $2000-$3000 → Position 25-30% (crecimiento)
# 4. Capital > $3000 → Position 30% (máximo recomendado)
# 5. Win rate < 70% → Reducir 5% siempre
# 6. Win rate > 95% → Mantener o subir 2-5%

optimal = 20  # Default

# Regla por capital
if capital < 1000:
    optimal = 15
elif capital < 2000:
    optimal = 22
elif capital < 3000:
    optimal = 25
elif capital < 5000:
    optimal = 28
else:
    optimal = 30

# Ajuste por win rate
if winrate < 70:
    optimal = max(15, optimal - 5)  # Reducir si win rate bajo
elif winrate > 95:
    optimal = min(30, optimal + 2)  # Subir ligeramente si excelente

# Límites absolutos
optimal = max(15, min(30, optimal))

print(int(optimal))
ENDPYTHON
}

update_config() {
    local new_position=$1
    
    # Actualizar TRADE_POSITION_PERCENT en capital-config.sh
    sed -i "s/TRADE_POSITION_PERCENT=[0-9]*/TRADE_POSITION_PERCENT=$new_position/" "$CONFIG_FILE"
    
    # Actualizar dynamic-config.env también
    local dynamic_config="$WORKSPACE/crypto-bots/dynamic-config.env"
    if [ -f "$dynamic_config" ]; then
        sed -i "s/export POSITION_SIZE=[0-9]*/export POSITION_SIZE=$new_position/" "$dynamic_config"
    fi
    
    log "✅ Position size actualizado: ${new_position}%"
}

send_telegram() {
    local message="$1"
    local config_file="$HOME/.openclaw/openclaw.json"
    
    if [ -f "$config_file" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_file" 2>/dev/null)
        if [ -n "$bot_token" ] && [ "$bot_token" != "null" ]; then
            curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
                -H "Content-Type: application/json" \
                -d "{\"chat_id\":\"7543955537\",\"text\":\"$message\",\"parse_mode=HTML\"}" > /dev/null
        fi
    fi
}

save_progress() {
    local position=$1
    local winrate=$2
    local capital=$3
    local action=$4
    local reason=$5
    
    # Escapar comillas y caracteres especiales para JSON
    local reason_escaped=$(echo "$reason" | sed 's/"/\\"/g' | tr -d '\n')
    local action_escaped=$(echo "$action" | sed 's/"/\\"/g')
    
    cat > "$PROGRESS_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "position_size": ${position},
    "win_rate": ${winrate},
    "total_capital": ${capital},
    "last_action": "${action_escaped}",
    "reason": "${reason_escaped}",
    "history": []
}
EOF
}

# ════════════════════════════════════════════════════════
# 🤖 ANÁLISIS AUTOMÁTICO DEL BOT
# ════════════════════════════════════════════════════════

log "╔═══════════════════════════════════════════════════════╗"
log "║  🤖 AUTO CAPITAL MANAGER - ANÁLISIS AUTOMÁTICO      ║"
log "╚═══════════════════════════════════════════════════════╝"

# Obtener métricas actuales
CURRENT_POSITION=$(get_current_position)
WINRATE=$(get_win_rate)
USDT_BALANCE=$(get_usdt_balance)

log ""
log "=== MÉTRICAS ACTUALES ==="
log "Position Size: ${CURRENT_POSITION}%"
log "Win Rate: ${WINRATE}%"
log "Balance USDT Disponible: \$${USDT_BALANCE} USDT"
log ""

# Calcular position óptimo basado en USDT disponible
OPTIMAL_POSITION=$(calculate_optimal_position $USDT_BALANCE $WINRATE)

log "=== ANÁLISIS DEL BOT ==="
log "Position ÓPTIMO calculado: ${OPTIMAL_POSITION}%"
log ""

# Determinar acción
ACTION="MAINTAIN"
NEW_POSITION=$CURRENT_POSITION
REASON="Mantener posición actual"

# Validar que CURRENT_POSITION y OPTIMAL_POSITION sean números
if ! [[ "$CURRENT_POSITION" =~ ^[0-9]+$ ]]; then
    log "⚠️  WARNING: CURRENT_POSITION inválido ($CURRENT_POSITION), usando default 15"
    CURRENT_POSITION=15
fi

if ! [[ "$OPTIMAL_POSITION" =~ ^[0-9]+$ ]]; then
    log "⚠️  WARNING: OPTIMAL_POSITION inválido ($OPTIMAL_POSITION), usando default 15"
    OPTIMAL_POSITION=15
fi

DIFF=$((CURRENT_POSITION - OPTIMAL_POSITION))

if [ $DIFF -gt 5 ]; then
    # Position actual mucho mayor que óptimo → REDUCIR
    NEW_POSITION=$OPTIMAL_POSITION
    ACTION="DECREASE"
    REASON="Position actual (${CURRENT_POSITION}%) muy alto para USDT disponible de \$${USDT_BALANCE}"
    log "⚠️  REDUCIR: Position actual (${CURRENT_POSITION}%) > Óptimo (${OPTIMAL_POSITION}%)"
elif [ $DIFF -lt -5 ]; then
    # Position actual mucho menor que óptimo → AUMENTAR
    NEW_POSITION=$OPTIMAL_POSITION
    ACTION="INCREASE"
    REASON="Position actual (${CURRENT_POSITION}%) bajo para USDT disponible de \$${USDT_BALANCE}"
    log "✅ AUMENTAR: Position actual (${CURRENT_POSITION}%) < Óptimo (${OPTIMAL_POSITION}%)"
elif [ $DIFF -gt 0 ]; then
    # Ligera reducción
    NEW_POSITION=$OPTIMAL_POSITION
    ACTION="DECREASE_SMALL"
    REASON="Ajuste menor a la baja (USDT: \$${USDT_BALANCE})"
    log "📉 Reducción menor: ${CURRENT_POSITION}% → ${OPTIMAL_POSITION}%"
elif [ $DIFF -lt 0 ]; then
    # Ligero aumento
    NEW_POSITION=$OPTIMAL_POSITION
    ACTION="INCREASE_SMALL"
    REASON="Ajuste menor al alza (USDT: \$${USDT_BALANCE})"
    log "📈 Aumento menor: ${CURRENT_POSITION}% → ${OPTIMAL_POSITION}%"
else
    log "✅ Position óptimo ya configurado (USDT disponible: \$${USDT_BALANCE})"
fi

log ""
log "=== DECISIÓN DEL BOT ==="
log "Acción: ${ACTION}"
log "Position anterior: ${CURRENT_POSITION}%"
log "Position nuevo: ${NEW_POSITION}%"
log "Razón: ${REASON}"
log ""

# ════════════════════════════════════════════════════════
# 🎯 EJECUTAR CAMBIO
# ════════════════════════════════════════════════════════

if [ "$ACTION" != "MAINTAIN" ]; then
    log "🔄 Ejecutando cambio de position size..."
    update_config $NEW_POSITION
    
    # Notificar por Telegram
    if [ "$ACTION" = "INCREASE" ] || [ "$ACTION" = "INCREASE_SMALL" ]; then
        send_telegram "📈 AUTO CAPITAL MANAGER - AUMENTO AUTOMÁTICO

🤖 El bot analizó tu capital y decidió aumentar:

💵 USDT Disponible: \$${USDT_BALANCE} USDT
📊 Win Rate: ${WINRATE}%

🎯 Position Size:
   Antes: ${CURRENT_POSITION}%
   Ahora: ${NEW_POSITION}%

✅ Aumento automático completado
📈 Monitoreando win rate..."
    else
        send_telegram "📉 AUTO CAPITAL MANAGER - REDUCCIÓN AUTOMÁTICA

🤖 El bot analizó tu capital y decidió reducir:

💵 USDT Disponible: \$${USDT_BALANCE} USDT
📊 Win Rate: ${WINRATE}%

🎯 Position Size:
   Antes: ${CURRENT_POSITION}%
   Ahora: ${NEW_POSITION}%

✅ Reducción automática completada
🛡️  Riesgo controlado"
    fi
else
    log "✅ Manteniendo position size actual (óptimo)"
fi

# ════════════════════════════════════════════════════════
# 💾 GUARDAR PROGRESO
# ════════════════════════════════════════════════════════

save_progress $NEW_POSITION $WINRATE $USDT_BALANCE $ACTION "$REASON"

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
echo "  USDT Disponible: \$${USDT_BALANCE} USDT"
echo "  Acción: ${ACTION}"
echo "  Razón: ${REASON}"
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ ANÁLISIS AUTOMÁTICO COMPLETADO                   ║"
echo "╚═══════════════════════════════════════════════════════╝"
