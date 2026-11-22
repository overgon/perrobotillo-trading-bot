#!/usr/bin/env bash
# ════════════════════════════════════════════════════════
# 🐕 WATCHDOG Perrobotillo — alerta por Telegram si algo esta mal
# ════════════════════════════════════════════════════════
# Corre cada 30 min desde cron. Si todo esta bien NO imprime nada y NO notifica.
# ════════════════════════════════════════════════════════
set -u

WS=/home/overgon/.openclaw/workspace
LOGS=/home/overgon/.openclaw/logs          # lo que escribe el cron (trading-*.log, cron-*.log)
REPO_LOGS="$WS/logs"                        # arbol del repo (trade-*.log, bot_cli_*.log)
NGROK_URL="https://knapsack-divinity-diffuser.ngrok-free.dev"
problems=()

# 1) Dashboard local
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8080/ || echo 000)
[ "$code" != "401" ] && [ "$code" != "200" ] && problems+=("dashboard 8080 responde $code")

# 2) Tunnel ngrok
tun=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$NGROK_URL/" || echo 000)
[ "$tun" != "401" ] && [ "$tun" != "200" ] && problems+=("tunnel ngrok responde $tun")

# 3) Ciclo del bot vivo: los logs cron-*.log deben tener actividad reciente (<=20 min)
now=$(date +%s)
stale=""
shopt -s nullglob
cron_logs=("$LOGS"/cron-*.log)
shopt -u nullglob
if [ ${#cron_logs[@]} -eq 0 ]; then
  problems+=("no existen logs cron-*.log en $LOGS")
else
  for f in "${cron_logs[@]}"; do
    m=$(stat -c %Y "$f")
    age=$(( (now - m) / 60 ))
    [ "$age" -gt 20 ] && stale="$stale $(basename "$f"):${age}m"
  done
fi
[ -n "$stale" ] && problems+=("logs del bot sin actividad:$stale")

# 4) Errores duros en los logs de trade (ultimas 2h), en AMBOS arboles de logs.
#    Antes solo miraba $WS/logs/trade-*.log y el filtro de hora comparaba mal
#    (las lineas empiezan con '[' y la comparacion nunca filtraba).
cutoff=$(date -d '2 hours ago' '+%Y-%m-%d %H')
errs=$(grep -hE "Traceback|CRITICAL|Error de Binance|APIError|Insufficient|pausado por riesgo" \
        "$LOGS"/trading-*.log "$REPO_LOGS"/trade-*.log "$REPO_LOGS"/bot_cli_*.log 2>/dev/null \
      | tail -n 500 | grep -F "$cutoff" | wc -l)
[ "$errs" -gt 0 ] && problems+=("$errs errores duros en las ultimas 2h")

# 5) Modelo de outcome presente
[ ! -f "$WS/ml/outcome_model.pkl" ] && problems+=("falta ml/outcome_model.pkl")

# 6) Circuit Breaker activo (el bot no deberia estar operando)
cb_file="$WS/crypto-bots/dashboard-circuit-breaker-status.json"
if [ -f "$cb_file" ] && grep -q '"circuitBreakerActive": true' "$cb_file" 2>/dev/null; then
  problems+=("CIRCUIT BREAKER ACTIVO (bot pausado)")
fi

if [ ${#problems[@]} -eq 0 ]; then
  exit 0
fi

msg="🚨 WATCHDOG Perrobotillo — $(date '+%Y-%m-%d %H:%M %Z')
$(printf '  • %s\n' "${problems[@]}")"

echo "$msg"

# Notificacion por Telegram (silenciosa si notify.sh no esta)
if [ -f "$WS/crypto-bots/notify.sh" ]; then
  # shellcheck disable=SC1090
  source "$WS/crypto-bots/notify.sh" 2>/dev/null || true
  notify "LIVE_WATCHDOG" "$msg" >/dev/null 2>&1 || true
fi
exit 1
