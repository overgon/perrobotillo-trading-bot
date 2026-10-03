"""
Fase 4: Custom Optuna optimization for Perrobotillo.
Unlike Jesse's built-in optimize() which filters score > 0.0001,
this script uses Optuna directly to find the BEST (even if negative) parameters.
Objective: maximize Sharpe ratio.
"""
import sys, os, json, datetime, warnings, traceback
warnings.filterwarnings('ignore')
sys.path.insert(0, '/home')
os.environ['JESSE_CHMOD'] = '0777'

from jesse.research import get_candles, backtest
import numpy as np

# Check if optuna is available
try:
    import optuna
    print(f'Optuna version: {optuna.__version__}')
except ImportError:
    print('Installing optuna...')
    import subprocess
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'optuna'], check=True)
    import optuna
    print(f'Optuna installed: {optuna.__version__}')

EXCHANGE = 'Binance Spot'
TIMEFRAME = '1h'
TEST_COIN = 'ETH'

# Train: Jan 18 - Mar 9, Test: Mar 9 - Apr 18
start_ms = int(datetime.datetime(2026, 1, 18).timestamp() * 1000)
train_end = int(datetime.datetime(2026, 3, 9).timestamp() * 1000)
end_ms = int(datetime.datetime(2026, 4, 18, 18).timestamp() * 1000)

# Warmup: 8 days before training
train_warmup_start = start_ms
train_warmup_end = start_ms + (8 * 24 * 60 * 60 * 1000)
test_warmup_start = train_end - (8 * 24 * 60 * 60 * 1000)
test_warmup_end = train_end

print("=== Optuna Optimization (custom) — ETH-USDT, Sharpe objective ===")
print(f"  Training:  Jan 28 to Mar 9")
print(f"  Testing:   Mar 9 to Apr 18")
print(f"  Trials:    50")


def load_period(symbol, s, e):
    result = get_candles(EXCHANGE, symbol, '1m', s, e)
    if isinstance(result, tuple):
        c = result[1] if result[0] is None else result[0]
    else:
        c = result
    return c if c is not None and len(c) > 0 else np.array([])


def build_candles(start_ts, end_ts):
    d = {}
    for coin in [TEST_COIN, 'BTC']:
        sym = f'{coin}-USDT'
        c = load_period(sym, start_ts, end_ts)
        if len(c) > 0:
            d[f'{EXCHANGE}-{sym}'] = {'exchange': EXCHANGE, 'symbol': sym, 'candles': c}
    return d


def run_backtest_with_hp(hp_values, period='training'):
    """Run backtest with given hyperparameters on specified period."""
    if period == 'training':
        w_start, w_end, t_start, t_end = start_ms, train_warmup_end, train_end - (8*24*60*60*1000), train_end
    else:
        w_start, w_end, t_start, t_end = train_end - (8*24*60*60*1000), train_end, train_end, end_ms

    train_w = build_candles(w_start, w_end)
    train_c = build_candles(w_start + (8*24*60*60*1000) if period == 'training' else w_end, t_end)
    all_candles = {}
    for key in set(list(train_w.keys()) + list(train_c.keys())):
        w = train_w.get(key, {'exchange': EXCHANGE, 'symbol': '', 'candles': np.array([])})
        t = train_c.get(key, {'exchange': EXCHANGE, 'symbol': '', 'candles': np.array([])})
        combined = np.concatenate([w['candles'], t['candles']], axis=0) if len(w['candles']) > 0 and len(t['candles']) > 0 else (t['candles'] if len(t['candles']) > 0 else w['candles'])
        if len(combined) > 0:
            all_candles[key] = {'exchange': w.get('exchange', EXCHANGE), 'symbol': t.get('symbol', w.get('symbol', '')), 'candles': combined}

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
        'exchange': EXCHANGE,
        'warm_up_candles': 200,
    }

    try:
        result = backtest(
            config=config,
            routes=routes,
            data_routes=data_routes,
            candles=all_candles,
            hyperparameters=hp_values,
            fast_mode=True,
        )
        metrics = result['metrics']
        sharpe = metrics.get('sharpe_ratio', -999)
        net_profit = metrics.get('net_profit', 0)
        total_trades = metrics.get('total', 0)
        win_rate = metrics.get('win_rate', 0)
        return {
            'sharpe': float(sharpe) if sharpe and not (isinstance(sharpe, float) and (sharpe != sharpe)) else -999,
            'net_profit': float(net_profit),
            'total_trades': int(total_trades),
            'win_rate': float(win_rate),
        }
    except Exception as e:
        return {'sharpe': -999, 'net_profit': 0, 'total_trades': 0, 'win_rate': 0, 'error': str(e)}


def objective(trial):
    # Define hyperparameter search space
    hp = {
        'tp1_percent': trial.suggest_float('tp1_percent', 1.0, 8.0),
        'tp2_percent': trial.suggest_float('tp2_percent', 3.0, 15.0),
        'tp3_percent': trial.suggest_float('tp3_percent', 5.0, 20.0),
        'stop_loss_percent': trial.suggest_float('stop_loss_percent', 2.0, 8.0),
        'position_size_percent': trial.suggest_float('position_size_percent', 5.0, 20.0),
        'ml_min_confidence': trial.suggest_float('ml_min_confidence', 30.0, 60.0),
        'ema_fast': trial.suggest_int('ema_fast', 10, 50),
        'ema_slow': trial.suggest_int('ema_slow', 50, 200),
    }
    # Ensure ema_fast < ema_slow
    if hp['ema_fast'] >= hp['ema_slow']:
        hp['ema_fast'] = min(hp['ema_fast'], hp['ema_slow'] - 1)

    result = run_backtest_with_hp(hp)
    return result['sharpe']  # Maximize Sharpe (can be negative)


print("\nRunning Optuna study (50 trials)...")
study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50, show_progress_bar=True)

print(f"\n=== Optimization Results ===")
print(f"  Best Sharpe: {study.best_value:.4f}")
print(f"  Best params:")
for k, v in study.best_params.items():
    print(f"    {k}: {v}")

# Evaluate best params on testing data
print("\nEvaluating on TESTING data...")
test_result = run_backtest_with_hp(study.best_params, period='testing')
print(f"  Test Sharpe: {test_result['sharpe']:.4f}")
print(f"  Test PnL: {test_result['net_profit']:.2f}")
print(f"  Test Trades: {test_result['total_trades']}")
print(f"  Test Win Rate: {test_result['win_rate']:.1f}%")

# Save full results
all_trials = []
for trial in study.trials:
    all_trials.append({
        'trial': trial.number,
        'params': trial.params,
        'value': trial.value,
        'state': str(trial.state),
    })

with open('/home/research/optuna_results.json', 'w') as f:
    json.dump({
        'best_params': study.best_params,
        'best_value': study.best_value,
        'test_result': test_result,
        'n_trials': len(study.trials),
        'all_trials': all_trials,
    }, f, indent=2, default=str)

print("\nResults saved to /home/research/optuna_results.json")
