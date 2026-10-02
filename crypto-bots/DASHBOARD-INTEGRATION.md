# 📊 Dashboard Integration - Circuit Breaker Countdown

## 🔧 Integración del Circuit Breaker Status

### Archivo de Estado
**Ubicación:** `crypto-bots/dashboard-circuit-breaker-status.json`

Este archivo se actualiza automáticamente cada minuto con:
- Estado del Circuit Breaker (ON/OFF)
- Countdown de tiempo restante
- Operaciones permitidas/bloqueadas
- Progreso hacia auto-resume

---

## 🎨 Visualización en Dashboard

### Sección: "Estrategia Actual"

Agregar debajo de la estrategia actual:

```html
<!-- Circuit Breaker Status -->
<div id="circuit-breaker-status" class="status-card">
  <div class="status-header">
    <span class="status-icon">🔴</span>
    <span class="status-title">Circuit Breaker</span>
    <span class="status-badge">ON</span>
  </div>
  
  <div class="countdown-container">
    <div class="countdown-label">Tiempo restante:</div>
    <div class="countdown-timer" id="cb-countdown">
      <span class="hours" id="cb-hours">9</span>h
      <span class="minutes" id="cb-minutes">19</span>m
      <span class="seconds" id="cb-seconds">58</span>s
    </div>
    
    <!-- Progress Bar -->
    <div class="progress-bar">
      <div class="progress-fill" id="cb-progress" style="width: 61.1%"></div>
    </div>
    <div class="progress-text">61.1% completado</div>
    
    <!-- Auto Resume Time -->
    <div class="auto-resume">
      🕐 Auto-resume: <strong>2026-06-04 00:22:01</strong>
    </div>
  </div>
  
  <!-- Allowed/Blocked Operations -->
  <div class="operations-grid">
    <div class="allowed">
      <h4>✅ Permitido</h4>
      <ul>
        <li>SL Management</li>
        <li>TP Management</li>
        <li>Emergency Close</li>
      </ul>
    </div>
    <div class="blocked">
      <h4>❌ Bloqueado</h4>
      <ul>
        <li>New Entries</li>
        <li>DCA Operations</li>
      </ul>
    </div>
  </div>
  
  <!-- Trigger Info -->
  <div class="trigger-info">
    <strong>Causa:</strong> loss_rate (3 pérdidas en 24h)
  </div>
</div>
```

---

## 🔄 Actualización Automática

### Opción 1: Polling JavaScript (Recomendado)

```javascript
// dashboard.js
async function updateCircuitBreakerStatus() {
  try {
    const response = await fetch('/api/crypto-bots/dashboard-circuit-breaker-status.json');
    const status = await response.json();
    
    if (status.circuitBreakerActive) {
      document.getElementById('circuit-breaker-status').style.display = 'block';
      document.getElementById('cb-hours').textContent = status.timeRemaining.hours;
      document.getElementById('cb-minutes').textContent = status.timeRemaining.minutes;
      document.getElementById('cb-seconds').textContent = status.timeRemaining.seconds;
      document.getElementById('cb-progress').style.width = `${status.timeRemaining.progress * 100}%`;
      
      // Actualizar cada segundo para countdown suave
      startCountdown(status.timeRemaining.totalSeconds);
    } else {
      document.getElementById('circuit-breaker-status').style.display = 'none';
    }
  } catch (error) {
    console.error('Error al obtener estado del Circuit Breaker:', error);
  }
}

function startCountdown(totalSeconds) {
  let remaining = totalSeconds;
  const interval = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
      clearInterval(interval);
      updateCircuitBreakerStatus(); // Recargar estado
      return;
    }
    
    const hours = Math.floor(remaining / 3600);
    const minutes = Math.floor((remaining % 3600) / 60);
    const seconds = remaining % 60;
    
    document.getElementById('cb-hours').textContent = hours;
    document.getElementById('cb-minutes').textContent = minutes;
    document.getElementById('cb-seconds').textContent = seconds;
  }, 1000);
}

// Actualizar cada minuto
setInterval(updateCircuitBreakerStatus, 60000);
updateCircuitBreakerStatus(); // Primera carga inmediata
```

---

### Opción 2: Cron Job + WebSocket

```bash
# Agregar a crontab - cada minuto
* * * * * cd /home/overgon/.openclaw/workspace/crypto-bots && python3 update-circuit-breaker-countdown.py > /dev/null 2>&1
```

El dashboard puede escuchar cambios en el archivo o hacer polling.

---

## 📍 Ubicación en Dashboard

```
┌─────────────────────────────────────────┐
│  ESTRATEGIA ACTUAL                      │
│  Dinámica (Auto-Ajuste)                 │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  🔴 CIRCUIT BREAKER [COUNTDOWN]         │  ← AGREGAR AQUÍ
│  9h 19m 58s restantes                   │
│  ████████████░░░░░░░░░ 61.1%            │
│  Auto-resume: 2026-06-04 00:22:01       │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  PORTFOLIO                              │
│  ...                                    │
└─────────────────────────────────────────┘
```

---

## 🎨 Estilos CSS Sugeridos

```css
.status-card {
  background: linear-gradient(135deg, #ff4444 0%, #cc0000 100%);
  border-radius: 8px;
  padding: 16px;
  margin: 16px 0;
  color: white;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.status-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.2em;
  font-weight: bold;
  margin-bottom: 12px;
}

.status-badge {
  background: rgba(255,255,255,0.2);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
}

.countdown-timer {
  font-family: 'Courier New', monospace;
  font-size: 2em;
  text-align: center;
  margin: 12px 0;
}

.progress-bar {
  background: rgba(255,255,255,0.2);
  border-radius: 4px;
  height: 8px;
  overflow: hidden;
  margin: 8px 0;
}

.progress-fill {
  background: #00ff00;
  height: 100%;
  transition: width 1s linear;
}

.operations-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}

.allowed h4 { color: #00ff00; }
.blocked h4 { color: #ff9999; }

.auto-resume {
  text-align: center;
  margin-top: 12px;
  font-size: 0.9em;
  opacity: 0.9;
}
```

---

## 🧪 Testing

Para probar la integración:

```bash
# Ejecutar actualización manual
python3 update-circuit-breaker-countdown.py

# Ver archivo generado
cat dashboard-circuit-breaker-status.json | jq .

# Simular fin de pausa (testing)
echo '{"pause_until": "2026-06-03 15:05:00"}' > global-pause-flag.json
python3 update-circuit-breaker-countdown.py
```

---

## 📊 Respuesta: BTC Slots 1 y 3

**Estado actual:**
- ✅ **BTC Slot 1:** CLOSED_MANUAL (no tiene pause)
- ✅ **BTC Slot 3:** CLOSED_UNKNOWN (no tiene pause)

**No hay pause específico para BTC.** El pause es **GLOBAL** por el Circuit Breaker.

**Tiempo para desactivación:**
- ⏰ **Faltan:** 9h 19m (aproximadamente)
- 🕐 **Auto-resume:** 2026-06-04 00:22:01 CST
- 📊 **Progreso:** 61.1% completado

**Mientras el Circuit Breaker esté activo:**
- ✅ Se permiten: SL, TP, Emergency Close
- ❌ Bloqueado: Nuevas entradas, DCA

---

_Generated by Perrobotillo Dashboard Integration System_ 🐕
