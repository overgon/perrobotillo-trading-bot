# 🐕 PERROBOTILLO TRADING BOT - CHEATSHEET COMPLETO

> **Última actualización:** Junio 10, 2026  
> **Total de scripts:** 30+ scripts  
> **Estado:** 100% OPERATIVO ✅  
> **Optimización:** Cero uso de LLM para tareas automáticas

---

## ⚡ OPTIMIZACIÓN JUNIO 2026 - CERO USO LLM AUTOMÁTICO

**Problema detectado:** ~1,560 llamadas Ollama/mes por tareas automáticas (circuit breaker countdown)

**Solución implementada:**
- ❌ **Circuit Breaker:** Removido cron (24 ejecuciones/día → 0)
  - Ahora: Trigger on-demand cuando se activa/desactiva
  - Dashboard lee JSON directamente sin polling
- ✅ **Slot Healbot:** Ejecución local Python (cada 10 min, sin LLM)
- ✅ **Auto-Adjust:** Solo notificación Telegram (sin procesamiento LLM)

**Resultado:**
- **Ahorro:** ~1,560 llamadas Ollama/mes eliminadas
- **Costo:** $0.00 en tokens para tareas automáticas
- **CPU/RAM:** Mínimo (scripts locales eficientes)

**Excepciones (uso intencional de LLM):**
- Chat directo con el Jefe (Telegram/Discord)
- Reportes diarios/mensuales (opcional, con LLM)
- Análisis complejos bajo demanda

---

## 📋 ÍNDICE

1. [🤖 ML TP Prediction (NUEVO)](#-ml-tp-prediction-nuevo)
2. [Trading Bot Principal](#-trading-bot-principal)
3. [Estrategia y Mercado](#-estrategia-y-mercado)
4. [Dashboard](#-dashboard)
5. [Reportes y Monitoreo](#-reportes-y-monitoreo)
6. [Seguridad y Emergencias](#-seguridad-y-emergencias)
7. [Backtesting](#-backtesting)
8. [Utilidades](#-utilidades)
9. [Gestión de Capital](#-gestión-de-capital)
10. [Sistema](#-sistema)
11. [Tests](#-tests)

---

## 🤖 ML TP PREDICTION (NUEVO)

### `predict-tp.py`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/ml/predict-tp.py`

**Propósito:** Predice probabilidad de TP en tiempo real usando ML

**Características:**
- ✅ Modelo: LightGBM Classifier (0.31 MB)
- ✅ Features: 22 indicadores (RSI, MACD, Bollinger, volatilidad, volumen)
- ✅ Accuracy: 79-90% (cross-validation)
- ✅ Inferencia: < 1 segundo
- ✅ Predice por coin: BTC, ETH, BNB, SOL, LINK, XRP, AVAX
- ✅ Output: Probabilidad TP1 + recomendación de TPs

**Niveles de confianza:**
- `AGGRESSIVE` (>75%) → TP1: 4.0% | TP2: 8.0% | TP3: 15.0%
- `NORMAL` (60-75%) → TP1: 3.5% | TP2: 7.0% | TP3: 12.0%
- `CONSERVATIVE` (40-60%) → TP1: 2.5% | TP2: 5.0% | TP3: 8.0%
- `DEFENSIVE` (<40%) → TP1: 2.0% | TP2: 4.0% | TP3: 6.0%

**Comando:**
```bash
python3 /home/<YOUR_USERNAME>/.openclaw/workspace/ml/predict-tp.py
```

**Output:**
```json
{
  "predictions": {
    "BTC": {"prob_tp1": 0.661, "prediction": "TP1_LIKELY"},
    "SOL": {"prob_tp1": 0.887, "prediction": "TP1_LIKELY"}
  },
  "recommendations": {
    "BTC": {"action": "NORMAL", "tp1_pct": 3.5, "tp2_pct": 7.0, "tp3_pct": 12.0},
    "SOL": {"action": "AGGRESSIVE", "tp1_pct": 4.0, "tp2_pct": 8.0, "tp3_pct": 15.0}
  }
}
```

---

### `get-tp-recommendation.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/ml/get-tp-recommendation.sh`

**Propósito:** Obtiene recomendación de TP para una moneda específica (usado por el bot principal)

**Comando:**
```bash
bash /home/<YOUR_USERNAME>/.openclaw/workspace/ml/get-tp-recommendation.sh BTC
# Output: 3.5|7.0|12.0 (TP1|TP2|TP3)
```

**Integración:** El bot principal llama este script automáticamente para ajustar TPs dinámicamente

---

### `auto-retrain.py`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/ml/auto-retrain.py`

**Propósito:** Re-entrena automáticamente el modelo con nuevos trades

**Características:**
- ✅ Trigger: Domingo 3 AM (cron) O cuando hay 10+ trades nuevos
- ✅ Carga trades reales de trade-history.json
- ✅ Crea labels basados en trades reales
- ✅ Re-entrena modelo LightGBM con class weights
- ✅ Guarda nuevo modelo y metadata
- ✅ Logs en ml-retrain.log

**Comando:**
```bash
python3 /home/<YOUR_USERNAME>/.openclaw/workspace/ml/auto-retrain.py
```

**Cron:** `0 3 * * 0` (domingo 3 AM)

**Logs:**
```bash
tail -f /home/<YOUR_USERNAME>/.openclaw/logs/ml-retrain.log
```

---

### `train-tp-model.py`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/ml/train-tp-model.py`

**Propósito:** Entrenamiento inicial del modelo (one-time)

**Características:**
- ✅ Usa datos históricos de backtest/data/
- ✅ Calcula 22 indicadores técnicos
- ✅ Crea labels basados en estrategia fija o trades reales
- ✅ Entrena LightGBM Classifier
- ✅ Guarda modelo en ml/tp_prediction_model.pkl

**Comando:**
```bash
python3 /home/<YOUR_USERNAME>/.openclaw/workspace/ml/train-tp-model.py
```

**Output:**
- `ml/tp_prediction_model.pkl` (0.31 MB)
- `ml/model_metadata.json` (accuracy, features, version)

---

### Archivos ML

| Archivo | Propósito |
|---------|----------|
| `ml/tp_prediction_model.pkl` | Modelo entrenado (0.31 MB) |
| `ml/model_metadata.json` | Metadata (accuracy, features) |
| `ml/tp-recommendations.json` | Recomendaciones actuales (se actualiza cada 5 min) |
| `ml/tp-predictions.json` | Predicciones raw |
| `ml/last_retrain.json` | Info del último re-entrenamiento |
| `logs/ml-retrain.log` | Logs de auto-retrain |

---

## 🤖 TRADING BOT PRINCIPAL

### `crypto-trade-moneda-v3-slots.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh`

**Propósito:** Script principal de trading multi-slot (7 monedas, 21 slots)

**Características:**
- ✅ 7 monedas: BTC, ETH, BNB, SOL, LINK, XRP, AVAX
- ✅ 21 slots (3 por moneda)
- ✅ Hybrid slot recycling (nuevos <1h: TP1→READY, existentes >1h: TP1→TP2→TP3)
- ✅ SCALPING MODE para mercado lateral (1.0% target, 2.5% SL)
- ✅ Auto-save de trades (TP1/TP2/TP3/SL/TRAILING/SCALP)
- ✅ P&L por moneda
- ✅ Check de duplicados antes de guardar
- ✅ TP3 quantity: 30% (después TP1+TP2) o 65% (solo TP1)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh [COIN]
# Ejemplo: ./crypto-trade-moneda-v3-slots.sh BTC
```

**Cron:** 7 bots activos (uno por moneda cada 10 min)

---

## 📈 ESTRATEGIA Y MERCADO

### `auto-adjust-strategy.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/auto-adjust-strategy.sh`

**Propósito:** Ajuste automático de estrategia según condiciones de mercado

**Características:**
- ✅ Detecta mercado: BULL / BEAR / LATERAL
- ✅ Ajusta TP/SL/Position automáticamente
- ✅ Lee Fear & Greed Index
- ✅ Notifica cambios por Telegram

**Configuración auto-generada:**
- **BULL:** TP1: 3.0% | TP2: 6.0% | TP3: 9.0% | SL: 6.0% | Position: 25%
- **BEAR:** TP1: 2.0% | TP2: 4.0% | TP3: 6.0% | SL: 4.0% | Position: 15%
- **LATERAL:** TP1: 2.5% | TP2: 5.0% | TP3: 7.0% | SL: 5.0% | Position: 20%
- **SCALPING:** Target: 1.0% | SL: 2.5% | Min Profit: $0.50

**Cron:** `0 */6 * * *` (cada 6 horas: 00:00, 06:00, 12:00, 18:00)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/auto-adjust-strategy.sh
```

---

### `market-sentiment.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/market-sentiment.sh`

**Propósito:** Análisis de sentimiento de mercado (RSI, EMAs, Fear & Greed)

**Características:**
- ✅ Calcula RSI (14 períodos)
- ✅ Calcula EMAs (20, 50, 200)
- ✅ Obtiene Fear & Greed Index de alternative.me
- ✅ Determina modo: BULL / BEAR / LATERAL
- ✅ Genera `market-mode.conf`

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/market-sentiment.sh
```

**Cron:** `0 * * * *` (cada hora)

---

### `test-scalping.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/test-scalping.sh`

**Propósito:** Testear configuración SCALPING MODE

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/test-scalping.sh
```

---

### `test-tp3-fix.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/test-tp3-fix.sh`

**Propósito:** Testear fix de TP3 (cantidad de venta 30%/65%)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/test-tp3-fix.sh
```

---

## 🖥️ DASHBOARD

### `start.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/dashboard/start.sh`

**Propósito:** Iniciar dashboard Flask (sin Ngrok)

**Comando:**
```bash
cd /home/<YOUR_USERNAME>/.openclaw/workspace/dashboard && bash start.sh
```

**URL:** `http://192.168.3.215:8080`

---

### `start-with-ngrok.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/dashboard/start-with-ngrok.sh`

**Propósito:** Iniciar dashboard + túnel Ngrok (HTTPS)

**Características:**
- ✅ HTTPS con candado verde
- ✅ Auto-start con systemd
- ✅ Dominio: `https://<YOUR_NGROK_SUBDOMAIN>.ngrok-free.dev`

**Comando:**
```bash
cd /home/<YOUR_USERNAME>/.openclaw/workspace/dashboard && bash start-with-ngrok.sh
```

**Systemd:** `perrobotillo-dashboard-ngrok.service`

---

## 📊 REPORTES Y MONITOREO

### `daily-report-9am.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/daily-report-9am.sh`

**Propósito:** Reporte diario automático a las 9 AM

**Características:**
- ✅ Portfolio total (USDT + MXN con tasa real de Binance)
- ✅ P&L 24h por moneda (7 coins)
- ✅ Trades de ayer (desde trade-history.json)
- ✅ Trades activos (tabla con entry/current/P&L)
- ✅ Estado del sistema
- ✅ Envío automático por Telegram

**Cron:** `0 9 * * *` (diario a las 9 AM)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/daily-report-9am.sh
```

**Output:** `daily-report-YYYY-MM-DD.md`

---

### `check-drawdown-alert.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/check-drawdown-alert.sh`

**Propósito:** Monitorear drawdown y alertar si excede límite

**Características:**
- ✅ Check cada 30 minutos
- ✅ Alerta si drawdown > 3% (configurable)
- ✅ Notificación por Telegram

**Cron:** `*/30 * * * *` (cada 30 min)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/check-drawdown-alert.sh
```

---

### `check-public-ip.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/check-public-ip.sh`

**Propósito:** Monitorear IP pública y alertar si cambia (Binance whitelist)

**Características:**
- ✅ Detecta IP pública actual
- ✅ Compara con IP en whitelist de Binance
- ✅ Alerta por Telegram si cambia
- ✅ Útil para IP dinámica

**Cron:** `0 * * * *` (cada hora)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/check-public-ip.sh
```

---

### `fan-control.sh` 🆕
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/scripts/fan-control.sh`

**Propósito:** Control automático del ventilador de RPi5 por temperatura

**Características:**
- ✅ Lee temperatura de CPU en tiempo real
- ✅ Ajusta velocidad PWM (0-255) según temperatura
- ✅ Evita flickering (solo cambia si diferencia >20)
- ✅ Loguea cambios en `fan-control.log`

**Configuración de temperatura:**

| Temp | Velocidad | PWM | % |
|------|-----------|-----|---|
| <38°C | OFF | 0 | 0% |
| 38-45°C | LOW | 80 | 31% |
| 45-60°C | MEDIUM-LOW | 140 | 55% |
| 60-70°C | MEDIUM | 190 | 75% |
| 70-75°C | HIGH | 230 | 90% |
| >75°C | MAX | 255 | 100% |

**Cron:** `*/2 * * * *` (cada 2 minutos)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/scripts/fan-control.sh
```

**Log:** `/home/<YOUR_USERNAME>/.openclaw/logs/fan-control.log`

---

### `tp-monitor.sh` 🆕🎯
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/scripts/tp-monitor.sh`

**Propósito:** Monitoreo en tiempo real de TPs y cierre INMEDIATO al 100%

**Características:**
- ✅ Escanea slots activos cada 30 segundos
- ✅ Detecta cuando TP1/TP2/TP3 llega a 100%
- ✅ Ejecuta cierre INMEDIATO (sin esperar 10 min)
- ✅ Alerta cuando slot está >95% del TP
- ✅ Evita perder TPs por caídas de precio

**Ventajas:**
- **ANTES:** Delay de 10 min (podía perder TPs)
- **AHORA:** Ejecución en ≤30 segundos

**Systemd:** `perrobotillo-tp-monitor.service` (auto-start)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/scripts/tp-monitor.sh
```

**Log:** `/home/<YOUR_USERNAME>/.openclaw/logs/tp-monitor.log`

**Output ejemplo:**
```
⚠️  CERCA DEL TP: SOL Slot 1 → 95.2%
🎯 TP HIT DETECTADO: SOL Slot 1 TP1
🚀 Ejecutando cierre INMEDIATO...
✅ Cierre ejecutado
```

---

## 🛡️ CIRCUIT BREAKER Y AUTO-HEAL (NUEVO 2026-06-10)

### `global-circuit-breaker.sh` 🆕🔴
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/global-circuit-breaker.sh`

**Propósito:** Proteger el portfolio de pérdidas catastróficas con pause automático

**Características:**
- ✅ Verifica losses globales (todas las monedas) en últimas 24h
- ✅ 4 reglas de protección:
  1. **4+ losses en 24h** → PAUSE 24h
  2. **-$50+ USDT en 24h** → PAUSE 48h
  3. **2+ losses en 1h** → PAUSE 4h (evita desastres)
  4. **Loss rate > 60% en 24h** → PAUSE 12h
- ✅ Actualiza dashboard on-demand (sin cron)
- ✅ Permite gestión de trades activos (SL/TP) durante pause
- ✅ Auto-resume después del pause

**Reglas de trading durante CB:**
- ✅ **Permitido:** SL Management, TP Management, Emergency Close
- ❌ **Bloqueado:** New Entries, DCA Operations

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/global-circuit-breaker.sh
# Output: OK_TO_TRADE o GLOBAL_PAUSE_XXH
```

**Uso en bots:**
```bash
if ! ./global-circuit-breaker.sh; then
    echo "Trading paused - Circuit Breaker active"
    exit 1
fi
```

**Archivos:**
- `global-pause-flag.json` - Flag de pause activo
- `dashboard-circuit-breaker-status.json` - Status para dashboard (on-demand)

**Logs:** Integrado en logs de cada bot que lo ejecuta

---

### `slot-healbot.py` 🆕🔧
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/slot-healbot.py`

**Propósito:** Verificar y reparar estado de slots automáticamente

**Características:**
- ✅ Escanea 21 slots (7 monedas × 3 slots) cada 10 min
- ✅ Detecta inconsistencias de estado
- ✅ Repara automáticamente:
  - CLOSED_* → READY (limpia datos)
  - READY con posición → ACTIVE (corrige status)
  - ACTIVE sin posición → READY (inconsistencia grave)
  - ACTIVE con TP3 completado → CLOSED (cierra trade)
- ✅ **REGLA DE ORO:** NUNCA toca slots ACTIVE con posición (excepto TP3)
- ✅ Notifica reparaciones por Telegram

**Estados válidos:**
- `READY` - Slot disponible (sin posición)
- `ACTIVE` - Posición abierta (IN TRADE)
- `CLOSED_TP1/TP2/TP3/SL/TRAILING` - Trade cerrado

**Cron:** `*/10 * * * *` (cada 10 minutos)

**Comando:**
```bash
python3 /home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/slot-healbot.py
```

**Log:** `/home/<YOUR_USERNAME>/.openclaw/logs/auto-heal.log`

---

### `update-circuit-breaker-countdown.py` 🔄 OPTIMIZADO
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/update-circuit-breaker-countdown.py`

**Propósito:** Generar status JSON del circuit breaker para dashboard

**Cambios Junio 2026:**
- ❌ Removido: Countdown en tiempo real (innecesario)
- ✅ Mantenido: Status básico (activo/inactivo)
- ✅ Trigger: On-demand cuando CB se activa/desactiva
- ❌ Sin cron: Dashboard lee directamente el JSON

**Comando:**
```bash
python3 /home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/update-circuit-breaker-countdown.py
```

**Output:** `dashboard-circuit-breaker-status.json`

---

## 🔒 SEGURIDAD Y EMERGENCIAS

### `emergency-close-all.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/emergency-close-all.sh`

**Propósito:** Cerrar TODAS las posiciones inmediatamente (emergency stop)

**Características:**
- ✅ Cierra todos los slots activos
- ✅ Vende 100% de la posición
- ✅ Guarda trades en histórico
- ✅ Notifica por Telegram

**⚠️ ADVERTENCIA:** Solo usar en emergencias reales (crash de mercado, bug crítico)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/emergency-close-all.sh
```

---

### `auto-reset-closed-slots.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/auto-reset-closed-slots.sh`

**Propósito:** Resetear slots cerrados a READY para nuevas entradas

**Características:**
- ✅ Detecta slots CLOSED_* (TP1/TP2/TP3/SL/TRAILING)
- ✅ Cambia status a READY
- ✅ Limpia campos de trade anterior
- ✅ Permite slot recycling

**Cron:** Activo (se ejecuta después de cada cierre)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/auto-reset-closed-slots.sh
```

---

## 🧪 BACKTESTING

### `run-backtest.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/backtest/run-backtest.sh`

**Propósito:** Ejecutar backtesting de estrategias con datos históricos

**Características:**
- ✅ Descarga datos históricos de Binance (CSV)
- ✅ Simula estrategia FASE 1 v2.1
- ✅ Calcula: Return, Win Rate, Drawdown, Sharpe
- ✅ Compara vs HODL
- ✅ Genera reporte en Markdown

**Resultados históricos (6 años 2020-2026):**
- **LONG (Current Strategy):** +961.5% average return 🏆 OPTIMAL
- **SHORT (All strategies):** +260.7% average (700% worse)
- **Conclusión:** LONG ONLY confirmado óptimo para crypto

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/backtest/run-backtest.sh [COIN] [YEARS]
# Ejemplo: ./run-backtest.sh BTC 2
```

---

## 🛠️ UTILIDADES

### `claw-utils.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/lib/claw-utils.sh`

**Propósito:** Utilidades generales del sistema (reemplaza OpenClaw CLI)

**Características:**
- ✅ Detecta si dashboard corre (manual o systemd)
- ✅ Verifica estado de servicios
- ✅ Funciones utilitarias para otros scripts

**Comando:**
```bash
source /home/<YOUR_USERNAME>/.openclaw/workspace/lib/claw-utils.sh
```

---

### `send-telegram.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/lib/send-telegram.sh`

**Propósito:** Enviar mensajes a Telegram sin OpenClaw (independiente)

**Características:**
- ✅ Usa Telegram Bot API directa
- ✅ No depende de OpenClaw Gateway
- ✅ Útil para alertas críticas

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/lib/send-telegram.sh "Mensaje de prueba"
```

**Secrets:** `/home/<YOUR_USERNAME>/.openclaw/secrets/telegram.env`

---

### `crypto-coincap-prices.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-coincap-prices.sh`

**Propósito:** Obtener precios de CoinCap API

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-coincap-prices.sh
```

---

### `crypto-exchange-compare.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-exchange-compare.sh`

**Propósito:** Comparar precios entre exchanges (Binance vs CoinCap)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-exchange-compare.sh
```

---

## 💰 GESTIÓN DE CAPITAL

### `auto-capital-manager.sh` 🆕🤖
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/scripts/auto-capital-manager.sh`

**Propósito:** Gestión AUTOMÁTICA de position size según capital y win rate

**Características:**
- ✅ Calcula portfolio REAL en tiempo real (todas las monedas + USDT)
- ✅ Decide position size óptimo automáticamente
- ✅ Ajusta según capital y win rate
- ✅ Notifica cambios por Telegram
- ✅ Ejecución diaria automática

**Reglas inteligentes:**

| Capital Total | Position Base | Ajuste Win Rate |
|---------------|---------------|-----------------|
| < $1,000 | 15% (Conservador) | WR < 70%: -5% |
| $1,000-$2,000 | 22% (Moderado) | WR > 95%: +2% |
| $2,000-$3,000 | 25% (Crecimiento) | Límites: 15-30% |
| $3,000-$5,000 | 28% (Alto) | |
| > $5,000 | 30% (Máximo) | |

**Cron:** `0 9 * * *` (diario a las 9 AM)

**Comando:**
```bash
/home/<YOUR_USERNAME>/.openclaw/workspace/scripts/auto-capital-manager.sh
```

**Log:** `/home/<YOUR_USERNAME>/.openclaw/logs/auto-capital-manager.log`

**Progreso:** `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/capital-manager-progress.json`

**Output ejemplo:**
```
Portfolio REAL: $2,887.02 USDT
Win Rate: 100.0%
Position actual: 24%
Position ÓPTIMO: 27%
📈 Aumento menor: 24% → 27%
✅ Position size actualizado: 27%
```

---

## ⚙️ CONFIGURACIÓN

### `capital-config.sh`
**Ubicación:** `/home/<YOUR_USERNAME>/.openclaw/workspace/config/capital-config.sh`

**Propósito:** Configuración de capital por moneda

**Características:**
- ✅ Define USDT por slot
- ✅ Define porcentaje de posición
- ✅ Configuración centralizada
- ✅ Actualizado por `auto-capital-manager.sh`

**Comando:**
```bash
source /home/<YOUR_USERNAME>/.openclaw/workspace/config/capital-config.sh
```

---

## 📋 RESUMEN DE CRON JOBS (ACTUALIZADO JUNIO 2026)

| Cron | Script | Propósito | Uso LLM |
|------|--------|-----------|----------|
| `*/10 * * * *` | `run-slot-healbot.sh` | Repara slots cada 10 min | ❌ Local |
| `*/2 * * * *` | `fan-control.sh` | Control ventilador (cada 2 min) | ❌ Local |
| `*/30 * * * *` | `check-drawdown-alert.sh` | Alerta drawdown (cada 30 min) | ❌ Local |
| `*/30 * * * *` | `proactive-alerts.sh` | Alertas proactivas (cada 30 min) | ❌ Local |
| `0 * * * *` | `check-public-ip.sh` | Check IP pública (cada hora) | ❌ Local |
| `0 */4 * * *` | `binance-maintenance-monitor.sh` | Monitor maintenance Binance | ❌ Local |
| `0 9 * * *` | `daily-report-9am.sh` | Reporte diario (9 AM) | ⚠️ Opcional |
| `0 9 * * *` | `auto-capital-manager.sh` | Gestión capital (9 AM) | ❌ Local |
| `0 9 * * *` | `monthly-report.sh` | Reporte mensual (día 1, 9 AM) | ⚠️ Opcional |
| `0 */6 * * *` | `auto-adjust-strategy.sh` | Auto-ajuste estrategia + ML | ⚠️ Notificación |
| `0 3 * * 0` | `ml/auto-retrain-v2.py` | ML re-entrenamiento (domingos 3 AM) | ❌ Local |
| `0 9 * * 0` | `ml-retrain-report.sh` | Reporte ML retrain (domingos 9 AM) | ⚠️ Opcional |
| `0 23 * * 0` | `portfolio-rebalance.sh` | Rebalanceo portfolio (domingos 11 PM) | ❌ Local |
| `0 */2 * * *` | `update-trailing-stops.sh` | Update trailing stops (cada 2h) | ❌ Local |
| `0 */4 * * *` | `eth-accumulation-tracker.sh` | ETH tracker (cada 4h) | ❌ Local |
| `0 * * * *` | `verify-balances.sh` | Verificar balances (cada hora) | ❌ Local |
| `*/10 * * * *` | `update-portfolio.sh` | Actualizar portfolio (cada 10 min) | ❌ Local |
| `0 */2 * * *` | `update-ml-predictions.sh` | ML predictions (cada 2h) | ❌ Local |
| `* * * * *` | `dashboard/watchdog.sh` | Dashboard watchdog (cada min) | ❌ Local |
| `*/5 * * * *` | `auto-reset-closed-slots.sh` | Reset slots cerrados (cada 5 min) | ❌ Local |
| `0 8 * * *` | `dynamic-position-sizing.py` | Position sizing (diario 8 AM) | ❌ Local |
| `0 1 1 * *` | `housekeeping.sh` | Limpieza mensual (día 1, 1 AM) | ❌ Local |
| `0 2 * * 0` | `logrotate` | Log rotation semanal (domingos 2 AM) | ❌ Local |
| Trading bots | `crypto-trade-moneda-v3-slots.sh [COIN]` | 7 monedas cada 10 min | ❌ Local |

**Total:** ~27 cron jobs activos  
**Optimización Junio 2026:** Circuit breaker removido (on-demand), cero uso de LLM para tareas automáticas

---

## 📁 ARCHIVOS CLAVE

### Configuración
- `/home/<YOUR_USERNAME>/.openclaw/secrets/binance.env` - API keys de Binance 🔒
- `/home/<YOUR_USERNAME>/.openclaw/secrets/telegram.env` - Telegram bot token 🔒
- `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/dynamic-config.env` - Config dinámica (auto-generada)
- `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/market-mode.conf` - Modo de mercado actual
- `/home/<YOUR_USERNAME>/.openclaw/workspace/config/capital-config.sh` - Capital por moneda

### Estado
- `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/[COIN]-trade-state.json` - Estado de slots por moneda
- `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/trade-history.json` - Histórico de trades
- `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/cashout-history.json` - Histórico de cashouts
- `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/capital-manager-progress.json` - Progreso auto-capital
- `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/global-pause-flag.json` - Circuit breaker pause flag 🔴
- `/home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json` - CB status dashboard
- `/home/<YOUR_USERNAME>/.openclaw/workspace/ml/market-predictions.json` - ML predictions actuales

### Logs
- `/home/<YOUR_USERNAME>/.openclaw/logs/auto-trade-all.log` - Log principal de trading
- `/home/<YOUR_USERNAME>/.openclaw/logs/fan-control.log` - Log de control de ventilador
- `/home/<YOUR_USERNAME>/.openclaw/logs/tp-monitor.log` - Log de monitoreo de TPs
- `/home/<YOUR_USERNAME>/.openclaw/logs/auto-capital-manager.log` - Log de gestión de capital
- `/home/<YOUR_USERNAME>/.openclaw/logs/auto-adjust.log` - Auto-adjust strategy + ML
- `/home/<YOUR_USERNAME>/.openclaw/logs/auto-heal.log` - Slot healbot reparaciones
- `/home/<YOUR_USERNAME>/.openclaw/logs/ml-predictions-update.log` - ML predictions update

### Reportes
- `/home/<YOUR_USERNAME>/.openclaw/workspace/daily-report-YYYY-MM-DD.md` - Reportes diarios

---

## 🎯 COMANDOS RÁPIDOS

### Ver estado del sistema
```bash
# Temperatura
vcgencmd measure_temp

# Ventilador
cat /sys/class/hwmon/hwmon2/fan1_input
cat /sys/class/hwmon/hwmon2/pwm1

# Dashboard
curl -s http://localhost:8080/api/status | jq .

# Portfolio
curl -s http://localhost:8080/api/portfolio | jq .

# Trades activos
jq '.slots[] | select(.status == "ACTIVE")' /home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/*-trade-state.json

# Circuit Breaker status
cat /home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/dashboard-circuit-breaker-status.json | jq .

# Global pause flag
cat /home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/global-pause-flag.json 2>/dev/null || echo "No active"

# TP Monitor status
systemctl status perrobotillo-tp-monitor

# Capital Manager progress
cat /home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/capital-manager-progress.json | jq .

# ML predictions
cat /home/<YOUR_USERNAME>/.openclaw/workspace/ml/market-predictions.json | jq '.predictions.BTC'
```

### Ver logs en tiempo real
```bash
tail -f /home/<YOUR_USERNAME>/.openclaw/logs/auto-trade-all.log
tail -f /home/<YOUR_USERNAME>/.openclaw/logs/fan-control.log
tail -f /home/<YOUR_USERNAME>/.openclaw/logs/tp-monitor.log
tail -f /home/<YOUR_USERNAME>/.openclaw/logs/auto-capital-manager.log
```

### Reiniciar servicios
```bash
# Dashboard
pkill -9 -f "python.*app.py" && cd /home/<YOUR_USERNAME>/.openclaw/workspace/dashboard && bash start-with-ngrok.sh &

# TP Monitor
sudo systemctl restart perrobotillo-tp-monitor

# Ngrok
pkill -9 ngrok && ngrok http 8080 --log=stdout &
```

### Ver cron jobs
```bash
crontab -l
```

---

## 📊 ESTADÍSTICAS ACTUALES (Junio 10, 2026)

```
Total Trades: [Actualizar con trade-history.json]
Win Rate: [Actualizar %]
Net P&L: +$[Actualizar] USDT

Portfolio: ~$500 USDT invertidos (FASE 1 v2.1 optimizada)
Daily Loss Limit: 3% (Circuit Breaker activo)

Slots Activos: 15/21 en profit (+2-3%)
SOL en TP1 - Esperando cierre automático

Cashouts: [Actualizar]

Temperatura RPi5: ~38-45°C
Ventilador: Auto control (PWM 0-255)

Position Size: [Actualizar]% (auto-ajustado)

Estrategia Actual: BEAR (auto-adjust a las 8 AM)
  TP1: 2.0% | TP2: 4.0% | TP3: 6.0% | SL: 4.0%
  Position: 15%
  
Circuit Breaker: ✅ Activo (protección 4 losses/24h, -$50/24h)
ML Validator: ✅ Integrado (override con >80% confianza)

Optimización LLM: ❌ Cero uso para tareas automáticas
  - Circuit breaker: On-demand (sin cron)
  - Slot healbot: Local Python (cada 10 min)
  - Auto-adjust: Solo notificación Telegram
```

---

## 🔐 SEGURIDAD

### Secretos (NUNCA commitear)
- ✅ `secrets/binance.env` - En `.gitignore`
- ✅ `secrets/telegram.env` - En `.gitignore`
- ✅ `dashboard/.htpasswd` - En `.gitignore`

### Whitelist
- ✅ IP pública en Binance API whitelist
- ✅ Monitor de IP activo (alertas si cambia)

### Permisos
- ✅ API keys con permisos limitados (Spot Trading ONLY)
- ✅ Sin retiros permitidos
- ✅ Emergency close protegido

### Independencia de OpenClaw
- ✅ Trading bot: Independiente (cron + API directa)
- ✅ Dashboard: Independiente (Flask + Ngrok)
- ✅ Alertas: Independientes (Telegram API directa)
- ✅ Solo chat: Depende de OpenClaw/Ollama

---

## 📚 DOCUMENTACIÓN ADICIONAL

- `/home/<YOUR_USERNAME>/.openclaw/workspace/README.md` - Introducción
- `/home/<YOUR_USERNAME>/.openclaw/workspace/INSTALL.md` - Instalación
- `/home/<YOUR_USERNAME>/.openclaw/workspace/SECURITY.md` - Seguridad
- `/home/<YOUR_USERNAME>/.openclaw/workspace/TRANSICION-SIN-OPENCLAW.md` - Migración
- `/home/<YOUR_USERNAME>/.openclaw/workspace/ESTRATEGIAS-TRADING.md` - Estrategias (10.2KB)
- `/home/<YOUR_USERNAME>/.openclaw/workspace/CHANGELOG-2026-05-08.md` - Changelog completo (14KB)
- `/home/<YOUR_USERNAME>/.openclaw/workspace/backtest/results/PROYECCION-FIN-2026.md` - Proyecciones

---

## 🦴 SOPORTE

**GitHub:** https://github.com/overgon/perrobotillo-trading-bot

**Dashboard:** https://<YOUR_NGROK_SUBDOMAIN>.ngrok-free.dev

**Telegram:** Bot integrado para alertas y reportes

---

## 🎯 NOVEDADES JUNIO 10, 2026

### 🆕 Circuit Breaker Global (global-circuit-breaker.sh)
- Protección contra pérdidas catastróficas
- 4 reglas: losses/24h, drawdown/$50, losses/1h, loss rate
- Pause automático (4h-48h según severidad)
- Actualización dashboard on-demand (sin cron)
- Permite gestión SL/TP durante pause

### 🆕 Slot Healbot (slot-healbot.py)
- Verifica y repara 21 slots cada 10 min
- Repara inconsistencias: CLOSED→READY, READY→ACTIVE
- REGLA DE ORO: Nunca toca slots ACTIVE con posición
- Notifica reparaciones por Telegram
- Ejecución local (sin LLM)

### 🧠 ML Validator Integrado (ml-market-validator.sh)
- Valida auto-adjust con ML predictions
- Override automático si discrepancia >80% confianza
- Predicciones frescas cada 2 horas
- Logs de reason y confidence

### 🔄 Optimización LLM - Cero Uso Automático
- ❌ Circuit breaker cron: Removido (on-demand)
- ❌ Slot healbot: Local Python
- ⚠️ Auto-adjust: Solo notificación Telegram
- ✅ Ahorro: ~1,560 llamadas Ollama/mes eliminadas

### 📊 Dashboard Circuit Breaker
- Status JSON actualizado on-demand
- Emergency mode visual (slots naranjas 🟠)
- Sin countdown en tiempo real (solo cuando activo)

---

## 🎯 NOVEDADES MAYO 2026

### 🆕 TP Monitor (`tp-monitor.sh`)
- Monitoreo en tiempo real cada 30 segundos
- Cierre INMEDIATO al detectar TP 100%
- Evita perder TPs por caídas de precio
- Systemd auto-start habilitado

### 🆕 Auto Capital Manager (`auto-capital-manager.sh`)
- Gestión AUTOMÁTICA de position size
- Calcula portfolio REAL (todas las monedas)
- Decide position óptimo según capital y win rate
- Ajuste automático diario (9 AM)
- Notificaciones por Telegram

### 📊 Stats Actualizadas
- Portfolio corregido: ~$2,887 USDT (antes $1,972)
- Position size: 27% (auto-ajustado de 40%)
- 62 trades en histórico (+$219.04 USDT)
- 100% win rate mantenido

---

_Generado por Perrobotillo 🐕_  
*"¡Nunca confiar, siempre verificar!"*
