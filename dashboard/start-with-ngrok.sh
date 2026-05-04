#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 Perrobotillo Dashboard + Ngrok Auto-Start
# ════════════════════════════════════════════════════════

echo "🐕 Iniciando Perrobotillo Dashboard con Ngrok..."

# 1. Iniciar Dashboard
echo "🚀 Iniciando dashboard..."
cd /home/overgon/.openclaw/workspace/dashboard
python3 app.py &
DASHBOARD_PID=$!

# 2. Esperar a que el dashboard esté listo
echo "⏳ Esperando dashboard..."
sleep 5

# 3. Verificar que el dashboard esté corriendo
if ! kill -0 $DASHBOARD_PID 2>/dev/null; then
    echo "❌ Error: Dashboard no inició"
    exit 1
fi

# 4. Iniciar Ngrok
echo "🔌 Iniciando ngrok tunnel..."
ngrok http 8080 --log=stdout &
NGROK_PID=$!

# 5. Esperar a que ngrok se conecte
sleep 8

# 6. Mostrar URL
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🎉 PERROBOTILLO DASHBOARD - ONLINE                   ║"
echo "╠═══════════════════════════════════════════════════════╣"
echo "║  URL pública: https://XXXXX.ngrok-free.dev           ║"
echo "║  Panel ngrok: http://localhost:4040                   ║"
echo "║  Dashboard local: http://192.168.3.215:8080          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "🔒 HTTPS habilitado con certificado Let's Encrypt"
echo "📊 Presiona Ctrl+C para detener"
echo ""

# 7. Mantener el script corriendo
wait
