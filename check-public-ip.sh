#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🌐 PUBLIC IP MONITOR - PERROBOTILLO                  ║
# ║  Monitorea cambios de IP pública y alerta por Telegram ║
# ═══════════════════════════════════════════════════════╝

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS="$HOME/.openclaw/secrets"
LOGS="$HOME/.openclaw/logs"
CONFIG_FILE="$WORKSPACE/crypto-bots/.public_ip"

# ============================================
# 🔧 FUNCIONES DE LOGGING
# ============================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [IP-MONITOR] $1" | tee -a "$LOGS/ip-monitor.log"
}

send_telegram() {
    local message="$1"
    local config_file="$HOME/.openclaw/openclaw.json"
    if [ -f "$config_file" ]; then
        local bot_token=$(jq -r '.channels.telegram.botToken // empty' "$config_file" 2>/dev/null)
        [ -n "$bot_token" ] && [ "$bot_token" != "null" ] && \
            curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
                -H "Content-Type: application/json" \
                -d "{\"chat_id\":\"7543955537\",\"text\":\"$message\",\"parse_mode=HTML\"}" > /dev/null
    fi
}

# ============================================
# 🌐 OBTENER IP PÚBLICA
# ============================================

get_public_ip() {
    # Intentar múltiples servicios para obtener IP pública
    local ip=""
    
    # Método 1: ifconfig.me
    ip=$(curl -s --max-time 5 ifconfig.me 2>/dev/null)
    if [ -n "$ip" ] && [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "$ip"
        return 0
    fi
    
    # Método 2: icanhazip.com
    ip=$(curl -s --max-time 5 icanhazip.com 2>/dev/null)
    if [ -n "$ip" ] && [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "$ip"
        return 0
    fi
    
    # Método 3: api.ipify.org
    ip=$(curl -s --max-time 5 api.ipify.org 2>/dev/null)
    if [ -n "$ip" ] && [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "$ip"
        return 0
    fi
    
    # Todos los métodos fallaron
    echo ""
    return 1
}

# ============================================
# 🎯 MAIN
# ============================================

log "🔍 Verificando IP pública..."

# Obtener IP actual
current_ip=$(get_public_ip)

if [ -z "$current_ip" ]; then
    log "❌ ERROR: No se pudo obtener la IP pública"
    send_telegram "❌ *ALERTA DE IP - ERROR*

🌐 Perrobotillo IP Monitor

⚠️ *No se pudo obtener la IP pública*

Posibles causas:
• Sin conexión a internet
• Servicios de IP caídos

Verificar manualmente:
• https://ifconfig.me
• https://icanhazip.com"
    exit 1
fi

log "✅ IP pública actual: $current_ip"

# Verificar si existe archivo de IP guardada
if [ -f "$CONFIG_FILE" ]; then
    saved_ip=$(cat "$CONFIG_FILE" 2>/dev/null)
    log "📄 IP guardada: $saved_ip"
    
    # Comparar IPs
    if [ "$current_ip" != "$saved_ip" ]; then
        log "🚨 ¡CAMBIO DE IP DETECTADO!"
        log "   Anterior: $saved_ip"
        log "   Actual:   $current_ip"
        
        # Enviar alerta de Telegram
        send_telegram "🚨 *ALERTA DE CAMBIO DE IP*

🌐 Perrobotillo Trading Bot

⚠️ *¡LA IP PÚBLICA HA CAMBIADO!*

📍 IPs:
• Anterior: \`$saved_ip\`
• Actual:   \`$current_ip\`

⚡ *Acción Requerida:*

1. Ir a Binance.com → API Management
2. Seleccionar API Key (pznuUtfQO6...4T1fmB)
3. Edit → IP Whitelist
4. Agregar: \`$current_ip\`
5. Remover IP antigua: \`$saved_ip\`
6. Guardar cambios

⏰ *Importante:*
La API de Binance dejará de funcionar hasta que actualices el whitelist.

_Jefe, necesitas actualizar Binance!_ 🐕"
        
        # Actualizar archivo con nueva IP
        echo "$current_ip" > "$CONFIG_FILE"
        log "✅ Archivo actualizado con nueva IP"
        
        # Verificar API de Binance después del cambio
        log "🧪 Testeando API de Binance..."
        sleep 2  # Esperar un poco
        
        source "$SECRETS/binance.env"
        timestamp=$(date +%s000)
        query="timestamp=${timestamp}&recvWindow=5000"
        signature=$(echo -n "$query" | openssl dgst -sha256 -hmac "$BINANCE_API_SECRET" | awk '{print $2}')
        
        test_result=$(curl -s -X GET "https://api.binance.com/api/v3/account?${query}&signature=${signature}" \
            -H "X-MBX-APIKEY: $BINANCE_API_KEY" 2>/dev/null)
        
        error_code=$(echo "$test_result" | jq -r '.code // empty' 2>/dev/null)
        
        if [ -n "$error_code" ]; then
            log "❌ API de Binance FALLÓ después del cambio de IP"
            log "   Error: $error_code - $(echo "$test_result" | jq -r '.msg // empty')"
            
            send_telegram "⚠️ *API BINANCE - VERIFICACIÓN*

🚨 La API de Binance está fallando:

Error: \`$error_code\`
Mensaje: \`$(echo "$test_result" | jq -r '.msg // empty')\`

Esto confirma que necesitas actualizar el IP whitelist en Binance.

_Jefe, actualiza Binance lo antes posible!_ 🐕"
        else
            log "✅ API de Binance funciona correctamente"
            send_telegram "✅ *API BINANCE - VERIFICADA*

🌐 Después del cambio de IP:

✅ La API de Binance sigue funcionando

Es posible que:
• El whitelist ya estaba actualizado
• O Binance aún no ha aplicado el filtro

Monitorear de cerca los trades.

_Jefe, todo sigue operando!_ 🐕"
        fi
    else
        log "✅ IP sin cambios ($current_ip)"
    fi
else
    log "📝 Primera ejecución - Guardando IP inicial: $current_ip"
    echo "$current_ip" > "$CONFIG_FILE"
    
    send_telegram "✅ *IP MONITOR - ACTIVADO*

🌐 Perrobotillo Trading Bot

✅ Sistema de monitoreo de IP activado

📍 IP inicial guardada: \`$current_ip\`

🔔 Recibirás alertas cuando:
• La IP pública cambie
• La API de Binance falle
• No se pueda obtener la IP

_Primer check completado, jefe!_ 🐕"
fi

log "✅ Verificación completada"
