#!/usr/bin/env bash
set -euo pipefail
URLS=(
  "https://forum.cosmos.network/t/hub-weekly-update-5-june-11-2026/17044"
  "https://coinmarketcap.com/cmc-ai/cosmos/latest-updates/"
)
OUT="/tmp/atom_weekly_news.json"
TMP="/tmp/atom_weekly_news_tmp.json"
RUN_TS=$(date -Iseconds)

items="[]"
for u in "${URLS[@]}"; do
  body=$(curl -s -m 25 "$u" || true)
  title=$(printf '%s' "$body" | grep -oE '<title>[^<]+' | head -n 1 | sed 's/<title>//' || true)
  desc=$(printf '%s' "$body" | grep -oE '<meta name="description" content="[^"]+' | head -n 1 | sed 's/<meta name="description" content="//' || true)
  if [ -z "$desc" ]; then
    desc=$(printf '%s' "$body" | grep -oE '<p>[^<]{20,220}</p>' | head -n 1 | sed 's/<p>//;s/<\/p>//' || true)
  fi
  items=$(printf '%s' "$items" | jq --arg u "$u" --arg t "${title:-}" --arg d "${desc:-}" '. + [{"url":$u,"title":$t,"snippet":$d}]')
done

jq -n --arg run "$RUN_TS" --argjson items "$items" '{runAt:$run, items:$items}' > "$TMP" && mv "$TMP" "$OUT"
cat "$OUT"
