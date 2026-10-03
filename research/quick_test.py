"""
Quick backtest test - single coin (BNB) to validate the pipeline.
Uses 1m candles (Jesse stores and validates 1m candles internally).
"""
import sys
import os
import datetime
import numpy as np

sys.path.insert(0, '/home')

from jesse.research import backtest, get_candles

# Date range matching Perrobotillo's 90-day data
start_ms = int(datetime.datetime(2026, 1, 18).timestamp() * 1000)
end_ms = int(datetime.datetime(2026, 4, 18, 18).timestamp() * 1000)

# Load 1m candles for each coin
print("Loading 1m candles...")
candles = {}

coins_for_test = ['BNB-USDT', 'BTC-USDT']

for symbol in coins_for_test:
    c = get_candles('Binance Spot', symbol, '1m', start_ms, end_ms)
    if isinstance(c, tuple):
        c = c[1]  # data is in second element
    if c is not None and len(c) > 0:
        key = f'Binance Spot-{symbol}'
        candles[key] = {
            'exchange': 'Binance Spot',
            'symbol': symbol,
            'candles': c,
        }
        print(f'  ✅ {symbol}: {len(c)} 1m rows | {datetime.datetime.fromtimestamp(c[0][0]/1000)}')
    else:
        print(f'  ❌ {symbol}: failed to load')

# Data routes (BTC for market mode detection)
data_routes = [
    {'exchange': 'Binance Spot', 'symbol': 'BTC-USDT', 'timeframe': '1h'},
]

# Main route - just BNB for testing
routes = [
    {'exchange': 'Binance Spot', 'symbol': 'BNB-USDT', 'timeframe': '1h', 'strategy': 'perrobotillo', 'stake': 100},
]

config = {
    'starting_balance': 10000,
    'fee': 0.001,  # 0.1% Binance spot taker fee
    'type': 'spot',
    'simulation_model': 'spot',
    'annualization': 365,
    'exchange': 'Binance Spot',
    'warm_up_candles': 200,  # ~3.3 hours of 1m candles for indicator warmup
}

print(f"\nRunning backtest for BNB...")
try:
    result = backtest(
        config=config,
        routes=routes,
        data_routes=data_routes,
        candles=candles,
        generate_json=True,
    )
    print(f"\n✅ Backtest completed!")
    if isinstance(result, dict):
        for k, v in sorted(result.items()):
            print(f"  {k}: {v}")
    else:
        print(f"  Result: {result}")
except Exception as e:
    import traceback
    print(f"❌ Backtest failed: {e}")
    traceback.print_exc()
