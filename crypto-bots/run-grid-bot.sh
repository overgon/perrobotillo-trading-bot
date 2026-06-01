#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - GRID TRADING BOT WRAPPER
# ════════════════════════════════════════════════════════
# Wrapper bash para ejecutar Grid Trading Bot
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
VENV_PYTHON="$WORKSPACE/venv/bin/python3"
GRID_SCRIPT="$WORKSPACE/crypto-bots/grid-trading-bot.py"
LOG_FILE="$WORKSPACE/logs/grid-trading.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Verificar virtualenv
if [ ! -f "$VENV_PYTHON" ]; then
    log "❌ Error: Virtualenv no encontrado en $VENV_PYTHON"
    exit 1
fi

# Parsear argumentos
COIN="${1:-BNB}"
HOURS="${2:-24}"
DRY_RUN=""

if [ "$3" == "--dry-run" ]; then
    DRY_RUN="--dry-run"
fi

# Ejecutar bot
log "╔═══════════════════════════════════════════════════════╗"
log "║  🐕 GRID TRADING BOT                                   ║"
log "╚═══════════════════════════════════════════════════════╝"
log "Moneda: $COIN"
log "Duración: $HOURS horas"
log "Dry Run: ${DRY_RUN:-NO}"
log ""

$VENV_PYTHON "$GRID_SCRIPT" --coin "$COIN" --hours "$HOURS" $DRY_RUN 2>&1 | tee -a "$LOG_FILE"

log ""
log "✅ Grid trading completado"
