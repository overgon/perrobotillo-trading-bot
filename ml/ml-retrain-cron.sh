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

# Ejecutar re-entrenamiento Fase 5 (pipeline completo de 7 monedas)
# run_fase5_all.sh ejecuta fase5_train.py dentro del container jesse
# 7 monedas × ~2 min cada una = ~15 min total
cd "$WORKSPACE/../jesse-research" 2>/dev/null || cd "$HOME/jesse-research"
if [ -f "run_fase5_all.sh" ]; then
    chmod +x run_fase5_all.sh
    timeout 3600 ./run_fase5_all.sh
    exit_code=$?
else
    log "❌ run_fase5_all.sh no encontrado en $(pwd)"
    exit_code=1
fi

if [ $exit_code -eq 0 ]; then
    log "✅ Re-entrenamiento completado exitosamente"
    
    # ═══ Sync new models to production ═══
    JESSE_MODELS_DIR="$HOME/jesse-research/fase5_models"
    PROD_MODELS_DIR="$WORKSPACE/ml/models_optimized"
    PROD_FEATURES_DIR="$WORKSPACE/ml/features"
    
    for coin in BTC ETH BNB SOL LINK XRP AVAX; do
        coin_model_dir="$JESSE_MODELS_DIR/$coin"
        if [ -f "$coin_model_dir/${coin}_optimized_model.pkl" ]; then
            cp "$coin_model_dir/${coin}_optimized_model.pkl" "$PROD_MODELS_DIR/"
            cp "$coin_model_dir/${coin}_scaler_optimized.pkl" "$PROD_MODELS_DIR/"
            cp "$coin_model_dir/${coin}_selected_features.pkl" "$PROD_MODELS_DIR/"
            cp "$coin_model_dir/${coin}_optimized_metadata.json" "$PROD_MODELS_DIR/"
            log "  ✅ $coin modelos sincronizados a producción"
        fi
    done
    log "✅ Modelos Fase 5 desplegados en models_optimized/"
    
    # ═══ Refresh feature CSVs with BTC context features ═══
    python3 "$WORKSPACE/ml/patch_context_features.py" >> "$LOG_FILE" 2>&1
    log "✅ Feature CSVs actualizados con BTC context (btc_ema_cross, fear_greed, market_mode, confidence_score)"
    
    # ═══ Telegram success notification ═══
    TELEGRAM_ENV="$WORKSPACE/secrets/telegram.env"
    if [ -f "$TELEGRAM_ENV" ]; then
        source "$TELEGRAM_ENV"
        message="✅ *ML Auto-Retrain EXITOSO*

✅ 7 monedas re-entrenadas y desplegadas
📊 Models Fase 5 en models_optimized/
🎯 Feature CSVs refrescados con BTC context
📅 Domingo $(date '+%Y-%m-%d %H:%M')

Revisar: \`ml-retrain.log\`"
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            --data-urlencode "text=${message}" \
            -d "parse_mode=Markdown" > /dev/null 2>&1
        log "✅ Notificación Telegram enviada"
    fi
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
            --data-urlencode "text=${message}" \
            -d "parse_mode=Markdown" > /dev/null
    fi
fi

log ""
