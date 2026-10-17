#!/usr/bin/env python3
"""
Download 1h Binance Spot OHLCV data for bull market period (2023-2024).
Uses Binance public API (no auth needed for klines).
Saves to backtest/data/{SYMBOL}_1h_bull2023_2024.csv

Bull market window: 2023-01-01 to 2024-12-31
(includes Jan 2023 accumulation + Oct 2023 ETF rumor pump + 2024 bull run to new highs)
"""
import ccxt
import pandas as pd
import time
import os
from datetime import datetime

DATA_DIR = os.path.expanduser("~/.openclaw/workspace/backtest/data")
COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

# Bull market period: Jan 2023 - Dec 2024
START_TS = int(datetime(2023, 1, 1).timestamp() * 1000)  # 2023-01-01
END_TS = int(datetime(2025, 1, 1).timestamp() * 1000)    # 2025-01-01 (so 2024 ends at 2024-12-31 18h)

exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

def download_ohlcv(symbol, timeframe='1h', since=None, until=None):
    """Download OHLCV data with pagination (Binance limit is 1000 candles)."""
    all_data = []
    batch_size = 1000  # max Binance allows
    ts = since

    print(f"  Downloading {symbol} {timeframe}...", end=' ', flush=True)
    while ts < until:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=ts, limit=batch_size)
            if not ohlcv:
                break
            all_data.extend(ohlcv)
            ts = ohlcv[-1][0] + 1  # move past last candle
            time.sleep(0.1)  # rate limit
        except Exception as e:
            print(f"\n  Error for {symbol}: {e}")
            break

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    print(f"  ✅ {len(df)} candles ({df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]})")
    return df

for coin in COINS:
    symbol = f"{coin}/USDT"
    out_file = f"{DATA_DIR}/{coin}USDT_1h_bull2023_2024.csv"
    if os.path.exists(out_file):
        print(f"  ⏭️  {coin}: already exists ({out_file})")
        continue

    df = download_ohlcv(symbol, '1h', since=START_TS, until=END_TS)
    if len(df) > 0:
        df.to_csv(out_file, index=False)
        print(f"  💾 Saved: {out_file}")
    else:
        print(f"  ❌ No data for {coin}")

print("\n✅ All done!")
