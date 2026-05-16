#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧠 ML Market Validator - Validación ML para Auto-Adjust
# ════════════════════════════════════════════════════════
# Ejecuta después de auto-adjust-strategy.sh para validar
# Uso: ./ml-market-validator.sh
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
ML_DIR="${WORKSPACE}/ml"
ML_PREDICTIONS="${ML_DIR}/market-predictions.json"
AUTO_CONFIG="${SCRIPT_DIR}/market-mode.conf"
DYNAMIC_CONFIG="${SCRIPT_DIR}/dynamic-config.env"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🧠 ML MARKET VALIDATOR                               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# ════════════════════════════════════════════════════════
# PASO 1: EJECUTAR PREDICCIÓN ML
# ════════════════════════════════════════════════════════

echo "⏳ Paso 1/3: Ejecutando ML classifier..."

# Primero predecir, luego validar
python3 "${ML_DIR}/market-classifier.py" --predict
python3 "${ML_DIR}/market-classifier.py" --validate

if [ ! -f "$ML_PREDICTIONS" ]; then
    echo "❌ Error: ML no generó predicciones"
    exit 1
fi

# ════════════════════════════════════════════════════════
# PASO 2: LEER RESULTADOS
# ════════════════════════════════════════════════════════

echo ""
echo "⏳ Paso 2/3: Analizando resultados..."

# Extraer datos de ML
ML_MODE=$(python3 -c "import json; d=json.load(open('$ML_PREDICTIONS')); print(d.get('recommended_mode', 'UNKNOWN'))")
ML_DISCREPANCY=$(python3 -c "import json; d=json.load(open('$ML_PREDICTIONS')); print('true' if d.get('discrepancy', False) else 'false')")
ML_REASON=$(python3 -c "import json; d=json.load(open('$ML_PREDICTIONS')); print(d.get('reason', ''))")

# Extraer BTC confidence
BTC_CONF=$(python3 -c "import json; d=json.load(open('$ML_PREDICTIONS')); print(f\"{d['predictions'].get('BTC', {}).get('confidence', 0)*100:.0f}%\")")

# Leer Auto-Adjust
if [ -f "$AUTO_CONFIG" ]; then
    AUTO_MODE=$(grep "^MARKET_MODE=" "$AUTO_CONFIG" | cut -d'=' -f2 | tr -d '"')
else
    AUTO_MODE="UNKNOWN"
fi

echo "   Auto-Adjust: $AUTO_MODE"
echo "   ML Recommended: $ML_MODE"
echo "   BTC Confidence: $BTC_CONF"
echo "   Discrepancy: $ML_DISCREPANCY"
[ -n "$ML_REASON" ] && echo "   Reason: $ML_REASON"

# ════════════════════════════════════════════════════════
# PASO 3: ACTUALIZAR CONFIGURACIÓN SI HAY DISCREPANCIA
# ════════════════════════════════════════════════════════

echo ""
echo "⏳ Paso 3/3: Aplicando validación..."

if [ "$ML_DISCREPANCY" = "true" ]; then
    # Hay discrepancia - verificar si ML tiene alta confianza
    BTC_CONF_NUM=$(python3 -c "import json; d=json.load(open('$ML_PREDICTIONS')); print(int(d['predictions'].get('BTC', {}).get('confidence', 0)*100))")
    
    if [ "$BTC_CONF_NUM" -gt 80 ]; then
        echo "⚠️ DISCREPANCIA: ML tiene >80% confianza"
        echo "   Actualizando MARKET_MODE de $AUTO_MODE → $ML_MODE"
        
        # Actualizar dynamic-config.env con ML mode
        if [ -f "$DYNAMIC_CONFIG" ]; then
            # Reemplazar MARKET_MODE
            sed -i "s/^export MARKET_MODE=.*/export MARKET_MODE=\"$ML_MODE\"/" "$DYNAMIC_CONFIG"
            
            # Agregar nota de ML override
            echo "" >> "$DYNAMIC_CONFIG"
            echo "# ML Override: $ML_REASON" >> "$DYNAMIC_CONFIG"
            echo "# ML Confidence: $BTC_CONF" >> "$DYNAMIC_CONFIG"
        fi
        
        echo "✅ Configuración actualizada con ML override"
        
        # Notificar por Telegram
        if [ -f "${WORKSPACE}/lib/send-telegram.sh" ]; then
            source "${WORKSPACE}/lib/send-telegram.sh"
            send_telegram "⚠️ ML VALIDATION OVERRIDE

🤖 Auto-Adjust: $AUTO_MODE
🧠 ML Classifier: $ML_MODE
📊 BTC Confidence: $BTC_CONF

Motivo: $ML_REASON

✅ Usando ML prediction por alta confianza"
        fi
    else
        echo "⚠️ DISCREPANCIA: ML tiene <80% confianza"
        echo "   Manteniendo Auto-Adjust ($AUTO_MODE) por seguridad"
        
        # Notificar discrepancia de baja confianza
        if [ -f "${WORKSPACE}/lib/send-telegram.sh" ]; then
            source "${WORKSPACE}/lib/send-telegram.sh"
            send_telegram "⚠️ ML VALIDATION - DISCREPANCIA

🤖 Auto-Adjust: $AUTO_MODE
🧠 ML Classifier: $ML_MODE
📊 BTC Confidence: $BTC_CONF

Manteniendo Auto-Adjust por baja confianza ML"
        fi
    fi
else
    echo "✅ ACUERDO: ML y Auto-Adjust coinciden en $ML_MODE"
    echo "   Sin cambios necesarios"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ ML VALIDATION COMPLETED                           ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

exit 0
