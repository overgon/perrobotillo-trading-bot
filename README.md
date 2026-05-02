# 🐕 Perrobotillo Trading Bot

**Bot de Trading Automatizado para Binance**  
*Versión: FASE 1 v2.1 Optimizada*

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

### Estrategia Actual (2026-05-02)

**Mercado:** Lateral (consolidación)

| Parámetro | Valor | Notas |
|-----------|-------|-------|
| **Stop Loss** | 5.5-8.0% | Por coin, basado en volatilidad |
| **Take Profit 1** | 1.8% | 35% de la posición |
| **Take Profit 2** | 3.5% | 35% de la posición |
| **Take Profit 3** | 5.0% | 30% de la posición |
| **Trailing Stop** | DESACTIVADO | Solo en mercado con trend |
| **Slots Máximos** | 14/21 | 67% exposición (mercado lateral) |

### Coins Soportadas

- BTC (Bitcoin)
- ETH (Ethereum)
- BNB (Binance Coin)
- SOL (Solana)
- LINK (Chainlink)
- XRP (Ripple)
- AVAX (Avalanche)

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

### Reportes

```bash
# Generar reporte diario manualmente
./daily-report-9am.sh

# Ver último reporte
cat crypto-bots/daily-report-$(date +%Y-%m-%d).md
```

---

## 🛠️ MANTENIMIENTO

### Monitoreo de IP (si es dinámica)

```bash
# Agregar al crontab (cada hora)
crontab -e

# Agrega esta línea:
0 * * * * /home/overgon/.openclaw/workspace/check-public-ip.sh
```

### Alertas de Drawdown

```bash
# Agregar al crontab (cada 30 min)
*/30 * * * * /home/overgon/.openclaw/workspace/check-drawdown-alert.sh
```

### Reporte Diario Automático

```bash
# Agregar al crontab (9 AM diario)
0 9 * * * /home/overgon/.openclaw/workspace/daily-report-9am.sh
```

---

## 📁 ESTRUCTURA DEL PROYECTO

```
perrobotillo-trading-bot/
├── README.md                 # Este archivo
├── SECURITY.md               # Políticas de seguridad
├── CHANGELOG-2026-05-02.md   # Historial de cambios
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
│   ├── daily-report-9am.sh              # Reporte diario
│   ├── check-public-ip.sh               # Monitor de IP
│   ├── check-drawdown-alert.sh          # Alertas drawdown
│   ├── emergency-close-all.sh           # Cierre emergencia
│   └── STRATEGY-UPDATE-2026-05-02.md    # Documentación estrategia
│
├── state/                   # Estados temporales (no subir)
├── logs/                    # Logs de operación
└── crypto-bots/             # Datos de trading (no subir)
    ├── *-trade-state.json   # Estado actual por coin
    ├── *-daily-pnl.json     # P&L diario
    └── trade-history.json   # Histórico de trades
```

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
```

---

## 📈 PERFORMANCE HISTÓRICA

**Desde:** 2026-04-26  
**Hasta:** 2026-05-02

| Métrica | Valor |
|---------|-------|
| Total Trades | 6 |
| Win Rate | 16.67% ⚠️ |
| Net P&L | -$18.40 USDT |
| Mayor Win | +$6.64 (SOL) |
| Mayor Loss | -$11.86 (BTC) |

> ⚠️ **Nota:** El win rate actual es bajo (16.67%). Se actualizó la estrategia el 2026-05-02 para mejorar a 45-50% esperado.

---

## 📝 LICENCIA

MIT License - Ver archivo LICENSE

---

## 🐕 SOBRE PERROBOTILLO

**Perrobotillo** es un perro cyborg trader creado para operar en el mercado de criptomonedas de forma automatizada, siguiendo estrategias técnicas y gestionando el riesgo de forma disciplinada.

*"Nunca confiar, siempre verificar"* 🐕

---

<div align="center">

**⚠️ TRADING CONLLEVA RIESGOS - OPERA RESPONSABLEMENTE**

[![GitHub](https://img.shields.io/github/stars/overgon/perrobotillo-trading-bot)](https://github.com/overgon/perrobotillo-trading-bot)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>
