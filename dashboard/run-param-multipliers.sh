#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# run-param-multipliers.sh — Refresh ML param multipliers
# Called by cron every 5 minutes
# Output: /home/overgon/.openclaw/workspace/ml/param-multipliers.json
# Firma: Perrobotron Aterrorizar!!
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

RESEARCH_DIR="/home/overgon/.openclaw/workspace"
RUNTIME_SCRIPT="$RESEARCH_DIR/param-multiplier-runtime.py"
OUTPUT_FILE="$HOME/.openclaw/workspace/ml/param-multipliers.json"
LOG_DIR="$HOME/.openclaw/logs"
LOG_FILE="$LOG_DIR/param-multipliers.log"

# Only download new data if the JSON is older than 5 minutes
if [ -f "$OUTPUT_FILE" ]; then
    FILE_AGE=$(($(date +%s) - $(stat -c %Y "$OUTPUT_FILE")))
    if [ "$FILE_AGE" -lt 300 ]; then
        # JSON is fresh enough, exit
        exit 0
    fi
fi

# Run runtime script — it writes JSON directly to OUTPUT_FILE
# (nested format: {"coins": {"ZEC": {"multipliers": {...}, ...}}})
mkdir -p "$(dirname "$OUTPUT_FILE")" 2>/dev/null || true
mkdir -p "$LOG_DIR" 2>/dev/null || true

PYTHONUNBUFFERED=1 /usr/bin/python3 "$RUNTIME_SCRIPT" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ "$EXIT_CODE" -ne 0 ]; then
    echo "ERROR: param-multiplier runtime failed (exit $EXIT_CODE)" >&2
    exit 1
fi

echo "✅ param-multipliers.json refreshed at $(date '+%Y-%m-%d %H:%M:%S')"
