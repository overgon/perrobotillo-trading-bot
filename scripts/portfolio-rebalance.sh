#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - PORTFOLIO REBALANCE WRAPPER
# ════════════════════════════════════════════════════════
# Wrapper bash para Portfolio Rebalancing Bot
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
VENV_PYTHON="$WORKSPACE/venv/bin/python3"
REBALANCE_SCRIPT="$WORKSPACE/scripts/portfolio-rebalance.py"
LOG_FILE="$WORKSPACE/logs/portfolio-rebalance.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Verificar virtualenv
if [ ! -f "$VENV_PYTHON" ]; then
    log "❌ Error: Virtualenv no encontrado en $VENV_PYTHON"
    exit 1
fi

# Parsear argumentos
MODE="${1:-status}"

case $MODE in
    status)
        log "╔═══════════════════════════════════════════════════════╗"
        log "║  📊 PORTFOLIO STATUS                                  ║"
        log "╚═══════════════════════════════════════════════════════╝"
        $VENV_PYTHON "$REBALANCE_SCRIPT" --status 2>&1 | tee -a "$LOG_FILE"
        ;;
    
    rebalance)
        DRY_RUN=""
        if [ "$2" == "--live" ]; then
            DRY_RUN="--live"
            log "⚠️  MODO LIVE - Trades reales se ejecutarán"
        else
            log "🧪 MODO DRY RUN - Solo simulación"
        fi
        
        log "╔═══════════════════════════════════════════════════════╗"
        log "║  🔄 PORTFOLIO REBALANCING                             ║"
        log "╚═══════════════════════════════════════════════════════╝"
        
        $VENV_PYTHON "$REBALANCE_SCRIPT" --rebalance $DRY_RUN 2>&1 | tee -a "$LOG_FILE"
        
        EXIT_CODE=${PIPESTATUS[1]}
        
        if [ $EXIT_CODE -eq 0 ]; then
            log "✅ Rebalanceo completado"
        else
            log "❌ Error en rebalanceo"
        fi
        
        exit $EXIT_CODE
        ;;
    
    *)
        echo "Uso: $0 {status|rebalance [--live]}"
        echo ""
        echo "Comandos:"
        echo "  status     - Mostrar estado actual del portfolio"
        echo "  rebalance  - Ejecutar rebalanceo (dry-run por defecto)"
        echo "  rebalance --live - Ejecutar rebalanceo con trades reales"
        echo ""
        echo "Ejemplos:"
        echo "  $0 status"
        echo "  $0 rebalance"
        echo "  $0 rebalance --live"
        exit 1
        ;;
esac
