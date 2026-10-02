#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 Perrobotillo - Ngrok Setup Script
# ════════════════════════════════════════════════════════
# Configura Ngrok automáticamente para acceso remoto al dashboard
# Uso: ./setup-ngrok.sh
# ════════════════════════════════════════════════════════

set -e

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🔌 NGROK SETUP - Perrobotillo Dashboard              ║"
echo "╚═══════════════════════════════════════════════════════╝"

# 1. Verificar si ngrok está instalado
if ! command -v ngrok &> /dev/null; then
    echo ""
    echo "❌ Ngrok no está instalado"
    echo ""
    echo "📦 INSTALACIÓN:"
    echo "  1. Descargá ngrok: https://ngrok.com/download"
    echo "  2. Descomprimí: unzip ngrok.zip"
    echo "  3. Mové a /usr/local/bin: sudo mv ngrok /usr/local/bin/"
    echo ""
    exit 1
fi

echo "✅ Ngrok instalado: $(ngrok --version | head -1)"

# 2. Verificar autenticación
echo ""
echo "🔑 Verificando autenticación de Ngrok..."

if [ ! -f ~/.config/ngrok/ngrok.yml ]; then
    echo ""
    echo "⚠️  Ngrok no está autenticado"
    echo ""
    echo "📝 AUTENTICACIÓN:"
    echo "  1. Creá una cuenta en: https://ngrok.com/signup"
    echo "  2. Obtené tu authtoken en: https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "  3. Ejecutá: ngrok config add-authtoken <TU_TOKEN>"
    echo ""
    read -p "¿Ya tenés tu authtoken? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Ingresa tu authtoken: " NGROK_TOKEN
        ngrok config add-authtoken "$NGROK_TOKEN"
        echo "✅ Ngrok autenticado"
    else
        echo "⚠️  No se puede continuar sin autenticación"
        exit 1
    fi
else
    echo "✅ Ngrok autenticado"
fi

# 3. Verificar dashboard
echo ""
echo "📊 Verificando dashboard..."

if ! curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
    echo "⚠️  Dashboard no está corriendo en puerto 8080"
    echo ""
    read -p "¿Querés iniciar el dashboard ahora? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$HOME/.openclaw/workspace/dashboard"
        nohup python3 app.py > /tmp/dashboard.log 2>&1 &
        echo "✅ Dashboard iniciado"
        sleep 5
    else
        echo "⚠️  No se puede continuar sin dashboard"
        exit 1
    fi
else
    echo "✅ Dashboard corriendo en puerto 8080"
fi

# 4. Iniciar ngrok
echo ""
echo "🔌 Iniciando Ngrok tunnel..."

cd "$HOME/.openclaw/workspace/dashboard"
nohup ngrok http 8080 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

echo "✅ Ngrok iniciado (PID: $NGROK_PID)"

# 5. Esperar y obtener URL
echo ""
echo "⏳ Esperando conexión con Ngrok..."
sleep 8

# Obtener URL pública
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url // empty')

if [ -n "$NGROK_URL" ]; then
    echo ""
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║  🎉 NGROK CONFIGURADO EXITOSAMENTE                    ║"
    echo "╠═══════════════════════════════════════════════════════╣"
    echo "║  URL pública: $NGROK_URL"
    echo "║  Panel ngrok: http://localhost:4040"
    echo "║  Dashboard local: http://localhost:8080"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo ""
    
    # Guardar URL en archivo
    echo "$NGROK_URL" > "$HOME/.openclaw/workspace/dashboard/ngrok-url.txt"
    echo "💾 URL guardada: $HOME/.openclaw/workspace/dashboard/ngrok-url.txt"
    echo ""
    
    # Actualizar README con la URL
    echo "📝 Actualizando documentación..."
    if [ -f "$HOME/.openclaw/workspace/README.md" ]; then
        sed -i "s|<YOUR_NGROK_SUBDOMAIN>.ngrok-free.dev|$NGROK_URL|g" "$HOME/.openclaw/workspace/README.md" 2>/dev/null || true
        echo "✅ README actualizado"
    fi
    
    echo ""
    echo "🔗 ACCESO REMOTO:"
    echo "  • URL: $NGROK_URL"
    echo "  • Panel: http://localhost:4040"
    echo ""
    echo "📌 NOTA: La URL cambia cada vez que reiniciás ngrok (free plan)"
    echo "   Para URL fija, necesitás plan de pago"
    echo ""
else
    echo "❌ Error: No se pudo obtener URL de Ngrok"
    echo "   Revisá log: /tmp/ngrok.log"
    exit 1
fi
