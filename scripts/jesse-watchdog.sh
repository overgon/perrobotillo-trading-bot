#!/bin/bash
# ════════════════════════════════════════════════════════
# 🤖 JESSE AI - WATCHDOG / AUTO-ARRANCE
# ════════════════════════════════════════════════════════
# Arranca Jesse si está caído. Idempotente: si ya responde
# en el puerto 9000 no hace nada.
# Uso: @reboot + */5 * * * * desde cron
# ════════════════════════════════════════════════════════

JESSE_DIR="/home/overgon/work/perrobotillo-trading-bot"
JESSE_BIN="$JESSE_DIR/venv-jesse/bin/jesse"
LOG="/home/overgon/.openclaw/logs/jesse-watchdog.log"
PORT=9000

mkdir -p /home/overgon/.openclaw/logs

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

responde() {
    curl -s -o /dev/null --connect-timeout 5 "http://127.0.0.1:$PORT/" 2>/dev/null
}

if responde; then
    log "✅ Jesse ONLINE (puerto $PORT)"
    exit 0
fi

# Hay proceso pero sin respuesta: darle un margen de arranque antes de matar
if pgrep -f 'venv-jesse/bin/jesse run' >/dev/null 2>&1; then
    log "⚠️ Proceso Jesse presente sin respuesta — esperando 25s de gracia"
    sleep 25
    if responde; then
        log "✅ Jesse ONLINE tras la espera"
        exit 0
    fi
    log "🔧 Jesse no respondió — reiniciando"
    pkill -f 'venv-jesse/bin/jesse run' 2>/dev/null
    sleep 5
fi

log "🔧 Iniciando Jesse..."

# Esperar a PostgreSQL (hasta ~60s) para no arrancar en carrera con el boot
for i in $(seq 1 30); do
    if (echo > /dev/tcp/127.0.0.1/5432) 2>/dev/null; then
        break
    fi
    sleep 2
done

cd "$JESSE_DIR" || exit 1
nohup "$JESSE_BIN" run >> "$JESSE_DIR/jesse.log" 2>&1 &
sleep 20

if responde; then
    log "✅ Jesse iniciado y respondiendo en puerto $PORT"
else
    log "❌ Jesse NO respondió tras el arranque (revisar $JESSE_DIR/jesse.log)"
fi
