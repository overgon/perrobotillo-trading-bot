#!/bin/bash
# SPOT TRACKER - Perrobotron
# Registra fluctuación real de Spot y P&L por activo
WORKSPACE="/home/overgon/.openclaw/workspace"
REGISTRY="$WORKSPACE/crypto-bots/spot-registry.json"
HISTORY_DIR="$WORKSPACE/crypto-bots/spot-history"
COINS="BTC ETH BNB SOL LINK XRP AVAX"

mkdir -p "$HISTORY_DIR"
TS=$(date -Iseconds)
SNAP="$HISTORY_DIR/${TS//[: ]/-}.json"

python3 - <<'PY'
import json, subprocess
from pathlib import Path
from datetime import datetime

work = Path('/home/overgon/.openclaw/workspace')
reg = json.loads((work/'crypto-bots/spot-registry.json').read_text())
ts = datetime.now().isoformat()
coins = ['BTC','ETH','BNB','SOL','LINK','XRP','AVAX']
prices = {}
for c in coins:
    raw = subprocess.check_output(['curl','-sf',f'https://api.binance.com/api/v3/ticker/price?symbol={c}USDT']).decode().strip()
    prices[c] = float(json.loads(raw)['price'])

assets = []
for a in reg.get('assets', []):
    sym = a.get('symbol')
    if sym not in prices:
        continue
    price_now = prices[sym]
    balance = float(a.get('balance', 0) or 0)
    mxn_now = balance * price_now * float(reg.get('total_mxn', 46079.39) / reg.get('total_usdt', 2646.72))
    prev = a.get('mxn', 0)
    assets.append({
        'symbol': sym,
        'balance': balance,
        'price_now': price_now,
        'mxn_now': mxn_now,
        'mxn_prev': prev,
        'diff_mxn': mxn_now - prev,
    })

snapshot = {
    'timestamp': ts,
    'prices': prices,
    'assets': assets,
    'total_assets_mxn_now': sum(x['mxn_now'] for x in assets),
}
(work/'crypto-bots/spot-history'/f'{ts.replace(":","-").replace(" ","_")}.json').write_text(json.dumps(snapshot, indent=2))
print(json.dumps(snapshot, indent=2))
PY
