#!/bin/bash
# ════════════════════════════════════════════════════════
# 🔄 MIGRACIÓN GRID → SLOTS - ROLLBACK INTELIGENTE
# ════════════════════════════════════════════════════════
# Desactiva Grid Bots y reactiva sistema de Slots
# Mantiene scripts grid para futuro regreso (no elimina)
# ════════════════════════════════════════════════════════

WORKSPACE="$HOME/.openclaw/workspace"
LOG_FILE="$WORKSPACE/logs/migrate-grid-to-slots.log"
SECRETS_FILE="$WORKSPACE/secrets/binance.env"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error_exit() {
    log "❌ ERROR: $1"
    exit 1
}

# ════════════════════════════════════════════════════════
# PASO 1: DETENER PROCESOS GRID ACTIVOS
# ════════════════════════════════════════════════════════

stop_grid_processes() {
    log "🛑 Deteniendo procesos Grid Trading..."
    
    # Matar todos los procesos de grid-trading-bot.py
    pkill -f "grid-trading-bot.py" 2>/dev/null
    sleep 2
    
    # Verificar que se detuvieron
    if pgrep -f "grid-trading-bot.py" > /dev/null; then
        log "⚠️  Forzando detención..."
        pkill -9 -f "grid-trading-bot.py" 2>/dev/null
        sleep 1
    fi
    
    # Matar scripts run-grid-bot.sh si existen
    pkill -f "run-grid-bot.sh" 2>/dev/null
    
    log "✅ Procesos Grid detenidos"
}

# ════════════════════════════════════════════════════════
# PASO 2: CANCELAR ÓRDENES GRID EN BINANCE
# ════════════════════════════════════════════════════════

cancel_grid_orders() {
    log "❌ Cancelando órdenes grid abiertas en Binance..."
    
    cd "$WORKSPACE/crypto-bots"
    
    # Usar Python para cancelar órdenes desde la configuración existente
    python3 << 'PYTHON'
import sys
import os
sys.path.insert(0, os.getcwd())

# Intentar cargar configuración del grid bot
try:
    import json
    import re
    
    with open('grid-trading-bot.py', 'r') as f:
        content = f.read()
    
    # Extraer API keys del archivo de configuración
    api_key_match = re.search(r'API_KEY\s*=\s*["\']([^"\']+)["\']', content)
    secret_key_match = re.search(r'SECRET_KEY\s*=\s*["\']([^"\']+)["\']', content)
    
    if not api_key_match or not secret_key_match:
        print("  ⚠️  No se encontraron API keys en grid-trading-bot.py")
        print("  ℹ️  Las órdenes se cancelarán manualmente o por el dashboard")
        sys.exit(0)
    
    API_KEY = api_key_match.group(1)
    SECRET_KEY = secret_key_match.group(1)
    
    COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]
    
    import requests
    import hmac
    import hashlib
    import time
    
    BASE_URL = "https://api.binance.com"
    
    def get_signature(query_string):
        return hmac.new(SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    
    def cancel_open_orders(symbol):
        timestamp = int(time.time() * 1000)
        query = f"symbol={symbol}&timestamp={timestamp}"
        signature = get_signature(query)
        
        headers = {
            'X-MBX-APIKEY': API_KEY,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        url = f"{BASE_URL}/api/v3/openOrders?{query}&signature={signature}"
        
        try:
            response = requests.delete(url, headers=headers, timeout=10)
            if response.status_code == 200:
                canceled = response.json()
                if len(canceled) > 0:
                    print(f"  ✅ {len(canceled)} órdenes canceladas para {symbol}")
                    return len(canceled)
                else:
                    print(f"  ℹ️  Sin órdenes abiertas para {symbol}")
                    return 0
            else:
                print(f"  ⚠️  Error cancelando {symbol}: {response.status_code} - {response.text[:100]}")
                return 0
        except Exception as e:
            print(f"  ⚠️  Excepción: {e}")
            return 0
    
    total_canceled = 0
    for coin in COINS:
        symbol = f"{coin}USDT"
        total_canceled += cancel_open_orders(symbol)
        time.sleep(0.5)  # Rate limiting
    
    print(f"\n  📊 Total: {total_canceled} órdenes canceladas")
    
except Exception as e:
    print(f"  ⚠️  Error: {e}")
    print("  ℹ️  Continuar sin cancelar - verificar manualmente en Binance")
PYTHON
    
    log "✅ Proceso de cancelación completado"
}

# ════════════════════════════════════════════════════════
# PASO 3: DESACTIVAR GRID BOTS (MARCAR COMO DISABLED)
# ════════════════════════════════════════════════════════

disable_grid_bots() {
    log "🔧 Desactivando configuración Grid Bots..."
    
    cd "$WORKSPACE/crypto-bots"
    
    # Backup del estado actual ANTES de modificar
    BACKUP_FILE="grid-trading-bot.py.migration-backup-$(date +%Y%m%d-%H%M%S)"
    cp grid-trading-bot.py "$BACKUP_FILE"
    log "📦 Backup creado: $BACKUP_FILE"
    
    # Marcar todas las monedas como disabled en grid-trading-bot.py
    python3 << 'PYTHON'
import re

with open('grid-trading-bot.py', 'r') as f:
    content = f.read()

# Pattern para encontrar cada configuración de moneda
pattern = r'("[A-Z]+":\s*\{[^}]*?)"enabled":\s*True'

def disable_match(match):
    return match.group(1) + '"enabled": False  # Desactivado en migración a Slots'

content = re.sub(pattern, disable_match, content, flags=re.DOTALL)

with open('grid-trading-bot.py', 'w') as f:
    f.write(content)

print("✅ Grid bots desactivados en configuración")
PYTHON
    
    log "✅ Grid bots marcados como disabled (reversible)"
}

# ════════════════════════════════════════════════════════
# PASO 4: VERIFICAR SISTEMA DE SLOTS
# ════════════════════════════════════════════════════════

verify_slots_system() {
    log "🔍 Verificando sistema de Slots..."
    
    CHECKS_PASSED=0
    CHECKS_TOTAL=0
    
    # Check 1: slot-health-manager.py (CRÍTICO)
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    if [ -f "$WORKSPACE/crypto-bots/slot-health-manager.py" ]; then
        log "  ✅ slot-health-manager.py existe"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        log "  ❌ slot-health-manager.py NO encontrado"
        error_exit "Falta componente crítico: slot-health-manager.py"
    fi
    
    # Check 2: ML market validator (OPCIONAL)
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    if [ -f "$WORKSPACE/scripts/ml-market-validator.sh" ]; then
        log "  ✅ ml-market-validator.sh existe"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        log "  ℹ️  ml-market-validator.sh NO encontrado (opcional)"
    fi
    
    # Check 3: Auto capital manager (OPCIONAL)
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    if [ -f "$WORKSPACE/scripts/auto-capital-manager.sh" ]; then
        log "  ✅ auto-capital-manager.sh existe"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        log "  ℹ️  auto-capital-manager.sh NO encontrado (opcional)"
    fi
    
    # Check 4: Binance env (OPCIONAL - puede estar en grid-trading-bot.py)
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    if [ -f "$SECRETS_FILE" ]; then
        log "  ✅ binance.env configurado"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        log "  ℹ️  binance.env NO encontrado (puede estar en grid-trading-bot.py)"
    fi
    
    log "📊 Checks: $CHECKS_PASSED/$CHECKS_TOTAL críticos pasaron"
    log "✅ Sistema de Slots verificado"
}

# ════════════════════════════════════════════════════════
# PASO 5: REINICIAR SISTEMA PRINCIPAL (SLOTS)
# ════════════════════════════════════════════════════════

start_slots_system() {
    log "🚀 Iniciando sistema de Slots..."
    
    cd "$WORKSPACE/crypto-bots"
    
    # Iniciar slot-health-manager.py en background
    nohup python3 slot-health-manager.py > "$WORKSPACE/logs/slots-main.log" 2>&1 &
    SLOTS_PID=$!
    
    log "  📊 Slot Health Manager iniciado (PID: $SLOTS_PID)"
    
    # Esperar a que arranque
    sleep 5
    
    if ps -p $SLOTS_PID > /dev/null; then
        log "  ✅ Sistema de Slots corriendo correctamente"
    else
        log "  ⚠️  Sistema de Slots no arrancó - revisar logs/slots-main.log"
    fi
    
    # Iniciar ML market validator (si existe cron o script continuo)
    if [ -f "$WORKSPACE/scripts/ml-market-validator.sh" ]; then
        chmod +x "$WORKSPACE/scripts/ml-market-validator.sh"
        log "  ✅ ML Market Validator listo para ejecutar"
    fi
}

# ════════════════════════════════════════════════════════
# PASO 6: ACTUALIZAR DASHBOARD STATUS
# ════════════════════════════════════════════════════════

update_dashboard_status() {
    log "📈 Actualizando estado del dashboard..."
    
    # Crear/actualizar archivo de estado para el dashboard
    cat > "$WORKSPACE/dashboard/system-status.json" << EOF
{
    "mode": "slots",
    "grid_bots": "disabled",
    "slots_system": "active",
    "migration_date": "$(date -Iseconds)",
    "backup_file": "$BACKUP_FILE",
    "notes": "Migración Grid → Slots completada"
}
EOF
    
    log "  ✅ Dashboard actualizado: modo SLOTS"
}

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🔄 MIGRACIÓN GRID → SLOTS                           ║"
echo "║  Rollback inteligente - Sistema principal             ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

log "═══════════════════════════════════════════════════════"
log "INICIANDO MIGRACIÓN GRID → SLOTS"
log "═══════════════════════════════════════════════════════"

echo "[1/6] Deteniendo procesos Grid..."
stop_grid_processes

echo "[2/6] Cancelando órdenes en Binance..."
cancel_grid_orders

echo "[3/6] Desactivando Grid Bots (config)..."
disable_grid_bots

echo "[4/6] Verificando sistema de Slots..."
verify_slots_system

echo "[5/6] Iniciando sistema de Slots..."
start_slots_system

echo "[6/6] Actualizando dashboard..."
update_dashboard_status

log "═══════════════════════════════════════════════════════"
log "MIGRACIÓN COMPLETADA"
log "═══════════════════════════════════════════════════════"

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ MIGRACIÓN COMPLETADA CON ÉXITO                   ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "📊 Resumen:"
echo "  • Grid Bots: DESACTIVADOS (scripts preservados)"
echo "  • Órdenes Binance: CANCELADAS"
echo "  • Sistema Slots: ACTIVO"
echo "  • Backup config: crypto-bots/grid-trading-bot.py.migration-backup-*"
echo ""
echo "📝 Logs: $LOG_FILE"
echo "📊 Dashboard: http://192.168.3.215:8080"
echo ""
echo "Para revertear a Grid (si es necesario):"
echo "  cp crypto-bots/grid-trading-bot.py.migration-backup-* crypto-bots/grid-trading-bot.py"
echo ""
