#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🚨 EMERGENCY CLOSE ALL - CIERRA TODOS LOS TRADES     ║
# ║  Uso: Cuando daily_loss >= 3% del portfolio           ║
# ╚═══════════════════════════════════════════════════════╝

set -e

WORKSPACE="/home/overgon/.openclaw/workspace"
SECRETS="/home/overgon/.openclaw/secrets"
LOGS="/home/overgon/.openclaw/logs"
BINANCE="https://api.binance.com"

source "$SECRETS/binance.env"

# ============================================
# 🔧 CONFIGURACIÓN
# ============================================

MAX_DAILY_LOSS_PERCENT=3
COINS=("BTC" "ETH" "SOL" "LINK" "XRP" "BNB")

# ============================================
# 🔧 FUNCIONES DE LOGGING
# ============================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [EMERGENCY] $1" | tee -a "$LOGS/emergency-close.log"
}

send_telegram() {
    local message="$1"
    local config_file="$HOME/.openclaw/openclaw.json"
    if [ -f "$config_file" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_file" 2>/dev/null)
        [ -n "$bot_token" ] && [ "$bot_token" != "null" ] && \
            curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
                -H "Content-Type: application/json" \
                -d "{\"chat_id\":\"7543955537\",\"text\":\"$message\",\"parse_mode=HTML\"}" > /dev/null
    fi
}

# ============================================
# 🛡️ FUNCIONES DE BINANCE
# ============================================

get_signature() {
    echo -n "$1" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}'
}

get_balance() {
    local symbol="$1"
    local timestamp=$(date -u +%s%3N)
    local query_string="timestamp=${timestamp}&recvWindow=5000"
    local signature=$(get_signature "$query_string")
    local result=$(curl -s -X GET "${BINANCE}/api/v3/account?${query_string}&signature=${signature}" -H "X-MBX-APIKEY: ${BINANCE_API_KEY}")

    # Try normal asset first, then try with "LD" prefix (Locked/Deposit)
    local balance=$(echo "$result" | jq -r ".balances[] | select(.asset == \"$symbol\") | .free")

    if [ -z "$balance" ] || [ "$balance" = "null" ]; then
        # Try with LD prefix (e.g., BTC -> LDBTC for staked/locked assets)
        balance=$(echo "$result" | jq -r ".balances[] | select(.asset == \"LD${symbol}\") | .free")
    fi

    echo "$balance"
}

get_portfolio_value() {
    local total=0
    
    log "📊 Calculando portfolio (Método Híbrido: API + State Files)..."
    
    # MÉTODO 1: Obtener USDT disponible de la API
    local usdt=$(get_balance "USDT")
    [ -z "$usdt" ] || [ "$usdt" = "null" ] && usdt="0"
    total=$usdt
    log "  USDT disponible: \$$usdt"
    
    # MÉTODO 2: Sumar valor de trades activos desde state files (MÁS CONFIABLE)
    for coin in "${COINS[@]}"; do
        local state_file="$WORKSPACE/crypto-bots/${coin}-trade-state.json"
        
        if [ -f "$state_file" ]; then
            # Obtener slots activos
            local active_slots=$(jq '[.slots[] | select(.status == "ACTIVE")]' "$state_file" 2>/dev/null)
            
            if [ -n "$active_slots" ] && [ "$active_slots" != "null" ] && [ "$active_slots" != "[]" ]; then
                # Calcular valor actual de cada slot activo
                local slot_values=$(echo "$active_slots" | jq --arg coin "$coin" '
                    .[] | 
                    select(.quantity != null and .quantity != 0) |
                    {
                        coin: $coin,
                        quantity: .quantity,
                        usdtSpent: .usdtSpent
                    }
                ')
                
                # Sumar usdtSpent de todos los slots activos
                local coin_value=$(echo "$active_slots" | jq '[.[] | .usdtSpent // 0] | add // 0')
                
                if [ -n "$coin_value" ] && [ "$coin_value" != "null" ] && [ "$coin_value" != "0" ]; then
                    total=$(awk -v t="$total" -v c="$coin_value" 'BEGIN {printf "%.2f", t + c}')
                    log "  $coin: Slots activos = \$$coin_value (usdtSpent)"
                fi
            fi
        fi
    done
    
    # Validar que el portfolio no sea $0 (si hay trades activos)
    local total_active_slots=0
    for coin in "${COINS[@]}"; do
        local state_file="$WORKSPACE/crypto-bots/${coin}-trade-state.json"
        if [ -f "$state_file" ]; then
            local count=$(jq '[.slots[] | select(.status == "ACTIVE")] | length' "$state_file" 2>/dev/null || echo "0")
            total_active_slots=$((total_active_slots + count))
        fi
    done
    
    if [ "$total_active_slots" -gt 0 ] && [ "$total" = "0" ]; then
        log "⚠️  WARNING: Portfolio = \$0 pero hay $total_active_slots trades activos"
        log "  Usando cálculo alternativo desde state files..."
        
        # Cálculo alternativo: sumar todo el usdtSpent de slots activos
        local alt_total=0
        for coin in "${COINS[@]}"; do
            local state_file="$WORKSPACE/crypto-bots/${coin}-trade-state.json"
            if [ -f "$state_file" ]; then
                local coin_total=$(jq '[.slots[] | select(.status == "ACTIVE") | .usdtSpent // 0] | add // 0' "$state_file" 2>/dev/null || echo "0")
                alt_total=$(awk -v a="$alt_total" -v c="$coin_total" 'BEGIN {printf "%.2f", a + c}')
            fi
        done
        
        if [ "$alt_total" != "0" ] && [ "$alt_total" != "null" ]; then
            total=$alt_total
            log "  ✅ Portfolio corregido: \$$total"
        fi
    fi
    
    log "📊 Portfolio total: \$$total"
    echo "$total"
}

place_sell_order_market() {
    local symbol="$1" quantity="$2"
    local timestamp=$(date -u +%s%3N)
    local query_string="symbol=${symbol}USDT&side=SELL&type=MARKET&quantity=${quantity}&timestamp=${timestamp}&recvWindow=5000"
    local signature=$(get_signature "$query_string")
    curl -s -X POST "${BINANCE}/api/v3/order?${query_string}&signature=${signature}" -H "X-MBX-APIKEY: ${BINANCE_API_KEY}"
}

# ============================================
# 📊 CÁLCULO DE PÉRDIDA DIARIA
# ============================================

calculate_daily_loss() {
    local total_loss=0
    log "📊 Calculando pérdida diaria..."
    
    for coin in "${COINS[@]}"; do
        local pnl_file="$WORKSPACE/crypto-bots/${coin}-daily-pnl.json"
        if [ -f "$pnl_file" ]; then
            local loss=$(jq -r '.loss_amount // 0' "$pnl_file" 2>/dev/null || echo "0")
            [ -z "$loss" ] || [ "$loss" = "null" ] && loss="0"
            total_loss=$(awk -v t="$total_loss" -v l="$loss" 'BEGIN {printf "%.2f", t+l}' 2>/dev/null || echo "$total_loss")
            [ "$loss" != "0" ] && log "  $coin: \$$loss (hoy)"
        else
            log "  ⚠️ $coin: No hay archivo daily-pnl.json"
        fi
    done
    
    log "📊 Pérdida diaria total: \$$total_loss"
    echo "$total_loss"
}

# ============================================
# 🚨 EMERGENCY CLOSE FUNCTION
# ============================================

emergency_close_all() {
    log "╔═══════════════════════════════════════════════════════╗"
    log "║  🚨 EMERGENCY CLOSE ALL - ACTIVADO                    ║"
    log "╚═══════════════════════════════════════════════════════╝"

    # ============================================
    # 🛡️ VALIDACIONES CRÍTICAS (BUG-052)
    # ============================================
    
    log "🛡️ Ejecutando validaciones críticas..."
    
    # VALIDACIÓN 1: Verificar que hay trades activos
    local total_active_slots=0
    for coin in "${COINS[@]}"; do
        local state_file="$WORKSPACE/crypto-bots/${coin}-trade-state.json"
        if [ -f "$state_file" ]; then
            local count=$(jq '[.slots[] | select(.status == "ACTIVE")] | length' "$state_file" 2>/dev/null || echo "0")
            total_active_slots=$((total_active_slots + count))
        fi
    done
    
    if [ "$total_active_slots" -eq 0 ]; then
        log "⚠️ VALIDACIÓN FALLIDA: No hay trades activos"
        log "  Abortando emergency close (no hay nada que cerrar)"
        return 0
    fi
    
    log "  ✅ Trades activos verificados: $total_active_slots"
    
    # VALIDACIÓN 2: Calcular portfolio y validar que sea razonable (> $100)
    local portfolio_value=$(get_portfolio_value)
    
    if [ -z "$portfolio_value" ] || [ "$portfolio_value" = "" ] || [ "$portfolio_value" = "0" ] || [ "$portfolio_value" = "0.00" ]; then
        log "❌ VALIDACIÓN FALLIDA: Portfolio = \$0 (cálculo incorrecto)"
        log "  Hay $total_active_slots trades activos pero portfolio = \$0"
        log "  Abortando emergency close para evitar falso positivo"
        log ""
        log "  🛡️ BUG-052 PREVENIDO: Emergency close cancelado por datos incompletos"
        
        # Enviar alerta de que el sistema funcionó
        send_telegram "🛡️ *BUG-052 PREVENIDO*

🚨 Emergency Close Cancelado

⚠️ *Motivo:* Portfolio calculado = \$0
✅ *Trades activos:* $total_active_slots
✅ *Stop Losses:* INTACTOS

El sistema detectó datos incompletos y canceló el emergency close para evitar un falso positivo.

🐕 Perrobotillo Trading Bot"
        
        return 0
    fi
    
    # VALIDACIÓN 3: Portfolio mínimo razonable
    if (( $(awk -v p="$portfolio_value" 'BEGIN {print (p < 100) ? 1 : 0}') )); then
        log "⚠️ VALIDACIÓN FALLIDA: Portfolio = \$$portfolio_value (< \$100 mínimo)"
        log "  Abortando emergency close (portfolio demasiado bajo)"
        return 0
    fi
    
    log "  ✅ Portfolio verificado: \$$portfolio_value"
    
    # VALIDACIÓN 4: Verificar snapshot de ayer para calcular pérdida
    local snapshot_file="$WORKSPACE/portfolio-snapshot.json"
    if [ ! -f "$snapshot_file" ]; then
        log "⚠️ VALIDACIÓN FALLIDA: No hay snapshot de ayer"
        log "  No se puede calcular pérdida diaria sin referencia"
        log "  Abortando emergency close"
        
        send_telegram "⚠️ *EMERGENCY CLOSE CANCELADO*

📊 No hay snapshot de ayer

No se puede calcular la pérdida diaria sin un punto de referencia.

✅ Tus trades están SEGUROS
🛡️ Stop Losses: INTACTOS

🐕 Perrobotillo Trading Bot"
        
        return 0
    fi
    
    log "  ✅ Snapshot de ayer verificado"
    
    log ""
    log "✅ Todas las validaciones críticas aprobadas"
    log ""

    # ============================================
    # 📊 CÁLCULO DE PÉRDIDA DIARIA
    # ============================================
    
    local daily_loss=$(calculate_daily_loss)
    
    # Validar que daily_loss no esté vacío
    if [ -z "$daily_loss" ] || [ "$daily_loss" = "" ]; then
        log "⚠️ ERROR: No se pudo calcular la pérdida diaria, usando fallback"
        daily_loss="0.00"
    fi
    
    local max_loss=$(awk -v p="$portfolio_value" -v pct="$MAX_DAILY_LOSS_PERCENT" 'BEGIN {printf "%.2f", p * pct / 100}' 2>/dev/null || echo "0.00")
    
    log "Portfolio: \$${portfolio_value}"
    log "Pérdida diaria: \$${daily_loss}"
    log "Límite (3%): \$${max_loss}"
    log ""

    # Verificar si realmente necesitamos emergency close
    if (( $(awk -v d="$daily_loss" -v m="$max_loss" 'BEGIN {print (d >= m) ? 1 : 0}') )); then
        log "✅ Límite diario superado (\$${daily_loss} >= \$${max_loss})"
        log "🚨 Iniciando cierre de emergencia..."
    else
        log "⚠️ Límite NO superado, pero se solicitó emergency close"
        log "   Continuando por solicitud manual..."
    fi

    local closed_count=0
    local total_recovered=0

    for coin in "${COINS[@]}"; do
        local state_file="$WORKSPACE/crypto-bots/${coin}-trade-state.json"

        if [ -f "$state_file" ]; then
            # Check si es V3 (tiene slots) o V1 (estado simple)
            local is_v3=$(jq 'has("slots")' "$state_file" 2>/dev/null || echo "false")

            if [ "$is_v3" = "true" ]; then
                # V3: Check cada slot
                local active_slots=$(jq '[.slots[] | select(.status == "ACTIVE")] | length' "$state_file")

                if [ "$active_slots" -gt 0 ]; then
                    log "🔍 $coin (V3): $active_slots slot(s) activo(s)"

                    for slot_id in $(jq -r '.slots[] | select(.status == "ACTIVE") | .slotId' "$state_file"); do
                        local quantity=$(jq -r ".slots[$((slot_id-1))].quantity // 0" "$state_file")
                        local entry_price=$(jq -r ".slots[$((slot_id-1))].entryPrice // 0" "$state_file")

                        if [ "$quantity" != "0" ] && [ -n "$quantity" ] && [ "$quantity" != "null" ]; then
                            log "  Slot $slot_id: Vendiendo $quantity $coin @ market"

                            # Formatear cantidad según stepSize
                            local stepSize=$(curl -s "${BINANCE}/api/v3/exchangeInfo?symbol=${coin}USDT" 2>/dev/null | jq -r '.symbols[0].filters[] | select(.filterType == "LOT_SIZE") | .stepSize')
                            local decimals=8
                            [[ "$stepSize" == "0.00001000" ]] && decimals=5
                            [[ "$stepSize" == "0.00010000" ]] && decimals=4
                            [[ "$stepSize" == "0.01000000" ]] && decimals=2

                            local qty_fmt=$(printf "%.${decimals}f" "$quantity" 2>/dev/null)

                            local sell_result=$(place_sell_order_market "$coin" "$qty_fmt")
                            local sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"')

                            if [ "$sell_status" = "FILLED" ]; then
                                local executed_qty=$(echo "$sell_result" | jq -r '.executedQty')
                                local avg_price=$(echo "$sell_result" | jq -r '.avgPrice // .fills[0].price')
                                local value=$(awk -v q="$executed_qty" -v p="$avg_price" 'BEGIN {printf "%.2f", q * p}')

                                log "  ✅ Slot $slot_id cerrado: $executed_qty @ \$${avg_price} = \$${value}"

                                # Actualizar slot state
                                jq --argjson sid "$slot_id" --arg ts "$(date -Iseconds)" \
                                   ".slots = [.slots[] | if .slotId == $sid then .status = \"CLOSED_EMERGENCY\" | .closeReason = \"DAILY_LIMIT_HIT\" | .exitTime = $ts else . end]" \
                                   "$state_file" > /tmp/state_$$.json && mv /tmp/state_$$.json "$state_file"

                                closed_count=$((closed_count + 1))
                                total_recovered=$(awk -v t="$total_recovered" -v v="$value" 'BEGIN {printf "%.2f", t+v}')
                            else
                                local error=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
                                log "  ❌ Slot $slot_id falló: $error"
                            fi
                        fi
                    done
                fi
            else
                # V1: Estado simple
                local status=$(jq -r '.status // "READY"' "$state_file")

                if [ "$status" = "ACTIVE" ]; then
                    local quantity=$(jq -r '.quantity // 0' "$state_file")
                    local entry_price=$(jq -r '.entryPrice // 0' "$state_file")

                    if [ "$quantity" != "0" ] && [ -n "$quantity" ] && [ "$quantity" != "null" ]; then
                        log "  $coin (V1): Vendiendo $quantity @ market"

                        # Formatear cantidad
                        local stepSize=$(curl -s "${BINANCE}/api/v3/exchangeInfo?symbol=${coin}USDT" 2>/dev/null | jq -r '.symbols[0].filters[] | select(.filterType == "LOT_SIZE") | .stepSize')
                        local decimals=8
                        [[ "$stepSize" == "0.00001000" ]] && decimals=5
                        [[ "$stepSize" == "0.00010000" ]] && decimals=4
                        [[ "$stepSize" == "0.01000000" ]] && decimals=2

                        local qty_fmt=$(printf "%.${decimals}f" "$quantity" 2>/dev/null)

                        local sell_result=$(place_sell_order_market "$coin" "$qty_fmt")
                        local sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"')

                        if [ "$sell_status" = "FILLED" ]; then
                            local executed_qty=$(echo "$sell_result" | jq -r '.executedQty')
                            local avg_price=$(echo "$sell_result" | jq -r '.avgPrice // .fills[0].price')
                            local value=$(awk -v q="$executed_qty" -v p="$avg_price" 'BEGIN {printf "%.2f", q * p}')

                            log "  ✅ $coin cerrado: $executed_qty @ \$${avg_price} = \$${value}"

                            # Actualizar state file
                            jq --arg ts "$(date -Iseconds)" \
                               '.status = "CLOSED_EMERGENCY" | .closeReason = "DAILY_LIMIT_HIT" | .exitTime = $ts' \
                               "$state_file" > /tmp/state_$$.json && mv /tmp/state_$$.json "$state_file"

                            closed_count=$((closed_count + 1))
                            total_recovered=$(awk -v t="$total_recovered" -v v="$value" 'BEGIN {printf "%.2f", t+v}')
                        else
                            local error=$(echo "$sell_result" | jq -r '.msg // "Unknown error"')
                            log "  ❌ $coin falló: $error"
                        fi
                    fi
                fi
            fi
        fi
    done

    log ""
    log "╔═══════════════════════════════════════════════════════╗"
    log "║  🛡️ EMERGENCY CLOSE COMPLETE                          ║"
    log "╠═══════════════════════════════════════════════════════╣"
    log "║  Trades cerrados: $closed_count                        ║"
    log "║  Capital recuperado: \$${total_recovered} USDT             ║"
    log "╚═══════════════════════════════════════════════════════╝"

    # Enviar Telegram
    send_telegram "🚨 *EMERGENCY CLOSE - COMPLETADO*

🛡️ Límite diario 3% superado
📊 Portfolio: \$${portfolio_value}
💔 Pérdida: \$${daily_loss}
✅ Límite: \$${max_loss}

╔═══════════════════════════════════════════╗
║  TRADES CERRADOS: $closed_count                    ║
║  RECUPERADO: \$${total_recovered} USDT              ║
╚═══════════════════════════════════════════╝

Trading detenido hasta mañana. 🛡️"

    # Marcar alerta enviada
    echo "$(date +%Y-%m-%d)" > "$WORKSPACE/crypto-bots/.daily_limit_alert_sent"
    echo "$(date +%Y-%m-%d)" > "$WORKSPACE/crypto-bots/.emergency_close_sent"

    log "✅ Telegram alerta enviada"
    log "✅ Flag files actualizados"
}

# ============================================
# 🎯 MAIN
# ============================================

log "🚨 Emergency Close All Script Iniciado"
emergency_close_all
log "✅ Script completado"
