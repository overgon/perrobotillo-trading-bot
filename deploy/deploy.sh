#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - DEPLOY SCRIPT (FASE 8)
# ════════════════════════════════════════════════════════
# Executes nginx + systemd deployment on Raspberry Pi 5
# Run: sudo bash deploy/deploy.sh
# ════════════════════════════════════════════════════════

set -euo pipefail

echo "═══════════════════════════════════════════════════════"
echo "  PERROBOTILLO FASE 8 — Production Deployment"
echo "═══════════════════════════════════════════════════════"

WORKSPACE="/home/overgon/.openclaw/workspace"
DEPLOY_DIR="${WORKSPACE}/deploy"
NGINX_CONF="${DEPLOY_DIR}/nginx-perrobotillo.conf"
SYSTEMD_SERVICE="${DEPLOY_DIR}/perrobotillo-dashboard.service"
NGINX_SITE="/etc/nginx/sites-available/perrobotillo"
NGINX_LINK="/etc/nginx/sites-enabled/perrobotillo"
SYSTEMD_SERVICE_FILE="/etc/systemd/system/perrobotillo-dashboard.service"

echo ""
echo "1️⃣  Stopping current dashboard..."
pkill -f "python3.*app.py" 2>/dev/null || true
echo "   ✅ Stopped"

echo ""
echo "2️⃣  Clearing Python cache..."
rm -rf "${WORKSPACE}/dashboard/__pycache__/"
find "${WORKSPACE}" -name "*.pyc" -delete 2>/dev/null || true
echo "   ✅ Cache cleared (forces fresh compile)"

echo ""
echo "3️⃣  Installing nginx config..."
if [ -f "$NGINX_CONF" ]; then
    cp "$NGINX_CONF" "$NGINX_SITE"
    ln -sf "$NGINX_SITE" "$NGINX_LINK"
    rm -f /etc/nginx/sites-enabled/default
    echo "   ✅ nginx config installed"
else
    echo "   ❌ nginx config not found: $NGINX_CONF"
    exit 1
fi

echo ""
echo "4️⃣  Installing systemd service..."
cp "$SYSTEMD_SERVICE" "$SYSTEMD_SERVICE_FILE"
systemctl daemon-reload
echo "   ✅ systemd service installed"

echo ""
echo "5️⃣  Testing nginx config..."
nginx -t 2>&1 | tail -3
echo "   ✅ nginx test passed"

echo ""
echo "6️⃣  Enabling services..."
systemctl enable perrobotillo-dashboard
systemctl enable nginx
echo "   ✅ Services enabled"

echo ""
echo "7️⃣  Starting services..."
systemctl restart perrobotillo-dashboard
sleep 2
systemctl restart nginx
echo "   ✅ Services started"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  🚀 FASE 8 DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  Dashboard: https://dashboard.perrobotillo.io"
echo "  API:       http://localhost:8080/api/status"
echo ""
echo "  Verificación:"
echo "    curl -s https://dashboard.perrobotillo.io/api/status"
echo "    Debería mostrar: 19/24 slots"
echo ""
echo "═══════════════════════════════════════════════════════"