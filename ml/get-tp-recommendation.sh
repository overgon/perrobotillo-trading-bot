#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 Perrobotillo ML - TP Recommendation Getter
# ════════════════════════════════════════════════════════
# Obtiene recomendación de TP para una moneda específica
# Uso: ./get-tp-recommendation.sh BTC
# Output: TP1|TP2|TP3 (ej: 4.0|8.0|15.0)
# ════════════════════════════════════════════════════════

COIN="${1:-BTC}"
RECOMMENDATIONS_FILE="/home/overgon/.openclaw/workspace/ml/tp-recommendations.json"
PREDICTIONS_FILE="/home/overgon/.openclaw/workspace/ml/tp-predictions.json"
LOG_FILE="/home/overgon/.openclaw/logs/ml-integration.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Verificar si existe el archivo de recomendaciones
if [ ! -f "$RECOMMENDATIONS_FILE" ]; then
    log "⚠️  No hay recomendaciones, ejecutando predict-tp.py..."
    python3 /home/overgon/.openclaw/workspace/ml/predict-tp.py > /dev/null 2>&1
fi

# Leer recomendaciones para la coin
if [ -f "$RECOMMENDATIONS_FILE" ]; then
    # Extraer recomendación usando jq
    tp1=$(jq -r ".recommendations.${COIN}.tp1_pct // empty" "$RECOMMENDATIONS_FILE" 2>/dev/null)
    tp2=$(jq -r ".recommendations.${COIN}.tp2_pct // empty" "$RECOMMENDATIONS_FILE" 2>/dev/null)
    tp3=$(jq -r ".recommendations.${COIN}.tp3_pct // empty" "$RECOMMENDATIONS_FILE" 2>/dev/null)
    action=$(jq -r ".recommendations.${COIN}.action // empty" "$RECOMMENDATIONS_FILE" 2>/dev/null)
    
    if [ -n "$tp1" ] && [ "$tp1" != "null" ]; then
        log "✅ $COIN: TP1=$tp1% TP2=$tp2% TP3=$tp3% ($action)"
        echo "$tp1|$tp2|$tp3"
        exit 0
    else
        log "⚠️  No hay recomendación para $COIN, usando defaults"
    fi
fi

# Fallback: TPs por defecto (FASE 1 v2.1)
log "📌 $COIN: Usando TPs por defecto (3.5|7.0|12.0)"
echo "3.5|7.0|12.0"
