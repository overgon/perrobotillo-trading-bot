# 🐕 PERROBOTILLO TRADING BOT - CHEATSHEET COMPLETO

> **Última actualización:** Mayo 11, 2026  
> **Total de scripts:** 21  
> **Estado:** 100% OPERATIVO ✅

---

## 📋 ÍNDICE

1. [Trading Bot Principal](#-trading-bot-principal)
2. [Estrategia y Mercado](#-estrategia-y-mercado)
3. [Dashboard](#-dashboard)
4. [Reportes y Monitoreo](#-reportes-y-monitoreo)
5. [Seguridad y Emergencias](#-seguridad-y-emergencias)
6. [Backtesting](#-backtesting)
7. [Utilidades](#-utilidades)
8. [Gestión de Capital](#-gestión-de-capital)
9. [Sistema](#-sistema)
10. [Tests](#-tests)

---

## 🤖 TRADING BOT PRINCIPAL

### `crypto-trade-moneda-v3-slots.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh`

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
/home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh [COIN]
# Ejemplo: ./crypto-trade-moneda-v3-slots.sh BTC
```

**Cron:** 7 bots activos (uno por moneda cada 10 min)

---

## 📈 ESTRATEGIA Y MERCADO

### `auto-adjust-strategy.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/crypto-bots/auto-adjust-strategy.sh`

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
/home/overgon/.openclaw/workspace/crypto-bots/auto-adjust-strategy.sh
```

---

### `market-sentiment.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/crypto-bots/market-sentiment.sh`

**Propósito:** Análisis de sentimiento de mercado (RSI, EMAs, Fear & Greed)

**Características:**
- ✅ Calcula RSI (14 períodos)
- ✅ Calcula EMAs (20, 50, 200)
- ✅ Obtiene Fear & Greed Index de alternative.me
- ✅ Determina modo: BULL / BEAR / LATERAL
- ✅ Genera `market-mode.conf`

**Comando:**
```bash
/home/overgon/.openclaw/workspace/crypto-bots/market-sentiment.sh
```

**Cron:** `0 * * * *` (cada hora)

---

### `test-scalping.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/crypto-bots/test-scalping.sh`

**Propósito:** Testear configuración SCALPING MODE

**Comando:**
```bash
/home/overgon/.openclaw/workspace/crypto-bots/test-scalping.sh
```

---

### `test-tp3-fix.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/crypto-bots/test-tp3-fix.sh`

**Propósito:** Testear fix de TP3 (cantidad de venta 30%/65%)

**Comando:**
```bash
/home/overgon/.openclaw/workspace/crypto-bots/test-tp3-fix.sh
```

---

## 🖥️ DASHBOARD

### `start.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/dashboard/start.sh`

**Propósito:** Iniciar dashboard Flask (sin Ngrok)

**Comando:**
```bash
cd /home/overgon/.openclaw/workspace/dashboard && bash start.sh
```

**URL:** `http://192.168.3.215:8080`

---

### `start-with-ngrok.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/dashboard/start-with-ngrok.sh`

**Propósito:** Iniciar dashboard + túnel Ngrok (HTTPS)

**Características:**
- ✅ HTTPS con candado verde
- ✅ Auto-start con systemd
- ✅ Dominio: `https://knapsack-divinity-diffuser.ngrok-free.dev`

**Comando:**
```bash
cd /home/overgon/.openclaw/workspace/dashboard && bash start-with-ngrok.sh
```

**Systemd:** `perrobotillo-dashboard-ngrok.service`

---

## 📊 REPORTES Y MONITOREO

### `daily-report-9am.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/daily-report-9am.sh`

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
/home/overgon/.openclaw/workspace/daily-report-9am.sh
```

**Output:** `daily-report-YYYY-MM-DD.md`

---

### `check-drawdown-alert.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/check-drawdown-alert.sh`

**Propósito:** Monitorear drawdown y alertar si excede límite

**Características:**
- ✅ Check cada 30 minutos
- ✅ Alerta si drawdown > 3% (configurable)
- ✅ Notificación por Telegram

**Cron:** `*/30 * * * *` (cada 30 min)

**Comando:**
```bash
/home/overgon/.openclaw/workspace/check-drawdown-alert.sh
```

---

### `check-public-ip.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/check-public-ip.sh`

**Propósito:** Monitorear IP pública y alertar si cambia (Binance whitelist)

**Características:**
- ✅ Detecta IP pública actual
- ✅ Compara con IP en whitelist de Binance
- ✅ Alerta por Telegram si cambia
- ✅ Útil para IP dinámica

**Cron:** `0 * * * *` (cada hora)

**Comando:**
```bash
/home/overgon/.openclaw/workspace/check-public-ip.sh
```

---

### `fan-control.sh` 🆕
**Ubicación:** `/home/overgon/.openclaw/workspace/scripts/fan-control.sh`

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
/home/overgon/.openclaw/workspace/scripts/fan-control.sh
```

**Log:** `/home/overgon/.openclaw/logs/fan-control.log`

---

### `tp-monitor.sh` 🆕🎯
**Ubicación:** `/home/overgon/.openclaw/workspace/scripts/tp-monitor.sh`

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
/home/overgon/.openclaw/workspace/scripts/tp-monitor.sh
```

**Log:** `/home/overgon/.openclaw/logs/tp-monitor.log`

**Output ejemplo:**
```
⚠️  CERCA DEL TP: SOL Slot 1 → 95.2%
🎯 TP HIT DETECTADO: SOL Slot 1 TP1
🚀 Ejecutando cierre INMEDIATO...
✅ Cierre ejecutado
```

---

## 🔒 SEGURIDAD Y EMERGENCIAS

### `emergency-close-all.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/emergency-close-all.sh`

**Propósito:** Cerrar TODAS las posiciones inmediatamente (emergency stop)

**Características:**
- ✅ Cierra todos los slots activos
- ✅ Vende 100% de la posición
- ✅ Guarda trades en histórico
- ✅ Notifica por Telegram

**⚠️ ADVERTENCIA:** Solo usar en emergencias reales (crash de mercado, bug crítico)

**Comando:**
```bash
/home/overgon/.openclaw/workspace/emergency-close-all.sh
```

---

### `auto-reset-closed-slots.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/auto-reset-closed-slots.sh`

**Propósito:** Resetear slots cerrados a READY para nuevas entradas

**Características:**
- ✅ Detecta slots CLOSED_* (TP1/TP2/TP3/SL/TRAILING)
- ✅ Cambia status a READY
- ✅ Limpia campos de trade anterior
- ✅ Permite slot recycling

**Cron:** Activo (se ejecuta después de cada cierre)

**Comando:**
```bash
/home/overgon/.openclaw/workspace/auto-reset-closed-slots.sh
```

---

## 🧪 BACKTESTING

### `run-backtest.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/backtest/run-backtest.sh`

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
/home/overgon/.openclaw/workspace/backtest/run-backtest.sh [COIN] [YEARS]
# Ejemplo: ./run-backtest.sh BTC 2
```

---

## 🛠️ UTILIDADES

### `claw-utils.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/lib/claw-utils.sh`

**Propósito:** Utilidades generales del sistema (reemplaza OpenClaw CLI)

**Características:**
- ✅ Detecta si dashboard corre (manual o systemd)
- ✅ Verifica estado de servicios
- ✅ Funciones utilitarias para otros scripts

**Comando:**
```bash
source /home/overgon/.openclaw/workspace/lib/claw-utils.sh
```

---

### `send-telegram.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/lib/send-telegram.sh`

**Propósito:** Enviar mensajes a Telegram sin OpenClaw (independiente)

**Características:**
- ✅ Usa Telegram Bot API directa
- ✅ No depende de OpenClaw Gateway
- ✅ Útil para alertas críticas

**Comando:**
```bash
/home/overgon/.openclaw/workspace/lib/send-telegram.sh "Mensaje de prueba"
```

**Secrets:** `/home/overgon/.openclaw/secrets/telegram.env`

---

### `crypto-coincap-prices.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/crypto-coincap-prices.sh`

**Propósito:** Obtener precios de CoinCap API

**Comando:**
```bash
/home/overgon/.openclaw/workspace/crypto-coincap-prices.sh
```

---

### `crypto-exchange-compare.sh`
**Ubicación:** `/home/overgon/.openclaw/workspace/crypto-exchange-compare.sh`

**Propósito:** Comparar precios entre exchanges (Binance vs CoinCap)

**Comando:**
```bash
/home/overgon/.openclaw/workspace/crypto-exchange-compare.sh
```

---

## 💰 GESTIÓN DE CAPITAL

### `auto-capital-manager.sh` 🆕🤖
**Ubicación:** `/home/overgon/.openclaw/workspace/scripts/auto-capital-manager.sh`

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
/home/overgon/.openclaw/workspace/scripts/auto-capital-manager.sh
```

**Log:** `/home/overgon/.openclaw/logs/auto-capital-manager.log`

**Progreso:** `/home/overgon/.openclaw/workspace/crypto-bots/capital-manager-progress.json`

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
**Ubicación:** `/home/overgon/.openclaw/workspace/config/capital-config.sh`

**Propósito:** Configuración de capital por moneda

**Características:**
- ✅ Define USDT por slot
- ✅ Define porcentaje de posición
- ✅ Configuración centralizada
- ✅ Actualizado por `auto-capital-manager.sh`

**Comando:**
```bash
source /home/overgon/.openclaw/workspace/config/capital-config.sh
```

---

## 📋 RESUMEN DE CRON JOBS

| Cron | Script | Propósito |
|------|--------|-----------|
| `*/2 * * * *` | `fan-control.sh` | Control ventilador (cada 2 min) |
| `*/30 * * * *` | `check-drawdown-alert.sh` | Alerta drawdown (cada 30 min) |
| `0 * * * *` | `market-sentiment.sh` | Sentimiento mercado (cada hora) |
| `0 * * * *` | `check-public-ip.sh` | Check IP pública (cada hora) |
| `0 9 * * *` | `daily-report-9am.sh` | Reporte diario (9 AM) |
| `0 9 * * *` | `auto-capital-manager.sh` | Gestión capital (9 AM) |
| `0 */6 * * *` | `auto-adjust-strategy.sh` | Auto-ajuste estrategia (6 horas) |
| `4,14,24,34,44,54 * * * *` | `crypto-trade-moneda-v3-slots.sh LINK` | Trading bot LINK |
| *(similar)* | `crypto-trade-moneda-v3-slots.sh [COIN]` | Trading bot cada moneda |

**Total:** 25 cron jobs activos

---

## 📁 ARCHIVOS CLAVE

### Configuración
- `/home/overgon/.openclaw/secrets/binance.env` - API keys de Binance 🔒
- `/home/overgon/.openclaw/secrets/telegram.env` - Telegram bot token 🔒
- `/home/overgon/.openclaw/workspace/crypto-bots/dynamic-config.env` - Config dinámica (auto-generada)
- `/home/overgon/.openclaw/workspace/crypto-bots/market-mode.conf` - Modo de mercado actual
- `/home/overgon/.openclaw/workspace/config/capital-config.sh` - Capital por moneda

### Estado
- `/home/overgon/.openclaw/workspace/crypto-bots/[COIN]-trade-state.json` - Estado de slots por moneda
- `/home/overgon/.openclaw/workspace/crypto-bots/trade-history.json` - Histórico de trades (62 trades, 100% win rate)
- `/home/overgon/.openclaw/workspace/crypto-bots/cashout-history.json` - Histórico de cashouts
- `/home/overgon/.openclaw/workspace/crypto-bots/capital-manager-progress.json` - Progreso auto-capital

### Logs
- `/home/overgon/.openclaw/logs/auto-trade-all.log` - Log principal de trading
- `/home/overgon/.openclaw/logs/fan-control.log` - Log de control de ventilador
- `/home/overgon/.openclaw/logs/tp-monitor.log` - Log de monitoreo de TPs
- `/home/overgon/.openclaw/logs/auto-capital-manager.log` - Log de gestión de capital

### Reportes
- `/home/overgon/.openclaw/workspace/daily-report-YYYY-MM-DD.md` - Reportes diarios

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
jq '.slots[] | select(.status == "ACTIVE")' /home/overgon/.openclaw/workspace/crypto-bots/*-trade-state.json

# TP Monitor status
systemctl status perrobotillo-tp-monitor

# Capital Manager progress
cat /home/overgon/.openclaw/workspace/crypto-bots/capital-manager-progress.json | jq .
```

### Ver logs en tiempo real
```bash
tail -f /home/overgon/.openclaw/logs/auto-trade-all.log
tail -f /home/overgon/.openclaw/logs/fan-control.log
tail -f /home/overgon/.openclaw/logs/tp-monitor.log
tail -f /home/overgon/.openclaw/logs/auto-capital-manager.log
```

### Reiniciar servicios
```bash
# Dashboard
pkill -9 -f "python.*app.py" && cd /home/overgon/.openclaw/workspace/dashboard && bash start-with-ngrok.sh &

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

## 📊 ESTADÍSTICAS ACTUALES (Mayo 11, 2026)

```
Total Trades: 62
Win Rate: 100% 🏆
Net P&L: +$219.04 USDT

Portfolio: ~$2,887 USDT (~$49,700 MXN con tasa real)

Slots Activos: 13/21 (62% utilización)
Slots Disponibles: 8/21

Cashouts: 2 ($360.04 USDT → $6,280.70 MXN)

Temperatura RPi5: ~38-45°C
Ventilador: Auto control (PWM 0-255)

Position Size: 27% (auto-ajustado por bot)
  → ~$779 USDT por trade

Estrategia Actual: LATERAL + SCALPING MODE
  TP1: 2.5% | TP2: 5.0% | TP3: 7.0% | SL: 5.0%
  SCALPING: 1.0% target, 2.5% SL
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

- `/home/overgon/.openclaw/workspace/README.md` - Introducción
- `/home/overgon/.openclaw/workspace/INSTALL.md` - Instalación
- `/home/overgon/.openclaw/workspace/SECURITY.md` - Seguridad
- `/home/overgon/.openclaw/workspace/TRANSICION-SIN-OPENCLAW.md` - Migración
- `/home/overgon/.openclaw/workspace/ESTRATEGIAS-TRADING.md` - Estrategias (10.2KB)
- `/home/overgon/.openclaw/workspace/CHANGELOG-2026-05-08.md` - Changelog completo (14KB)
- `/home/overgon/.openclaw/workspace/backtest/results/PROYECCION-FIN-2026.md` - Proyecciones

---

## 🦴 SOPORTE

**GitHub:** https://github.com/overgon/perrobotillo-trading-bot

**Dashboard:** https://knapsack-divinity-diffuser.ngrok-free.dev

**Telegram:** Bot integrado para alertas y reportes

---

## 🎯 NOVEDADES MAYO 11, 2026

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
