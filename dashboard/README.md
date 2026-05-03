# 🐕 Perrobotillo Dashboard - Cyberpunk Edition

**Dashboard avanzado de monitoreo para Perrobotillo Trading Bot**

---

## 🚀 INICIO RÁPIDO

### 1. Iniciar el Dashboard

```bash
cd /home/overgon/.openclaw/workspace/dashboard
./start.sh
```

### 2. Acceder desde el navegador

**Desde la Raspberry Pi:**
```
http://localhost:8080
```

**Desde tu PC/Móvil en la misma red:**
```
http://192.168.3.215:8080
```

---

## 📊 FEATURES

### ✅ En Tiempo Real (auto-refresh cada 10s)

- 💰 **Portfolio Total** - USDT y MXN
- 📈 **P&L 24h** - Ganancias/pérdidas del día
- 🎯 **21 Slots Activos** - 3 por moneda (BTC, ETH, BNB, SOL, LINK, XRP, AVAX)
- 📊 **Barras de Progreso** - Distancia a TP1/TP2/TP3
- 💹 **Precios en Vivo** - Desde Binance API
- 📉 **Histórico de Trades** - Últimos 10 trades
- 🏆 **Win Rate** - Estadísticas de performance
- 🔧 **System Status** - API, IP Whitelist, Gateway

### 🎨 Diseño Cyberpunk

- 🌐 Grid animado en background
- 💙 Colores neón (azul, pink, purple)
- ⚡ Efectos de scanlines
- 🔊 Alertas sonoras (cuando está cerca de TP)
- 📱 Responsive (PC, tablet, móvil)

---

## 🎯 SECCIONES DEL DASHBOARD

### 1. Portfolio Overview
- Total del portfolio en USDT y MXN
- P&L de 24 horas con porcentaje
- Win Rate actual (W/L)
- Total de trades y P&L neto

### 2. Active Slots
Cada slot muestra:
- Moneda y número de slot
- Status (ACTIVE / READY / CLOSED)
- Entry Price vs Current Price
- P&L en tiempo real ($ y %)
- TP1, TP2, TP3 targets
- **Barra de progreso** a TP1 (solo activos)

### 3. Price Charts
- Precios actuales de todas las coins
- Actualización cada 5 segundos
- Cambio 24h en porcentaje

### 4. Recent Trades
- Últimos 10 trades cerrados
- Entry, Exit, P&L
- Tipo de cierre (TP1/TP2/TP3/SL/TRAILING)
- Fecha del trade

### 5. System Status
- API Binance: Online/Offline
- IP Whitelist: Tu IP pública
- Gateway OpenClaw: Status
- Última actualización

---

## ⚙️ CONFIGURACIÓN

### Cambiar puerto

Editar `app.py`:
```python
app.run(
    host='0.0.0.0',
    port=8080,  # Cambiar aquí
    debug=False,
    threaded=True
)
```

### Cambiar refresh interval

Editar `static/js/app.js`:
```javascript
const CONFIG = {
    REFRESH_INTERVAL: 10000, // Cambiar aquí (ms)
    ...
};
```

### Habilitar alertas sonoras

Las alertas suenan cuando una coin está a <0.5% de TP1.

Para cambiar el umbral, editar `static/js/app.js`:
```javascript
if (distance > 0 && distance < 0.5) {  // Cambiar 0.5
    triggerAlert(coin, slotId, distance);
}
```

---

## 🔧 TROUBLESHOOTING

### "Flask not found"
```bash
pip3 install flask --break-system-packages
```

### "Port already in use"
```bash
# Matar proceso usando el puerto 8080
sudo lsof -ti:8080 | xargs kill -9
```

### "Cannot access from network"
```bash
# Verificar IP de la Raspberry Pi
hostname -I

# Asegurarte que el firewall permite el puerto 8080
sudo ufw allow 8080
```

### Dashboard no actualiza
- Verificar que el bot de trading esté corriendo
- Verificar conexión a internet
- Revisar logs: `tail -f logs/trade-*.log`

---

## 🛑 DETENER EL DASHBOARD

Presionar `Ctrl+C` en la terminal donde está corriendo.

---

## 📱 ACCESO REMOTO

### Desde tu móvil (misma red WiFi):
```
http://192.168.3.215:8080
```

### Desde tu PC (misma red):
```
http://192.168.3.215:8080
```

### Para acceso externo (fuera de casa):
Se requiere configurar:
1. Port forwarding en tu router
2. O usar Tailscale/VPN
3. O usar ngrok

**No recomendado sin seguridad adicional.**

---

## 🎨 PERSONALIZACIÓN

### Cambiar colores

Editar `static/css/style.css`:
```css
:root {
    --neon-blue: #00f3ff;      /* Cambiar */
    --neon-pink: #ff00ff;      /* Cambiar */
    --neon-purple: #bc13fe;    /* Cambiar */
    --neon-green: #0aff00;     /* Cambiar */
    --neon-red: #ff003c;       /* Cambiar */
}
```

### Cambiar logo

Editar `templates/index.html`:
```html
<div class="logo-icon">🐕</div>  <!-- Cambiar emoji -->
```

O agregar una imagen:
```html
<img src="{{ url_for('static', filename='images/logo.png') }}" class="logo-icon">
```

---

## 📊 API ENDPOINTS

El dashboard expone estos endpoints para uso externo:

### `/api/data`
Datos completos del portfolio y slots.

```json
{
  "timestamp": "2026-05-03T13:30:00",
  "portfolio": {
    "total_usdt": 2628.74,
    "total_mxn": 45976.73
  },
  "coins": {...},
  "prices": {...},
  "history": {...},
  "system": {...}
}
```

### `/api/prices`
Solo precios actuales (más rápido).

```json
{
  "BTCUSDT": "78741.01000000",
  "ETHUSDT": "2328.44000000",
  ...
}
```

### `/api/health`
Health check del servidor.

```json
{
  "status": "ok",
  "timestamp": "2026-05-03T13:30:00"
}
```

---

## 🐕 CRÉDITOS

**Desarrollado por:** Perrobotillo 🐕  
**Para:** Jefe (Rull Ox)  
**Versión:** 1.0 Cyberpunk Edition  
**Fecha:** 2026-05-03

*"Nunca confiar, siempre verificar"*

---

<div align="center">

**🚀 Enjoy the dashboard, Jefe!**

</div>
