#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧠 ML AUTO-RETRAIN - Weekly Cron Job
# ════════════════════════════════════════════════════════
# Corre todos los domingos a las 3:00 AM
# Re-entrena el modelo ML validator con nuevos trades
# ════════════════════════════════════════════════════════

WORKSPACE="$HOME/.openclaw/workspace"
LOG_FILE="$HOME/.openclaw/logs/ml-retrain-cron.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "╔═══════════════════════════════════════════════════════╗"
log "║  🧠 ML Auto-Retrain - Domingo 3:00 AM                 ║"
log "╚═══════════════════════════════════════════════════════╝"

# Activar virtualenv si existe
if [ -f "$WORKSPACE/venv/bin/activate" ]; then
    source "$WORKSPACE/venv/bin/activate"
    log "✅ Virtualenv activado"
fi

# Ejecutar re-entrenamiento
cd "$WORKSPACE/ml"
python3 ml-retrain.py

if [ $? -eq 0 ]; then
    log "✅ Re-entrenamiento completado exitosamente"
    # El reporte detallado ya se envía desde ml-retrain.py
else
    log "❌ Error en el re-entrenamiento"
    
    # Notificar error
    TELEGRAM_ENV="$WORKSPACE/secrets/telegram.env"
    if [ -f "$TELEGRAM_ENV" ]; then
        source "$TELEGRAM_ENV"
        
        message="🚨 *ML Auto-Retrain FALLÓ*

❌ Error al re-entrenar el modelo
🕐 Domingo $(date '+%Y-%m-%d %H:%M')

Revisar logs: \`ml-retrain.log\`"
        
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=${message}" \
            -d "parse_mode=Markdown" > /dev/null
    fi
fi

log ""
