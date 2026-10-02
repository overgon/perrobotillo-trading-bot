#!/bin/bash
# ════════════════════════════════════════════════════════
# 📊 CAPITAL REPORT - Perrobotillo Trading Bot
# ════════════════════════════════════════════════════════
WORKSPACE="$HOME/.openclaw/workspace"
TRACKER="$WORKSPACE/crypto-bots/capital-tracker.json"
LOG="$WORKSPACE/logs/capital-report.log"

mkdir -p "$(dirname "$LOG")" 2>/dev/null || true

log(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] [CAPITAL] $*" | tee -a "$LOG"; }

if [ ! -f "$TRACKER" ]; then
  log "❌ capital-tracker.json no existe"
  exit 1
fi

log "=== REPORTE DE FLUJO DE CAPITAL ==="
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/home/overgon/.openclaw/workspace/crypto-bots/capital-tracker.json')
data=json.loads(p.read_text())
moves=data.get('moves',[])
print(f'Registros: {len(moves)}')
print(f'Último balance USDT: {data.get("lastBalanceUSDT")}')
print()
for m in moves[-20:]:
    print(f"{m.get('timestamp')} | {m.get('type','?')} {m.get('coin','?')} | USDT: {m.get('usdt_amount',0):.2f} | qty: {m.get('quantity',0)} | order: {m.get('order_id','?')} | note: {m.get('note','')}")
PY
