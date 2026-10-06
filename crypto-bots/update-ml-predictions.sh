#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧠 UPDATE ML PREDICTIONS - Rápido y Ligero
# ════════════════════════════════════════════════════════
# Actualiza ONLY las predicciones del mercado (sin validación)
# Para usar con cron cada 1-2 horas
# Uso: ./update-ml-predictions.sh
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
ML_DIR="${WORKSPACE}/ml"
ML_PREDICTIONS="${ML_DIR}/market-predictions.json"
LOG_FILE="${WORKSPACE}/logs/ml-predictions-update.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "╔═══════════════════════════════════════════════════════╗"
log "║  🧠 UPDATE ML PREDICTIONS                             ║"
log "╚═══════════════════════════════════════════════════════╝"

# ✅ JSONL: Log de predicciones ML
ML_INPUT_LOG="$WORKSPACE/logs/ml-prediction-input.log"

log_ml_prediction() {
    local event="$1"
    local detail="$2"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "{\"timestamp\":\"$ts\",\"event\":\"$event\",\"detail\":\"$detail\"}" >> "$ML_INPUT_LOG"
}

# Verificar que existan los modelos
if [ ! -f "${ML_DIR}/models/BTC_ml_model.pkl" ]; then
    log "❌ Error: Modelos ML no encontrados. Ejecutar auto-retrain primero."
    log_ml_prediction "ml.predict.error" "models_not_found"
    exit 1
fi

# Ejecutar SOLO predicción (sin validación completa)
log "⏳ Ejecutando ML classifier (predict only)..."

python3 "${ML_DIR}/market-classifier.py" --predict 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -ne 0 ]; then
    log "❌ Error ejecutando ML classifier"
    exit 1
fi

# Verificar que se generó el archivo
if [ ! -f "$ML_PREDICTIONS" ]; then
    log "❌ Error: No se generó market-predictions.json"
    exit 1
fi

# Leer resultados rápidos
TIMESTAMP=$(python3 -c "import json; d=json.load(open('$ML_PREDICTIONS')); print(d.get('timestamp', 'UNKNOWN'))")
MODE=$(python3 -c "import json; d=json.load(open('$ML_PREDICTIONS')); print(d.get('recommended_mode', 'UNKNOWN'))")
BTC_CONF=$(python3 -c "import json; d=json.load(open('$ML_PREDICTIONS')); print(f\"{d['predictions'].get('BTC', {}).get('confidence', 0)*100:.0f}%\")")

log "✅ ML Predictions actualizadas"
log "   Timestamp: ${TIMESTAMP}"
log "   Recommended Mode: ${MODE}"
log "   BTC Confidence: ${BTC_CONF}"

log_ml_prediction "ml.predict.success" "timestamp=$TIMESTAMP,mode=$MODE,btc_conf=$BTC_CONF"

# ✅ JSONL: Log de features individuales si existen
if [ -f "$ML_PREDICTIONS" ]; then
    python3 -c "
import json, sys
try:
    d = json.load(open('$ML_PREDICTIONS'))
    ts = d.get('timestamp','UNKNOWN')
    mode = d.get('recommended_mode','UNKNOWN')
    preds = d.get('predictions', {})
    for coin, p in preds.items():
        conf = p.get('confidence', 0)
        action = p.get('action', 'UNKNOWN')
        print(json.dumps({'timestamp': ts, 'coin': coin, 'confidence': conf, 'action': action}))
except Exception as e:
    print(json.dumps({'error': str(e)}), file=sys.stderr)
" >> "$ML_INPUT_LOG" 2>/dev/null || true
fi

# Verificar edad del archivo anterior (opcional, para logging)
if [ -f "$ML_PREDICTIONS" ]; then
    FILE_AGE=$(python3 -c "
import json, datetime
d = json.load(open('$ML_PREDICTIONS'))
ts = datetime.datetime.fromisoformat(d['timestamp'])
age = (datetime.datetime.now() - ts).total_seconds() / 60
print(f'{age:.0f} min')
")
    log "   Edad de predicciones anteriores: ${FILE_AGE}"
fi

log ""
log "╔═══════════════════════════════════════════════════════╗"
log "║  ✅ UPDATE COMPLETED                                  ║"
log "╚═══════════════════════════════════════════════════════╝"
log ""

exit 0
