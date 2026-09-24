#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧠 ML VALIDATOR STATUS REPORT - Domingo 9 AM
# Envía reporte semanal del status del auto-retrain ML
# ════════════════════════════════════════════════════════

set +e

WORKSPACE="/home/overgon/.openclaw/workspace"
OPENCLAW_BASE="/home/overgon/.openclaw"
LOG_FILE="$OPENCLAW_BASE/logs/ml-retrain-report.log"
MODELS_DIR="$WORKSPACE/ml/models_optimized"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "╔════════════════════════════════════════════════════════╗"
log "║  🧠 ML RETRAIN STATUS REPORT - Domingo 9 AM            ║"
log "╚════════════════════════════════════════════════════════╝"
log ""

# ═══════════════════════════════════════════
# 1. Verificar metadatos de todos los modelos
# ═══════════════════════════════════════════
log "📊 STATUS POR MONEDA:"

PASS=0; WARN=0; FAIL=0
coin_lines=""

for coin in BTC ETH BNB SOL LINK XRP AVAX; do
    meta="$MODELS_DIR/${coin}_optimized_metadata.json"
    if [ -f "$meta" ]; then
        acc=$(jq -r '.metrics.accuracy * 100 | floor' "$meta" 2>/dev/null)
        gap=$(jq -r '.metrics.overfitting_gap * 100 | floor' "$meta" 2>/dev/null)
        cv=$(jq -r '.metrics.cv_mean * 100 | floor' "$meta" 2>/dev/null)
        f1=$(jq -r '.metrics.f1 * 100 | floor' "$meta" 2>/dev/null)
        trained_date=$(jq -r '.trained_at | split("T")[0]' "$meta" 2>/dev/null)

        if [ "$gap" -lt 5 ] 2>/dev/null; then
            status="✅"
            PASS=$((PASS + 1))
        else
            status="⚠️"
            WARN=$((WARN + 1))
        fi

        log "  ${coin}: acc=${acc}% gap=${gap}% cv=${cv}% f1=${f1}% trained=${trained_date} ${status}"
        coin_lines="${coin_lines}├─ ${coin}: acc=${acc}% gap=${gap}% cv=${cv}% ${status}\n"
    else
        log "  ${coin}: ❌ Modelo no encontrado"
        coin_lines="${coin_lines}├─ ${coin}: ❌ No modelo\n"
        FAIL=$((FAIL + 1))
    fi
done

log ""
log "📊 RESUMEN: ${PASS}/7 OK | ${WARN}/7 Warn | ${FAIL}/7 Fail"
log ""

# ═══════════════════════════════════════════
# 2. Enviar mensaje formateado para Telegram
# ═══════════════════════════════════════════
LAST_TRAIN_DATE=$(jq -r '.trained_at | split("T")[0]' "$MODELS_DIR/LINK_optimized_metadata.json" 2>/dev/null || echo "N/A")

# Construir mensaje con echo para preservar newlines reales
MESSAGE=$(echo -e "🧠 *ML VALIDATOR - REPORTE SEMANAL*

📅 Última actualización: $LAST_TRAIN_DATE

📊 *STATUS POR MONEDA:*
$(echo -e "$coin_lines")
📈 *Resumen:* ${PASS}/7 OK | ${WARN}/7 Warn | ${FAIL}/7 Fail
⏰ *Próximo retrain:* Domingo 3:00 AM
✅ *ML VALIDATOR Status:* OPERATIVO
🤖 Perrobotillo Trading Bot v2.1")

# ═══════════════════════════════════════════
# 3. Enviar por Telegram
# ═══════════════════════════════════════════
log "--- ENVÍO DE NOTIFICACIÓN ---"

# Cargar credenciales de telegram
TELEGRAM_ENV="$WORKSPACE/secrets/telegram.env"
if [ -f "$TELEGRAM_ENV" ]; then
    source "$TELEGRAM_ENV"
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    log "❌ Error: TELEGRAM_BOT_TOKEN no configurado"
    echo "$MESSAGE"
    exit 1
fi

# Enviar usando send-telegram.sh (método probado)
SEND_TELEGRAM="$WORKSPACE/lib/send-telegram.sh"
if [ -f "$SEND_TELEGRAM" ]; then
    "$SEND_TELEGRAM" "$MESSAGE" "Markdown" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        log "✅ Notificación enviada por Telegram (via send-telegram.sh)"
    else
        log "⚠️ send-telegram.sh falló, retry con curl directo"
        HTTP_CODE=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            --data-urlencode "text=${MESSAGE}" \
            -d "parse_mode=Markdown" \
            -w "%{http_code}" -o /dev/null 2>/dev/null)
        if [ "$HTTP_CODE" = "200" ]; then
            log "✅ Notificación enviada por Telegram (HTTP $HTTP_CODE)"
        else
            log "❌ Error enviando Telegram (HTTP $HTTP_CODE)"
        fi
    fi
else
    log "❌ No se encontró send-telegram.sh, usando curl directo"
    HTTP_CODE=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${MESSAGE}" \
        -d "parse_mode=Markdown" \
        -w "%{http_code}" -o /dev/null 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        log "✅ Notificación enviada por Telegram (HTTP $HTTP_CODE)"
    else
        log "❌ Error enviando Telegram (HTTP $HTTP_CODE)"
    fi
fi

exit 0
