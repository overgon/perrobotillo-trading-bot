#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🚨 EMERGENCY CLOSE - SLOTS CON SL CRUZADO            ║
# ║  Cierra forzosamente slots donde current_price < SL   ║
# ╚═══════════════════════════════════════════════════════╝

# FIX (2026-10-14): Removed set -e - it kills the script on jq parse errors
# when Binance returns non-JSON (rate limit, HTML edge). SL trades get stuck.
set +e

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="$HOME/.openclaw/secrets"
LOGS="$HOME/.openclaw/logs"
BINANCE="https://api.binance.com"

source "$SECRETS/binance.env"

# ============================================
# 🔧 CONFIGURACIÓN
# ============================================

COINS=("BTC" "ETH" "SOL" "ZEC" "XRP" "BNB" "AVAX")
HISTORY_FILE="$WORKSPACE/crypto-bots/trade-history.json"
PYTHON="/usr/bin/python3"

# ============================================
# 🔧 FUNCIONES DE LOGGING
# ============================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [EMERGENCY-SL] $1" | tee -a "$LOGS/emergency-close-sl-crossed.log" >&2
}

# 🔧 FIX (2026-10-25): Check if a trade already exists in history to prevent duplicates.
# Now includes minute-level timestamp check — a slot can have multiple CLOSED_SL_EMERGENCY
# entries from different trade cycles. Only skip if symbol+slotId+closeType+same-minute match
# (prevents false positive: Slot 1 closed on Oct 14 shouldn't block Oct 25 close).
trade_already_logged() {
    local coin="$1" slot="$2" close_type="$3"
    if [ -f "$HISTORY_FILE" ]; then
        local now_minute
        now_minute=$(date '+%Y-%m-%dT%H:%M')
        local count
        count=$(jq --arg sy "$coin" --argjson sid "$slot" --arg ct "$close_type" --arg minute "$now_minute" \
            '[.trades[] | select(.symbol == $sy and .slotId == $sid and .closeType == $ct and (.timestamp // "" | startswith($minute)))] | length' \
            "$HISTORY_FILE" 2>/dev/null || echo "0")
        [ "${count:-0}" -gt 0 ] && return 0 || return 1
    fi
    return 1
}

# 🔧 FIX (2026-10-25): Log emergency close to trade history for dashboard visibility
# This ensures CLOSED_SL_EMERGENCY slots appear in RECENT TRADES HISTORY.
# Uses trade_already_logged() to prevent duplicates (dedup at minute level).
# FIX: Capture Python exit code (no more 2>/dev/null || true that hides failures)
# FIX: Always recalculate PnL — caller may pass "0" as placeholder for external-sell case
log_emergency_trade() {
    local coin="$1" slot_id="$2" entry="$3" exit_price="$4" qty="$5" pnl="$6" reason="$7"
    # $8 = sl_price (fallback when exit_price is empty, i.e. position sold externally)
    # FIX (2026-10-25): qty param may be empty for "no balance"/"below step size" paths.
    # Fall back to outer-scope $quantity (derived from usdtSpent/entryPrice in main loop).
    if [ -z "$qty" ]; then
        qty="$quantity"
    fi
    if [ -z "$exit_price" ] || [ "$exit_price" = "null" ] || [ "$exit_price" = "0" ]; then
        # No actual sell — use SL as approximate exit for P&L estimation
        exit_price="$8"
    fi
    # FIX (2026-10-25): Always recalculate PnL when exit_price was derived from SL
    # or when PnL is 0/null — the "no balance" path passes pnl="0" as placeholder,
    # but the real PnL must be calculated from (SL - entry) * qty * 0.999 (0.1% fee)
    if [ -z "$pnl" ] || [ "$pnl" = "null" ] || [ "$pnl" = "0" ]; then
        local sl_price="$8"
        pnl=$(awk -v e="$entry" -v x="$sl_price" -v q="$qty" 'BEGIN {printf "%.8f", ((x - e) * q) * 0.999}')
    fi
    if ! trade_already_logged "$coin" "$slot_id" "CLOSED_SL_EMERGENCY"; then
        # FIX (2026-10-25): Don't suppress stderr — capture it for diagnostics
        local py_output
        py_output=$(SYMBOL="$coin" "$PYTHON" "$WORKSPACE/scripts/log_trade_to_history.py" \
            "$slot_id" "CLOSED_SL_EMERGENCY" "$entry" "$exit_price" "$qty" "$pnl" \
            "" "emergency-close" "$reason" 2>&1) || true
        # FIX: Only print "logged to history" if Python actually wrote the trade
        if echo "$py_output" | grep -q "Trade logged to history"; then
            log "     📜 Trade logged to history: ${coin} slot ${slot_id} ${reason}"
        else
            log "     ⚠️  FAILED to log trade: ${coin} slot ${slot_id} — Python output: ${py_output}"
        fi
    else
        log "     ⏭️  Trade already in history: ${coin} slot ${slot_id} - skip"
    fi
}

# ✅ Consolidado: usar notify.sh centralizado en lugar de send_telegram duplicada
source "$WORKSPACE/crypto-bots/notify.sh" 2>/dev/null || true

# ============================================
# 🛡️ FUNCIONES DE BINANCE
# ============================================

get_signature() {
    echo -n "$1" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}'
}

get_current_price() {
    local symbol="$1"
    local price=$(curl -s "${BINANCE}/api/v3/ticker/price?symbol=${symbol}USDT" 2>/dev/null | jq -r '.price')
    echo "$price"
}

place_market_sell() {
    local symbol="$1"
    local quantity="$2"
    
    # Reintentar hasta 3 veces por temas de timestamp
    local attempt=1
    local max_attempts=3
    
    while [ $attempt -le $max_attempts ]; do
        # Obtener timestamp fresco justo antes de enviar
        local timestamp=$(date -u +%s%3N)
        local query_string="symbol=${symbol}&side=SELL&type=MARKET&quantity=${quantity}&timestamp=${timestamp}&recvWindow=60000"
        local signature=$(get_signature "$query_string")
        
        log "     Intento ${attempt}/${max_attempts}..."
        
        local result=$(curl -s -X POST "${BINANCE}/api/v3/order" \
            -H "X-MBX-APIKEY: ${BINANCE_API_KEY}" \
            -d "${query_string}&signature=${signature}")
        
        local status=$(echo "$result" | jq -r '.status // "ERROR"' 2>/dev/null || echo "ERROR")
        local code=$(echo "$result" | jq -r '.code // 0' 2>/dev/null || echo "0")
        
        # Si éxito, retornar inmediatamente
        if [ "$status" = "FILLED" ] || [ "$status" = "PARTIALLY_FILLED" ]; then
            echo "$result"
            return 0
        fi
        
        # Si es error de timestamp (-1021), reintentar con nuevo timestamp
        if [ "$code" = "-1021" ] && [ $attempt -lt $max_attempts ]; then
            log "     Timestamp error, reintentando..."
            sleep 1
            attempt=$((attempt + 1))
            continue
        fi
        
        # Si es otro error o último intento, retornar resultado
        echo "$result"
        return 0
    done
    
    echo '{"status":"ERROR","msg":"Max retries exceeded"}'
}

# ============================================
# 🎯 MAIN - VERIFICAR Y CERRAR SLOTS
# ============================================

log "╔═══════════════════════════════════════════════════════╗"
log "║  🚨 EMERGENCY CLOSE - SL CRUZADO                      ║"
log "╚═══════════════════════════════════════════════════════╝"

closed_count=0
total_pnl=0
report=""

for COIN in "${COINS[@]}"; do
    STATE_FILE="$WORKSPACE/crypto-bots/${COIN}-trade-state.json"
    
    if [ ! -f "$STATE_FILE" ]; then
        log "⚠️  ${COIN}: No state file found, skipping..."
        continue
    fi
    
    log "🔍 Revisando ${COIN}..."
    
    # Leer slots activos
    active_slots=$(jq -c '.slots[] | select(.status == "ACTIVE")' "$STATE_FILE" 2>/dev/null)
    
    if [ -z "$active_slots" ] || [ "$active_slots" = "" ]; then
        log "  ✅ ${COIN}: No active slots"
        continue
    fi
    
    # Obtener precio actual
    current_price=$(get_current_price "$COIN")
    log "  💰 ${COIN} current price: \$${current_price}"
    # FIX: Skip if price is invalid (null/empty/non-numeric) - prevents false SL crossing
    if [ "$current_price" = "null" ] || [ -z "$current_price" ] || ! echo "$current_price" | grep -qE '^[0-9]+\.?[0-9]*$'; then
        log "  ⚠️  ${COIN}: Precio inválido ($current_price), skipping..."
        continue
    fi
    
    # Revisar cada slot activo
    while IFS= read -r slot; do
        [ -z "$slot" ] && continue
        
        slot_id=$(echo "$slot" | jq -r '.slotId' 2>/dev/null || echo "0")
        entry_price=$(echo "$slot" | jq -r '.entryPrice' 2>/dev/null || echo "0")
        sl=$(echo "$slot" | jq -r '.stopLoss' 2>/dev/null || echo "null")
        quantity=$(echo "$slot" | jq -r '.quantity' 2>/dev/null || echo "0")
        tp1_done=$(echo "$slot" | jq -r '.tp1Done' 2>/dev/null || echo "false")
        # FIX (2026-10-14): Derive correct quantity from usdtSpent/entryPrice
        # The quantity field was corrupt (19.75x too small) causing LOT_SIZE failures.
        # If TP1 was executed, reduce by tp1Pct to get remaining position.
        usdt_spent=$(echo "$slot" | jq -r '.usdtSpent // 0' 2>/dev/null || echo "0")
        tp1_pct=$(echo "$slot" | jq -r '.tp1Pct // 0' 2>/dev/null || echo "0")
        if [ -n "$usdt_spent" ] && [ "$usdt_spent" != "0" ] && [ -n "$entry_price" ] && [ "$entry_price" != "null" ]; then
            if [ "$tp1_done" = "true" ] && [ -n "$tp1_pct" ] && [ "$tp1_pct" != "null" ] && [ "$tp1_pct" != "0" ]; then
                quantity=$(awk -v u="$usdt_spent" -v e="$entry_price" -v p="$tp1_pct" 'BEGIN {printf "%.8f", (u/e) * (1 - p)}')
            else
                quantity=$(awk -v u="$usdt_spent" -v e="$entry_price" 'BEGIN {printf "%.8f", u/e}')
            fi
            log "     ℹ️  Qty derivado: ${quantity} (de usdtSpent=${usdt_spent} / entry=${entry_price})"
        fi
        # FIX: Round down to LOT_SIZE step size to avoid filter failure
        case "$COIN" in
            BTC|ETH) _step="0.000001" ;;
            BNB|SOL|ZEC|LINK) _step="0.001" ;;
            XRP|AVAX) _step="0.01" ;;
            *) _step="0.001" ;;
        esac
        quantity=$(awk -v q="$quantity" -v s="$_step" 'BEGIN {printf "%.8f", int(q/s)*s}')
        
        if [ -z "$sl" ] || [ "$sl" = "null" ] || [ "$sl" = "0" ]; then
            log "  ⚠️  Slot ${slot_id}: No SL definido, skipping..."
            continue
        fi
        
        # Calcular si SL está cruzado
        sl_crossed=$(echo "$current_price <= $sl" | bc -l 2>/dev/null || echo "0")
        # FIX: Validate bc result is 0 or 1 - prevents false positives when bc fails
        # Also prevents "null <= number" being interpreted as 0 <= number = TRUE
        if ! echo "$sl_crossed" | grep -qE '^[01]$'; then
            log "  ⚠️  Slot ${slot_id}: bc comparison error, skipping..."
            continue
        fi
        
        if [ "$sl_crossed" -eq 1 ]; then
            log "  🔴 SLOT ${slot_id} - SL CRUZADO! (\$${current_price} <= \$${sl})"
            
            # Calcular distancia al SL (%)
            dist_pct=$(echo "scale=2; ((${entry_price} - ${current_price}) / (${entry_price} - ${sl})) * 100" | bc)
            log "     Distancia al SL: ${dist_pct}%"
            
            # Ejecutar cierre de emergencia
            log "     🚨 Ejecutando market sell de ${quantity} ${COIN}..."
            
            sell_result=$(place_market_sell "${COIN}USDT" "$quantity")
            
            # Verificar resultado
            # FIX: Validate sell_result is valid JSON before parsing
            if ! echo "$sell_result" | jq -e . >/dev/null 2>&1; then
                sell_status="ERROR"
                error_msg="Invalid API response: ${sell_result}"
            else
                sell_status=$(echo "$sell_result" | jq -r '.status // "ERROR"' 2>/dev/null || echo "ERROR")
                error_msg=$(echo "$sell_result" | jq -r '.msg // "Unknown error"' 2>/dev/null || echo "Unknown error")
            fi
            
            if [ "$sell_status" = "FILLED" ] || [ "$sell_status" = "PARTIALLY_FILLED" ]; then
                exit_price=$(echo "$sell_result" | jq -r '.fills[0].price // 0' 2>/dev/null || echo "0")
                fee_bnb=$(echo "$sell_result" | jq -r '.fills[0].commission // 0' 2>/dev/null || echo "0")
                fee_asset=$(echo "$sell_result" | jq -r '.fills[0].commissionAsset // "USDT"' 2>/dev/null || echo "USDT")
                
                # Calcular fee en USDT
                fee_usd=$fee_bnb
                if [ "$fee_asset" = "BNB" ]; then
                    fee_usd=$(awk -v b="$fee_bnb" -v p="$exit_price" 'BEGIN {printf "%.8f", b * p}')
                fi
                
                # Calcular P&L
                pnl=$(awk -v e="$entry_price" -v x="$exit_price" -v q="$quantity" -v f="$fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                
                log "     ✅ CERRADO: Exit=\$${exit_price}, P&L=\$${pnl}"
                
                # Actualizar estado del slot — null ALL trade fields per dashboard pattern
                tmp_file=$(mktemp)
                if jq --argjson sid "$slot_id" --arg ep "$exit_price" --arg pn "$pnl" '
                    .slots = [.slots[] | if .slotId == $sid then .
                        .status = "CLOSED_SL_EMERGENCY" |
                        .quantity = null |
                        .entryPrice = null |
                        .usdtSpent = null |
                        .stopLoss = null |
                        .tp1 = null |
                        .tp2 = null |
                        .tp3 = null |
                        .exitPrice = ($ep | tonumber) |
                        .pnlUSDT = ($pn | tonumber)
                    else . end]
                ' "$STATE_FILE" > "$tmp_file" 2>/dev/null && mv "$tmp_file" "$STATE_FILE"; then
                    log "     ✅ Estado del slot actualizado"
                else
                    log "     ⚠️  No se pudo actualizar estado del slot (continuando...)"
                fi
                
                # 🔧 FIX: Log to trade history for dashboard RECENT TRADES visibility
                log_emergency_trade "$COIN" "$slot_id" "$entry_price" "$exit_price" "$quantity" "$pnl" "Emergency SL close (market sell)" "$sl"
                
                # Agregar al reporte
                pnl_icon="🔴"
                report+="${pnl_icon} <b>${COIN} Slot ${slot_id}</b>\n"
                report+="   Entry: \$${entry_price} → Exit: \$${exit_price}\n"
                report+="   SL: \$${sl} (cruzado ${dist_pct}%)\n"
                report+="   P&L: \$${pnl}\n\n"
                
                closed_count=$((closed_count + 1))
                total_pnl=$(awk -v t="$total_pnl" -v p="$pnl" 'BEGIN {printf "%.8f", t + p}')
                
                # Pequeño delay entre orders
                sleep 1
            else
                log "     ❌ ERROR al cerrar: $sell_result ($error_msg)"

                # ================================================================
                # FIX (2026-10-14): Handle -2010 insufficient balance
                # State file quantity may be out of sync with Binance. Query actual
                # free balance and sell what is really available.
                # ================================================================
                if [ "$code" = "-2010" ] || echo "$error_msg" | grep -q "insufficient balance"; then
                    ts=$(date -u +%s%3N)
                    sig=$(get_signature "timestamp=${ts}&recvWindow=60000")
                    free_bal=$(curl -s "${BINANCE}/api/v3/balance?timestamp=${ts}&recvWindow=60000&signature=${sig}" | jq -r --arg c "${COIN}" '.[] | select(.asset == $c) | .balance // "0"' 2>/dev/null || echo "0")
                    if [ -n "$free_bal" ] && [ "$free_bal" != "0" ] && [ "$free_bal" != "null" ]; then
                        actual_qty=$(awk -v b="$free_bal" -v s="$_step" 'BEGIN {printf "%.8f", int(b/s)*s}')
                        if [ -n "$actual_qty" ] && [ "$actual_qty" != "0.00000000" ] && [ "$actual_qty" != "0" ]; then
                            log "     💰 Balance real ${COIN}: ${free_bal} → intentando vender ${actual_qty}..."
                            sell_result2=$(place_market_sell "${COIN}USDT" "$actual_qty")
                            if echo "$sell_result2" | jq -e . >/dev/null 2>&1; then
                                sell_status2=$(echo "$sell_result2" | jq -r '.status // "ERROR"' 2>/dev/null || echo "ERROR")
                                if [ "$sell_status2" = "FILLED" ] || [ "$sell_status2" = "PARTIALLY_FILLED" ]; then
                                    exit_price2=$(echo "$sell_result2" | jq -r '.fills[0].price // 0' 2>/dev/null || echo "0")
                                    fee_bnb2=$(echo "$sell_result2" | jq -r '.fills[0].commission // 0' 2>/dev/null || echo "0")
                                    fee_asset2=$(echo "$sell_result2" | jq -r '.fills[0].commissionAsset // "USDT"' 2>/dev/null || echo "USDT")
                                    fee_usd2=$fee_bnb2
                                    [ "$fee_asset2" = "BNB" ] && fee_usd2=$(awk -v b="$fee_bnb2" -v p="$exit_price2" 'BEGIN {printf "%.8f", b * p}')
                                    pnl2=$(awk -v e="$entry_price" -v x="$exit_price2" -v q="$actual_qty" -v f="$fee_usd2" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                                    log "     ✅ CERRADO (balance real): Exit=$exit_price2, Qty=$actual_qty, P&L=$pnl2"
                                    tmp_file=$(mktemp)
                                    jq --argjson sid "$slot_id" --arg ep "$exit_price2" --arg pn "$pnl2" --arg aq "$actual_qty" '.slots = [.slots[] | if .slotId == $sid then . | .status = "CLOSED_SL_EMERGENCY" | .quantity = null | .entryPrice = null | .usdtSpent = null | .stopLoss = null | .tp1 = null | .tp2 = null | .tp3 = null | .exitPrice = ($ep | tonumber) | .pnlUSDT = ($pn | tonumber) | .actualSoldQty = ($aq | tonumber) else . end]' "$STATE_FILE" > "$tmp_file" 2>/dev/null && mv "$tmp_file" "$STATE_FILE"
                                    # 🔧 FIX: Log to trade history for dashboard visibility
                                    log_emergency_trade "$COIN" "$slot_id" "$entry_price" "$exit_price2" "$actual_qty" "$pnl2" "SL close via real balance retry" "$sl"
                                    report+="🔴 <b>${COIN} Slot ${slot_id}</b> (sold ${actual_qty} real)
   Entry: $${entry_price} → Exit: $${exit_price2}
   P&L: $${pnl2}

"
                                    closed_count=$((closed_count + 1))
                                    total_pnl=$(awk -v t="$total_pnl" -v p="$pnl2" 'BEGIN {printf "%.8f", t + p}')
                                else
                                    log "     ❌ Retry con balance real también falló"
                                fi
                            else
                                log "     ❌ Retry con balance real respuesta inválida"
                            fi
                        else
                            log "     ⚠️ Balance ${free_bal} < step size ${_step} - mark slot como CLOSED (liquidez insuficiente)"
                            tmp_file=$(mktemp)
                            jq --argjson sid "$slot_id" '.slots = [.slots[] | if .slotId == $sid then . | .status = "CLOSED_SL_EMERGENCY" | .quantity = null | .entryPrice = null | .usdtSpent = null | .stopLoss = null | .tp1 = null | .tp2 = null | .tp3 = null | .exitPrice = null | .pnlUSDT = null | .closeNote = "below step size" | .closeType = "CLOSED_SL_EMERGENCY" | .closeTime = (now | todate) else . end]' "$STATE_FILE" > "$tmp_file" 2>/dev/null && mv "$tmp_file" "$STATE_FILE"
                            # 🔧 FIX: Log to trade history for dashboard visibility
                            log_emergency_trade "$COIN" "$slot_id" "$entry_price" "" "" "0" "Position below step size, externally liquidated" "$sl"
                            report+="⚠️ <b>${COIN} Slot ${slot_id}</b>: Posición ya vendida (< step size)

"
                            closed_count=$((closed_count + 1))
                        fi
                    else
                        log "     ⚠️ Sin balance ${COIN} en cuenta - posición ya vendida externamente"
                        tmp_file=$(mktemp)
                        # 🔧 FIX: closeNote now uses $coin arg instead of hardcoded "0 ZEC balance"
                        jq --argjson sid "$slot_id" --arg coin "$COIN" '.slots = [.slots[] | if .slotId == $sid then . | .status = "CLOSED_SL_EMERGENCY" | .quantity = null | .entryPrice = null | .usdtSpent = null | .stopLoss = null | .tp1 = null | .tp2 = null | .tp3 = null | .exitPrice = null | .pnlUSDT = null | .closeNote = ("0 " + $coin + " balance") | .closeType = "CLOSED_SL_EMERGENCY" | .closeTime = (now | todate) else . end]' "$STATE_FILE" > "$tmp_file" 2>/dev/null && mv "$tmp_file" "$STATE_FILE"
                        # 🔧 FIX: Log to trade history for dashboard visibility
                        log_emergency_trade "$COIN" "$slot_id" "$entry_price" "" "" "0" "Position already sold externally (0 ${COIN} balance)" "$sl"
                        report+="⚠️ <b>${COIN} Slot ${slot_id}</b>: Ya vendida externamente (0 ${COIN})

"
                        closed_count=$((closed_count + 1))
                    fi
                # ================================================================
                # Original LOT_SIZE retry (for remaining edge cases)
                # ================================================================
                elif echo "$error_msg" | grep -q "LOT_SIZE\|NOTIONAL\|MIN_NOTIONAL"; then
                    full_qty=$(awk -v u="$usdt_spent" -v e="$entry_price" 'BEGIN {printf "%.8f", u/e}')
                    log "     🔄 Retry con qty completa: ${full_qty} ${COIN}..."
                    sell_result2=$(place_market_sell "${COIN}USDT" "$full_qty")
                    if echo "$sell_result2" | jq -e . >/dev/null 2>&1; then
                        sell_status2=$(echo "$sell_result2" | jq -r '.status // "ERROR"' 2>/dev/null || echo "ERROR")
                        if [ "$sell_status2" = "FILLED" ] || [ "$sell_status2" = "PARTIALLY_FILLED" ]; then
                            exit_price=$(echo "$sell_result2" | jq -r '.fills[0].price // 0' 2>/dev/null || echo "0")
                            fee_bnb=$(echo "$sell_result2" | jq -r '.fills[0].commission // 0' 2>/dev/null || echo "0")
                            fee_asset=$(echo "$sell_result2" | jq -r '.fills[0].commissionAsset // "USDT"' 2>/dev/null || echo "USDT")
                            fee_usd=$fee_bnb
                            [ "$fee_asset" = "BNB" ] && fee_usd=$(awk -v b="$fee_bnb" -v p="$exit_price" 'BEGIN {printf "%.8f", b * p}')
                            pnl=$(awk -v e="$entry_price" -v x="$exit_price" -v q="$full_qty" -v f="$fee_usd" 'BEGIN {printf "%.8f", ((x - e) * q) - f}')
                            log "     ✅ RETRY CERRADO: Exit=${exit_price}, P&L=${pnl}"
                            tmp_file=$(mktemp)
                            jq --argjson sid "$slot_id" --arg ep "$exit_price" --arg pn "$pnl" '
                                .slots = [.slots[] | if .slotId == $sid then .
                                    .status = "CLOSED_SL_EMERGENCY" |
                                    .quantity = null | .entryPrice = null | .usdtSpent = null |
                                    .stopLoss = null | .tp1 = null | .tp2 = null | .tp3 = null |
                                    .exitPrice = ($ep | tonumber) | .pnlUSDT = ($pn | tonumber)
                                else . end]
                            ' "$STATE_FILE" > "$tmp_file" 2>/dev/null && mv "$tmp_file" "$STATE_FILE"
                            # 🔧 FIX: Log to trade history for dashboard visibility
                            log_emergency_trade "$COIN" "$slot_id" "$entry_price" "$exit_price" "$full_qty" "$pnl" "SL close via LOT_SIZE retry" "$sl"
                            report+="🔴 <b>${COIN} Slot ${slot_id} (retry)</b>\n"
                            report+="   Entry: ${entry_price} → Exit: ${exit_price}\n"
                            report+="   P&L: ${pnl}\n\n"
                            closed_count=$((closed_count + 1))
                            total_pnl=$(awk -v t="$total_pnl" -v p="$pnl" 'BEGIN {printf "%.8f", t + p}')
                            sleep 1
                        else
                            log "     ❌ Retry también falló: $sell_result2"
                            report+="❌ <b>${COIN} Slot ${slot_id}</b>: Retry failed (LOT_SIZE/NOTIONAL)\n\n"
                        fi
                    else
                        log "     ❌ Retry respuesta inválida"
                        report+="❌ <b>${COIN} Slot ${slot_id}</b>: Invalid retry response\n\n"
                    fi
                else
                    report+="❌ <b>${COIN} Slot ${slot_id}</b>: ERROR - $error_msg\n\n"
                fi
            fi
        else
            log "  🟢 Slot ${slot_id}: OK (SL no cruzado)"
        fi
    done <<< "$active_slots"
done

# ============================================
# 📊 REPORTE FINAL
# ============================================

log "╔═══════════════════════════════════════════════════════╗"
log "║  REPORTE FINAL                                        ║"
log "╚═══════════════════════════════════════════════════════╝"
log "Slots cerrados: ${closed_count}"
log "P&L Total: \$${total_pnl}"

# Enviar Telegram
if [ $closed_count -gt 0 ]; then
    total_pnl_fmt=$(awk -v p="$total_pnl" 'BEGIN {printf "%.2f", p}')
    pnl_icon="🔴"
    
    notify "EMERGENCY_CLOSE_SL" "🚨 **EMERGENCY CLOSE - SL CRUZADO**

Se cerraron ${closed_count} slots con Stop Loss cruzado:

${report}
**📊 Resumen:**
• Slots cerrados: ${closed_count}
• P&L Total: ${pnl_icon} \$${total_pnl_fmt}
• Razón: Prevención de mayores pérdidas

⚠️ Los slots se marcaron como CLOSED_SL_EMERGENCY para no re-entrar automáticamente.

_Generated by Perrobotillo Emergency System_ 🐕"
fi

log "✅ Emergency close completado"
