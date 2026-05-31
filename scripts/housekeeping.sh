#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧹 HOUSEKEEPING - Log Rotation & Cleanup
# ════════════════════════════════════════════════════════
# Corre diariamente a las 2:00 AM
# - Rota logs grandes (>10MB)
# - Elimina logs viejos (>30 días)
# - Mantiene logs críticos
# ════════════════════════════════════════════════════════

WORKSPACE="/home/overgon/.openclaw/workspace"
LOGS_DIR="$HOME/.openclaw/logs"
MAX_SIZE_MB=10
MAX_AGE_DAYS=30

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGS_DIR/housekeeping.log"
}

log "╔═══════════════════════════════════════════════════════╗"
log "║  🧹 HOUSEKEEPING - Starting                           ║"
log "╚═══════════════════════════════════════════════════════╝"

# ════════════════════════════════════════════════════════
# LOGS CRÍTICOS (No eliminar, solo rotar)
# ════════════════════════════════════════════════════════

CRITICAL_LOGS=(
    "trade-BTC.log"
    "trade-ETH.log"
    "trade-BNB.log"
    "trade-SOL.log"
    "trade-LINK.log"
    "trade-XRP.log"
    "trade-AVAX.log"
    "tp-monitor.log"
    "ml-retrain.log"
    "auto-retrain.log"
    "ml-validator-log.json"
    "dashboard.log"
    "gateway.log"
    "commands.log"
)

# ════════════════════════════════════════════════════════
# LOGS DE AUDITORÍA (Mantener 30 días)
# ════════════════════════════════════════════════════════

AUDIT_LOGS=(
    "trade-history.json"
    "cashout-history.json"
    "daily-report-*.md"
)

# ════════════════════════════════════════════════════════
# ROTAR LOGS GRANDES
# ════════════════════════════════════════════════════════

rotate_large_logs() {
    log "🔄 Rotando logs > ${MAX_SIZE_MB}MB..."
    
    for log_file in "$LOGS_DIR"/*.log; do
        [ ! -f "$log_file" ] && continue
        
        file_size=$(stat -c%s "$log_file" 2>/dev/null || echo "0")
        size_mb=$((file_size / 1048576))
        
        if [ $size_mb -gt $MAX_SIZE_MB ]; then
            log "  📝 Rotando $(basename $log_file) (${size_mb}MB)"
            
            # Rotar con timestamp
            timestamp=$(date +%Y%m%d_%H%M%S)
            mv "$log_file" "${log_file}.${timestamp}"
            
            # Crear archivo vacío
            touch "$log_file"
            
            # Comprimir rotado
            gzip "${log_file}.${timestamp}" &
        fi
    done
    
    wait
    log "  ✅ Rotación completada"
}

# ════════════════════════════════════════════════════════
# ELIMINAR LOGS VIEJOS
# ════════════════════════════════════════════════════════

cleanup_old_logs() {
    log "🗑️ Eliminando logs > ${MAX_AGE_DAYS} días..."
    
    # Logs rotados (.gz)
    old_count=$(find "$LOGS_DIR" -name "*.log.*.gz" -mtime +$MAX_AGE_DAYS 2>/dev/null | wc -l)
    if [ $old_count -gt 0 ]; then
        find "$LOGS_DIR" -name "*.log.*.gz" -mtime +$MAX_AGE_DAYS -delete
        log "  ✅ Eliminados $old_count logs rotados viejos"
    fi
    
    # Reports diarios viejos
    old_reports=$(find "$WORKSPACE/crypto-bots" -name "daily-report-*.md" -mtime +$MAX_AGE_DAYS 2>/dev/null | wc -l)
    if [ $old_reports -gt 0 ]; then
        find "$WORKSPACE/crypto-bots" -name "daily-report-*.md" -mtime +$MAX_AGE_DAYS -delete
        log "  ✅ Eliminados $old_reports reports viejos"
    fi
    
    # Backups temporales
    find /tmp -name "perrobotillo-backup-*.tar.gz" -mtime +7 -delete 2>/dev/null
    log "  ✅ Backups temporales limpiados"
}

# ════════════════════════════════════════════════════════
# LIMPIAR ARCHIVOS TEMPORALES
# ════════════════════════════════════════════════════════

cleanup_temp_files() {
    log "🗑️ Limpiando archivos temporales..."
    
    # Temp files
    rm -rf /tmp/portfolio_cache.json.old 2>/dev/null
    rm -rf /tmp/mxn_rate_cache.json.old 2>/dev/null
    
    # Old state files (si existen backups)
    find "$WORKSPACE/crypto-bots" -name "*-backup.json" -mtime +7 -delete 2>/dev/null
    
    log "  ✅ Temporales limpiados"
}

# ════════════════════════════════════════════════════════
# VERIFICAR ESPACIO EN DISCO
# ════════════════════════════════════════════════════════

check_disk_space() {
    log "💾 Verificando espacio en disco..."
    
    available=$(df -h "$HOME" | tail -1 | awk '{print $4}')
    used_percent=$(df -h "$HOME" | tail -1 | awk '{print $5}')
    
    log "  💿 Disponible: $available"
    log "  📊 Usado: $used_percent"
    
    if [ "${used_percent%\%}" -gt 80 ]; then
        log "  ⚠️ ALERTA: Espacio en disco bajo!"
        
        # Notificar por Telegram
        TELEGRAM_ENV="$WORKSPACE/secrets/telegram.env"
        if [ -f "$TELEGRAM_ENV" ]; then
            source "$TELEGRAM_ENV"
            
            message="⚠️ *Alerta de Espacio en Disco*
            
Espacio usado: ${used_percent}
Disponible: ${available}

Housekeeping ejecutado. Revisar logs grandes."
            
            curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
                -d "chat_id=${TELEGRAM_CHAT_ID}" \
                -d "text=$message" \
                -d "parse_mode=Markdown" > /dev/null
        fi
    fi
}

# ════════════════════════════════════════════════════════
# GENERAR REPORTE DE HOUSEKEEPING
# ════════════════════════════════════════════════════════

generate_report() {
    log "📊 Generando reporte..."
    
    report_file="$LOGS_DIR/housekeeping-report-$(date +%Y-%m-%d).txt"
    
    {
        echo "╔═══════════════════════════════════════════════════════╗"
        echo "║  🧹 HOUSEKEEPING REPORT                               ║"
        echo "╚═══════════════════════════════════════════════════════╝"
        echo ""
        echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
        echo "LOGS PRINCIPALES:"
        echo "───────────────────────────────────────────────────────"
        ls -lhS "$LOGS_DIR"/*.log 2>/dev/null | head -20 | awk '{printf "%-40s %s\n", $9, $5}' | sed 's|.*/||'
        echo ""
        echo "ESPACIO EN DISCO:"
        echo "───────────────────────────────────────────────────────"
        df -h "$HOME" | tail -1 | awk '{printf "Usado: %s | Disponible: %s\n", $5, $4}'
        echo ""
        echo "ESTADO: ✅ COMPLETADO"
    } > "$report_file"
    
    log "  📝 Reporte guardado: $(basename $report_file)"
}

# ════════════════════════════════════════════════════════
# EJECUCIÓN PRINCIPAL
# ════════════════════════════════════════════════════════

rotate_large_logs
cleanup_old_logs
cleanup_temp_files
check_disk_space
generate_report

log ""
log "╔═══════════════════════════════════════════════════════╗"
log "║  ✅ HOUSEKEEPING COMPLETED                            ║"
log "╚═══════════════════════════════════════════════════════╝"
log ""
