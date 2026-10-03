#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# run-param-multipliers.sh — Refresh ML param multipliers
# Called by cron every 5 minutes
# Output: /home/overgon/.openclaw/workspace/ml/param-multipliers.json
# Firma: Perrobotron Aterrorrizar!!
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

RESEARCH_DIR="/home/overgon/.openclaw/workspace"
RUNTIME_SCRIPT="$RESEARCH_DIR/param_multiplier_inference.py"
OUTPUT_FILE="/home/vergon/.openclaw/workspace/ml/param-multipliers.json"

# Only download new data if the JSON is older than 10 minutes
if [ -f "$OUTPUT_FILE" ]; then
    FILE_AGE=$(($(date +%s) - $(stat -c %Y "$OUTPUT_FILE")))
    if [ "$FILE_AGE" -lt 300 ]; then
        # JSON is fresh enough, exit
        exit 0
    fi
fi

# Run inference (downloads latest candles + predicts multipliers)
PYTHONUNBUFFERED=1 PYTHON=/usr/bin/python3
$PYTHON "$RUNTIME_SCRIPT" 2>&1 || {
    echo "ERROR: param-multiplier inference failed" >&2
    exit 1
}

echo "✅ param-multipliers.json refreshed at $(date '+%Y-%m-%d %H:%M:%S')"
