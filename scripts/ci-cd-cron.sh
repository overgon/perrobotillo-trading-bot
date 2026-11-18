#!/bin/bash
# ╔═══════════════════════════════════════════════════════════════════╗
# ║  CD PIPELINE — Perrobotillo + Jesse AI  (Issue #66)               ║
# ║  Wrapper NATIVO (sin Docker) para el Raspberry Pi.                ║
# ╚═══════════════════════════════════════════════════════════════════╝
#
# Uso:  ci-cd-cron.sh <daily|optimize|ml-retrain|deploy-gate>
#
#   daily       Mon-Sat 05:05 → backtest 90d + CI gate + alerta Telegram
#   optimize    Dom     03:00 → Optuna 50 trials
#   ml-retrain  Dom     05:00 → reentrenamiento RF por moneda (Jesse)
#   deploy-gate Dom     07:00 → lee el gate y reporta (no auto-commit)
#
# Todas las salidas quedan en /home/overgon/.openclaw/logs/ci-cd-<fase>.log
# ═══════════════════════════════════════════════════════════════════

set -uo pipefail

WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
PYTHON="$WORKSPACE/venv-jesse/bin/python3"
LOG_DIR="/home/overgon/.openclaw/logs"
LOG_FILE="$LOG_DIR/ci-cd-${1:-daily}.log"
NOTIFY="$WORKSPACE/crypto-bots/notify.sh"

# El gate corre en modo determinista (sin modelo ML), el mismo con el que se
# genero research/ci_baseline.json y el mismo que usa el CI de GitHub Actions.
export PERROBOTILLO_ML_DISABLE=1

PHASE="${1:-daily}"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

notify_telegram() {
    local key="$1" msg="$2"
    if [ -x "$NOTIFY" ]; then
        bash "$NOTIFY" "$key" "$msg" >>"$LOG_FILE" 2>&1 || log "⚠️  notify falló"
    else
        log "⚠️  notify.sh no encontrado: $NOTIFY"
    fi
}

cd "$WORKSPACE" || { log "❌ no existe $WORKSPACE"; exit 1; }

log "=== CD PIPELINE — fase: $PHASE — inicio ==="

case "$PHASE" in
  daily)
    OUT="$LOG_DIR/ci-backtest-latest.json"
    log "▶ Backtest 90d (fee 0.15%)"
    if ! "$PYTHON" research/run_full_backtest.py --symbol ALL --days 90 --slippage-bps 5 --out "$OUT" >>"$LOG_FILE" 2>&1; then
        log "❌ backtest falló"
        notify_telegram "ci-cd-daily-error" "🚨 *CI/CD daily* — backtest FALLÓ. Ver logs/ci-cd-daily.log"
        exit 1
    fi
    log "▶ CI gate"
    if "$PYTHON" research/ci_backtest_gate.py "$OUT" >>"$LOG_FILE" 2>&1; then
        log "✅ gate PASO"
        notify_telegram "ci-cd-daily-ok" "✅ *CI/CD daily* — gate PASO (backtest 90d, fee 0.15%). Revisar logs/ci-cd-daily.log"
    else
        rc=$?
        log "❌ gate REGRESIÓN (exit $rc)"
        notify_telegram "ci-cd-daily-regression" "⚠️ *CI/CD daily* — REGRESIÓN vs baseline. Revisar logs/ci-cd-daily.log"
        exit "$rc"
    fi
    ;;

  optimize)
    log "▶ Optuna 50 trials"
    "$PYTHON" research/optuna_custom.py >>"$LOG_FILE" 2>&1 \
        && log "✅ Optuna completo" \
        || { log "❌ Optuna falló"; notify_telegram "ci-cd-optimize-error" "🚨 *CI/CD optimize* — Optuna falló."; exit 1; }
    ;;

  ml-retrain)
    START="$(date -u -d '-2 years' +%Y-%m-%d)"
    END="$(date -u +%Y-%m-%d)"
    log "▶ Reentrenamiento ML ($START → $END)"
    if "$PYTHON" research/jesse_ml_train.py --coins ALL --start "$START" --end "$END" --model rf --fast --quiet >>"$LOG_FILE" 2>&1; then
        log "✅ Reentrenamiento completo"
        notify_telegram "ci-cd-retrain-ok" "🧠 *CI/CD ml-retrain* — modelos reentrenados ($START → $END)."
    else
        log "❌ Reentrenamiento falló"
        notify_telegram "ci-cd-retrain-error" "🚨 *CI/CD ml-retrain* — falló. Ver logs/ci-cd-ml-retrain.log"
        exit 1
    fi
    ;;

  deploy-gate)
    # A propósito NO hace commit/tag automático: publicar config en el bot en
    # producción sin revisión humana es inseguro. Solo reporta el estado.
    GATE="$LOG_DIR/ci-backtest-latest.json"
    if [ -f "$GATE" ]; then
        log "▶ Deploy gate (solo reporte)"
        "$PYTHON" research/ci_backtest_gate.py "$GATE" >>"$LOG_FILE" 2>&1 \
            && notify_telegram "ci-cd-deploy" "🚀 *CI/CD deploy-gate* — gate PASO. Pendiente aprobación humana para desplegar." \
            || notify_telegram "ci-cd-deploy" "⛔ *CI/CD deploy-gate* — gate NO aprobado. No se despliega."
    else
        log "⚠️  no hay resultado de gate ($GATE)"
    fi
    ;;

  *)
    echo "Uso: $0 <daily|optimize|ml-retrain|deploy-gate>" >&2
    exit 2
    ;;
esac

log "=== CD PIPELINE — fase: $PHASE — fin ==="
