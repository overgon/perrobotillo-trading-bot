# 🟠 Dashboard Emergency Mode - Naranja Metálico

## Cambios Realizados

### Fecha: 2026-06-03 21:45 CST
**Motivo:** Cuando el Circuit Breaker está activo (GLOBAL_PAUSE o EMERGENCY_CONSERVATIVE), los slots del dashboard ahora se muestran en **naranja metálico** con animación de pulso en lugar de gris/amarillo.

---

## Archivos Modificados

### 1. Backend - `dashboard/app.py`
- ✅ Agregada detección de circuit breaker status
- ✅ Lectura de `dashboard-circuit-breaker-status.json`
- ✅ Envío de `circuitBreakerActive` y `circuitStatus` en API response

```python
# 🟠 VERIFICAR CIRCUIT BREAKER STATUS
circuit_breaker_active = False
circuit_status = 'NORMAL'
try:
    with open(f'{CRYPTO_BOTS}/dashboard-circuit-breaker-status.json', 'r') as f:
        cb_data = json.load(f)
        circuit_breaker_active = cb_data.get('circuitBreakerActive', False)
        circuit_status = cb_data.get('status', 'NORMAL')
except:
    pass
```

### 2. Frontend Desktop - `dashboard/static/css/style.css`
- ✅ Nuevo estilo `.slot-card.emergency-pause` (naranja metálico #FF6B35)
- ✅ Animación `emergency-pulse` (2s infinite)
- ✅ Nuevo estilo `.slot-status.emergency-pause` (badge naranja)
- ✅ Animación `emergency-badge-pulse` (1.5s infinite)

### 3. Frontend Mobile - `dashboard/static/css/mobile.css`
- ✅ Mismos estilos que desktop para consistencia
- ✅ Naranja metálico #FF6B35 con animaciones

### 4. JavaScript Desktop - `dashboard/static/js/app.js`
- ✅ Detección de emergency mode en `updateSlots()`
- ✅ Aplicación dinámica de clase `emergency-pause` cuando CB activo
- ✅ Cambio de texto e íconos (🟠 en lugar de 🟡)

### 5. JavaScript Mobile - `dashboard/static/js/mobile.js`
- ✅ Misma lógica que desktop para consistencia
- ✅ Slots READY y CLOSED muestran naranja en emergency mode

---

## Comportamiento

### Cuando Circuit Breaker está INACTIVO:
- Slots READY: **Amarillo** 🟡 con estilo `.ready`
- Slots CLOSED: **Gris** ⏸️ con estilo `.pause`

### Cuando Circuit Breaker está ACTIVO (GLOBAL_PAUSE / EMERGENCY_CONSERVATIVE):
- Slots READY: **Naranja Metálico** 🟠 con estilo `.emergency-pause` + animación pulse
- Slots CLOSED: **Naranja Metálico** 🟠 con estilo `.emergency-pause` + animación pulse
- Texto cambia a "PAUSED (CB)" o "EMERGENCY PAUSE 🟠"

---

## Colores Usados

```css
/* Naranja Metálico Cyberpunk */
--metallic-orange: #FF6B35;
--metallic-orange-light: #FF8C42;

/* Efectos */
box-shadow: 0 0 25px rgba(255, 107, 53, 0.4);
animation: emergency-pulse 2s ease-in-out infinite;
```

---

## Pruebas

1. Abrir dashboard mientras Circuit Breaker está activo
2. Verificar que todos los slots muestran color naranja metálico
3. Verificar animación de pulso (2s ciclo)
4. Verificar badge de status también naranja
5. Probar en desktop y mobile

---

## Notas

- El color naranja metálico (#FF6B35) fue elegido para ser visible pero no alarmista como el rojo
- Las animaciones son sutiles (2s y 1.5s) para no distraer demasiado
- Compatible con ambos themes (desktop y mobile)
- Cache busting recomendado después del deploy

---

*Documentado por Perrobotillo 🐕*
