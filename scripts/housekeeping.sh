#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - HOUSEKEEPING SCRIPT
# ════════════════════════════════════════════════════════
# Limpieza mensual de logs + alertas de espacio
# Ejecutar: 1ro de cada mes a las 01:00 AM
# ════════════════════════════════════════════════════════

LOGS_DIR="/home/overgon/.openclaw/logs"
LOG_FILE="/home/overgon/.openclaw/logs/housekeeping.log"
MAX_LOGS_MB=500
MAX_DISK_PERCENT=80

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_telegram() {
    local message="$1"
    local config_file="$HOME/.openclaw/openclaw.json"
    
    if [ -f "$config_file" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_file" 2>/dev/null)
        local chat_id=$(jq -r '.channels.telegram.chatIds[0] // empty' "$config_file" 2>/dev/null)
        
        if [ -n "$bot_token" ] && [ -n "$chat_id" ]; then
            curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
                -d "chat_id=${chat_id}" \
                -d "text=$message" \
                -d "parse_mode=HTML" > /dev/null
            return 0
        fi
    fi
    return 1
}

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

log "╔═══════════════════════════════════════════════════════╗"
log "║  🧹 HOUSEKEEPING - Limpieza Mensual                   ║"
log "╚═══════════════════════════════════════════════════════╝"

# 1. Verificar espacio actual
log ""
log "📊 Espacio actual de logs:"
du -sh "$LOGS_DIR" | tee -a "$LOG_FILE"

# 2. Eliminar logs .gz mayores a 7 días
log ""
log "🗑️  Eliminando logs comprimidos > 7 días..."
deleted_gz=$(find "$LOGS_DIR" -name "*.gz" -type f -mtime +7 -delete -print 2>/dev/null | wc -l)
log "✅ Eliminados: $deleted_gz archivos .gz viejos"

# 3. Eliminar logs normales mayores a 30 días
log ""
log "🗑️  Eliminando logs > 30 días..."
deleted_old=$(find "$LOGS_DIR" -name "*.log" -type f -mtime +30 -delete -print 2>/dev/null | wc -l)
log "✅ Eliminados: $deleted_old archivos .log viejos"

# Eliminar logs de ML > 14 días (son más verbosos)
log ""
log "🗑️  Eliminando logs de ML > 14 días..."
deleted_ml=$(find "$LOGS_DIR" -name "ml-*.log" -type f -mtime +14 -delete -print 2>/dev/null | wc -l)
log "✅ Eliminados: $deleted_ml archivos ml-*.log viejos"

# 4. Mantener solo últimos 7 días de trade-*.log
log ""
log "🗑️  Limpiando trade-*.log antiguos (mantener últimos 7 días)..."
cd "$LOGS_DIR"
ls -t trade-*.log 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null
remaining=$(ls trade-*.log 2>/dev/null | wc -l)
log "✅ Trade logs restantes: $remaining"

# Mantener solo últimas 1000 líneas de ml-retrain.log (rotar)
log ""
log "🗑️  Rotando logs de ML (mantener últimas 1000 líneas)..."
if [ -f "$LOGS_DIR/ml-retrain.log" ]; then
    tail -1000 "$LOGS_DIR/ml-retrain.log" > "$LOGS_DIR/ml-retrain.log.tmp" 2>/dev/null
    mv "$LOGS_DIR/ml-retrain.log.tmp" "$LOGS_DIR/ml-retrain.log" 2>/dev/null
    log "✅ ML log rotado (últimas 1000 líneas)"
fi

# 5. Rotar logs manualmente (si logrotate está disponible)
log ""
if command -v logrotate &> /dev/null; then
    log "🔄 Ejecutando logrotate..."
    logrotate -f "$LOGS_DIR/logrotate.conf" 2>&1 | tee -a "$LOG_FILE"
    log "✅ Logrotate completado"
else
    log "⚠️  logrotate no instalado - saltando rotación"
fi

# 6. Calcular espacio después de limpieza
log ""
log "📊 Espacio después de limpieza:"
du -sh "$LOGS_DIR" | tee -a "$LOG_FILE"
logs_size_mb=$(du -sm "$LOGS_DIR" | cut -f1)

# 7. Verificar espacio en disco
disk_usage=$(df -h /home | awk 'NR==2 {print $5}' | sed 's/%//')
log ""
log "💾 Uso de disco: ${disk_usage}%"

# 8. Enviar alertas si es necesario
if [ "$logs_size_mb" -gt "$MAX_LOGS_MB" ]; then
    log ""
    log "🚨 ALERTA: Logs > ${MAX_LOGS_MB}MB (actual: ${logs_size_mb}MB)"
    
    send_telegram "<b>🚨 ALERTA: Logs Excedidos</b>

📊 <b>Tamaño actual:</b> ${logs_size_mb}MB
⚠️  <b>Límite:</b> ${MAX_LOGS_MB}MB

<b>Acciones tomadas:</b>
• Eliminados logs > 30 días
• Eliminados .gz > 7 días
• Trade logs limitados a 7 días

<b>Recomendación:</b>
Revisar logs más grandes:
<code>du -sh /home/overgon/.openclaw/logs/* | sort -hr</code>

🐕 Perrobotillo Trading Bot"
fi

if [ "$disk_usage" -gt "$MAX_DISK_PERCENT" ]; then
    log ""
    log "🚨 ALERTA: Disco > ${MAX_DISK_PERCENT}% (actual: ${disk_usage}%)"
    
    send_telegram "<b>🚨 ALERTA: Disco Lleno</b>

💾 <b>Uso actual:</b> ${disk_usage}%
⚠️  <b>Límite:</b> ${MAX_DISK_PERCENT}%

<b>Acciones tomadas:</b>
• Housekeeping ejecutado
• Logs antiguos eliminados

<b>Acción requerida:</b>
Revisar archivos grandes:
<code>du -ah /home | sort -rh | head -20</code>

🐕 Perrobotillo Trading Bot"
fi

# 9. Resumen final
log ""
log "╔═══════════════════════════════════════════════════════╗"
log "║  ✅ HOUSEKEEPING COMPLETED                            ║"
log "╚═══════════════════════════════════════════════════════╝"
log ""
log "📊 RESUMEN:"
log "  • Logs .gz eliminados: $deleted_gz"
log "  • Logs viejos eliminados: $deleted_old"
log "  • Trade logs restantes: $remaining"
log "  • Tamaño final: ${logs_size_mb}MB"
log "  • Uso de disco: ${disk_usage}%"
log ""
