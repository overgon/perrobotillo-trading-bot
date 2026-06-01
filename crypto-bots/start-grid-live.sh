#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - START GRID LIVE TRADING
# ════════════════════════════════════════════════════════
# Inicia Grid Trading Bot para monedas asignadas:
# BNB, XRP, AVAX (exclusivo Grid Bot)
# ════════════════════════════════════════════════════════

set -e

WORKSPACE="/home/overgon/.openclaw/workspace"
LOGS_DIR="$WORKSPACE/logs"

# Monedas asignadas al Grid Bot
GRID_COINS=("BNB" "XRP" "AVAX")

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🐕 GRID BOT - STARTING LIVE TRADING                 ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "📊 Monedas asignadas: ${GRID_COINS[*]}"
echo "⏰ Duración: 24 horas"
echo "📁 Logs: $LOGS_DIR/grid-*.log"
echo ""

# Verificar saldo en Binance antes de iniciar
echo "🔍 Verificando saldo en Binance..."
source "$HOME/.openclaw/secrets/binance.env"

BALANCE=$(curl -s -X GET "https://api.binance.com/api/v3/account" \
    -H "X-MBX-APIKEY: $BINANCE_API_KEY" \
    --data-urlencode "timestamp=$(date +%s000)" \
    --data-urlencode "signature=$(echo -n \"timestamp=$(date +%s000)\" | openssl dgst -sha256 -hmac \"$BINANCE_API_SECRET\" | awk '{print $2}')")

USDT_BALANCE=$(echo "$BALANCE" | jq -r '.balances[] | select(.asset=="USDT") | .free')

if [ -z "$USDT_BALANCE" ] || [ "$USDT_BALANCE" == "null" ]; then
    USDT_BALANCE="0.00"
fi

echo "💰 Saldo USDT disponible: \$${USDT_BALANCE}"

if (( $(echo "$USDT_BALANCE < 100" | bc -l) )); then
    echo ""
    echo "⚠️  ADVERTENCIA: Saldo insuficiente (< $100 USDT)"
    echo "   Para operar Grid Bot necesitás al menos $300 USDT"
    echo ""
    echo "   Monedas asignadas y capital recomendado:"
    echo "   - BNB: $100 USDT"
    echo "   - XRP: $100 USDT"
    echo "   - AVAX: $100 USDT"
    echo ""
    read -p "¿Querés continuar igual? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "❌ Cancelado por usuario"
        exit 0
    fi
fi

echo ""
echo "🚀 Iniciando Grid Bot para cada moneda..."
echo ""

# Iniciar un bot por cada moneda en paralelo
for COIN in "${GRID_COINS[@]}"; do
    LOG_FILE="$LOGS_DIR/grid-${COIN}.log"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando ${COIN}..." | tee -a "$LOG_FILE"
    
    # Ejecutar en background
    (
        cd "$WORKSPACE"
        source venv/bin/activate
        python3 crypto-bots/grid-trading-bot.py \
            --coin "$COIN" \
            --hours 24 \
            2>&1 | tee -a "$LOG_FILE"
    ) &
    
    PID=$!
    echo "   ✅ ${COIN} iniciado (PID: $PID)"
done

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ GRID BOTS INICIADOS                               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "📋 Status:"
for COIN in "${GRID_COINS[@]}"; do
    echo "   • ${COIN}: Corriendo (24h)"
done
echo ""
echo "📊 Para ver logs en tiempo real:"
echo "   tail -f $LOGS_DIR/grid-BNB.log"
echo "   tail -f $LOGS_DIR/grid-XRP.log"
echo "   tail -f $LOGS_DIR/grid-AVAX.log"
echo ""
echo "🛑 Para detener todos los grid bots:"
echo "   pkill -f grid-trading-bot.py"
echo ""
echo "⏰ Próximo restart automático: $(date -d '+24 hours' '+%Y-%m-%d %H:%M:%S')"
echo ""
