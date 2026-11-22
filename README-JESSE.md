# 🐕 Jesse AI — Perrobotillo Trading Bot Integration

## 📖 Panorama
Jesse AI se integra en Perrobotillo como **laboratorio de investigación offline** (Issue #44, Issue #62). Permite:
- **Backtest** estrategias con multi-timeframe (1m → 1D)
- **ML Pipeline end-to-end** (gather → train → deploy)
- **Optuna** para optimización de parámetros
- **Monte Carlo** para detectar overfitting/luck

## 🏗️ Arquitectura
```
┌─────────────────────────────────────────┐
│  🌐 Dashboard: http://localhost:9000     │
│  📊 MCP Server: /mcp  (auth Bearer)     │
└─────────────────────────────────────────┘
        ▲                    ▲
        │ jesse run          │ PostgreSQL 17
        ▼                    ▼
   venv-jesse/             jesse_db (jesse_user)
   Python 3.13              (superuser)
```

## 🚀 Inicio Rápido
```bash
# 1. Ir al directorio
cd /home/overgon/work/perrobotillo-trading-bot

# 2. Activar entorno
source venv-jesse/bin/activate

# 3. Iniciar Jesse
jesse run &

# 4. Verificar
curl http://localhost:9000/  # → HTML (auth requerido)
```

## 📊 Trading Configuración
- **Símbolos:** BTC-USDT, ETH-USDT, BNB-USDT, SOL-USDT, LINK-USDT, XRP-USDT, AVAX-USDT
- **Exchange:** Binance Spot
- **Timeframes:** 1m, 5m, 15m, 1h, 4h, 1D
- **Modo:** BACKTEST (debug luego en LIVE/PAPER)

## 🔗 Integración con Perrobotillo
La estrategia `strategies/perrobotillo/perrobotillo.py` replica la lógica de producción:
- Detección de mercado (BULL, BEAR, LATERAL, VOLATILE_BULL, VOLATILE_BEAR, LATERAL_BULL)
- ML mode: `before()` guarda features, `after()` etiqueta velas
- Entrada/Salida: TP1/TP2/TP3 + SL dinámico + overrides por moneda

## 📝 Comandos Útiles
| Comando | Descripción |
|---------|-------------|
| `jesse run` | Inicia dashboard + MCP |
| `jesse import-candles binance-spot BTC-USDT 2024-01-01` | Import de velas |
| `mvn test` | Ejecutar backtest (desde dashboard) |
| `tail -f logs/jesse-*.log` | Ver logs |

## 🐛 Troubleshooting
| Error | Solución |
|-------|----------|
| `password auth failed` | `ALTER USER jesse_user WITH SUPERUSER;` |
| `permission denied for schema public` | `GRANT ALL ON SCHEMA public TO jesse_user;` |
| `jesse run` no arranca | Verificar `.env` (`POSTGRES_HOST=localhost`, `PASSWORD=***`) |

---
_Modificado por: Perrobotron Aterrorizar!! — 2026-11-17_
_"_Nunca confiar, siempre verificar._"_
