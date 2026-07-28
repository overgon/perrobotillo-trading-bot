#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  📱 PERROBOTILLO NOTIFY - Notificador centralizado   ║
# ║  v2.0 - Con retry exponencial + cola local           ║
# ╚═══════════════════════════════════════════════════════╝
#
# Uso desde bash:
#   source "$HOME/.openclaw/workspace/crypto-bots/notify.sh"
#   notify "OPEN_TRADE|BTC|1" "✅ OPEN BTC Slot 1 @ \$..."
#
# Uso directo:
#   bash crypto-bots/notify.sh "EVENTO|..." "mensaje"
#   bash crypto-bots/notify.sh process-queue  # Procesar cola pendiente
#
# Características:
# - Centraliza envío Telegram
# - Dedup por clave de evento + ventana temporal (no spam)
# - Retry exponencial (3 intentos: 2s → 4s → 8s)
# - Cola local persistente para eventos fallidos
# - Usa openclaw.json para token; chat fijo por ahora
# ────────────────────────────────────────────────────────

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
LOG_FILE="$HOME/.openclaw/logs/notify.log"
DEDUP_DIR="$HOME/.openclaw/logs/notify-dedup"
QUEUE_FILE="$HOME/.openclaw/logs/notify-queue.json"
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
    escaped="$(printf '%s' "$message" | jq -R . | jq -s -R 'rtrimstr("\n")')"
    local result
    result="$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST \
        "https://api.telegram.org/bot${bot_token}/sendMessage" \
        -H 'Content-Type: application/json' \
        -d "{\"chat_id\":\"${CHAT_ID}\",\"text\":${escaped},\"parse_mode\":\"HTML\"}" 2>&1)"
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

send_with_retry() {
    local message="$1"
    local event_key="$2"
    local max_retries=3
    local delay=2  # segundos iniciales
    
    for i in $(seq 1 $max_retries); do
        log "Intento $i/$max_retries para enviar: $event_key"
        
        if send_telegram "$message"; then
            log "Telegram enviado exitosamente (intento $i)"
            return 0
        fi
        
        if [ $i -lt $max_retries ]; then
            log "Intento $i fallido, esperando ${delay}s antes del próximo intento..."
            sleep $delay
            delay=$((delay * 2))  # exponencial: 2s → 4s → 8s
        fi
    done
    
    # Si llega acá, todos los retries fallaron → encolar
    log "Todos los retries fallidos, encolando mensaje: $event_key"
    enqueue_message "$message" "$event_key"
    return 1
}

enqueue_message() {
    local message="$1"
    local event_key="$2"
    local timestamp=$(now_ts)
    
    # Leer cola actual o crear nueva
    local queue
    if [ -f "$QUEUE_FILE" ]; then
        queue=$(cat "$QUEUE_FILE" 2>/dev/null)
    else
        queue='{"pending":[]}'
    fi
    
    # Agregar nuevo mensaje con retries=0
    echo "$queue" | jq --arg msg "$message" --arg key "$event_key" --arg ts "$timestamp" \
        '.pending += [{"message": $msg, "event_key": $key, "timestamp": ($ts|tonumber), "retries": 0}]' \
        > "$QUEUE_FILE.tmp" && mv "$QUEUE_FILE.tmp" "$QUEUE_FILE"
    
    log "Mensaje encolado: $event_key (cola: $(echo "$queue" | jq '.pending | length'))"
}

process_queue() {
    log "=== Procesando cola de notificaciones ==="
    
    if [ ! -f "$QUEUE_FILE" ]; then
        log "Cola no existe, nada que procesar"
        return 0
    fi
    
    local queue=$(cat "$QUEUE_FILE" 2>/dev/null)
    local pending=$(echo "$queue" | jq '.pending | length')
    
    if [ "$pending" = "0" ] || [ "$pending" = "null" ]; then
        log "Cola vacía, nada que procesar"
        return 0
    fi
    
    log "Procesando $pending mensajes pendientes..."
    
    # Procesar cada mensaje (máx 1 retry por corrida)
    echo "$queue" | jq -c '.pending[]' | while read -r item; do
        local message=$(echo "$item" | jq -r '.message')
        local event_key=$(echo "$item" | jq -r '.event_key')
        local retries=$(echo "$item" | jq -r '.retries')
        
        log "Procesando: $event_key (retries previos: $retries)"
        
        if send_telegram "$message"; then
            # Remover de la cola - éxito
            echo "$queue" | jq --arg key "$event_key" \
                '.pending = [.pending[] | select(.event_key != $key)]' \
                > "$QUEUE_FILE.tmp" && mv "$QUEUE_FILE.tmp" "$QUEUE_FILE"
            log "✅ Mensaje enviado desde cola: $event_key"
        elif [ "$retries" -ge 5 ]; then
            # Descartar después de 5 retries totales
            log "❌ Descartando mensaje tras 5 retries: $event_key"
            echo "$queue" | jq --arg key "$event_key" \
                '.pending = [.pending[] | select(.event_key != $key)]' \
                > "$QUEUE_FILE.tmp" && mv "$QUEUE_FILE.tmp" "$QUEUE_FILE"
        else
            # Incrementar contador de retries
            local new_retries=$((retries + 1))
            echo "$queue" | jq --arg key "$event_key" --argjson nr "$new_retries" \
                '.pending = [.pending[] | if .event_key == $key then .retries = $nr else . end]' \
                > "$QUEUE_FILE.tmp" && mv "$QUEUE_FILE.tmp" "$QUEUE_FILE"
            log "⚠️ Retry fallido, actualizado a $new_retries retries: $event_key"
        fi
        
        # Recargar queue para el próximo item
        queue=$(cat "$QUEUE_FILE" 2>/dev/null)
    done
    
    local remaining=$(echo "$queue" | jq '.pending | length')
    log "=== Cola procesada. Mensajes restantes: $remaining ==="
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
    send_with_retry "$message" "$key"
}

# CLI directo
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    action="${1:-}"
    
    if [ "$action" = "process-queue" ]; then
        # Modo procesamiento de cola
        process_queue
        exit $?
    fi
    
    key="${2:-}"
    message="${3:-}"
    if [ -z "$action" ] || [ -z "$key" ] || [ -z "$message" ]; then
        echo "Uso:"
        echo "  $0 <event_key> <message>              # Enviar notificación"
        echo "  $0 process-queue                       # Procesar cola pendiente"
        exit 2
    fi
    notify "$key" "$message"
    exit $?
fi
