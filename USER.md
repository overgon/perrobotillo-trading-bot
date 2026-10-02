# USER.md - About Your Human

_Learn about the person you're helping. Update this as you go._

- **Name:** Rull Ox
- **What to call them:** Jefe
- **Pronouns:** _(optional)_
- **Timezone:** America/Mexico_City (CST)
- **Notes:** 

## Context

### 🎯 Proyectos
- **Perrobotillo Trading Bot** - Bot de trading automatizado para Binance
  - 7 monedas: BTC, ETH, BNB, SOL, LINK, XRP, AVAX
  - 21 slots (3 por moneda)
  - FASE 1 v2.1 optimizada
  - Daily loss limit: 3%

### 💡 Preferencias
- **Modo de trading:** Piloto automático
- **Motto:** "Nunca confiar, siempre verificar"
- **Comunicación:** Español
- **Vibe:** Directo, sin rodeos, competente

### 🛡️ Seguridad
- **IP Whitelist:** Binance (dinámica, puede cambiar)
- **API Keys:** Configuradas en secrets/binance.env
- **Monitor de IP:** Activo (hourly alerts)
- **Drawdown Alert:** Cada 30 min

### 😄 Lo que le gusta
- Trading automatizado
- Backtesting con datos reales
- Documentación clara de bugs
- Monitoreo proactivo
- Alertas en Telegram

### 👎 Lo que le molesta
- API keys expuestas
- IPs públicas en repositorios
- Bugs sin documentar
- Falsos positivos en emergency close
- Que el bot no verifique antes de actuar

### 📊 Status Actual
- **Sistema:** SLOTS TRADING BOT (7 monedas)
- **Portfolio:** ~$2,393 USDT
- **Slots activos:** 9/21 (BTC, ETH, BNB, SOL, LINK, XRP, AVAX)
- **Órdenes activas:** 9 posiciones LONG con TP1/TP2/TP3
- **P&L Hoy:** -$4.31 USDT (-0.18%) - normal por comisiones + SL recientes
- **Último rebalanceo:** 2026-06-16 00:19 AM (+$1,335 invertidos en ETH/BNB/SOL)

### 🎯 Sistema Actual
- **Grid Trading:** ❌ DESACTIVADO (desde Jun 2026)
- **Sistema de Slots:** ✅ ACTIVO - posiciones direccionales LONG con TP escalonados
- **Estrategia:** TP1 cobrado → espera TP2/TP3 o SL
- **Memory Search:** Automático cada 6 horas (solo alertas críticas)
- **Dashboard:** http://192.168.3.215:8080 con animaciones cyberpunk
- **API quota:** Optimizada (mínimo gasto innecesario)

### 🏠 Setup
- **Hardware:** Raspberry Pi 5 (192.168.3.215)
- **OpenClaw:** Gateway + Ollama + Qwen 3.5
- **Channel:** Telegram
- **Avatar:** Cyberpunk dog con lentes de trading

---

## 🧠 Memory Notes

- Revisar daily report a las 9 AM
- Monitorear Binance maintenance announcements (manual)
- IP pública puede cambiar (dinámica)
- Nunca exponer credenciales en GitHub
- Validar portfolio antes de emergency close

---

_The more you know, the better you can help. But remember — you're learning about a person, not building a dossier. Respect the difference._
