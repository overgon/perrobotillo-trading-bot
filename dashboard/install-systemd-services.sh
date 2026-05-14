#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO DASHBOARD - SYSTEMD INSTALL SCRIPT
# ════════════════════════════════════════════════════════
# Instala servicios systemd para auto-inicio del dashboard
# Uso: sudo ./install-systemd-services.sh
# ════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER=$(whoami)
HOME_DIR=$(eval echo ~$USER)

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🐕 PERROBOTILLO DASHBOARD - SYSTEMD INSTALL          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Verificar que se ejecute con sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: Este script debe ejecutarse con sudo"
    echo "   Uso: sudo ./install-systemd-services.sh"
    exit 1
fi

echo "✅ Ejecutando como root"
echo ""

# Crear servicio del dashboard
echo "📝 Creando servicio del dashboard..."
cat > /etc/systemd/system/perrobotillo-dashboard.service << EOF
[Unit]
Description=Perrobotillo Dashboard - Cyberpunk Edition
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=5
StandardOutput=append:$HOME_DIR/.openclaw/logs/dashboard-stdout.log
StandardError=append:$HOME_DIR/.openclaw/logs/dashboard-stderr.log

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Servicio dashboard creado"

# Crear servicio de ngrok
echo "📝 Creando servicio de ngrok..."
cat > /etc/systemd/system/perrobotillo-ngrok.service << EOF
[Unit]
Description=Perrobotillo Ngrok Tunnel
After=network.target perrobotillo-dashboard.service

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/ngrok http 8080 --log=stdout
Restart=always
RestartSec=10
StandardOutput=append:$HOME_DIR/.openclaw/logs/ngrok-stdout.log
StandardError=append:$HOME_DIR/.openclaw/logs/ngrok-stderr.log

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Servicio ngrok creado"

# Recargar systemd
echo "🔄 Recargando systemd..."
systemctl daemon-reload

# Habilitar servicios
echo "⚙️  Habilitando servicios para auto-inicio..."
systemctl enable perrobotillo-dashboard.service
systemctl enable perrobotillo-ngrok.service

echo "✅ Servicios habilitados"

# Detener procesos manuales si existen
echo "🛑 Deteniendo procesos manuales existentes..."
pkill -f "python3 app.py" 2>/dev/null || true
pkill ngrok 2>/dev/null || true
sleep 2

# Iniciar servicios
echo "🚀 Iniciando servicios..."
systemctl start perrobotillo-dashboard.service
systemctl start perrobotillo-ngrok.service

sleep 3

# Verificar status
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  STATUS DE SERVICIOS                                  ║"
echo "╠═══════════════════════════════════════════════════════╣"

if systemctl is-active --quiet perrobotillo-dashboard.service; then
    echo "║  🐕 Dashboard:  ✅ ACTIVO"
else
    echo "║  🐕 Dashboard:  ❌ INACTIVO"
fi

if systemctl is-active --quiet perrobotillo-ngrok.service; then
    echo "║  🔌 Ngrok:      ✅ ACTIVO"
else
    echo "║  🔌 Ngrok:      ❌ INACTIVO"
fi

echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Mostrar URL de ngrok
if systemctl is-active --quiet perrobotillo-ngrok.service; then
    sleep 5
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url' 2>/dev/null)
    if [ -n "$NGROK_URL" ] && [ "$NGROK_URL" != "null" ]; then
        echo "🌐 URL pública: $NGROK_URL"
    fi
fi

echo ""
echo "📋 Comandos útiles:"
echo "   Ver status:     sudo systemctl status perrobotillo-dashboard.service"
echo "   Ver logs:       tail -f $HOME_DIR/.openclaw/logs/dashboard-stderr.log"
echo "   Reiniciar:      sudo systemctl restart perrobotillo-dashboard.service"
echo "   Detener:        sudo systemctl stop perrobotillo-dashboard.service"
echo ""
echo "✅ ¡Instalación completa! El dashboard arrancará automáticamente al reiniciar."
echo "🐕 ¡Listo para operar!"
