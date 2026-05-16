#!/bin/bash
# ════════════════════════════════════════════════════════
# 🛡️ ML Drawdown Risk Checker
# ════════════════════════════════════════════════════════
# Obtiene nivel de riesgo desde ML
# Uso: ./ml-drawdown-check.sh [SYMBOL]
# Output: RISK_LEVEL|ACTION|POSITION_SIZE|MESSAGE
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
ML_DIR="${SCRIPT_DIR}"
RECOMMENDATIONS_FILE="${ML_DIR}/drawdown-recommendations.json"

SYMBOL="${1:-BTC}"

# Ejecutar predictor
python3 "${ML_DIR}/drawdown-predictor.py" --predict "$SYMBOL" > /dev/null 2>&1

# Leer recomendación
if [ -f "$RECOMMENDATIONS_FILE" ]; then
    python3 << PYEOF
import json
with open('$RECOMMENDATIONS_FILE', 'r') as f:
    data = json.load(f)
pred = data['predictions'].get('$SYMBOL', {})
risk = pred.get('risk_level', 'LOW_RISK')
action = pred.get('action', 'NORMAL')
pos_size = pred.get('position_size', 40)
msg = pred.get('message', 'Riesgo bajo')
print(f"{risk}|{action}|{pos_size}|{msg}")
PYEOF
else
    echo "LOW_RISK|NORMAL|40|Riesgo bajo"
fi
