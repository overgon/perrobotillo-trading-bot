# 🐕 Perrobotillo Dashboard - Guía Completa

**Documentación oficial del sistema de monitoreo**

---

## 📋 ÍNDICE

1. [Descripción General](#descripción-general)
2. [Arquitectura](#arquitectura)
3. [Instalación](#instalación)
4. [Configuración](#configuración)
5. [Uso](#uso)
6. [API Reference](#api-reference)
7. [Troubleshooting](#troubleshooting)
8. [Seguridad](#seguridad)
9. [Mantenimiento](#mantenimiento)
10. [Desarrollo](#desarrollo)

---

## DESCRIPCIÓN GENERAL

### ¿Qué es el Dashboard?

El Dashboard de Perrobotillo es una interfaz gráfica web para monitorear en tiempo real el estado del bot de trading. Proporciona visualización de:

- Portfolio total (USDT y MXN)
- P&L en tiempo real
- 21 slots de trading (3 por moneda)
- Progreso a Take Profits
- Histórico de trades
- Estado del sistema

### Características Principales

| Feature | Descripción |
|---------|-------------|
| **Tiempo Real** | Auto-refresh cada 10 segundos |
| **Responsive** | Funciona en PC, tablet y móvil |
| **Cyberpunk UI** | Diseño moderno con colores neón |
| **Alertas** | Notificaciones visuales y sonoras |
| **API REST** | Endpoints para integración externa |

### Tecnologías Utilizadas

- **Backend:** Python 3 + Flask
- **Frontend:** HTML5 + CSS3 + JavaScript (Vanilla)
- **Datos:** Binance API + Archivos JSON locales
- **Estilo:** Cyberpunk (neón, grid animado, scanlines)

---

## ARQUITECTURA

### Estructura de Archivos

```
dashboard/
├── app.py                      # Servidor Flask (backend)
├── start.sh                    # Script de inicio
├── README.md                   # Documentación rápida
├── static/
│   ├── css/
│   │   └── style.css          # Estilos Cyberpunk
│   ├── js/
│   │   └── app.js             # Lógica frontend
│   └── sounds/
│       └── alert.mp3          # Sonido de alertas
└── templates/
    └── index.html             # Interfaz principal
```

### Flujo de Datos

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Binance   │────▶│  Bot Scripts │────▶│  JSON Files │
│    API      │     │  (.sh)       │     │  (local)    │
└─────────────┘     └──────────────┘     └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Browser    │◀────│   Flask App  │◀────│   app.py   │
│  (Client)   │     │  (Server)    │     │  (Reader)  │
└─────────────┘     └──────────────┘     └─────────────┘
```

### Componentes

1. **Data Layer** - Archivos JSON con estado del bot
2. **API Layer** - Flask app que lee y sirve datos
3. **Presentation Layer** - HTML/CSS/JS que muestra datos

---

## INSTALACIÓN

### Pre-requisitos

- Python 3.7+
- pip3 (Python package manager)
- Perrobotillo Trading Bot instalado
- Raspberry Pi 5 o Linux

### Paso 1: Verificar Python

```bash
python3 --version
# Debería mostrar: Python 3.x.x
```

### Paso 2: Instalar Flask

```bash
pip3 install flask --break-system-packages
```

### Paso 3: Verificar Archivos

```bash
cd /home/overgon/.openclaw/workspace/dashboard
ls -la
# Deberías ver: app.py, start.sh, static/, templates/
```

### Paso 4: Probar Inicio

```bash
./start.sh
# Debería iniciar el servidor en puerto 8080
```

---

## CONFIGURACIÓN

### Configuración Básica

**Archivo:** `app.py`

```python
# Cambiar puerto (default: 8080)
app.run(
    host='0.0.0.0',
    port=8080,      # ← Cambiar aquí
    debug=False,
    threaded=True
)
```

### Configuración de Refresh

**Archivo:** `static/js/app.js`

```javascript
const CONFIG = {
    API_URL: '/api/data',
    PRICES_URL: '/api/prices',
    REFRESH_INTERVAL: 10000,  // ← Cambiar (ms)
    MAX_TRADES_DISPLAY: 10
};
```

### Configuración de Alertas

**Archivo:** `static/js/app.js`

```javascript
// Umbral de alerta (default: 0.5%)
if (distance > 0 && distance < 0.5) {  // ← Cambiar 0.5
    triggerAlert(coin, slotId, distance);
}
```

### Configuración de Sonido

**Archivo:** `static/js/app.js`

```javascript
// Habilitar/deshabilitar sonido
function triggerAlert(coin, slotId, distance) {
    const audio = document.getElementById('alertSound');
    if (audio) {
        audio.play().catch(e => console.log('Audio play failed:', e));
    }
}
```

---

## USO

### Iniciar el Dashboard

```bash
cd /home/overgon/.openclaw/workspace/dashboard
./start.sh
```

### Acceder al Dashboard

**Desde la Raspberry Pi:**
```
http://localhost:8080
```

**Desde otra dispositivo en la misma red:**
```
http://192.168.3.215:8080
```

### Detener el Dashboard

```bash
# Opción 1: Ctrl+C en la terminal

# Opción 2: Matar proceso
pkill -f "python3 app.py"

# Opción 3: Matar por puerto
sudo lsof -ti:8080 | xargs kill -9
```

### Auto-Inicio con el Sistema

**Opción 1: Crontab**

```bash
crontab -e

# Agregar línea:
@reboot cd /home/overgon/.openclaw/workspace/dashboard && nohup python3 app.py > /tmp/dashboard.log 2>&1 &
```

**Opción 2: Systemd Service**

Crear archivo `/etc/systemd/system/perrobotillo-dashboard.service`:

```ini
[Unit]
Description=Perrobotillo Dashboard
After=network.target

[Service]
Type=simple
User=overgon
WorkingDirectory=/home/overgon/.openclaw/workspace/dashboard
ExecStart=/usr/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Habilitar servicio:

```bash
sudo systemctl daemon-reload
sudo systemctl enable perrobotillo-dashboard
sudo systemctl start perrobotillo-dashboard
```

---

## API REFERENCE

### Endpoints Disponibles

#### GET `/api/data`

**Descripción:** Obtiene todos los datos del dashboard.

**Response:**
```json
{
  "timestamp": "2026-05-03T13:30:00",
  "portfolio": {
    "total_usdt": 2628.74,
    "total_mxn": 45976.73
  },
  "coins": {
    "BTC": {
      "symbol": "BTC",
      "slots": [...]
    },
    ...
  },
  "prices": {
    "BTCUSDT": "78741.01000000",
    ...
  },
  "history": {
    "totalTrades": 6,
    "totalWins": 1,
    "totalLosses": 5,
    "winRate": 16.67,
    "trades": [...]
  },
  "system": {
    "api_binance": "✅ Online",
    "ip_whitelist": "✅ 187.188.230.163",
    "gateway": "✅ Online",
    "last_update": "2026-05-03 13:30:00"
  }
}
```

**Uso desde curl:**
```bash
curl http://localhost:8080/api/data | jq
```

#### GET `/api/prices`

**Descripción:** Obtiene solo precios actuales (más rápido).

**Response:**
```json
{
  "BTCUSDT": "78741.01000000",
  "ETHUSDT": "2328.44000000",
  "BNBUSDT": "619.98000000",
  "SOLUSDT": "84.37000000",
  "LINKUSDT": "9.16000000",
  "XRPUSDT": "1.40000000",
  "AVAXUSDT": "9.09000000"
}
```

#### GET `/api/health`

**Descripción:** Health check del servidor.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-05-03T13:30:00"
}
```

### Integración con Otras Apps

**Ejemplo en Python:**
```python
import requests

response = requests.get('http://localhost:8080/api/data')
data = response.json()

print(f"Portfolio: ${data['portfolio']['total_usdt']}")
print(f"P&L 24h: ${data['portfolio']['pnl_24h']}")
```

**Ejemplo en JavaScript:**
```javascript
fetch('http://localhost:8080/api/data')
  .then(response => response.json())
  .then(data => {
    console.log('Portfolio:', data.portfolio.total_usdt);
  });
```

---

## TROUBLESHOOTING

### Problema: Flask no está instalado

**Síntoma:**
```
ModuleNotFoundError: No module named 'flask'
```

**Solución:**
```bash
pip3 install flask --break-system-packages
```

---

### Problema: Puerto ya en uso

**Síntoma:**
```
OSError: [Errno 98] Address already in use
```

**Solución:**
```bash
# Matar proceso usando el puerto
sudo lsof -ti:8080 | xargs kill -9

# O cambiar puerto en app.py
```

---

### Problema: No puedo acceder desde la red

**Síntoma:** Timeout al acceder desde otro dispositivo.

**Solución:**

1. Verificar IP de la Raspberry Pi:
   ```bash
   hostname -I
   ```

2. Verificar firewall:
   ```bash
   sudo ufw allow 8080
   sudo ufw status
   ```

3. Verificar que el servidor está escuchando:
   ```bash
   netstat -tulpn | grep 8080
   ```

---

### Problema: Datos no se actualizan

**Síntoma:** Dashboard muestra datos viejos o "Loading..."

**Solución:**

1. Verificar que el bot de trading está corriendo:
   ```bash
   ps aux | grep crypto-trade
   ```

2. Verificar archivos JSON:
   ```bash
   ls -la /home/overgon/.openclaw/workspace/crypto-bots/*-trade-state.json
   ```

3. Revisar logs del dashboard:
   ```bash
   tail -f /tmp/dashboard.log
   ```

---

### Problema: Alertas sonoras no funcionan

**Síntoma:** No suena la alerta cuando está cerca de TP.

**Solución:**

1. Verificar que el archivo de sonido existe:
   ```bash
   ls -la static/sounds/alert.mp3
   ```

2. Los navegadores requieren interacción del usuario para reproducir sonido. Hacer click en la página primero.

3. Verificar volumen del sistema.

---

## SEGURIDAD

### 🔐 Best Practices

#### 1. No Exponer a Internet Pública

**Riesgo:** El dashboard no tiene autenticación.

**Mitigación:**
- Solo acceder desde red local
- Usar VPN (Tailscale, WireGuard)
- Si es necesario exponer, usar reverse proxy con auth

#### 2. Firewall Configurado

```bash
# Solo permitir desde red local
sudo ufw allow from 192.168.3.0/24 to any port 8080

# Denegar desde internet
sudo ufw deny 8080
```

#### 3. HTTPS (Opcional pero Recomendado)

Si exponés el dashboard, usar HTTPS:

```bash
# Instalar certbot
sudo apt install certbot python3-certbot-nginx

# Obtener certificado
sudo certbot --nginx -d tu-dominio.com
```

#### 4. Autenticación Básica (Opcional)

Agregar auth a Flask:

```python
from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    if username == "admin" and password == "tu_password":
        return True

@app.route('/api/data')
@auth.login_required
def api_data():
    ...
```

---

### 🔒 Checklist de Seguridad

- [ ] Firewall configurado (ufw)
- [ ] Solo acceso desde red local
- [ ] No exponer puerto 8080 a internet
- [ ] Contraseñas fuertes si usás auth
- [ ] HTTPS si exponés públicamente
- [ ] Monitorear logs de acceso
- [ ] Actualizar Flask regularmente

---

## MANTENIMIENTO

### Diario

- Verificar que el dashboard está corriendo
- Revisar logs de errores
- Verificar que los datos se actualizan

```bash
# Verificar proceso
ps aux | grep "python3 app.py"

# Verificar logs
tail -f /tmp/dashboard.log

# Verificar actualización
curl http://localhost:8080/api/health
```

### Semanal

- Revisar uso de memoria
- Limpiar logs viejos
- Verificar actualizaciones de Flask

```bash
# Uso de memoria
ps aux | grep python3 | awk '{print $2, $6}'

# Limpiar logs viejos
find /tmp -name "*.log" -mtime +7 -delete

# Verificar actualizaciones
pip3 list --outdated | grep flask
```

### Mensual

- Actualizar Flask si hay nueva versión
- Revisar configuración de seguridad
- Backup de configuración

```bash
# Actualizar Flask
pip3 install --upgrade flask

# Backup de configuración
cp -r dashboard/ ~/backups/dashboard-$(date +%Y%m%d)/
```

---

## DESARROLLO

### Agregar Nueva Feature

1. **Crear branch:**
   ```bash
   git checkout -b feature/nueva-feature
   ```

2. **Implementar cambios:**
   - Backend: `app.py`
   - Frontend: `static/js/app.js`, `templates/index.html`
   - Estilos: `static/css/style.css`

3. **Testear localmente:**
   ```bash
   ./start.sh
   # Acceder a http://localhost:8080
   ```

4. **Commit y push:**
   ```bash
   git add .
   git commit -m "✨ Add: nueva feature"
   git push origin feature/nueva-feature
   ```

### Estándares de Código

#### Python (Backend)

```python
# Usar docstrings
def get_portfolio_value():
    """Obtener valor total del portfolio"""
    ...

# Usar type hints
def update_portfolio(data: dict) -> None:
    ...

# Manejar errores
try:
    result = subprocess.run(cmd, shell=True, capture_output=True)
except Exception as e:
    print(f"Error: {e}")
```

#### JavaScript (Frontend)

```javascript
// Usar const/let en vez de var
const CONFIG = {
    REFRESH_INTERVAL: 10000
};

// Usar async/await
async function loadData() {
    try {
        const response = await fetch(CONFIG.API_URL);
        const data = await response.json();
        updateUI(data);
    } catch (error) {
        console.error('Error:', error);
    }
}

// Comentarios descriptivos
// Calcular progreso a TP1
let progress = ((currentPrice - entryPrice) / (tp1 - entryPrice)) * 100;
```

#### CSS (Estilos)

```css
/* Usar variables para colores */
:root {
    --neon-blue: #00f3ff;
    --neon-pink: #ff00ff;
}

/* Comentarios para secciones */
/* ════════════════════════════════
   HEADER STYLES
   ════════════════════════════════ */
.cyber-header {
    ...
}
```

---

## SOPORTE

### Documentación Adicional

- [README.md](../README.md) - Guía principal del proyecto
- [SECURITY.md](../SECURITY.md) - Políticas de seguridad
- [INSTALL.md](../INSTALL.md) - Guía de instalación completa

### Contacto

- **GitHub:** [github.com/overgon/perrobotillo-trading-bot](https://github.com/overgon/perrobotillo-trading-bot)
- **Discord:** [OpenClaw Discord](https://discord.com/invite/clawd)
- **Issues:** [GitHub Issues](https://github.com/overgon/perrobotillo-trading-bot/issues)

---

<div align="center">

**🐕 Perrobotillo Trading Bot**  
*"Nunca confiar, siempre verificar"*

**Versión:** 1.0 Cyberpunk Edition  
**Última Actualización:** 2026-05-03

</div>
