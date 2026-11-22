#!/usr/bin/env python3
"""
📸 Portfolio Snapshot — guarda el valor total de la cuenta en USDT.

Antes NADIE escribia $WORKSPACE/portfolio-snapshot.json: solo se leia (limite
diario del bot, emergency-close-all.sh y el dashboard). Consecuencia: el chequeo
de limite diario se saltaba siempre ("No hay snapshot de ayer").

Formato (lo esperan los lectores):
    {"value": 1234.56, "timestamp": "...", "date": "YYYY-MM-DD", "assets": {...}}
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(os.environ.get('WORKSPACE', '/home/overgon/.openclaw/workspace'))
SECRETS = Path('/home/overgon/.openclaw/secrets/binance.env')
OUT = WORKSPACE / 'portfolio-snapshot.json'
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC']


def load_credentials():
    creds = {}
    if not SECRETS.exists():
        raise SystemExit(f'❌ No existe {SECRETS}')
    for line in SECRETS.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            creds[k.strip()] = v.strip().strip('"').strip("'")
    return creds['BINANCE_API_KEY'], creds['BINANCE_API_SECRET']


def main():
    import ccxt

    key, secret = load_credentials()
    ex = ccxt.binance({
        'apiKey': key,
        'secret': secret,
        'options': {'defaultType': 'spot'},
        'timeout': 15000,
    })

    bal = ex.fetch_balance()
    totals = bal['total']

    # precios en USDT
    prices = {'USDT': 1.0, 'USDC': 1.0}
    for coin in COINS:
        try:
            prices[coin] = float(ex.fetch_ticker(f'{coin}/USDT')['last'])
        except Exception:
            prices[coin] = 0.0

    assets = {}
    value = 0.0
    for asset, amount in totals.items():
        amount = float(amount or 0)
        if amount <= 0:
            continue
        p = prices.get(asset)
        if p is None:
            try:
                p = float(ex.fetch_ticker(f'{asset}/USDT')['last'])
            except Exception:
                p = 0.0
            prices[asset] = p
        v = amount * p
        if v <= 0:
            continue
        assets[asset] = {'amount': amount, 'price': p, 'usd': round(v, 4)}
        value += v

    payload = {
        'value': round(value, 2),
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'assets': assets,
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"✅ portfolio-snapshot.json: ${payload['value']:.2f} | {len(assets)} activos")


if __name__ == '__main__':
    sys.exit(main())
