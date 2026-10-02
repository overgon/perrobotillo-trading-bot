#!/usr/bin/env bash
# 🔔 Notificación de trade cerrado a Telegram v2 - sin comillas extra
# Uso: notify_trade.sh <symbol> <closeType> <pnl> <tradeId> <entry> <exit>
set -euo pipefail

SYMBOL="${1:-UNKNOWN}"
CLOSE_TYPE="${2:-CLOSED}"
PNL="${3:-0.00}"
TRADE_ID="${4:-0}"
ENTRY="${5:-0}"
EXIT="${6:-0}"

TELEGRAM_SECRETS="/home/overgon/.openclaw/secrets/telegram.env"
if [[ -f "$TELEGRAM_SECRETS" ]]; then
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

# Formatear PnL con signo
PNL_SIGN="+"; [[ $(echo "$PNL < 0" | bc -l 2>/dev/null || echo 0) -eq 1 ]] && PNL_SIGN="-" || PNL_SIGN="+"

# 📱 Mensaje compacto - una sola línea + separador
MSG="📜 ${SYMBOL} ${CLOSE_TYPE} [Trade #${TRADE_ID}]
Exit: \$${EXIT} | Entrada: \$${ENTRY} | PnL: ${PNL_SIGN}\$${PNL}
$(date '+%H:%M:%S') CST 🐕"

# Enviar a Telegram con --data-urlencode para evitar comillas extra
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    --data-urlencode "text=${MSG}" \
    -d "parse_mode=Markdown" \
    >/dev/null 2>&1 || true

echo "✅ Enviado: ${SYMBOL} ${CLOSE_TYPE} PnL=${PNL_SIGN}\$${PNL}"
