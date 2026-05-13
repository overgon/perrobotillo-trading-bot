#!/bin/bash
# ════════════════════════════════════════════════════════
# 📱 Send Telegram Message - Direct API
# ════════════════════════════════════════════════════════
# Uso: ./send-telegram.sh "Mensaje en Markdown"
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../secrets/telegram.env"

# Cargar configuración
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    # Fallback a openclaw.json
    CONFIG_JSON="${SCRIPT_DIR}/../openclaw.json"
    if [ -f "$CONFIG_JSON" ]; then
        TELEGRAM_BOT_TOKEN=$(jq -r '.channels.telegram.botToken // empty' "$CONFIG_JSON" 2>/dev/null)
        TELEGRAM_CHAT_ID="7543955537"
    fi
fi

# Validar configuración
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ Error: TELEGRAM_BOT_TOKEN no configurado"
    exit 1
fi

if [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "❌ Error: TELEGRAM_CHAT_ID no configurado"
    exit 1
fi

# Función para enviar mensaje
send_telegram() {
    local message="$1"
    local parse_mode="${2:-HTML}"
    
    local result=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${message}" \
        -d "parse_mode=${parse_mode}" \
        --max-time 10)
    
    local http_code=$(echo "$result" | grep "HTTP_CODE:" | cut -d':' -f2)
    local body=$(echo "$result" | sed '/HTTP_CODE:/d')
    
    if [ "$http_code" = "200" ]; then
        local ok=$(echo "$body" | jq -r '.ok // false')
        if [ "$ok" = "true" ]; then
            return 0
        else
            local error=$(echo "$body" | jq -r '.description // "Unknown error"')
            echo "❌ Telegram API Error: $error" >&2
            return 1
        fi
    else
        echo "❌ HTTP Error: $http_code" >&2
        return 1
    fi
}

# Si se ejecuta directamente (no como library)
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    if [ -z "$1" ]; then
        echo "Uso: $0 \"Mensaje\""
        exit 1
    fi
    send_telegram "$1"
fi
