# 🐕 PERROBOTILLO TRADING BOT - CHEATSHEET OPERATIVO

> **Última actualización:** 2026-10-21
> **Estado:** Operativo — 8 monedas, 23/24 slots ACTIVE
> **Coins activas:** BTC, ETH, BNB, SOL, LINK, XRP, AVAX, ZEC
> **Slots totales:** 24 (3 por moneda, max)
> **Capital Spot:** Consultar en vivo vía `scripts/balance-now.sh`

---

## 🎯 Qué es este archivo
Lista los **scripts que un operador puede correr manualmente**, con una descripción breve y el comando exacto. Acá no va teoría larga: solo pasos accionables.

---

## 🤖 Bot principal

### `crypto-trade-moneda-v3-slots.sh <COIN>`
**Ubicación:** `/home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh`

**Qué hace:** Ejecuta un ciclo completo de trading para la moneda indicada: lee balance, consulta ML, valida señal, ejecuta orden y actualiza slots.

**Cuándo usarlo:**
- Smoke test manual
- Diagnóstico por moneda
- Verificar comportamiento en vivo

**Ejemplos:**
```bash
cd /home/overgon/.openclaw/workspace
./crypto-trade-moneda-v3-slots.sh BTC
./crypto-trade-moneda-v3-slots.sh ETH
./crypto-trade-moneda-v3-slots.sh ZEC
```

**Notas:**
- Respeta lock `.SYMBOL-trading.lock` (no forzar si otro ciclo está corriendo).
- Usa `recvWindow=60000` y defaults seguros para SL/TP.

---

## 🧠 ML

### `ml/auto-retrain-v2.py`
**Ubicación:** `/home/overgon/.openclaw/workspace/ml/auto-retrain-v2.py`

**Qué hace:** Reentrena los modelos optimizados del día si corresponde.

**Cuándo usarlo:**
- Después de muchos trades nuevos
- Para forzar actualización porque el modelo se siente desfasado
- Troubleshooting del cron de retrain

**Ejemplo:**
```bash
cd /home/overgon/.openclaw/workspace/ml
source ../venv/bin/activate
python3 auto-retrain-v2.py
```

**Criterios que aplica hoy:**
- Modelo > 7 días
- Accuracy < 85%
- ≥10 trades nuevos desde último entrenamiento
- Modelo no existe

---

## 🛡️ Reconciliación Binance ↔ State

### `scripts/reconcile-binance-state.py`
**Ubicación:** `/home/overgon/.openclaw/workspace/scripts/reconcile-binance-state.py`

**Qué hace:** Compara el estado local de slots con órdenes y balances reales en Binance. Reporta inconsistencias sin cerrar posiciones activas.

**Cuándo usarlo:**
- Después de un bug de parsing
- Cuando un slot queda ACTIVE pero no se ve en exchange
- Auditoria semanal

**Ejemplo:**
```bash
cd /home/overgon/.openclaw/workspace
python3 scripts/reconcile-binance-state.py
```

---

## 📈 TP/SL monitor

### `scripts/tp-monitor.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/scripts/tp-monitor.sh`

**Qué hace:** Monitorea TP1/TP2/TP3 y SL de trades activos. Notifica cuando se cumplen niveles.

**Cuándo usarlo:**
- Verificar que un trade activo está siendo monitoreado
- Revisar alcances de TP/SL en vivo

**Ejemplo:**
```bash
cd /home/overgon/.openclaw/workspace
bash scripts/tp-monitor.sh ZEC
```

### `scripts/check-tp.py`
**Ubicación:** `/home/overgon/.openclaw/workspace/scripts/check-tp.py`

**Qué hace:** Respaldo en Python del monitor TP/SL.

**Ejemplo:**
```bash
cd /home/overgon/.openclaw/workspace
python3 scripts/check-tp.py AVAX
```

---

## 📊 Dashboard

### Endpoints útiles
```bash
# Portfolio actual
curl http://127.0.0.1:8080/api/portfolio

# Status / trades
curl http://127.0.0.1:8080/api/status
```

**Frontend:** `dashboard/static/js/app.js` consume `/api/portfolio` de forma estable.

---

## ⚙️ Configuración editable por operador

### `crypto-bots/market-mode.conf`
Define modo de mercado y overrides por moneda.

**Ejemplo real actual:**
```
MARKET_MODE="LATERAL"
AVAX_SL=3.5
BNB_TP1=3.0
SOL_TP2=5.5
```

### `crypto-bots/dynamic-config.env`
Parámetros generales: limites diarios, modo default, etc.

---

## 🧰 Utilidades

### `scripts/balance-now.sh`
Saldo Spot USDT en formato JSON.

```bash
cd /home/overgon/.openclaw/workspace
bash scripts/balance-now.sh
```

### `scripts/watchdog-bots-vivos.sh`
Verifica que los bots estén vivos y revive si corresponde.

```bash
cd /home/overgon/.openclaw/workspace
bash scripts/watchdog-bots-vivos.sh
```

---

## 🚨 Emergencias

### Si el bot abre trades sin querer / comportamiento raro
```bash
# 1. Resetear pause global
echo '{}' > /home/overgon/.openclaw/workspace/crypto-bots/global-pause-flag.json

# 2. Revisar logs
tail -n 200 /home/overgon/.openclaw/logs/cron-BNB.log
tail -n 200 /home/overgon/.openclaw/logs/ml-auto-retrain.log
```

### Si hay discrepancy con Binance
```bash
python3 /home/overgon/.openclaw/workspace/scripts/reconcile-binance-state.py
```

---

## 📌 Notas de operación

- **No agregar capital manualmente sin coordinación.**
- **No desactivar ML validator ni fallback.** Solo reentrenar.
- **No subir** `secrets/binance.env` ni backups sensibles.
- El repo mantiene código, docs y modelos ML entrenados. El estado vivo (trade-state.json, logs, cache) se genera en runtime y está en `.gitignore`.
