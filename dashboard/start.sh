#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO DASHBOARD - STARTUP SCRIPT
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🐕 PERROBOTILLO DASHBOARD - CYBERPUNK EDITION       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Check if Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "⚠️  Flask not found. Installing..."
    pip3 install flask --quiet
fi

echo "✅ Flask installed"
echo ""
echo "🚀 Starting dashboard server..."
echo ""
echo "📡 ACCESS URLS:"
echo "   Local:   http://localhost:8080"
echo "   Network: http://192.168.3.215:8080"
echo ""
echo "⚠️  Press Ctrl+C to stop"
echo "═══════════════════════════════════════════════════════"
echo ""

# Start the dashboard
python3 app.py
