# 🚀 AUTO-RESUME SYSTEM - Documentación

## Overview

Sistema automático para reactivar trading de monedas pausadas cuando las condiciones mejoran.

---

## 📋 CRITERIOS DE REACTIVACIÓN

**Basta que UNO de estos criterios se cumpla:**

### 📊 Criterio 1: PERFORMANCE

- ✅ **Win Rate ≥ 50%** en últimos 10 trades
- ✅ **5+ trades ganadores consecutivos**

### 📈 Criterio 2: MERCADO

- ✅ **BTC > EMA20** (tendencia alcista)
- ✅ **Fear & Greed > 40** (optimismo del mercado)

---

## ⏰ FRECUENCIA DE EJECUCIÓN

```bash
# Cron job - cada 6 horas
0 */6 * * * /home/overgon/.openclaw/workspace/crypto-bots/auto-resume-trading.sh
```

Horarios de revisión (hora México):
- 00:00, 06:00, 12:00, 18:00 CST

---

## 📝 EJEMPLO DE NOTIFICACIÓN TELEGRAM

```
✅ TRADING REANUDADO - BTC

📊 Performance: Win Rate 55.0% >= 50% | WR=55.0% | Consec=2
📈 Mercado: BTC $76500 > EMA20 $75200 | F&G 45 > 40 (optimismo)

🚀 Bot reactivado automáticamente - Monitoreando TPs...

Nota: La reactivación fue automática porque al menos uno de 
los criterios se cumplió:
• Win Rate últimos 10 trades ≥ 50% O 5+ wins consecutivos
• O BTC > EMA20 Y Fear & Greed > 40

¡Nunca confiar, siempre verificar! 🐕
```

---

## 🔧 ARCHIVOS INVOLUCRADOS

| Archivo | Propósito |
|---------|-----------|
| `crypto-bots/auto-resume-trading.sh` | Script principal |
| `crypto-bots/{COIN}-ml-pause-flag.json` | Flag de pausa por moneda |
| `crypto-bots/trade-history.json` | Histórico para calcular WR |
| `backtest/data/BTCUSDT_historical.csv` | Datos para EMA20 |
| `crypto-bots/dynamic-config.env` | Fear & Greed value |
| `logs/auto-resume.log` | Logs de ejecución |

---

## 🧪 TESTING MANUAL

```bash
# Ejecutar manualmente para testing
bash /home/overgon/.openclaw/workspace/crypto-bots/auto-resume-trading.sh

# Ver logs
tail -f /home/overgon/.openclaw/logs/auto-resume.log
```

---

## 🎯 CASOS DE USO

### Caso 1: Pausa por Bajo Performance
- **Escenario:** Moneda con WR < 40% en últimos 10 trades
- **Acción:** Se pausa automáticamente (ML Risk Detector)
- **Reactivación:** Cuando WR ≥ 50% en siguientes 10 trades

### Caso 2: Pausa por Mercado Bajista
- **Escenario:** BTC < EMA20 + Fear & Greed < 40
- **Acción:** ML Risk Detector pausa monedas afectadas
- **Reactivación:** Cuando mercado muestra señales de recuperación

### Caso 3: Pausa Manual (Auditoría)
- **Escenario:** Admin pausa manualmente (como BTC/ETH el 28-May)
- **Acción:** Editar JSON con `"paused": true`
- **Reactivación:** Automática cuando criterios se cumplen ✅

---

## 🛠️ AJUSTES RECOMENDADOS

Si los criterios son muy estrictos o muy laxos, ajustar en `auto-resume-trading.sh`:

```bash
# Línea ~80 - Win Rate mínimo
if win_rate >= 50:  # Cambiar a 45 o 55

# Línea ~85 - Rachas consecutivas
if consecutive_wins >= 5:  # Cambiar a 3 o 7

# Línea ~130 - Fear & Greed mínimo
if fg_value > 40:  # Cambiar a 35 o 45
```

---

## 🐕 NOTAS IMPORTANTES

1. **No interfiere con ML Risk Detector** - Trabajan en paralelo
2. **Notifica cada reactivación** - Evita spam (solo cuando cambia estado)
3. **Verifica TODAS las monedas** - No solo BTC/ETH
4. **Logs detallados** - Para debugging y auditoría

---

_Implementado: 2026-05-28_  
_Por: Perrobotillo 🐕_
