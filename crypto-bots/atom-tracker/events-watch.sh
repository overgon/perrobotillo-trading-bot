#!/usr/bin/env bash
set -euo pipefail
FEED="https://forum.cosmos.network/latest.json"
RAW=$(curl -s -m 20 "$FEED" || true)
TITLE=$(printf '%s' "$RAW" | jq -r '.topic_list.topics[0].fancy_title // .topic_list.topics[0].title // empty' 2>/dev/null || true)
SLUG=$(printf '%s' "$RAW" | jq -r '.topic_list.topics[0].slug // empty' 2>/dev/null || true)
ID=$(printf '%s' "$RAW" | jq -r '.topic_list.topics[0].id // empty' 2>/dev/null || true)
LINK=""
if [ -n "${SLUG:-}" ] && [ -n "${ID:-}" ]; then
  LINK="https://forum.cosmos.network/t/${SLUG}/${ID}"
fi
UPDATED=$(date -Iseconds)
jq -n \
  --arg updated "$UPDATED" \
  --arg title "${TITLE:-}" \
  --arg link "${LINK:-}" \
  '{updated:$updated, latestTitle:$title, latestLink:$link, notes:"forum latest only; manual review recommended"}' \
  > /tmp/atom_events_watch.json || true
printf 'updated=%s\n' "$UPDATED"
printf 'latestTitle=%s\n' "${TITLE:-}"
printf 'latestLink=%s\n' "${LINK:-}"
