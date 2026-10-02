#!/bin/bash
# ════════════════════════════════════════════════════════
# 🔧 Claw Utils - Reemplazo de comandos OpenClaw
# ════════════════════════════════════════════════════════
# Uso: source claw-utils.sh
#      status
#      start_gateway
#      stop_gateway
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."

# ════════════════════════════════════════════════════════
# STATUS
# ════════════════════════════════════════════════════════
status() {
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║  🐕 PERROBOTILLO - SYSTEM STATUS                      ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo ""
    
    # Trading Bot
    echo "📊 TRADING BOT:"
    local bot_running=$(pgrep -f "crypto-trade-moneda-v3-slots.sh" | wc -l)
    if [ "$bot_running" -gt 0 ]; then
        echo "   ✅ Bot corriendo ($bot_running procesos)"
    else
        echo "   ⚠️  Bot no está corriendo (es normal, es por cron)"
    fi
    
    # Cron Jobs
    echo ""
    echo "⏰ CRON JOBS:"
    local cron_count=$(crontab -l 2>/dev/null | grep -c "crypto-trade-moneda")
    echo "   ✅ $cron_count jobs de trading activos"
    
    # Dashboard
    echo ""
    echo "🎨 DASHBOARD:"
    if systemctl is-active --quiet perrobotillo-dashboard-ngrok 2>/dev/null; then
        echo "   ✅ Dashboard + Ngrok corriendo (systemd)"
        local url=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | jq -r '.tunnels[0].public_url // "N/A"')
        if [ "$url" != "N/A" ] && [ "$url" != "null" ]; then
            echo "   🌐 URL: $url"
        fi
    elif pgrep -f "start-with-ngrok.sh" > /dev/null 2>&1 || (pgrep -f "python.*app.py" > /dev/null 2>&1 && pgrep -f "ngrok" > /dev/null 2>&1); then
        echo "   ✅ Dashboard + Ngrok corriendo (manual)"
        local url=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | jq -r '.tunnels[0].public_url // "N/A"')
        if [ "$url" != "N/A" ] && [ "$url" != "null" ]; then
            echo "   🌐 URL: $url"
        else
            echo "   🌐 URL: http://192.168.3.215:8080"
        fi
    else
        echo "   ❌ Dashboard no está corriendo"
    fi
    
    # API Binance
    echo ""
    echo "🔑 API BINANCE:"
    if [ -f "${WORKSPACE}/secrets/binance.env" ] || [ -f "/home/overgon/.openclaw/secrets/binance.env" ]; then
        echo "   ✅ Credenciales configuradas"
    else
        echo "   ❌ Credenciales no encontradas"
    fi
    
    # IP Pública y Whitelist
    echo ""
    echo "🌐 IP PÚBLICA:"
    local public_ip=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "No disponible")
    if [ "$public_ip" != "No disponible" ] && [ -n "$public_ip" ]; then
        echo "   📍 Tu IP: $public_ip"
        echo "   ⚠️  Verificá que esté en el whitelist de Binance"
    else
        echo "   ❌ No se pudo obtener la IP"
    fi
    
    # Slots Status
    echo ""
    echo "🎯 SLOTS STATUS:"
    local total_slots=0
    local active_slots=0
    for coin in BTC ETH BNB SOL XRP AVAX ZEC; do
        local state_file="${WORKSPACE}/crypto-bots/${coin}-trade-state.json"
        if [ -f "$state_file" ]; then
            local coin_slots=$(jq -r '.slots | length' "$state_file" 2>/dev/null || echo "0")
            local coin_active=$(jq -r '[.slots[] | select(.status == "ACTIVE")] | length' "$state_file" 2>/dev/null || echo "0")
            total_slots=$((total_slots + coin_slots))
            active_slots=$((active_slots + coin_active))
        fi
    done
    echo "   Total: $total_slots slots"
    echo "   Activos: $active_slots"
    echo "   Ready: $((total_slots - active_slots))"
    
    # Disk Space
    echo ""
    echo "💾 DISK SPACE:"
    local disk_usage=$(df -h "${WORKSPACE}" | tail -1 | awk '{print $5}')
    echo "   Usage: $disk_usage"
    
    echo ""
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║  ✅ SYSTEM OPERATIONAL                                ║"
    echo "╚═══════════════════════════════════════════════════════╝"
}

# ════════════════════════════════════════════════════════
# GATEWAY CONTROLS (OpenClaw)
# ════════════════════════════════════════════════════════
start_gateway() {
    echo "🚀 Starting OpenClaw Gateway..."
    openclaw gateway start
}

stop_gateway() {
    echo "🛑 Stopping OpenClaw Gateway..."
    openclaw gateway stop
}

restart_gateway() {
    echo "🔄 Restarting OpenClaw Gateway..."
    openclaw gateway restart
}

# ════════════════════════════════════════════════════════
# HELP
# ════════════════════════════════════════════════════════
claw_help() {
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║  🐕 PERROBOTILLO - AVAILABLE COMMANDS                 ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo ""
    echo "System:"
    echo "   status              - Show system status"
    echo ""
    echo "OpenClaw Gateway:"
    echo "   start_gateway       - Start OpenClaw Gateway"
    echo "   stop_gateway        - Stop OpenClaw Gateway"
    echo "   restart_gateway     - Restart OpenClaw Gateway"
    echo ""
    echo "Usage:"
    echo "   source claw-utils.sh"
    echo "   status"
    echo ""
}

# Auto-run if executed directly
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    case "$1" in
        status)
            status
            ;;
        start|start_gateway)
            start_gateway
            ;;
        stop|stop_gateway)
            stop_gateway
            ;;
        restart|restart_gateway)
            restart_gateway
            ;;
        *)
            claw_help
            ;;
    esac
fi
