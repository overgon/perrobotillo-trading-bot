#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 Perrobotillo - Ngrok Simple Starter
# ════════════════════════════════════════════════════════
# Inicia ngrok de forma simple y estable
# Uso: ./start-ngrok-simple.sh
# ════════════════════════════════════════════════════════

set -e

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🔌 Ngrok Simple Starter - Perrobotillo               ║"
echo "╚═══════════════════════════════════════════════════════╝"

# 1. Matar cualquier ngrok existente
echo "🔫 Limpiando ngrok existentes..."
pkill -9 -f "/usr/local/bin/ngrok" 2>/dev/null || true
sleep 2

# 2. Verificar dashboard
echo "📊 Verificando dashboard..."
if ! curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
    echo "⚠️  Dashboard no está corriendo, iniciando..."
    cd "$HOME/.openclaw/workspace/dashboard"
    nohup python3 app.py > /tmp/dashboard.log 2>&1 &
    sleep 5
fi

# Verificar que dashboard responde
if curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
    echo "✅ Dashboard ONLINE"
else
    echo "❌ Dashboard NO responde"
    exit 1
fi

# 3. Iniciar ngrok
echo "🔌 Iniciando ngrok..."
cd "$HOME/.openclaw/workspace/dashboard"
/usr/local/bin/ngrok http 8080 > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

echo "✅ Ngrok iniciado (PID: $NGROK_PID)"

# 4. Esperar conexión
echo "⏳ Esperando conexión con ngrok..."
sleep 10

# 5. Verificar tunnel
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url // empty')

if [ -n "$NGROK_URL" ]; then
    echo ""
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║  🎉 NGROK ONLINE                                       ║"
    echo "╠═══════════════════════════════════════════════════════╣"
    echo "║  URL: $NGROK_URL"
    echo "║  Panel: http://localhost:4040"
    echo "╚═══════════════════════════════════════════════════════╝"
    
    # Guardar URL
    echo "$NGROK_URL" > "$HOME/.openclaw/workspace/dashboard/ngrok-url.txt"
    echo "💾 URL guardada en: ngrok-url.txt"
    echo ""
    echo "📌 NOTA: HTTP 401 es NORMAL (free tier requiere auth)"
    echo "   El tunnel SÍ funciona aunque diga 401"
else
    echo "❌ Error: No se pudo obtener URL de ngrok"
    echo "   Revisá log: /tmp/ngrok.log"
    exit 1
fi
