#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 GRID TRADING - REPORTE TELEGRAM
# ════════════════════════════════════════════════════════
# Envía reporte periódico del Grid Trading a Telegram
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

WORKSPACE="$HOME/.openclaw/workspace"
LOG_FILE="$WORKSPACE/logs/grid-telegram-report.log"
GRID_STATUS="$WORKSPACE/dashboard/grid-status.json"
TELEGRAM_CHAT_ID="7543955537"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

notify() {
    local message="$1"
    
    # Usar la herramienta message de OpenClaw si está disponible
    # Si no, usar curl directo con bot token
    
    python3 << ENDPYTHON
import requests
import json

try:
    # Leer token de secrets
    with open('$HOME/.openclaw/secrets/telegram.env', 'r') as f:
        for line in f:
            if line.startswith('TELEGRAM_BOT_TOKEN'):
                token = line.split('=')[1].strip()
                break
    
    chat_id = "$TELEGRAM_CHAT_ID"
    message = '''$message'''
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    response = requests.post(url, json=data, timeout=10)
    if response.status_code == 200:
        print("✅ Reporte enviado a Telegram")
    else:
        print(f"❌ Error: {response.text}")
except Exception as e:
    print(f"❌ Error enviando Telegram: {e}")
ENDPYTHON
}

generate_report() {
    log "📊 Generando reporte Grid Trading..."
    
    if [ ! -f "$GRID_STATUS" ]; then
        log "❌ Grid status no encontrado"
        return 1
    fi
    
    # Leer datos del grid
    python3 << ENDPYTHON
import json
from datetime import datetime

with open('$GRID_STATUS', 'r') as f:
    data = json.load(f)

bots = data.get('bots', {})
total_orders = data.get('totalOrders', 0)
total_pnl = data.get('totalPnL', 0.00)
trades_executed = data.get('tradesExecuted', 0)
status = data.get('status', 'unknown')

# Header
report = "🐕 *GRID TRADING REPORT* 🐕\n"
report += f"📊 Status: *{status.upper()}*\n"
report += f"⏰ Update: {datetime.now().strftime('%H:%M:%S')}\n"
report += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

# Bot status
for coin, info in bots.items():
    if info.get('active', False):
        orders = info.get('orders', 0)
        price = info.get('price', 0)
        range_low = info.get('range', {}).get('low', 0)
        range_high = info.get('range', {}).get('high', 0)
        balance = info.get('balanceUSDT', 0)
        
        emoji = "🟢" if orders > 0 else "🟡"
        report += f"{emoji} *{coin}* @ \${price:,.2f}\n"
        report += f"   Orders: {orders} | Rango: \${range_low:,.0f}-\${range_high:,.0f}\n"
        report += f"   Balance: \${balance:.2f} USDT\n\n"

# Summary
report += "━━━━━━━━━━━━━━━━━━━━━━\n"
report += f"📈 Total Orders: *{total_orders}*\n"
report += f"💰 Trades Ejecutados: *{trades_executed}*\n"
report += f"📊 P&L Total: *\${total_pnl:.2f} USDT*\n"

print(report)
ENDPYTHON
}

# Main
log "═══════════════════════════════════════════════════════"
log "Iniciando reporte Grid Trading"

report=$(generate_report)

if [ -n "$report" ]; then
    notify "$report"
    log "✅ Reporte completado"
else
    log "❌ Error generando reporte"
fi
