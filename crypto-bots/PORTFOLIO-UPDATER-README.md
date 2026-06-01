# 💰 Portfolio Updater - Fix Permanente

## 🐛 Problema Original

El dashboard mostraba **$0** porque:
1. El archivo `portfolio-snapshot.json` tenia valor 0
2. El dashboard no podia conectar a Binance API (bug en la ruta de `binance.env`)
3. No habia actualizacion automatica del portfolio

## ✅ Solucion Implementada

### 1. **Fix en `dashboard/app.py`**
- Corregido bug: `$HOME` → `os.path.expanduser("~/.openclaw/secrets/binance.env")`
- Cache aumentado: 30 segundos → **10 minutos** (600 segundos)
- Ahora el dashboard consulta Binance directamente si el cache expira

### 2. **Script `update-portfolio.sh`**
- Actualiza el portfolio desde Binance API cada 10 minutos
- Guarda cache en `/tmp/portfolio_cache.json`
- Logs en `/home/overgon/.openclaw/logs/portfolio-updater.log`
- Incluye desglose de holdings por moneda

### 3. **Cron Job**
```bash
*/10 * * * * /home/overgon/.openclaw/workspace/crypto-bots/update-portfolio.sh
```
- Ejecuta cada 10 minutos
- Mantiene el cache siempre actualizado
- Reduce llamadas a Binance API (rate limit friendly)

## 🔧 Comandos Utiles

### Verificar estado actual:
```bash
# Ver cache actual
cat /tmp/portfolio_cache.json | python3 -m json.tool

# Ver ultima ejecucion del script
tail -20 /home/overgon/.openclaw/logs/portfolio-updater.log

# Ejecutar manualmente
/home/overgon/.openclaw/workspace/crypto-bots/update-portfolio.sh

# Ver cron jobs
crontab -l | grep portfolio
```

### Forzar actualizacion:
```bash
rm /tmp/portfolio_cache.json
/home/overgon/.openclaw/workspace/crypto-bots/update-portfolio.sh
```

## 📊 Flujo de Actualizacion

```
┌─────────────────────────────────────────────────────────┐
│  Dashboard solicita /api/portfolio                      │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  1. Checa cache (/tmp/portfolio_cache.json)             │
│     - Si edad < 10 min → Retorna cache                  │
│     - Si edad >= 10 min → Actualiza desde Binance       │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  2. Cron job actualiza cache cada 10 min                │
│     - Lee balances de Binance API                       │
│     - Calcula valor total en USDT                       │
│     - Guarda en /tmp/portfolio_cache.json               │
└─────────────────────────────────────────────────────────┘
```

## 🎯 Resultado

- ✅ Dashboard muestra valor **real y actualizado** desde Binance
- ✅ **Tipo de cambio MXN en tiempo real** desde Binance (USDTMXN)
- ✅ Actualizacion automatica cada **10 minutos**
- ✅ Fallback a snapshot si Binance falla
- ✅ Logs completos para debugging
- ✅ Rate-limit friendly (6 llamadas/hora max)

### API Response:
```json
{
  "value": 2597.25,
  "value_mx": 45140.2,
  "mxn_rate": 17.38,
  "timestamp": "2026-05-30T00:33:59.353486"
}
```

---

_Implementado: 2026-05-30 00:24 CST_
_Perrobotillo Trading Bot Team 🐕_
