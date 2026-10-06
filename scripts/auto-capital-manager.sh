#!/bin/bash
# ════════════════════════════════════════════════════════
# 🤖 AUTO CAPITAL MANAGER - GESTIÓN AUTOMÁTICA DE CAPITAL
# ════════════════════════════════════════════════════════
# Optimizado: menos subprocesos, lock file, fallback venv,
# timeout en API, dry-run y manejo de errores robusto.
# ════════════════════════════════════════════════════════

set -euo pipefail

WORKSPACE="${HOME}/.openclaw/workspace"
CONFIG_FILE="${WORKSPACE}/config/capital-config.sh"
LOG_FILE="${HOME}/.openclaw/logs/auto-capital-manager.log"
PROGRESS_FILE="${WORKSPACE}/crypto-bots/capital-manager-progress.json"
TRADE_HISTORY="${WORKSPACE}/crypto-bots/trade-history.json"
LOCK_FILE="${WORKSPACE}/crypto-bots/.auto-capital-manager.lock"
DRY_RUN="${DRY_RUN:-0}"

# Timeout para llamadas HTTP
HTTP_TIMEOUT="${HTTP_TIMEOUT:-8}"

# ════════════════════════════════════════════════════════
# ⚙️ CONFIGURACIÓN INTELIGENTE
# ════════════════════════════════════════════════════════

WINRATE_EXCELLENT=95
WINRATE_GOOD=85
WINRATE_REGULAR=75
WINRATE_BAD=70

# ────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────

_python() {
  if [ -x "${WORKSPACE}/venv/bin/python3" ]; then
    "${WORKSPACE}/venv/bin/python3" "$@"
  else
    python3 "$@"
  fi
}

log() {
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[${ts}] $1" | tee -a "${LOG_FILE}"
}

require_config() {
  if [ ! -f "${CONFIG_FILE}" ]; then
    log "❌ CONFIG_FILE no existe: ${CONFIG_FILE}"
    return 1
  fi
  return 0
}

acquire_lock() {
  if [ -f "${LOCK_FILE}" ]; then
    local pid
    pid="$(cat "${LOCK_FILE}" 2>/dev/null || true)"
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
      log "⏳ Lock activo (PID ${pid}), abortando para evitar corrida concurrente"
      return 1
    else
      log "🧹 Lock huérfano detectado, limpiando"
      rm -f "${LOCK_FILE}"
    fi
  fi
  echo $$ > "${LOCK_FILE}"
  return 0
}

release_lock() {
  rm -f "${LOCK_FILE}"
}

# ────────────────────────────────────────────────────────
# IO / parsing
# ────────────────────────────────────────────────────────

get_current_position() {
  require_config || { echo "15"; return; }
  local pos
  pos="$(grep -E '^TRADE_POSITION_PERCENT=' "${CONFIG_FILE}" 2>/dev/null | head -n1 | cut -d'=' -f2- | tr -d '"' | tr -d '#' | awk '{print $1}')" || true
  if [[ ! "${pos}" =~ ^[0-9]+$ ]]; then
    echo "15"
  else
    echo "${pos}"
  fi
}

# Single Python call: winrate + usdt balance
get_win_rate_and_balance() {
  _python - <<'PY'
import json, os, sys, time, hmac, hashlib
from urllib.request import Request, urlopen
from urllib.error import URLError

trade_history = os.environ.get("TRADE_HISTORY", "")
http_timeout = int(os.environ.get("HTTP_TIMEOUT", "8"))

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

total = wins = 0
if trade_history and os.path.exists(trade_history):
    data = read_json(trade_history)
    if isinstance(data, dict):
        total = int(data.get("totalTrades", 0) or 0)
        wins = int(data.get("totalWins", 0) or 0)
winrate = round((wins / total) * 100, 2) if total > 0 else 0.0

usdt = 0.0
key_path = os.path.expanduser("~/.openclaw/secrets/binance.env")
if os.path.exists(key_path):
    api_key = api_secret = ""
    try:
        with open(key_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("BINANCE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                elif line.startswith("BINANCE_API_SECRET="):
                    api_secret = line.split("=", 1)[1].strip()
    except Exception:
        pass
    if api_key and api_secret:
        try:
            timestamp = int(time.time() * 1000)
            params = f"timestamp={timestamp}"
            signature = hmac.new(api_secret.encode(), params.encode(), hashlib.sha256).hexdigest()
            req = Request(
                f"https://api.binance.com/api/v3/account?{params}&signature={signature}",
                headers={"X-MBX-APIKEY": api_key},
            )
            with urlopen(req, timeout=http_timeout) as resp:
                account = json.loads(resp.read().decode("utf-8", errors="replace"))
            for bal in account.get("balances", []):
                if bal.get("asset") == "USDT":
                    usdt = float(bal.get("free", 0)) + float(bal.get("locked", 0))
                    break
        except Exception:
            usdt = 0.0
print(f"{winrate}|{round(usdt, 2)}")
PY
}

calculate_optimal_position() {
  local capital="$1"
  local winrate="${2:-0}"

  # Bash-native calculation (no subprocess)
  local optimal=20
  if (( capital < 1000 )); then
    optimal=15
  elif (( capital < 2000 )); then
    optimal=22
  elif (( capital < 3000 )); then
    optimal=25
  elif (( capital < 5000 )); then
    optimal=28
  else
    optimal=30
  fi

  # Adjust by winrate
  if awk -v w="${winrate}" 'BEGIN{exit !(w < 70)}'; then
    if (( optimal > 15 )); then optimal=$((optimal - 5)); fi
  elif awk -v w="${winrate}" 'BEGIN{exit !(w > 95)}'; then
    if (( optimal < 30 )); then optimal=$((optimal + 2)); fi
  fi

  # Clamp
  if (( optimal < 15 )); then optimal=15; fi
  if (( optimal > 30 )); then optimal=30; fi

  echo "${optimal}"
}

update_config() {
  local new_position="$1"
  local action="${2:-UPDATE}"

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "🧪 dry-run: no se actualiza ${CONFIG_FILE} -> ${new_position}% (${action})"
    return 0
  fi

  if [ ! -f "${CONFIG_FILE}" ]; then
    log "❌ No se actualiza config: falta ${CONFIG_FILE}"
    return 1
  fi

  sed -i.bak -E "s/^TRADE_POSITION_PERCENT=[0-9]+/TRADE_POSITION_PERCENT=${new_position}/" "${CONFIG_FILE}"

  local dynamic_config="${WORKSPACE}/crypto-bots/dynamic-config.env"
  if [ -f "${dynamic_config}" ]; then
    sed -i.bak -E "s/^export POSITION_SIZE=[0-9]+/export POSITION_SIZE=${new_position}/" "${dynamic_config}"
  fi

  log "✅ Position size actualizado: ${new_position}% (${action})"
}

# ✅ BUG #9/#10 FIX: Source centralized notify.sh
source "$WORKSPACE/crypto-bots/notify.sh" 2>/dev/null || true

save_progress() {
  local position="$1"
  local winrate="$2"
  local capital="$3"
  local action="$4"
  local reason="$5"

  local reason_escaped action_escaped
  reason_escaped="$(printf '%s' "${reason}" | sed 's/"/\\\"/g' | tr -d '\n')"
  action_escaped="$(printf '%s' "${action}" | sed 's/"/\\\"/g')"

  cat > "${PROGRESS_FILE}" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "position_size": ${position},
  "win_rate": ${winrate},
  "total_capital": ${capital},
  "last_action": "${action_escaped}",
  "reason": "${reason_escaped}",
  "history": []
}
EOF
}

# ✅ JSONL: Log de decisiones del capital manager
CAPITAL_LOG="$HOME/.openclaw/logs/auto-capital-adjust.log"

save_progress() {
  local position="$1"
  local winrate="$2"
  local capital="$3"
  local action="$4"
  local reason="$5"

  local reason_escaped action_escaped
  reason_escaped="$(printf '%s' "${reason}" | sed 's/"/\\"/g' | tr -d '\n')"
  action_escaped="$(printf '%s' "${action}" | sed 's/"/\\"/g')"

  # ✅ JSONL: Log estructurado de decisión capital
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "{\"timestamp\":\"$ts\",\"event\":\"capital.adjust\",\"action\":\"$action_escaped\",\"position_size\":$position,\"win_rate\":$winrate,\"total_capital\":\"$capital\",\"reason\":\"$reason_escaped\"}" >> "$CAPITAL_LOG" 2>/dev/null || true

  cat > "${PROGRESS_FILE}" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "position_size": ${position},
  "win_rate": ${winrate},
  "total_capital": ${capital},
  "last_action": "${action_escaped}",
  "reason": "${reason_escaped}",
  "history": []
}
EOF
}

# ────────────────────────────────────────────────────────
# Recomendación con memoria
# ────────────────────────────────────────────────────────

decide_position() {
  local current="$1"
  local optimal="$2"
  local diff=$((current - optimal))

  if (( diff > 5 )); then
    local reason="Position actual (${current}%) muy alto para capital/USDT disponible"
    echo "DECREASE|${optimal}|${reason}"
  elif (( diff < -5 )); then
    local reason="Position actual (${current}%) bajo para capital/USDT disponible"
    echo "INCREASE|${optimal}|${reason}"
  elif (( diff > 0 )); then
    echo "DECREASE_SMALL|${optimal}|Ajuste menor a la baja"
  elif (( diff < 0 )); then
    echo "INCREASE_SMALL|${optimal}|Ajuste menor al alza"
  else
    echo "MAINTAIN|${current}|Position óptimo ya configurado"
  fi
}

# ────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────

main() {
  log "╔═══════════════════════════════════════════════════════╗"
  log "║  🤖 AUTO CAPITAL MANAGER - ANÁLISIS AUTOMÁTICO       ║"
  log "╚═══════════════════════════════════════════════════════╝"

  if ! acquire_lock; then
    exit 1
  fi
  trap release_lock EXIT

  current_win_rate=""
  usdt_balance=""
  IFS='|' read -r current_win_rate usdt_balance < <(get_win_rate_and_balance)
  current_win_rate="${current_win_rate:-0}"
  usdt_balance="${usdt_balance:-0}"

  CURRENT_POSITION="$(get_current_position)"

  log ""
  log "=== MÉTRICAS ACTUALES ==="
  log "Position Size: ${CURRENT_POSITION}%"
  log "Win Rate: ${current_win_rate}%"
  log "Balance USDT Disponible: ${usdt_balance} USDT"
  log ""

  optimal_position="$(calculate_optimal_position "$(printf "%.0f" "${usdt_balance}")" "$(printf "%.0f" "${current_win_rate}")")"

  log "=== ANÁLISIS DEL BOT ==="
  log "Position ÓPTIMO calculado: ${optimal_position}%"
  log ""

  decision_line="$(decide_position "${CURRENT_POSITION}" "${optimal_position}")"
  ACTION="$(printf '%s' "${decision_line}" | cut -d'|' -f1)"
  NEW_POSITION="$(printf '%s' "${decision_line}" | cut -d'|' -f2)"
  REASON="$(printf '%s' "${decision_line}" | cut -d'|' -f3-)"

  log "=== DECISIÓN DEL BOT ==="
  log "Acción: ${ACTION}"
  log "Position anterior: ${CURRENT_POSITION}%"
  log "Position nuevo: ${NEW_POSITION}%"
  log "Razón: ${REASON}"
  log ""

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "🧪 DRY-RUN: no se ejecuta update_config ni se envían alertas"
  fi

  if [ "${ACTION}" != "MAINTAIN" ]; then
    update_config "${NEW_POSITION}" "${ACTION}"

    if [[ "${DRY_RUN}" != "1" ]]; then
      if [[ "${ACTION}" == INCREASE* ]]; then
        notify "AUTO_CAPITAL" "📈 CAPITAL UP - ${NEW_POSITION}% position
USDT: ${usdt_balance} | WR: ${current_win_rate}%
${CURRENT_POSITION}% → ${NEW_POSITION}% ✅"
      else
        notify "AUTO_CAPITAL" "📉 CAPITAL DOWN - ${NEW_POSITION}% position
USDT: ${usdt_balance} | WR: ${current_win_rate}%
${CURRENT_POSITION}% → ${NEW_POSITION}% 🛡️"
      fi
    fi
  else
    log "✅ Position óptimo ya configurado (USDT disponible: ${usdt_balance})"
  fi

  save_progress "${NEW_POSITION}" "${current_win_rate}" "${usdt_balance}" "${ACTION}" "${REASON}"

  log ""
  log "✅ Progreso guardado en ${PROGRESS_FILE}"
  log ""

  echo ""
  echo "╔═══════════════════════════════════════════════════════╗"
  echo "║  📋 RESUMEN FINAL                                     ║"
  echo "╚═══════════════════════════════════════════════════════╝"
  echo ""
  echo "  Position Size: ${NEW_POSITION}%"
  echo "  Win Rate: ${current_win_rate}%"
  echo "  USDT Disponible: ${usdt_balance} USDT"
  echo "  Acción: ${ACTION}"
  echo "  Razón: ${REASON}"
  echo ""
  echo "╔═══════════════════════════════════════════════════════╗"
  echo "║  ✅ ANÁLISIS AUTOMÁTICO COMPLETADO                   ║"
  echo "╚═══════════════════════════════════════════════════════╝"
}

main "$@"
