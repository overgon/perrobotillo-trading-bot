#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ════════════════════════════════════════════════════════
# 📥 Descarga velas 5m REALES de Binance Spot → backtest/data
# ════════════════════════════════════════════════════════
# La DB de Jesse se expande desde 1h y pierde el path intrabar;
# el ML del bot usa features de 5m, así que necesita las velas
# reales de 5m (no las derivadas del resampleo 1h→1m).
#
# Uso: venv-jesse/bin/python3 research/download_bot_5m.py [--days 95] [--coins BTC,ETH]
# ════════════════════════════════════════════════════════

import argparse
import csv
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

ALL_COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC']
INTERVAL = '5m'
API = 'https://api.binance.com/api/v3/klines'
OUT = Path('/home/overgon/work/perrobotillo-trading-bot/backtest/data')


def download(symbol: str, start_ms: int, end_ms: int, max_iters: int = 40) -> list:
    rows = []
    cur = start_ms
    it = 0
    while cur < end_ms and it < max_iters:
        it += 1
        for attempt in range(3):
            try:
                r = requests.get(API, params={
                    'symbol': symbol, 'interval': INTERVAL,
                    'startTime': cur, 'endTime': end_ms, 'limit': 1000,
                }, timeout=10)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
        if not data:
            break
        rows.extend(data)
        new_cur = data[-1][0] + 1
        if new_cur <= cur:
            break
        cur = new_cur
        time.sleep(0.1)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=95)
    ap.add_argument('--coins', default='ALL')
    ap.add_argument('--max-iters', type=int, default=40, help='paginas de 1000 velas por moneda')
    args = ap.parse_args()

    coins = ALL_COINS if args.coins.upper() == 'ALL' else [c.strip().upper() for c in args.coins.split(',')]
    end = datetime.now()
    start = end - timedelta(days=args.days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    OUT.mkdir(parents=True, exist_ok=True)

    print(f'=== 5m real Binance Spot | {start:%Y-%m-%d} → {end:%Y-%m-%d} | {args.days} días ===', flush=True)
    for coin in coins:
        symbol = f'{coin}USDT'
        try:
            rows = download(symbol, start_ms, end_ms, max_iters=args.max_iters)
        except Exception as exc:  # noqa: BLE001
            print(f'  ❌ {coin}: {exc}', flush=True)
            continue
        path = OUT / f'{coin}_5m.csv'
        with path.open('w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            for k in rows:
                ts = datetime.fromtimestamp(k[0] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                w.writerow([ts, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])])
        print(f'  ✅ {coin}: {len(rows)} velas → {path.name}', flush=True)


if __name__ == '__main__':
    main()
