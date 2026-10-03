"""
Fase 4: Optuna hyperparameter optimization for Perrobotillo strategy.
Uses Jesse research.optimize() (Optuna Bayesian). Objective: Sharpe.
Train/test split: 70% training (Jan 18-Mar 9), 30% testing (Mar 9-Apr 18).
"""
import sys, datetime, json, traceback, numpy as np
sys.path.insert(0, '/home')
from jesse.research import get_candles, optimize

EXCHANGE = 'Binance Spot'
TIMEFRAME = '1h'
TEST_COIN = 'ETH'

full_start = int(datetime.datetime(2026, 1, 18).timestamp() * 1000)
full_end = int(datetime.datetime(2026, 4, 18, 18).timestamp() * 1000)
train_end = int(datetime.datetime(2026, 3, 9).timestamp() * 1000)
test_end = full_end

# Warmup: ~8 days of 1h candles = ~12K 1m candles before each period
train_warmup_start = full_start
train_warmup_end = full_start + (8 * 24 * 60 * 60 * 1000)
test_warmup_start = train_end - (8 * 24 * 60 * 60 * 1000)
test_warmup_end = train_end

def load_period(symbol, start_ts, end_ts):
    result = get_candles(EXCHANGE, symbol, '1m', start_ts, end_ts)
    if isinstance(result, tuple):
        c = result[1] if result[0] is None else result[0]
    else:
        c = result
    return c if c is not None else np.array([])

def build_candles(start_ts, end_ts):
    d = {}
    for coin in [TEST_COIN, 'BTC']:
        symbol = f'{coin}-USDT'
        c = load_period(symbol, start_ts, end_ts)
        if len(c) > 0:
            d[f'{EXCHANGE}-{symbol}'] = {'exchange': EXCHANGE, 'symbol': symbol, 'candles': c}
            print(f'  {symbol}: {len(c)} candles')
    return d

print("=== Optuna Optimization (ETH-USDT, 50 trials) ===\n")
print(f"  Training:     Jan 18 to Mar 9")
print(f"  Testing:      Mar 9 to Apr 18")
print(f"  Warmup:       8 days before each period\n")

print("Loading candles...")
train_warmup = build_candles(train_warmup_start, train_warmup_end)
train_candles = build_candles(train_warmup_end, train_end)
test_warmup = build_candles(test_warmup_start, test_warmup_end)
test_candles = build_candles(train_end, test_end)

total_all = sum(len(v["candles"]) for v in {**train_warmup, **train_candles, **test_warmup, **test_candles}.values())
print(f"\nTotal candles loaded: {total_all}")

routes = [{
    'exchange': EXCHANGE,
    'symbol': f'{TEST_COIN}-USDT',
    'timeframe': TIMEFRAME,
    'strategy': 'perrobotillo',
    'stake': 10000.0,
}]

data_routes = [{'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'}]

config = {
    'starting_balance': 10000,
    'fee': 0.001,
    'type': 'spot',
    'simulation_model': 'spot',
    'exchange': {'name': 'Binance Spot'},
    'warm_up_candles': 200,
}

print("\nRunning Optuna optimization (50 trials, objective=sharpe)...")

try:
    result = optimize(
        config=config,
        routes=routes,
        data_routes=data_routes,
        training_candles=train_candles,
        training_warmup_candles=train_warmup,
        testing_candles=test_candles,
        testing_warmup_candles=test_warmup,
        fast_mode=True,
        trials=50,
        objective_function='sharpe',
        best_candidates_count=5,
        progress_bar=True,
    )

    print("\nOptimization completed!")

    if hasattr(result, '_asdict'):
        result = result._asdict()
    elif not isinstance(result, dict):
        result = {'raw': str(result)}

    print(f"Result type: {type(result)}")
    if isinstance(result, dict):
        print(f"Keys: {list(result.keys())}")

        if 'best_candidates' in result:
            print("\n=== BEST CANDIDATES (5) ===")
            for i, cand in enumerate(result['best_candidates'][:5]):
                print(f"  #{i+1}: {cand}")

        if 'optimal_hyperparameters' in result:
            print("\n=== OPTIMAL HYPERPARAMETERS ===")
            for k, v in result['optimal_hyperparameters'].items():
                print(f"  {k}: {v}")

    with open('/home/research/optimize_eth_results.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print("\nResults saved to /home/research/optimize_eth_results.json")

except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
