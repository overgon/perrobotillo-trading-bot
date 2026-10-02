#!/usr/bin/env bash
set -euo pipefail
SYMBOL="ATOMUSDT"
OUT="/tmp/atom_price_check.json"
TMP="/tmp/atom_price_check_tmp.json"

price=$(curl -s -m 15 "https://api.binance.com/api/v3/ticker/price?symbol=${SYMBOL}" | jq -r '.price // empty')
if [ -z "$price" ]; then
  echo '{"error":"no_price"}'
  exit 0
fi

prev=""
if [ -f "$OUT" ]; then
  prev=$(jq -r '.price // empty' "$OUT" 2>/dev/null || echo "")
fi

chg=""
if [ -n "$prev" ]; then
  chg=$(awk -v p="$price" -v q="$prev" 'BEGIN {printf "%.2f", (p-q)/q*100}')
fi

jq -n \
  --arg ts "$(date -Iseconds)" \
  --arg price "$price" \
  --arg prev "$prev" \
  --arg chg "$chg" \
  '{symbol:"ATOM", asOf:$ts, price:$price, prev:$price, changePct:($chg|if .=="" then null else (.|tonumber) end)}' \
  > "$TMP" && mv "$TMP" "$OUT"

cat "$OUT"
