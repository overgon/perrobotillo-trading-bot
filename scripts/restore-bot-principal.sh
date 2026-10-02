#!/bin/bash
# ════════════════════════════════════════════════════════
# 🛡️ RESTORE BOT PRINCIPAL - DESACTIVAR GRID TRADING
# ════════════════════════════════════════════════════════
# Script de emergencia para volver al sistema por slots
# SOLO USAR SI EL JEFE LO SOLICITA EXPLÍCITAMENTE
# ════════════════════════════════════════════════════════

WORKSPACE="$HOME/.openclaw/workspace"
LOG_FILE="$WORKSPACE/logs/restore-bot-principal.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

confirm() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║  ⚠️  RESTAURACIÓN DEL BOT PRINCIPAL                  ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo ""
    echo "Esto hará:"
    echo "  1. Detener todos los bots de Grid Trading"
    echo "  2. Revertir config de grid-trading-bot.py"
    echo "  3. Reactivar el sistema por slots (21 slots)"
    echo ""
    read -p "¿Confirmar restauración? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log "❌ Restauración cancelada por el usuario"
        exit 1
    fi
}

# ════════════════════════════════════════════════════════
# PASO 1: DETENER GRID TRADING BOTS
# ════════════════════════════════════════════════════════

stop_grid_bots() {
    log "🛑 Deteniendo Grid Trading Bots..."
    
    pkill -f "grid-trading-bot.py"
    sleep 3
    
    if pgrep -f "grid-trading-bot.py" > /dev/null; then
        log "❌ Error: Algunos bots no se detuvieron"
        pkill -9 -f "grid-trading-bot.py"
    else
        log "✅ Todos los Grid Trading Bots detenidos"
    fi
}

# ════════════════════════════════════════════════════════
# PASO 2: REVERTIR CONFIGURACIÓN DE GRID
# ════════════════════════════════════════════════════════

revert_grid_config() {
    log "🔄 Revertiendo configuración de grid-trading-bot.py..."
    
    cd "$WORKSPACE/crypto-bots"
    
    # Backup del estado actual antes de revertir
    cp grid-trading-bot.py grid-trading-bot.py.grid-backup
    
    # Revertir BTC a disabled
    sed -i 's/"BTC": {$/"BTC": {\n        "enabled": False,  # Asignado al Bot Principal (Trend + ML)/' grid-trading-bot.py
    sed -i 's/"low_price": 63000,   # Actualizado: BTC ~\$66,660/"low_price": 70000,\n        "high_price": 80000,\n        "note": "Operado por Bot Principal - evitar duplicación"\n    },\n    "ETH_OLD": {/' grid-trading-bot.py
    
    log "⚠️  Configuración revertida parcialmente - revisar manualmente"
    log "📝 Archivo backup: grid-trading-bot.py.grid-backup"
}

# ════════════════════════════════════════════════════════
# PASO 3: VERIFICAR SISTEMA POR SLOTS
# ════════════════════════════════════════════════════════

verify_slot_system() {
    log "🔍 Verificando sistema por slots..."
    
    if [ -f "$WORKSPACE/crypto-bots/slot-health-manager.py" ]; then
        log "✅ slot-health-manager.py existe"
    else
        log "❌ ERROR: slot-health-manager.py no encontrado"
        exit 1
    fi
    
    if [ -f "$WORKSPACE/scripts/ml-market-validator.sh" ]; then
        log "✅ ml-market-validator.sh existe"
    else
        log "❌ ERROR: ml-market-validator.sh no encontrado"
        exit 1
    fi
    
    if [ -f "$WORKSPACE/scripts/auto-capital-manager.sh" ]; then
        log "✅ auto-capital-manager.sh existe"
    else
        log "❌ ERROR: auto-capital-manager.sh no encontrado"
        exit 1
    fi
}

# ════════════════════════════════════════════════════════
# PASO 4: REINICIAR SISTEMA PRINCIPAL
# ════════════════════════════════════════════════════════

start_principal_bot() {
    log "🚀 Iniciando Bot Principal por Slots..."
    
    # Aquí iría el comando para iniciar el bot principal
    # Ejemplo:
    # nohup venv/bin/python3 crypto-bots/slot-health-manager.py >> logs/bot-principal.log 2>&1 &
    
    log "⚠️  Iniciar el bot principal manualmente según tu configuración"
}

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🛡️  RESTORE BOT PRINCIPAL - GRID → SLOTS           ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

confirm

log "═══════════════════════════════════════════════════════"
log "INICIANDO RESTAURACIÓN"
log "═══════════════════════════════════════════════════════"

stop_grid_bots
revert_grid_config
verify_slot_system
start_principal_bot

log "═══════════════════════════════════════════════════════"
log "RESTAURACIÓN COMPLETADA"
log "═══════════════════════════════════════════════════════"

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ RESTAURACIÓN COMPLETADA                          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "Próximos pasos:"
echo "  1. Revisar logs/restore-bot-principal.log"
echo "  2. Verificar configuración en grid-trading-bot.py"
echo "  3. Iniciar bot principal manualmente si es necesario"
echo ""
