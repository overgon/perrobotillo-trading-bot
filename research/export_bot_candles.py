#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
# Exporta velas de la DB de Jesse a backtest/data/{COIN}_5m.csv
#
# El ML del bot (ml/ml_pipeline.py::gather_phase) lee backtest/data/{COIN}_*.csv
# con columnas timestamp,open,high,low,close,volume. Este script las genera
# desde las velas ya importadas en Jesse (en vez de la API de Binance).
#
# Uso (venv-jesse):
#   venv-jesse/bin/python3 research/export_bot_candles.py --days 95
# ═══════════════════════════════════════════════════════════════════════════

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, '/home')

from jesse.research import get_candles  # noqa: E402

EXCHANGE = 'Binance Spot'
OUT_DIR = ROOT / 'backtest' / 'data'
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC']


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=95)
    ap.add_argument('--timeframe', default='5m')
    ap.add_argument('--coins', default='ALL')
    args = ap.parse_args()

    coins = COINS if args.coins.upper() == 'ALL' else [c.strip().upper() for c in args.coins.split(',')]
    end = datetime.now()
    start = end - timedelta(days=args.days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== Jesse → backtest/data ({args.timeframe}, {args.days} días) ===")

    for coin in coins:
        try:
            c = get_candles(EXCHANGE, f'{coin}-USDT', args.timeframe, start_ms, end_ms)
            if isinstance(c, tuple):
                c = c[1]
            if c is None or len(c) == 0:
                print(f"  ❌ {coin}: sin velas")
                continue
            out = OUT_DIR / f'{coin}_{args.timeframe}.csv'
            with out.open('w') as f:
                f.write('timestamp,open,high,low,close,volume\n')
                for row in c:
                    ts = datetime.fromtimestamp(row[0] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    # Jesse 3.6: [timestamp, open, high, low, close, volume]
                    f.write(f"{ts},{row[1]},{row[2]},{row[3]},{row[4]},{row[5]}\n")
            print(f"  ✅ {coin}: {len(c)} velas → {out.name}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ {coin}: {type(exc).__name__}: {exc}")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
