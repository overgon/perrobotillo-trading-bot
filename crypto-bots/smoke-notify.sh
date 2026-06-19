#!/bin/bash
# ╔═══════════════════════════════════════════════════════╗
# ║  🧪 SMOKE TEST - Sistema de notificaciones           ║
# ╚═══════════════════════════════════════════════════════╝
set -euo pipefail
WORKSPACE="$HOME/.openclaw/workspace"
notify="$WORKSPACE/crypto-bots/notify.sh"
required=(
  "$WORKSPACE/crypto-bots/notify.sh"
  "$HOME/.openclaw/openclaw.json"
  "$HOME/.openclaw/secrets/binance.env"
  "$WORKSPACE/crypto-bots/dynamic-config.env"
)
for f in "${required[@]}"; do
  [ -f "$f" ] || { echo "❌ Falta: $f"; exit 1; }
done
bash "$notify" "SMOKE|1" "🧪 Smoke test 1: sistema vivo"
bash "$notify" "SMOKE|2" "🧪 Smoke test 2: dedup será efectivo si se repite"
echo "✅ Smoke test enviado"
