#!/bin/bash
# crypto-coincap-prices.sh
# Obtener precios de CoinCap API V3

# Cargar token desde secrets
source /home/overgon/.openclaw/secrets/coincap.env 2>/dev/null || {
    echo "❌ Error: No se encontró COINCAP_TOKEN en ~/.openclaw/secrets/coincap.env"
    echo "   Creá el archivo con: export COINCAP_TOKEN='tu_token_aqui'"
    exit 1
}

BASE_URL="https://rest.coincap.io/v3"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  💰 COINCAP API - PRECIOS EN VIVO                     ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Obtener precios de múltiples cryptos
echo "=== PRECIOS ACTUALES ==="
response=$(curl -s "$BASE_URL/price/bysymbol/BTC,ETH,BNB,SOL,XRP,AVAX,ZEC" \
  -H "Authorization: Bearer $COINCAP_TOKEN")

# Parsear respuesta
timestamp=$(echo "$response" | jq -r '.timestamp // 0')
prices=$(echo "$response" | jq -r '.data[]')

# Mostrar precios
coins=("BTC" "ETH" "BNB" "SOL" "XRP" "AVAX" "ZEC")
i=0
for price in $prices; do
    coin=${coins[$i]}
    if [ "$price" != "null" ] && [ -n "$price" ]; then
        printf "%-6s \$%s\n" "$coin" "$price"
    else
        printf "%-6s No disponible\n" "$coin"
    fi
    ((i++))
done

echo ""
echo "=== DETALLE DE BITCOIN ==="
btc_data=$(curl -s "$BASE_URL/assets/bitcoin" \
  -H "Authorization: Bearer $COINCAP_TOKEN" | jq '.data')

echo "$btc_data" | jq '{
  name: .name,
  symbol: .symbol,
  priceUsd: .priceUsd,
  changePercent24Hr: .changePercent24Hr,
  marketCapUsd: .marketCapUsd
}'

echo ""
echo "Timestamp: $timestamp"
echo "Actualizado: $(date -d @$((timestamp/1000)) '+%Y-%m-%d %H:%M:%S CST' 2>/dev/null || date)"
