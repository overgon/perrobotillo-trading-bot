#!/usr/bin/env python3
"""
ZEC Backtest ML Data Generator v2

Runs perrobotillo strategy on ZEC historical data in Jesse AI (Docker),
extracts trades, and generates ML training samples by matching trade entry
timestamps with features from ZEC_features.csv.

Key insight: features CSV has NO timestamp column — rows are sequential 1h candles
matching raw_data/ZECUSDT_1h.csv in the same order. We build a timestamp->index
map from raw_data to find the corresponding feature row for each trade.
"""
import sys, os, json, argparse, csv, io
import numpy as np
from datetime import datetime
from contextlib import redirect_stdout

PROJECT_ROOT = os.environ.get('PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from jesse.research import backtest

DATA_DIR = os.path.join(PROJECT_ROOT, 'backtest', 'data')
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, 'raw_data')
FEATURES_DIR = os.path.join(PROJECT_ROOT, 'ml', 'features')
EXCHANGE = 'Binance Spot'
TIMEFRAME = '1h'


def load_csv_1h_with_raw(coin: str, days: int = 730) -> tuple:
    """Load 1h CSV from raw_data/ and expand to 1m candles (Jesse requires 1m).

    Returns (candles_1m_array, raw_rows) for timestamp mapping.
    Both ZEC and BTC use raw_data/ for identical date ranges.
    """
    symbol_usdt = f'{coin}USDT'
    csv_path = os.path.join(RAW_DATA_DIR, f'{symbol_usdt}_1h.csv')

    if not os.path.exists(csv_path):
        csv_path = os.path.join(DATA_DIR, f'{symbol_usdt}_1h_180days.csv')
        if not os.path.exists(csv_path):
            csv_path = os.path.join(DATA_DIR, f'{symbol_usdt}_1h_90days.csv')

    if not os.path.exists(csv_path):
        print(f"  ⚠️  CSV not found for {coin}: {csv_path}")
        return None, None

    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    hours_needed = min(days * 24, len(rows))
    rows = rows[-hours_needed:]

    candles_1m = []
    for r in rows:
        ts = datetime.fromisoformat(r['timestamp'])
        ts_ms = int(ts.timestamp() * 1000)
        o = float(r['open'])
        h = float(r['high'])
        l = float(r['low'])
        c = float(r['close'])
        v = float(r['volume']) / 60.0
        for minute in range(60):
            candles_1m.append([ts_ms + minute * 60000, o, h, l, c, v])

    return np.array(candles_1m, dtype=np.float64), rows


def build_timestamp_index(raw_rows: list) -> dict:
    """Build a {timestamp_str: row_index} map for matching trades to features.

    The features CSV rows correspond 1:1 with raw_data rows in the same slice.
    So if a trade enters at raw_data timestamp T (corresponding to raw_rows index I),
    the feature row is at the same index I in the features CSV.
    """
    ts_map = {}
    for i, r in enumerate(raw_rows):
        ts_map[r['timestamp']] = i
    return ts_map


def run_zec_backtest(days: int, hyperparams: dict) -> tuple | None:
    """Run backtest for ZEC with BTC as data route. Returns (result, zec_raw_rows)."""
    print(f"=== ZEC Backtest (Jesse AI, {days} days) ===\n")

    routes = [
        {
            'exchange': EXCHANGE,
            'symbol': 'ZEC-USDT',
            'timeframe': TIMEFRAME,
            'stake': 500.0,
            'strategy': 'perrobotillo',
        }
    ]

    candles = {}

    # ZEC candles (main route)
    zec_c, zec_raw_rows = load_csv_1h_with_raw('ZEC', days)
    if zec_c is None or len(zec_c) < 240:
        print(f"❌ Insufficient ZEC data: {len(zec_c) if zec_c is not None else 0} candles")
        return None
    candles[f'{EXCHANGE}-ZEC-USDT'] = {
        'exchange': EXCHANGE,
        'symbol': 'ZEC-USDT',
        'candles': zec_c,
    }
    print(f"  ✅ ZEC: {len(zec_c)} 1m candles loaded from raw_data")

    # BTC candles (data route for market-mode detection)
    btc_c, _ = load_csv_1h_with_raw('BTC', days)
    if btc_c is not None and len(btc_c) > 0:
        candles[f'{EXCHANGE}-BTC-USDT'] = {
            'exchange': EXCHANGE,
            'symbol': 'BTC-USDT',
            'candles': btc_c,
        }
        print(f"  ✅ BTC: {len(btc_c)} 1m candles loaded (data route)")
    else:
        print("  ⚠️  BTC data not found — market mode will use defaults")

    data_routes = [{'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'}]

    config = {
        'starting_balance': 10000,
        'fee': 0.001,
        'type': 'spot',
        'simulation_model': 'spot',
        'exchange': EXCHANGE,
        'warm_up_candles': 200,
    }

    print(f"\n  Hyperparameters: {json.dumps(hyperparams, indent=2)}")
    print(f"\n  Running backtest...")

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

    return result, zec_raw_rows


def extract_trades_with_features(result: dict, zec_raw_rows: list, features_csv: str, output_file: str):
    """Extract backtest trades and match with features CSV for ML training.

    The features CSV has the same row ordering as full raw_data, but with an
    offset (first ~54 rows trimmed for indicator warmup). We compute:
      feature_idx = full_raw_index - (len(full_raw) - len(features))
    to correctly map trade timestamps from the backtest slice to feature rows.
    """
    import pandas as pd
    import csv as csv_module

    trades = result.get('trades', [])
    metrics = result.get('metrics', {})

    print(f"\n=== Backtest Results ===")
    print(f"  Total trades: {len(trades)}")
    print(f"  Net profit: ${metrics.get('net_profit', 0):.2f}")
    print(f"  Sharpe: {metrics.get('sharpe_ratio', 0):.3f}")
    print(f"  Win rate: {metrics.get('win_rate', 0):.1%}")

    if len(trades) == 0:
        print("  ⚠️  No trades generated — strategy didn't trigger")
        return 0, trades

    # Load features CSV
    features_df = pd.read_csv(features_csv)
    n_feat = len(features_df)

    # Load FULL raw_data to build complete timestamp->index map
    full_raw_csv = os.path.join(RAW_DATA_DIR, 'ZECUSDT_1h.csv')
    full_raw_rows = []
    with open(full_raw_csv) as f:
        reader = csv_module.DictReader(f)
        for r in reader:
            full_raw_rows.append(r)

    # The backtest used the LAST N days of raw_data. The features CSV was
    # generated from the FULL raw_data with an offset (warmup trim).
    # offset = len(full_raw) - len(features)
    offset = len(full_raw_rows) - n_feat
    print(f"\n  Features CSV: {n_feat} rows")
    print(f"  Full raw_data: {len(full_raw_rows)} rows")
    print(f"  Offset (raw trim): {offset} rows")
    print(f"  Raw data rows in backtest slice: {len(zec_raw_rows)}")

    # Build complete timestamp→full_index map
    full_ts_map = {}
    for i, r in enumerate(full_raw_rows):
        full_ts_map[r['timestamp']] = i

    ml_samples = []
    unmatched = 0
    for t in trades:
        # Jesse trade timestamp is 'opened_at' (millisecond float)
        opened_at = t.get('opened_at', None)
        if opened_at is None:
            unmatched += 1
            continue

        # Convert ms timestamp to datetime
        entry_ts_ms = float(opened_at)
        entry_ts_dt = pd.to_datetime(entry_ts_ms, unit='ms')

        # Find closest timestamp in FULL raw_data
        best_full_idx = None
        best_diff = float('inf')
        for ts_str, full_idx in full_ts_map.items():
            ts_dt = pd.to_datetime(ts_str)
            diff = abs((entry_ts_dt - ts_dt).total_seconds())
            if diff < best_diff:
                best_diff = diff
                if diff < 3600:  # within 1h
                    best_full_idx = full_idx

        if best_full_idx is None:
            unmatched += 1
            continue

        # Map full_raw index to features index
        feature_idx = best_full_idx - offset
        if feature_idx < 0 or feature_idx >= n_feat:
            print(f"    ⚠️  feature_idx={feature_idx} out of range [0, {n_feat}) for trade at {entry_ts_dt}")
            unmatched += 1
            continue

        row = features_df.iloc[feature_idx].to_dict()
        feature_cols = [c for c in features_df.columns if c != 'label']
        features = {k: row[k] for k in feature_cols if k in row}

        pnl = float(t.get('PNL', t.get('pnl', 0)))
        is_profitable = 1 if pnl > 0 else 0

        ml_samples.append({
            **features,
            'label': is_profitable,
            'is_profitable': is_profitable,
            'entry_price': float(t.get('entry_price', t.get('avg_entry_price', 0))),
            'exit_price': float(t.get('exit_price', t.get('avg_exit_price', 0))),
            'pnl': pnl,
            'entry_timestamp': str(entry_ts_dt),
            'source': 'jesse_backtest',
        })

    print(f"  ML samples extracted: {len(ml_samples)} (unmatched: {unmatched})")
    profitable = sum(1 for s in ml_samples if s['is_profitable'])
    if ml_samples:
        print(f"  Profitable trades: {profitable}/{len(ml_samples)} ({100*profitable/len(ml_samples):.1f}%)")

    if ml_samples:
        out_df = pd.DataFrame(ml_samples)
        out_df.to_csv(output_file, index=False)
        print(f"  ✅ ML training data saved to: {output_file}")

        # Save full trade details
        trades_file = output_file.replace('.csv', '_trades.json')
        with open(trades_file, 'w') as f:
            json.dump({
                'total_trades': len(trades),
                'profitable': profitable,
                'unmatched': unmatched,
                'metrics': dict(metrics),
                'trades': trades,
            }, f, indent=2, default=str)
        print(f"  ✅ Trade details saved to: {trades_file}")

    return len(ml_samples), trades


def main():
    parser = argparse.ArgumentParser(description='ZEC Backtest ML Data Generator v2')
    parser.add_argument('--days', type=int, default=730,
                        help='Days of historical data (default: 730 = 2 years)')
    parser.add_argument('--output', default=None, help='Output ML samples CSV path')
    parser.add_argument('--features-csv', default=None, help='Path to ZEC_features.csv')
    parser.add_argument('--ml-min', type=float, default=30.0,
                        help='ML min confidence for signal generation (lower = more trades)')
    parser.add_argument('--sl', type=float, default=4.66, help='Stop loss percent (ZEC per-coin)')
    parser.add_argument('--tp', type=float, default=0.5, help='Take profit percent (single TP)')
    parser.add_argument('--pos-size', type=float, default=11.05, help='Position size percent')
    args = parser.parse_args()

    output_file = args.output or os.path.join(
        PROJECT_ROOT, 'ml', 'backtest_data', 'ZEC_backtest_ml_samples.csv'
    )
    features_csv = args.features_csv or os.path.join(FEATURES_DIR, 'ZEC_features.csv')

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    hyperparams = {
        'ema_fast': 12,
        'ema_slow': 140,
        'tp_percent': args.tp,
        'stop_loss_percent': args.sl,
        'ml_min_confidence': args.ml_min,
        'position_size_percent': args.pos_size,
        'rsi_overbought': 75,
        'rsi_oversold': 30,
        'min_adx': 20,
    }

    # Run backtest
    result_tuple = run_zec_backtest(args.days, hyperparams)
    if result_tuple is None:
        print("\n❌ Backtest failed")
        return 1

    result, zec_raw_rows = result_tuple

    # Extract trades and generate ML samples
    n_samples, trades = extract_trades_with_features(result, zec_raw_rows, features_csv, output_file)

    if n_samples > 0:
        print(f"\n✅ SUCCESS: {n_samples} ML samples generados para ZEC")
        print(f"   Output: {output_file}")
        print(f"   Next: Merge with existing ZEC_features.csv for retrain")
        return 0
    else:
        print("\n⚠️  No ML samples generated")
        return 1


if __name__ == '__main__':
    sys.exit(main())
