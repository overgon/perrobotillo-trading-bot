"""Monte Carlo simulation - reduced scenarios for stability."""
import sys, datetime, json, traceback
sys.path.insert(0, '/home')
from jesse.research import get_candles, monte_carlo_trades

COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
EXCHANGE = 'Binance Spot'
TIMEFRAME = '1h'

start_ms = int(datetime.datetime(2026, 1, 18).timestamp() * 1000)
end_ms = int(datetime.datetime(2026, 4, 18, 18).timestamp() * 1000)

candles = {}
for coin in COINS:
    symbol = f'{coin}-USDT'
    result = get_candles(EXCHANGE, symbol, '1m', start_ms, end_ms)
    if isinstance(result, tuple):
        c = result[1] if result[0] is None else result[0]
    else:
        c = result
    if c is not None and len(c) > 0:
        key = f'{EXCHANGE}-{symbol}'
        candles[key] = {'exchange': EXCHANGE, 'symbol': symbol, 'candles': c}
        print(f'  OK: {symbol} {len(c)} candles')

routes = []
for coin in COINS:
    routes.append({
        'exchange': EXCHANGE,
        'symbol': f'{coin}-USDT',
        'timeframe': TIMEFRAME,
        'strategy': 'perrobotillo',
        'stake': 1000.0,
    })

data_routes = [{'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'}]

config = {
    'starting_balance': 70000,
    'fee': 0.001,
    'type': 'spot',
    'simulation_model': 'spot',
    'exchange': EXCHANGE,
    'warm_up_candles': 200,
}

print('Running Monte Carlo (50 scenarios, fast mode)...')

try:
    result = monte_carlo_trades(
        config=config,
        routes=routes,
        data_routes=data_routes,
        candles=candles,
        fast_mode=True,
        num_scenarios=50,
        progress_bar=True,
        cpu_cores=None,
    )
    print('Monte Carlo completed!')

    if isinstance(result, tuple) and len(result) >= 2:
        mc_results, stats = result[0], result[1]
    elif isinstance(result, dict):
        mc_results = result.get('results', [])
        stats = result.get('stats', {})
    else:
        mc_results = []
        stats = {}

    print(f'Stats type: {type(stats)}')
    if hasattr(stats, 'keys'):
        print(f'Keys: {list(stats.keys())[:10]}')
        for k, v in stats.items():
            print(f'  {k}: {v}')

    with open('/home/research/mc_trades_results.json', 'w') as f:
        json.dump({'stats': dict(stats) if hasattr(stats, '__dict__') else stats,
                   'num_scenarios': 50}, f, indent=2, default=str)
    print('Results saved')

except Exception as e:
    print(f'Error: {e}')
    traceback.print_exc()
