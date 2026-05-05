#!/bin/bash
# ════════════════════════════════════════════════════════
# 📊 Market Sentiment Analyzer
# ════════════════════════════════════════════════════════
# Detecta el estado del mercado y guarda la configuración
# Uso: ./market-sentiment.sh
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
CONFIG_FILE="${SCRIPT_DIR}/market-mode.conf"

# Crear directorio de estado
mkdir -p "${SCRIPT_DIR}/state"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  📊 MARKET SENTIMENT ANALYZER                         ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# ════════════════════════════════════════════════════════
# OBTENER DATOS DEL MERCADO
# ════════════════════════════════════════════════════════

echo "⏳ Obteniendo datos del mercado..."

# Obtener precios y datos de BTC desde Binance
BTC_DATA=$(curl -s --max-time 10 "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT")

if [ -z "$BTC_DATA" ]; then
    echo "❌ Error: No se pudo obtener datos de Binance"
    exit 1
fi

# Extraer datos
BTC_PRICE=$(echo "$BTC_DATA" | grep -o '"lastPrice":"[^"]*"' | cut -d'"' -f4)
BTC_CHANGE=$(echo "$BTC_DATA" | grep -o '"priceChangePercent":"[^"]*"' | cut -d'"' -f4)
BTC_VOLUME=$(echo "$BTC_DATA" | grep -o '"volume":"[^"]*"' | cut -d'"' -f4)

# Obtener Fear & Greed (API alternativa)
FG_DATA=$(curl -s --max-time 5 "https://api.alternative.me/fng/?limit=1&format=json" 2>/dev/null)

if [ -n "$FG_DATA" ]; then
    FG_VALUE=$(echo "$FG_DATA" | grep -o '"value":"[0-9]*"' | head -1 | cut -d'"' -f4)
    FG_CLASS=$(echo "$FG_DATA" | grep -o '"value_classification":"[^"]*"' | head -1 | cut -d'"' -f4)
else
    # Fallback: usar valor neutral
    FG_VALUE=50
    FG_CLASS="Neutral"
fi

# Obtener EMA20 y EMA50 (calculado simple con últimos 50 días)
echo "   Calculando EMAs..."
EMA_DATA=$(curl -s --max-time 10 "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=50")

if [ -n "$EMA_DATA" ]; then
    # Calcular EMA20 y EMA50 con Python
    read EMA20 EMA50 <<< $(python3 << PYEOF
import json
import sys

data = json.loads('''$EMA_DATA''')
closes = [float(k[4]) for k in data]

# EMA20
ema20 = sum(closes[:20]) / 20
for i in range(20, len(closes)):
    ema20 = (closes[i] * (2/21)) + (ema20 * (19/21))

# EMA50
ema50 = sum(closes[:50]) / 50 if len(closes) >= 50 else ema20
for i in range(50, len(closes)):
    ema50 = (closes[i] * (2/51)) + (ema50 * (49/51))

print(f"{ema20:.2f} {ema50:.2f}")
PYEOF
)
else
    EMA20=$BTC_PRICE
    EMA50=$BTC_PRICE
fi

# Calcular RSI (14 días)
echo "   Calculando RSI..."
RSI_DATA=$(curl -s --max-time 10 "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=20")

if [ -n "$RSI_DATA" ]; then
    RSI=$(python3 << PYEOF
import json

data = json.loads('''$RSI_DATA''')
closes = [float(k[4]) for k in data]

if len(closes) < 15:
    print(50)
    exit()

# Calcular RSI
gains = []
losses = []
for i in range(1, len(closes)):
    change = closes[i] - closes[i-1]
    if change > 0:
        gains.append(change)
        losses.append(0)
    else:
        gains.append(0)
        losses.append(abs(change))

# Promedio de 14 días
avg_gain = sum(gains[-14:]) / 14
avg_loss = sum(losses[-14:]) / 14

if avg_loss == 0:
    print(100)
else:
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    print(f"{rsi:.2f}")
PYEOF
)
else
    RSI=50
fi

echo ""
echo "📊 DATOS DEL MERCADO:"
echo "   Precio BTC: \$${BTC_PRICE}"
echo "   24h Change: ${BTC_CHANGE}%"
echo "   Fear & Greed: ${FG_VALUE} (${FG_CLASS})"
echo "   EMA20: \$${EMA20}"
echo "   EMA50: \$${EMA50}"
echo "   RSI: ${RSI}"
echo ""

# ════════════════════════════════════════════════════════
# DETERMINAR MODO DE MERCADO
# ════════════════════════════════════════════════════════

echo "🔍 Analizando modo de mercado..."

# Convertir a float para comparaciones
BTC_PRICE_F=$(echo "$BTC_PRICE" | sed 's/[^0-9.]//g')
EMA20_F=$(echo "$EMA20" | sed 's/[^0-9.]//g')
FG_VALUE_F=$(echo "$FG_VALUE" | sed 's/[^0-9.]//g')
RSI_F=$(echo "$RSI" | sed 's/[^0-9.]//g')

# Determinar modo
MARKET_MODE="LATERAL"
MARKET_REASON="RSI neutral, precio entre EMAs"

# Bear Market: FG < 40 Y precio < EMA20
if [ "$FG_VALUE_F" -lt 40 ] 2>/dev/null && [ "$(echo "$BTC_PRICE_F < $EMA20_F" | bc -l 2>/dev/null)" = "1" ]; then
    MARKET_MODE="BEAR"
    MARKET_REASON="Fear & Greed < 40 + Precio < EMA20"
    
# Bull Market: FG > 60 Y precio > EMA20
elif [ "$FG_VALUE_F" -gt 60 ] 2>/dev/null && [ "$(echo "$BTC_PRICE_F > $EMA20_F" | bc -l 2>/dev/null)" = "1" ]; then
    MARKET_MODE="BULL"
    MARKET_REASON="Fear & Greed > 60 + Precio > EMA20"
    
# Alta Volatilidad: RSI > 70 o RSI < 30
elif [ "$(echo "$RSI_F > 70" | bc -l 2>/dev/null)" = "1" ]; then
    MARKET_MODE="VOLATILE_BULL"
    MARKET_REASON="RSI > 70 (sobrecompra)"
    
elif [ "$(echo "$RSI_F < 30" | bc -l 2>/dev/null)" = "1" ]; then
    MARKET_MODE="VOLATILE_BEAR"
    MARKET_REASON="RSI < 30 (sobreventa)"
fi

echo "   🎯 MODO DETECTADO: ${MARKET_MODE}"
echo "   📝 Razón: ${MARKET_REASON}"
echo ""

# ════════════════════════════════════════════════════════
# GUARDAR CONFIGURACIÓN
# ════════════════════════════════════════════════════════

# Configurar parámetros según modo
case $MARKET_MODE in
    "BULL")
        TP1=3.0
        TP2=6.0
        TP3=10.0
        SL=8.0
        POSITION_SIZE=25
        TRAILING="true"
        ;;
    "BEAR")
        TP1=2.0
        TP2=4.0
        TP3=6.0
        SL=4.0
        POSITION_SIZE=15
        TRAILING="false"
        ;;
    "VOLATILE_BULL")
        TP1=3.5
        TP2=7.0
        TP3=12.0
        SL=10.0
        POSITION_SIZE=20
        TRAILING="true"
        ;;
    "VOLATILE_BEAR")
        TP1=2.0
        TP2=4.0
        TP3=6.0
        SL=5.0
        POSITION_SIZE=15
        TRAILING="false"
        ;;
    *)  # LATERAL (default)
        TP1=2.5
        TP2=5.0
        TP3=7.0
        SL=5.0
        POSITION_SIZE=20
        TRAILING="false"
        ;;
esac

# Guardar configuración
cat > "$CONFIG_FILE" << EOF
# Market Mode Configuration
# Generated: $(date '+%Y-%m-%d %H:%M:%S')

MARKET_MODE="${MARKET_MODE}"
MARKET_REASON="${MARKET_REASON}"

# Trading Parameters
TP1=${TP1}
TP2=${TP2}
TP3=${TP3}
SL=${SL}
POSITION_SIZE=${POSITION_SIZE}
TRAILING_STOP=${TRAILING}

# Market Data
BTC_PRICE=${BTC_PRICE}
BTC_CHANGE=${BTC_CHANGE}
FG_VALUE=${FG_VALUE}
FG_CLASS="${FG_CLASS}"
EMA20=${EMA20}
EMA50=${EMA50}
RSI=${RSI}

# Timestamp
LAST_UPDATE=$(date +%s)
EOF

echo "✅ Configuración guardada en: ${CONFIG_FILE}"
echo ""

# ════════════════════════════════════════════════════════
# MOSTRAR RESUMEN
# ════════════════════════════════════════════════════════

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🎯 CONFIGURACIÓN APLICADA                            ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "   Modo: ${MARKET_MODE}"
echo ""
echo "   TP1: +${TP1}%"
echo "   TP2: +${TP2}%"
echo "   TP3: +${TP3}%"
echo "   SL: -${SL}%"
echo "   Position Size: ${POSITION_SIZE}%"
echo "   Trailing Stop: ${TRAILING}"
echo ""
echo "✅ Market sentiment analysis completed"

# Enviar alerta por Telegram si cambió el modo
STATE_FILE="${SCRIPT_DIR}/state/last-market-mode.txt"
LAST_MODE=""
if [ -f "$STATE_FILE" ]; then
    LAST_MODE=$(cat "$STATE_FILE")
fi

if [ "$LAST_MODE" != "$MARKET_MODE" ] && [ -n "$LAST_MODE" ]; then
    echo ""
    echo "⚠️  CAMBIO DE MODO DETECTADO: ${LAST_MODE} → ${MARKET_MODE}"
    
    # Enviar alerta por Telegram
    if [ -f "${WORKSPACE}/lib/send-telegram.sh" ]; then
        source "${WORKSPACE}/lib/send-telegram.sh"
        send_telegram "🚨 CAMBIO DE MODO DE MERCADO

De: ${LAST_MODE}
A: ${MARKET_MODE}

Razón: ${MARKET_REASON}

Nueva configuración:
TP1: +${TP1}%
TP2: +${TP2}%
TP3: +${TP3}%
SL: -${SL}%
Position: ${POSITION_SIZE}%"
    fi
fi

# Guardar modo actual
echo "$MARKET_MODE" > "$STATE_FILE"

exit 0
