# 🐕 WATCHDOG - Configuración Actualizada

## 📋 Cambios Realizados (2026-06-16 11:11 AM)

### ✅ Dashboard Update
**ANTES:** Cada 5 min  
**AHORA:** Cada hora (`0 * * * *`)  
**Razón:** Optimizar recursos, el watchdog vigila constantemente

### ⚠️ Watchdog Grid
**ANTES:** Corría en background, notificaba todo  
**AHORA:** 
- Corre cada 10 min (unchanged)
- **NOTIFICA SOLO EN INCIDENTES:**
  - 🚨 Grid bot detenido → Notifica y repara
  - ❌ Reinicio fallido → Notifica urgente
  - ⚠️ Rebalanceo fallido → Notifica con error
  - ✅ Reinicio exitoso → Notifica confirmación
- **NO NOTIFICA:**
  - Rebalanceos exitosos (silencioso)
  - Dashboard updates (silencioso)
  - Todo operativo (silencioso = todo bien)

### ✅ Memory Search
**SIN CAMBIOS:** 4x día (00:00, 06:00, 12:00, 18:00)

### ❌ Status Hourly
**ANTES:** Reporte hourly  
**AHORA:** **DESACTIVADO** (redundante con watchdog + dashboard hourly)

### ✅ Reporte Diario 9 AM
**SIN CAMBIOS:** Diario 9 AM

---

## 📊 Cron Jobs Activos (Final)

| Job | Schedule | Notifica | Status |
|-----|----------|----------|--------|
| watchdog-grid | `*/10 * * * *` | Solo incidentes | ✅ Activo |
| update-grid-status | `0 * * * *` | Nunca | ✅ Activo |
| memory-search | `0 0,6,12,18 * * *` | Solo hallazgos >0.6 | ✅ Activo |
| daily-report-9am | `0 9 * * *` | Siempre | ✅ Activo |

**Total:** 4 jobs activos (antes: 5)

---

## 🚨 Incidentes que Disparan Notificación

El watchdog ahora notifica **SOLO** cuando:

1. **🚨 Grid Bot Detenido**
   ```
   ✅ Grid Bots Reiniciados
   PID: 12345
   Sistema recuperado ✅
   ```

2. **❌ Reinicio Fallido**
   ```
   🚨 ALERTA CRÍTICA
   ❌ Falló reinicio de grid bots
   PID: 12345 no sobrevivió
   Requiere atención manual inmediata 🆘
   ```

3. **⚠️ Rebalanceo Fallido**
   ```
   ⚠️ Rebalanceo Fallido
   Error: [detalle del error]
   Requiere revisión 🔧
   ```

4. **📊 Rebalanceo Exitoso** (solo si hubo trades)
   ```
   📊 Rebalanceo Completado
   Trades ejecutados: 2
   Portfolio optimizado ✅
   ```

---

## 🔇 Modo Silencioso (Operación Normal)

Cuando **todo está operativo**:
- ❌ NO notifica dashboard update hourly
- ❌ NO notifica chequeos watchdog exitosos
- ❌ NO notifica heartbeat OK
- ✅ **Silencio = Todo bien**

---

## 📝 Archivos Actualizados

- `scripts/watchdog-grid.sh` → Lógica de notificación mejorada
- Cron job `update-grid-status-5min` → Cambiado a hourly
- Cron job `update-grid-status` (hourly legacy) → **Desactivado**

---

_Última actualización: 2026-06-16 11:15 AM_  
_🐕 Perrobotillo Trading Bot_
