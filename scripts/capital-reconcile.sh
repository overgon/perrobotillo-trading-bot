#!/bin/bash
# ════════════════════════════════════════════════════════
# 🔁 CAPITAL RECONCILE - Perrobotillo Trading Bot
# ════════════════════════════════════════════════════════
WORKSPACE="$HOME/.openclaw/workspace"
TRACKER="$WORKSPACE/crypto-bots/capital-tracker.json"
LOG="$WORKSPACE/logs/capital-reconcile.log"

mkdir -p "$(dirname "$LOG")" 2>/dev/null || true

log(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] [CAPITAL] $*" | tee -a "$LOG"; }

log "=== RECONCILIACIÓN CAPITAL INICIADA ==="
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/home/overgon/.openclaw/workspace/crypto-bots/capital-tracker.json')
data=json.loads(p.read_text())
moves=data.get('moves',[])
print(f'Movimientos registrados: {len(moves)}')
print('Resumen por tipo:')
from collections import Counter
c=Counter(m.get('type','?') for m in moves)
for k,v in c.items():
    print(f'  {k}: {v}')
PY
log "=== RECONCILIACIÓN CAPITAL FINALIZADA ==="
