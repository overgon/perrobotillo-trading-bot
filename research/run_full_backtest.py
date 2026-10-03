"""Run full 7-coin backtest with Perrobotillo strategy."""
import sys, datetime, numpy as np
sys.path.insert(0, '/home')
from jesse.research import backtest, get_candles

COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
EXCHANGE = 'Binance Spot'

start_ms = int(datetime.datetime(2026, 1, 18).timestamp() * 1000)
end_ms = int(datetime.datetime(2026, 4, 18, 18).timestamp() * 1000)

# Load 1m candles for all 7 coins
candles = {}
for coin in COINS:
    symbol = f'{coin}-USDT'
    c = get_candles(EXCHANGE, symbol, '1m', start_ms, end_ms)
    if isinstance(c, tuple):
        c = c[1]
    if c is not None and len(c) > 0:
        key = f'{EXCHANGE}-{symbol}'
        candles[key] = {'exchange': EXCHANGE, 'symbol': symbol, 'candles': c}
        print(f'✅ {symbol}: {len(c)} 1m candles')

# Routes: all 7 coins on 1h
routes = []
for coin in COINS:
    routes.append({
        'exchange': EXCHANGE,
        'symbol': f'{coin}-USDT',
        'timeframe': '1h',
        'strategy': 'perrobotillo',
        'stake': 1000.0,
    })

# Data routes: BTC at 1h (already in main routes, but needed for strategy access)
data_routes = [
    {'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'},
]

config = {
    'starting_balance': 70000,  # 10k per coin (7 coins)
    'fee': 0.001,
    'type': 'spot',
    'simulation_model': 'spot',
    'annualization': 365,
    'exchange': EXCHANGE,
    'warm_up_candles': 200,
}

print(f'\nRunning full backtest with {len(routes)} routes...')
print(f'Candles: {sum(len(v["candles"]) for v in candles.values())} total 1m candles')
print(f'This may take a while (~{sum(len(v["candles"]) for v in candles.values()) // 60} hours of 1m data)...\n')

result = backtest(config=config, routes=routes, data_routes=data_routes, candles=candles)

print(f'\n✅ Full backtest completed!')
print(f'  Total PnL: ${result["metrics"]["net_profit"]:+.2f}')
print(f'  Win rate: {result["metrics"]["win_rate"] * 100:.1f}%')
print(f'  Net profit %: {result["metrics"]["net_profit_percentage"]:.2f}%')
print(f'  Total trades: {len(result.get("trades", []))}')

# Per-coin analysis
trades = result.get('trades', [])
by_coin = {}
for t in trades:
    sym = t.get('symbol', 'UNKNOWN')
    if sym not in by_coin:
        by_coin[sym] = []
    by_coin[sym].append(t)

print(f'\n  Per-coin:')
for coin in COINS:
    symbol = f'{coin}-USDT'
    ts = by_coin.get(symbol, [])
    if ts:
        wins = sum(1 for t in ts if t.get('PNL', 0) > 0)
        total = len(ts)
        print(f'    {coin:6s}: N={total:3d}  WR={wins/total*100:5.1f}%')
    else:
        print(f'    {coin:6s}: N=  0  (no trades)')

# Save results
import json
with open('/home/research/backtest_results.json', 'w') as f:
    json.dump({
        'metrics': result['metrics'],
        'trades': trades,
        'per_coin': {k: len(v) for k, v in by_coin.items()},
    }, f, indent=2, default=float)
    print(f'\nResults saved to /home/research/backtest_results.json')
