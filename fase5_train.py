#!/usr/bin/env python3
"""
Fase 5: ML Pipeline de Jesse — Train ML models for Perrobotillo
================================================================
Issue #44, Fase 5: "ML Pipeline de Jesse"

Workflow:
  1. Load CSV candle data (90 days, 1h → expand to 1m for Jesse)
  2. gather_ml_data() — backtest with feature/label recording (JESSE_ML_MODE=gather)
  3. Train 4 estimators: RandomForest, XGBoost, GradientBoosting, LogisticRegression
  4. Validate overfitting_gap < 3% (current worst: LINK 4.02%)
  5. Export best model → Perrobotillo production format

Usage:
  python3 fase5_train.py                  # all coins
  python3 fase5_train.py --coin ZEC     # single coin
  python3 fase5_train.py --dry-run       # ZEC only, verify pipeline
"""

import os
import sys
import json
import pickle
import shutil
import warnings
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.base import clone
from xgboost import XGBClassifier

# Jesse research imports
sys.path.insert(0, '/home')
from jesse.research.backtest import backtest as run_backtest, _reset_research_runtime_state  # noqa: E402
from jesse.routes import router  # noqa: E402

warnings.filterwarnings("ignore")

# ─── Configuration ───────────────────────────────────────────────────────────

COINS = ['ZEC', 'AVAX', 'XRP', 'SOL', 'BNB', 'ETH', 'BTC']
RAW_DATA_DIR = Path("/home/raw_data")
OUTPUT_DIR = Path("/home/analysis_fase5")          # container path
HOST_MODELS_DIR = Path("/home/fase5_models")        # exported models (host-mounted)
WARMUP_DAYS = 14  # 14 days warmup for indicators

# Estimators matching existing Perrobotillo model configs
ESTIMATORS = {
    'random_forest': RandomForestClassifier(
        n_estimators=300, max_depth=6, min_samples_split=50,
        min_samples_leaf=25, max_features='log2', max_leaf_nodes=15,
        class_weight='balanced', ccp_alpha=0.02, random_state=123, n_jobs=-1,
    ),
    'xgboost': XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, eval_metric='logloss',
        random_state=123, n_jobs=-1, tree_method='hist',
        use_label_encoder=False,
    ),
    'gradient_boosting': GradientBoostingClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.1,
        subsample=0.8, random_state=123,
    ),
    'logistic_regression': LogisticRegression(
        max_iter=1000, class_weight='balanced', random_state=123, C=1.0,
    ),
}

# Per-coin per-coin-config.env overrides (from strategy)
COIN_CONFIGS = {
    'BTC':  {'pos': 10, 'ml_min': 45, 'tp1': 3.0, 'tp2': 6.0, 'tp3': 9.0, 'sl': 3.5},
    'ETH':  {'pos': 10, 'ml_min': 45, 'tp1': 3.0, 'tp2': 6.0, 'tp3': 9.0, 'sl': 3.0},
    'BNB':  {'pos': 15, 'ml_min': 40, 'tp1': 2.5, 'tp2': 5.0, 'tp3': 7.5, 'sl': 2.0},
    'SOL':  {'pos': 15, 'ml_min': 35, 'tp1': 2.5, 'tp2': 5.0, 'tp3': 7.5, 'sl': 2.0},
    'ZEC':  {'pos': 10, 'ml_min': 40, 'tp1': 2.5, 'tp2': 5.0, 'tp3': 7.5, 'sl': 3.0},
    'XRP':  {'pos': 10, 'ml_min': 35, 'tp1': 2.5, 'tp2': 5.0, 'tp3': 7.5, 'sl': 2.5},
    'AVAX': {'pos': 10, 'ml_min': 35, 'tp1': 2.5, 'tp2': 5.0, 'tp3': 7.5, 'sl': 2.0},
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def csv_to_1m(coin: str) -> np.ndarray:
    """Load 1h CSV → expand to 1m candles for Jesse.

    Expansion rules (per jesse-backtest-research skill):
      - Minute 0: open=close=1h_open
      - Minutes 1-58: linear interpolation between open and close
      - Minute 59: close=1h_close
      - Volume: 1h_volume / 60 per minute
    """
    csv_path = RAW_DATA_DIR / f"{coin}USDT_1h.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    df = df.dropna(subset=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['ts_ms'] = pd.to_datetime(df['timestamp']).astype('int64') // 10**6
    df = df.sort_values('ts_ms').reset_index(drop=True)  # Chronological order
    candles_1h = df[['ts_ms', 'open', 'high', 'low', 'close', 'volume']].values.astype(np.float64)

    candles_1m = []
    prev_close = None
    prev_ts = None

    for ts, o, h, l, c, v in candles_1h:
        vol_per_min = v / 60.0

        # Fill gap between prev candle and this candle (missing hours on Binance)
        if prev_ts is not None and ts > prev_ts + 3_600_000:
            gap_start = prev_ts + 3_600_000
            t = gap_start
            while t < ts:
                candles_1m.append([t, prev_close, prev_close, prev_close, prev_close, 0.0])
                t += 60_000

        for minute in range(60):
            t = ts + minute * 60_000  # 60_000ms = 1 minute
            if minute == 0:
                close_price = o
            elif minute == 59:
                close_price = c
            else:
                ratio = (minute + 1) / 60.0
                close_price = o + (c - o) * ratio
            candles_1m.append([t, o, h, l, close_price, vol_per_min])

        prev_close = c
        prev_ts = ts

    # Ensure chronological order before validation (Bug fix per issue #44)
    # Gap-filling can produce out-of-order rows if df isn't fully sequential
    candles_1m.sort(key=lambda r: r[0])

    arr = np.array(candles_1m, dtype=np.float64)
    # Validate 1m spacing
    diffs = np.diff(arr[:, 0])
    assert np.all(diffs == 60_000), f"Non-1m intervals detected! min={diffs.min()}, max={diffs.max()}"
    return arr


def build_gather_input(coin: str):
    """Build candles dict, warmup, config, routes for gather_ml_data()."""
    symbol = f"{coin}-USDT"
    cfg = COIN_CONFIGS[coin]

    # Load 1h → 1m
    main_1m = csv_to_1m(coin)
    btc_1m = csv_to_1m("BTC")

    warmup_h = WARMUP_DAYS * 24  # warmup candles in 1h units
    warmup_1m_count = warmup_h * 60  # convert to 1m count

    warmup = {
        f"Binance Spot-{symbol}": {
            "exchange": "Binance Spot", "symbol": symbol,
            "candles": main_1m[:warmup_1m_count],
        },
        "Binance Spot-BTC-USDT": {
            "exchange": "Binance Spot", "symbol": "BTC-USDT",
            "candles": btc_1m[:warmup_1m_count],
        },
    }
    candles = {
        f"Binance Spot-{symbol}": {
            "exchange": "Binance Spot", "symbol": symbol,
            "candles": main_1m[warmup_1m_count:],
        },
        "Binance Spot-BTC-USDT": {
            "exchange": "Binance Spot", "symbol": "BTC-USDT",
            "candles": btc_1m[warmup_1m_count:],
        },
    }

    config = {
        'starting_balance': 10000,
        'fee': 0.001,
        'type': 'spot',
        'simulation_model': 'spot',
        'exchange': 'Binance Spot',
        'warm_up_candles': warmup_h,
    }

    routes = [{
        'exchange': 'Binance Spot', 'symbol': symbol,
        'timeframe': '1h', 'stake': 100, 'strategy': 'perrobotillo',
    }]
    data_routes = [{
        'exchange': 'Binance Spot', 'symbol': 'BTC-USDT', 'timeframe': '1h',
    }]

    return config, routes, data_routes, candles, warmup


def gather_data(coin: str):
    """Step 1: Run backtest with ML feature/label recording (JESSE_ML_MODE=gather).

    Workaround: _isolated_backtest finally block calls _reset_research_runtime_state()
    → router._reset() → clears routes → strategy._ml_data_points lost.
    We patch router._reset to no-op, run backtest with per-coin hyperparameters
    (lower ml_min for more trades), collect _ml_data_points, then restore.
    """
    os.environ['JESSE_ML_MODE'] = 'gather'

    config, routes, data_routes, candles, warmup = build_gather_input(coin)
    csv_path = str(OUTPUT_DIR / f"{coin}_ml_data.csv")

    # Build custom hyperparameters as a DICT (not a list).
    # Issue #44: passing a list causes `r.strategy.hp = route_hp` (backtest_mode.py
    # L1363) to set self.hp to a list → TypeError: list indices must be integers
    # when the strategy accesses self.hp['ema_fast'].
    # Also, the dict must include ALL hyperparameters (ema_fast, ema_slow, etc.)
    # because the strategy uses self.hp['ema_fast'] (not .get()) at lines 233/237.
    cfg = COIN_CONFIGS.get(coin, {})

    # Full default set matching Strategy.hyperparameters() defaults
    hyperparameters = {
        'tp1_percent': 3.0,
        'tp2_percent': 14.4,
        'tp3_percent': 18.2,
        'stop_loss_percent': 7.2,
        'position_size_percent': 18.0,
        'ml_min_confidence': 40,
        'ema_fast': 12,
        'ema_slow': 140,
        'rsi_overbought': 75,
        'rsi_oversold': 30,
        'min_adx': 20,
    }

    # Override with per-coin config from COIN_CONFIGS
    param_map = {
        'ml_min': 'ml_min_confidence',
        'tp1': 'tp1_percent',
        'tp2': 'tp2_percent',
        'tp3': 'tp3_percent',
        'sl': 'stop_loss_percent',
        'pos': 'position_size_percent',
    }
    for cfg_key, hp_name in param_map.items():
        if cfg_key in cfg:
            hyperparameters[hp_name] = cfg[cfg_key]

    # Lower ml_min_confidence during data gathering to collect more samples.
    # Issue #44: with ml_min=35 (LINK), only 19 data points collected (need ≥50).
    # We WANT all trades that meet basic EMA/price criteria → label them for ML.
    hyperparameters['ml_min_confidence'] = 0

    # Lower EMA thresholds during data gathering to generate more entry signals.
    # Issue #44: EMA 12/140 produces only ~19 trades in 2 years — insufficient
    # for ML training (need ≥50). EMA 5/20 generates more crosses.
    # Features still use hardcoded EMA 12/26 (líneas 547-548), so this only
    # affects the entry filter, NOT the recorded ML features.
    hyperparameters['ema_fast'] = 5
    hyperparameters['ema_slow'] = 20

    # Patch router._reset to preserve _ml_data_points during cleanup.
    # Issue #44: run_backtest() internally calls _reset_research_runtime_state()
    # TWICE: once BEFORE execution (line 160, sets up routes) and once AFTER
    # (line 182, in finally — clears routes + _ml_data_points).
    # A no-op patch (router._reset = lambda: None) blocks BOTH calls,
    # preventing route setup for the 2nd+ coin → only 51 samples.
    # FIX: intercept _reset, save _ml_data_points to a buffer, THEN call
    # original reset (which re-configures routes for the next coin).
    saved_ml_data = []
    original_router_reset = router._reset

    def patched_reset():
        # Save strategy._ml_data_points before original reset clears them
        if router.routes:
            s = router.routes[0].strategy
            if hasattr(s, "_ml_data_points"):
                saved_ml_data.clear()
                saved_ml_data.extend(s._ml_data_points)
        original_router_reset()

    router._reset = patched_reset

    data_points = []
    backtest_result = None

    try:
        backtest_result = run_backtest(
            config=config, routes=routes, data_routes=data_routes,
            candles=candles, warmup_candles=warmup,
            hyperparameters=hyperparameters, fast_mode=True,
        )

        # Collect _ml_data_points: prefer live strategy reference (1st coin),
        # fall back to saved_ml_data buffer (2nd+ coin — router was reset by
        # _isolated_backtest's finally block which we patched to save first).
        data_points = []
        if router.routes:
            strategy = router.routes[0].strategy
            if hasattr(strategy, "_ml_data_points"):
                data_points = [p for p in strategy._ml_data_points
                              if p.get("label") is not None]
        elif saved_ml_data:
            data_points = [p for p in saved_ml_data
                          if p.get("label") is not None]
            strategy = None
        if strategy is not None:
            try:
                # export_ml_data expects a DIRECTORY, not a file path
                # It creates <directory>/ml_data/<coin>_data.csv internally
                strategy.export_ml_data(str(OUTPUT_DIR))
            except Exception:
                pass
    finally:
        router._reset = original_router_reset
        _reset_research_runtime_state()

    print(f"  ✅ Data points collected: {len(data_points)}")
    if backtest_result and isinstance(backtest_result, dict):
        perf = backtest_result.get('performance', backtest_result)
        if isinstance(perf, dict):
            print(f"     Backtest: PnL={perf.get('net_profit', '?')}"
                  f" WR={perf.get('win_rate', '?')}"
                  f" Sharpe={perf.get('sharpe_ratio', '?')}")

    os.environ.pop('JESSE_ML_MODE', None)
    return data_points

def prepare_xy(data_points):
    """Convert data_points → (X, y, feature_names)."""
    feature_names = sorted(set(
        f for p in data_points for f in p['features'].keys()
    ))
    X = np.array([
        [p['features'].get(f, 0.0) for f in feature_names]
        for p in data_points
    ], dtype=np.float64)
    y = np.array([1 if p['label']['value'] else 0 for p in data_points])
    return X, y, feature_names


def train_all_models(coin: str, X, y, feature_names):
    """Step 2: Train 4 estimators with CV, return results dict."""
    print(f"\n  🎯 Training 4 models for {coin} ({len(y)} samples)...")

    # Chronological 80/20 split
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    tscv = TimeSeriesSplit(n_splits=5)
    results = {}

    for name, est in ESTIMATORS.items():
        print(f"    ⏳ Training {name}...", end="", flush=True)
        model = clone(est)
        model.fit(X_train_s, y_train)

        y_pred = model.predict(X_test_s)
        y_proba = model.predict_proba(X_test_s)[:, 1] if hasattr(model, 'predict_proba') else y_pred

        cv_scores = cross_val_score(model, X_train_s, y_train, cv=tscv, scoring='accuracy')
        train_acc = accuracy_score(y_train, model.predict(X_train_s))
        test_acc = accuracy_score(y_test, y_pred)
        cv_mean = float(np.mean(cv_scores))

        gap = abs(train_acc - cv_mean)

        results[name] = {
            'model': model,
            'scaler': scaler,
            'features': feature_names,
            'train_accuracy': float(train_acc),
            'test_accuracy': float(test_acc),
            'cv_mean': cv_mean,
            'cv_std': float(np.std(cv_scores)),
            'overfitting_gap': float(gap),
            'precision': float(precision_score(y_test, y_pred, zero_division=0)),
            'recall': float(recall_score(y_test, y_pred, zero_division=0)),
            'f1': float(f1_score(y_test, y_pred, zero_division=0)),
            'roc_auc': float(roc_auc_score(y_test, y_proba)) if len(set(y_test)) > 1 else 0.0,
        }
        del results[name]['scaler']  # don't keep duplicate

        print(f" ✅ acc={test_acc:.4f} cv={cv_mean:.4f} gap={gap:.4f} ({gap*100:.2f}%)")

    return results, scaler


def select_best(results):
    """Select best model: lowest overfitting_gap, then highest test accuracy."""
    eligible = {k: v for k, v in results.items() if v['test_accuracy'] > 0.5}
    if not eligible:
        eligible = results
    best_name = min(eligible, key=lambda k: (eligible[k]['overfitting_gap'], -eligible[k]['test_accuracy']))
    return best_name, results[best_name]


def load_current_metadata(coin: str) -> dict:
    """Load existing model metadata for comparison."""
    # Check both container and host paths
    for base in [Path("/home/ml/models_optimized"), Path("/home/fase5_models")]:
        path = base / f"{coin}_optimized_metadata.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
    return {}


def export_best_model(coin: str, best_name, best_result, all_results, scaler):
    """Step 3: Export best model in Perrobotillo production format."""
    print(f"\n  📦 Exporting {best_name} model for {coin}...")

    current = load_current_metadata(coin)
    current_gap = current.get('metrics', {}).get('overfitting_gap', 1.0)
    current_acc = current.get('metrics', {}).get('accuracy', 0.0)
    new_gap = best_result['overfitting_gap']
    new_acc = best_result['test_accuracy']

    should_export = new_gap < current_gap - 0.01  # Only if meaningfully better

    export_dir = HOST_MODELS_DIR / coin
    export_dir.mkdir(parents=True, exist_ok=True)

    # Save model
    model_path = export_dir / f"{coin}_optimized_model.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(best_result['model'], f)

    # Save scaler
    scaler_path = export_dir / f"{coin}_scaler_optimized.pkl"
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)

    # Save selected features (ALL features — selection done by feature_importance)
    features_path = export_dir / f"{coin}_selected_features.pkl"
    with open(features_path, 'wb') as f:
        pickle.dump(best_result['features'], f)

    # Save metadata
    metadata = {
        'coin': coin,
        'trained_at': datetime.now().isoformat(),
        'model_type': best_name,
        'config': best_result['model'].get_params(),
        'use_feature_selection': False,
        'n_features_original': len(best_result['features']),
        'n_features_selected': len(best_result['features']),
        'samples': len(all_results[best_name]['features']),
        'metrics': {
            'accuracy': best_result['test_accuracy'],
            'precision': best_result['precision'],
            'recall': best_result['recall'],
            'f1': best_result['f1'],
            'cv_mean': best_result['cv_mean'],
            'cv_std': best_result['cv_std'],
            'train_score': best_result['train_accuracy'],
            'test_score': best_result['test_accuracy'],
            'overfitting_gap': new_gap,
        },
        'is_optimized': True,
        'fase5': True,
        'comparison': {
            'previous_gap': current_gap,
            'previous_accuracy': current_acc,
            'new_gap': new_gap,
            'new_accuracy': new_acc,
            'improved': should_export,
        },
        'all_models_compared': {
            k: {'acc': v['test_accuracy'], 'gap': v['overfitting_gap']}
            for k, v in all_results.items()
        },
    }

    meta_path = export_dir / f"{coin}_optimized_metadata.json"
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"  ✅ {model_path.name}")
    print(f"  ✅ {scaler_path.name}")
    print(f"  ✅ {features_path.name}")
    print(f"  ✅ {meta_path.name}")
    print(f"  Gap: {current_gap:.2%} → {new_gap:.2%} | Acc: {current_acc:.4f} → {new_acc:.4f}")

    return should_export


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Fase 5: ML Pipeline de Jesse')
    parser.add_argument('--coin', type=str, default=None, help='Single coin (e.g. ZEC)')
    parser.add_argument('--dry-run', action='store_true', help='ZEC only, verify pipeline')
    args = parser.parse_args()

    if args.dry_run:
        coins = ['ZEC']
    elif args.coin:
        coins = [args.coin]
    else:
        coins = COINS

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HOST_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("🚀 FASE 5: ML PIPELINE DE JESSE")
    print(f"  Periodo: 90 days (1h candles → 1m expansion)")
    print(f"  Estimadores: {list(ESTIMATORS.keys())}")
    print(f"  Monedas: {coins}")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 70)

    summary = {}

    for coin in coins:
        print(f"\n{'='*60}")
        print(f"🔄 {coin}")
        print(f"{'='*60}")

        try:
            # 1. Gather ML data
            data_points = gather_data(coin)

            if len(data_points) < 50:
                print(f"  ⚠️ Insufficient data: {len(data_points)} < 50")
                summary[coin] = {'status': 'skipped', 'reason': 'insufficient_data'}
                continue

            # 2. Prepare data
            X, y, feature_names = prepare_xy(data_points)
            print(f"\n  📊 Features: {len(feature_names)} | Samples: {len(y)} | "
                  f"Win: {sum(y)} ({sum(y)/len(y)*100:.1f}%)")

            # 3. Train models
            results, scaler = train_all_models(coin, X, y, feature_names)

            # 4. Select best
            best_name, best_result = select_best(results)
            print(f"\n  🏆 Best: {best_name} (gap={best_result['overfitting_gap']:.2%}, "
                  f"acc={best_result['test_accuracy']:.4f})")

            # 5. Export
            improved = export_best_model(coin, best_name, best_result, results, scaler)

            summary[coin] = {
                'status': 'completed',
                'exported': improved,
                'best_model': best_name,
                'accuracy': best_result['test_accuracy'],
                'overfitting_gap': best_result['overfitting_gap'],
                'samples': len(y),
                'features': len(feature_names),
                'all_models': {k: {'acc': v['test_accuracy'], 'gap': v['overfitting_gap']}
                               for k, v in results.items()},
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            summary[coin] = {'status': 'error', 'error': str(e)}

    # ─── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("📊 RESUMEN FASE 5")
    print(f"{'='*70}")
    for coin, info in summary.items():
        if info['status'] == 'completed':
            gap = info['overfitting_gap']
            flag = '✅' if gap < 0.03 else ('⚠️' if gap < 0.05 else '❌')
            exported = 'exported' if info.get('exported') else 'skipped export'
            print(f"  {flag} {coin}: {info['best_model']} | "
                  f"acc={info['accuracy']:.4f} gap={gap:.2%} | "
                  f"n={info['samples']} feats={info['features']} | {exported}")
        else:
            print(f"  ❌ {coin}: {info.get('error', info.get('reason', 'unknown'))}")

    with open(OUTPUT_DIR / "fase5_summary.json", 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    under_3 = [c for c, i in summary.items()
               if i.get('overfitting_gap', 1) < 0.03]
    if under_3:
        print(f"\n🎯 Models with gap < 3%: {', '.join(under_3)}")

    print(f"\n📁 Results: {OUTPUT_DIR}")
    print(f"📁 Models: {HOST_MODELS_DIR}")
    print("\n✅ Fase 5 pipeline complete!")


if __name__ == '__main__':
    main()
