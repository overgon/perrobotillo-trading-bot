#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 Perrobotillo Dashboard + Ngrok Auto-Start
# ════════════════════════════════════════════════════════

echo "🐕 Iniciando Perrobotillo Dashboard con Ngrok..."

# 1. Iniciar Dashboard
echo "🚀 Iniciando dashboard..."
cd $HOME/.openclaw/workspace/dashboard
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

echo "✅ Dashboard corriendo (PID: $DASHBOARD_PID)"

# 4. Iniciar Ngrok (sin --log=stdout para evitar problemas)
echo "🔌 Iniciando ngrok tunnel..."
ngrok http 8080 > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

echo "✅ Ngrok iniciado (PID: $NGROK_PID)"

# 5. Esperar a que ngrok se conecte
sleep 8

# 6. Obtener URL de ngrok
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url')

# 7. Mostrar URL
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🎉 PERROBOTILLO DASHBOARD - ONLINE                   ║"
echo "╠═══════════════════════════════════════════════════════╣"
echo "║  URL pública: $NGROK_URL"
echo "║  Panel ngrok: http://localhost:4040                   ║"
echo "║  Dashboard local: http://192.168.3.215:8080          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "🔒 HTTPS habilitado"
echo "📊 Dashboard y ngrok corriendo"
echo ""

# 8. Mantener el script corriendo (esperar ambos procesos)
wait $NGROK_PID
