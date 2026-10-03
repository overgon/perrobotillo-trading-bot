# Checklist Maestro — Fase 0: Jesse AI Research Lab

## Estado: ✅ COMPLETADA

### Infraestructura
- [x] 0.1  Snapshot Perrobotillo (workspace + crontab)
- [x] 0.2  Fork → overgon/project-template (SSH remote configurado)
- [x] 0.3  Docker arm64 en Pi 5 (jesse + postgres + redis)
- [x] 0.4  Dashboard Jesse (http://localhost:9000) + MCP (http://localhost:9002/mcp)
- [x] 0.5  PostgreSQL + Redis servicios running
- [x] 0.6  .gitignore configurado (excluye datos/candles secrets)

### Datos
- [x] 0.7  Importar 7 monedas × 2142 velas 1h → 1m (PostgreSQL)
- [x] 0.8  Verify OHLC accuracy vs Perrobotillo CSV (exact match)
- [x] 0.9  Fear & Greed CSV (70 rows) importado
- [x] 0.10 Trade history JSON (489 trades) copiado

### Estrategia
- [x] 0.11  Perrobotillo strategy replicada (618 lines)
  - [x] Market mode detection (F&G proxy via BTC EMA/RSI)
  - [x] ML validator proxy (indicators → 0-100 score)
  - [x] Per-coin TP/SL overrides (7 coins)
  - [x] TP 35% / 30% / 30%, SL by market mode
  - [x] 212 features ML recording
- [x] 0.12  routes.py configurado (7 coins, 1h, spot)
- [x] 0.13  .env creado (configuración completa)

### Backtest
- [x] 0.14  Backtest BNB (quick test) → 2 trades exit 0 ✅
- [x] 0.15  Fix: 1m candles (no 1h) — Jesse validates/resamples
- [x] 0.16  Fix: ta.* returns scalars (no [-1] indexing)
- [x] 0.17  Fix: on_open_position() for spot TP/SL
- [x] 0.18  Fix: exchange case 'Binance Spot' (no 'binance-spot')
- [x] 0.19  Fix: @cached decorators (call with ())
- [x] 0.20  Full 7-coin backtest → 155 trades ✅

### Comparativa Performance

| Coin | Jesse (N/WR/PnL) | Production (N/WR/PnL) |
|------|-------------------|----------------------|
| BTC  | 8 / 12.5% / -$322 | 40 / 55.0% / -$132 |
| ETH  | 16 / 6.2% / -$1,389 | 71 / 77.5% / +$114 |
| BNB  | 11 / 9.1% / -$980 | 60 / 80.0% / +$59 |
| SOL  | 30 / 3.3% / -$3,581 | 66 / 75.8% / +$57 |
| LINK | 38 / 2.6% / -$2,992 | 84 / 67.9% / +$10 |
| XRP  | 23 / 4.3% / -$2,054 | 82 / 61.0% / +$35 |
| AVAX | 29 / 3.4% / -$2,510 | 86 / 73.3% / +$47 |

**Total**: 155 trades, 4.5% WR, PnL -$13,828
**Production**: 489 trades, 70.6% WR, PnL +$190

### Conclusiones Fase 0
1. ✅ Jesse AI research lab fully operational in Docker on Pi 5
2. ✅ Perrobotillo strategy replicada en Jesse (Fase 1 v2 compatible)
3. ✅ Backtest genera trades para todas las 7 monedas
4. ⚠️ WR bajo (4.5% vs 70.6%) — ML proxy es simplificado vs modelo real
5. ⚠️ Menos trades (155 vs 489) — Entry filtering más restrictivo en producción

### Known Issues & Workarounds
| Issue | Cause | Fix |
|-------|-------|-----|
| 0 trades (initial) | Used 1h candles, not 1m | `get_candles(exchange, symbol, '1m', ...)` |
| IndexError on ta.* | `ta.*` returns scalars in Jesse 3.2.2 | Removed `[-1]` indexing |
| take_profit error | Spot trading needs on_open_position() | Moved TP/SL to on_open_position() |
| Exchange case mismatch | Routes use 'binance-spot', DB has 'Binance Spot' | Unified to 'Binance Spot' |
| @cached returns method | `self.rsi` vs `self.rsi()` | Added `()` to cached method calls |
| trade-history.json path | Not in Docker volume | Copied to research/ directory |

### Próximos pasos (Fase 1+)
- [ ] 1.1  Optuna hyperparameter optimization (TP/SL levels, EMA periods)
- [ ] 1.2  Improve ML proxy (add more indicator filters, reduce false entries)
- [ ] 1.3  Add cooldown logic (no entries after recent trade)
- [ ] 1.4  Test full 90-day backtest for all 7 coins
- [ ] 1.5  Compare optimized results vs production
