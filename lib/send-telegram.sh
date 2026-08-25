#!/bin/bash
# ════════════════════════════════════════════════════════
# 📱 Send Telegram Message - Direct API v2 (url-encoded)
# ════════════════════════════════════════════════════════
# Uso: ./send-telegram.sh "Mensaje en Markdown" [parse_mode]
# Fix: usa --data-urlencode para escapar correctamente
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../secrets/telegram.env"

# Cargar configuración
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
elif [ -f "${SCRIPT_DIR}/../openclaw.json" ]; then
    TELEGRAM_BOT_TOKEN=$(jq -r '.channels.telegram.botToken // empty' "${SCRIPT_DIR}/../openclaw.json" 2>/dev/null)
    TELEGRAM_CHAT_ID="7543955537"
fi

# Validar configuración
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ Error: TELEGRAM_BOT_TOKEN no configurado" >&2
    exit 1
fi

if [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "❌ Error: TELEGRAM_CHAT_ID no configurado" >&2
    exit 1
fi

# Función para enviar mensaje usando --data-urlencode (evita comillas extra)
send_telegram() {
    local message="$1"
    local parse_mode="${2:-Markdown}"

    local result
    result=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${message}" \
        -d "parse_mode=${parse_mode}" \
        --max-time 10 2>&1)

    local http_code
    http_code=$(echo "$result" | grep "HTTP_CODE:" | cut -d':' -f2)
    local body
    body=$(echo "$result" | sed '/HTTP_CODE:/d')

    if [ "$http_code" = "200" ]; then
        local ok
        ok=$(echo "$body" | jq -r '.ok // false' 2>/dev/null)
        if [ "$ok" = "true" ]; then
            return 0
        else
            echo "❌ Telegram API Error: $(echo "$body" | jq -r '.description // "Unknown error"' 2>/dev/null)" >&2
            return 1
        fi
    else
        echo "❌ HTTP Error: $http_code | $body" >&2
        return 1
    fi
}

# Si se ejecuta directamente (no como library)
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    if [ -z "$1" ]; then
        echo "Uso: $0 \"Mensaje\" [parse_mode]"
        exit 1
    fi
    send_telegram "$1" "${2:-Markdown}"
fi
