#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧠 ML VALIDATOR STATUS REPORT - Domingo 9 AM
# Envía reporte semanal del status del auto-retrain ML
# ════════════════════════════════════════════════════════

# NO usar set -e porque grep puede retornar 1 si no encuentra

WORKSPACE="/home/overgon/.openclaw/workspace"
OPENCLAW_BASE="/home/overgon/.openclaw"
LOG_FILE="$OPENCLAW_BASE/logs/ml-retrain-report.log"
LAST_RETRAIN_JSON="$WORKSPACE/ml/ml-last-retrain.json"
MODEL_METADATA="$WORKSPACE/ml/ml-validator-model.json"
ML_RETRAIN_LOG="$OPENCLAW_BASE/logs/ml-retrain.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🤖 ML RETRAIN STATUS REPORT"

# Verificar archivos existentes
if [ ! -f "$LAST_RETRAIN_JSON" ]; then
    log "❌ Error: No existe last_retrain.json"
    exit 1
fi

# Leer última fecha de retrain
LAST_RETRAIN=$(jq -r '.last_retrain' "$LAST_RETRAIN_JSON")
TRADE_COUNT=$(jq -r '.trade_count_at_retrain' "$LAST_RETRAIN_JSON")
RETRAIN_COUNT=$(jq -r '.retrain_count' "$LAST_RETRAIN_JSON")

# Convertir fecha a formato legible
LAST_RETRAIN_DATE=$(echo "$LAST_RETRAIN" | cut -d'T' -f1)
LAST_RETRAIN_TIME=$(echo "$LAST_RETRAIN" | cut -d'T' -f2 | cut -d'.' -f1)

# Calcular días desde último retrain
LAST_RETRAIN_EPOCH=$(date -d "$LAST_RETRAIN_DATE" +%s 2>/dev/null || echo "0")
NOW_EPOCH=$(date +%s)
DAYS_SINCE=$(( (NOW_EPOCH - LAST_RETRAIN_EPOCH) / 86400 ))

# Leer accuracy desde model_metadata.json (fuente confiable)
CURRENT_ACCURACY="N/A"
PREV_ACCURACY="N/A"
MODEL_SIZE="N/A"
if [ -f "$MODEL_METADATA" ]; then
    ACCURACY_RAW=$(jq -r '.accuracy // empty' "$MODEL_METADATA" 2>/dev/null)
    if [ -n "$ACCURACY_RAW" ]; then
        # Convertir de 0.8052 a 80.52%
        CURRENT_ACCURACY=$(echo "$ACCURACY_RAW * 100" | bc | xargs printf "%.2f%%")
    fi
fi

# Calcular tamaño del modelo desde el archivo .pkl
MODEL_PKL="$WORKSPACE/ml/ml-validator-model.pkl"
if [ -f "$MODEL_PKL" ]; then
    SIZE_BYTES=$(stat -c%s "$MODEL_PKL" 2>/dev/null || echo "0")
    SIZE_MB=$(echo "scale=2; $SIZE_BYTES / 1048576" | bc)
    # Asegurar formato con cero a la izquierda (0.48 en lugar de .48)
    if [[ "$SIZE_MB" == .* ]]; then
        SIZE_MB="0$SIZE_MB"
    fi
    MODEL_SIZE="${SIZE_MB}"
fi

# Leer accuracy anterior del log (penúltimo valor único)
if [ -f "$ML_RETRAIN_LOG" ]; then
    # Obtener accuracies únicos en orden
    ALL_ACCURACIES=$(grep "Accuracy:" "$ML_RETRAIN_LOG" | grep -oP '\d+\.\d+' | awk '!seen[$0]++')
    ACCURACY_COUNT=$(echo "$ALL_ACCURACIES" | wc -l)
    if [ "$ACCURACY_COUNT" -ge 2 ]; then
        PREV_ACC_RAW=$(echo "$ALL_ACCURACIES" | tail -2 | head -1)
        CURR_ACC_RAW=$(echo "$ALL_ACCURACIES" | tail -1)
        CURRENT_ACCURACY=$(printf "%.2f%%" "$CURR_ACC_RAW")
        PREV_ACCURACY=$(printf "%.2f%%" "$PREV_ACC_RAW")
    elif [ "$ACCURACY_COUNT" -eq 1 ]; then
        CURR_ACC_RAW=$(echo "$ALL_ACCURACIES" | tail -1)
        CURRENT_ACCURACY=$(printf "%.2f%%" "$CURR_ACC_RAW")
    fi
    # Leer trades (formato: "• Trades usados: 106")
    # Fix: usar grep -oP para extraer solo números y manejar múltiples formatos
    TRADES_USED=$(grep -E "Trades usados:|Trades usados:" "$ML_RETRAIN_LOG" | tail -1 | grep -oP '\d+' | head -1)
    if [ -z "$TRADES_USED" ]; then
        TRADES_USED="N/A"
    fi
    TRADES_NUEVOS=$(grep -E "Trades nuevos:|Trades nuevos:" "$ML_RETRAIN_LOG" | tail -1 | grep -oP '\d+' | head -1)
    if [ -z "$TRADES_NUEVOS" ]; then
        TRADES_NUEVOS="N/A"
    fi
else
    TRADES_USED="N/A"
    TRADES_NUEVOS="N/A"
fi

# Calcular cambio en accuracy
ACCURACY_CHANGE=""
if [ -n "$PREV_ACCURACY" ] && [ "$PREV_ACCURACY" != "N/A" ]; then
    # Remover % para calcular
    PREV_NUM=$(echo "$PREV_ACCURACY" | tr -d '%')
    CURR_NUM=$(echo "$CURRENT_ACCURACY" | tr -d '%')
    DIFF=$(echo "$CURR_NUM - $PREV_NUM" | bc)
    # Formatear DIFF con signo y ceros a la izquierda
    DIFF_FORMATTED=$(printf "%.2f" "$DIFF")
    if (( $(echo "$DIFF > 0" | bc -l) )); then
        ACCURACY_CHANGE="📈 **+${DIFF_FORMATTED}%** vs retrain anterior"
    elif (( $(echo "$DIFF < 0" | bc -l) )); then
        ACCURACY_CHANGE="📉 **${DIFF_FORMATTED}%** vs retrain anterior"
    else
        ACCURACY_CHANGE="➡️ Sin cambio vs retrain anterior"
    fi
fi

# Verificar próximo retrain (domingos 3 AM)
TODAY=$(date +%A)
NEXT_RETRAIN="Domingo 3:00 AM"

# Construir mensaje para Telegram
MESSAGE="🧠 ML VALIDATOR - REPORTE SEMANAL

📅 **Última Ejecución:** $LAST_RETRAIN_DATE $LAST_RETRAIN_TIME
🔄 **Días desde último retrain:** $DAYS_SINCE días

📊 **STATS DEL MODELO:**
├─ Accuracy: ${CURRENT_ACCURACY} $ACCURACY_CHANGE
├─ Trades usados: $TRADES_USED
├─ Trades nuevos: $TRADES_NUEVOS
├─ Total retrainings: $RETRAIN_COUNT
└─ Tamaño modelo: ${MODEL_SIZE} MB

⏰ **Próximo retrain:** $NEXT_RETRAIN

✅ **Status:** OPERATIVO"

# Enviar a Telegram
log "Enviando reporte a Telegram..."

# Leer configuración desde openclaw.json
CONFIG_JSON="/home/overgon/.openclaw/openclaw.json"
TELEGRAM_BOT_TOKEN=$(jq -r '.channels.telegram.botToken // empty' "$CONFIG_JSON" 2>/dev/null)
TELEGRAM_CHAT_ID="7543955537"

if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$TELEGRAM_CHAT_ID" \
        -d "text=$MESSAGE" \
        -d "parse_mode=Markdown" \
        >> "$LOG_FILE" 2>&1
    log "✅ Reporte enviado a Telegram"
else
    log "⚠️ No se encontró TELEGRAM_BOT_TOKEN en openclaw.json"
fi

log "✅ Reporte completado"
log ""
