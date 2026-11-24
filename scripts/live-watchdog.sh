#!/usr/bin/env bash
# ════════════════════════════════════════════════════════
# 🐕 WATCHDOG Perrobotillo — alerta por Telegram si algo esta mal
# ════════════════════════════════════════════════════════
# Corre cada 30 min desde cron.
#
# ANTI-SPAM: cada chequeo tiene una clave estable (dashboard, ngrok,
# cron_stale, hard_errors, missing_model, cb_active...). Se compara el
# conjunto de claves activas contra la pasada anterior y SOLO se notifica
# cuando hay un cambio: un problema nuevo, uno que se recupero, o ambos.
# Un problema persistente NO vuelve a notificarse.
# ════════════════════════════════════════════════════════
set -u

WS=/home/overgon/.openclaw/workspace
LOGS=/home/overgon/.openclaw/logs          # lo que escribe el cron (trading-*.log, cron-*.log)
REPO_LOGS="$WS/logs"                        # arbol del repo (trade-*.log, bot_cli_*.log)
NGROK_URL="https://knapsack-divinity-diffuser.ngrok-free.dev"

STATE_FILE="$HOME/.openclaw/live-watchdog.state"
mkdir -p "$(dirname "$STATE_FILE")"

keys=()
declare -A MSG

# add_problem <clave_estable> <mensaje>
add_problem() {
  keys+=("$1")
  MSG["$1"]="$2"
}

# 1) Dashboard local
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8080/ || echo 000)
if [ "$code" != "401" ] && [ "$code" != "200" ]; then
  add_problem "dashboard" "dashboard 8080 responde $code"
fi

# 2) Tunnel ngrok
tun=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$NGROK_URL/" || echo 000)
if [ "$tun" != "401" ] && [ "$tun" != "200" ]; then
  add_problem "ngrok" "tunnel ngrok responde $tun"
fi

# 3) Ciclo del bot vivo: los logs cron-*.log deben tener actividad reciente (<=20 min)
now=$(date +%s)
stale=""
shopt -s nullglob
cron_logs=("$LOGS"/cron-*.log)
shopt -u nullglob
if [ ${#cron_logs[@]} -eq 0 ]; then
  add_problem "cron_logs_missing" "no existen logs cron-*.log en $LOGS"
else
  for f in "${cron_logs[@]}"; do
    m=$(stat -c %Y "$f")
    age=$(( (now - m) / 60 ))
    [ "$age" -gt 20 ] && stale="$stale $(basename "$f"):${age}m"
  done
fi
[ -n "$stale" ] && add_problem "cron_stale" "logs del bot sin actividad:$stale"

# 4) Errores duros en los logs de trade (ultimas 2h), en AMBOS arboles de logs.
cutoff=$(date -d '2 hours ago' '+%Y-%m-%d %H')
errs=$(grep -hE "Traceback|CRITICAL|Error de Binance|APIError|Insufficient|pausado por riesgo" \
        "$LOGS"/trading-*.log "$REPO_LOGS"/trade-*.log "$REPO_LOGS"/bot_cli_*.log 2>/dev/null \
      | tail -n 500 | grep -F "$cutoff" | wc -l)
[ "$errs" -gt 0 ] && add_problem "hard_errors" "$errs errores duros en las ultimas 2h"

# 5) Modelo de outcome presente
[ ! -f "$WS/ml/outcome_model.pkl" ] && add_problem "missing_model" "falta ml/outcome_model.pkl"

# 6) Circuit Breaker activo (el bot no deberia estar operando)
cb_file="$WS/crypto-bots/dashboard-circuit-breaker-status.json"
if [ -f "$cb_file" ] && grep -q '"circuitBreakerActive": true' "$cb_file" 2>/dev/null; then
  rem=$(grep -oE '"timeRemaining": *"[^"]*"' "$cb_file" 2>/dev/null | sed 's/.*: *"//; s/"$//')
  add_problem "cb_active" "CIRCUIT BREAKER ACTIVO — bot pausado (queda ${rem:-?})"
fi

# ════════════════════════════════════════════════════════
# DEDUP: notificar solo si el conjunto de claves cambió
# ════════════════════════════════════════════════════════
cur="$(printf '%s\n' "${keys[@]}" 2>/dev/null | sort -u | tr '\n' ',')"
prev="$(cat "$STATE_FILE" 2>/dev/null || echo '')"

if [ "$cur" = "$prev" ]; then
  exit 0
fi

added=$(comm -23 <(printf '%s\n' "$cur" | tr ',' '\n' | sed '/^$/d' | sort -u) \
                <(printf '%s\n' "$prev" | tr ',' '\n' | sed '/^$/d' | sort -u) | tr '\n' ' ')
recovered=$(comm -23 <(printf '%s\n' "$prev" | tr ',' '\n' | sed '/^$/d' | sort -u) \
                    <(printf '%s\n' "$cur" | tr ',' '\n' | sed '/^$/d' | sort -u) | tr '\n' ' ')

lines=""
for k in $added; do
  lines="${lines}  • ${MSG[$k]}"$'\n'
done
for k in $recovered; do
  lines="${lines}  ✅ recuperado: $k"$'\n'
done

# Guardar el nuevo estado pase lo que pase
printf '%s' "$cur" > "$STATE_FILE"

if [ -z "$lines" ]; then
  exit 0
fi

msg="🚨 WATCHDOG Perrobotillo — $(date '+%Y-%m-%d %H:%M %Z')
$lines"

echo "$msg"

# Notificacion por Telegram (silenciosa si notify.sh no esta)
if [ -f "$WS/crypto-bots/notify.sh" ]; then
  # shellcheck disable=SC1090
  source "$WS/crypto-bots/notify.sh" 2>/dev/null || true
  notify "LIVE_WATCHDOG" "$msg" >/dev/null 2>&1 || true
fi
exit 1
