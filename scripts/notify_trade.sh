#!/usr/bin/env bash
# 🔔 Notificación de trade cerrado a Telegram
# Uso: notify_trade.sh <symbol> <closeType> <pnl> <tradeId> <entry> <exit>
set -euo pipefail

SYMBOL="${1:-UNKNOWN}"
CLOSE_TYPE="${2:-CLOSED}"
PNL="${3:-0.00}"
TRADE_ID="${4:-0}"
ENTRY="${5:-0}"
EXIT="${6:-0}"

# Cargar secrets de Telegram
TELEGRAM_SECRETS="/home/overgon/.openclaw/secrets/telegram.env"
if [[ -f "$TELEGRAM_SECRETS" ]]; then
    # shellcheck disable=SC1090
    source "$TELEGRAM_SECRETS"
else
    echo "⚠️ telegram.env not found" >&2
    exit 1
fi

TOKEN="${TELEGRAM_BOT_TOKEN:-${TELEGRAM_TOKEN:-}}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"

if [[ -z "$TOKEN" || -z "$CHAT_ID" ]]; then
    echo "⚠️ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID" >&2
    exit 1
fi

# Formatear mensaje
PNL_SIGN="+"; [[ $(echo "$PNL < 0" | bc -l 2>/dev/null || echo 0) -eq 1 ]] && PNL_SIGN="-" || PNL_SIGN="+"

MSG="${MSG_PREFIX:-}📜 Perrobotillo Trade Cerrado

🪙 ${SYMBOL} | ${CLOSE_TYPE}
💰 P&L: ${PNL_SIGN}$${PNL}
🆔 Trade #${TRADE_ID}
📈 Entrada: \$${ENTRY} → Salida: \$${EXIT}
⏰ $(date '+%Y-%m-%d %H:%M:%S') CST"

# Enviar a Telegram
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d chat_id="${CHAT_ID}" \
    -d text="$MSG" \
    -d parse_mode="Markdown" \
    >/dev/null 2>&1 || true

echo "✅ Notificación enviada: ${SYMBOL} ${CLOSE_TYPE} PnL=\$${PNL}"