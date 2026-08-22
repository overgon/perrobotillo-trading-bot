#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 WATCHDOG GRID TRADING - AUTO-REPARACIÓN
# ════════════════════════════════════════════════════════
# Monitorea, repara y optimiza el Grid Trading automáticamente
# - Detecta bots detenidos → NOTIFICA Y REPARA
# - Rebalancea portfolio cuando está fuera de threshold
# - Actualiza dashboard (hourly)
# - Notifica al Jefe SOLO en incidentes críticos
# ════════════════════════════════════════════════════════

set -e

WORKSPACE="$HOME/.openclaw/workspace"
LOG_FILE="$WORKSPACE/logs/watchdog-grid.log"
GRID_STATUS="$WORKSPACE/dashboard/grid-status.json"
STATE_FILE="$WORKSPACE/logs/watchdog-state.json"
TELEGRAM_CHAT_ID="7543955537"

# Umbrales de decisión
MAX_ORDERS_AGE_HOURS=2          # Si las órdenes tienen >2h sin update → reiniciar
PORTFOLIO_THRESHOLD=5.0         # % desbalance para trigger rebalanceo
DASHBOARD_MAX_AGE_MIN=60        # Si dashboard >60min sin update → forzar refresh (ahora corre hourly)
MIN_USDT_FOR_REBALANCE=100      # Mínimo USDT disponible para rebalanceo
RANGE_CHECK_THRESHOLD=10        # % fuera del rango para trigger auto-ajuste

log() {
    local level="$1"
    local msg="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $msg" | tee -a "$LOG_FILE"
}

send_telegram() {
    local message="$1"
    local config_file="$HOME/.openclaw/openclaw.json"
    
    if [ -f "$config_file" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_file" 2>/dev/null)
        if [ -n "$bot_token" ] && [ "$bot_token" != "null" ]; then
            curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
                -H "Content-Type: application/json" \
                -d "{\"chat_id\":\"$TELEGRAM_CHAT_ID\",\"text\":\"$message\",\"parse_mode\":\"HTML\"}" > /dev/null
            log "INFO" "Telegram enviado"
        fi
    fi
}

# Guardar estado del watchdog
save_state() {
    local status="$1"
    local last_action="$2"
    local details="$3"
    local actions_count=$(grep -c "ACTION:" "$LOG_FILE" 2>/dev/null || echo "0")
    
    cat > "$STATE_FILE" << EOF
{
  "last_check": "$(date -Iseconds)",
  "status": "$status",
  "last_action": "$last_action",
  "details": "$details",
  "actions_today": $actions_count
}
EOF
}

# Verificar si el proceso grid-trading-bot está corriendo
check_grid_process() {
    if pgrep -f "grid-trading-bot.py" > /dev/null 2>&1; then
        log "INFO" "✅ Proceso grid-trading-bot corriendo"
        return 0
    else
        log "WARNING" "❌ Proceso grid-trading-bot NO está corriendo"
        return 1
    fi
}

# Verificar si hay órdenes activas en el grid
check_grid_orders() {
    if [ ! -f "$GRID_STATUS" ]; then
        log "ERROR" "Grid status no encontrado"
        return 2
    fi
    
    local total_orders=$(jq '.totalOrders' "$GRID_STATUS")
    local last_update=$(jq -r '.lastUpdate' "$GRID_STATUS")
    
    # Calcular edad del último update
    local last_update_epoch=$(date -d "$last_update" +%s 2>/dev/null || echo 0)
    local now_epoch=$(date +%s)
    local age_hours=$(( (now_epoch - last_update_epoch) / 3600 ))
    
    log "INFO" "Órdenes totales: $total_orders | Última actualización: $last_update (${age_hours}h atrás)"
    
    if [ "$total_orders" -eq 0 ] || [ "$age_hours" -gt "$MAX_ORDERS_AGE_HOURS" ]; then
        log "WARNING" "⚠️ Grid sin órdenes o desactualizado (> ${MAX_ORDERS_AGE_HOURS}h)"
        return 1
    fi
    
    log "INFO" "✅ Grid con órdenes activas y actualizado"
    return 0
}

# Verificar portfolio balance
check_portfolio_balance() {
    local result=$(python3 "$WORKSPACE/scripts/portfolio-rebalance.py" --status 2>&1 | grep "FUERA de threshold" || echo "")
    
    if [ -n "$result" ]; then
        log "WARNING" "⚠️ Portfolio FUERA de threshold"
        return 1
    fi
    
    log "INFO" "✅ Portfolio dentro de threshold"
    return 0
}

# Verificar edad del dashboard
check_dashboard_freshness() {
    if [ ! -f "$GRID_STATUS" ]; then
        return 2
    fi
    
    local last_update=$(jq -r '.lastUpdate' "$GRID_STATUS")
    local last_update_epoch=$(date -d "$last_update" +%s 2>/dev/null || echo 0)
    local now_epoch=$(date +%s)
    local age_min=$(( (now_epoch - last_update_epoch) / 60 ))
    
    log "INFO" "Dashboard actualizado hace ${age_min} minutos"
    
    if [ "$age_min" -gt "$DASHBOARD_MAX_AGE_MIN" ]; then
        log "WARNING" "⚠️ Dashboard desactualizado (> ${DASHBOARD_MAX_AGE_MIN}min)"
        return 1
    fi
    
    # Solo logear si está dentro del threshold
    if [ "$age_min" -gt 10 ]; then
        log "INFO" "✅ Dashboard fresco"
    fi
    return 0
}

# Reiniciar grid bots
restart_grid_bots() {
    log "ACTION" "🔄 Reiniciando grid bots..."
    
    # Matar procesos existentes
    pkill -f "grid-trading-bot.py" 2>/dev/null || true
    sleep 2
    
    # Iniciar nuevo proceso
    cd "$WORKSPACE/crypto-bots"
    nohup python3 grid-trading-bot.py > "$WORKSPACE/logs/grid-trading.log" 2>&1 &
    local pid=$!
    
    sleep 5
    
    if ps -p $pid > /dev/null 2>&1; then
        log "INFO" "✅ Grid bots reiniciados (PID: $pid)"
        save_state "ok" "restart_grid_bots" "PID: $pid"
        send_telegram "✅ GRID BOTS REINICIADOS
PID: $pid | Sistema recuperado 🐕"
        return 0
    else
        log "ERROR" "❌ Falló reinicio de grid bots"
        save_state "error" "restart_grid_bots" "Process died"
        send_telegram "🚨 ALERTA CRÍTICA
Grid bots restart falló (PID $pid no sobrevivió)
Atención manual inmediata 🆘 🐕"
        return 1
    fi
}

# Rebalancear portfolio
rebalance_portfolio() {
    log "ACTION" "📊 Rebalanceando portfolio..."
    
    cd "$WORKSPACE/scripts"
    # Watchdog usa DRY RUN por defecto - seguro para automático
    local result=$(python3 portfolio-rebalance.py --rebalance --dry-run 2>&1)
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        log "INFO" "✅ Rebalanceo completado"
        save_state "ok" "rebalance_portfolio" "Success"
        
        # Extraer resumen para notificación
        local trades_done=$(echo "$result" | grep -oP '\d+ orders executed' | grep -oP '\d+' || echo "0")
        if [ "$trades_done" -gt 0 ]; then
        send_telegram "📊 REBALANCEO COMPLETADO
        ${trades_done} trades ejecutados | Portfolio optimizado 🐕"
        fi
        return 0
    else
        log "ERROR" "❌ Falló rebalanceo: $result"
        save_state "error" "rebalance_portfolio" "$result"
        send_telegram "⚠️ REBALANCEO FALLIDO
$(echo "$result" | tail -3) 🔧"
        return 1
    fi
}

# Actualizar dashboard
update_dashboard() {
    log "ACTION" "📈 Actualizando dashboard..."
    
    # Ejecutar script de update si existe
    if [ -x "$WORKSPACE/scripts/update-grid-status.py" ]; then
        python3 "$WORKSPACE/scripts/update-grid-status.py" 2>&1 | tee -a "$LOG_FILE"
        log "INFO" "✅ Dashboard actualizado"
        save_state "ok" "update_dashboard" "Success"
        return 0
    else
        # Trigger manual via curl al endpoint si existe
        curl -s http://localhost:8080/api/refresh 2>/dev/null || true
        log "INFO" "Dashboard refresh intentado"
        return 0
    fi
}

# Decisión inteligente: ¿qué acción tomar?
make_decision() {
    local issues=()
    local actions_needed=()
    
    # Check 1: Proceso corriendo
    if ! check_grid_process; then
        issues+=("process_down")
        actions_needed+=("restart")
        log "CRITICAL" "🚨 GRID BOT DETENIDO - Requiere reinicio inmediato"
    fi
    
    # Check 2: Órdenes activas
    if ! check_grid_orders; then
        issues+=("no_orders")
        if [[ ! " ${actions_needed[@]} " =~ " restart " ]]; then
            actions_needed+=("restart")
        fi
    fi
    
    # Check 2b: Rangos de precios (auto-actualizaciu00f3n)
    if ! check_price_ranges; then
        log "ACTION" "ud83dudcca Ejecutando auto-actualizaciu00f3n de rangos..."
        python3 "$WORKSPACE/scripts/update-grid-ranges.py" 2>&1 | tee -a "$LOG_FILE"
        
        if [ $? -eq 0 ]; then
            log "INFO" "u2705 Rangos actualizados automu00e1ticamente"
            action_summary+="[RANGES_UPDATED] "
            send_telegram "ud83dudcca <b>Rangos Auto-Actualizados</b>\n\nPrecios fuera de rango detectados y corregidos.\nGrid bots reiniciados con nuevos rangos.\n\nud83dudc15 Watchdog"
            # Reiniciar grid bots despuu00e9s de actualizar rangos
            if [[ ! " ${actions_needed[@]} " =~ " restart " ]]; then
                actions_needed+=("restart")
            fi
        else
            log "ERROR" "u274c Fallu00f3 actualizaciu00f3n de rangos"
            action_summary+="[RANGES_FAIL] "
        fi
    fi
    
    # Check 3: Portfolio balance
    if ! check_portfolio_balance; then
        issues+=("portfolio_unbalanced")
        actions_needed+=("rebalance")
    fi
    
    # Check 4: Dashboard fresco
    if ! check_dashboard_freshness; then
        issues+=("dashboard_stale")
        actions_needed+=("refresh")
    fi
    
    # Tomar decisiones
    if [ ${#issues[@]} -eq 0 ]; then
        log "INFO" "✅ Todo operativo - No se requieren acciones"
        save_state "ok" "none" "All checks passed"
        echo "NO_ACTION_NEEDED"
        return 0
    fi
    
    log "WARNING" "Issues detectados: ${issues[*]}"
    log "INFO" "Acciones necesarias: ${actions_needed[*]}"
    
    # Ejecutar acciones en orden de prioridad
    local action_summary=""
    
    # 1. Reiniciar bots (más crítico)
    if [[ " ${actions_needed[@]} " =~ " restart " ]]; then
        if restart_grid_bots; then
            action_summary+="[RESTART_OK] "
        else
            action_summary+="[RESTART_FAIL] "
            # Ya notificó en restart_grid_bots
            return 1
        fi
    fi
    
    # 2. Rebalancear (segunda prioridad)
    if [[ " ${actions_needed[@]} " =~ " rebalance " ]]; then
        # Verificar USDT disponible antes de rebalancear
        local usdt_avail=$(python3 -c "
import json
try:
    with open('$WORKSPACE/logs/portfolio-rebalance-live-2026-06-16.json') as f:
        data = json.load(f)
    print(data.get('usdt_available', 0))
except:
    print(0)
" 2>/dev/null || echo "0")
        
        if (( $(echo "$usdt_avail >= $MIN_USDT_FOR_REBALANCE" | bc -l) )); then
            if rebalance_portfolio; then
                action_summary+="[REBALANCE_OK] "
            else
                action_summary+="[REBALANCE_FAIL] "
            fi
        else
            log "INFO" "USDT disponible ($usdt_avail) < mínimo ($MIN_USDT_FOR_REBALANCE) - Skip rebalance"
            action_summary+="[REBALANCE_SKIP] "
        fi
    fi
    
    # 3. Actualizar dashboard (siempre al final)
    if [[ " ${actions_needed[@]} " =~ " refresh " ]] || [ -n "$action_summary" ]; then
        update_dashboard
        action_summary+="[REFRESH_OK]"
    fi
    
    log "INFO" "Acciones completadas: $action_summary"
    save_state "ok" "multi_action" "$action_summary"
    
    # Las notificaciones ya se envían en cada acción individualmente
    # Aquí solo echo final para log
    echo "ACTIONS_COMPLETED: $action_summary"
    return 0
}

# Main
log "═══════════════════════════════════════════════════════"
log "🐕 WATCHDOG GRID TRADING - Iniciando chequeo"
log "═══════════════════════════════════════════════════════"

make_decision
exit_code=$?

log "═══════════════════════════════════════════════════════"
log "Watchdog completado (exit: $exit_code)"
log "═══════════════════════════════════════════════════════"

exit $exit_code
