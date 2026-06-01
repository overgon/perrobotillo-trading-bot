#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - BACKTEST WRAPPER
# ════════════════════════════════════════════════════════
# Wrapper bash para el motor de backtesting
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
VENV_PYTHON="$WORKSPACE/venv/bin/python3"
BACKTEST_SCRIPT="$WORKSPACE/backtest/backtest_engine.py"
LOG_FILE="$WORKSPACE/logs/backtest.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Verificar virtualenv
if [ ! -f "$VENV_PYTHON" ]; then
    log "❌ Error: Virtualenv no encontrado en $VENV_PYTHON"
    echo "Creando virtualenv..."
    cd "$WORKSPACE"
    python3 -m venv venv
    source venv/bin/activate
    pip install ccxt pandas numpy talib scikit-learn >/dev/null 2>&1
fi

# Ejecutar backtest
log "╔═══════════════════════════════════════════════════════╗"
log "║  🐕 PERROBOTILLO BACKTEST ENGINE                      ║"
log "╚═══════════════════════════════════════════════════════╝"

if [ "$1" == "--all" ]; then
    log "📊 Ejecutando backtest para TODAS las monedas..."
    $VENV_PYTHON "$BACKTEST_SCRIPT" --all --timeframe "${2:-5m}" --days "${3:-30}" 2>&1 | tee -a "$LOG_FILE"
elif [ -n "$1" ]; then
    log "📊 Ejecutando backtest para $1..."
    $VENV_PYTHON "$BACKTEST_SCRIPT" --coin "$1" --timeframe "${2:-5m}" --days "${3:-30}" 2>&1 | tee -a "$LOG_FILE"
else
    echo "Uso: $0 [--all|<COIN>] [timeframe] [days]"
    echo ""
    echo "Ejemplos:"
    echo "  $0 BTC              # Backtest BTC (5m, 30 días)"
    echo "  $0 ETH 1h 60        # Backtest ETH (1h, 60 días)"
    echo "  $0 --all 15m 90     # Backtest todas las monedas (15m, 90 días)"
    echo ""
    echo "Monedas disponibles: BTC ETH BNB SOL LINK XRP AVAX"
fi

log "✅ Backtest completado"
