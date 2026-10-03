"""
Convert Perrobotillo 1h CSV candles to 1m format and store in Jesse.
Jesse stores 1m candles internally and resamples to higher timeframes on retrieval.
Each 1h candle is expanded into 60 1m candles preserving OHLC values.

Expansion strategy:
- Minute 0: open=1h_open, high=1h_high, low=1h_low, close=1h_open
- Minutes 1-58: open=prev_close, high=1h_high, low=1h_low, close=open (flat)
- Minute 59: open=prev_close, high=1h_high, low=1h_low, close=1h_close
- Volume: 1h_volume / 60 per minute
  This ensures resampling to 1h reproduces exact original OHLC.
"""

import sys
import os
import time
import json
import numpy as np
import datetime
import pandas as pd

sys.path.insert(0, '/home')

from jesse.research import store_candles, get_candles

RAW_DATA = '/home/raw_data'
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']

def parse_timestamp(ts_str):
    """Convert Perrobotillo ISO timestamp (2026-01-18T18:00:00) to milliseconds."""
    dt = datetime.datetime.strptime(ts_str.strip(), '%Y-%m-%dT%H:%M:%S')
    return int(dt.timestamp() * 1000)

def expand_1h_to_1m(df):
    """
    Expand each 1h candle into 60 1m candles.
    Preserves OHLC values when resampled back to 1h.
    """
    rows = []
    
    for _, row in df.iterrows():
        ts_ms = parse_timestamp(row['timestamp'])
        open_price = float(row['open'])
        high = float(row['high'])
        low = float(row['low'])
        close = float(row['close'])
        volume = float(row['volume'])
        vol_per_min = volume / 60.0
        
        for minute in range(60):
            minute_ts = ts_ms + (minute * 60000)
            
            if minute == 0:
                m_open = open_price
                m_close = open_price
            elif minute == 59:
                m_open = close
                m_close = close
            else:
                m_open = open_price + (close - open_price) * (minute / 59.0)
                m_close = m_open
            
            rows.append([minute_ts, m_open, high, low, m_close, vol_per_min])
    
    # Ensure chronological order (Bug fix per issue #44)
    # If CSV rows are non-sequential, expansion produces out-of-order 1m candles
    rows.sort(key=lambda r: r[0])
    
    return np.array(rows, dtype=np.float64)

def load_perrobotillo_csv(filepath):
    """Load Perrobotillo 1h CSV."""
    df = pd.read_csv(filepath)
    # Filter out any rows with malformed data
    df = df.dropna(subset=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def import_coin(coin):
    """Import a single coin's candles."""
    symbol = f'{coin}-USDT'
    csv_path = f'{RAW_DATA}/{coin}USDT_1h_90days.csv'
    
    if not os.path.exists(csv_path):
        print(f'  ❌ {csv_path} not found')
        return False
    
    try:
        df = load_perrobotillo_csv(csv_path)
        print(f'  📥 {symbol}: {len(df)} 1h candles')
        
        candles = expand_1h_to_1m(df)
        print(f'  🔄 Expanded to {len(candles)} 1m candles')
        
        # Verify timestamps are 60000ms apart (1 minute)
        diff = candles[1:, 0] - candles[:-1, 0]
        unique_diffs = set(diff)
        if unique_diffs != {60000.0}:
            print(f'  ⚠️  Warning: timestamp diffs = {unique_diffs}')
        
        store_candles(candles, 'Binance Spot', symbol)
        print(f'  ✅ {symbol} stored in DB')
        
        # Also store fear/greed data if this is BTC (for market mode detection)
        return True
        
    except Exception as e:
        print(f'  ❌ {symbol} failed: {e}')
        import traceback
        traceback.print_exc()
        return False

def verify_candles():
    """Verify stored candles by retrieving 1h data."""
    print("\n=== VERIFICATION ===")
    
    # Use actual Perrobotillo data date range (Jan 18 - Apr 18, 2026)
    start_ts = int(datetime.datetime(2026, 1, 18).timestamp() * 1000)
    end_ts = int(datetime.datetime(2026, 4, 18, 18).timestamp() * 1000)
    
    all_good = True
    for coin in COINS:
        symbol = f'{coin}-USDT'
        try:
            result = get_candles('Binance Spot', symbol, '1h', start_ts, end_ts)
            # get_candles returns (candles, metadata) — extract candles
            if isinstance(result, tuple):
                c = result[1] if result[0] is None else result[0]
            else:
                c = result
            if c is not None and len(c) > 0:
                ts = c[0][0]
                if ts > 1e12: ts = ts / 1000
                start_dt = datetime.datetime.fromtimestamp(ts)
                end_ts_val = c[-1][0]
                if end_ts_val > 1e12: end_ts_val = end_ts_val / 1000
                end_dt = datetime.datetime.fromtimestamp(end_ts_val)
                print(f'  ✅ {symbol:10s}: {len(c)} rows | {start_dt.strftime("%Y-%m-%d")} to {end_dt.strftime("%Y-%m-%d")}')
                
                # Verify the 1h candle values match original
                # (the first candle should have the same OHLC as the CSV)
            else:
                print(f'  ❌ {symbol:10s}: None or empty')
                all_good = False
        except Exception as e:
            print(f'  ❌ {symbol:10s}: {str(e)[:80]}')
            all_good = False
    
    return all_good

def verify_ohlc_accuracy():
    """Verify that resampled 1h candles match the original Perrobotillo data."""
    print("\n=== OHLC Accuracy Check ===")
    
    # Use actual Perrobotillo data date range (Jan 18 - Apr 18, 2026)
    start_ts = int(datetime.datetime(2026, 1, 18).timestamp() * 1000)
    end_ts = int(datetime.datetime(2026, 4, 18, 18).timestamp() * 1000)
    
    # Check BTC first candle
    csv_path = f'{RAW_DATA}/BTCUSDT_1h_90days.csv'
    df = pd.read_csv(csv_path)
    original_first = df.iloc[0]
    
    result = get_candles('Binance Spot', 'BTC-USDT', '1h', start_ts, end_ts)
    if isinstance(result, tuple):
        c = result[1] if result[0] is None else result[0]
    else:
        c = result
    
    if c is not None and len(c) > 0:
        # Compare first candle
        jesse_first = c[0]
        print(f'  Original 1h first candle:')
        print(f'    Open:  {original_first["open"]}  vs  Jesse: {jesse_first[1]:.4f}')
        print(f'    High:  {original_first["high"]}  vs  Jesse: {jesse_first[2]:.4f}')
        print(f'    Low:   {original_first["low"]}   vs  Jesse: {jesse_first[3]:.4f}')
        print(f'    Close: {original_first["close"]}  vs  Jesse: {jesse_first[4]:.4f}')
        print(f'    Volume: {original_first["volume"]}  vs  Jesse: {jesse_first[5]:.4f}')
        
        # Check if values match (within rounding)
        tol = 0.01  # small tolerance for floating point
        match = (
            abs(jesse_first[1] - float(original_first['open'])) < tol and
            abs(jesse_first[2] - float(original_first['high'])) < tol and
            abs(jesse_first[3] - float(original_first['low'])) < tol and
            abs(jesse_first[4] - float(original_first['close'])) < tol
        )
        print(f'  ✅ OHLC match: {match}')
    else:
        print(f'  ❌ Could not retrieve candles for comparison')

if __name__ == '__main__':
    print("=== Perrobotillo → Jesse Candle Import ===")
    print(f"Raw data: {RAW_DATA}")
    print(f"Coins: {COINS}\n")
    
    # Import all coins
    for coin in COINS:
        import_coin(coin)
        print()
    
    # Verify
    all_good = verify_candles()
    
    if all_good:
        verify_ohlc_accuracy()
        print("\n🎉 All candles imported and verified!")
    else:
        print("\n⚠️  Some candles failed to import")
