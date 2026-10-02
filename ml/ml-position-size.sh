#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧠 ML Position Size Recommender
# ════════════════════════════════════════════════════════
# Obtiene recomendación de position size desde ML
# Uso: ./ml-position-size.sh [SYMBOL]
# Output: POSITION_SIZE (25, 40, o 50)
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
ML_DIR="${WORKSPACE}/ml"
RECOMMENDATIONS_FILE="${ML_DIR}/position-size-recommendations.json"

SYMBOL="${1:-BTC}"

# Ejecutar predictor
python3 "${ML_DIR}/position-size-optimizer.py" --predict "$SYMBOL" > /dev/null 2>&1

# Leer recomendación
if [ -f "$RECOMMENDATIONS_FILE" ]; then
    POSITION_SIZE=$(python3 -c "import json; d=json.load(open('$RECOMMENDATIONS_FILE')); print(d['recommendations'].get('$SYMBOL', {}).get('position_size', 40))")
    CONFIDENCE=$(python3 -c "import json; d=json.load(open('$RECOMMENDATIONS_FILE')); print(d['recommendations'].get('$SYMBOL', {}).get('confidence', 0))")
    RECOMMENDATION=$(python3 -c "import json; d=json.load(open('$RECOMMENDATIONS_FILE')); print(d['recommendations'].get('$SYMBOL', {}).get('recommendation', 'MEDIUM'))")
    
    echo "$POSITION_SIZE"
else
    echo "40"  # Default
fi
