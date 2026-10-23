#!/usr/bin/env python3
"""
CI Backtest Gate — Perrobotillo strategy regression check.

Runs a quick backtest using CSV candle data from backtest/data/ and
compares metrics against research/ci_baseline.json. Designed to run
in GitHub Actions CI or as a local pre-commit hook.

Usage:
    python3 ci_backtest_gate.py [--coins BNB BTC ETH] [--days 14]

Exit codes:
    0 = PASS (no regression)
    1 = FAIL (regression detected)
    2 = ERROR (backtest could not run)

Author: Perrobotron Aterrorizar!!
"""

import sys
import os
import json
import csv as csv_module
import argparse
import datetime
import logging
import io

# ── Suppress verbose Jesse logs ──
logging.disable(logging.WARNING)
logging.getLogger('jesse').setLevel(logging.ERROR)

# Ensure project root is importable (strategies/ directory)
PROJECT_ROOT = os.environ.get('PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from contextlib import redirect_stdout

from jesse.research import backtest

COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
EXCHANGE = 'Binance Spot'
TIMEFRAME = '1h'
DATA_DIR = os.path.join(PROJECT_ROOT, 'backtest', 'data')
RESULTS_FILE = os.path.join(PROJECT_ROOT, 'research', 'ci_backtest_result.json')
BASELINE_FILE = os.path.join(PROJECT_ROOT, 'research', 'ci_baseline.json')


def load_csv_1h(coin: str, days: int) -> 'np.ndarray | None':
    """Load 1h CSV for a coin and expand to 1m candles (Jesse requires 1m)."""
    import numpy as np

    symbol_usdt = f'{coin}USDT'
    csv_path = os.path.join(DATA_DIR, f'{symbol_usdt}_1h_90days.csv')
    if not os.path.exists(csv_path):
        print(f"  ⚠️  CSV not found: {symbol_usdt}")
        return None

    rows = []
    with open(csv_path) as f:
        reader = csv_module.DictReader(f)
        for r in reader:
            rows.append(r)

    hours_needed = min(days * 24, len(rows))
    rows = rows[-hours_needed:]  # use most recent N days

    # Expand each 1h candle → 60 1m candles.
    # Preserves OHLC (important for TP/SL detection); volume / 60 per minute.
    candles_1m = []
    for r in rows:
        ts = datetime.datetime.fromisoformat(r['timestamp'])
        ts_ms = int(ts.timestamp() * 1000)
        o = float(r['open'])
        h = float(r['high'])
        l = float(r['low'])
        c = float(r['close'])
        v = float(r['volume']) / 60.0
        for minute in range(60):
            candles_1m.append([ts_ms + minute * 60000, o, h, l, c, v])

    return np.array(candles_1m, dtype=np.float64)


def run_ci_backtest(coins: list, days: int, hyperparams: dict) -> dict | None:
    """Run a quick backtest for CI gate."""
    import numpy as np

    routes = []
    candles = {}

    # Always include BTC as a data route (strategy calls self.get_candles for BTC)
    all_coins = list(dict.fromkeys(coins + ['BTC']))

    for coin in all_coins:
        symbol = f'{coin}-USDT'
        c = load_csv_1h(coin, days)
        if c is None or len(c) < 240:  # need at least 4h of 1m data
            print(f"  ⚠️  Skipping {coin}: insufficient data ({len(c) if c is not None else 0} candles)")
            continue

        if coin in coins:
            # Main trading route
            routes.append({
                'exchange': EXCHANGE,
                'symbol': symbol,
                'timeframe': TIMEFRAME,
                'stake': 500.0,
                'strategy': 'perrobotillo',
            })

        # Always load BTC candles (needed by strategy's btc_candles property)
        key = f'{EXCHANGE}-{symbol}'
        candles[key] = {
            'exchange': EXCHANGE,
            'symbol': symbol,
            'candles': c,
        }
        print(f"  ✅ {symbol}: {len(c)} 1m candles loaded")

    if not routes:
        print("ERROR: No trading routes configured")
        return None

    # Data routes: BTC for market-mode detection (only if BTC not in main routes)
    data_routes = []
    if 'BTC' not in coins:
        data_routes = [{'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'}]

    config = {
        'starting_balance': 10000,
        'fee': 0.001,
        'type': 'spot',
        'simulation_model': 'spot',
        'exchange': EXCHANGE,
        'warm_up_candles': 200,
    }

    # Capture backtest output (it prints verbose stats)
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = backtest(
            config=config,
            routes=routes,
            data_routes=data_routes,
            candles=candles,
            hyperparameters=hyperparams,
            fast_mode=True,
        )

    return result


def compare_with_baseline(metrics: dict, baseline: dict) -> tuple[bool, list[str]]:
    """Compare backtest metrics against baseline. Returns (passed, check_messages)."""
    b = baseline['metrics']
    t = baseline['regression_thresholds']

    checks = []
    all_pass = True

    # 1. Sharpe ratio
    sharpe = metrics.get('sharpe_ratio', 0)
    b_sharpe = b['sharpe_ratio']
    sharpe_diff = sharpe - b_sharpe
    sharpe_ok = sharpe_diff >= -t['sharpe_drop_max']
    checks.append(f"Sharpe: {sharpe:.3f} vs baseline {b_sharpe:.3f} (Δ={sharpe_diff:+.3f}) {'PASS' if sharpe_ok else 'FAIL'}")
    if not sharpe_ok:
        all_pass = False

    # 2. Net profit
    profit = metrics.get('net_profit', 0)
    b_profit = b['net_profit']
    if abs(b_profit) > 0.01:
        profit_drop = (profit - b_profit) / abs(b_profit)
    else:
        profit_drop = 0.0
    profit_ok = profit_drop >= -t['net_profit_drop_max_pct']
    checks.append(f"Net Profit: ${profit:.2f} vs ${b_profit:.2f} (Δ={profit_drop:+.1%}) {'PASS' if profit_ok else 'FAIL'}")
    if not profit_ok:
        all_pass = False

    # 3. Win rate (only if we have enough trades)
    trades = metrics.get('total', 0)
    if trades >= 3:
        wr = metrics.get('win_rate', 0)
        wr_ok = wr >= t['win_rate_min']
        checks.append(f"Win Rate: {wr:.1%} (min {t['win_rate_min']:.0%}) {'PASS' if wr_ok else 'FAIL'}")
        if not wr_ok:
            all_pass = False
    else:
        checks.append(f"Win Rate: skipped (only {trades} trades)")

    # 4. Trade count sanity
    checks.append(f"Total Trades: {metrics.get('total', 0)}")

    return all_pass, checks


def main():
    parser = argparse.ArgumentParser(description='CI Backtest Gate for Perrobotillo')
    parser.add_argument('--coins', nargs='+', default=['BNB', 'BTC', 'ETH'],
                        help='Coins to backtest (default: BNB BTC ETH)')
    parser.add_argument('--days', type=int, default=14,
                        help='Days of historical data to use (default: 14)')
    parser.add_argument('--baseline', default='research/ci_baseline.json',
                        help='Path to baseline JSON')
    args = parser.parse_args()

    print("=" * 60)
    print("  CI Backtest Gate — Perrobotillo / Jesse 3.4.0")
    print("=" * 60)
    print(f"  Coins: {args.coins}")
    print(f"  Days:  {args.days}")
    print(f"  Timeframe: {TIMEFRAME} (1m candles internally)")
    print()

    # Load baseline
    baseline_path = os.path.join(PROJECT_ROOT, args.baseline)
    if not os.path.exists(baseline_path):
        print(f"ERROR: Baseline file not found: {baseline_path}")
        sys.exit(2)

    with open(baseline_path) as f:
        baseline = json.load(f)

    hyperparams = baseline['hyperparameters']
    print(f"  Hyperparameters: {json.dumps(hyperparams, indent=2)}")
    print()

    # Run backtest
    print("  Loading candles and running backtest...")
    result = run_ci_backtest(args.coins, args.days, hyperparams)

    if result is None:
        print("\n❌ BACKTEST FAILED — could not execute")
        sys.exit(2)

    metrics = result['metrics']
    trades = result.get('trades', [])

    print(f"\n  Results:")
    print(f"    Trades:       {len(trades)}")
    print(f"    Net Profit:   ${metrics.get('net_profit', 0):.2f}")
    print(f"    Win Rate:     {metrics.get('win_rate', 0):.1%}")
    print(f"    Sharpe:       {metrics.get('sharpe_ratio', 0):.3f}")

    # Compare with baseline
    print(f"\n  Regression Checks:")
    passed, checks = compare_with_baseline(metrics, baseline)
    for check in checks:
        print(f"    {check}")

    # Save result for inspection
    output = {
        'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        'jesse_version': os.popen('jesse --version 2>/dev/null').read().strip() or 'unknown',
        'coins': args.coins,
        'days': args.days,
        'metrics': dict(metrics),
        'trade_count': len(trades),
        'passed': passed,
    }
    with open(RESULTS_FILE, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Result saved to: {RESULTS_FILE}")

    print()
    if passed:
        print("✅ CI GATE PASSED — no regression detected")
        print(f"::set-output name=pass::true")
        sys.exit(0)
    else:
        print("❌ CI GATE FAILED — regression detected")
        print(f"::set-output name=pass::false")
        sys.exit(1)


if __name__ == '__main__':
    main()
