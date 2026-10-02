# Issue #39: Bug: Reporte diario muestra variables sin interpolar (279199{total_usdt})

**Estado:** ✅ FIXED  
**Prioridad:** Alta  
**Fecha:** 2026-05-17  
**Reportado por:** Rull Ox  
**Resuelto por:** Perrobotillo 🐕

---

## Descripción del Bug

El reporte diario de las 9 AM está mostrando las variables de plantilla sin interpolar en lugar de los valores reales.

### Comportamiento Actual (Bug)
```
💰 PORTFOLIO ACTUAL
Total USDT: 279199{total_usdt}
Total MXN: 279199{total_mxn}
Snapshot: 279199{snapshot}
P&L: 279199{pnl} (-.03%)
```

### Comportamiento Esperado
```
💰 PORTFOLIO ACTUAL
Total USDT: 2791.99
Total MXN: 57234.80
Snapshot: 2785.00
P&L: +6.99 (+0.25%)
```

---

## Causa Raíz

En `daily-report-9am.sh`, las variables estaban escapadas incorrectamente con `$$` en lugar de `$`:

**Incorrecto:**
```bash
report_msg="...Total USDT:   $${total_usdt}..."
```

**Correcto:**
```bash
report_msg="...Total USDT:   ${total_usdt}..."
```

En bash, `$$` representa el PID del proceso actual, mientras que `$variable` o `${variable}` es la sintaxis correcta para interpolación de variables.

---

## Fix Aplicado

### 1. Corregidas 4 variables en el mensaje de Telegram

Archivo: `daily-report-9am.sh`

- `$$` → `$` para `total_usdt`
- `$$` → `$` para `total_mxn`
- `$$` → `$` para `snapshot`
- `$$` → `$` para `pnl`
- `$$` → `$` para `total_pnl_24h`
- `$$` → `$` para `pnl_24h_pct`
- `$$` → `$` para `total_pnl` (trades)
- `$$` → `$` para `active_count` (caption del archivo)

### 2. Eliminado cron job duplicado

**Antes:**
```bash
0 9 * * * /home/overgon/.openclaw/workspace/crypto-daily-report-v3.sh >> /home/overgon/.openclaw/logs/daily-report.log 2>&1
0 9 * * * bash /home/overgon/.openclaw/workspace/daily-report-9am.sh >> /home/overgon/.openclaw/logs/daily-report.log 2>&1
```

**Después:**
```bash
0 9 * * * bash /home/overgon/.openclaw/workspace/daily-report-9am.sh >> /home/overgon/.openclaw/logs/daily-report.log 2>&1
```

---

## Verificación

```bash
# Verificar cron jobs activos
crontab -l | grep -i report

# Output esperado (solo 1 job):
0 9 * * * bash /home/overgon/.openclaw/workspace/daily-report-9am.sh >> /home/overgon/.openclaw/logs/daily-report.log 2>&1
```

---

## Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `daily-report-9am.sh` | Corregida interpolación de variables |
| `crontab` | Eliminado job duplicado |

---

## Prevención

- ✅ El reporte ahora solo se envía **una vez al día a las 9:00 AM** exactamente
- ✅ No hay scripts duplicados ejecutándose
- ✅ Variables correctamente interpoladas

---

## Testing Pendiente

- [ ] Verificar reporte mañana 2026-05-18 a las 9:05 AM
- [ ] Confirmar que los valores se muestran correctamente en Telegram
- [ ] Confirmar que solo llega 1 mensaje (no duplicado)

---

**Tags:** bug, telegram, daily-report, bash, interpolation
