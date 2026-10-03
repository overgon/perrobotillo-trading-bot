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
NGROK_LOG="$HOME/.openclaw/logs/ngrok-stdout.log"
TELEGRAM_SENT_FILE="/tmp/watchdog-telegram-sent.txt"

# ✅ BUG #9/#10 FIX: Source centralized notify.sh (Markdown parse_mode, --data-urlencode)
WORKSPACE="$HOME/.openclaw/workspace"
source "$WORKSPACE/crypto-bots/notify.sh" 2>/dev/null || true

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "$1"
}

# Verificar si el dashboard responde
check_dashboard() {
    if curl -s --connect-timeout 5 http://localhost:$PORT/api/status > /dev/null 2>&1; then
        return 0  # Dashboard está funcionando
    else
        return 1  # Dashboard no responde
    fi
}

# Extraer URL pública de ngrok desde el log (sin depender del puerto 4040)
get_ngrok_url() {
    local url=""
    if [ -f "$NGROK_LOG" ]; then
        url=$(grep -oP 'url=\Khttps://[^ ]+' "$NGROK_LOG" 2>/dev/null | tail -1)
    fi
    if [ -z "$url" ]; then
        url=$(journalctl -u perrobotillo-ngrok.service --no-pager -n 50 2>/dev/null | grep -oP 'url=\Khttps://[^ ]+' | tail -1)
    fi
    echo "$url"
}

# Verificar si ngrok está funcionando
check_ngrok() {
    # Verificar si ngrok está corriendo
    if ! pgrep -x "ngrok" > /dev/null 2>&1; then
        return 1  # ngrok no está corriendo
    fi

    # Extraer URL pública del log (sin API de inspección en puerto 4040)
    local public_url=$(get_ngrok_url)
    if [ -z "$public_url" ]; then
        # ngrok corre pero aún no registró URL — asumir arranque en curso
        log "⏳ Ngrok en arranque (URL no disponible aún)"
        return 0
    fi

    # ✅ VERIFICAR SI EL TUNNEL RESPONDE (ngrok free tier devuelve 401/403 normalmente)
    local http_status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$public_url" 2>/dev/null)

    # Solo es ERROR si es 502, 503, 504, o timeout (000)
    if [ "$http_status" = "502" ] || [ "$http_status" = "503" ] || [ "$http_status" = "504" ] || [ "$http_status" = "000" ]; then
        log "❌ Ngrok tunnel responde con HTTP $http_status - SERVIDOR CAÍDO"
        return 1  # Tunnel no funciona
    fi

    # 401/403 es NORMAL en ngrok free tier (requiere auth en browser)
    if [ "$http_status" = "401" ] || [ "$http_status" = "403" ]; then
        log "✅ Ngrok tunnel ONLINE (HTTP $http_status - auth requerida, normal en free tier)"
    fi

    # Verificar errores recientes en el log de ngrok
    if [ -f "$NGROK_LOG" ]; then
        local recent_errors=$(tail -30 "$NGROK_LOG" 2>/dev/null | grep -c "ERR_NGROK\|failed to start tunnel\|authentication failed")
        if [ "$recent_errors" -gt 0 ]; then
            return 1  # Hay errores recientes
        fi
    fi

    return 0  # ngrok está funcionando correctamente
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
    pkill -9 -x "ngrok" 2>/dev/null
    sleep 2

    # Iniciar ngrok con config file (inspect: false, tunnel nombrado "dashboard")
    /usr/local/bin/ngrok start dashboard --config=/home/overgon/.config/ngrok/ngrok.yml >> "$NGROK_LOG" 2>&1 &
    local ngrok_pid=$!
    log "✅ Ngrok iniciado (PID: $ngrok_pid) - inspect: false, tunnel: dashboard"

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

    # URL dinámica desde el log
    local current_url=$(get_ngrok_url)
    if [ -z "$current_url" ]; then
        current_url="knapsack-divinity-diffuser.ngrok-free.dev"
    fi

    # Enviar alerta
    local message="**🚨 NGROK FALLÓ**

📅 **Fecha:** $timestamp
🔧 **Error:** $error_type
🔗 **Endpoint:** $current_url

**Acciones tomadas:**
• Ngrok reiniciado automáticamente (inspect: false)
• Dashboard verificado

**Recomendación:**
Si el problema persiste, reiniciar la RPi5:
`sudo reboot`

🐕 Perrobotillo Trading Bot"

    notify "WATCHDOG_NGROK" "$message"
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
        send_telegram "**🚨 CRÍTICO: Dashboard CAÍDO**

📅 **Fecha:** $(date '+%Y-%m-%d %H:%M:%S')
❌ **Estado:** Dashboard no responde
🔧 **Acción:** Reinicio automático fallido

**Revisar:**
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
        send_telegram "**🚨 CRÍTICO: Sistema CAÍDO**

📅 **Fecha:** $(date '+%Y-%m-%d %H:%M:%S')
❌ **Estado:** Dashboard + Ngrok caídos
🔧 **Acción:** Reinicios fallidos

**Acción requerida:**
Reiniciar RPi5 manualmente:
`sudo reboot`

🐕 Perrobotillo Trading Bot"
    fi
fi

log ""
