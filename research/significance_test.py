"""
Rule significance test — per coin (Jesse requires exactly 1 route).
Test coin: ETH (production best: 71 trades, 77.5% WR, +$113.62)
"""
import sys, datetime, json, traceback
sys.path.insert(0, '/home')
from jesse.research import get_candles, rule_significance_test

EXCHANGE = 'Binance Spot'
TIMEFRAME = '1h'
TEST_COIN = 'ETH'  # Best production performer

start_ms = int(datetime.datetime(2026, 1, 18).timestamp() * 1000)
end_ms = int(datetime.datetime(2026, 4, 18, 18).timestamp() * 1000)

# Load test coin + BTC (data route for market mode detection)
candles = {}
for coin in [TEST_COIN, 'BTC']:
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

routes = [{
    'exchange': EXCHANGE,
    'symbol': f'{TEST_COIN}-USDT',
    'timeframe': TIMEFRAME,
    'strategy': 'perrobotillo',
    'stake': 1000.0,
}]

data_routes = [{'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'}]

config = {
    'starting_balance': 10000,
    'fee': 0.001,
    'type': 'spot',
    'simulation_model': 'spot',
    'exchange': EXCHANGE,
    'warm_up_candles': 200,
}

print(f'Running Rule Significance Test for {TEST_COIN}-USDT (100 simulations)...')

try:
    result = rule_significance_test(
        config=config,
        routes=routes,
        data_routes=data_routes,
        candles=candles,
        n_simulations=100,
        progress_bar=True,
        cpu_cores=None,
        random_seed=42,
    )

    print('\n✅ Significance test completed!')

    if isinstance(result, dict):
        print(f'Keys: {list(result.keys())[:10]}')
        for key, value in result.items():
            if isinstance(value, dict):
                print(f'\n  {key}:')
                for k, v in list(value.items())[:15]:
                    print(f'    {k}: {v}')
            elif isinstance(value, (list, tuple)):
                print(f'  {key}: {value[:5]}')
            else:
                print(f'  {key}: {value}')

    with open('/home/research/significance_test_results.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print('\nResults saved')

except Exception as e:
    print(f'Error: {e}')
    traceback.print_exc()
