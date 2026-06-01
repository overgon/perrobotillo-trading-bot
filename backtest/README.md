# 🐕 Perrobotillo Backtest Engine

## Descripción

Motor de backtesting inspirado en Freqtrade pero mejorado para nuestro setup específico.

## Features Implementadas

### ✅ Fase 1: Backtesting Básico (COMPLETADO)
- **simple_backtest.py**: Backtest usando logs históricos reales
- Métricas completas: Win Rate, P&L, Drawdown, Profit Factor, Sharpe
- Reportes en Markdown y JSON
- Soporte para todas las 7 monedas

### 🔄 Fase 2: Backtesting Avanzado (EN PROGRESO)
- **backtest_engine.py**: Motor completo con descarga de Binance
- 27 indicadores técnicos
- Estrategias personalizables
- Datos OHLCV históricos

## Uso Rápido

### Backtest con datos históricos (RECOMENDADO)

```bash
# Todas las monedas (últimos 30 días)
python3 backtest/simple_backtest.py --all 30

# Moneda específica
python3 backtest/simple_backtest.py BTC 60
```

### Backtest con datos de Binance (EXPERIMENTAL)

```bash
# Todas las monedas
python3 backtest/backtest_engine.py --all --timeframe 5m --days 30

# Moneda específica
python3 backtest/backtest_engine.py --coin BTC --timeframe 1h --days 60
```

## Resultados Recientes (30 días)

| Coin | Trades | Win Rate | P&L | Profit Factor |
|------|--------|----------|-----|---------------|
| BNB | 60 | 96.67% | +$131.75 | 38.64 |
| XRP | 33 | 72.73% | +$40.75 | 3.59 |
| AVAX | 42 | 71.43% | +$42.75 | 3.04 |
| SOL | 38 | 60.53% | +$40.50 | 2.54 |
| BTC | 10 | 50.00% | +$2.75 | 1.31 |
| ETH | 29 | 48.28% | +$8.50 | 1.32 |
| LINK | 89 | 34.83% | -$40.50 | 0.60 |

**TOTAL:** 301 trades, 61.46% win rate, +$226.5 USDT

## Reportes Generados

Los reportes se guardan en:
- `/home/overgon/.openclaw/workspace/backtest/reports/`
- Formato: `backtest_<COIN>_<DAYS>d.md` y `.json`

## Próximas Mejoras

### Feature Engineering (Esta semana)
- [ ] 100+ features automáticas
- [ ] Lag features
- [ ] Rolling statistics
- [ ] Correlaciones entre monedas

### Hyperopt (Este fin de semana)
- [ ] Búsqueda automática de mejores SL/TP
- [ ] Optimización de parámetros
- [ ] Walk-forward validation

---

🐕 Perrobotillo Trading Bot  
*"¡Nunca confiar, siempre verificar!"*
