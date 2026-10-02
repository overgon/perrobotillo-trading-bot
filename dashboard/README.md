# 🐕 Perrobotillo Trading Bot — FASE 1 v2.1

**Bot de trading automatizado para Binance** con ML, circuit breaker, dashboard cyberpunk y notificaciones en vivo.

> **"Nunca confiar, siempre verificar." — Jefe**

---

## 🏗️ ARQUITECTURA DEL SISTEMA

```
┌─────────────────────────────────────────────────────────┐
│                    Raspberry Pi 5                       │
│                   (Cron-based, no systemd)             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📊 Dashboard (Flask)           ML Pipeline              │
│  ├── app.py                    ├── market-predictions   │
│  ├── static/js/                ├── models_optimized/   │
│  │  ├── app.js                 ├── auto-retrain-v2.py    │
│  │  ├── mobile.js              └── ml_validator_wrapper  │
│  └── templates/                                         │
│                                                         │
│  🤖 Trading Bot                   🔔 Notificaciones     │
│  ├── crypto-trade-moneda-v3-      ├── notify.sh          │
│  │   slots.sh                     ├── send-telegram.sh   │
│  ├── auto-adjust-strategy.sh      └── telegram-notif..   │
│  ├── global-circuit-breaker.sh                            │
│  ├── ip-monitor.sh                                       │
│  └── market-sentiment.sh                                 │
│                                                         │
│  📈 Reports                         💾 Data              │
│  ├── daily-report.py               ├── trade-history.json │
│  ├── monthly-report.sh             ├── *-trade-state.json │
│  └── housekeeping.sh               └── portfolio-*.json  │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 CARACTERÍSTICAS PRINCIPALES

| Característica | Detalle |
|---|---|
| **Monedas** | 7: BTC, ETH, BNB, SOL, LINK, XRP, AVAX |
| **Slots** | 21 (3 por moneda) |
| **Exchange** | Binance Spot |
| **ML** | RandomForest classifier (7 modelos, 72-94% accuracy) |
| **CB** | Circuit Breaker (6 losses/24h → pausa trading) |
| **Cron** | No systemd — todo via cron (`*/5`, `0 * *`, etc.) |
| **Notify** | Telegram con `--data-urlencode` + `parse_mode=Markdown` |
| **IP Watch** | Monitor hourly, alerta inmediata si cambia |

---

## 🚀 INICIO RÁPIDO

### 1. Configurar credenciales
```bash
# Secrets viven en:
# - secrets/binance.env  (API keys — NUNCA subir a GitHub)
# - secrets/telegram.env (Bot token + chat ID)
cp secrets/binance.env.example secrets/binance.env
cp secrets/telegram.env.example secrets/telegram.env
# Editar con tus credenciales
```

### 2. Iniciar el dashboard
```bash
cd dashboard
./setup-auth.sh    # Configurar usuario/password
./start.sh         # O: systemd service
# Acceso: http://localhost:8080
# Red local: http://192.168.3.215:8080
```

### 3. Verificar cron jobs
```bash
crontab -l
# Expected:
# */5 * * * *  → global-circuit-breaker.sh (CB monitor)
# 0 * * * *    → ip-monitor.sh (IP whitelist check)
# 0 9 * * *    → daily-report.py (reporte diario 9 AM)
# 0 3 * * 0   → auto-retrain-v2.py (ML retraining Sunday 3 AM)
```

---

## 📊 DASHBOARD

### Autenticación
- HTTP Basic Auth vía `dashboard/.htpasswd`
- Setup: `cd dashboard && ./setup-auth.sh`

### URLs
| Contexto | URL |
|---|---|
| Local (Raspberry Pi) | `http://localhost:8080` |
| Red local | `http://192.168.3.215:8080` |
| Externo (ngrok) | `https://*.ngrok-free.dev` |

### API Endpoints
| Endpoint | Descripción |
|---|---|
| `/api/data` | Portfolio, slots, trades, system status |
| `/api/prices` | Precios en vivo desde Binance |
| `/api/status` | Circuit breaker + health check |
| `/api/health` | Health check del servidor |

---

## 🧠 ML PIPELINE

### Modelos
- 7 modelos RandomForest (uno por moneda) en `ml/models_optimized/`
- Features: SMA50, RSI(max_5/10/20), ROC(max_10)
- LINK: 5 features críticas (overfitting arreglado, gap 3.32%)

### Retraining
```bash
# Manual
python3 ml/auto-retrain-v2.py

# Cron (Sunday 3 AM)
0 3 * * 0  /home/.../ml/auto-retrain-v2.py
```

### Validation
- `ml_validator_wrapper.py` valida pause flag antes de aprobar trades
- Fallback: SMA20/50 + RSI + vol, posición al 25% si confidence < 60%

---

## 🛡️ CIRCUIT BREAKER

| Componente | Archivo |
|---|---|
| Configuración | `crypto-bots/global-pause-flag.json` |
| Monitor (5 min) | `crypto-bots/global-circuit-breaker.sh` |
| Dashboard sync | `crypto-bots/dashboard-circuit-breaker-status.json` |

- **Trigger**: 6 losses/24h → pausa nuevos trades hasta N horas después
- **SL/TP**: Siguen ejecutándose durante pausa
- **ML Validator**: Rechaza todos los trades si CB activo (`approved: False, reason: PAUSE FLAG ACTIVO`)

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

- Registra IP en `crypto-bots/last-known-ip.txt`
- Notifica via Telegram si cambia (para Binance IP Whitelist)

---

## 📈 REPORTE DIARIO

```bash
# Ejecutar manualmente
python3 scripts/daily-report.py

# Cron: 9 AM diario
0 9 * * * python3 scripts/daily-report.py
```

Incluye:
- Portfolio total (USDT + MXN)
- PnL 24h por moneda
- Trades del día anterior (win rate, PnL)
- Trades activos
- Estado del sistema (API, IP, órdenes)

---

## 🔧 COMANDOS ÚTILES

```bash
# Ver trades en history
jq '.trades[-5:]' crypto-bots/trade-history.json

# Contar trades activos
jq '.slots[] | select(.status=="ACTIVE") | .symbol' crypto-bots/XRP-trade-state.json

# Dashboard en vivo
tail -f logs/dashboard-stdout.log

# IP pública actual
curl -s https://api.ipify.org

# Ver circuit breaker status
cat crypto-bots/global-pause-flag.json
```

---

## 💾 ESTRUCTURA DE ARCHIVOS

```
workspace/
├── crypto-bots/
│   ├── crypto-trade-moneda-v3-slots.sh    # Bot principal
│   ├── auto-adjust-strategy.sh            # Strategy engine
│   ├── ml-market-validator.sh             # ML validator
│   ├── market-sentiment.sh                # F&G + EMAs + RSI
│   ├── global-circuit-breaker.sh          # CB monitor
│   ├── ip-monitor.sh                      # IP whitelist monitor
│   ├── notify.sh                          # Telegram notifications
│   ├── trade-history.json                 # 437+ trades
│   ├── dynamic-config.env                 # Active strategy params
│   ├── market-mode.conf                   # Current market classification
│   ├── global-pause-flag.json             # CB state
│   ├── last-known-ip.txt                  # Registered public IP
│   └── *-trade-state.json                 # Slot states per coin
│
├── ml/
│   ├── models_optimized/                  # 7 trained models (.pkl)
│   ├── market-classifier.py               # ML classifier
│   ├── ml_validator_wrapper.py            # Trade validation
│   ├── auto-retrain-v2.py                 # Retraining script
│   └── market-predictions.json            # Latest predictions
│
├── scripts/
│   ├── daily-report.py                    # Daily report
│   ├── log_trade_to_history.py            # Trade logger w/ dedup
│   ├── housekeeping.py                    # Cleanup
│   └── binance-maintenance-monitor.sh     # Exchange downtime check
│
├── dashboard/
│   ├── app.py                             # Flask app
│   ├── setup-auth.sh                      # Auth setup
│   ├── templates/
│   └── static/
│       ├── css/style.css                  # Cyberpunk theme
│       └── js/
│           ├── app.js                     # Desktop dashboard
│           └── mobile.js                  # Mobile dashboard + CB status
│
├── lib/
│   ├── send-telegram.sh                   # curl --data-urlencode
│   └── telegram-notifications.sh          # Notification helpers
│
├── logs/                                  # All logs
└── secrets/                               # NEVER COMMITTED
    ├── binance.env                        # API keys
    └── telegram.env                       # Bot token + chat ID
```

---

## 📊 REPORTAS AUTOMÁTICAS

### Diario (9:00 AM CST)
- Portfolio total (USDT + MXN)
- **PnL 24h** por moneda (corregido: timezone UTC)
- Trades del día anterior (win rate, PnL)
- Trades activos con status actual
- Estado del sistema (API, IP, alertas)

### Semanal (ML)
- Model accuracy por moneda
- Retraining status
- Overfitting gap (objetivo < 5%)

---

## 🔒 SEGURIDAD

- **API keys**: Solo en `secrets/binance.env`, nunca en repo ✅
- **Git**: SSH-only, firma `Perrobotron Aterrorizar!!` ✅
- **IP Whitelist**: Binance con IP dinámica — monitor hourly ✅
- **Circuit Breaker**: Pausa automática si drawdown ⚠️
- **Telegram**: `--data-urlencode` + `parse_mode=Markdown` (evita HTTP 400)

---

## ⚙️ CONFIGURACIÓN DEL BOT

### Parámetros por modo de mercado
| Mode | TP1 | TP2 | TP3 | SL | Posición |
|---|---|---|---|---|---|
| **BULL** | +3.0% | +6.0% | +10.0% | -4.0% | 25% |
| **BEAR** | +1.0% | +3.0% | +5.0% | -3.0% | 15% |
| **LATERAL** | +1.5% | +3.0% | +5.0% | -3.5% | 20% |
| **CB ON** | +1.5% | +3.0% | +5.0% | -3.5% | 10% |

---

## 🛠️ TROUBLESHOOTING

| Problema | Solución |
|---|---|
| Dashboard HTTP 400 en notificaciones | `curl` usa `--data-urlencode`, no `-d` |
| `totalTrades` mismatch | Derivado de `len(trades)`, nunca counter |
| Trades duplicados en history | `log_trade_to_history.py` dedup (key: symbol:slotId:closeTime:pnl) |
| Dashboard no refresca | Verificar que Flask esté corriendo: `curl localhost:8080/api/health` |
| ML stale predicciones | `ml/auto-retrain-v2.py` o `update-ml-predictions.sh` |

---

## 🐕 CRÉDITOS

**Desarrollado por:** [Perrobotron](https://t.me/perrobotron) 🐕  
**Para:** Jefe (Rull Ox)  
**Versión:** FASE 1 v2.1  
**Fecha:** 2026-08-24

*"'Nunca confiar, siempre verificar.' — Perrobotron Aterrorizar!!"*

---

<div align="center">

**🚀 El bot está vivo, Jefe. ¡A operar se ha dicho!**

</div>