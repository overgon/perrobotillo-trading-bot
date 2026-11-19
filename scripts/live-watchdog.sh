#!/usr/bin/env bash
# Watchdog del bot Perrobotillo — imprime ALERTA solo si algo esta mal.
# Pensado para correr cada 15-30 min (no_agent): salida vacia = todo bien.
set -u
WS=/home/overgon/.openclaw/workspace
CRON_LOGS=/home/overgon/.openclaw/logs
problems=()

# 1) Dashboard local
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8080/ || echo 000)
[ "$code" != "401" ] && [ "$code" != "200" ] && problems+=("dashboard 8080 responde $code")

# 2) Tunnel ngrok
tun=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://knapsack-divinity-diffuser.ngrok-free.dev/ || echo 000)
[ "$tun" != "401" ] && [ "$tun" != "200" ] && problems+=("tunnel ngrok responde $tun")

# 3) Ciclo del bot vivo: los logs cron-* deben tener actividad reciente (<=20 min)
now=$(date +%s)
stale=""
for f in "$CRON_LOGS"/cron-*.log; do
  [ -e "$f" ] || { stale="$stale $(basename "$f")"; continue; }
  m=$(stat -c %Y "$f")
  age=$(( (now - m) / 60 ))
  [ "$age" -gt 20 ] && stale="$stale $(basename "$f"):${age}m"
done
[ -n "$stale" ] && problems+=("logs del bot sin actividad:$stale")

# 4) Errores duros en los logs de trade (ultimas 2h)
errs=$(grep -hE "Traceback|CRITICAL|Error de Binance|APIError|Insufficient|pausado por riesgo" "$WS"/logs/trade-*.log 2>/dev/null \
       | tail -n 200 | awk -v d="$(date -d '2 hours ago' '+%Y-%m-%d %H')" '$0 >= d' | wc -l)
[ "$errs" -gt 0 ] && problems+=("$errs errores duros en las ultimas 2h")

# 5) Modelo de outcome presente
[ ! -f "$WS/ml/outcome_model.pkl" ] && problems+=("falta ml/outcome_model.pkl")

if [ ${#problems[@]} -eq 0 ]; then
  exit 0
fi
echo "🚨 WATCHDOG Perrobotillo — $(date '+%Y-%m-%d %H:%M %Z')"
for p in "${problems[@]}"; do echo "  • $p"; done
