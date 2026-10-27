#!/usr/bin/env python3
"""
ZEC Multi-Config Backtest ML Data Generator

Runs multiple perrobotillo backtests with different hyperparameters
to generate diverse ML training samples for ZEC. Combines all trades
into a single labeled dataset.

Approach:
1. Run backtests with 4 parameter sets (different TP/SL/confidence combos)
2. Extract ALL trades with features + labels
3. Merge into a balanced dataset for ML retraining
"""
import sys, os, json, argparse, csv, io
import numpy as np
from datetime import datetime
from contextlib import redirect_stdout

PROJECT_ROOT = os.environ.get('PROJECT_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from jesse.research import backtest

RAW_DATA_DIR = os.path.join(PROJECT_ROOT, 'raw_data')
FEATURES_DIR = os.path.join(PROJECT_ROOT, 'ml', 'features')
EXCHANGE = 'Binance Spot'
TIMEFRAME = '1h'


def load_csv_1h(coin: str, days: int) -> np.ndarray:
    """Load 1h CSV from raw_data/ and expand to 1m candles."""
    csv_path = os.path.join(RAW_DATA_DIR, f'{coin}USDT_1h.csv')
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
        o, h, l, c = float(r['open']), float(r['high']), float(r['low']), float(r['close'])
        v = float(r['volume']) / 60.0
        for minute in range(60):
            candles_1m.append([ts_ms + minute * 60000, o, h, l, c, v])

    return np.array(candles_1m, dtype=np.float64), rows


def run_backtest_for_config(days: int, hp: dict) -> dict | None:
    """Run a single backtest for ZEC with given hyperparameters."""
    zec_c, zec_raw = load_csv_1h('ZEC', days)
    btc_c, _ = load_csv_1h('BTC', days)

    candles = {
        f'{EXCHANGE}-ZEC-USDT': {'exchange': EXCHANGE, 'symbol': 'ZEC-USDT', 'candles': zec_c},
        f'{EXCHANGE}-BTC-USDT': {'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'candles': btc_c},
    }

    config = {
        'starting_balance': 10000,
        'fee': 0.001,
        'type': 'spot',
        'simulation_model': 'spot',
        'exchange': EXCHANGE,
        'warm_up_candles': 200,
    }

    routes = [{'exchange': EXCHANGE, 'symbol': 'ZEC-USDT', 'timeframe': TIMEFRAME,
               'stake': 500.0, 'strategy': 'perrobotillo'}]
    data_routes = [{'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'}]

    buf = io.StringIO()
    with redirect_stdout(buf):
        result = backtest(config=config, routes=routes, data_routes=data_routes,
                          candles=candles, hyperparameters=hp, fast_mode=True)

    return result, zec_raw


def extract_samples(result: dict, zec_raw_rows: list, features_df, offset: int) -> list:
    """Extract ML training samples from backtest trades."""
    import pandas as pd

    trades = result.get('trades', [])
    if len(trades) == 0:
        return []

    # Build timestamp→full_index map
    full_ts_map = {}
    for i, r in enumerate(zec_raw_rows):
        full_ts_map[r['timestamp']] = i

    # But zec_raw_rows is the last N days slice — we need the FULL raw_data map
    full_csv = os.path.join(RAW_DATA_DIR, 'ZECUSDT_1h.csv')
    full_raw_rows = []
    with open(full_csv) as f:
        reader = csv.DictReader(f)
        for r in reader:
            full_raw_rows.append(r)

    full_ts_map = {r['timestamp']: i for i, r in enumerate(full_raw_rows)}
    offset = len(full_raw_rows) - len(features_df)

    samples = []
    for t in trades:
        opened_at = t.get('opened_at', None)
        if opened_at is None:
            continue

        entry_ts_dt = pd.to_datetime(float(opened_at), unit='ms')

        # Find closest timestamp in FULL raw_data
        best_full_idx = None
        best_diff = float('inf')
        for ts_str, full_idx in full_ts_map.items():
            ts_dt = pd.to_datetime(ts_str)
            diff = abs((entry_ts_dt - ts_dt).total_seconds())
            if diff < best_diff:
                best_diff = diff
                if diff < 3600:
                    best_full_idx = full_idx

        if best_full_idx is None:
            continue

        feature_idx = best_full_idx - offset
        if feature_idx < 0 or feature_idx >= len(features_df):
            continue

        row = features_df.iloc[feature_idx].to_dict()
        feature_cols = [c for c in features_df.columns if c != 'label']
        features = {k: row[k] for k in feature_cols if k in row}

        pnl = float(t.get('PNL', 0))
        is_profitable = 1 if pnl > 0 else 0

        samples.append({
            **features,
            'label': is_profitable,
            'is_profitable': is_profitable,
            'entry_price': float(t.get('entry_price', 0)),
            'exit_price': float(t.get('exit_price', 0)),
            'pnl': pnl,
            'entry_timestamp': str(entry_ts_dt),
            'config_name': t.get('_config_name', 'backtest'),
        })

    return samples


# Parameter sets for diverse backtests
CONFIGS = [
    {
        'name': 'balanced_tp2.5_sl3.5_conf30',
        'hp': {'ema_fast': 12, 'ema_slow': 140, 'tp_percent': 2.5, 'stop_loss_percent': 3.5,
               'ml_min_confidence': 30.0, 'position_size_percent': 11.05, 'rsi_overbought': 75,
               'rsi_oversold': 30, 'min_adx': 20},
    },
    {
        'name': 'aggressive_tp5.0_sl3.5_conf25',
        'hp': {'ema_fast': 12, 'ema_slow': 140, 'tp_percent': 5.0, 'stop_loss_percent': 3.5,
               'ml_min_confidence': 25.0, 'position_size_percent': 11.05, 'rsi_overbought': 70,
               'rsi_oversold': 35, 'min_adx': 18},
    },
    {
        'name': 'conservative_tp2.0_sl4.0_conf35',
        'hp': {'ema_fast': 12, 'ema_slow': 140, 'tp_percent': 2.0, 'stop_loss_percent': 4.0,
               'ml_min_confidence': 35.0, 'position_size_percent': 11.05, 'rsi_overbought': 75,
               'rsi_oversold': 30, 'min_adx': 20},
    },
    {
        'name': 'scalp_tp1.0_sl3.5_conf28',
        'hp': {'ema_fast': 21, 'ema_slow': 80, 'tp_percent': 1.0, 'stop_loss_percent': 3.5,
               'ml_min_confidence': 28.0, 'position_size_percent': 11.05, 'rsi_overbought': 70,
               'rsi_oversold': 35, 'min_adx': 15},
    },
]


def main():
    parser = argparse.ArgumentParser(description='ZEC Multi-Config Backtest ML Data Generator')
    parser.add_argument('--days', type=int, default=730)
    parser.add_argument('--output', default=None)
    parser.add_argument('--features-csv', default=None)
    args = parser.parse_args()

    import pandas as pd

    output_file = args.output or os.path.join(
        PROJECT_ROOT, 'ml', 'backtest_data', 'ZEC_backtest_ml_samples.csv'
    )
    features_csv = args.features_csv or os.path.join(FEATURES_DIR, 'ZEC_features.csv')

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    features_df = pd.read_csv(features_csv)
    print(f"Features CSV: {len(features_df)} rows, {len(features_df.columns)-1} features\n")

    all_samples = []
    all_trades = []

    for i, cfg in enumerate(CONFIGS):
        print(f"=== Config {i+1}/{len(CONFIGS)}: {cfg['name']} ===")
        print(f"  TP={cfg['hp']['tp_percent']}% SL={cfg['hp']['stop_loss_percent']}% "
              f"ML_MIN={cfg['hp']['ml_min_confidence']}%")

        result, zec_raw = run_backtest_for_config(args.days, cfg['hp'])
        trades = result.get('trades', [])
        metrics = result.get('metrics', {})

        print(f"  Trades: {len(trades)} | "
              f"PnL=${metrics.get('net_profit', 0):.2f} | "
              f"Sharpe={metrics.get('sharpe_ratio', 0):.3f} | "
              f"WR={metrics.get('win_rate', 0):.1%}")

        # Tag trades with config name
        for t in trades:
            t['_config_name'] = cfg['name']

        samples = extract_samples(result, zec_raw, features_df, 0)
        for s in samples:
            s['config_name'] = cfg['name']
        all_samples.extend(samples)
        all_trades.extend(trades)
        print(f"  ML samples: {len(samples)}\n")

    # Deduplicate by entry timestamp + config_name
    seen = set()
    unique_samples = []
    for s in all_samples:
        key = (s.get('entry_timestamp', ''), s.get('config_name', ''))
        if key not in seen:
            seen.add(key)
            unique_samples.append(s)
    deduped = len(all_samples) - len(unique_samples)
    if deduped > 0:
        print(f"  Deduplicated {deduped} duplicate samples\n")

    # Save combined dataset
    if unique_samples:
        df = pd.DataFrame(unique_samples)
        df.to_csv(output_file, index=False)
        print(f"\n✅ Combined ML samples saved to: {output_file}")

        profitable = sum(1 for s in unique_samples if s['is_profitable'])
        print(f"  Total samples: {len(unique_samples)}")
        print(f"  Profitable: {profitable} ({100*profitable/len(unique_samples):.1f}%)")
        print(f"  Unprofitable: {len(unique_samples) - profitable} ({100*(len(unique_samples)-profitable)/len(unique_samples):.1f}%)")

        # Save trade details
        trades_file = output_file.replace('.csv', '_trades.json')
        with open(trades_file, 'w') as f:
            json.dump({
                'source': 'jesse_ai_backtest_multi_config',
                'configs': [c['name'] for c in CONFIGS],
                'total_trades': len(all_trades),
                'unique_samples': len(unique_samples),
                'profitable': profitable,
                'configs_results': [
                    {
                        'config': c['name'],
                        'trades': len([t for t in all_trades if t.get('_config_name') == c['name']]),
                    } for c in CONFIGS
                ],
            }, f, indent=2, default=str)
        print(f"  ✅ Trade details saved to: {trades_file}")

        print(f"\n  Próximo paso: Merge con ZEC_features.csv existente para retrain")
        print(f"  python3 auto-retrain-v2.py  # incluirá datos backtest complementarios")
        return 0
    else:
        print("\n⚠️  No ML samples generated")
        return 1


if __name__ == '__main__':
    sys.exit(main())
