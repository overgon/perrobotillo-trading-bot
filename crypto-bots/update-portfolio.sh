#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - Portfolio Updater
# ════════════════════════════════════════════════════════
# Actualiza el portfolio desde Binance API cada 10 min
# Se ejecuta via cron: */10 * * * * /home/overgon/.openclaw/workspace/crypto-bots/update-portfolio.sh

set -e

WORKSPACE="$HOME/.openclaw/workspace"
SECRETS_FILE="$HOME/.openclaw/secrets/binance.env"
CACHE_FILE="/tmp/portfolio_cache.json"
LOG_FILE="$HOME/.openclaw/logs/portfolio-updater.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🔄 Iniciando actualización de portfolio..."

# Verificar credenciales
if [ ! -f "$SECRETS_FILE" ]; then
    log "❌ Error: No se encontró $SECRETS_FILE"
    exit 1
fi

# Leer credenciales
API_KEY=$(grep BINANCE_API_KEY "$SECRETS_FILE" | cut -d'=' -f2)
API_SECRET=$(grep BINANCE_API_SECRET "$SECRETS_FILE" | cut -d'=' -f2)

if [ -z "$API_KEY" ] || [ -z "$API_SECRET" ]; then
    log "❌ Error: Credenciales inválidas"
    exit 1
fi

# Obtener balance de Binance
TIMESTAMP=$(date +%s%3N)
RECV_WINDOW=5000
PARAMS="recvWindow=${RECV_WINDOW}&timestamp=${TIMESTAMP}"
SIGNATURE=$(echo -n "$PARAMS" | openssl dgst -sha256 -hmac "$API_SECRET" | awk '{print $2}')

HEADERS="X-MBX-APIKEY: $API_KEY"
URL="https://api.binance.com/api/v3/account?${PARAMS}&signature=${SIGNATURE}"

RESPONSE=$(curl -s -H "$HEADERS" "$URL")

if echo "$RESPONSE" | grep -q '"code"'; then
    log "❌ Error de Binance API: $RESPONSE"
    exit 1
fi

# Obtener precios actuales y tasa MXN
PRICES_RESPONSE=$(curl -s 'https://api.binance.com/api/v3/ticker/price')
MXN_RESPONSE=$(curl -s 'https://api.binance.com/api/v3/ticker/price?symbol=USDTMXN')

# Calcular total con Python (más fácil para parsing JSON)
python3 << PYTHON_EOF
import json
import sys

account_data = json.loads('''$RESPONSE''')
prices_data = json.loads('''$PRICES_RESPONSE''')
mxn_data = json.loads('''$MXN_RESPONSE''')

mxn_rate = float(mxn_data.get('price', 17.5))
prices = {p['symbol']: float(p['price']) for p in prices_data}

total_usdt = 0.0
holdings = []

for b in account_data.get('balances', []):
    free = float(b['free'])
    locked = float(b['locked'])
    total = free + locked
    
    if total < 0.001:
        continue
    
    asset = b['asset']
    
    if asset in ['USDT', 'BUSD', 'USDC']:
        total_usdt += total
        holdings.append(f"{asset}: {total:.2f} (stable)")
        continue
    
    symbol = f'{asset}USDT'
    if symbol in prices:
        value = total * prices[symbol]
        total_usdt += value
        holdings.append(f"{asset}: {total:.4f} × \${prices[symbol]:.2f} = \${value:.2f}")

# Guardar cache con tasa MXN
cache_data = {
    'value': round(total_usdt, 2),
    'value_mx': round(total_usdt * mxn_rate, 2),
    'mxn_rate': mxn_rate,
    'timestamp': $(date +%s),
    'holdings': holdings
}

with open('$CACHE_FILE', 'w') as f:
    json.dump(cache_data, f, indent=2)

print(f"💰 Portfolio actualizado: \${total_usdt:.2f} USDT (~\${total_usdt * mxn_rate:.2f} MXN)")
print(f"💱 Tasa USDT/MXN: \${mxn_rate:.4f}")
PYTHON_EOF

RESULT=$?

if [ $RESULT -eq 0 ]; then
    log "✅ Portfolio actualizado exitosamente"
else
    log "❌ Error al calcular el portfolio"
    exit 1
fi
