#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - UPDATE TRAILING STOPS CACHE
# ════════════════════════════════════════════════════════
# Actualiza cache de trailing stops ATR para todas las monedas
# Para usar con cron cada 1-2 horas
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
VENV_PYTHON="$WORKSPACE/venv/bin/python3"
TRAILING_SCRIPT="$WORKSPACE/scripts/trailing-stop-atr.py"
LOG_FILE="$WORKSPACE/logs/trailing-stops-update.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "╔═══════════════════════════════════════════════════════╗"
log "║  🎯 ACTUALIZANDO TRAILING STOPS ATR                  ║"
log "╚═══════════════════════════════════════════════════════╝"

# Verificar virtualenv
if [ ! -f "$VENV_PYTHON" ]; then
    log "❌ Error: Virtualenv no encontrado en $VENV_PYTHON"
    exit 1
fi

# Ejecutar cálculo para todas las monedas
$VENV_PYTHON "$TRAILING_SCRIPT" --all >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "✅ Trailing stops actualizados exitosamente"
else
    log "❌ Error actualizando trailing stops (exit code: $EXIT_CODE)"
fi

log ""

exit $EXIT_CODE
