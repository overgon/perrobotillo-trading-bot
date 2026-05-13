#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO DASHBOARD - WATCHDOG V2.1
# ════════════════════════════════════════════════════════
# Monitorea dashboard + ngrok y notifica fallas por Telegram
# Ejecución: Cada 1 minuto desde cron
# ════════════════════════════════════════════════════════

DASHBOARD_DIR="$HOME/.openclaw/workspace/dashboard"
LOG_FILE="$HOME/.openclaw/logs/dashboard-watchdog.log"
PID_FILE="/tmp/dashboard.pid"
PORT=8080
NGROK_LOG="/tmp/ngrok.log"
TELEGRAM_SENT_FILE="/tmp/watchdog-telegram-sent.txt"

# Configuración de Telegram
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
            log "📱 Telegram enviado"
            return 0
        fi
    fi
    log "⚠️  No se pudo enviar Telegram (config faltante)"
    return 1
}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "$1"
}

# Verificar si el dashboard responde
check_dashboard() {
    if curl -s http://localhost:$PORT/api/status > /dev/null 2>&1; then
        return 0  # Dashboard está funcionando
    else
        return 1  # Dashboard no responde
    fi
}

# Verificar si ngrok está funcionando
check_ngrok() {
    # Verificar si ngrok está corriendo
    if ! pgrep -f "ngrok" > /dev/null 2>&1; then
        return 1  # ngrok no está corriendo
    fi
    
    # Verificar si la API de ngrok responde
    local tunnels=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null)
    if [ -z "$tunnels" ] || [ "$tunnels" = "null" ]; then
        return 1  # ngrok API no responde
    fi
    
    # Verificar si hay un tunnel activo
    local public_url=$(echo "$tunnels" | jq -r '.tunnels[0].public_url // empty' 2>/dev/null)
    if [ -z "$public_url" ]; then
        return 1  # No hay tunnel activo
    fi
    
    # Verificar errores recientes en el log de ngrok
    if [ -f "$NGROK_LOG" ]; then
        local recent_errors=$(tail -20 "$NGROK_LOG" 2>/dev/null | grep -c "ERR_NGROK\|failed to start tunnel")
        if [ "$recent_errors" -gt 0 ]; then
            return 1  # Hay errores recientes
        fi
    fi
    
    return 0  # ngrok está funcionando
}

# Matar procesos del dashboard
kill_dashboard() {
    pkill -9 -f "python.*app.py" 2>/dev/null
    sleep 2
}

# Iniciar el dashboard
start_dashboard() {
    cd "$DASHBOARD_DIR"
    nohup python3 app.py > /tmp/dashboard.log 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"
    log "✅ Dashboard iniciado (PID: $pid)"
    sleep 4
    
    if check_dashboard; then
        log "✅ Dashboard verificado - Respondiendo en puerto $PORT"
        return 0
    else
        log "❌ Dashboard no responde después de iniciar"
        return 1
    fi
}

# Reiniciar ngrok
restart_ngrok() {
    log "🔄 Reiniciando ngrok..."
    
    # Matar ngrok existente
    pkill -9 ngrok 2>/dev/null
    sleep 2
    
    # Iniciar ngrok
    cd "$DASHBOARD_DIR"
    nohup ngrok http 8080 > "$NGROK_LOG" 2>&1 &
    local ngrok_pid=$!
    log "✅ Ngrok iniciado (PID: $ngrok_pid)"
    
    sleep 8
    
    if check_ngrok; then
        log "✅ Ngrok verificado - Tunnel activo"
        return 0
    else
        log "❌ Ngrok no se pudo iniciar correctamente"
        return 1
    fi
}

# Enviar alerta de ngrok (con rate limiting)
send_ngrok_alert() {
    local error_type="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Rate limiting: no enviar más de 1 alerta cada 10 minutos
    if [ -f "$TELEGRAM_SENT_FILE" ]; then
        local last_sent=$(cat "$TELEGRAM_SENT_FILE" 2>/dev/null)
        local now=$(date +%s)
        local diff=$((now - last_sent))
        
        if [ "$diff" -lt 600 ]; then
            log "📫 Alerta suprimida (rate limit: ${diff}s desde última alerta)"
            return 0
        fi
    fi
    
    # Guardar timestamp
    date +%s > "$TELEGRAM_SENT_FILE"
    
    # Enviar alerta
    local message="<b>🚨 NGROK FALLÓ</b>

📅 <b>Fecha:</b> $timestamp
🔧 <b>Error:</b> $error_type
🔗 <b>Endpoint:</b> knapsack-divinity-diffuser.ngrok-free.dev

<b>Acciones tomadas:</b>
• Ngrok reiniciado automáticamente
• Dashboard verificado

<b>Recomendación:</b>
Si el problema persiste, reiniciar la RPi5:
<code>sudo reboot</code>

🐕 Perrobotillo Trading Bot"

    send_telegram "$message"
    log "📱 Alerta de ngrok enviada por Telegram"
}

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

log "╔═══════════════════════════════════════════════════════╗"
log "║  🐕 Dashboard Watchdog - Check                        ║"
log "╚═══════════════════════════════════════════════════════╝"

# Verificar dashboard
if check_dashboard; then
    log "✅ Dashboard está ONLINE"
    dashboard_ok=true
else
    log "❌ Dashboard NO RESPONDE"
    dashboard_ok=false
fi

# Verificar ngrok
if check_ngrok; then
    log "✅ Ngrok está ONLINE"
    ngrok_ok=true
else
    log "❌ Ngrok FALLÓ o no responde"
    ngrok_ok=false
fi

# Acciones
if [ "$dashboard_ok" = true ] && [ "$ngrok_ok" = true ]; then
    log "✅ Todo operativo - No se requiere acción"
    
elif [ "$dashboard_ok" = false ] && [ "$ngrok_ok" = true ]; then
    # Solo dashboard caído
    log "🔧 Dashboard caído, ngrok OK - Reiniciando dashboard..."
    kill_dashboard
    
    if start_dashboard; then
        log "✅ Dashboard reiniciado exitosamente"
    else
        log "❌ ERROR: No se pudo reiniciar el dashboard"
        
        # Enviar alerta crítica
        send_telegram "<b>🚨 CRÍTICO: Dashboard CAÍDO</b>

📅 <b>Fecha:</b> $(date '+%Y-%m-%d %H:%M:%S')
❌ <b>Estado:</b> Dashboard no responde
🔧 <b>Acción:</b> Reinicio automático fallido

<b>Revisar:</b>
• Log: $HOME/.openclaw/logs/dashboard-watchdog.log
• Dashboard: /tmp/dashboard.log

🐕 Perrobotillo Trading Bot"
    fi
    
elif [ "$dashboard_ok" = true ] && [ "$ngrok_ok" = false ]; then
    # Solo ngrok falló (dashboard OK)
    log "🔧 Ngrok falló, dashboard OK - Reiniciando ngrok..."
    
    if restart_ngrok; then
        log "✅ Ngrok reiniciado exitosamente"
        # Enviar alerta informativa
        send_ngrok_alert "Ngrok se cayó pero se reinició automáticamente"
    else
        log "❌ ERROR: No se pudo reiniciar ngrok"
        # Enviar alerta
        send_ngrok_alert "Ngrok falló y NO se pudo reiniciar automáticamente"
    fi
    
elif [ "$dashboard_ok" = false ] && [ "$ngrok_ok" = false ]; then
    # Ambos cayeron
    log "🔧 Ambos cayeron - Reiniciando dashboard primero..."
    kill_dashboard
    
    if start_dashboard; then
        log "✅ Dashboard reiniciado"
        # Ahora intentar con ngrok
        log "🔧 Intentando reiniciar ngrok..."
        
        if restart_ngrok; then
            log "✅ Ngrok reiniciado"
            send_ngrok_alert "Dashboard y Ngrok cayeron, ambos reiniciados"
        else
            log "❌ Ngrok no se pudo reiniciar"
            send_ngrok_alert "Dashboard OK, pero Ngrok FALLÓ después de reinicio"
        fi
    else
        log "❌ Dashboard no se pudo reiniciar"
        send_telegram "<b>🚨 CRÍTICO: Sistema CAÍDO</b>

📅 <b>Fecha:</b> $(date '+%Y-%m-%d %H:%M:%S')
❌ <b>Estado:</b> Dashboard + Ngrok caídos
🔧 <b>Acción:</b> Reinicios fallidos

<b>Acción requerida:</b>
Reiniciar RPi5 manualmente:
<code>sudo reboot</code>

🐕 Perrobotillo Trading Bot"
    fi
fi

log ""
