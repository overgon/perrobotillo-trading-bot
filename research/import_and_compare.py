"""
Import Perrobotillo CSV candles to Jesse and run backtest comparison.
===============================================================

This script:
1. Reads Perrobotillo's cached 1h CSV data (90 days)
2. Converts to Jesse's numpy format
3. Stores in Jesse's PostgreSQL via store_candles()
4. Runs a backtest with the Perrobotillo strategy
5. Compares results against trade-history.json (production)
"""

import sys
import os
import time
import json
import numpy as np
import datetime

# Add project root to path
sys.path.insert(0, '/home')

from jesse.research import store_candles, get_candles
# backtest will be imported in run_backtest()

WORKSPACE = '/home/overgon/.openclaw/workspace'
RAW_DATA = '/home/raw_data'

# Perrobotillo coins
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']

def parse_timestamp(ts_str):
    """Convert Perrobotillo ISO timestamp to milliseconds."""
    # Format: 2026-01-18T18:00:00
    dt = datetime.datetime.strptime(ts_str, '%Y-%m-%dT%H:%M:%S')
    return int(dt.timestamp() * 1000)

def load_perrobotillo_csv(filepath):
    """Load Perrobotillo 1h CSV and convert to Jesse format numpy array."""
    import pandas as pd
    df = pd.read_csv(filepath)
    
    # Perrobotillo CSV format: timestamp,open,high,low,close,volume
    candles = np.zeros((len(df), 6), dtype=np.float64)
    
    for i, row in df.iterrows():
        ts = parse_timestamp(row['timestamp'])
        candles[i, 0] = ts
        candles[i, 1] = float(row['open'])
        candles[i, 2] = float(row['high'])
        candles[i, 3] = float(row['low'])
        candles[i, 4] = float(row['close'])
        candles[i, 5] = float(row['volume'])
    
    return candles

def import_all_candles():
    """Import all 7 coins' 1h candles into Jesse's database."""
    print("=== STEP 1: Importing candles ===")
    
    for coin in COINS:
        symbol = f'{coin}-USDT'
        csv_path = f'{RAW_DATA}/{coin}USDT_1h_90days.csv'
        
        if not os.path.exists(csv_path):
            print(f'  ❌ {csv_path} not found')
            continue
        
        try:
            candles = load_perrobotillo_csv(csv_path)
            print(f'  📥 {symbol}: {len(candles)} rows, '
                  f'{datetime.datetime.fromtimestamp(candles[0,0]/1000)} to '
                  f'{datetime.datetime.fromtimestamp(candles[-1,0]/1000)}')
            store_candles(candles, 'Binance Spot', symbol)
            print(f'  ✅ {symbol} stored')
        except Exception as e:
            print(f'  ❌ {symbol} failed: {e}')
    
    print("\n=== STEP 2: Verification ===")
    
    # Verify by reloading
    end_ts = int(time.time() * 1000)
    start_ts = end_ts - (90 * 24 * 60 * 60 * 1000)
    
    for coin in COINS:
        symbol = f'{coin}-USDT'
        try:
            c = get_candles('Binance Spot', symbol, '1h', start_ts, end_ts)
            print(f'  ✅ {symbol}: {len(c)} rows verified')
        except Exception as e:
            print(f'  ❌ {symbol}: {e}')

def run_backtest():
    """Run backtest with Perrobotillo strategy and compare with production."""
    print("\n=== STEP 3: Running backtest ===")
    
    from jesse.research import backtest
    import numpy as np
    
    # Load candles for all coins
    end_ts = int(time.time() * 1000)
    start_ts = end_ts - (90 * 24 * 60 * 60 * 1000)
    
    # Build routes for all 7 coins
    routes = []
    for coin in COINS:
        symbol = f'{coin}-USDT'
        routes.append({
            'exchange': 'binance-spot',
            'symbol': symbol,
            'timeframe': '1h',
            'strategy': 'Perrobotillo',
            'stake': 1000,
        })
    
    config = {
        'starting_balance': 10000,
        'fee': 0.1,
        'type': 'backtest',
        'futures_leverage': 10,
        'futures_leverage_mode': 1,
        'slippage': 0.5,  # 0.5% slippage (conservative for spot)
    }
    
    # Get candles
    candles = {}
    for route in routes:
        coin = route['symbol']
        try:
            c = get_candles('Binance Spot', coin, '1h', start_ts, end_ts)
            candles[(route['exchange'], coin, route['timeframe'])] = c
            print(f'  Loaded {coin}: {len(c)} candles')
        except Exception as e:
            print(f'  ❌ Failed to load {coin}: {e}')
    
    # Run backtest
    result = backtest(
        config=config,
        routes=routes,
        data_routes=[],  # No data routes needed
        candles=candles,
        # strategies={'Perrobotillo': Perrobotillo},  # loaded from file
    )
    
    return result

def load_trade_history():
    """Load Perrobotillo's production trade history."""
    history_path = os.path.expanduser('~/.openclaw/workspace/crypto-bots/trade-history.json')
    with open(history_path) as f:
        return json.load(f)

def compare_results(bt_result, trade_history):
    """Compare Jesse backtest results with Perrobotillo production trades."""
    print("\n=== STEP 4: Comparison ===")
    
    # Parse Jesse backtest results
    # (This depends on the backtest() return format)
    
    # Parse production trade history
    trades = trade_history.get('trades', [])
    pnls = [t.get('pnlUSDT', 0) for t in trades if t.get('pnlUSDT') is not None]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    
    print("\n📊 Perrobotillo Production (last 90 days window):")
    print(f"  Total trades: {len(trades)}")
    print(f"  Win rate: {len(wins)/len(pnls)*100:.1f}%" if pnls else "  Win rate: N/A")
    print(f"  Total PnL: ${sum(pnls):+.2f} USDT")
    print(f"  Avg win: ${sum(wins)/len(wins):+.2f}" if wins else "  Avg win: N/A")
    print(f"  Avg loss: ${sum(losses)/len(losses):+.2f}" if losses else "  Avg loss: N/A")
    
    # Per-coin
    by_coin = {}
    for t in trades:
        coin = t.get('coin', '?')
        if coin not in by_coin:
            by_coin[coin] = {'wins': 0, 'losses': 0, 'pnls': []}
        by_coin[coin]['pnls'].append(t.get('pnlUSDT', 0))
        if t.get('pnlUSDT', 0) > 0:
            by_coin[coin]['wins'] += 1
        elif t.get('pnlUSDT', 0) < 0:
            by_coin[coin]['losses'] += 1
    
    print("\n  Per-coin:")
    for coin in COINS:
        if coin in by_coin:
            s = by_coin[coin]
            total = s['wins'] + s['losses']
            wr = s['wins']/total*100 if total > 0 else 0
            print(f"    {coin:6s} | W:{s['wins']:3d} L:{s['losses']:3d} | WR:{wr:5.1f}% | PnL:{sum(s['pnls']):+.2f}")
    
    print("\n📊 Jesse Backtest (Perrobotillo strategy):")
    print(f"  {bt_result}")

if __name__ == '__main__':
    import_all_candles()
    print("\n✅ Candle import complete!")
    print("Now configure routes in the dashboard and run backtests via the UI.")
    print("Dashboard: http://localhost:9000")
