# 🐕 Perrobotillo - Cambios Recientes

## 📅 2026-05-30 - Sistema de Sonidos TP/SL + Fixes Dashboard

### 🔔 NUEVO: Sistema de Sonidos para TP Hits y Stop Loss

#### Archivos Modificados:
- `dashboard/static/js/app.js`
- `dashboard/static/sounds/cash-register.wav` (existente)
- `dashboard/static/sounds/stop-loss.mp3` (nuevo)

#### Cambios:

1. **Sonido para TP HIT** 💰
   - Archivo: `cash-register.wav`
   - Se reproduce cuando un slot alcanza TP1, TP2 o TP3
   - Volumen: 100%
   - Notificación visual en esquina superior derecha

2. **Sonido para STOP LOSS** 🛑
   - Archivo: `stop-loss.mp3`
   - Se reproduce cuando un slot toca el Stop Loss
   - Volumen: 100%
   - Notificación visual con ícono 🛑

3. **Audio Unlock Automático**
   - Se agregó listener para desbloquear audio con primer click/touch/tecla
   - Previene errores de navegadores que bloquean audio automático
   - Pre-carga silenciosa de ambos sonidos al iniciar

4. **Fix TypeError**
   - Se agregó verificación de `playPromise` antes de usar `.catch()`
   - Previene error: "can't access property 'catch', n() is undefined"

5. **Sistema de Notificaciones**
   - Set en memoria para trackear notificaciones ya reproducidas
   - Previene reproducción múltiple del mismo TP/SL
   - ID único por notificación: `${coin}-${slot_id}-${tp}-${timestamp}`

### 📊 Funcionamiento:

```javascript
// Check every 5 seconds
setInterval(checkTPNotifications, 5000);

// When TP/SL detected:
if (notif.tp === 'SL') {
    playStopLoss();  // 🛑 Sonido "loser"
} else {
    playCashRegister();  // 💰 Caja registradora
}
```

### 🎯 Flujo Completo:

1. **TP Monitor** (`scripts/tp-monitor.sh`) detecta TP/SL
2. Envía notificación a `dashboard/app.py` endpoint `/api/notify-tp`
3. Dashboard guarda en `crypto-bots/tp-notifications.json`
4. Frontend lee cada 5 segundos y detecta nuevas notificaciones
5. Reproduce sonido correspondiente
6. Muestra notificación visual por 5 segundos
7. Marca notificación como "played" en memoria

### ⚠️ Requisitos:

- Usuario debe hacer **click/tocar la página al menos una vez** para desbloquear audio
- Navegadores modernos bloquean audio automático por defecto
- El dashboard guarda el estado en memoria (se resetea al recargar página)

### 📁 Archivos Involucrados:

| Archivo | Propósito |
|---------|-----------|
| `dashboard/static/js/app.js` | Lógica de sonidos + audio unlock |
| `dashboard/static/sounds/cash-register.wav` | Sonido TP hit |
| `dashboard/static/sounds/stop-loss.mp3` | Sonido Stop Loss |
| `dashboard/templates/index.html` | Elementos `<audio>` |
| `dashboard/app.py` | Endpoint `/api/notify-tp` |
| `scripts/tp-monitor.sh` | Detecta TPs/SLs y notifica |
| `crypto-bots/tp-notifications.json` | Cola de notificaciones |

### 🧪 Testing:

- ✅ TP HIT → Caja registradora suena
- ✅ STOP LOSS → Sonido "loser" suena
- ✅ Notificaciones no se repiten
- ✅ Audio se desbloquea con primer click
- ✅ Sin errores en consola del navegador

### 🐛 Bugs Fixeados:

1. **TypeError: can't access property "catch"** - Fixed
2. **Reproducción infinita de sonidos** - Fixed con Set en memoria
3. **Audio bloqueado por navegador** - Fixed con user interaction listener

---

## 📝 Notas para Futuros Cambios:

- Los cambios en `app.js` son permanentes hasta que se sobrescriba el archivo
- Reiniciar el dashboard después de cambios: `sudo systemctl restart perrobotillo-dashboard.service`
- Para agregar nuevos sonidos: copiar a `dashboard/static/sounds/` y registrar en `app.js`
