#!/bin/bash
# Refresca spot-registry.json: precios actuales + balances
set -e
python3 - <<'PY'
import json, subprocess
from pathlib import Path
from datetime import datetime

p = Path('crypto-bots/spot-registry.json')
data = json.loads(p.read_text())
COINS = ['BTC','ETH','BNB','SOL','LINK','XRP','AVAX']
for c in COINS:
    raw = subprocess.check_output(['curl','-sf',f'https://api.binance.com/api/v3/ticker/price?symbol={c}USDT']).decode().strip()
    data['prices_now'][c] = float(json.loads(raw)['price'])
data['timestamp'] = datetime.now().isoformat()
p.write_text(json.dumps(data, indent=2))
print(json.dumps({'ok': True, 'timestamp': data['timestamp'], 'prices': data['prices_now']}))
PY
