#!/bin/bash
# 🕵️ IP Monitor - Detecta cambios de IP pública con doble provider
# Uso: ./ip-monitor.sh
# Envía alerta solo si la IP cambió (para Binance whitelist)
# Optimizado: 5-min cron, doble provider, retry notificación

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IP_FILE="${SCRIPT_DIR}/last-known-ip.txt"
WORKSPACE="${SCRIPT_DIR}/.."

# 1. Obtener IP pública con PROVIDER PRIMARIO (ipify)
CURRENT_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null)

# 2. Si falla el primario, usar provider secundario (ifconfigme)
if [ -z "$CURRENT_IP" ] || [ "$CURRENT_IP" = "0.0.0.0" ]; then
    CURRENT_IP=$(curl -s --max-time 5 https://api4.ip.works 2>/dev/null)
fi

# 3. Si aún falla, intentar ipinfo.io
if [ -z "$CURRENT_IP" ] || [ "$CURRENT_IP" = "0.0.0.0" ]; then
    CURRENT_IP=$(curl -s --max-time 5 https://ipecho.net/plain 2>/dev/null | tr -d '[:space:]')
fi

if [ -z "$CURRENT_IP" ] || [ "$CURRENT_IP" = "0.0.0.0" ]; then
    echo "[$(date -Iseconds)] ❌ No se pudo obtener IP pública (fallaron 3 providers)"
    exit 1
fi

# Validar formato de IP
if ! echo "$CURRENT_IP" | grep -qE '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'; then
    echo "[$(date -Iseconds)] ❌ IP inválida: $CURRENT_IP"
    exit 1
fi

LAST_IP=""
if [ -f "$IP_FILE" ]; then
    LAST_IP=$(cat "$IP_FILE" | tr -d '[:space:]')
fi

if [ "$CURRENT_IP" != "$LAST_IP" ]; then
    # IP cambió o es primera vez - ACTUALIZAR INMEDIATAMENTE
    echo "$CURRENT_IP" > "$IP_FILE"
    
    if [ -n "$LAST_IP" ]; then
        # ===============================
        # 🚨 CAMBIO DE IP DETECTADO
        # Enviar notificación con RETRY (hasta 3 intentos)
        # ===============================
        
        if [ -f "${WORKSPACE}/crypto-bots/notify.sh" ]; then
            source "${WORKSPACE}/crypto-bots/notify.sh"
        fi
        
        MSG="🚨🚨 CAMBIO DE IP DETECTADO 🚨🚨
📅 Hora: $(date '+%Y-%m-%d %H:%M:%S') CST
📍 Anterior: ${LAST_IP}
📍 Actual: ${CURRENT_IP}
🔐 Verifica Binance IP Whitelist inmediatamente!
⚠️ Si no añades esta IP, el bot no podrá operar."
        
        # Retry loop: 3 intentos con 2 segundos de gap
        SENT=false
        for attempt in 1 2 3; do
            if send_telegram "$MSG" "HTML"; then
                SENT=true
                echo "[$(date -Iseconds)] ✅ Notificación de cambio IP enviada (intento $attempt)"
                break
            else
                echo "[$(date -Iseconds)] ⚠️ Intento $attempt fallido, reintentando..."
                sleep 2
            fi
        done
        
        if [ "$SENT" = "false" ]; then
            echo "[$(date -Iseconds)] ❌❌ FALLÓ envío de notificación de cambio IP tras 3 intentos"
            echo "⚠️  IP cambió de ${LAST_IP} a ${CURRENT_IP} pero NOTIFICACIÓN FALLÓ"
        fi
        
        echo "[$(date -Iseconds)] 🚨🚨 IP CAMBIÓ: ${LAST_IP} → ${CURRENT_IP} 🚨🚨"
    else
        echo "[$(date -Iseconds)] 📝 IP registrada (primera vez): ${CURRENT_IP}"
    fi
else
    # IP no cambió - log silencioso
    echo "[$(date -Iseconds)] ✅ IP estable: ${CURRENT_IP}"
fi
