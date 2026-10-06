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
/usr/local/bin/ngrok start dashboard --config=/home/overgon/.config/ngrok/ngrok.yml > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

echo "✅ Ngrok iniciado (PID: $NGROK_PID)"

# 5. Esperar a que ngrok se conecte
sleep 8

# 6. Obtener URL de ngrok
NGROK_URL=$(grep -oP 'url=\Khttps://[^ ]+' "$HOME/.openclaw/logs/ngrok-stdout.log" 2>/dev/null | tail -1 || true)

# 7. Mostrar URL
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🎉 PERROBOTILLO DASHBOARD - ONLINE                   ║"
echo "╠═══════════════════════════════════════════════════════╣"
echo "║  URL pública: $NGROK_URL"
echo "║  Inspección: OFF (inspect: false)                ║"
echo "║  Dashboard local: http://192.168.3.215:8080          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "🔒 HTTPS habilitado"
echo "📊 Dashboard y ngrok corriendo"
echo ""

# 8. Mantener el script corriendo (esperar ambos procesos)
wait $NGROK_PID
