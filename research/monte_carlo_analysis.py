"""
Monte Carlo simulation for Perrobotillo strategy in Jesse.
Validates that backtest results are not just due to luck.
"""
import sys, datetime, json
sys.path.insert(0, '/home')
from jesse.research import get_candles, monte_carlo_trades

COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
EXCHANGE = 'Binance Spot'
TIMEFRAME = '1h'

start_ms = int(datetime.datetime(2026, 1, 18).timestamp() * 1000)
end_ms = int(datetime.datetime(2026, 4, 18, 18).timestamp() * 1000)


def load_candles():
    """Load 1m candles for all coins."""
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
            print(f'  ✅ {symbol}: {len(c)} 1m candles')
    return candles


def main():
    print("=== Monte Carlo: Trade Shuffling ===\n")
    candles = load_candles()
    print(f'\nLoaded {len(candles)} coins\n')

    # Build routes (same as backtest)
    routes = []
    for coin in COINS:
        routes.append({
            'exchange': EXCHANGE,
            'symbol': f'{coin}-USDT',
            'timeframe': TIMEFRAME,
            'strategy': 'perrobotillo',
            'stake': 1000.0,
        })

    data_routes = [
        {'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'},
    ]

    config = {
        'starting_balance': 70000,
        'fee': 0.001,
        'type': 'spot',
        'simulation_model': 'spot',
        'exchange': EXCHANGE,
        'warm_up_candles': 200,
    }

    print(f'Running Monte Carlo with 200 scenarios (fast mode)...')
    print(f'Coins: {len(routes)}  |  Date range: 2026-01-18 to 2026-04-18')
    print()

    result = monte_carlo_trades(
        config=config,
        routes=routes,
        data_routes=data_routes,
        candles=candles,
        hyperparameters=None,
        fast_mode=True,
        num_scenarios=200,
        progress_bar=True,
        cpu_cores=None,
    )

    # Unpack results
    # MonteCarloTradesReturn is typically (results_array, stats_dict)
    if isinstance(result, tuple):
        results, stats = result[0], result[1]
    else:
        results = result.get('results', [])
        stats = result.get('stats', {})

    # Print summary
    print(f'\n=== Monte Carlo Results (200 scenarios) ===')
    print(f'  Original PnL: ${stats.get("original_pnl", "N/A"):.2f}')
    print(f'  Mean PnL: ${stats.get("mean", 0):.2f}')
    print(f'  Median PnL: ${stats.get("median", 0):.2f}')
    print(f'  Std Dev: ${stats.get("std", 0):.2f}')
    print(f'  Min PnL: ${stats.get("min", 0):.2f}')
    print(f'  Max PnL: ${stats.get("max", 0):.2f}')
    print(f'  Probability of loss: {stats.get("prob_of_loss", 0):.1f}%')
    print(f'  Probability of profit: {stats.get("prob_of_profit", 0):.1f}%')

    # Save results
    output = {
        'stats': stats if isinstance(stats, dict) else {},
        'results_count': len(results) if hasattr(results, '__len__') else 0,
        'num_coins': len(routes),
        'date_range': '2026-01-18 to 2026-04-18',
    }
    with open('/home/research/mc_trades_results.json', 'w') as f:
        json.dump(output, f, indent=2, default=float)

    print(f'\nResults saved to /home/research/mc_trades_results.json')


if __name__ == '__main__':
    main()
