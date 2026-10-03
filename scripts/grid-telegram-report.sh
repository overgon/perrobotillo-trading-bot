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

    # ✅ FIX: Read token from openclaw.json (telegram.env does not exist in secrets/)
    python3 << ENDPYTHON
import json, os, sys
from pathlib import Path

message = """$message"""
chat_id = "7543955537"
token = ""

config_file = Path.home() / ".openclaw" / "openclaw.json"
if config_file.exists():
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        token = config.get('channels', {}).get('telegram', {}).get('botToken', '')
        ids = config.get('channels', {}).get('telegram', {}).get('chatIds', [])
        if ids:
            chat_id = ids[0]
    except Exception:
        pass

if not token:
    print("❌ No Telegram token found", file=sys.stderr)
    sys.exit(1)

import urllib.request, urllib.parse

url = f"https://api.telegram.org/bot{token}/sendMessage"
data = {
    'chat_id': chat_id,
    'text': message,
    'parse_mode': 'Markdown'
}
response = urllib.request.urlopen(
    url,
    data=urllib.parse.urlencode(data).encode('utf-8'),
    timeout=10
)
if response.status == 200:
    print("✅ Reporte enviado a Telegram")
else:
    print(f"❌ Error: {response.read().decode()}")
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
report = "🐕 **GRID TRADING REPORT**\n"
report += f"📊 Status: *{status.upper()}* | ⏰ {datetime.now().strftime('%H:%M:%S')}\n"
report += "━━━━━━━━━━━━━━━━━━\n"

# Bot status
for coin, info in bots.items():
    if info.get('active', False):
        orders = info.get('orders', 0)
        price = info.get('price', 0)
        range_low = info.get('range', {}).get('low', 0)
        range_high = info.get('range', {}).get('high', 0)
        balance = info.get('balanceUSDT', 0)

        emoji = "🟢" if orders > 0 else "🟡"
        report += f"{emoji} *{coin}* | ${price:,.2f} | Orders: {orders}\n"
        report += f"   Rango: ${range_low:,.0f}-${range_high:,.0f} | Bal: ${balance:.2f} USDT\n"

# Summary
report += "━━━━━━━━━━━━━━━━━━\n"
report += f"📈 Orders: *{total_orders}* | Trades: *{trades_executed}*\n"
report += f"💰 PnL Total: *${total_pnl:.2f} USDT* 🐕\n"

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
