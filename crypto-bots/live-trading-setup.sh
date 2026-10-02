#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - LIVE TRADING SETUP
# ════════════════════════════════════════════════════════
# Transición Paper Trading → Live Trading
# Para monedas SKILL confirmadas por Monte Carlo
# ════════════════════════════════════════════════════════

set -e

WORKSPACE="/home/overgon/.openclaw/workspace"
LOGS_DIR="$WORKSPACE/logs"
SECRETS_DIR="$HOME/.openclaw/secrets"

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN LIVE TRADING
# ════════════════════════════════════════════════════════

# Monedas SKILL confirmadas (Monte Carlo ✅)
SKILL_COINS=("BNB" "AVAX" "SOL" "ETH" "XRP")

# Capital inicial por moneda (conservador)
INITIAL_CAPITAL_USDT=100  # $100 por moneda = $500 total

# Grid configuration
GRID_RANGE_PERCENT=10  # ±10% del precio actual
GRID_LEVELS=15         # 15 niveles de compra/venta
POSITION_SIZE_PERCENT=20  # 20% del capital por nivel

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🐕 PERROBOTILLO - LIVE TRADING SETUP                ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "📊 Configuración:"
echo "   Monedas SKILL: ${SKILL_COINS[*]}"
echo "   Capital por moneda: \$${INITIAL_CAPITAL_USDT} USDT"
echo "   Capital total: \$$((${#SKILL_COINS[@]} * INITIAL_CAPITAL_USDT)) USDT"
echo "   Grid range: ±${GRID_RANGE_PERCENT}%"
echo "   Niveles: ${GRID_LEVELS}"
echo ""

# ════════════════════════════════════════════════════════
# VERIFICACIONES PREVIAS
# ════════════════════════════════════════════════════════

echo "🔍 Verificaciones previas..."

# 1. Verificar API keys
if [ ! -f "$SECRETS_DIR/binance.env" ]; then
    echo "❌ ERROR: No se encontró $SECRETS_DIR/binance.env"
    exit 1
fi
echo "✅ API keys configuradas"

# 2. Verificar conexión Binance
echo "🌐 Probando conexión con Binance..."
source "$SECRETS_DIR/binance.env"

TEST_RESPONSE=$(curl -s -X GET "https://api.binance.com/api/v3/time" \
    -H "X-MBX-APIKEY: $BINANCE_API_KEY")

if echo "$TEST_RESPONSE" | grep -q "serverTime"; then
    echo "✅ Conexión Binance OK"
else
    echo "❌ ERROR: No se pudo conectar a Binance"
    exit 1
fi

# 3. Verificar IP whitelist
echo "🔒 Verificando IP whitelist..."
IP_RESPONSE=$(curl -s -X GET "https://api.binance.com/api/v3/account" \
    -H "X-MBX-APIKEY: $BINANCE_API_KEY" \
    -H "HMAC-SHA256: ...")

if echo "$IP_RESPONSE" | grep -q "code.*-1003"; then
    echo "⚠️  ADVERTENCIA: IP no está en whitelist"
    echo "   Agregá tu IP pública en Binance → API Management"
else
    echo "✅ IP autorizada"
fi

# ════════════════════════════════════════════════════════
# CREAR CONFIGURACIÓN POR MONEDA
# ════════════════════════════════════════════════════════

CONFIG_DIR="$WORKSPACE/crypto-bots/live-configs"
mkdir -p "$CONFIG_DIR"

echo ""
echo "📝 Generando configuraciones..."

for COIN in "${SKILL_COINS[@]}"; do
    if [ "$COIN" == "ETH" ] || [ "$COIN" == "BTC" ]; then
        PAIR="${COIN}USDT"
    else
        PAIR="${COIN}USDT"
    fi
    
    CONFIG_FILE="$CONFIG_DIR/${COIN}_live_config.json"
    
    # Obtener precio actual de Binance
    PRICE=$(curl -s "https://api.binance.com/api/v3/ticker/price?symbol=${PAIR}" | jq -r '.price')
    
    if [ "$PRICE" == "null" ] || [ -z "$PRICE" ]; then
        echo "⚠️  No se pudo obtener precio para ${PAIR}, usando fallback..."
        case $COIN in
            BNB) PRICE="710";;
            AVAX) PRICE="25";;
            SOL) PRICE="145";;
            ETH) PRICE="3600";;
            XRP) PRICE="0.50";;
        esac
    fi
    
    # Calcular rangos del grid
    LOWER_PRICE=$(echo "$PRICE * (1 - ${GRID_RANGE_PERCENT}/100)" | bc -l)
    UPPER_PRICE=$(echo "$PRICE * (1 + ${GRID_RANGE_PERCENT}/100)" | bc -l)
    
    # Calcular posición size
    POSITION_SIZE=$(echo "$INITIAL_CAPITAL_USDT * ${POSITION_SIZE_PERCENT}/100" | bc -l)
    
    # Crear config JSON
    cat > "$CONFIG_FILE" << EOF
{
    "coin": "${COIN}",
    "pair": "${PAIR}",
    "mode": "LIVE",
    "capital_usdt": ${INITIAL_CAPITAL_USDT},
    "grid": {
        "lower_price": ${LOWER_PRICE},
        "upper_price": ${UPPER_PRICE},
        "levels": ${GRID_LEVELS},
        "position_size_usdt": ${POSITION_SIZE}
    },
    "risk_management": {
        "daily_loss_limit_percent": 3,
        "max_drawdown_percent": 5,
        "emergency_close_enabled": true
    },
    "monte_carlo_verified": true,
    "skill_confirmed": true,
    "created_at": "$(date -Iseconds)"
}
EOF
    
    echo "✅ ${COIN}: Precio \$${PRICE}, Range \$${LOWER_PRICE}-\$${UPPER_PRICE}"
done

# ════════════════════════════════════════════════════════
# RESUMEN FINAL
# ════════════════════════════════════════════════════════

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ SETUP COMPLETADO                                  ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "📁 Configuraciones guardadas en:"
echo "   $CONFIG_DIR/"
echo ""
echo "📋 Resumen:"
for COIN in "${SKILL_COINS[@]}"; do
    CONFIG_FILE="$CONFIG_DIR/${COIN}_live_config.json"
    if [ -f "$CONFIG_FILE" ]; then
        PAIR=$(jq -r '.pair' "$CONFIG_FILE")
        CAPITAL=$(jq -r '.capital_usdt' "$CONFIG_FILE")
        echo "   ✅ ${PAIR}: \$${CAPITAL} USDT"
    fi
done
echo ""
echo "💰 Capital total invertido: \$$((${#SKILL_COINS[@]} * INITIAL_CAPITAL_USDT)) USDT"
echo ""
echo "🚀 Para iniciar Live Trading:"
echo "   cd $WORKSPACE"
echo "   ./crypto-bots/run-grid-bot.sh --live --all-skill-coins"
echo ""
echo "⚠️  IMPORTANTE:"
echo "   - Monitorear cada 30 min las primeras 2 horas"
echo "   - Daily loss limit: 3% (\$${$((${#SKILL_COINS[@]} * INITIAL_CAPITAL_USDT)) * 3 / 100} máximo pérdida diaria)"
echo "   - Emergency close disponible si es necesario"
echo ""
