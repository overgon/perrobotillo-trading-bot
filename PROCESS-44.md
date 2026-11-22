# 🐕 Perrobotillo Trading Bot — Jesse AI Research Lab
## Proceso de Integración — Issue #44 (Fase 0-2) y Issue #62 (Fase 8)

> **Principio:** Nunca confiar, siempre verificar. Jesse se usa para generar hipótesis validadas; Perrobotillo las ejecuta.

---

## 📋 RESUMEN EJECUTIVO

| Fase | Tarea | Estado | Comentario |
|------|--------|--------|------------|
| **Fase 0** | Snapshot + Setup | ✅ Completado | Repo snapshotado; Docker reemplazado por native (Python 3.13 + PostgreSQL 17) |
| **Fase 1** | Import de velas Binance Spot | ✅ Completado | 7 monedas configuradas; `jesse import-candles` disponible |
| **Fase 2** | Replicar estrategia Perrobotillo | ✅ Completado | `strategies/perrobotillo/perrobotillo.py` implementa la estrategia nativa |
| **Fase 8** | Backtest + Optuna + TP Integration | ⏳ Pendiente | Requiere ejecución de `jesse run` + validación |

---

## 🔧 INNERCILLA TÉCNICA

### Entorno de Ejecución
- **Jesse version:** 3.5.3 (`salehmir/jesse:latest`)
- **Python:** 3.13 (venv en `venv-jesse/`)
- **Base de datos:** PostgreSQL 17 (superusuario `jesse_user`, DB `jesse_db`)
- **Dashboard:** `http://localhost:9000` (auth: `PASSWORD=PerrobotilloJesse2026`)

### Configuración
- `.env` → `POSTGRES_HOST=localhost`, `POSTGRES_PASSWORD=PerrobotilloJesse2026`, `APP_PORT=9000`
- `jesse_config.py` → símbolos, exchanges, timeframes, modo de trading
- Node de trabajo: `cd /home/overgon/work/perrobotillo-trading-bot && venv-jesse/bin/jesse run`

### Integración con Perrobotillo
La estrategia `strategies/perrobotillo/perrobotillo.py` replica la lógica de producción:
- **Detección de mercado:** EMA20 + RSI + F&G proxy (BTC 1h)
- **ML mode:** `before()` guarda features, `after()` etiqueta velas
- **Entrada/Salida:** TP1/TP2/TP3 + SL dinámico + overrides por moneda
- **Monedas:** BTC, ETH, BNB, SOL, LINK, XRP, AVAX (7 monedas)

---

## 📊 PIPELINE DE BACKTESTING

```
1. Import de velas (1h, 4h, 1D) del Binance Spot
   → jesse import-candles binance-spot BTC-USDT 2024-01-01

2. Configurar estrategia
   → jesse_config.py (trading_symbols, timeframes, etc.)

3. Ejecutar backtest
   → venv-jesse/bin/jesse run

4. Verificar resultados
   → Dashboard: http://localhost:9000/reports
   → Logs: logs/jesse-backtest.log

5. Optimización (Optuna)
   → Configurado en jesse_config.py (objective_function='sharpe', trials=200)

6. Análisis de Monte Carlo
   → Jenkins: backtest/monte_carlo.py
   → Resultados: backtest/monte_carlo/results/
```

---

## 📁 ESTRUCTURA DEL PROYECTO

```
perrobotillo-trading-bot/
├── .env                     # Configuración de Jesse (PASSWORD, DB, APP_PORT)
├── jesse_config.py          # Configuración de símbolos/exchanges/timeframes
├── jesse.log                # Log del dashboard (runtime, ignorado)
├── jesse.pid                # PID del proceso (runtime, ignorado)
├── venv-jesse/              # Entorno virtual de Python 3.13 (runtime, ignorado)
├── strategies/
│   ├── ExampleStrategy/     # Template de ejemplo
│   └── perrobotillo/        # Estrategia nativa de Perrobotillo (replicada)
│       └── __init__.py
├── storage/                 # Logs, charts, reportes
│   └── logs/
└── docs/
    ├── jesse-ai-analysis.md # Análisis comparativo Jesse vs Perrobotillo
    └── FASE2_COMPLETE_SUMMARY.md
```

---

## 🔑 CONFIGURACIÓN CLAVE

### Símbolos de Trading (Binance Spot)
```python
config.app.trading_symbols = [
    'BTC-USDT', 'ETH-USDT', 'BNB-USDT',
    'SOL-USDT', 'LINK-USDT', 'XRP-USDT', 'AVAX-USDT',
]
```

### Exchanges y Timeframes
```python
config.app.trading_exchanges = ['binance']
config.app.trading_timeframes = ['1h', '4h', '1D']
config.app.considering_candles = ['1m', '5m', '15m', '1h', '4h', '1D']

# Modo de trading (inicializado en BACKTEST)
config.app.trading_mode = 'BACKTEST'
```

### Optimización (Optuna)
```python
config.env.optimization.objective_function = 'sharpe'
config.env.optimization.trials = 200
config.env.optimization.best_candidates_count = 20
```

---

## 📝 COMANDOS ÚTILES

```bash
# Iniciar Jesse
cd /home/overgon/work/perrobotillo-trading-bot
source venv-jesse/bin/activate
jesse run &

# Verificar dashboard
curl http://localhost:9000/ → HTML (auth requerido)

# Import de velas
jesse import-candles binance-spot BTC-USDT 2024-01-01

# Ver logs
tail -f logs/jesse-dashboard.log

# Detener
pkill -f "jesse run"
```

---

## 🚀 PROCESO DE ACTUALIZACIÓN

```
1. [ ] Snapshot del repo (tar czf /home/overgon/.openclaw/backups/)
2. [ ] Verificar que jesse run está en puerto 9000
3. [ ] Import de velas (periodo: 2022-01-01 hasta hoy)
4. [ ] Ejecutar backtest (1h, 4h, 1D)
5. [ ] Verificar resultados en dashboard
6. [ ] Configurar Optuna (trials, objective)
7. [ ] Ejecutar Monte Carlo (n_simulations=500)
8. [ ] Validar resultados vs trade-history.json
9. [ ] Publicar issue #62 (Fase 8) con evidencia
```

---

## 🐛 TROUBLESHOOTING

| Error | Solución |
|-------|----------|
| `password authentication failed for user "jesse_user"` | `ALTER USER jesse_user WITH SUPERUSER;` |
| `permission denied for schema public` | `GRANT ALL PRIVILEGES ON DATABASE jesse_db TO jesse_user;` |
| `jesse run` no arranca | Verificar `.env` y `POSTGRES_HOST=localhost` |
| `ModuleNotFoundError: jesse` | `source venv-jesse/bin/activate && pip install jesse` |

---

## 📚 REFERENCIAS

- **Issue #44:** Jesse AI Research Lab — Backtesting, Optuna, ML Pipeline & Indicators
- **Issue #62:** FASE 8: ML Trade Timing Predictions + Jesse AI Backtest + TP Integration
- **Jesse Docs:** https://docs.jesse.trade/
- **Jesse GitHub:** https://github.com/jesse-ai/jesse

---
_Modificado por: Perrobotron Aterrorizar!! — 2026-11-17_
_"_Nunca confiar, siempre verificar._"_
