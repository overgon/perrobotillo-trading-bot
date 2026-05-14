#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO DASHBOARD - AUTH SETUP SCRIPT
# ════════════════════════════════════════════════════════
# Script interactivo para configurar autenticación del dashboard
# Uso: ./setup-auth.sh
# ════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HTPASSWD_FILE="${SCRIPT_DIR}/.htpasswd"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🐕 PERROBOTILLO DASHBOARD - AUTH SETUP              ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Verificar htpasswd
if ! command -v htpasswd &> /dev/null; then
    echo "❌ Error: htpasswd no encontrado"
    echo "   Instala apache2-utils (Debian/Ubuntu): sudo apt install apache2-utils"
    echo "   O httpd-tools (RHEL/CentOS): sudo yum install httpd-tools"
    exit 1
fi

echo "✅ htpasswd encontrado"
echo ""

# Pedir usuario
read -p "👤 Ingresa el usuario para el dashboard: " USERNAME

if [ -z "$USERNAME" ]; then
    echo "❌ Error: El usuario no puede estar vacío"
    exit 1
fi

echo ""

# Pedir contraseña (sin eco)
read -sp "🔑 Ingresa la contraseña: " PASSWORD
echo ""
read -sp "🔑 Confirma la contraseña: " PASSWORD_CONFIRM
echo ""

if [ "$PASSWORD" != "$PASSWORD_CONFIRM" ]; then
    echo "❌ Error: Las contraseñas no coinciden"
    exit 1
fi

if [ ${#PASSWORD} -lt 6 ]; then
    echo "❌ Error: La contraseña debe tener al menos 6 caracteres"
    exit 1
fi

echo ""
echo "🔐 Generando archivo .htpasswd..."

# Crear/actualizar .htpasswd
htpasswd -cb "$HTPASSWD_FILE" "$USERNAME" "$PASSWORD"

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ AUTENTICACIÓN CONFIGURADA                         ║"
echo "╠═══════════════════════════════════════════════════════╣"
echo "║  Usuario: $USERNAME"
echo "║  Archivo: $HTPASSWD_FILE"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Verificar que app.py tenga el fix de WORKSPACE
APP_FILE="${SCRIPT_DIR}/app.py"
if grep -q 'WORKSPACE = "\$HOME' "$APP_FILE" 2>/dev/null; then
    echo "⚠️  Advertencia: app.py tiene WORKSPACE con \$HOME sin expandir"
    echo "   Ejecuta este fix:"
    echo ""
    echo "   sed -i 's|WORKSPACE = \"\$HOME|WORKSPACE = os.path.expanduser(\"~|g' $APP_FILE"
    echo ""
    read -p "¿Quieres aplicar el fix ahora? (s/n): " APPLY_FIX
    if [ "$APPLY_FIX" = "s" ]; then
        sed -i 's|WORKSPACE = "\$HOME|WORKSPACE = os.path.expanduser("~|g' "$APP_FILE"
        echo "✅ Fix aplicado"
    fi
fi

echo ""
echo "📋 Siguientes pasos:"
echo "   1. Reinicia el dashboard: pkill -f 'python3 app.py' && cd $SCRIPT_DIR && python3 app.py &"
echo "   2. Accede a http://localhost:8080 o tu URL de ngrok"
echo "   3. Usa las credenciales que acabas de configurar"
echo ""
echo "🐕 ¡Listo para operar!"
