#!/bin/bash
# crypto-exchange-compare.sh
# Compara precios entre Binance, Bitso, Bybit y CoinCap

source /home/overgon/.openclaw/secrets/binance.env 2>/dev/null
source /home/overgon/.openclaw/secrets/coincap.env 2>/dev/null

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  📊 COMPARADOR DE PRECIOS - MULTI-EXCHANGE            ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Monedas a comparar
COINS=("BTC" "ETH" "XRP")

for COIN in "${COINS[@]}"; do
    echo "═══════════════════════════════════════"
    echo "💰 $COIN"
    echo "═══════════════════════════════════════"
    
    # ===========================
    # BINANCE
    # ===========================
    if [ "$COIN" == "BTC" ]; then symbol="BTCUSDT"
    elif [ "$COIN" == "ETH" ]; then symbol="ETHUSDT"
    elif [ "$COIN" == "XRP" ]; then symbol="XRPUSDT"
    fi
    
    binance_price=$(curl -s "https://api.binance.com/api/v3/ticker/price?symbol=$symbol" | jq -r '.price' 2>/dev/null)
    if [ "$binance_price" != "null" ] && [ -n "$binance_price" ]; then
        printf "  🌐 Binance:  \$%-12s\n" "$binance_price"
    else
        printf "  🌐 Binance:  %-12s\n" "No disponible"
    fi
    
    # ===========================
    # BITSO (México - MXN a USD)
    # ===========================
    if [ "$COIN" == "BTC" ]; then bitso_pair="btc_mxn"
    elif [ "$COIN" == "ETH" ]; then bitso_pair="eth_mxn"
    elif [ "$COIN" == "XRP" ]; then bitso_pair="xrp_mxn"
    fi
    
    bitso_response=$(curl -s "https://api.bitso.com/v3/ticker?book=$bitso_pair" 2>/dev/null)
    bitso_mxn=$(echo "$bitso_response" | jq -r '.payload.last // empty' 2>/dev/null)
    
    # Obtener precio MXN/USD de Bitso (usd_mxn, NO usdc_mxn)
    usdmxn_response=$(curl -s "https://api.bitso.com/v3/ticker?book=usd_mxn" 2>/dev/null)
    usdmxn_rate=$(echo "$usdmxn_response" | jq -r '.payload.last // empty' 2>/dev/null)
    
    if [ -n "$bitso_mxn" ] && [ -n "$usdmxn_rate" ] && [ "$usdmxn_rate" != "0" ]; then
        bitso_usd=$(echo "scale=2; $bitso_mxn / $usdmxn_rate" | bc 2>/dev/null)
        printf "  🇲🇽 Bitso:    \$%-12s (MXN \$%s)\n" "$bitso_usd" "$bitso_mxn"
    else
        printf "  🇲🇽 Bitso:    %-12s\n" "No disponible"
        bitso_usd=""
    fi
    
    # ===========================
    # BYBIT
    # ===========================
    bybit_price=$(curl -s "https://api.bybit.com/v5/market/tickers?category=spot&symbol=${COIN}USDT" 2>/dev/null | jq -r '.result.list[0].lastPrice' 2>/dev/null)
    if [ "$bybit_price" != "null" ] && [ -n "$bybit_price" ]; then
        printf "  🌏 Bybit:    \$%-12s\n" "$bybit_price"
    else
        printf "  🌏 Bybit:    %-12s\n" "No disponible"
    fi
    
    # ===========================
    # COINCAP (Referencia)
    # ===========================
    if [ "$COIN" == "BTC" ]; then coincap_id="bitcoin"
    elif [ "$COIN" == "ETH" ]; then coincap_id="ethereum"
    elif [ "$COIN" == "XRP" ]; then coincap_id="xrp"  # Corregido: era "ripple"
    fi
    
    coincap_response=$(curl -s "https://rest.coincap.io/v3/assets/$coincap_id" \
      -H "Authorization: Bearer $COINCAP_TOKEN" 2>/dev/null)
    coincap_price=$(echo "$coincap_response" | jq -r '.data.priceUsd' 2>/dev/null | cut -c1-10)
    
    if [ "$coincap_price" != "null" ] && [ -n "$coincap_price" ]; then
        printf "  💰 CoinCap:  \$%-12s (Referencia)\n" "$coincap_price"
    else
        printf "  💰 CoinCap:  %-12s\n" "No disponible"
    fi
    
    echo ""
    
    # ===========================
    # CÁLCULO DE DIFERENCIAS
    # ===========================
    echo "  📊 DIFERENCIAS vs CoinCap:"
    
    # Binance vs CoinCap
    if [ -n "$binance_price" ] && [ -n "$coincap_price" ] && [ "$coincap_price" != "null" ]; then
        binance_diff=$(echo "scale=2; ($binance_price - $coincap_price) / $coincap_price * 100" | bc 2>/dev/null)
        if (( $(echo "$binance_diff > 0" | bc -l) )); then
            printf "    Binance: +%.2f%% 🟢\n" "$binance_diff"
        else
            printf "    Binance: %.2f%% 🔴\n" "$binance_diff"
        fi
    fi
    
    # Bitso vs CoinCap
    if [ -n "$bitso_usd" ] && [ -n "$coincap_price" ] && [ "$coincap_price" != "null" ]; then
        bitso_diff=$(echo "scale=2; ($bitso_usd - $coincap_price) / $coincap_price * 100" | bc 2>/dev/null)
        if (( $(echo "$bitso_diff > 0" | bc -l) )); then
            printf "    Bitso:   +%.2f%% 🟢\n" "$bitso_diff"
        else
            printf "    Bitso:   %.2f%% 🔴\n" "$bitso_diff"
        fi
    fi
    
    # Bybit vs CoinCap
    if [ -n "$bybit_price" ] && [ -n "$coincap_price" ] && [ "$coincap_price" != "null" ]; then
        bybit_diff=$(echo "scale=2; ($bybit_price - $coincap_price) / $coincap_price * 100" | bc 2>/dev/null)
        if (( $(echo "$bybit_diff > 0" | bc -l) )); then
            printf "    Bybit:   +%.2f%% 🟢\n" "$bybit_diff"
        else
            printf "    Bybit:   %.2f%% 🔴\n" "$bybit_diff"
        fi
    fi
    
    echo ""
    
    # ===========================
    # ALERTA DE ARBITRAJE
    # ===========================
    if [ -n "$binance_price" ] && [ -n "$bitso_usd" ]; then
        arb_diff=$(echo "scale=2; ($bitso_usd - $binance_price) / $binance_price * 100" | bc 2>/dev/null)
        arb_abs=$(echo "$arb_diff" | tr -d '-')
        
        if (( $(echo "$arb_abs > 2" | bc -l) )); then
            echo "  ⚠️  OPORTUNIDAD DE ARBITRAJE: ${arb_diff}% entre Binance y Bitso!"
        fi
    fi
    
    echo ""
done

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🕐 ACTUALIZADO: $(date '+%Y-%m-%d %H:%M:%S CST')                  ║"
echo "╚═══════════════════════════════════════════════════════╝"
