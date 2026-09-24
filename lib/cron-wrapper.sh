#!/bin/bash
# Central cron wrapper - usa $HOME para portabilidad
set -euo pipefail

# Resolve workspace via $HOME
WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
LOG_DIR="$WORKSPACE/logs"
mkdir -p "$LOG_DIR"

# Script to execute + args
SCRIPT="$1"
shift

# Source secrets
if [ -f "$WORKSPACE/secrets/binance.env" ]; then
    source "$WORKSPACE/secrets/binance.env"
fi
if [ -f "$WORKSPACE/secrets/telegram.env" ]; then
    source "$WORKSPACE/secrets/telegram.env"
fi

# Execute
if [ -x "$SCRIPT" ] || [ -f "$SCRIPT" ]; then
    bash "$SCRIPT" "$@"
else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: Script not found: $SCRIPT" >&2
    exit 1
fi
