#!/bin/bash
# ════════════════════════════════════════════════════════
# 🔧 BINANCE MAINTENANCE MONITOR
# Monitorea anuncios de mantenimiento de Binance
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
LOG_FILE="/home/overgon/.openclaw/logs/binance-maintenance.log"
STATE_FILE="$WORKSPACE/crypto-bots/binance-maintenance-state.json"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_telegram() {
    local message="$1"
    local config_json="/home/overgon/.openclaw/openclaw.json"
    local chat_id="7543955537"
    
    if [ -f "$config_json" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_json" 2>/dev/null)
        if [ -n "$bot_token" ]; then
            curl -s -X POST "https://api.telegram.org/bot$bot_token/sendMessage" \
                -d "chat_id=$chat_id" \
                -d "text=$message" \
                -d "parse_mode=Markdown" > /dev/null 2>&1
        fi
    fi
}

check_maintenance() {
    log "🔧 Verificando mantenimiento de Binance..."
    
    # Obtener announcements de Binance
    ANNOUNCEMENTS_URL="https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=20&catalogId=48"
    
    response=$(curl -s "$ANNOUNCEMENTS_URL" 2>/dev/null)
    
    if [ -z "$response" ]; then
        log "⚠️ Error obteniendo announcements"
        return
    fi
    
    # Buscar palabras clave de mantenimiento
    maintenance_keywords=("maintenance" "mantenimiento" "upgrade" "actualización" "system update" "trading halt")
    
    found_maintenance=false
    latest_title=""
    latest_url=""
    latest_time=""
    
    # Parsear JSON (simplificado)
    echo "$response" | python3 << 'PYEOF'
import sys
import json

try:
    data = json.load(sys.stdin)
    articles = data.get('data', {}).get('articles', [])
    
    keywords = ['maintenance', 'mantenimiento', 'upgrade', 'actualización', 'system update', 'trading halt', 'pause']
    
    for article in articles[:5]:  # Revisar últimos 5
        title = article.get('title', '').lower()
        catalog_name = article.get('catalogName', '').lower()
        
        # Verificar si es de mantenimiento
        if any(kw in title or kw in catalog_name for kw in keywords):
            print(f"MANTENIMIENTO_ENCONTRADO|{article.get('title', '')}|{article.get('releaseDate', '')}|{article.get('id', '')}")
            break
    else:
        print("SIN_MANTENIMIENTO")
        
except Exception as e:
    print(f"ERROR|{str(e)}")
PYEOF
}

# Main
log "╔═══════════════════════════════════════════════════════╗"
log "║  🔧 BINANCE MAINTENANCE CHECK                         ║"
log "╚═══════════════════════════════════════════════════════╝"

result=$(check_maintenance)
status=$(echo "$result" | cut -d'|' -f1)

if [ "$status" = "MANTENIMIENTO_ENCONTRADO" ]; then
    title=$(echo "$result" | cut -d'|' -f2)
    date=$(echo "$result" | cut -d'|' -f3)
    id=$(echo "$result" | cut -d'|' -f4)
    
    # Verificar si ya notificamos este announcement
    notified_id=""
    if [ -f "$STATE_FILE" ]; then
        notified_id=$(jq -r '.last_notified_id // ""' "$STATE_FILE" 2>/dev/null)
    fi
    
    if [ "$notified_id" != "$id" ]; then
        log "🚨 Mantenimiento detectado: $title"
        
        send_telegram "🔧 BINANCE MAINTENANCE
⚠️ *Anuncio oficial: $title*
ID: $id - $(date -d "@$((date / 1000))" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "$date")
• Monitorear trades activos
• Considerar pausar nuevas operaciones 🐕"
        
        # Guardar estado
        echo "{\"last_notified_id\": \"$id\", \"notified_at\": \"$(date -Iseconds)\", \"title\": \"$title\"}" > "$STATE_FILE"
        
        log "✅ Notificación enviada"
    else
        log "✅ Ya notificado este mantenimiento (ID: $id)"
    fi
else
    log "✅ Sin mantenimiento pendiente"
fi

log ""
