#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧠 ML AUTO-RETRAIN - Weekly Cron Job
# ════════════════════════════════════════════════════════
# Corre todos los domingos a las 3:00 AM
# Re-entrena el modelo ML validator con nuevos trades
# Pipeline: auto-retrain-v2.py (8 coins, sin Docker)
# ════════════════════════════════════════════════════════

HOME="/home/overgon"
WORKSPACE="$HOME/.openclaw/workspace"
ML_DIR="$WORKSPACE/ml"
LOG_FILE="$HOME/.openclaw/logs/ml-retrain-cron.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "╔═══════════════════════════════════════════════════════╗"
log "║  🧠 ML Auto-Retrain - Domingo 3:00 AM                 ║"
log "╚═══════════════════════════════════════════════════════╝"

# Usar python directo (no venv, no Docker)
PYTHON="/usr/bin/python3"
RETAIN_DAYS=90

cd "$ML_DIR" || {
    log "❌ No se pudo cd a $ML_DIR"
    exit_code=1
}

if [ "${exit_code:-0}" -eq 0 ]; then
    log "🚀 Ejecutando auto-retrain-v2.py con timeout 3600s..."
    timeout 3600 "$PYTHON" "$ML_DIR/auto-retrain-v2.py" >> "$LOG_FILE" 2>&1
    exit_code=$?
    log "Exit code: $exit_code"
fi

if [ $exit_code -eq 0 ]; then
    log "✅ Re-entrenamiento completado exitosamente"

    # ═══ Patch context features for BTC (needed since auto-retrain-v2 uses system CSVs) ═══
    if [ -f "$ML_DIR/patch_context_features.py" ]; then
        "$PYTHON" "$ML_DIR/patch_context_features.py" >> "$LOG_FILE" 2>&1
        log "✅ Feature CSVs actualizados con BTC context"
    fi

    # ═══ Telegram success notification ═══
    TELEGRAM_ENV="$WORKSPACE/secrets/telegram.env"
    if [ -f "$TELEGRAM_ENV" ]; then
        source "$TELEGRAM_ENV"
        message="✅ *ML Auto-Retrain EXITOSO*
- 8 monedas re-entrenadas y desplegadas
- Models en models_optimized/
- Feature CSVs refrescados con BTC context
- Domingo $(date '+%Y-%m-%d %H:%M')"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            --data-urlencode "text=${message}" \
            -d "parse_mode=Markdown" > /dev/null 2>&1
        log "✅ Notificación Telegram enviada"
    fi
else
    log "❌ Error en el re-entrenamiento (exit code $exit_code)"

    # Notificar error
    TELEGRAM_ENV="$WORKSPACE/secrets/telegram.env"
    if [ -f "$TELEGRAM_ENV" ]; then
        source "$TELEGRAM_ENV"
        message="🚨 *ML Auto-Retrain FALLÓ*
- Error al re-entrenar modelos (exit code $exit_code)
- Domingo $(date '+%Y-%m-%d %H:%M')
- Revisar: ml-retrain-cron.log"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            --data-urlencode "text=${message}" \
            -d "parse_mode=Markdown" > /dev/null 2>&1
    fi
fi

log "═══ FIN ML RETRAIN ═══"