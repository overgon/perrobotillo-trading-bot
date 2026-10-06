#!/bin/bash
# ════════════════════════════════════════════════════════
# 🔗 Ngrok URL Helper - Perrobotillo
# ════════════════════════════════════════════════════════
# Extrae la URL pública de ngrok desde el log (sin depender
# del puerto 4040 / API de inspección)
# Uso: source ngrok-url.sh && ngrok_get_url
# ════════════════════════════════════════════════════════

NGROK_LOG="${NGROK_LOG:-$HOME/.openclaw/logs/ngrok-stdout.log}"
NGROK_URL_CACHE="${NGROK_URL_CACHE:-/tmp/ngrok-url-cache.txt}"

# Extrae la URL pública más reciente del log de ngrok
ngrok_get_url() {
    local url=""
    # Intentar desde el log de ngrok (patrón: msg="started tunnel" ... url=https://...)
    if [ -f "$NGROK_LOG" ]; then
        url=$(grep -oP 'url=\Khttps://[^ ]+' "$NGROK_LOG" 2>/dev/null | tail -1)
    fi
    # Fallback: desde journalctl si el log no existe o está vacío
    if [ -z "$url" ]; then
        url=$(journalctl -u perrobotillo-ngrok.service --no-pager -n 50 2>/dev/null | grep -oP 'url=\Khttps://[^ ]+' | tail -1)
    fi
    echo "$url"
}

# Refresca y guarda la URL en el cache
ngrok_refresh_url() {
    local url=$(ngrok_get_url)
    if [ -n "$url" ]; then
        echo "$url" > "$NGROK_URL_CACHE"
    fi
    echo "$url"
}

# Lee la URL desde el cache (o refresca si no existe)
ngrok_get_cached_url() {
    if [ -f "$NGROK_URL_CACHE" ] && [ -s "$NGROK_URL_CACHE" ]; then
        cat "$NGROK_URL_CACHE"
    else
        ngrok_refresh_url
    fi
}
