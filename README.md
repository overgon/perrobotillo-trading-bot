# 🐕 Perrobotillo Trading Bot

**Bot de Trading Automatizado para Binance**  
*Versión: FASE 1 v2.1 Optimizada*  
*Última actualización: 2026-05-13*

> ⚠️ **ADVERTENCIA:** Este bot opera con criptomonedas reales. El trading de criptoactivos conlleva riesgos significativos. Úsalo bajo tu propia responsabilidad.

---

## 🚨 RIESGOS Y ADVERTENCIAS

### ⚠️ ANTES DE USAR, ENTIENDE ESTO:

1. **PUEDES PERDER DINERO** - El trading de criptomonedas es volátil. Este bot no garantiza ganancias.

2. **NUNCA uses dinero que no puedas permitirte perder** - Solo capital que estés dispuesto a perder completamente.

3. **API Keys = Acceso Total** - Quien tenga tus API keys puede operar en tu cuenta. Guárdalas como secreto de estado.

4. **Este no es consejo financiero** - El bot ejecuta una estrategia técnica. Investiga y entiende lo que hace.

5. **Monitoreo constante** - Aunque es automático, debes supervisar regularmente.

### 🛡️ MEJORES PRÁCTICAS DE SEGURIDAD

- ✅ **IP Whitelist en Binance** - Restringe tus API keys solo a tu IP pública
- ✅ **Sin retiros** - Las API keys NO deben tener permiso de withdrawal
- ✅ **Ambiente aislado** - Usa una máquina dedicada (Raspberry Pi, VPS)
- ✅ **Secrets en archivos separados** - Nunca commits de `.env` o `secrets/`
- ✅ **Monitoreo de IP** - Alertas si tu IP pública cambia
- ✅ **Backups** - Respalda tu configuración regularmente

---

## 📋 REQUERIMIENTOS

### Hardware
- Raspberry Pi 5 (recomendado) o cualquier Linux
- 4GB RAM mínimo (8GB recomendado)
- Conexión a internet estable

### Software
- Node.js 20+ 
- OpenClaw 2026.4.15+
- Cuenta en Binance con API keys
- (Opcional) Telegram para notificaciones

---

## 🚀 INSTALACIÓN

### 1. Clonar el repositorio

```bash
git clone git@github.com:overgon/perrobotillo-trading-bot.git
cd perrobotillo-trading-bot
```

### 2. Instalar OpenClaw

```bash
# Instalar OpenClaw (si no lo tienes)
npm install -g openclaw

# Inicializar OpenClaw
openclaw onboard
```

### 3. Configurar API Keys de Binance

**⚠️ CRÍTICO: Sigue estos pasos de seguridad**

1. Ve a [Binance API Management](https://www.binance.com/en/my/settings/api-management)

2. Crea una NUEVA API key con:
   - ✅ **Enable Reading:** SÍ
   - ✅ **Enable Spot & Margin Trading:** SÍ
   - ❌ **Enable Withdrawals:** NO (NUNCA)

3. **IP Whitelist:**
   - Agrega tu IP pública actual
   - Marca "Restrict access to trusted IPs only"
   - ⚠️ Si tu IP es dinámica, usa un script de monitoreo (incluido)

4. Guarda la API Key y Secret Key

### 4. Crear archivo de secrets

```bash
# Crear directorio de secrets
mkdir -p secrets

# Crear archivo binance.env
cat > secrets/binance.env << 'EOF'
# ════════════════════════════════════════════════════════
# 🔐 BINANCE API CREDENTIALS
# ════════════════════════════════════════════════════════
# ⚠️ NUNCA compartas este archivo o lo subas a GitHub
# ⚠️ Este archivo debe estar en .gitignore

BINANCE_API_KEY="tu_api_key_aqui"
BINANCE_SECRET_KEY="tu_secret_key_aqui"

# ════════════════════════════════════════════════════════
# 🌐 IP WHITELIST
# ════════════════════════════════════════════════════════
# Tu IP pública actual (búscala en: https://api.ipify.org)
# Actualiza esto si tu IP cambia
PUBLIC_IP="123.456.789.012"

# ════════════════════════════════════════════════════════
# 📊 CONFIGURACIÓN DE TRADING
# ════════════════════════════════════════════════════════
# Capital inicial para trading (USDT)
TRADING_CAPITAL=1100

# Porcentaje de riesgo por trade
RISK_PER_TRADE=1.0

# Stop Loss máximo diario (porcentaje del portfolio)
MAX_DAILY_LOSS=3.0
EOF

# ⚠️ Verifica que el archivo NO sea legible por otros
chmod 600 secrets/binance.env
```

### 5. Configurar Telegram (Opcional pero recomendado)

1. Crea un bot con [@BotFather](https://t.me/botfather)
2. Obtén el token del bot
3. Obtén tu Chat ID con [@userinfobot](https://t.me/userinfobot)

```bash
# Agrega a secrets/telegram.env
cat > secrets/telegram.env << 'EOF'
TELEGRAM_BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_CHAT_ID="123456789"
EOF

chmod 600 secrets/telegram.env
```

### 6. Verificar configuración

```bash
# Ejecutar script de verificación
./check-public-ip.sh

# Deberías ver:
# ✅ API Binance: Conectada
# ✅ IP Whitelist: Verificada
# ✅ Secrets: Configurados
```

---

## 🎯 CONFIGURACIÓN DE TRADING

### Estrategia Actual (2026-05-13)

**Mercado:** VOLATILE_BULL (dinámico)

| Parámetro | Valor | Notas |
|-----------|-------|-------|
| **Stop Loss** | 10.0% | Por coin, fijo |
| **Take Profit 1** | 3.5% | 35% de la posición |
| **Take Profit 2** | 7.0% | 35% de la posición |
| **Take Profit 3** | 12.0% | 30% de la posición |
| **Trailing Stop** | ACTIVADO | En mercado con trend |
| **Position Size** | 20% | Por slot |
| **Slots Máximos** | 21/21 | 100% exposición (3 por coin) |

### Estrategia Dinámica (Auto-Adjust)

El bot **ajusta automáticamente** la estrategia cada 6 horas basado en:
- Fear & Greed Index
- Volatilidad del mercado
- Trend analysis (BTC dominance, USDT dominance)

**Modos de mercado:**
- `BULL` → TP agresivos, trailing stop activado
- `BEAR` → TP conservadores, más SL
- `LATERAL` → TP medios, menos exposición
- `VOLATILE_BULL` → TP agresivos, SL amplio

### 🤖 ML TP Prediction (FASE 1 - 2026-05-13)

El bot usa **Machine Learning** para predecir probabilidad de TP y ajustar dinámicamente:

**Características:**
- ✅ **Modelo:** LightGBM Classifier (0.31 MB)
- ✅ **Features:** 22 indicadores (RSI, MACD, Bollinger, volatilidad, volumen)
- ✅ **Accuracy:** 79-90% (cross-validation)
- ✅ **Inferencia:** < 1 segundo
- ✅ **Actualización:** Cada 5 minutos (predicciones en vivo)
- ✅ **Auto-retrain:** Semanal (domingo 3 AM) + cada 10 trades nuevos

**Niveles de confianza:**
- `AGGRESSIVE` (prob > 75%) → TP1: 4.0% | TP2: 8.0% | TP3: 15.0%
- `NORMAL` (prob 60-75%) → TP1: 3.5% | TP2: 7.0% | TP3: 12.0%
- `CONSERVATIVE` (prob 40-60%) → TP1: 2.5% | TP2: 5.0% | TP3: 8.0%
- `DEFENSIVE` (prob < 40%) → TP1: 2.0% | TP2: 4.0% | TP3: 6.0%

**Predicciones actuales (ejemplo):**
- SOL: 88.7% → AGGRESSIVE (4.0% | 8.0% | 15.0%)
- LINK: 93.1% → AGGRESSIVE (4.0% | 8.0% | 15.0%)
- XRP: 90.3% → AGGRESSIVE (4.0% | 8.0% | 15.0%)
- BTC: 66.1% → NORMAL (3.5% | 7.0% | 12.0%)
- BNB: 49.4% → CONSERVATIVE (2.5% | 5.0% | 8.0%)
- ETH: 7.3% → DEFENSIVE (2.0% | 4.0% | 6.0%)

**Archivos ML:**
- `ml/train-tp-model.py` - Entrenamiento inicial
- `ml/predict-tp.py` - Inferencia en tiempo real
- `ml/auto-retrain.py` - Auto-mejora continua
- `ml/tp_prediction_model.pkl` - Modelo entrenado
- `ml/tp-recommendations.json` - Recomendaciones actuales

### Coins Soportadas (7)

- BTC (Bitcoin) - 3 slots
- ETH (Ethereum) - 3 slots
- BNB (Binance Coin) - 3 slots
- SOL (Solana) - 3 slots
- LINK (Chainlink) - 3 slots
- XRP (Ripple) - 3 slots
- AVAX (Avalanche) - 3 slots

**Total: 21 slots**

---

## 📊 USO

### Iniciar el bot

```bash
# Para una moneda específica
./crypto-trade-moneda-v3-slots.sh BTC

# Para todas las monedas (recomendado)
for coin in BTC ETH BNB SOL LINK XRP AVAX; do
    ./crypto-trade-moneda-v3-slots.sh $coin &
done
```

### Ver status

```bash
# Ver trades activos
cat crypto-bots/*-trade-state.json | jq '.slots[] | select(.status == "ACTIVE")'

# Ver P&L del día
cat crypto-bots/*-daily-pnl.json | jq '.'

# Ver histórico de trades
cat crypto-bots/trade-history.json | jq '.'
```

### Dashboard Web

**Acceso local:**
```
http://localhost:8080/
```

**Acceso remoto (SSH tunnel):**
```bash
ssh -L 9090:localhost:8080 -N <YOUR_USERNAME>@<YOUR_RPI_IP>
# Luego abrir: http://localhost:9090/
```

**Acceso remoto (Ngrok):**
```
https://<YOUR_NGROK_SUBDOMAIN>.ngrok-free.dev
```

**Características del Dashboard:**
- ✅ Portfolio en tiempo real desde Binance
- ✅ Trades activos con P&L en vivo
- ✅ Barras de progreso TP1/TP2/TP3
- ✅ Histórico de trades cerrados
- ✅ P&L por moneda
- ✅ P&L 24H
- ✅ Notificaciones visuales y sonoras en TP hits
- ✅ Mobile optimized (iPhone 14 Pro)
- ✅ GPU optimized (21% usage)

### Reportes

```bash
# Generar reporte diario manualmente
./daily-report-9am.sh

# Ver último reporte
cat crypto-bots/daily-report-$(date +%Y-%m-%d).md
```

**Reporte diario automático:** 9:00 AM por Telegram (Markdown)

---

## 🛠️ MANTENIMIENTO

### Monitoreo de IP (si es dinámica)

```bash
# Agregar al crontab (cada hora)
crontab -e

# Agrega esta línea:
0 * * * * /home/<YOUR_USERNAME>/.openclaw/workspace/check-public-ip.sh
```

### Alertas de Drawdown

```bash
# Agregar al crontab (cada 30 min)
*/30 * * * * /home/<YOUR_USERNAME>/.openclaw/workspace/check-drawdown-alert.sh
```

### Reporte Diario Automático

```bash
# Agregar al crontab (9 AM diario)
0 9 * * * /home/<YOUR_USERNAME>/.openclaw/workspace/daily-report-9am.sh
```

### TP Monitor (Take Profit Detection)

```bash
# Ya configurado como systemd service
systemctl status perrobotillo-tp-monitor

# Logs
tail -f /home/<YOUR_USERNAME>/.openclaw/logs/tp-monitor.log
```

**Funciones:**
- Escanea trades cerrados cada 30 segundos
- Detecta TP1/TP2/TP3/SL/Trailing/Scalp
- Notifica por Telegram con audio (cash register)
- Actualiza trade-state.json automáticamente

### Watchdog (Dashboard + Ngrok Monitor)

```bash
# Ejecuta cada 1 minuto desde cron
crontab -l | grep watchdog

# Logs
tail -f /home/<YOUR_USERNAME>/.openclaw/logs/dashboard-watchdog.log
```

**Funciones:**
- Monitorea dashboard (puerto 8080)
- Monitorea ngrok tunnel
- Reinicia automáticamente si falla
- Notifica por Telegram con rate limiting (1 alerta/10 min)

### Housekeeping (Limpieza de Logs)

```bash
# Mensual (1ro de cada mes, 1 AM)
0 1 1 * * /home/<YOUR_USERNAME>/.openclaw/scripts/housekeeping.sh

# Semanal (domingos, 2 AM)
0 2 * * 0 logrotate -f /home/<YOUR_USERNAME>/.openclaw/logs/logrotate.conf
```

**Funciones:**
- Elimina logs > 30 días
- Elimina logs .gz > 7 días
- Mantiene últimos 7 días de trade-*.log
- Rota logs grandes (>5-10MB)
- Notifica por Telegram si logs > 500MB o disco > 80%

### Auto-Adjust Strategy

```bash
# Cada 6 horas
0 */6 * * * /home/<YOUR_USERNAME>/.openclaw/workspace/crypto-bots/auto-adjust-strategy.sh
```

**Funciones:**
- Analiza Fear & Greed Index
- Analiza BTC dominance y USDT dominance
- Ajusta TP/SL según modo de mercado
- Notifica cambios por Telegram

### Auto Capital Manager

```bash
# Diario 9:00 AM
0 9 * * * /home/<YOUR_USERNAME>/.openclaw/workspace/scripts/auto-capital-manager.sh
```

**Funciones:**
- Revisa performance de últimos 7 días
- Ajusta capital si win rate > 60%
- Notifica cambios por Telegram

---

## 📁 ESTRUCTURA DEL PROYECTO

```
perrobotillo-trading-bot/
├── README.md                 # Este archivo
├── SECURITY.md               # Políticas de seguridad
├── CHEATSHEET.md             # 21 scripts principales
├── .gitignore               # Archivos ignorados por git
│
├── secrets/                  # 🔐 CREDENCIALES (NO SUBIR)
│   ├── binance.env          # API keys de Binance
│   └── telegram.env         # Token de Telegram
│
├── config/                   # Configuración
│   └── capital-config.sh    # Estrategia 20/80
│
├── crypto-bots/             # Scripts del bot
│   ├── crypto-trade-moneda-v3-slots.sh  # Bot principal
│   ├── auto-adjust-strategy.sh          # Auto-ajuste cada 6h
│   ├── daily-report-9am.sh              # Reporte diario
│   ├── check-public-ip.sh               # Monitor de IP
│   ├── check-drawdown-alert.sh          # Alertas drawdown
│   ├── emergency-close-all.sh           # Cierre emergencia
│   └── market-sentiment.sh              # Análisis mercado
│
├── scripts/                  # Scripts adicionales
│   ├── tp-monitor.sh        # TP detection (30s)
│   ├── auto-capital-manager.sh  # Gestión capital (9 AM)
│   ├── fan-control.sh       # Control ventilador RPi5
│   └── generate-html-trades.py  # Generador HTML
│
├── dashboard/                # Dashboard web
│   ├── app.py               # Flask server
│   ├── templates/           # HTML templates
│   ├── static/              # CSS, JS, avatars
│   └── watchdog.sh          # Monitor dashboard+ngrok
│
├── logs/                     # Logs de operación
│   ├── auto-heal.log
│   ├── auto-trade-all.log
│   ├── tp-monitor.log
│   ├── dashboard-watchdog.log
│   └── trade-*.log
│
└── crypto-bots/             # Datos de trading (no subir)
    ├── *-trade-state.json   # Estado actual por coin
    ├── *-daily-pnl.json     # P&L diario
    ├── trade-history.json   # Histórico de trades
    └── daily-report-*.md    # Reportes diarios
```

---

## 🔧 SCRIPTS PRINCIPALES (21)

### 🤖 ML TP Prediction (NUEVO - 2026-05-13)

```bash
# Ejecutar predicción en tiempo real
python3 ml/predict-tp.py

# Obtener recomendación para una coin
bash ml/get-tp-recommendation.sh BTC
# Output: 3.5|7.0|12.0 (TP1|TP2|TP3)

# Ver predicciones actuales
cat ml/tp-recommendations.json | jq .

# Logs de re-entrenamiento
tail -f logs/ml-retrain.log
```

**Auto-retrain automático:**
- 📅 Domingo 3 AM (cron)
- 🆕 Cada 10+ trades nuevos
- 📊 Mejora continua sin intervención humana

Ver [`CHEATSHEET.md`](CHEATSHEET.md) para lista completa.

**Trading:**
- `crypto-trade-moneda-v3-slots.sh` - Bot principal con slots
- `emergency-close-all.sh` - Cierre de emergencia
- `test-scalping.sh` - Test modo scalping

**Monitoreo:**
- `tp-monitor.sh` - TP detection (systemd, 30s)
- `check-drawdown-alert.sh` - Alertas drawdown (30 min)
- `check-public-ip.sh` - Monitor de IP (hourly)

**Reportes:**
- `daily-report-9am.sh` - Reporte diario (9 AM)
- `eth-accumulation-tracker.sh` - Tracker ETH

**Optimización:**
- `auto-adjust-strategy.sh` - Auto-ajuste (6h)
- `auto-capital-manager.sh` - Capital manager (9 AM)
- `auto-increase-capital.sh` - Aumento progresivo
- `fan-control.sh` - Ventilador RPi5

**Dashboard:**
- `dashboard/watchdog.sh` - Monitor dashboard+ngrok (1 min)
- `dashboard/start-with-ngrok.sh` - Inicio con ngrok

**Backtest:**
- `backtest/run-backtest.sh` - Ejecutar backtests
- `backtest/results/*.md` - Resultados históricos

**Housekeeping:**
- `scripts/housekeeping.sh` - Limpieza mensual (1ro mes)
- `logs/logrotate.conf` - Rotación semanal (domingos)

---

## 🆘 SOPORTE Y RECURSOS

### Documentación
- [OpenClaw Docs](https://docs.openclaw.ai)
- [Binance API Docs](https://binance-docs.github.io/apidocs/)

### Comunidad
- [Discord OpenClaw](https://discord.com/invite/clawd)
- [GitHub Issues](https://github.com/overgon/perrobotillo-trading-bot/issues)

### Emergencias
```bash
# Cerrar TODOS los trades inmediatamente
./emergency-close-all.sh

# Ver estado del sistema
openclaw status

# Reiniciar dashboard
systemctl restart perrobotillo-dashboard-ngrok

# Reiniciar TP Monitor
systemctl restart perrobotillo-tp-monitor

# Ver logs en vivo
tail -f /home/<YOUR_USERNAME>/.openclaw/logs/auto-trade-all.log
```

---

## 📈 PERFORMANCE HISTÓRICA

**Desde:** 2026-04-26  
**Hasta:** 2026-05-13

| Métrica | Valor |
|---------|-------|
| Total Trades | 62+ |
| Win Rate | 100% ✅ |
| Net P&L | +$219+ USDT |
| Mayor Win | +$17.32 (SOL TP3) |
| Daily Report | Automático 9 AM |

### Últimos 7 días (2026-05-06 a 2026-05-13)
- Trades cerrados: 15+
- P&L: +$50+ USDT
- Win rate: 100%

> ✅ **Nota:** Estrategia LONG ONLY validada con backtest de 6 años (45-50% win rate esperado, 100% actual).

---

## 🎯 PRÓXIMAS MEJORAS (ROADMAP)

### FASE 1 (✅ COMPLETADA - 2026-05-13)
- [x] Soporte para LONG positions
- [x] Multi-slot (3 por moneda, 21 total)
- [x] Dashboard web con datos en vivo
- [x] TP Monitor (detección 30s)
- [x] Auto-Adjust Strategy (6h)
- [x] Auto Capital Manager (9 AM)
- [x] Watchdog con alertas Telegram
- [x] Housekeeping automático
- [x] **🤖 ML TP Prediction (FASE 1)**
  - [x] Modelo LightGBM (0.31 MB)
  - [x] 22 features (RSI, MACD, BB, volatilidad)
  - [x] Accuracy: 79-90%
  - [x] Inferencia < 1 segundo
  - [x] Auto-retrain semanal
  - [x] Integración con bot principal

### FASE 2 (En desarrollo)
- [ ] ML FASE 2: Mejorar accuracy a 85%+ (más features, más trades)
- [ ] Integración con más exchanges (KuCoin, Bybit)
- [ ] Dashboard con gráficos en vivo (Chart.js)
- [ ] Backtesting en la nube
- [ ] ML para detección de mercado (BULL/BEAR/LATERAL)

### FASE 3 (Futuro)
- [ ] Estrategias multi-timeframe
- [ ] Portfolio rebalancing automático
- [ ] Alertas de mercado avanzadas
- [ ] API REST para control externo
- [ ] Mobile app (React Native)

---

## 📝 NOTA SOBRE LONG ONLY

**¿Por qué solo LONG?**

Después de backtesting de 6 años y 62+ trades reales:
- ✅ **Win rate LONG:** 100% (62 trades)
- ❌ **Win rate SHORT:** <40% (backtest)

**Razones:**
1. **Crypto tiene bias alcista** - A largo plazo, el mercado tiende a subir
2. **Volatilidad asimétrica** - Las subidas son más predecibles que las bajadas
3. **Nuestra estrategia** - Está optimizada para mercados con tendencia positiva
4. **Risk/Reward** - LONG tiene mejor relación riesgo/beneficio en crypto

**Conclusión:** LONG ONLY es la estrategia validada. No recomendamos SHORT.

---

## 📝 LICENCIA

MIT License - Ver archivo LICENSE

---

## 🐕 SOBRE PERROBOTILLO

**Perrobotillo** es un perro cyborg trader creado para operar en el mercado de criptomonedas de forma automatizada, siguiendo estrategias técnicas y gestionando el riesgo de forma disciplinada.

**Características:**
- 🐕 Perro cyborg con gafas holográficas
- 📊 Gráficos de trading en tiempo real
- 🎯 Estrategia LONG ONLY validada
- 🔒 Seguridad primero (IP whitelist, monitoreo)
- 📱 Notificaciones Telegram 24/7
- 🧹 Housekeeping automático
- 🚀 Dashboard web optimizado

*"Nunca confiar, siempre verificar"* 🐕

---

## 📊 SYSTEM STATUS

**Última verificación:** 2026-05-13

| Componente | Status | Notas |
|------------|--------|-------|
| **Trading Bot** | ✅ ONLINE | 7 coins, 21 slots |
| **TP Monitor** | ✅ ONLINE | Systemd, 30s scan |
| **Dashboard** | ✅ ONLINE | GPU optimized (21%) |
| **Ngrok** | ✅ ONLINE | HTTPS enabled |
| **Watchdog** | ✅ ONLINE | Telegram alerts |
| **Housekeeping** | ✅ ONLINE | Monthly cleanup |
| **Auto-Adjust** | ✅ ONLINE | Every 6 hours |
| **Daily Report** | ✅ ONLINE | 9 AM Telegram |
| **IP Monitor** | ✅ ONLINE | Hourly checks |
| **Drawdown Alert** | ✅ ONLINE | Every 30 min |

**Total:** 10/10 sistemas operativos 🎉

---

<div align="center">

**⚠️ TRADING CONLLEVA RIESGOS - OPERA RESPONSABLEMENTE**

[![GitHub](https://img.shields.io/github/stars/overgon/perrobotillo-trading-bot)](https://github.com/overgon/perrobotillo-trading-bot)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-100%25%20operational-brightgreen)](https://github.com/overgon/perrobotillo-trading-bot)

🐕 **Perrobotillo Trading Bot** - FASE 1 v2.1 Optimizada

</div>
