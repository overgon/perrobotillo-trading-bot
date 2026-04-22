# 🐕 Perrobotillo Trading Bot

**Bot de Trading Cripto Automatizado para Binance**  
**Versión:** FASE 1 v2 (2026.4.16)  
**Plataforma:** Raspberry Pi 5 + OpenClaw + Ollama + Qwen 3.5

[![Status](https://img.shields.io/badge/status-active-success)](https://github.com/overgon/perrobotillo-trading-bot)
[![Version](https://img.shields.io/badge/version-FASE%201%20v2-blue)](https://github.com/overgon/perrobotillo-trading-bot)
[![Win Rate](https://img.shields.io/badge/win%20rate-30--35%25-green)](https://github.com/overgon/perrobotillo-trading-bot)

---

## 📋 **ÍNDICE**

- [Descripción](#-descripción)
- [Características](#-características)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Uso](#-uso)
- [Estructura](#-estructura)
- [FASE 1 v2 Config](#-fase-1-v2-configuración)
- [Comandos Útiles](#-comandos-útiles)
- [Troubleshooting](#-troubleshooting)
- [Seguridad](#-seguridad)

---

## 🎯 **DESCRIPCIÓN**

Perrobotillo es un bot de trading cripto automatizado que opera en Binance con **7 activos** (BTC, ETH, BNB, SOL, LINK, XRP, AVAX) usando un sistema de **21 slots** (3 por coin).

**Objetivos:**
- Win Rate: 30-35% (TP3 3.5%)
- P&L Mensual: $180-240 USDT
- Operación 24/7 con auto-reparación
- Notificaciones Telegram en tiempo real

---

## ✨ **CARACTERÍSTICAS**

### **Trading:**
- ✅ 7 coins: BTC, ETH, BNB, SOL, LINK, XRP, AVAX
- ✅ 21 slots (3 por coin)
- ✅ Take Profit escalonado: TP1 1.5%, TP2 3.0%, TP3 3.5%
- ✅ Stop Loss por volatilidad (3.5%-7.0%)
- ✅ Trailing Stop (breakeven + 2%)
- ✅ Acumulación 5% (reinvertir ganancias)

### **Auto-Repair V2:**
- ✅ Detección a nivel de slot (no global)
- ✅ Auto-reset después de 10 minutos
- ✅ Pre-alerta a los 7 minutos
- ✅ Excluye CLOSED_EMERGENCY y CLOSED_MANUAL

### **Emergency Close:**
- ✅ Cierre de emergencia por caídas del mercado
- ✅ Validación `&& daily_loss > 0` (anti-falsos positivos)
- ✅ Actualización correcta de state files

### **Notificaciones:**
- ✅ Telegram bot (@PerrobotilloBot)
- ✅ Alertas de compra, TP, SL
- ✅ Daily Report automático (9 AM)
- ✅ Health checks periódicos

### **IA:**
- ✅ Ollama como runtime
- ✅ Qwen 3.5 (qwen3.5:cloud) para decisiones

---

## 📦 **REQUISITOS**

### **Hardware:**
- Raspberry Pi 5 (4GB+ RAM) o Linux x86_64
- Conexión a internet estable
- Almacenamiento: 10GB mínimo

### **Software:**
```yaml
OS: Raspberry Pi OS (Linux 6.12+) o Ubuntu 22.04+
Node.js: v22.x
OpenClaw: 2026.4.15+
Ollama: Latest (para qwen3.5:cloud)
Git: Latest
Binance API: Key + Secret (read + trade permissions)
Telegram Bot: Creado vía @BotFather
SSH Key: Para GitHub (opcional)
```

---

## 🚀 **INSTALACIÓN**

### **Paso 1: Clonar el Repositorio**

```bash
# Clonar el repo
git clone git@github.com:overgon/perrobotillo-trading-bot.git
cd perrobotillo-trading-bot
```

### **Paso 2: Instalar OpenClaw**

```bash
# Instalar OpenClaw globalmente
npm install -g openclaw

# Verificar instalación
openclaw --version  # Debe mostrar 2026.4.15+
```

### **Paso 3: Instalar Ollama**

```bash
# Instalar Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull del modelo Qwen 3.5
ollama pull qwen3.5:cloud

# Verificar
ollama list
```

### **Paso 4: Configurar Credenciales**

```bash
# Crear directorio de secrets
mkdir -p ~/.openclaw/secrets

# Configurar Binance API
cat > ~/.openclaw/secrets/binance.env << EOF
export BINANCE_API_KEY="tu_api_key_aqui"
export BINANCE_API_SECRET="tu_api_secret_aqui"
EOF

chmod 600 ~/.openclaw/secrets/binance.env

# Configurar GitHub (opcional, para push automático)
cat > ~/.openclaw/secrets/github.env << EOF
export GITHUB_TOKEN="ghp_tu_token_aqui"
EOF

chmod 600 ~/.openclaw/secrets/github.env
```

### **Paso 5: Configurar OpenClaw**

```bash
# Crear config de OpenClaw
mkdir -p ~/.openclaw

cat > ~/.openclaw/openclaw.json << EOF
{
  "models": {
    "default": "ollama/qwen3.5:cloud",
    "qwen": "ollama/qwen3.5:cloud"
  },
  "channels": {
    "telegram": {
      "botToken": "tu_bot_token",
      "chatId": "tu_chat_id",
      "streaming": {
        "mode": "partial"
      }
    }
  }
}
EOF
```

### **Paso 6: Configurar Cron Jobs**

```bash
# Abrir crontab
crontab -e

# Agregar jobs (ajustar ruta del workspace)
*/5 * * * * /home/overgon/.openclaw/workspace/auto-repair-states.sh
*/10 * * * * /home/overgon/.openclaw/workspace/auto-heal-monitor.sh
0 9 * * * /home/overgon/.openclaw/workspace/crypto-daily-report-v3.sh
```

### **Paso 7: Iniciar OpenClaw Gateway**

```bash
# Iniciar el gateway
openclaw gateway start

# Verificar status
openclaw gateway status
```

---

## ⚙️ **CONFIGURACIÓN**

### **Binance API**

1. Ir a https://www.binance.com/en/my/settings/api-management
2. Crear nueva API Key
3. **Permisos necesarios:**
   - ✅ Enable Reading
   - ✅ Enable Spot & Margin Trading
   - ❌ NO Enable Withdrawals (seguridad)
4. Guardar Key y Secret en `~/.openclaw/secrets/binance.env`

### **Telegram Bot**

1. Abrir Telegram y buscar `@BotFather`
2. Enviar `/newbot`
3. Seguir instrucciones para crear el bot
4. Obtener el token (ej: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Buscar `@userinfobot` para obtener tu Chat ID
6. Configurar en `~/.openclaw/openclaw.json`

### **Ollama + Qwen**

```bash
# Verificar Ollama corriendo
ollama list

# Si no está qwen3.5:cloud
ollama pull qwen3.5:cloud

# Testear
ollama run qwen3.5:cloud "Hola, cómo estás?"
```

---

## 📖 **USO**

### **Iniciar el Bot**

```bash
# Desde el workspace
cd /home/overgon/.openclaw/workspace

# El bot opera automáticamente vía OpenClaw
# Los scripts se ejecutan vía cron jobs
```

### **Ver Status**

```bash
# Status completo del sistema
./status-bot-full.sh

# Ver balances en Binance
./check-balances.sh

# Ver estado de slots
cat crypto-bots/*-trade-state.json | jq '.slots[] | {coin, status}'
```

### **Daily Report**

El reporte diario se envía automáticamente a las 9 AM vía Telegram.

Para generar manualmente:
```bash
./crypto-daily-report-v3.sh
```

---

## 📁 **ESTRUCTURA**

```
perrobotillo-trading-bot/
├── crypto-bots/
│   ├── BTC-bot.json              # Config BTC
│   ├── BTC-trade-state.json      # Estado slots BTC
│   ├── BTC-daily-pnl.json        # P&L diario BTC
│   └── [ETH, BNB, SOL, LINK, XRP, AVAX] (mismo patrón)
├── auto-repair-states.sh         # Auto-reset de slots
├── auto-heal-monitor.sh          # Health monitoring
├── emergency-close-all.sh        # Cierre de emergencia
├── crypto-trade-moneda-v3-slots.sh  # Bot principal
├── crypto-daily-report-v3.sh     # Reporte diario
├── check-balances.sh             # Verificación saldos
├── calculate-real-pnl.sh         # Cálculo P&L
├── PERROBOTILLO-CLONE-PROMPT.md  # Prompt para clonar
├── FASE1-V2-OPTIMIZADA.md        # Configuración
├── BUG-*.md                      # Bugs documentados
├── README.md                     # Este archivo
└── .gitignore                    # Git ignore
```

---

## 📊 **FASE 1 v2 CONFIGURACIÓN**

### **Parámetros Globales:**
```yaml
Trade Percent: 30% del balance por coin
TP3: 3.5% (optimizado para mayor win rate)
Acumulación: 5% (reinvertir ganancias)
Daily Loss Limit: 3% por coin
90/10 Rule: Máximo 10% USDT disponible
```

### **Take Profit Escalonado:**
```yaml
TP1: 1.5% → Vender 30% de la posición
TP2: 3.0% → Vender 30% de la posición
TP3: 3.5% → Vender 40% restante + acumular 5%
```

### **Stop Loss por Volatilidad:**
| Coin | Stop Loss | Razón |
|------|-----------|-------|
| BTC | 3.5% | Baja volatilidad |
| ETH | 4.5% | Volatilidad media |
| BNB | 3.5% | Baja volatilidad |
| SOL | 7.0% | Alta volatilidad |
| LINK | 5.5% | Volatilidad media-alta |
| XRP | 4.5% | Volatilidad media |
| AVAX | 6.0% | Alta volatilidad |

### **Trailing Stop:**
```yaml
Activación: Después de TP1
Breakeven: Inmediato después de TP1 hit
Trailing: 2% después de TP2 hit
```

---

## 🛠️ **COMANDOS ÚTILES**

### **Gestión del Bot:**
```bash
# Ver status completo
./status-bot-full.sh

# Ver balances
./check-balances.sh

# Calcular P&L realizado
./calculate-real-pnl.sh

# Resetear slot manual
./reset-trade-state.sh
```

### **Git:**
```bash
# Ver status del repo
git status

# Commit y push
git add .
git commit -m "Descripción del cambio"
git push origin master

# Ver historial
git log --oneline
```

### **OpenClaw:**
```bash
# Status del gateway
openclaw gateway status

# Reiniciar gateway
openclaw gateway restart

# Ver logs
openclaw gateway logs
```

### **Ollama:**
```bash
# Ver modelos instalados
ollama list

# Ver logs de Ollama
journalctl -u ollama -f
```

---

## 🔧 **TROUBLESHOOTING**

### **El bot no opera:**
```bash
# 1. Verificar OpenClaw
openclaw gateway status

# 2. Verificar API Binance
source ~/.openclaw/secrets/binance.env
curl -s "https://api.binance.com/api/v3/account" \
  -H "X-MBX-APIKEY: $BINANCE_API_KEY"

# 3. Verificar cron jobs
crontab -l

# 4. Verificar logs
tail -f /home/overgon/.openclaw/workspace/*.log
```

### **Auto-Repair no funciona:**
```bash
# Ejecutar manualmente
./auto-repair-states.sh

# Verificar cron
systemctl status cron
```

### **Telegram no envía notificaciones:**
```bash
# Verificar token y chat ID en openclaw.json
cat ~/.openclaw/openclaw.json | jq '.channels.telegram'

# Testear envío manual
curl -s "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>&text=Test"
```

### **Ollama no responde:**
```bash
# Reiniciar Ollama
sudo systemctl restart ollama

# Verificar modelo
ollama list

# Re-instalar modelo
ollama pull qwen3.5:cloud
```

---

## 🛡️ **SEGURIDAD**

### **NUNCA hacer:**
```bash
❌ Commitear archivos .env o secrets
❌ Compartir API keys en texto plano
❌ Dar permisos de withdrawal a la API
❌ Usar el bot en redes públicas sin VPN
```

### **SIEMPRE hacer:**
```bash
✅ Guardar secrets en ~/.openclaw/secrets/
✅ Usar chmod 600 para archivos sensibles
✅ Rotar API keys periódicamente
✅ Usar 2FA en Binance
✅ Mantener el sistema actualizado
✅ Backup periódico del workspace
```

### .gitignore:**
El repo incluye `.gitignore` que excluye:
- `*.env`
- `secrets/`
- `*.log`
- `*.backup`
- `.openclaw/`

---

## 📈 **MÉTRICAS Y KPIs**

### **Objetivos FASE 1 v2:**
```yaml
Win Rate TP3: 30-35% (vs 4.4% FASE 1 v1)
Ganancia/trade: $1.50-1.70 USDT
P&L mensual: $180-240 USDT
Mejora: +800% vs FASE 1 v1
```

### **Monitoreo Diario:**
- Win rate del día
- P&L realizado (USDT + MXN)
- Total de trades
- Slots activos vs disponibles
- Alertas de auto-repair

---

## 🤝 **CONTRIBUCIÓN**

1. Fork el repo
2. Crear branch (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Pull Request

---

## 📄 **LICENCIA**

Uso personal. No comercial.

---

## 🙏 **AGRADECIMIENTOS**

- **OpenClaw:** https://github.com/openclaw/openclaw
- **Ollama:** https://ollama.com
- **Qwen:** https://github.com/QwenLM/Qwen
- **Binance API:** https://binance.com
- **Telegram Bot API:** https://core.telegram.org/bots/api

---

## 📞 **SOPORTE**

- **Issues:** https://github.com/overgon/perrobotillo-trading-bot/issues
- **Discussions:** https://github.com/overgon/perrobotillo-trading-bot/discussions
- **Email:** perrobotillo@users.noreply.github.com

---

## 🎯 **ROADMAP**

### **FASE 2 (En desarrollo):**
- [ ] Filtros de entrada (RSI, volumen, tendencia)
- [ ] Machine Learning para predicción
- [ ] Backtesting automático
- [ ] Dashboard web

### **FASE 3 (Futuro):**
- [ ] Soporte para más exchanges
- [ ] Trading de futuros
- [ ] Estrategias personalizadas
- [ ] API pública

---

**🐕 Hecho con ❤️ por Perrobotillo Trading Bot**

*Última actualización: 2026-04-16 22:45 CST*
