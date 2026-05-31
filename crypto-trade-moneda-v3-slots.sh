#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🤖 CRYPTO TRADE BOT V3 - MULTI-SLOT SYSTEM           ║
# ║  Soporta hasta 3 trades simultáneos por moneda        ║
# ╚═══════════════════════════════════════════════════════╝

# BUG-041 FIX: set -e causa exit prematuro cuando auto_reset_slots retorna 1
# set -e  # REMOVIDO - funciones pueden retornar 1 normalmente sin ser error fatal

SYMBOL="$1"
if [ -z "$SYMBOL" ]; then
    echo "❌ Uso: $0 <SYMBOL> (ej: BTC, ETH, BNB, SOL, LINK, XRP)"
    exit 1
fi

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="$HOME/.openclaw/secrets"
LOGS="$HOME/.openclaw/logs"
BINANCE="https://api.binance.com"

source "$SECRETS/binance.env"

# ════════════════════════════════════════════════════════
# 🎯 CONFIGURACIÓN OPTIMIZADA - FASE 1 v2.1 + 20/80
# ════════════════════════════════════════════════════════
# Actualizado: 2026-04-22 12:55 CST (Perrobotillo)
# Estrategia: 20% HOLDING + 80% TRADING
# Objetivo: Máximo capital trabajando sin NOTIONAL filter
# Status: LISTO PARA OPERAR

# Source config 20/80
CONFIG_FILE="$WORKSPACE/config/capital-config.sh"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
    log "✅ Estrategia 20/80 cargada"
else
    log "⚠️ Config 20/80 no encontrada, usando defaults"
    HOLD_PERCENT=20
    TRADE_PERCENT=80
    TRADE_POSITION_PERCENT=40
    MIN_TRADE_SIZE=10
fi

# ════════════════════════════════════════════════════════
# 🧠 CARGAR CONFIGURACIÓN DINÁMICA (Auto-Adjust)
# ════════════════════════════════════════════════════════

DYNAMIC_CONFIG="${SCRIPT_DIR}/dynamic-config.env"
if [ -f "$DYNAMIC_CONFIG" ]; then
    source "$DYNAMIC_CONFIG"
    
    # Aplicar parámetros dinámicos si existen
    [ -n "$TP1" ] && NORMAL_TP1=$TP1 && AGGRESSIVE_TP1=$TP1
    [ -n "$TP2" ] && NORMAL_TP2=$TP2 && AGGRESSIVE_TP2=$TP2
    [ -n "$TP3" ] && NORMAL_TP3=$TP3 && AGGRESSIVE_TP3=$TP3
    [ -n "$STOP_LOSS" ] && STOP_LOSS_PERCENT=$STOP_LOSS
    [ -n "$POSITION_SIZE" ] && TRADE_POSITION_PERCENT=$POSITION_SIZE
    
    log "🧠 MODO: ${MARKET_MODE:-LATERAL}"
    log "   TP1: ${NORMAL_TP1}% | TP2: ${NORMAL_TP2}% | TP3: ${NORMAL_TP3}%"
    log "   SL: ${STOP_LOSS_PERCENT:-5.0}%"
else
    log "⚠️ Sin config dinámica (usando defaults)"
fi

# Fallback: Asegurar que TRADE_POSITION_PERCENT tenga valor default
if [ -z "$TRADE_POSITION_PERCENT" ] || [ "$TRADE_POSITION_PERCENT" = "0" ]; then
    TRADE_POSITION_PERCENT=40
    log "💡 TRADE_POSITION_PERCENT no definido, usando default 40%"
fi

# Fallback para NORMAL_TRADE_PERCENT
if [ -z "$NORMAL_TRADE_PERCENT" ] || [ "$NORMAL_TRADE_PERCENT" = "0" ]; then
    NORMAL_TRADE_PERCENT=$TRADE_POSITION_PERCENT
    log "💡 NORMAL_TRADE_PERCENT no definido, usando TRADE_POSITION_PERCENT=$NORMAL_TRADE_PERCENT%"
fi

TRADING_HOURS_OPTIMAL="00,01,13,14,15,16,21,22"
AGGRESSIVE_MODE=true

# TRADE PERCENT - CONFIGURADO POR 20/80
# El tamaño real se calcula dinámicamente basado en USDT disponible
NORMAL_TRADE_PERCENT=$TRADE_POSITION_PERCENT  # 40% del capital de trading
AGGRESSIVE_TRADE_PERCENT=45  # Un poco más agresivo

# ACUMULACIÓN REDUCIDA (15% → 5%)
# Más ganancias realizadas, menos acumulación
ACCUMULATION_PERCENT=5  # (antes: 15)

# ════════════════════════════════════════════════════════
# 🔄 MODO RECICLAJE DE SLOTS (HÍBRIDO - 2026-05-03)
# ════════════════════════════════════════════════════════
# Para NUEVAS entradas: TP1 → READY → nueva entrada
# Para entradas EXISTENTES: TP1 → TP2 → TP3 (piramidal)
# 
# true = Reciclaje activado para nuevas entradas
# false = Mantener estrategia piramidal tradicional
SLOT_RECYCLING_ENABLED=true

# ════════════════════════════════════════════════════════
# 🎯 SCALPING MODE (LATERAL MARKET - 2026-05-08)
# ════════════════════════════════════════════════════════
# Activado solo en mercado lateral para ganancias rápidas
# Target: 1.0% (rango: 0.8-1.5%)
# SL: 2.5% (más tight para scalping)
SCALPING_ENABLED=true
SCALP_TARGET_PERCENT="1.0"
SCALP_SL_PERCENT="2.5"
SCALP_MIN_PROFIT="0.50"

# STOP LOSS POR COIN (basado en volatilidad diaria promedio)
# ACTUALIZADO 2026-05-02: Ajustado para mercado lateral (5-6% vs 3-4%)
# Razón: Evitar ruido del mercado y reducir falsos positivos
declare -A STOP_LOSS_BY_COIN=(
    ["BTC"]="5.5"   # Antes: 3.5% (Volatilidad 2-4%)
    ["ETH"]="6.0"   # Antes: 4.5% (Volatilidad 3-5%)
    ["SOL"]="8.0"   # Antes: 7.0% (Volatilidad 5-8%)
    ["LINK"]="7.0"  # Antes: 5.5% (Volatilidad 4-6%)
    ["XRP"]="6.0"   # Antes: 4.5% (Volatilidad 3-5%)
    ["BNB"]="5.5"   # Antes: 3.5% (Volatilidad 2-4%)
    ["AVAX"]="7.5"  # Antes: 6.0% (Volatilidad 4-7%)
)

# TAKE PROFIT OPTIMIZADOS v3 (2026-05-02) - MERCADO LATERAL
# Ajustado para mercado en consolidación (rangos estrechos)
# TP1: 2.5% → 1.8% (tomar profits más rápido)
# TP2: 5.0% → 3.5% (más realista en rango)
# TP3: 8.0% → 5.0% (objetivo alcanzable)
# Win rate esperado: 16% → 45-50%
NORMAL_TP1=1.8   # Reducido de 2.5% (mercado lateral)
NORMAL_TP2=3.5   # Reducido de 5.0% (mercado lateral)
NORMAL_TP3=5.0   # Reducido de 8.0% (mercado lateral)

AGGRESSIVE_TP1=2.0
AGGRESSIVE_TP2=4.0
AGGRESSIVE_TP3=6.0

# ════════════════════════════════════════════════════════
# 🤖 ML TP PREDICTION - DYNAMIC TP ADJUSTMENT
# ════════════════════════════════════════════════════════
# Obtiene recomendación de ML para TPs dinámicos
# Ejecuta predict-tp.py si no hay recomendaciones recientes
ML_RECOMMENDATIONS_FILE="$HOME/.openclaw/workspace/ml/tp-recommendations.json"
ML_SCRIPT="$HOME/.openclaw/workspace/ml/predict-tp.py"
ML_GETTER="$HOME/.openclaw/workspace/ml/get-tp-recommendation.sh"

# Función para obtener TPs de ML
get_ml_tp() {
    local coin="$1"
    
    # Si no existe el archivo de recomendaciones o tiene > 5 minutos, actualizar
    if [ ! -f "$ML_RECOMMENDATIONS_FILE" ] || [ $(find "$ML_RECOMMENDATIONS_FILE" -mmin +5 2>/dev/null | wc -l) -gt 0 ]; then
        log "🤖 ML: Actualizando predicciones..."
        python3 "$ML_SCRIPT" > /dev/null 2>&1 &
    fi
    
    # Obtener recomendación para esta coin
    if [ -f "$ML_RECOMMENDATIONS_FILE" ] && [ -x "$ML_GETTER" ]; then
        local ml_tps=$(bash "$ML_GETTER" "$coin" 2>/dev/null)
        if [ -n "$ml_tps" ]; then
            ML_TP1=$(echo "$ml_tps" | cut -d'|' -f1)
            ML_TP2=$(echo "$ml_tps" | cut -d'|' -f2)
            ML_TP3=$(echo "$ml_tps" | cut -d'|' -f3)
            log "🤖 ML $coin: TP1=$ML_TP1% TP2=$ML_TP2% TP3=$ML_TP3%"
            return 0
        fi
    fi
    
    # Fallback a TPs normales
    ML_TP1=$NORMAL_TP1
    ML_TP2=$NORMAL_TP2
    ML_TP3=$NORMAL_TP3
    return 1
}

# Obtener TPs dinámicos para esta coin (si ML está disponible)
if [ -f "$ML_SCRIPT" ] && [ -f "$ML_GETTER" ]; then
    get_ml_tp "$COIN"
    # Sobrescribir TPs con recomendación de ML
    TP1=$ML_TP1
    TP2=$ML_TP2
    TP3=$ML_TP3
    log "🤖 ML TP Prediction: $COIN → TP1=$TP1% TP2=$TP2% TP3=$TP3%"
else
    log "⚠️  ML no disponible, usando TPs fijos"
fi

# Zero Trust + NOTIONAL Filter Fix (BUG-052)
MIN_TRADE_USDT=10  # Mínimo Binance con margen (era $5)
MAX_TRADE_USDT=100
MIN_BALANCE_CHECK=true
CHECK_DAILY_LOSS=true
MAX_DAILY_LOSS_PERCENT=3
BINANCE_FEE_PERCENT=0.015

# Validaciones pre-trade (BUG-052)
MIN_PORTFOLIO_FOR_TRADE=50  # No operar si portfolio < $50
SNAPSHOT_REQUIRED=true      # Requiere snapshot válido

# FASE 1: Trailing Stop DESACTIVADO para mercado lateral
# ACTUALIZADO 2026-05-02: Trailing muy sensible causaba cierres prematuros
# Se reactivará cuando BTC rompa rango ($77,750 o $78,600)
TRAILING_STOP_ENABLED=false
TRAILING_AFTER_TP1_PERCENT="2.0"  # Aumentado de 0.5% a 2.0% (menos sensible)
TRAILING_AFTER_TP2_PERCENT="4.0"  # Aumentado de 3.0% a 4.0% (más margen)

# Multi-Slot
MAX_SLOTS=3

# ============================================
# 📁 FILES
# ============================================

STATE_FILE="$WORKSPACE/crypto-bots/${SYMBOL}-trade-state.json"
DAILY_PNL_FILE="$WORKSPACE/crypto-bots/${SYMBOL}-daily-pnl.json"
BOT_FILE="$WORKSPACE/crypto-bots/${SYMBOL}-bot.json"

# ============================================
# 🔧 FUNCIONES DE LOGGING
# ============================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$SYMBOL] $1" | tee -a "$LOGS/trade-${SYMBOL}.log"
}

log_debug() {
    [ "${DEBUG:-false}" = "true" ] && echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$SYMBOL-DEBUG] $1" | tee -a "$LOGS/trade-${SYMBOL}-debug.log" || true
}

# ============================================
# 📜 HISTORICAL TRADE LOGGING
# ============================================

HISTORY_FILE="$WORKSPACE/crypto-bots/trade-history.json"

init_trade_history() {
    if [ ! -f "$HISTORY_FILE" ]; then
        cat > "$HISTORY_FILE" << EOF
{
  "version": "1.0",
  "created": "$(date -Iseconds)",
  "totalTrades": 0,
  "totalWins": 0,
  "totalLosses": 0,
  "totalProfitUSDT": 0,
  "totalLossUSDT": 0,
  "netPnLUSDT": 0,
  "winRate": 0,
  "trades": []
}
EOF
    fi
}

log_trade_to_history() {
    local slot_id="$1"
    local close_type="$2"  # TP1, TP2, TP3, SL, TRAILING, SCALP
    local entry_price="$3"
    local exit_price="$4"
    local quantity="$5"
    local pnl="$6"
    
    init_trade_history
    
    # Leer contadores actuales
    local current_trades=$(jq -r '.totalTrades // 0' "$HISTORY_FILE")
    local current_wins=$(jq -r '.totalWins // 0' "$HISTORY_FILE")
    local current_losses=$(jq -r '.totalLosses // 0' "$HISTORY_FILE")
    local current_profit=$(jq -r '.totalProfitUSDT // 0' "$HISTORY_FILE")
    local current_loss=$(jq -r '.totalLossUSDT // 0' "$HISTORY_FILE")
    local current_net=$(jq -r '.netPnLUSDT // 0' "$HISTORY_FILE")
    
    # Actualizar contadores
    local new_trades=$((current_trades + 1))
    local new_wins=$current_wins
    local new_losses=$current_losses
    local new_profit=$current_profit
    local new_loss=$current_loss
    local new_net=$(awk -v c="$current_net" -v p="$pnl" 'BEGIN {printf "%.8f", c + p}')
    
    # Determinar si fue win o loss
    local is_win=$(awk -v p="$pnl" 'BEGIN {print (p > 0) ? 1 : 0}')
    if [ "$is_win" = "1" ]; then
        new_wins=$((current_wins + 1))
        new_profit=$(awk -v c="$current_profit" -v p="$pnl" 'BEGIN {printf "%.8f", c + p}')
    else
        new_losses=$((current_losses + 1))
        new_loss=$(awk -v c="$current_loss" -v p="$pnl" 'BEGIN {printf "%.8f", c + p}')
    fi
    
    # Calcular win rate
    local win_rate=$(awk -v w="$new_wins" -v t="$new_trades" 'BEGIN {if (t > 0) printf "%.2f", (w/t)*100; else print "0"}')
    
    # BUG FIX: Verificar duplicado EXACTO (mismo symbol+slot+closeType+timestamp minuto)
    # NO bloquear trades nuevos del mismo slot
    local current_minute=$(date +%Y-%m-%dT%H:%M)
    local existing=$(jq --arg sym "$SYMBOL" --argjson slot "$slot_id" --arg close "$close_type" --arg ts "$current_minute" \
        '[.trades[] | select(.symbol == $sym and .slotId == $slot and .closeType == $close) | select(.timestamp | startswith($ts))] | length' \
        "$HISTORY_FILE" 2>/dev/null)
    
    if [ "$existing" -gt 0 ]; then
        log "  ⚠️ Trade DUPLICADO del mismo minuto (${SYMBOL} Slot ${slot_id} ${close_type}) - NO guardar"
        return 0  # Salir sin guardar
    fi
    
    # Crear nuevo trade entry
    local trade_id=$new_trades
    local timestamp=$(date -Iseconds)
    local close_time=$(date '+%Y-%m-%d %H:%M:%S')
    
    local new_trade=$(jq -n \
        --argjson id "$trade_id" \
        --arg symbol "$SYMBOL" \
        --argjson slot "$slot_id" \
        --arg type "LONG" \
        --argjson entry "$entry_price" \
        --argjson exit "$exit_price" \
        --argjson qty "$quantity" \
        --arg closeType "$close_type" \
        --argjson pnl "$pnl" \
        --arg ts "$timestamp" \
        --arg closeTime "$close_time" \
        '{
            id: $id,
            symbol: $symbol,
            slotId: $slot,
            type: $type,
            entryPrice: $entry,
            exitPrice: $exit,
            quantity: $qty,
            closeType: $closeType,
            pnlUSDT: $pnl,
            timestamp: $ts,
            closeTime: $closeTime,
            seeded: false
        }')
    
    # Actualizar archivo con jq
    local temp_file="/tmp/history_$$.json"
    jq --argjson trades "$new_trade" \
       --argjson totalTrades "$new_trades" \
       --argjson totalWins "$new_wins" \
       --argjson totalLosses "$new_losses" \
       --argjson totalProfit "$new_profit" \
       --argjson totalLoss "$new_loss" \
       --argjson netPnL "$new_net" \
       --arg winRate "$win_rate" \
       '.trades = [$trades] + .trades | .totalTrades = $totalTrades | .totalWins = $totalWins | .totalLosses = $totalLosses | .totalProfitUSDT = $totalProfit | .totalLossUSDT = $totalLoss | .netPnLUSDT = $netPnL | .winRate = ($winRate | tonumber)' \
       "$HISTORY_FILE" > "$temp_file" && mv "$temp_file" "$HISTORY_FILE"
    
    log "  📜 Trade logged to history: #${trade_id} ${SYMBOL} ${close_type} PnL=\$${pnl}"
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
    local timestamp=$(date -u +%s%3N)
    local query_string="timestamp=${timestamp}&recvWindow=5000"
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
    local total=$usdt
    
    for coin in BTC ETH BNB SOL LINK XRP AVAX; do
        local balance=$(get_balance "$coin")
        if [ -n "$balance" ] && [ "$balance" != "0" ] && (( $(echo "$balance > 0" | bc -l) )); then
            local price=$(curl -s "${BINANCE}/api/v3/ticker/price?symbol=${coin}USDT" 2>/dev/null | jq -r '.price // 0')
            if [ -n "$price" ] && [ "$price" != "0" ]; then
                local value=$(echo "scale=2; $balance * $price" | bc)
                total=$(echo "scale=2; $total + $value" | bc)
            fi
        fi
    done
    
    echo "$total"
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
    {"slotId": 1, "status": "READY", "type": "NONE", "orderId": null, "entryPrice": null, "quantity": null, "usdtSpent": null, "stopLoss": null, "tp1": null, "tp2": null, "tp3": null, "tp1Done": false, "tp2Done": false, "tp3Done": false, "timestamp": null},
    {"slotId": 2, "status": "READY", "type": "NONE", "orderId": null, "entryPrice": null, "quantity": null, "usdtSpent": null, "stopLoss": null, "tp1": null, "tp2": null, "tp3": null, "tp1Done": false, "tp2Done": false, "tp3Done": false, "timestamp": null},
    {"slotId": 3, "status": "READY", "type": "NONE", "orderId": null, "entryPrice": null, "quantity": null, "usdtSpent": null, "stopLoss": null, "tp1": null, "tp2": null, "tp3": null, "tp1Done": false, "tp2Done": false, "tp3Done": false, "timestamp": null}
  ],
  "lastUpdated": "$(date -Iseconds)"
}
EOF
    fi
}

get_available_slot() {
    local slot_id=$(jq -r '.slots[] | select(.status == "READY") | .slotId' "$STATE_FILE" | head -1)
    echo "${slot_id:-0}"
}

get_active_slots_count() {
    local count=$(jq '[.slots[] | select(.status == "ACTIVE")] | length' "$STATE_FILE")
    echo "$count"
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
    
    log "DEBUG: update_slot_field slot=$slot_id field=$field value=$value"
    
    # Determinar tipo de valor
    local jq_update=""
    local jq_type=""
    
    # Booleanos
    if [ "$value" = "true" ] || [ "$value" = "false" ]; then
        jq_update='.slots = [.slots[] | if (.slotId | tostring) == $sid then .[$field] = ($val == "true") else . end]'
        jq_type="BOOLEAN"
        log "  → Tipo: BOOLEAN"
    # Números (solo dígitos, puntos, signos)
    elif echo "$value" | grep -qE '^-?[0-9]+\.?[0-9]*$'; then
        jq_update='.slots = [.slots[] | if (.slotId | tostring) == $sid then .[$field] = ($val | tonumber) else . end]'
        jq_type="NUMERIC"
        log "  → Tipo: NUMERIC"
    # Strings (todo lo demás)
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
        local jq_error=$(cat /tmp/jq_error_$$.txt)
        log "  ❌ jq falló: $jq_error"
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
# 💰 ACTUALIZAR P&L DESPUÉS DE CIERRE
# ============================================

update_pnl_after_close() {
    local slot_id="$1"
    local close_type="$2"  # TP1, TP2, TP3, SL
    local entry_price="$3"
    local exit_price="$4"
    local quantity="$5"
    local fee_usd="$6"
    
    init_daily_pnl
    
    # Calcular P&L
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
    
    # Leer P&L actual
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
    
    log "  📊 P&L actualizado: Trades=$new_trades, Wins=$new_wins, Net=\$$new_pnl"
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
    local max_loss=$(echo "scale=2; $portfolio_value * $MAX_DAILY_LOSS_PERCENT / 100" | bc)
    
    # ============================================
    # 🛡️ VALIDACIONES CRÍTICAS (BUG-052)
    # ============================================
    
    # VALIDACIÓN 1: Portfolio no puede ser $0
    if [ -z "$portfolio_value" ] || [ "$portfolio_value" = "0" ] || [ "$portfolio_value" = "0.00" ]; then
        log "❌ VALIDACIÓN FALLIDA: Portfolio = \$0 (cálculo incorrecto)"
        log "  Abortando check de límite diario para evitar falso positivo"
        log "  🛡️ BUG-052 PREVENIDO: Límite diario cancelado por datos incompletos"
        return 0  # No abortar trading, solo saltar el check de límite
    fi
    
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
    
    if (( $(echo "$daily_loss >= $max_loss" | bc -l) )); then
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
            send_telegram "⚠️ LÍMITE DIARIO - $SYMBOL

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

send_telegram() {
    local message="$1"
    local config_file="$HOME/.openclaw/openclaw.json"
    log "📱 Intentando enviar Telegram..."
    if [ -f "$config_file" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_file" 2>/dev/null)
        if [ -n "$bot_token" ] && [ "$bot_token" != "null" ]; then
            local result=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
                -H "Content-Type: application/json" \
                -d "{\"chat_id\":\"7543955537\",\"text\":\"$message\",\"parse_mode=HTML\"}" 2>&1)
            local http_code=$(echo "$result" | grep "HTTP_CODE:" | cut -d':' -f2)
            if [ "$http_code" = "200" ]; then
                log "✅ Telegram enviado exitosamente"
            else
                log "❌ Error Telegram: HTTP $http_code - $result"
            fi
        else
            log "❌ Error: Bot token no encontrado en openclaw.json"
        fi
    else
        log "❌ Error: openclaw.json no encontrado"
    fi
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
    # 🧠 ML VALIDATOR - Pre-Trade Validation
    # ════════════════════════════════════════════════════
    
    ML_VALIDATOR="$WORKSPACE/ml/ml-validator.py"
    local ml_approved="N/A"
    local ml_confidence="N/A"
    local ml_position="N/A"
    local ml_reason="N/A"
    local ml_risk="N/A"
    
    if [ -f "$ML_VALIDATOR" ]; then
        log "🧠 ML Validator: Consultando validación pre-trade..."
        
        # Ejecutar validator y capturar resultado (2>&1 para capturar errores también)
        log "🔍 Ejecutando: python3 $ML_VALIDATOR $SYMBOL NORMAL LONG"
        ml_result=$(python3 "$ML_VALIDATOR" "$SYMBOL" "NORMAL" "LONG" 2>&1)
        ml_exit_code=$?
        log "📝 ML Exit code: $ml_exit_code"
        log "📝 ML Resultado crudo:"
        echo "$ml_result" | while read line; do log "   $line"; done
        
        # Parsear resultado
        ml_approved=$(echo "$ml_result" | grep -o '"approved": [a-z]*' | cut -d: -f2 | tr -d ' ')
        ml_confidence=$(echo "$ml_result" | grep -o '"confidence": [0-9]*' | cut -d: -f2 | tr -d ' ')
        ml_position=$(echo "$ml_result" | grep -o '"position_size_percent": [0-9]*' | cut -d: -f2 | tr -d ' ')
        ml_reason=$(echo "$ml_result" | grep -o '"reason": "[^"]*"' | cut -d: -f2 | tr -d '"')
        ml_risk=$(echo "$ml_result" | grep -o '"risk_level": "[^"]*"' | cut -d: -f2 | tr -d '"')
        
        log "🔍 ML Parseado: approved='$ml_approved', confidence='$ml_confidence', position='$ml_position'"
        log "🔍 ML Parseado: reason='$ml_reason', risk='$ml_risk'"
        
        # Si ML rechaza el trade, skippear
        if [ "$ml_approved" = "false" ]; then
            log "❌ ML Validator RECHAZÓ el trade (confianza: ${ml_confidence}%)"
            log "   Razón: $ml_reason"
            return 1
        fi
        
        # Si ML sugiere menor posición, ajustar
        if [ -n "$ml_position" ] && [ "$ml_position" -lt "$position_percent" ]; then
            log "⚠️ ML sugiere reducir posición: ${position_percent}% → ${ml_position}%"
            position_percent="$ml_position"
        fi
        
        log "✅ ML Validator APROBÓ trade con ${ml_confidence}% confianza"
    else
        log "⚠️ ML Validator no encontrado, continuando sin validación"
    fi
    
    check_daily_limit || return 1
    
    local usdt_balance=$(get_balance "USDT")
    [ -z "$usdt_balance" ] || [ "$usdt_balance" = "0" ] && { log "⚠️ USDT balance no disponible"; return 1; }
    
    local price=$(curl -s "${BINANCE}/api/v3/ticker/price?symbol=${SYMBOL}USDT" 2>/dev/null | jq -r '.price')
    [ -z "$price" ] || [ "$price" = "0" ] && { log "⚠️ Precio no disponible"; return 1; }
    
    # Calcular order value con position %
    local order_value=$(awk -v bal="$usdt_balance" -v pct="$position_percent" 'BEGIN {printf "%.2f", bal * pct / 100}')
    
    # Si position % da menos de $5, usar TODO el balance (si alcanza)
    log "DEBUG: Checking if $order_value < $MIN_ORDER_USDT"
    if (( $(awk -v val="$order_value" -v min="5" 'BEGIN {print (val < min) ? 1 : 0}') )); then
        log "⚠️ ${position_percent}% = \$${order_value} < \$${MIN_ORDER_USDT} mínimo"
    log "DEBUG: Condition result = $(awk -v val="$order_value" -v min="5" 'BEGIN {print (val < min) ? 1 : 0}')"
        
        # Verificar si el balance TOTAL alcanza para el mínimo
        if (( $(awk -v bal="$usdt_balance" -v min="5" 'BEGIN {print (bal < min) ? 1 : 0}') )); then
            log "❌ Balance insuficiente para trade mínimo (\$${usdt_balance} < \$${MIN_ORDER_USDT})"
            return 1
        fi
        
        # Usar 100% del balance en vez de position %
        log "💡 Usando 100% del balance (\$${usdt_balance}) en vez de ${position_percent}%"
        order_value="$usdt_balance"
        log "DEBUG: order_value actualizado a $order_value"
    fi
    
    log "DEBUG: Calculando quantity con order_value=$order_value, price=$price"
    
    # Calcular cantidad basada en order value
    local quantity=$(awk -v val="$order_value" -v p="$price" 'BEGIN {printf "%.8f", val / p}')
    log "DEBUG: quantity raw = $quantity"
    [ -z "$quantity" ] || [ "$quantity" = "0.00000000" ] && { log "⚠️ Cantidad calculada inválida"; return 1; }
    quantity=$(format_quantity "$SYMBOL" "$quantity")
    
    local tp1=$(echo "scale=8; $price * (1 + $TP1_PERCENT / 100)" | bc)
    local tp2=$(echo "scale=8; $price * (1 + $TP2_PERCENT / 100)" | bc)
    local tp3=$(echo "scale=8; $price * (1 + $TP3_PERCENT / 100)" | bc)
    local sl=$(echo "scale=8; $price * (1 - $STOP_LOSS_PERCENT / 100)" | bc)
    
    # ============================================
    # 🚀 EJECUTAR ORDEN PRIMERO (antes de notificar)
    # ============================================
    
    # DEBUG: Log balance antes de orden
    log "💰 DEBUG: Balance USDT free: \$${usdt_balance}"
    log "💰 DEBUG: Order value calculado: \$${order_value}"
    log "💰 DEBUG: Quantity: $quantity @ \$${price}"
    log "💰 DEBUG: Slot $slot_id de $MAX_SLOTS"
    
    # Verificar mínimo de Binance ANTES de enviar orden
    if (( $(awk -v val="$order_value" -v min="10" 'BEGIN {print (val < min) ? 1 : 0}') )); then
        log "❌ Orden rechazada: \$${order_value} < \$10 mínimo de Binance"
        send_telegram "❌ ORDEN FALLÓ - $SYMBOL

Slot: $slot_id / $MAX_SLOTS
Razón: Order value \$${order_value} es menor al mínimo de Binance (\$10)
Balance disponible: \$${usdt_balance}

Ajusta position_size o espera más capital. 🛡️"
        return 1
    fi
    
    log "📈 BUY Slot $slot_id: $quantity $SYMBOL @ \$${price}"
    
    # DEBUG: Log details antes de enviar
    log "🔍 DEBUG: Quantity='$quantity' | Price='$price' | OrderValue='$order_value'"
    log "🔍 DEBUG: Balance free='$usdt_balance' | Position%='$position_percent'"
    
    # Validar quantity antes de enviar orden
    if [ -z "$quantity" ] || [ "$quantity" = "0" ] || [ "$quantity" = "0.00000000" ]; then
        log "❌ Quantity inválida: '$quantity'"
        send_telegram "❌ ORDEN FALLÓ - $SYMBOL

Slot: $slot_id / $MAX_SLOTS
Razón: Quantity calculada es inválida ($quantity)
Precio: \$${price} | Order value: \$${order_value}

Revisa configuración del bot. 🛡️"
        return 1
    fi
    
    local buy_result=$(place_buy_order_market "$SYMBOL" "$quantity")
    
    # DEBUG: Log raw response
    log "🔍 DEBUG: Binance response: $buy_result"
    
    local buy_status=$(echo "$buy_result" | jq -r '.status // "ERROR"')
    
    # Verificar si la orden fue exitosa
    if [ "$buy_status" != "NEW" ] && [ "$buy_status" != "FILLED" ]; then
        local error_msg=$(echo "$buy_result" | jq -r '.msg // "Unknown error"' 2>/dev/null)
        local error_code=$(echo "$buy_result" | jq -r '.code // "-1"' 2>/dev/null)
        
        # Fallback si jq falla
        [ -z "$error_msg" ] || [ "$error_msg" = "null" ] && error_msg="Unknown error"
        [ -z "$error_code" ] || [ "$error_code" = "null" ] && error_code="-1"
        
        log "❌ Orden falló: status=$buy_status, code=$error_code, msg=$error_msg"
        
        # Obtener balance actual para debugging
        local current_balance=$(get_balance "USDT")
        
        # Notificar falla por Telegram con más contexto
        send_telegram "❌ ORDEN FALLÓ - $SYMBOL

Slot: $slot_id / $MAX_SLOTS
Razón: $error_msg
Código: $error_code

Balance disponible: \$${current_balance} USDT
Order value: \$${order_value}

El slot permanece disponible para próximo trade. 🛡️"
        
        return 1
    fi
    
    # Orden exitosa - extraer datos reales de ejecución
    local order_id=$(echo "$buy_result" | jq -r '.orderId')
    local fill_price=$(echo "$buy_result" | jq -r '.fills[0].price // "'$price'"')
    local usdt_spent=$(echo "scale=2; $quantity * $fill_price" | bc)
    local fee_buy=$(echo "scale=4; $usdt_spent * $BINANCE_FEE_PERCENT / 100" | bc)
    local total_cost=$(echo "scale=2; $usdt_spent + $fee_buy" | bc)
    
    log "✅ Orden ejecutada: ID=$order_id, fill_price=\$${fill_price}"
    
    # ============================================
    # 📝 ACTUALIZAR ESTADO DEL SLOT
    # ============================================
    
    if [ "$buy_status" = "NEW" ] || [ "$buy_status" = "FILLED" ]; then

        # Actualizar slot
        update_slot_status "$slot_id" "ACTIVE"
        update_slot_field "$slot_id" "type" "\"LONG\""
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
        if [ "$ml_approved" = "true" ]; then
            ml_section="🧠 ML Validator: ✅ APROBADO
   Confianza: ${ml_confidence}% | Riesgo: ${ml_risk}
   Razón: $ml_reason"
        elif [ "$ml_approved" = "false" ]; then
            ml_section="🧠 ML Validator: ❌ RECHAZADO
   Confianza: ${ml_confidence}%
   Razón: $ml_reason"
        else
            ml_section="🧠 ML Validator: ⚠️ No disponible (trade sin validación)"
        fi
        
        
        local open_msg="🟢 LONG V3 SLOT $slot_id - $SYMBOL [$CURRENT_MODE]

Slot: $slot_id / $MAX_SLOTS
Entry: \$${fill_price} | Qty: $quantity
Costo: \$${usdt_spent} | Fee: -\$${fee_buy}

TPs:
TP1: \$${tp1} (+${TP1_PERCENT}%) 50%
TP2: \$${tp2} (+${TP2_PERCENT}%) 30%
TP3: \$${tp3} (+${TP3_PERCENT}%) 20%

SL: \$${sl} (-${STOP_LOSS_PERCENT}%)

$ml_section

🚀 Trade activo - Monitoreando TPs..."
        
        send_telegram "$open_msg"
        log "  📱 DEBUG: Notificación de apertura enviada"
        log "✅ Slot $slot_id LONG abierto: Order $order_id"
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
                    
                    # Calcular P&L
                    local exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0')
                    local fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0')
                    local fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
                    local fee_usd=$fee_bnb
                    if [ "$fee_asset" = "BNB" ]; then
                        fee_usd=$(awk -v b="$fee_bnb" -v p="$exit_price" 'BEGIN {printf "%.8f", b * p}')
                    fi
                    
                    # Calcular P&L ANTES de guardar
                    local pnl=$(awk -v e="$entry" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                    
                    # LOG TRADE TO HISTORY
                    log_trade_to_history "$slot_id" "SCALP" "$entry" "$exit_price" "$quantity" "$pnl"
                    
                    # Actualizar P&L diario
                    update_pnl_after_close "$slot_id" "SCALP" "$entry" "$exit_price" "$quantity" "$fee_usd"
                    
                    # P&L para notificación
                    local pnl_display=$(awk -v p="$pnl" 'BEGIN {printf "%.2f", p}')
                    local pnl_icon="🟢"
                    [ $(echo "$pnl < 0" | bc -l) -eq 1 ] && pnl_icon="🔴"
                    
                    # Telegram
                    send_telegram "${pnl_icon} SCALP HIT - $SYMBOL 🎯

Slot: $slot_id / $MAX_SLOTS
Exit: \$${exit_price}
P&L: \$${pnl_display}
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
            local trailing_percent
            if [ "$tp2_done" = "true" ]; then
                trailing_percent="2.0"
            else
                trailing_percent="0.2"
            fi
            
            if [ "$highest_price" != "null" ]; then
                local trailing_stop_level=$(echo "scale=8; $highest_price * (1 - $trailing_percent / 100)" | bc)
                if (( $(echo "$current_price <= $trailing_stop_level" | bc -l) )); then
                    log "🛡️ Slot $slot_id: TRAILING STOP HIT - \$${current_price} <= \$${trailing_stop_level}"
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
                update_slot_field "$slot_id" "tp1Done" "true"
                
                # Calcular P&L ANTES de guardar en histórico
                local pnl=$(awk -v e="$entry" -v x="$current_price" -v q="$sell_qty" -v f="$fee_buy" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                
                # LOG TRADE TO HISTORY
                log_trade_to_history "$slot_id" "TP1" "$entry" "$current_price" "$sell_qty" "$pnl"
                
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
                # Solo para NUEVAS entradas (detectado por timestamp reciente < 24h)
                if [ "$SLOT_RECYCLING_ENABLED" = "true" ]; then
                    local slot_age_hours=$(awk -v ts="$timestamp" -v now="$(date +%s)" 'BEGIN {
                        gsub(/"/, "", ts);
                        cmd = "date -d "" ts "" +%s";
                        cmd | getline entry_time;
                        close(cmd);
                        print int((now - entry_time) / 3600)
                    }')
                    
                    # Si el slot tiene menos de 1 hora, es entrada nueva → aplicar reciclaje
                    if [ "$slot_age_hours" -lt 1 ] || [ -z "$slot_age_hours" ] || [ "$slot_age_hours" -lt 0 ]; then
                        log "  🔄 MODO RECICLAJE: Slot #$slot_id es entrada nueva (<1h)"
                        log "  🔄 TP1 cerrado → Slot pasa a READY para nueva entrada"
                        
                        # Resetear flags para próxima entrada
                        update_slot_field "$slot_id" "tp1Done" "false"
                        update_slot_field "$slot_id" "tp2Done" "false"
                        update_slot_field "$slot_id" "tp3Done" "false"
                        
                        # NO cambiar a READY aquí - el ciclo actual continúa
                        # El slot quedará disponible para nueva entrada en el próximo ciclo
                        log "  ✅ Slot #$slot_id listo para nueva entrada en próximo ciclo"
                        
                        # Enviar Telegram TP1 con nota de reciclaje
                        send_telegram "✅ TP1 HIT - $SYMBOL [35%] 🎯

Slot: $slot_id / $MAX_SLOTS
Exit: \$${current_price}
Qty: $sell_qty_fmt (35%)
P&L: \$${pnl_partial}

🔄 MODO RECICLAJE ACTIVADO
El slot buscará nueva entrada 🚀"
                    else
                        # Slot existente → mantener estrategia piramidal
                        log "  📊 Slot #$slot_id es entrada existente (${slot_age_hours}h) → mantiene estrategia piramidal"
                        
                        # Calcular P&L parcial para notificación
                        local pnl_partial=$(awk -v e="$entry" -v x="$current_price" -v q="$sell_qty" -v f="$fee_buy" 'BEGIN {printf "%.2f", ((x - e) * q) - f}')
                        
                        # Enviar Telegram TP1 (versión piramidal)
                        send_telegram "✅ TP1 HIT - $SYMBOL [35%] 🎯

Slot: $slot_id / $MAX_SLOTS
Exit: \$${current_price}
Qty: $sell_qty_fmt (35%)
P&L Parcial: \$${pnl_partial}
ACUMULADO: 5% 📈

Quedan 65% para TP2/TP3 🎯"
                    fi
                else
                    # Reciclaje desactivado → mantener estrategia piramidal tradicional
                    # Calcular P&L parcial para notificación
                    local pnl_partial=$(awk -v e="$entry" -v x="$current_price" -v q="$sell_qty" -v f="$fee_buy" 'BEGIN {printf "%.2f", ((x - e) * q) - f}')
                    
                    # Enviar Telegram TP1 (versión piramidal)
                    send_telegram "✅ TP1 HIT - $SYMBOL [35%] 🎯

Slot: $slot_id / $MAX_SLOTS
Exit: \$${current_price}
Qty: $sell_qty_fmt (35%)
P&L Parcial: \$${pnl_partial}
ACUMULADO: 5% 📈

Quedan 65% para TP2/TP3 🎯"
                fi
            else
                local error=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
                log "  ❌ TP1 venta falló: $error"
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
                update_slot_field "$slot_id" "tp2Done" "true"
                
                # Calcular P&L ANTES de guardar en histórico
                local pnl=$(awk -v e="$entry" -v x="$current_price" -v q="$sell_qty" -v f="$fee_buy" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                
                # LOG TRADE TO HISTORY
                log_trade_to_history "$slot_id" "TP2" "$entry" "$current_price" "$sell_qty" "$pnl"
                
                # Marcar TP2 como completado
                log "  ✅ TP2 marcado como completado"
                update_slot_field "$slot_id" "tp2Done" "true"
                
                # FASE 1: TRAILING STOP - Activar trailing stop 2% después de TP2
                if [ "$TRAILING_STOP_ENABLED" = "true" ]; then
                    log "  🛡️ TP2 done - Activando trailing stop 2%"
                    update_slot_field "$slot_id" "trailingStop" "true"
                    update_slot_field "$slot_id" "trailingPercent" "2.0"
                    log "  ✅ Trailing stop 2% activado"
                fi
                
                # Calcular P&L parcial para notificación
                local pnl_partial=$(awk -v e="$entry" -v x="$current_price" -v q="$sell_qty" -v f="$fee_buy" 'BEGIN {printf "%.2f", ((x - e) * q) - f}')
                
                # BUG-036 FIX: Enviar Telegram TP2
                log "  📱 DEBUG: Preparando notificación TP2..."
                
                local tp2_msg="✅ TP2 HIT - $SYMBOL [30%] 🎯

Slot: $slot_id / $MAX_SLOTS
Exit: \$${current_price}
Qty: $sell_qty_fmt (30%)
P&L Parcial: \$${pnl_partial}
ACUMULADO: 5% 📈

Queda 35% para TP3 🎯"
                
                send_telegram "$tp2_msg"
                log "  📱 DEBUG: send_telegram TP2 completado"
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
                        log "  ⚠️ Resto < \$5 (\$${remaining_value}) - Slot marcado como CLOSED_TP2"
                        log "  💡 Resto se queda como 'dust' en Binance (convertible a BNB)"
                        
                        send_telegram "⚠️ TP2 FALLÓ - $SYMBOL [BUG-047 FIX]

Slot: $slot_id
Error: $error
Razón: Valor < \$5 mínimo de Binance
Resto: \$${remaining_value} (< \$5)

✅ Slot cerrado automáticamente
💡 Resto se queda como 'dust' (convertible a BNB)

🛡️ Auto-Heal v2.0"
                    else
                        # Resto >= $5 - mantener slot activo
                        send_telegram "⚠️ TP2 FALLÓ - $SYMBOL

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
                update_slot_field "$slot_id" "tp3Done" "true"
                update_slot_field "$slot_id" "status" "CLOSED_TP3"
                log "  ✅ Slot cerrado - TP3 completado (5% acumulado en Binance)"
                
                # Calcular P&L ANTES de guardar en histórico
                local pnl=$(awk -v e="$entry" -v x="$current_price" -v q="$quantity" -v f="$fee_buy" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                
                # LOG TRADE TO HISTORY
                log_trade_to_history "$slot_id" "TP3" "$entry" "$current_price" "$quantity" "$pnl"
                
                # Marcar TP3 como completado
                log "  ✅ TP3 marcado como completado"
                update_slot_field "$slot_id" "tp3Done" "true"
                
                # Actualizar P&L
                local exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0')
                local fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0')
                local fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
                local fee_usd=$fee_bnb
                if [ "$fee_asset" = "BNB" ]; then
                    fee_usd=$(awk -v b="$fee_bnb" -v p="$current_price" 'BEGIN {printf "%.8f", b * p}')
                fi
                update_pnl_after_close "$slot_id" "TP3" "$entry" "$exit_price" "$quantity" "$fee_usd"
                log "  📱 DEBUG: Después de update_pnl, antes de send_telegram" "$entry" "$exit_price" "$quantity" "$fee_usd"
                
                # Calcular P&L total para notificación
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
                
                local tp3_msg="${pnl_icon} TP3 HIT - $SYMBOL [$tp3_percentage - $tp3_note] 🎯

Slot: $slot_id / $MAX_SLOTS
Exit: \$${exit_price}
Qty: $sell_qty_fmt ($tp3_percentage)
ACUMULADO: 5% 📈

$acumulado_note
P&L Total: \$${pnl_total}

✅ Slot cerrado y disponible 🎯"
                
                send_telegram "$tp3_msg"
                log "  📱 DEBUG: send_telegram completado"
            else
                local error=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
                log "  ❌ TP3 venta falló: $error"
                
                # BUG-036 FIX: Notificar incluso si falla por NOTIONAL
                if echo "$error" | grep -q "NOTIONAL\|minimum"; then
                    log "  📱 Enviando notificación de falla NOTIONAL..."
                    send_telegram "⚠️ TP3 FALLÓ - $SYMBOL

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
                update_slot_status "$slot_id" "CLOSED_SL"
                
                # Actualizar P&L
                local exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0')
                local fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0')
                local fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
                local fee_usd=$fee_bnb
                if [ "$fee_asset" = "BNB" ]; then
                    fee_usd=$(awk -v b="$fee_bnb" -v p="$current_price" 'BEGIN {printf "%.8f", b * p}')
                fi
                
                # Calcular P&L ANTES de guardar en histórico
                local pnl=$(awk -v e="$entry" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                
                # LOG TRADE TO HISTORY
                log_trade_to_history "$slot_id" "SL" "$entry" "$exit_price" "$quantity" "$pnl"
                
                # Marcar SL como ejecutado
                log "  🛑 SL ejecutado"
                update_slot_field "$slot_id" "status" "CLOSED_SL"
                
                # Actualizar P&L diario
                update_pnl_after_close "$slot_id" "SL" "$entry" "$exit_price" "$quantity" "$fee_usd"
                
                # Calcular P&L para notificación
                local pnl_display=$(awk -v p="$pnl" 'BEGIN {printf "%.2f", p}')
                local pnl_icon="🔴"
                [ $(echo "$pnl > 0" | bc -l) -eq 1 ] && pnl_icon="🟢"
                
                # Enviar Telegram
                send_telegram "${pnl_icon} SL HIT - $SYMBOL

Slot: $slot_id / $MAX_SLOTS
Exit: \$${exit_price}
P&L: \$${pnl_display}

El slot está disponible para próximo trade. 🛡️"
                
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
        log "  ✅ Trailing stop ejecutado exitosamente - Slot cerrado"
        update_slot_status "$slot_id" "CLOSED_TRAILING"
        
        # Actualizar P&L
        local exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0')
        local fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0')
        local fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"')
        local fee_usd=$fee_bnb
        if [ "$fee_asset" = "BNB" ]; then
            fee_usd=$(awk -v b="$fee_bnb" -v p="$exit_price" 'BEGIN {printf "%.8f", b * p}')
        fi
        
        # Calcular P&L ANTES de guardar en histórico
        local pnl=$(awk -v e="$entry" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
        
        # LOG TRADE TO HISTORY
        log_trade_to_history "$slot_id" "TRAILING" "$entry" "$exit_price" "$quantity" "$pnl"
        
        # Actualizar P&L diario
        update_pnl_after_close "$slot_id" "TRAILING" "$entry" "$exit_price" "$quantity" "$fee_usd"
        
        # Calcular P&L para notificación
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
        send_telegram "${pnl_icon} TRAILING STOP - $SYMBOL

Slot: $slot_id / $MAX_SLOTS
Exit: \$${exit_price}
P&L: \$${pnl_display}
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
        if [[ "$slot_status" == "CLOSED_SL" || "$slot_status" == "CLOSED_TP" || "$slot_status" == "CLOSED_TP3" || "$slot_status" == "CLOSED_SCALP" || "$slot_status" == "CLOSED_TRAILING" ]]; then
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
    local active_count=$(get_active_slots_count)
    local closed_count=$(jq '[.slots[] | select(.status | startswith("CLOSED"))] | length' "$STATE_FILE")
    
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
    echo "  Net P&L: \$${net_pnl}"
    echo ""
    echo "📜 ÚLTIMOS 10 TRADES"
    echo "─────────────────────────────────────────────────────────"
    printf "%-4s %-6s %-6s %-8s %-10s %-10s\n" "ID" "Coin" "Tipo" "P&L" "Cierre" "Fecha"
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
    log "╔═══════════════════════════════════════════════════════╗"
    log "║  🤖 CRYPTO TRADE BOT V3 - $SYMBOL [MULTI-SLOT]           ║"
    log "╚═══════════════════════════════════════════════════════╝"
    
    # ============================================
    # 🛡️ CHECK SYSTEM STATUS (BINANCE MAINTENANCE)
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
    
    # Detectar modo y obtener STOP LOSS por coin
    local current_hour=$(date -u +%H | sed 's/^0//')
    
    # Obtener STOP LOSS específico para esta coin
    if [ -n "${STOP_LOSS_BY_COIN[$SYMBOL]}" ]; then
        STOP_LOSS_PERCENT="${STOP_LOSS_BY_COIN[$SYMBOL]}"
    else
        STOP_LOSS_PERCENT="4.0"  # Default si no está en la lista
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
                    send_telegram "🛑 TRADING PAUSADO - $SYMBOL

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
                for coin in BTC ETH BNB SOL LINK XRP AVAX; do
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
    
    # Check if we can open new trades
    if [ $active_count -ge $MAX_SLOTS ]; then
        log "⏸️ Máximo de slots alcanzado ($active_count / $MAX_SLOTS)"
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
