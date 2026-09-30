#!/usr/bin/env python3
"""
Download 1h klines from Binance public API → CSV → expand to 1m → store in Jesse DB.
Fase 5 prerequisite: 2 years of candle data (2023-01-01 → 2025-01-01) per issue #44.

Usage:
    python3 research/download_candles.py              # all 7 coins
    python3 research/download_candles.py --coin LINK  # single coin
    python3 research/download_candles.py --test       # BTC only (quick test)
"""

import os, sys, time, json, argparse
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, '/home')
from jesse.research import store_candles  # noqa: E402

BINANCE_API = "https://api.binance.com/api/v3/klines"
RAW_DATA_DIR = Path("/home/raw_data")
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'AVAX', 'ZEC', 'XRP']
START_DATE = "2023-01-01"
END_DATE = "2025-01-01"
INTERVAL = "1h"
RATE_LIMIT_SLEEP = 0.1  # 100 req/s is generous; sleep 0.1s between requests


def download_klines(symbol: str, start_ts: int, end_ts: int) -> pd.DataFrame:
    """Download 1h klines from Binance API with pagination."""
    all_rows = []
    current_start = start_ts

    while current_start < end_ts:
        params = {
            'symbol': symbol,
            'interval': INTERVAL,
            'startTime': current_start,
            'endTime': end_ts,
            'limit': 1000,
        }
        resp = requests.get(BINANCE_API, params=params, timeout=30)

        if resp.status_code != 200:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
            break

        data = resp.json()
        if not data:
            break

        for row in data:
            all_rows.append({
                'timestamp': datetime.fromtimestamp(row[0] / 1000).strftime('%Y-%m-%dT%H:%M:%S'),
                'open': float(row[1]),
                'high': float(row[2]),
                'low': float(row[3]),
                'close': float(row[4]),
                'volume': float(row[5]),
            })

        if len(data) < 1000:
            break  # Last page

        current_start = data[-1][0] + 1  # Move past last candle
        time.sleep(RATE_LIMIT_SLEEP)

    return pd.DataFrame(all_rows)


def expand_1h_to_1m(df: pd.DataFrame) -> np.ndarray:
    """Expand 1h candles to 1m (same logic as import_candles_1m.py).
    Fills gaps between missing 1h candles with carry-forward prices."""
    rows = []
    prev_close = None
    prev_ts = None

    for _, r in df.iterrows():
        ts_ms = int(datetime.strptime(r['timestamp'], '%Y-%m-%dT%H:%M:%S').timestamp() * 1000)
        o, h, l, c, v = float(r['open']), float(r['high']), float(r['low']), float(r['close']), float(r['volume'])
        vol_per_min = v / 60.0

        # Fill gap between prev candle and this candle (missing hours on Binance)
        if prev_ts is not None and ts_ms > prev_ts + 3_600_000:
            gap_start = prev_ts + 3_600_000
            t = gap_start
            while t < ts_ms:
                rows.append([t, prev_close, prev_close, prev_close, prev_close, 0.0])
                t += 60_000

        for minute in range(60):
            t = ts_ms + minute * 60_000
            if minute == 0:
                m_open, m_close = o, o
            elif minute == 59:
                m_open, m_close = c, c
            else:
                m_open = o + (c - o) * (minute / 59.0)
                m_close = m_open
            rows.append([t, m_open, h, l, m_close, vol_per_min])

        prev_close = c
        prev_ts = ts_ms

    # Ensure chronological order before 1m spacing assertion
    # (Bug fix per issue #44: gap-filling + expansion can produce out-of-order
    #  rows if Binance returns non-sequential 1h timestamps)
    rows.sort(key=lambda r: r[0])

    arr = np.array(rows, dtype=np.float64)
    diffs = np.diff(arr[:, 0])
    assert np.all(diffs == 60_000), f"Non-1m intervals! min={diffs.min()} max={diffs.max()}"
    return arr


def download_and_store(coin: str):
    """Download 2 years of 1h klines, save CSV, expand to 1m, store in Jesse DB."""
    symbol = f"{coin}USDT"
    start_ts = int(datetime.strptime(START_DATE, '%Y-%m-%d').timestamp() * 1000)
    end_ts = int(datetime.strptime(END_DATE, '%Y-%m-%d').timestamp() * 1000)

    print(f"\n{'='*50}")
    print(f"📥 {symbol} ({START_DATE} → {END_DATE})")
    print(f"{'='*50}")

    # 1. Download
    df = download_klines(symbol, start_ts, end_ts)
    if len(df) == 0:
        print(f"  ❌ No data returned")
        return False

    print(f"  📊 Downloaded: {len(df)} 1h candles")

    # 2. Save CSV
    csv_path = RAW_DATA_DIR / f"{coin}USDT_1h.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    print(f"  💾 CSV: {csv_path} ({len(df)} rows)")

    # 3. Expand to 1m
    candles_1m = expand_1h_to_1m(df)
    diffs = np.diff(candles_1m[:, 0])
    assert np.all(diffs == 60_000), f"Non-1m intervals! min={diffs.min()} max={diffs.max()}"
    print(f"  🔄 Expanded: {len(candles_1m)} 1m candles")

    # 4. Store in Jesse DB
    store_candles(candles_1m, "Binance Spot", f"{coin}-USDT")
    print(f"  ✅ Stored in Jesse DB: Binance Spot / {coin}-USDT")

    return True


def main():
    parser = argparse.ArgumentParser(description='Download candles from Binance → Jesse DB')
    parser.add_argument('--coin', type=str, default=None)
    parser.add_argument('--test', action='store_true', help='BTC only (quick test)')
    args = parser.parse_args()

    coins = ['BTC'] if args.test else ([args.coin] if args.coin else COINS)

    print(f"=== Binance → Jesse Candle Downloader ===")
    print(f"Coins: {coins} | Interval: {INTERVAL} | Period: {START_DATE} → {END_DATE}")

    summary = {}
    for coin in coins:
        try:
            success = download_and_store(coin)
            summary[coin] = '✅' if success else '❌'
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            summary[coin] = '❌'
        time.sleep(0.5)  # Small delay between coins

    print(f"\n=== Summary ===")
    for coin, status in summary.items():
        print(f"  {status} {coin}")


if __name__ == '__main__':
    main()
