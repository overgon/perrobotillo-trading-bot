#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧠 Auto-Adjust Strategy Engine
# ════════════════════════════════════════════════════════
# Aplica la configuración dinámica al bot de trading
# Uso: ./auto-adjust-strategy.sh
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
CONFIG_FILE="${SCRIPT_DIR}/market-mode.conf"
BOT_SCRIPT="${SCRIPT_DIR}/crypto-trade-moneda-v3-slots.sh"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🧠 AUTO-ADJUST STRATEGY ENGINE                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# ════════════════════════════════════════════════════════
# PASO 1: EJECUTAR ANÁLISIS DE MERCADO
# ════════════════════════════════════════════════════════

echo "⏳ Paso 1/3: Analizando mercado..."
"${SCRIPT_DIR}/market-sentiment.sh"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: No se generó el archivo de configuración"
    exit 1
fi

# Cargar configuración
source "$CONFIG_FILE"

echo ""
echo "✅ Mercado analizado: ${MARKET_MODE}"
echo ""

# ════════════════════════════════════════════════════════
# PASO 2: ACTUALIZAR CONFIGURACIÓN DEL BOT
# ════════════════════════════════════════════════════════

echo "⏳ Paso 2/3: Actualizando configuración del bot..."

# Obtener Fear & Greed Index de Alternative.me
echo "   📊 Obteniendo Fear & Greed Index..."
FG_DATA=$(curl -s "https://api.alternative.me/fng/" 2>/dev/null)
FG_VALUE=$(echo "$FG_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['value'])" 2>/dev/null || echo "N/A")
FG_CLASS=$(echo "$FG_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin)['data'][0]['value_classification'])" 2>/dev/null || echo "N/A")
echo "   ✅ F&G: ${FG_VALUE} (${FG_CLASS})"

# Crear archivo de configuración dinámica
DYNAMIC_CONFIG="${SCRIPT_DIR}/dynamic-config.env"

cat > "$DYNAMIC_CONFIG" << EOF
# Dynamic Strategy Configuration
# Generated: $(date '+%Y-%m-%d %H:%M:%S')
# Market Mode: ${MARKET_MODE}

# Auto-Adjusted Parameters
export TP1=${TP1}
export TP2=${TP2}
export TP3=${TP3}
export STOP_LOSS=${SL}
export POSITION_SIZE=${POSITION_SIZE}
export TRAILING_STOP=${TRAILING_STOP}

# Scalping Mode (Lateral Market)
export SCALPING_ENABLED="true"
export SCALP_TARGET_PERCENT="1.0"
export SCALP_SL_PERCENT="2.5"

# Market Context
export MARKET_MODE="${MARKET_MODE}"
export MARKET_REASON="${MARKET_REASON}"
export BTC_PRICE="${BTC_PRICE}"
export RSI="${RSI}"
export FG_VALUE="${FG_VALUE}"
EOF

echo "✅ Configuración dinámica guardada: ${DYNAMIC_CONFIG}"
echo ""

# ════════════════════════════════════════════════════════
# PASO 3: NOTIFICAR CAMBIOS
# ════════════════════════════════════════════════════════

echo "⏳ Paso 3/3: Notificando cambios..."

# Enviar resumen por Telegram (formato compacto)
if [ -f "${WORKSPACE}/lib/send-telegram.sh" ]; then
    source "${WORKSPACE}/lib/send-telegram.sh"
    send_telegram "🧠 AUTO-ADJUST STRATEGY

🎯 Modo: ${MARKET_MODE}
📝 Razón: ${MARKET_REASON}

⚙️ TP1/2/3: +${TP1}/${TP2}/${TP3}% | SL: -${SL}%
💰 Position: ${POSITION_SIZE}%

📊 BTC: \$${BTC_PRICE} | RSI: ${RSI} | F&G: ${FG_VALUE} (${FG_CLASS})

✅ Estrategia ajustada"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ AUTO-ADJUST COMPLETED                             ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "📁 Configuración en: ${DYNAMIC_CONFIG}"
echo ""
echo "🔄 El bot usará esta configuración en la próxima ejecución"
echo ""

# ════════════════════════════════════════════════════════
# PASO 4: VALIDACIÓN ML (NUEVO)
# ════════════════════════════════════════════════════════

echo "⏳ Paso 4/4: Ejecutando ML validation..."
"${SCRIPT_DIR}/ml-market-validator.sh"

# ════════════════════════════════════════════════════════
# PASO 5: NOTIFICAR + APLICAR OVERRIDE (DESPUÉS DE ML VALIDATION)
# ════════════════════════════════════════════════════════

# Leer resultado de ML validation
ML_RESULT_FILE="${SCRIPT_DIR}/../ml/market-predictions.json"
if [ -f "$ML_RESULT_FILE" ]; then
    ML_DISCREPANCY=$(python3 -c "import json; d=json.load(open('$ML_RESULT_FILE')); print('true' if d.get('discrepancy', False) else 'false')")
    ML_MODE=$(python3 -c "import json; d=json.load(open('$ML_RESULT_FILE')); print(d.get('recommended_mode', 'UNKNOWN'))")
    ML_CONFIDENCE=$(python3 -c "import json; d=json.load(open('$ML_RESULT_FILE')); print(f\"{d['predictions'].get('BTC', {}).get('confidence', 0)*100:.0f}%\")")
    ML_CONF_NUM=$(python3 -c "import json; d=json.load(open('$ML_RESULT_FILE')); print(int(d['predictions'].get('BTC', {}).get('confidence', 0)*100))")
    
    # Determinar modo final y aplicar override si corresponde
    if [ "$ML_DISCREPANCY" = "true" ] && [ "$ML_CONF_NUM" -gt 80 ]; then
        FINAL_MODE="$ML_MODE"
        OVERRIDE="✅ ML override aplicado"
        
        # Aplicar override en dynamic-config.env
        if [ -f "$DYNAMIC_CONFIG" ]; then
            sed -i "s/^export MARKET_MODE=.*/export MARKET_MODE=\"$FINAL_MODE\"/" "$DYNAMIC_CONFIG"
            echo "" >> "$DYNAMIC_CONFIG"
            echo "# ML Override: $(python3 -c "import json; d=json.load(open('$ML_RESULT_FILE')); print(d.get('reason', ''))")" >> "$DYNAMIC_CONFIG"
            echo "# ML Confidence: $ML_CONFIDENCE" >> "$DYNAMIC_CONFIG"
        fi
    else
        FINAL_MODE="$AUTO_MODE"
        OVERRIDE="✅ ML de acuerdo"
    fi
    
    # Notificar resultado final (formato compacto)
    if [ -f "${WORKSPACE}/lib/send-telegram.sh" ]; then
        source "${WORKSPACE}/lib/send-telegram.sh"
        send_telegram "🧠 AUTO-ADJUST + ML VALIDATION

🎯 Modo: ${FINAL_MODE} | ${OVERRIDE}
📝 Razón: ${MARKET_REASON}

⚙️ TP1/2/3: +${TP1}/${TP2}/${TP3}% | SL: -${SL}%
💰 Position: ${POSITION_SIZE}%

📊 BTC: \$${BTC_PRICE} | RSI: ${RSI} | F&G: ${FG_VALUE} (${FG_CLASS})
🤖 ML: ${ML_CONFIDENCE}

✅ Estrategia validada"
    fi
else
    # Fallback: notificar sin ML (formato compacto)
    if [ -f "${WORKSPACE}/lib/send-telegram.sh" ]; then
        source "${WORKSPACE}/lib/send-telegram.sh"
        send_telegram "🧠 AUTO-ADJUST STRATEGY

🎯 Modo: ${MARKET_MODE}
📝 Razón: ${MARKET_REASON}

⚙️ TP1/2/3: +${TP1}/${TP2}/${TP3}% | SL: -${SL}%
💰 Position: ${POSITION_SIZE}%

📊 BTC: \$${BTC_PRICE} | RSI: ${RSI} | F&G: ${FG_VALUE} (${FG_CLASS})

✅ Estrategia ajustada"
    fi
fi

exit 0
