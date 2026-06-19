#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  📱 PERROBOTILLO NOTIFY - Notificador centralizado   ║
# ╚═══════════════════════════════════════════════════════╝
#
# Uso desde bash:
#   source "$HOME/.openclaw/workspace/crypto-bots/notify.sh"
#   notify "OPEN_TRADE|BTC|1" "✅ OPEN BTC Slot 1 @ \$..."
#
# Uso directo:
#   bash crypto-bots/notify.sh "EVENTO|..." "mensaje"
#
# Características:
# - Centraliza envío Telegram
# - Dedup por clave de evento + ventana temporal (no spam)
# - Usa openclaw.json para token; chat fijo por ahora
# ────────────────────────────────────────────────────────

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
LOG_FILE="$HOME/.openclaw/logs/notify.log"
DEDUP_DIR="$HOME/.openclaw/logs/notify-dedup"
DEDUP_WINDOW_SECONDS="${NOTIFY_DEDUP_WINDOW:-600}"  # 10 min default
CHAT_ID="${NOTIFY_CHAT_ID:-7543955537}"

mkdir -p "$(dirname "$LOG_FILE")" "$DEDUP_DIR" 2>/dev/null || true

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [NOTIFY] $1" | tee -a "$LOG_FILE" 2>/dev/null || true
}

now_ts() {
    date +%s
}

is_duplicate() {
    local key="$1"
    local now
    now="$(now_ts)"
    local file="$DEDUP_DIR/${key//|/_}.txt"
    if [ -f "$file" ]; then
        local last
        last="$(cat "$file" 2>/dev/null || echo 0)"
        if [ -n "$last" ] && [ $(( now - last )) -lt "$DEDUP_WINDOW_SECONDS" ]; then
            return 0  # duplicado dentro de ventana
        fi
    fi
    echo "$now" > "$file"
    return 1  # no duplicado
}

send_telegram() {
    local message="$1"
    local config_file="$HOME/.openclaw/openclaw.json"
    if [ ! -f "$config_file" ]; then
        log "openclaw.json no encontrado"
        return 1
    fi
    local bot_token
    bot_token="$(jq -r '.channels.telegram.botToken // empty' "$config_file" 2>/dev/null)"
    if [ -z "$bot_token" ] || [ "$bot_token" = "null" ]; then
        log "Bot token no encontrado"
        return 1
    fi
    local escaped
    escaped="$(printf '%s' "$message" | sed 's/"/\\"/g' | tr '\n' ' ')";
    local result
    result="$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST \
        "https://api.telegram.org/bot${bot_token}/sendMessage" \
        -H 'Content-Type: application/json' \
        -d "{\"chat_id\":\"${CHAT_ID}\",\"text\":\"${escaped}\",\"parse_mode\":\"HTML\"}" 2>&1)"
    local code
    code="$(echo "$result" | grep "HTTP_CODE:" | cut -d':' -f2)"
    if [ "$code" = "200" ]; then
        log "Telegram enviado"
        return 0
    else
        log "Error Telegram: HTTP ${code}"
        return 1
    fi
}

notify() {
    # notify "EVENT_KEY|SYMBOL|EXTRA" "Mensaje HTML"
    local key="$1"
    local message="$2"
    if [ -z "$key" ] || [ -z "$message" ]; then
        log "notify() requiere key y message"
        return 1
    fi
    if is_duplicate "$key"; then
        log "Notify dedup: ${key}"
        return 0
    fi
    log "Notify: ${key}"
    send_telegram "$message"
}

# CLI directo
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    key="${1:-}"
    message="${2:-}"
    if [ -z "$key" ] || [ -z "$message" ]; then
        echo "Uso: $0 <event_key> <message>"
        exit 2
    fi
    notify "$key" "$message"
    exit $?
fi
