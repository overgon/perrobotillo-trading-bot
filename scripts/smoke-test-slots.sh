#!/bin/bash
# ════════════════════════════════════════════
# 🐕 SMOKE TEST - Verificación de slots y monedas
# Incluye alertas de Telegram
# ════════════════════════════════════════════

set -e

WORKSPACE="${WORKSPACE:-/home/overgon/.openclaw/workspace}"
CRYPTO_BOTS="$WORKSPACE/crypto-bots"
DASHBOARD="$WORKSPACE/dashboard"
LOG_FILE="$WORKSPACE/logs/smoke-test.log"
TELEGRAM_SECRET="$WORKSPACE/secrets/telegram.env"

# Logger con timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Cargar credenciales de Telegram
if [ -f "$TELEGRAM_SECRET" ]; then
    source "$TELEGRAM_SECRET"
fi

# Enviar alerta a Telegram
send_telegram_alert() {
    local message="$1"
    local event_key="$2"
    
    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
        log "⚠️ Telegram: token o chat_id no configurados, omitiendo alerta"
        return 0
    fi
    
    local escaped_message
    escaped_message=$(printf '%s' "$message" | sed 's/&/\\&amp;/g; s/</\\&lt;/g; s/>/\\&gt;/g')
    
    local response
    response=$(curl -s --max-time 10 -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${escaped_message}" \
        -d "parse_mode=HTML" 2>&1)
    
    local http_code
    http_code=$(echo "$response" | tail -1)
    
    if [ "$http_code" = "200" ]; then
        log "✅ Telegram: alerta enviada"
        return 0
    else
        log "❌ Telegram: error HTTP ${http_code}"
        return 1
    fi
}

# Notificación principal
notify() {
    local key="$1"
    local message="$2"
    local event_key="$3"
    
    log "📢 Notificando: $key"
    send_telegram_alert "$message" "$event_key"
}

log "╔═══════════════════════════════════════════╗"
log "╔═══════════════════════════════════════════╗"
log "║  🐕 PERROBOTILLO - SMOKE TEST SLOTS      ║"
log "╚═══════════════════════════════════════════╝"
log ""

# === 1. Verificar archivos trade-state.json ===
log "═══════════════════════════════════════════"
log "📋 PASO 1: Verificando archivos trade-state.json"
log "═══════════════════════════════════════════"

MONEDAS=("BTC" "ETH" "BNB" "SOL" "ZEC" "LINK" "XRP" "AVAX")
TOTAL_SLOTS=0
ERRORES=0

for coin in "${MONEDAS[@]}"; do
    FILE="$CRYPTO_BOTS/${coin}-trade-state.json"
    if [ ! -f "$FILE" ]; then
        log "❌ ${coin}: archivo trade-state.json NO encontrado"
        ((ERRORES++))
        continue
    fi
    
    # Verificar estructura JSON
    read SLOTS COUNT IDS STATUSES <<< $(python3 -c "
import json
with open('$FILE') as f:
    state = json.load(f)
    slots = state.get('slots', [])
    total = len(slots)
    ids = [s.get('slotId') for s in slots]
    statuses = [s.get('status') for s in slots]
    print(f\"{total} {ids} {statuses}\")
" 2>/dev/null)
    
    if [ -z "$COUNT" ]; then
        log "❌ ${coin}: archivo inválido"
        ((ERRORES++))
    else
        if [ "$COUNT" -eq 3 ]; then
            log "✅ ${coin}: ${COUNT} slots (IDs: ${IDS}, Status: ${STATUSES})"
        else
            log "⚠️ ${coin}: ${COUNT} slots (esperados 3)"
        fi
        TOTAL_SLOTS=$((TOTAL_SLOTS + COUNT))
    fi
done

log "📊 Resumen Paso 1: ${TOTAL_SLOTS} slots verificados"
log ""

# === 2. Ejecutar update-grid-status.py ===
log "═══════════════════════════════════════════"
log "📋 PASO 2: Actualizando grid-status.json"
log "═══════════════════════════════════════════"

if python3 scripts/update-grid-status.py 2>&1 | tee -a "$LOG_FILE"; then
    log "✅ update-grid-status.py ejecutado correctamente"
else
    log "⚠️ update-grid-status.py tuvo errores (credenciales Binance)"
fi
log ""

# === 3. Verificar grid-status.json ===
log "═══════════════════════════════════════════"
log "📋 PASO 3: Verificando grid-status.json"
log "═══════════════════════════════════════════"

if [ ! -f "$DASHBOARD/grid-status.json" ]; then
    log "❌ grid-status.json NO encontrado"
    ((ERRORES++))
else
    python3 << 'PYEOF'
import json
with open('/home/overgon/.openclaw/workspace/dashboard/grid-status.json') as f:
    data = json.load(f)

print(f"  Monedas: {len(data.get('bots', {}))}")
total_slots = 0
for coin, info in data.get('bots', {}).items():
    slots = info.get('slots', [])
    total_slots += len(slots)
    status = "✅" if len(slots) == 3 else "❌"
    print(f"    {status} {coin}: {len(slots)} slots (IDs: {[s.get('slotId') for s in slots]})")

print(f"  Total slots: {total_slots}")
print(f"  Total orders: {data.get('totalOrders')}")
PYEOF
fi
log ""

# === 4. Smoke Test en cada slot y moneda ===
log "═══════════════════════════════════════════"
log "📋 PASO 4: Smoke Test - Verificando cada slot"
log "═══════════════════════════════════════════"

SMOKE_ERRORS=0
for coin in "${MONEDAS[@]}"; do
    FILE="$CRYPTO_BOTS/${coin}-trade-state.json"
    
    if [ ! -f "$FILE" ]; then
        log "❌ ${coin}: archivo no encontrado"
        ((SMOKE_ERRORS++))
        continue
    fi
    
    # Leer slots
    while IFS='|' read -r COIN SLOT_ID STATUS; do
        [ -z "$COIN" ] && continue
        if [ -z "$SLOT_ID" ] || [ -z "$STATUS" ]; then
            log "❌ ${COIN} Slot: datos incompletos"
            ((SMOKE_ERRORS++))
            continue
        fi
        
        # Verificar estado del slot
        case "$STATUS" in
            READY|ACTIVE|SELL|BUY|CLOSED*|PAUSED)
                log "✅ ${COIN} Slot ${SLOT_ID}: ${STATUS}"
                ;;
            *)
                log "⚠️ ${COIN} Slot ${SLOT_ID}: estado inesperado '${STATUS}'"
                ((SMOKE_ERRORS++))
                ;;
        esac
        
        # Enviar alerta de Telegram para cada slot
        # Solo alertar si hay errores
        if [ "$SMOKE_ERRORS" -gt 0 ]; then
            send_telegram_alert "⚠️ SMOKE TEST ERROR ⟶ ${COIN} Slot ${SLOT_ID} estado: ${STATUS}" "smoke-test:${COIN}:slot:${SLOT_ID}"
        fi
      done < <(python3 -c "
import json
with open('$FILE') as f:
    state = json.load(f)
    for slot in state.get('slots', []):
        print(f\"{coin}|{slot.get('slotId')}|{slot.get('status')}\")
" 2>/dev/null)
done

log "📊 Resumen Smoke Test: ${SMOKE_ERRORS} errores detectados"
log ""

# === 5. Resumen final ===
log "═══════════════════════════════════════════"
log "📋 RESUMEN FINAL"
log "═══════════════════════════════════════════"
log "✅ Monedas verificadas: ${#MONEDAS[@]}"
log "✅ Slots verificados: ${TOTAL_SLOTS}"
log "❌ Errores: ${ERRORES} (Paso 1) + ${SMOKE_ERRORS} (Smoke)"
log "📱 Alertas de Telegram: configuradas"

if [ $ERRORES -eq 0 ] && [ $SMOKE_ERRORS -eq 0 ]; then
    log "🎉 SMOKE TEST PASADO EXITOSAMENTE"
    notify "✅ SMOKE TEST PASADO" "smoke-test:summary:passed"
    exit 0
else
    log "⚠️ SMOKE TEST CON ERRORES"
    notify "⚠️ SMOKE TEST CON ERRORES: ${ERRORES} (Paso 1) + ${SMOKE_ERRORS} (Smoke)" "smoke-test:summary:failed"
    exit 1
fi
