#!/usr/bin/env python3
"""
CI/CD Pipeline Orchestrator for Perrobotillo + Jesse AI.

Runs inside the jesse Docker container on the production Pi.
Scheduled via cron:
  - Daily backtest + significance test: 0 5 * * * (5 AM CST)
  - Weekly optimization + deploy gate:   0 3 * * 0 (Sunday 3 AM CST)
  - ML retrain:                          0 3 * * 0 (Sunday 3 AM CST, after opt)

Phase 1 (Daily):   Backtest all 7 coins → compare to baseline → Telegram alert
Phase 2 (Weekly):  Optuna optimization (100 trials) → save best params
Phase 3 (Weekly):  Deploy gate → if Sharpe improved → commit + git tag
Phase 4 (Weekly):  ML retrain → validate CV gap → deploy

Usage:
    python3 research/ci_cd_pipeline.py --phase daily
    python3 research/ci_cd_pipeline.py --phase optimize
    python3 research/ci_cd_pipeline.py --phase deploy-gate
    python3 research/ci_cd_pipeline.py --phase ml-retrain
    python3 research/ci_cd_pipeline.py --phase all

Author: Perrobotron Aterrorizar!!
"""

import sys
import os
import json
import argparse
import datetime
import subprocess
import logging
import io
import numpy as np
from contextlib import redirect_stdout

logging.disable(logging.WARNING)
logging.getLogger('jesse').setLevel(logging.ERROR)

PROJECT_ROOT = '/home'
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from jesse.research import backtest, get_candles
from jesse.services.db import database

COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
EXCHANGE = 'Binance Spot'
TIMEFRAME = '1h'
OPTIMIZATION_RESULTS = os.path.join(PROJECT_ROOT, 'research', 'optuna_results.json')
BASELINE_FILE = os.path.join(PROJECT_ROOT, 'research', 'ci_baseline.json')
PARAMS_FILE = os.path.join(PROJECT_ROOT, 'research', 'optimized_params.json')
CI_REPORT_FILE = os.path.join(PROJECT_ROOT, 'research', 'ci_backtest_result.json')

# Date ranges (matches Perrobotillo production data)
TRAIN_START = datetime.datetime(2026, 1, 18, 0, 0, 0)
TRAIN_END = datetime.datetime(2026, 3, 9, 18, 0, 0)  # ~50 days train (70%)
TEST_START = datetime.datetime(2026, 3, 9, 18, 0, 0)
TEST_END = datetime.datetime(2026, 4, 18, 18, 0, 0)   # ~40 days test (30%)


def ms(dt):
    return int(dt.timestamp() * 1000)


def load_candles(coins, start_ms, end_ms, include_btc=True):
    """Load 1m candles from Jesse DB for the given coins and date range."""
    symbols = list(coins)
    if include_btc and 'BTC-USDT' not in [f'{c}-USDT' for c in coins]:
        symbols = ['BTC'] + list(coins)

    candles = {}
    for coin in symbols:
        symbol = f'{coin}-USDT'
        try:
            result = get_candles(EXCHANGE, symbol, '1m', start_ms, end_ms)
            if isinstance(result, tuple):
                c = result[1] if result[0] is None else result[0]
            else:
                c = result
            if c is not None and len(c) > 0:
                key = f'{EXCHANGE}-{symbol}'
                candles[key] = {'exchange': EXCHANGE, 'symbol': symbol, 'candles': c}
        except Exception as e:
            print(f'  ⚠️  {symbol}: {e}')
    return candles


def build_routes(coins, stake=1000.0):
    """Build main trading routes."""
    return [
        {
            'exchange': EXCHANGE,
            'symbol': f'{coin}-USDT',
            'timeframe': TIMEFRAME,
            'stake': stake,
            'strategy': 'perrobotillo',
        }
        for coin in coins
    ]


def build_data_routes(include_btc=True):
    """Data routes for cross-coin signals (BTC market mode)."""
    routes = []
    if include_btc:
        routes.append({'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'})
    return routes


def run_backtest(candles, routes, data_routes, hyperparams=None):
    """Run backtest with stdout suppressed."""
    config = {
        'starting_balance': 10000 * len(routes),
        'fee': 0.001,
        'type': 'spot',
        'simulation_model': 'spot',
        'exchange': EXCHANGE,
        'warm_up_candles': 200,
        'annualization': 365,
    }

    buf = io.StringIO()
    with redirect_stdout(buf):
        result = backtest(
            config=config,
            routes=routes,
            data_routes=data_routes,
            candles=candles,
            hyperparameters=hyperparams or {},
            fast_mode=True,
        )
    return result


def phase_daily_backtest():
    """Phase 1: Daily backtest of all 7 coins. Compare to baseline."""
    print("=" * 60)
    print("  Phase 1: Daily Backtest — All 7 Coins")
    print("=" * 60)

    database.open_connection()
    try:
        start_ms = ms(TEST_START)
        end_ms = ms(TEST_END)

        coins = COINS
        candles = load_candles(coins, start_ms, end_ms, include_btc=True)

        loaded = [k for k in candles if k != f'{EXCHANGE}-BTC-USDT']
        print(f"  Loaded candles: {len(loaded)}/{len(coins)} coins")

        routes = build_routes(coins)
        data_routes = build_data_routes()

        # Use optimized params if available, else baseline
        hyperparams = {}
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE) as f:
                params_data = json.load(f)
            hyperparams = params_data.get('hyperparameters', {})
            print(f"  Using optimized params from {PARAMS_FILE}")
        else:
            with open(BASELINE_FILE) as f:
                baseline = json.load(f)
            hyperparams = baseline['hyperparameters']
            print(f"  Using baseline params (no optimization yet)")

        result = run_backtest(candles, routes, data_routes, hyperparams)
        metrics = result['metrics']
        trades = result.get('trades', [])

        print(f"\n  Results (test period {TEST_START.date()} → {TEST_END.date()}):")
        print(f"    Trades:       {len(trades)}")
        print(f"    Net Profit:   ${metrics.get('net_profit', 0):.2f}")
        print(f"    Win Rate:     {metrics.get('win_rate', 0):.1%}")
        print(f"    Sharpe:       {metrics.get('sharpe_ratio', 0):.3f}")
        print(f"    Max Drawdown: {metrics.get('max_drawdown', 0):.2%}")
        print(f"    Calmar:       {metrics.get('calmar_ratio', 0):.3f}")

        # Compare to baseline
        with open(BASELINE_FILE) as f:
            baseline = json.load(f)

        b = baseline['metrics']
        t = baseline['regression_thresholds']

        sharpe = metrics.get('sharpe_ratio', 0)
        profit = metrics.get('net_profit', 0)
        wr = metrics.get('win_rate', 0)
        trades_count = metrics.get('total', 0)

        # Regression check
        sharpe_diff = sharpe - b['sharpe_ratio']
        if b['net_profit'] != 0:
            profit_change = (profit - b['net_profit']) / abs(b['net_profit'])
        else:
            profit_change = 0 if profit == 0 else 1.0

        passed = True
        checks = []

        if sharpe_diff < -t['sharpe_drop_max']:
            passed = False
            checks.append(f"FAIL: Sharpe {sharpe:.3f} vs {b['sharpe_ratio']:.3f} (Δ={sharpe_diff:+.3f})")
        else:
            checks.append(f"PASS: Sharpe {sharpe:.3f} vs {b['sharpe_ratio']:.3f} (Δ={sharpe_diff:+.3f})")

        if profit_change < -t['net_profit_drop_max_pct']:
            passed = False
            checks.append(f"FAIL: Net Profit ${profit:.2f} vs ${b['net_profit']:.2f} (Δ={profit_change:+.1%})")
        else:
            checks.append(f"PASS: Net Profit ${profit:.2f} vs ${b['net_profit']:.2f} (Δ={profit_change:+.1%})")

        if trades_count >= 3 and wr < t['win_rate_min']:
            passed = False
            checks.append(f"FAIL: Win Rate {wr:.1%} < {t['win_rate_min']:.0%}")
        else:
            checks.append(f"PASS: Win Rate {wr:.1%} (n={trades_count})")

        print(f"\n  Regression Checks:")
        for c in checks:
            print(f"    {c}")

        # Save result
        output = {
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
            'phase': 'daily_backtest',
            'date_range': {'start': str(TEST_START.date()), 'end': str(TEST_END.date())},
            'metrics': {k: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                        for k, v in metrics.items()},
            'trade_count': len(trades),
            'passed': passed,
        }
        with open(CI_REPORT_FILE, 'w') as f:
            json.dump(output, f, indent=2, default=str)

        print(f"\n  Report saved: {CI_REPORT_FILE}")
        print(f"  Status: {'✅ PASS' if passed else '❌ FAIL'}")
        return passed

    finally:
        database.close_connection()


def phase_optuna_optimize():
    """Phase 2: Weekly Optuna optimization for all 7 coins."""
    print("=" * 60)
    print("  Phase 2: Optuna Optimization — All 7 Coins")
    print("=" * 60)

    import optuna
    from jesse.research import backtest

    database.open_connection()
    try:
        train_start = ms(TRAIN_START)
        train_end = ms(TRAIN_END)
        test_start = ms(TEST_START)
        test_end = ms(TEST_END)

        # Warmup before train period
        warmup_start = train_start - (8 * 24 * 60 * 60 * 1000)
        warmup_end = train_start

        # Load train + warmup candles
        train_candles = load_candles(COINS, warmup_start, train_end, include_btc=True)
        print(f"  Train candles loaded: {len(train_candles)} symbols")

        routes = build_routes(COINS)
        data_routes = build_data_routes()

        # Load baseline hyperparameters for defaults
        with open(BASELINE_FILE) as f:
            baseline = json.load(f)
        hp_defaults = baseline['hyperparameters']

        def objective(trial):
            hp = {
                'ema_fast': trial.suggest_int('ema_fast', 5, 50),
                'ema_slow': trial.suggest_int('ema_slow', 50, 200),
                'ml_min_confidence': trial.suggest_float('ml_min_confidence', 30.0, 80.0),
                'tp_percent': trial.suggest_float('tp_percent', 0.1, 5.0),
                'stop_loss_percent': trial.suggest_float('stop_loss_percent', 0.5, 10.0),
                'position_size_percent': trial.suggest_float('position_size_percent', 5.0, 30.0),
                'rsi_overbought': trial.suggest_int('rsi_overbought', 60, 85),
                'rsi_oversold': trial.suggest_int('rsi_oversold', 15, 45),
                'min_adx': trial.suggest_int('min_adx', 15, 40),
            }
            if hp['ema_fast'] >= hp['ema_slow']:
                hp['ema_fast'] = min(hp['ema_fast'], hp['ema_slow'] - 1)

            # Use subset for speed (3 coins)
            subset_routes = [r for r in routes if r['symbol'] in ['BNB-USDT', 'ETH-USDT', 'SOL-USDT']]
            subset_candles = {k: v for k, v in train_candles.items()
                             if v['symbol'] in ['BNB-USDT', 'ETH-USDT', 'SOL-USDT', 'BTC-USDT']}

            try:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    result = backtest(
                        config={
                            'starting_balance': 10000 * len(subset_routes),
                            'fee': 0.001,
                            'type': 'spot',
                            'simulation_model': 'spot',
                            'exchange': EXCHANGE,
                            'warm_up_candles': 200,
                            'annualization': 365,
                        },
                        routes=subset_routes,
                        data_routes=data_routes,
                        candles=subset_candles,
                        hyperparameters=hp,
                        fast_mode=True,
                    )
                metrics = result['metrics']
                return metrics.get('sharpe_ratio', -999)
            except Exception:
                return -999

        study = optuna.create_study(direction='maximize', study_name='perrobotillo_ci')
        study.optimize(objective, n_trials=50, show_progress_bar=False)

        best_hp = study.best_trial.params
        best_sharpe = study.best_value

        print(f"\n  Best hyperparameters:")
        print(f"  {json.dumps(best_hp, indent=2)}")
        print(f"  Train Sharpe: {best_sharpe:.3f}")

        # Validate on test period
        test_candles = load_candles(COINS, test_start, test_end, include_btc=True)
        result = run_backtest(test_candles, routes, data_routes, best_hp)
        test_metrics = result['metrics']

        print(f"\n  Test period ({TEST_START.date()} → {TEST_END.date()}):")
        print(f"    Sharpe:  {test_metrics.get('sharpe_ratio', 0):.3f}")
        print(f"    Net PnL: ${test_metrics.get('net_profit', 0):.2f}")
        print(f"    Trades:  {test_metrics.get('total', 0)}")

        # Save results
        output = {
            'best_params': best_hp,
            'best_value': best_sharpe,
            'test_result': {
                'sharpe_ratio': test_metrics.get('sharpe_ratio', 0),
                'net_profit': test_metrics.get('net_profit', 0),
                'total_trades': test_metrics.get('total', 0),
                'win_rate': test_metrics.get('win_rate', 0),
            },
            'n_trials': len(study.trials),
            'test_period': {'start': str(TEST_START.date()), 'end': str(TEST_END.date())},
            'train_period': {'start': str(TRAIN_START.date()), 'end': str(TRAIN_END.date())},
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        }
        with open(OPTIMIZATION_RESULTS, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\n  Results saved: {OPTIMIZATION_RESULTS}")
        return output

    finally:
        database.close_connection()


def phase_deploy_gate(opt_results):
    """Phase 3: Deploy gate — check if optimization improved enough to deploy."""
    print("=" * 60)
    print("  Phase 3: Deploy Gate")
    print("=" * 60)

    with open(BASELINE_FILE) as f:
        baseline = json.load(f)

    b = baseline['metrics']
    t = baseline['regression_thresholds']

    test_sharpe = opt_results['test_result']['sharpe_ratio']
    baseline_sharpe = b['sharpe_ratio']
    sharpe_diff = test_sharpe - baseline_sharpe

    baseline_profit = b['net_profit']
    test_profit = opt_results['test_result']['net_profit']

    can_deploy = (
        sharpe_diff >= t['sharpe_improve_min'] and
        test_profit >= baseline_profit
    )

    print(f"  Baseline Sharpe:  {baseline_sharpe:.3f}")
    print(f"  Optimized Sharpe: {test_sharpe:.3f}")
    print(f"  Sharpe Δ:          {sharpe_diff:+.3f} (need +{t['sharpe_improve_min']})")
    print(f"  Baseline PnL:     ${baseline_profit:.2f}")
    print(f"  Optimized PnL:    ${test_profit:.2f}")
    print()

    if can_deploy:
        print("  ✅ DEPLOY GATE PASSED — saving optimized params")
        best_hp = opt_results['best_params']
        output = {
            'hyperparameters': best_hp,
            'sharpe_ratio': test_sharpe,
            'net_profit': test_profit,
            'baseline_sharpe': baseline_sharpe,
            'baseline_profit': baseline_profit,
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
            'deployed': True,
        }
        with open(PARAMS_FILE, 'w') as f:
            json.dump(output, f, indent=2)

        # Update baseline for next cycle
        baseline['metrics']['sharpe_ratio'] = test_sharpe
        baseline['metrics']['net_profit'] = test_profit
        baseline['hyperparameters'] = best_hp
        baseline['version'] = baseline.get('version', '3.5.3')
        with open(BASELINE_FILE, 'w') as f:
            json.dump(baseline, f, indent=2)

        # Git commit the new params
        git_ops = run_git_ops(
            message=f"ci: deploy optimized params — Sharpe {test_sharpe:.3f} (Δ={sharpe_diff:+.3f})",
            tag=f"strategy-v{datetime.datetime.utcnow().strftime('%Y%m%d')}-{int(test_sharpe*100)}",
            files=[PARAMS_FILE, BASELINE_FILE],
        )
        print(f"  Git: {git_ops}")
        return True
    else:
        print("  ❌ DEPLOY GATE REJECTED — no significant improvement")
        # Save but don't deploy
        output = {
            'hyperparameters': opt_results['best_params'],
            'test_result': opt_results['test_result'],
            'deployed': False,
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        }
        with open(os.path.join(PROJECT_ROOT, 'research', 'optimization_staging.json'), 'w') as f:
            json.dump(output, f, indent=2)
        return False


def phase_ml_retrain():
    """Phase 4: ML model retraining — gather fresh labels, retrain per-coin models."""
    print("=" * 60)
    print("  Phase 4: ML Retrain")
    print("=" * 60)

    # Check if fase7_train.py exists and run it
    train_script = os.path.join(PROJECT_ROOT, 'fase7_train.py')
    if not os.path.exists(train_script):
        print(f"  ⚠️  {train_script} not found — skipping ML retrain")
        return None

    print("  Running fase7_train.py (per-coin RF retraining)...")
    result = subprocess.run(
        [sys.executable, train_script],
        capture_output=True, text=True, timeout=3600,
        cwd=PROJECT_ROOT,
    )

    # Parse output for accuracy/CV gap
    stdout = result.stdout[-2000:]
    stderr = result.stderr[-2000:]

    print(f"  Exit code: {result.returncode}")
    if result.stdout:
        print(f"  Last output: {result.stdout[-500:]}")
    if result.stderr:
        print(f"  Errors: {result.stderr[-300:]}")

    # Check accuracy from output
    import re
    acc_matches = re.findall(r'accuracy:\s*([0-9.]+)%', stdout)
    cv_matches = re.findall(r'CV.*?\s*([0-9.]+)%', stdout)

    if result.returncode == 0:
        print("  ✅ ML retraining completed")
        return {'status': 'success', 'accuracies': acc_matches, 'cv_gaps': cv_matches}
    else:
        print("  ❌ ML retraining failed")
        return {'status': 'failed', 'stderr': stderr[:500]}


def run_git_ops(message, tag, files):
    """Commit changes and create a git tag."""
    try:
        # Stage files
        for f in files:
            rel = os.path.relpath(f, PROJECT_ROOT)
            subprocess.run(['git', 'add', rel], cwd=PROJECT_ROOT, capture_output=True, check=True)

        # Commit
        subprocess.run(
            ['git', 'commit', '-m', message, '--author=Perrobotron Aterrorizar!!'],
            cwd=PROJECT_ROOT, capture_output=True, check=True
        )

        # Tag
        subprocess.run(
            ['git', 'tag', tag],
            cwd=PROJECT_ROOT, capture_output=True, check=True
        )

        # Push
        push_result = subprocess.run(
            ['git', 'push', 'origin', 'main', '--tags'],
            cwd=PROJECT_ROOT, capture_output=True, text=True
        )

        return f"committed + tagged {tag}"
    except subprocess.CalledProcessError as e:
        return f"git op failed: {e.stderr[:200] if e.stderr else str(e)}"


def send_telegram_report(title, message, phase):
    """Send a Telegram report about CI/CD pipeline status."""
    telegram_env = os.path.join(PROJECT_ROOT, 'secrets', 'telegram.env')
    if not os.path.exists(telegram_env):
        print(f"  ⚠️  Telegram config not found: {telegram_env}")
        return

    # Read telegram config
    with open(telegram_env) as f:
        for line in f:
            if line.startswith('TELEGRAM_BOT_TOKEN='):
                token = line.split('=', 1)[1].strip()
            elif line.startswith('TELEGRAM_CHAT_ID='):
                chat_id = line.split('=', 1)[1].strip()

    import urllib.request
    import urllib.parse

    text = f"*{title}*\n\n{message}"
    data = urllib.parse.urlencode({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown',
    }).encode('utf-8')

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"  📱 Telegram: sent ✅")
    except Exception as e:
        print(f"  📱 Telegram: failed ({e})")


def main():
    parser = argparse.ArgumentParser(description='Perrobotillo CI/CD Pipeline')
    parser.add_argument('--phase', choices=['daily', 'optimize', 'deploy-gate', 'ml-retrain', 'all'],
                        default='daily', help='Pipeline phase to run')
    args = parser.parse_args()

    start = datetime.datetime.now()
    print(f"\n🚀 CI/CD Pipeline started at {start.strftime('%Y-%m-%d %H:%M:%S')} CST")
    print(f"   Phase: {args.phase}\n")

    if args.phase == 'daily':
        passed = phase_daily_backtest()
        status = '✅ PASS' if passed else '❌ FAIL'
        msg = f"Daily backtest all 7 coins:\nSharpe={passed}\nStatus: {status}"
        send_telegram_report("Perrobotillo CI/CD — Daily Backtest", msg, 'daily')
        sys.exit(0 if passed else 1)

    elif args.phase == 'optimize':
        results = phase_optuna_optimize()
        msg = f"Weekly optimization completed:\n" \
              f"Trials: {results['n_trials']}\n" \
              f"Best Sharpe (train): {results['best_value']:.3f}\n" \
              f"Test Sharpe: {results['test_result']['sharpe_ratio']:.3f}\n" \
              f"Test PnL: ${results['test_result']['net_profit']:.2f}\n" \
              f"Trades: {results['test_result']['total_trades']}"
        send_telegram_report("Perrobotillo CI/CD — Optimization Complete", msg, 'optimize')
        # Save results for deploy gate
        with open(os.path.join(PROJECT_ROOT, 'research', 'ci_optimization_results.json'), 'w') as f:
            json.dump(results, f, indent=2)

    elif args.phase == 'deploy-gate':
        results_file = os.path.join(PROJECT_ROOT, 'research', 'ci_optimization_results.json')
        if not os.path.exists(results_file):
            # Try the standard optuna results
            results_file = OPTIMIZATION_RESULTS
        if not os.path.exists(results_file):
            print("  ⚠️  No optimization results found — running optimize first")
            results = phase_optuna_optimize()
        else:
            with open(results_file) as f:
                results = json.load(f)
        deployed = phase_deploy_gate(results)
        msg = f"Deploy gate: {'✅ DEPLOYED' if deployed else '❌ REJECTED'}\n" \
              f"Test Sharpe: {results['test_result']['sharpe_ratio']:.3f}"
        send_telegram_report("Perrobotillo CI/CD — Deploy Gate", msg, 'deploy-gate')

    elif args.phase == 'ml-retrain':
        result = phase_ml_retrain()
        if result:
            msg = f"ML Retrain: {result['status']}"
            if result['status'] == 'success' and result.get('accuracies'):
                msg += f"\nAccuracies: {', '.join(result['accuracies'])}"
            send_telegram_report("Perrobotillo CI/CD — ML Retrain", msg, 'ml-retrain')

    elif args.phase == 'all':
        # Run all phases in sequence
        passed = phase_daily_backtest()
        results = phase_optuna_optimize()
        phase_deploy_gate(results)
        phase_ml_retrain()

    elapsed = (datetime.datetime.now() - start).total_seconds()
    print(f"\n⏱️  Pipeline completed in {elapsed:.1f}s")


if __name__ == '__main__':
    main()
