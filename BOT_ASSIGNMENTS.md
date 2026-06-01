# 🤖 BOT ASSIGNMENTS - Asignación de Monedas

_Última actualización: 2026-05-31 17:40 CST_

---

## 📊 Asignación Oficial

Para evitar conflictos de capital y operaciones cruzadas, cada bot opera monedas específicas.

---

## 🎯 Bot Principal (Trend + ML Validator)

**Script:** `crypto-trade-moneda-v3-slots.sh`  
**Estrategia:** Trend Following con validación ML  
**Timeframe:** Horas a días (swing trading)

### Monedas Asignadas:
| Coin | Pairs | Slots | Capital Aprox | Status |
|------|-------|-------|---------------|--------|
| **BTC** | BTCUSDT | 3 | $150 | ✅ Activo |
| **ETH** | ETHUSDT | 3 | $150 | ✅ Activo |
| **SOL** | SOLUSDT | 3 | $100 | ✅ Activo |
| **LINK** | LINKUSDT | 3 | $100 | ✅ Activo |

**Capital Total:** ~$500 USDT  
**Trades Activos:** 15 (todos en profit +2-3%)  
**Daily Loss Limit:** 3% ($15 máximo)

### Características:
- ✅ ML Validator obligatorio pre-trade
- ✅ Stop Loss / Take Profit dinámicos
- ✅ BTC Trend Filter (evita operar contra tendencia mayor)
- ✅ 3 slots por moneda (DCA automático)
- ✅ Trailing stop dinámico

---

## 🕸️ Grid Trading Bot (Lateral Markets)

**Script:** `grid-trading-bot.py`  
**Estrategia:** Grid Trading (compra/vende en rangos)  
**Timeframe:** Minutos a horas

### Monedas Asignadas:
| Coin | Pairs | Grid Range | Capital | Status |
|------|-------|------------|---------|--------|
| **BNB** | BNBUSDT | $650-$800 | $100 | ⏸️ Pendiente fondeo |
| **XRP** | XRPUSDT | $1.20-$1.50 | $100 | ⏸️ Pendiente fondeo |
| **AVAX** | AVAXUSDT | $8-$10 | $100 | ⏸️ Pendiente fondeo |

**Capital Total:** $300 USDT  
**Trades Activos:** 0 (esperando fondeo)  
**Daily Loss Limit:** 3% ($9 máximo)

### Características:
- ✅ 15 niveles de compra/venta por grid
- ✅ Opera 24/7 automáticamente
- ✅ Ideal para mercados laterales
- ✅ Múltiples trades pequeños por día
- ✅ Paper Trading disponible para testing

---

## 🚫 Monedas NO Operadas (por ahora)

| Coin | Razón | Futuro |
|------|-------|--------|
| **DOGE** | Muy volátil, meme coin | ❌ No planeado |
| **ADA** | Baja prioridad | ⏳ Evaluar después |
| **MATIC** | Similar a AVAX | ⏳ Evaluar después |

---

## 📋 Reglas de Operación

### 1. **Sin Superposición**
- Cada moneda opera en UN solo bot
- No hay competencia por capital
- Fácil medir performance individual

### 2. **Capital Separado**
```
Binance Account:
├── Bot Principal: $500 USDT (BTC, ETH, SOL, LINK)
└── Grid Bot: $300 USDT (BNB, XRP, AVAX)
    └── Total recomendado: $800 USDT
```

### 3. **Monitoreo Independiente**
- Bot Principal: Reports diario/semanal/mensual
- Grid Bot: Reports separado (logs en `logs/grid-*.log`)

### 4. **Emergency Close por Bot**
- Si Bot Principal tiene issues → cerrar solo ese bot
- Si Grid Bot tiene issues → cerrar solo ese bot
- El otro bot continúa operando normalmente

---

## 📊 Performance Tracking

### Bot Principal (Último reporte):
- **P&L 24h:** +$10.50 USDT (+2.14%)
- **Trades Activos:** 15 (todos profit)
- **Win Rate:** 100% (trades abiertos)
- **SOL en TP1:** Esperando cierre automático

### Grid Bot (Paper Trading):
- **Test BNB:** 1 hora, 0 trades, 0 pérdidas
- **Precio BNB:** $710 (rango medio $650-800)
- **Status:** Validado, listo para live

---

## 🔧 Comandos por Bot

### Bot Principal:
```bash
# Iniciar todas las monedas
./crypto-trade-moneda-v3-slots.sh --start

# Ver status
./crypto-trade-moneda-v3-slots.sh --status

# Emergency close
./crypto-trade-moneda-v3-slots.sh --emergency-close

# Daily report
./crypto-bots/daily-report.sh
```

### Grid Bot:
```bash
# Iniciar para una moneda específica
./crypto-bots/run-grid-bot.sh BNB 24

# Iniciar para todas las monedas asignadas
./crypto-bots/run-grid-bot.sh BNB,XRP,AVAX 24

# Paper trading (testing sin dinero real)
./crypto-bots/run-grid-bot.sh BNB 1 --dry-run

# Ver logs
tail -f logs/grid-BNB.log
```

---

## ⚠️ IMPORTANTE

### Antes de Operar:
1. ✅ Verificar saldo USDT en Binance (mínimo $800 total)
2. ✅ Confirmar IP whitelist activa
3. ✅ API keys con permisos correctos (Spot Trading)
4. ✅ Monitorear primeras 2 horas después de iniciar

### Durante Operación:
- 📱 Alerts Telegram cada 30 min (drawdown)
- 📊 Daily report 9:00 AM CST
- 🛑 Stop automático si daily loss > 3%

### En Caso de Problemas:
```bash
# Emergency close Bot Principal
./crypto-trade-moneda-v3-slots.sh --emergency-close

# Emergency close Grid Bot
pkill -f grid-trading-bot.py

# Ver status de todos los procesos
ps aux | grep -E "(crypto-trade|grid-trading)" | grep -v grep
```

---

## 📈 Roadmap

### Semana 1 (31 May - 6 Jun):
- ✅ Asignación completada
- ⏳ Fondear Grid Bot ($300 USDT)
- ⏳ Monitorear performance separada
- 📊 Primer reporte comparativo (7 Jun)

### Semana 2-3:
- Evaluar ajustes de configuración
- Optimizar grid ranges si es necesario
- Considerar expansión a más monedas

### Mes 2:
- Review completo de performance
- Decidir si mantener separación o integrar
- Potencial aumento de capital si profitable

---

_Generado por Perrobotillo Trading Bot 🐕_  
*"¡Nunca confiar, siempre verificar!"*_
