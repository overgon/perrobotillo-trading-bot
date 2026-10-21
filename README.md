# 🐕 Perrobotillo Trading Bot — FASE 1 v2.1

**Bot de trading automatizado para Binance Spot** con ML classifier, circuit breaker, IP whitelist monitor y dashboard cyberpunk.

> **"Nunca confiar, siempre verificar." — Jefe**

---

## 🏗️ ARQUITECTURA DEL SISTEMA

```
┌─────────────────────────────────────────────────────────┐
│                   Raspberry Pi 5                         │
│                   (Cron-based, no systemd)               │
├─────────────────────────────────────────────────────────┤
│  🤖 Trading Bot          🧠 ML Pipeline     📊 Dashboard │
│  crypto-trade-moneda-    auto-retrain-v2.py  app.py       │
│  v3-slots.sh             ml_validator_       static/js/  │
│  (8 coins, 24 slots)     wrapper.py          app.js      │
│  └─ TP1/TP2/TP3/SL       └─ models_optimized/ └─ mobile.js  │
│                                                         │
│  🛡️ Circuit Breaker    🕵️ IP Monitor      🔔 Notify     │
│  global-circuit-      ip-monitor.sh         notify.sh    │
│  breaker.sh                                send-telegram │
│                                                         │
│  📈 Reports          💾 Data               ⚙️ Config     │
│  daily-report.py     trade-history.json    dynamic-     │
│  monthly-report.sh   *-trade-state.json     config.env  │
│  housekeeping.sh     portfolio-*.json      market-      │
│                      balance-*.json        mode.conf      │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 ESPECIFICACIONES

| Componente | Detalle |
|---|---|
| **Monedas** | BTC, ETH, BNB, SOL, LINK, XRP, AVAX, ZEC |
| **Slots** | 24 (3 por moneda, max) |
| **Exchange** | Binance Spot |
| **ML** | RandomForest (8 modelos, 68-94% accuracy) |
| **CB** | Circuit Breaker (6 losses/24h → pausa) |
| **Schedule** | Cron-only (systemd reservado para watchs) |
| **Notify** | Telegram con `--data-urlencode` + `parse_mode=Markdown` |

---

## 🚀 INICIO RÁPIDO

### 1. Credenciales
```bash
# Secrets viven en secrets/ — NUNCA subir a git
ls secrets/
# binance.env     — BINANCE_API_KEY, BINANCE_API_SECRET
# telegram.env    — TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

### 2. Iniciar Dashboard
```bash
cd dashboard
./setup-auth.sh    # Configurar usuario/password HTTP Basic
./start.sh         # Inicia Flask en puerto 8080
# Local:      http://localhost:8080
# Red local:  http://192.168.3.215:8080
```

### 3. Verificar cron jobs
```bash
crontab -l
# */5 * * * *  → global-circuit-breaker.sh (CB monitor cada 5 min)
# 0 * * * *    → ip-monitor.sh (IP whitelist check cada hora)
# 0 9 * * *    → daily-report.py (reporte diario 9 AM CST)
# 0 3 * * 0   → auto-retrain-v2.py (ML retraining Sunday 3 AM)
```

---

## 🧠 ML PIPELINE

### Modelos
- 7 modelos RandomForest en `ml/models_optimized/`
- Features: SMA50, RSI(max_5/10/20), ROC(max_10)
- LINK: 5 features (overfitting arreglado, gap 3.32%)

### Retraining (Sunday 3 AM)
```bash
python3 ml/auto-retrain-v2.py
# Logs: ml/ml-retrain.log
```

### ML Validator
```bash
# Manual validation
python3 ml/ml_validator_wrapper.py BTC NORMAL LONG
# Returns: approved, confidence, position_size, reason
```

---

## 🛡️ CIRCUIT BREAKER

| Archivo | Propósito |
|---|---|
| `crypto-bots/global-pause-flag.json` | Estado live de CB |
| `crypto-bots/dashboard-circuit-breaker-status.json` | Sync con dashboard |
| `crypto-bots/global-circuit-breaker.sh` | Monitor (5 min cron) |

- **Trigger**: 6 losses/24h → pausa nuevos trades
- **SL/TP**: Siguen ejecutándose durante pausa
- **ML Validator**: Rechaza todos los trades si CB activo

---

## 🕵️ IP MONITOR

```bash
# Script
crypto-bots/ip-monitor.sh

# Cron: cada hora
0 * * * * bash crypto-bots/ip-monitor.sh

# Providers (dual):
# 1. ipify.org
# 2. api4.ip.works (fallback)
```

- IP registrada en `crypto-bots/last-known-ip.txt`
- Notifica via Telegram si cambia
- **Importante**: actualizar Binance IP Whitelist si cambia

---

## 📈 REPORTE DIARIO (9:00 AM CST)

```bash
python3 scripts/daily-report.py
```

Incluye:
- 💰 **Portfolio total** (USDT + MXN)
- 📊 **PnL 24h** por moneda
- 📈 **Trades del día anterior** (win rate, PnL)
- 🎯 **Trades activos** con status actual
- 🛡️ **Estado del sistema** (API, IP, órdenes)

### 🔧 Fix aplicado (PnL ceros):
- `parse_datetime_safe()` maneja timestamps con espacio (`YYYY-MM-DD HH:MM:SS`)
- Fallback logscan restringido a líneas reales de trade (no cron genérico)
- `totalTrades` derivado de `len(trades)` array

---

## 🔧 TRADE HISTORY DEDUP

### Bug histórico (arreglado):
El bot logueaba con `closeType: "SL"` y `log_trade_to_history.py` con `closeType: "CLOSED_SL"` → **duplicados**.

### Fix:
1. **Dedup check** en `scripts/log_trade_to_history.py`:
   - Key: `symbol:slotId:closeTime:pnlUSDT`
   - Skips si trade ya existe
2. **Normalize close_type** en `crypto-trade-moneda-v3-slots.sh`:
   - `SL` → `CLOSED_SL`, `TP1` → `CLOSED_TP1`, etc.
3. **Trades duplicados previamente eliminados**:
   - #438 (XRP SL dup de #437)
   - #415 (AVAX SL dup de #414)
   - #299 (AVAX TP1 exact dup de #300)

### Nota sobre "trades duplicados":
**NO todos los trades con el mismo PnL son duplicados.** Si LINK y AVAX cierran SL en el mismo segundo con PnL similar, son trades reales distintos. El dedup usa `symbol:slotId` para diferenciar.

---

## 📊 DASHBOARD

### Mobile Dashboard
- `dashboard/static/js/mobile.js` — responsive design
- `updateCircuitBreakerStatus()` — CB badge en tiempo real
- `loadData(true)` — fuerza full refresh con cache-buster

### Desktop Dashboard
- `dashboard/static/js/app.js` — auto-refresh cada 10s
- Progress bars a TP1/TP2/TP3
- Precios en vivo desde Binance API

---

## ⚙️ CONFIGURACIÓN

### Parámetros por modo de mercado
| Mode | TP1 | TP2 | TP3 | SL | Posición |
|---|---|---|---|---|---|
| **BULL** | +3.0% | +6.0% | +10.0% | -4.0% | 25% |
| **BEAR** | +1.5% | +3.0% | +5.0% | -3.5% | 10% |
| **LATERAL** | +1.5% | +3.0% | +5.0% | -3.5% | 20% |

### Config files
- `crypto-bots/dynamic-config.env` — params activos del bot
- `crypto-bots/market-mode.conf` — clasificación de mercado + params
- `crypto-bots/per-coin-config.env` — overrides por moneda

---

## 🔔 NOTIFICACIONES TELEGRAM

### Formato de mensajes
```
🧠 AUTO-ADJUST | BULL ✅ ML de acuerdo
📝 Fear & Greed > 60 + Precio > EMA20
⚙️ TP1/2/3: +3.0/6.0/10.0% | SL: -4.0% | Pos: 25%
📊 BTC: $80,658 | RSI: 90.44 | F&G: 74 (Greed) | ML: 79%
✅ Ajuste aplicado
```

### Fix quoting:
- `send_telegram()` usa `curl --data-urlencode` (no `-d`)
- `parse_mode=Markdown`
- P&L → **PnL** estandarizado

---

## 📁 ESTRUCTURA DE ARCHIVOS

```
workspace/
├── crypto-bots/
│   ├── crypto-trade-moneda-v3-slots.sh    # Bot principal (8 monedas)
│   ├── auto-adjust-strategy.sh            # Strategy engine
│   ├── ml-market-validator.sh             # ML validator wrapper
│   ├── market-sentiment.sh                # F&G + EMAs + RSI
│   ├── global-circuit-breaker.sh          # CB monitor
│   ├── ip-monitor.sh                      # IP whitelist check
│   ├── notify.sh                          # Telegram notifications
│   ├── trade-history.json                 # Trade history (437+ trades)
│   ├── dynamic-config.env                 # Active strategy params
│   ├── market-mode.conf                   # Market classification
│   ├── global-pause-flag.json             # CB state
│   ├── last-known-ip.txt                  # Registered public IP
│   └── *-trade-state.json                 # Slot states (7 coins)
│       # NOT in git: .gitignore
│
├── ml/
│   ├── models_optimized/                  # 7 trained models (.pkl)
│   ├── auto-retrain-v2.py                 # Retraining script
│   ├── ml_validator_wrapper.py            # Trade validation
│   ├── market-classifier.py               # ML classifier
│   └── market-predictions.json            # Latest predictions
│
├── scripts/
│   ├── daily-report.py                    # Daily report (9 AM)
│   ├── log_trade_to_history.py            # Trade logger (w/ dedup)
│   ├── housekeeping.py                    # Cleanup
│   ├── monthly-report.sh                  # Monthly report
│   └── binance-maintenance-monitor.sh     # Exchange downtime
│
├── dashboard/
│   ├── app.py                             # Flask app
│   ├── setup-auth.sh                      # Auth setup
│   ├── start.sh                           # Start dashboard
│   ├── templates/
│   └── static/
│       ├── css/style.css                  # Cyberpunk theme
│       └── js/
│           ├── app.js                     # Desktop dashboard
│           └── mobile.js                  # Mobile + CB status
│
├── lib/                                   # SHARED LIBRARIES
│   ├── send-telegram.sh                   # curl --data-urlencode
│   └── telegram-notifications.sh          # Notification helpers
│
├── logs/                                  # All logs
└── secrets/                               # NEVER COMMITTED
    ├── binance.env                        # Binance API keys
    └── telegram.env                       # Telegram bot token + chat ID
```

---

## 🛠️ COMANDOS ÚTILES

```bash
# Ver trades en history
jq '.trades[-5:]' crypto-bots/trade-history.json

# Contar trades activos
jq '.slots[] | select(.status=="ACTIVE")' crypto-bots/*-trade-state.json

# Dashboard health
curl http://localhost:8080/api/health

# IP pública actual
curl -s https://api.ipify.org

# Ver CB status
cat crypto-bots/global-pause-flag.json

# Ver ML predictions
jq '.predictions | to_entries[] | {coin, mode, confidence}' ml/market-predictions.json

# Ejecutar reporte diario manualmente
python3 scripts/daily-report.py

# Test notificación Telegram
bash lib/send-telegram.sh
```

---

## 🐛 BUGS CONOCIDOS Y FIXES

| Bug | Status | Fix |
|-----|--------|-----|
| PnL 24h = $0 en todas monedas | ✅ Fixed | `parse_datetime_safe()` handles space-format timestamps |
| 4883 trades ayer en reporte | ✅ Fixed | Logscan restringido a líneas reales de trade |
| Trade #438/#415/#299 duplicados | ✅ Fixed | Dedup check + normalize close_type |
| Telegram HTTP 400 (emoji) | ✅ Fixed | `--data-urlencode` + `parse_mode=Markdown` |
| Dashboard CB sync (LATERAL vs BULL) | ✅ Fixed | Post-ML sync: `source dynamic-config.env` |
| IP Monitor (hourly) | ✅ Active | `ip-monitor.sh` + `*/5 * * * *` cron (wait... 0 * * * * hourly) |
| ML validator sin CB check | ✅ Fixed | `validate_trade()` blocks when CB active |
| LINK overfitting (gap 10.33%) | ✅ Fixed | 5 critical features, ccp_alpha=0.005 |

---

## 📊 REPORTAS AUTOMÁTICAS

### Diario (9:00 AM CST)
- Portfolio total (USDT + MXN)
- PnL 24h por moneda
- Trades del día anterior (win rate, PnL)
- Trades activos con status actual
- Estado del sistema (API, IP, alertas)

---

## 🔒 SEGURIDAD

- **API keys**: Solo en `secrets/binance.env`, nunca en git ✅
- **Git**: SSH-only, firma: `Perrobotron Aterrorizar!!` ✅
- **IP Whitelist**: Binance con IP dinámica — monitor hourly ✅
- **Circuit Breaker**: Pausa automática (6 losses/24h) ✅
- **Telegram**: `--data-urlencode` + `parse_mode=Markdown` ✅

---

## 🐕 CRÉDITOS

**Desarrollado por:** [Perrobotron](https://t.me/perrobotron) 🐕  
**Para:** Jefe (Rull Ox)  
**Versión:** FASE 1 v2.1.1  
**Fecha:** 2026-10-21

*"'Nunca confiar, siempre verificar.' — Perrobotron Aterrorizar!!"*

---

<div align="center">

**🚀 El bot está operativo, Jefe. ¡A operar se ha dicho!**

</div>