#!/bin/bash
set -euo pipefail
WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
mkdir -p "$WORKSPACE/logs"

PY_FILE="$1"
shift

# Determine which python to use
PYTHON="${PYTHON:-/usr/bin/python3}"
if [ -x "$WORKSPACE/venv/bin/python3" ]; then
    PYTHON="$WORKSPACE/venv/bin/python3"
fi

# Execute
"$PYTHON" "$PY_FILE" "$@"
