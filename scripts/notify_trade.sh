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

# ✅ FIX: Load token from openclaw.json (telegram.env does not exist in secrets/)
# Perrobotillo centraliza el token en $HOME/.openclaw/openclaw.json
CONFIG_FILE="$HOME/.openclaw/openclaw.json"
TOKEN=""
CHAT_ID="7543955537"

if [[ -f "$CONFIG_FILE" ]]; then
    TOKEN=$(jq -r '.channels.telegram.botToken // empty' "$CONFIG_FILE" 2>/dev/null)
    CHAT_ID=$(jq -r '.channels.telegram.chatIds[0] // "7543955537"' "$CONFIG_FILE" 2>/dev/null)
fi

# Fallback: also check notify.sh centralized path
if [[ -z "$TOKEN" ]]; then
    source "$HOME/.openclaw/workspace/crypto-bots/notify.sh" 2>/dev/null
fi

if [[ -z "$TOKEN" ]]; then
    echo "⚠️ No Telegram token found" >&2
    exit 1
fi

# Formatear PnL con signo
PNL_SIGN="+"; [[ $(echo "$PNL < 0" | bc -l 2>/dev/null || echo 0) -eq 1 ]] && PNL_SIGN="-" || PNL_SIGN="+"

# 📱 Mensaje compacto - una sola línea + separador
MSG="📜 ${SYMBOL} ${CLOSE_TYPE} [Trade #${TRADE_ID}]
Exit: \$${EXIT} | Entrada: \$${ENTRY} | PnL: ${PNL_SIGN}\$${PNL}
$(date '+%H:%M:%S') CST 🐕"

# 📱 Enviar a Telegram con HTML escaping (evita \\ bugs de Markdown)
# ✅ FIX: Use HTML parse_mode — only < > & need escaping, no fragile sed chains
escaped_message=$(printf '%s' "$MSG" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    --data-urlencode "text=${escaped_message}" \
    -d "parse_mode=HTML" \
    >/dev/null 2>&1 || true

echo "✅ Enviado: ${SYMBOL} ${CLOSE_TYPE} PnL=${PNL_SIGN}\$${PNL}"
