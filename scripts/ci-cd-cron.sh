#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  CI/CD Pipeline Wrapper — Perrobotillo + Jesse AI     ║
# ║  Runs inside the jesse Docker container via cron.    ║
# ║                                                      ║
# ║  Author: Perrobotron Aterrorizar!!                   ║
# ╚═══════════════════════════════════════════════════════╝
#
# Usage: ci-cd-cron.sh <phase>
#   phases: daily | optimize | deploy-gate | ml-retrain
#
# Scheduled via crontab:
#   0 5 * * *   ci-cd-cron.sh daily       (Mon-Sat daily backtest)
#   0 3 * * 0   ci-cd-cron.sh optimize    (Sun 3 AM — Optuna)
#   0 5 * * 0   ci-cd-cron.sh ml-retrain   (Sun 5 AM — ML retrain)
#   0 7 * * 0   ci-cd-cron.sh deploy-gate  (Sun 7 AM — deploy gate)

set -euo pipefail

PHASE="${1:-daily}"
LOG_DIR="/home/overgon/jesse-research/logs"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/ci-cd-${PHASE}.log"
ERR_FILE="$LOG_DIR/ci-cd-${PHASE}.err"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] CI/CD pipeline — Phase: $PHASE" | tee -a "$LOG_FILE"

# Run inside the jesse Docker container
# Scripts are at /home/research/ inside the container (mounted from jesse-research/)
EXIT_CODE=0
sudo docker exec jesse python3 "/home/research/ci_cd_pipeline.py" --phase "$PHASE" 2>&1 | tee -a "$LOG_FILE" || EXIT_CODE=$?

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] Phase '$PHASE' completed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"

# Keep last 500 lines
tail -500 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"

exit $EXIT_CODE
