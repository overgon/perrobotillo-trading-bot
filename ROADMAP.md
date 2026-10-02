# 🗺️ Perrobotillo Trading Bot - ROADMAP

**Última actualización:** 2026-05-16  
**Versión actual:** FASE 2 v2.2

---

## ✅ FASE 1 - LONG Only + ML TP Prediction (COMPLETADA - 2026-05-13)

### Objetivos
- [x] Bot de trading LONG only funcional
- [x] Multi-slot (3 por moneda, 21 total)
- [x] ML para predicción de TP

### Features Implementadas
- ✅ Trading LONG en 7 coins (BTC, ETH, BNB, SOL, LINK, XRP, AVAX)
- ✅ 3 slots por moneda (21 total)
- ✅ TP1/TP2/TP3 con porcentajes dinámicos
- ✅ Stop Loss automático
- ✅ Dashboard web en tiempo real
- ✅ TP Monitor (detección 30s)
- ✅ Auto-Adjust Strategy (cada 6h)
- ✅ Auto Capital Manager (9 AM diario)
- ✅ Watchdog con alertas Telegram
- ✅ Housekeeping automático
- ✅ **ML TP Prediction (LightGBM)**
  - Accuracy: 79-90%
  - 22 features (RSI, MACD, BB, volatilidad)
  - Auto-retrain semanal
  - Inferencia \u003c 1 segundo

### Resultados
- **Win rate:** 100% (62+ trades reales)
- **P&L:** +$200+ USDT
- **Backtest 6 años:** 45-50% win rate esperado

---

## ✅ FASE 2 - ML Drawdown Predictor + Anti-Spam (COMPLETADA - 2026-05-16)

### Objetivos
- [x] ML para predecir rachas de pérdidas
- [x] Pausa automática en drawdowns críticos
- [x] Sistema anti-spam de notificaciones
- [x] Dashboard sincronizado con estado real

### Features Implementadas
- ✅ **ML Drawdown Predictor v2.0**
  - Entrenado con 14,498 trades (6 años)
  - Incluye COVID crash (2020), FTX collapse (2022)
  - Accuracy: 76.31% (vs 64% anterior)
  - HIGH_RISK samples: 6,517 (45% del dataset)
  
- ✅ **Sistema Híbrido de Protección**
  - Reglas hard-coded (emergencia)
  - ML Random Forest (v2.0)
  - Loss Rate \u003e80% → PAUSE
  - Loss Streak \u003e5 → PAUSE
  - Drawdown \u003e$50 → PAUSE

- ✅ **Anti-Spam de Notificaciones**
  - Flag files por moneda
  - 1 notificación por evento
  - Notifica al reanudar

- ✅ **Dashboard Fixes**
  - Parser de dynamic-config.env
  - MARKET_MODE sincronizado (BEAR/LATERAL)

- ✅ **Reporte Diario Optimizado**
  - Formato Telegram sin asteriscos
  - Notificaciones sin duplicados

### Resultados
- **12 SLs evitados** (2026-05-16)
- **Pérdidas prevenidas:** ~$70 USDT
- **ML accuracy:** +12% vs modelo anterior

---

## 🚧 FASE 2.5 - Pipeline ML + Coin Ranking (Q3 2026)

### Objetivos
- Pipeline de re-entrenamiento automático
- ML para ranking de coins
- Mejoras de seguridad

### Features Planeadas

#### 1. Pipeline de Re-entrenamiento ML
- [ ] Re-entrenamiento mensual (día 1, 3 AM)
- [ ] Validación de accuracy antes de deploy
- [ ] Rollback automático si accuracy \u003c 70%
- [ ] Model registry con versionado
- [ ] Alertas de degradation

**Implementación:**
```yaml
Frecuencia: Mensual
Data: 70% histórico + 30% producción
Validación: Accuracy ≥ 75%
Backup: 3 versiones anteriores
```

#### 2. ML Coin Ranking (80/20)
- [ ] Ranking simple de coins
- [ ] Performance histórico por coin
- [ ] Volatilidad actual + volume relativo
- [ ] Correlación entre coins
- [ ] Sugerir coins a pausar
- [ ] Balanceo automático de portfolio

**Features:**
- Win rate por coin (24h, 7d, 30d)
- Volatilidad (ATR, std dev)
- Volume relativo vs promedio
- Correlación BTC/ETH
- Score compuesto (0-100)

#### 3. Mejoras de Seguridad
- [ ] Emergency Stop con confirmación
- [ ] Circuit breaker automático
- [ ] Alertas de anomalías en tiempo real
- [ ] Monitoreo de latency de Binance API
- [ ] Detección de fallos de conexión

### Timeline
- **Pipeline ML:** Junio 2026
- **Coin Ranking:** Julio 2026
- **Security Enhancements:** Agosto 2026

### Métricas de Éxito
- ML accuracy se mantiene ≥75%
- Coin ranking mejora win rate a 55%+
- 0 falsos positivos en circuit breaker

---

## 🔮 FASE 3 - Estrategias Avanzadas (Q4 2026 / Q1 2027)

### Objetivos
- Estrategias multi-timeframe
- Portfolio rebalancing automático
- ML avanzado (LSTM, Ensemble)
- Dashboard Pro
- API REST

### Features Planeadas

#### 1. Estrategias Multi-Timeframe
- [ ] Análisis 1h + 4h + 1d simultáneo
- [ ] Detección de divergencias (RSI, MACD)
- [ ] Confirmación de tendencias
- [ ] Detección de reversales
- [ ] Adaptive TP/SL basado en timeframe

**Implementación:**
- 1h para entry timing
- 4h para trend confirmation
- 1d para bias direccional
- Score ponderado (40% 1h, 40% 4h, 20% 1d)

#### 2. Portfolio Rebalancing Automático
- [ ] Rebalanceo semanal/mensual
- [ ] Optimización de correlaciones
- [ ] Take profit automático a USDT
- [ ] Re-asignación de capital
- [ ] Tax harvesting (pérdidas fiscales)

**Estrategia:**
- Target allocation por coin
- Rebalancear si desviación \u003e10%
- Rotar a USDT en bear market
- Compounding automático

#### 3. ML Avanzado
- [ ] LSTM para predicción de series temporales
- [ ] Ensemble de múltiples modelos (LightGBM + RF + LSTM)
- [ ] Feature engineering automático (AutoML)
- [ ] Detección de regime de mercado (HMM)
- [ ] Transfer learning de otros exchanges

**Modelos:**
- LSTM: Predicción de precio (next 10 velas)
- Ensemble: Voting classifier (3+ modelos)
- HMM: Bull/Bear/Lateral detection
- Autoencoder: Detección de anomalías

#### 4. Dashboard Pro
- [ ] Gráficos en vivo (Chart.js o TradingView)
- [ ] Backtesting on-demand
- [ ] Simulación de estrategias
- [ ] Mobile responsive
- [ ] Export de datos (CSV, JSON)
- [ ] P&L histórico con gráficos

**Features:**
- Velas japonesas en tiempo real
- Indicadores técnicos (RSI, MACD, BB)
- Backtest con parámetros custom
- Compare strategies
- Download reports

#### 5. API REST
- [ ] Control externo del bot
- [ ] Webhooks para integraciones
- [ ] Export de datos en tiempo real
- [ ] Autenticación (JWT, API keys)
- [ ] Rate limiting
- [ ] Swagger/OpenAPI docs

**Endpoints:**
- `GET /status` - Estado del bot
- `GET /positions` - Trades activos
- `POST /pause` - Pausar trading
- `POST /resume` - Reanudar trading
- `GET /pnl` - P&L histórico
- `WS /live` - WebSocket para datos en vivo

#### 6. Notificaciones Inteligentes
- [ ] Resumen diario por email
- [ ] Alertas SMS para eventos críticos
- [ ] Integración con Discord/Slack
- [ ] Notificaciones push (mobile)
- [ ] Customización de alertas

### Timeline
- **Multi-Timeframe:** Octubre 2026
- **Rebalancing:** Noviembre 2026
- **ML Avanzado:** Diciembre 2026
- **Dashboard Pro:** Enero 2027
- **API REST:** Febrero 2027

### Métricas de Éxito
- Win rate ≥60% con multi-timeframe
- Sharpe ratio \u003e1.5 con rebalancing
- ML ensemble accuracy ≥80%
- Dashboard load time \u003c2s
- API latency \u003c100ms

---

## 🎯 METAS A LARGO PLAZO (2027+)

### FASE 4 - Autonomía Total
- [ ] Bot 100% autónomo (sin intervención humana)
- [ ] Auto-optimización de parámetros
- [ ] Detección de bugs y auto-fix
- [ ] Multi-exchange (Binance, KuCoin, Bybit)
- [ ] Arbitraje entre exchanges

### FASE 5 - Social Trading
- [ ] Copy trading (seguir traders exitosos)
- [ ] Leaderboard público
- [ ] Signals para otros usuarios
- [ ] API pública para developers
- [ ] Marketplace de estrategias

### FASE 6 - Institucional
- [ ] Compliance regulatorio
- [ ] Auditorías de seguridad
- [ ] Insurance fund
- [ ] Multi-currency (USD, EUR, MXN)
- [ ] Reporting fiscal automático

---

## 📊 MÉTRICAS DE PROGRESO

### Actuales (2026-05-16)
| Métrica | Valor | Target FASE 3 |
|---------|-------|---------------|
| **Win Rate** | 100% (62 trades) | 60%+ |
| **P&L Total** | +$200+ USDT | +$1000+ USDT |
| **ML Accuracy (TP)** | 79-90% | 85%+ |
| **ML Accuracy (Drawdown)** | 76% | 80%+ |
| **Trades/Mes** | ~40 | 100+ |
| **Sharpe Ratio** | N/A | \u003e1.5 |
| **Max Drawdown** | -$70 USDT | \u003c-$100 USDT |
| **Uptime** | 99%+ | 99.9%+ |

### Progreso por FASE
- **FASE 1:** 100% ✅
- **FASE 2:** 100% ✅
- **FASE 2.5:** 0% 🚧
- **FASE 3:** 0% 🔮

---

## 🔄 PROCESO DE DESARROLLO

### Sprint Planning
- **Duración:** 2 semanas
- **Planning:** Lunes semana 1
- **Review:** Viernes semana 2
- **Retro:** Después del review

### Git Workflow
- `main` - Producción (stable)
- `develop` - Desarrollo (integration)
- `feature/*` - Features nuevas
- `hotfix/*` - Fixes críticos

### Testing
- Unit tests para funciones críticas
- Integration tests para APIs
- Backtesting antes de deploy
- Paper trading para validación

### Deployment
- CI/CD con GitHub Actions
- Auto-deploy a production en merge a `main`
- Rollback automático si tests fallan

---

## 📝 CHANGELOG

### v2.2 (2026-05-16) - FASE 2 COMPLETADA
- ✅ ML Drawdown Predictor con 14,498 trades históricos
- ✅ Sistema híbrido (Reglas + ML)
- ✅ Anti-spam de notificaciones
- ✅ Dashboard MARKET_MODE sync fix
- ✅ Reporte diario sin asteriscos
- ✅ Notificaciones de orden sin duplicados

### v2.1 (2026-05-13) - FASE 1 COMPLETADA
- ✅ ML TP Prediction (LightGBM)
- ✅ Auto-Adjust Strategy
- ✅ Auto Capital Manager
- ✅ Dashboard web
- ✅ TP Monitor

### v2.0 (2026-05-01) - Multi-Slot
- ✅ 3 slots por moneda
- ✅ 21 slots total
- ✅ Trailing stop
- ✅ TP Monitor

### v1.0 (2026-04-23) - Initial Release
- ✅ Trading LONG basic
- ✅ TP/SL fijos
- ✅ Binance integration

---

<div align="center">

**🐕 Perrobotillo Trading Bot** - *"Nunca confiar, siempre verificar"*

[GitHub](https://github.com/overgon/perrobotillo-trading-bot) | [Docs](https://docs.openclaw.ai)

</div>
