#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# ml-param-multiplier-train.py — Fase 7: ML Param Multiplier Model (Option A)
#
# Trains per-coin regressors that predict optimal TP1/TP2/TP3/SL/SIZE
# multipliers based on current market features.
#
#   effective_param = per_coin_base × ml_multiplier
#
# Reuses feature computation from fase7_train.py:
#   - 51 Fase 5 features (RSI, MACD, BB, ATR, Stoch, etc.)
#   - BTC context (fear_greed, market_mode, btc_ema_cross)
#   - Trade matching by entry timestamp (5-min tolerance)
#
# Labels are generated from trade outcomes:
#   - SL hits → SL_mult=1.3, SIZE_mult=0.8 (too tight, reduce risk)
#   - TP1 hits → if low PnL: TP1_mult=1.2 (wider); else 1.0
#   - TP2 hits → all ~1.0 (params were good)
#   - TP3 hits → SIZE_mult=1.1 (be more aggressive)
#   - Emergency closes → SL_mult=1.5, SIZE_mult=0.5 (defensive)
#   + market mode adjustment (BULL: TPs×1.15, SL×0.95; BEAR: TPs×0.85, SL×0.85, SZ×0.7)
#
# Refs: issue #44 (Fase 7)
# Firma: Perrobotron Aterrorrizar!!
# ═══════════════════════════════════════════════════════════════════════════

import json
import sys
import os
import joblib
import warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, r2_score
from concurrent.futures import ThreadPoolExecutor, as_completed

# ════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
TRADE_HISTORY = WORKSPACE / "crypto-bots" / "trade-history.json"
PROD_MODELS_DIR = WORKSPACE / "ml" / "models_optimized"
MODELS_DIR = Path("/home/overgon/jesse-research/param_multiplier_models")
DATA_DIR = WORKSPACE / "backtest" / "data"
DAYS_HISTORICAL = 90
DAYS_DOWNLOAD = 60
COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]
BINANCE_URL = "https://api.binance.com/api/v3/klines"
MIN_TRADES = 10
N_SPLITS = 5

# Reuse feature computation from fase7_train
sys.path.insert(0, "/home/overgon/jesse-research")
from fase7_train import (
    compute_all_features,
    add_btc_context,
    rsi_ewm,
    match_trades_to_features,
)

# Load selected features from Fase 5 (use LINK as reference — same 51 features for all)
FASE5_FEATURES_PKL = PROD_MODELS_DIR / "LINK_selected_features.pkl"

# Multiplier label names (5 regression targets)
MULTIPLIER_TARGETS = ["tp1_mult", "tp2_mult", "tp3_mult", "sl_mult", "size_mult"]

# Market mode mapping (from fase7_train.py add_btc_context)
# 0=BEAR, 1=LATERAL, 2=STRONG_BULL, 3=BEAR_rsi, 4=VOLATILE_BULL, 5=BULL
BULL_MODES = {2, 4, 5}
BEAR_MODES = {0, 3}


# ════════════════════════════════════════════════════════
# LABEL GENERATION
# ════════════════════════════════════════════════════════

def normalize_close_type(close_type):
    """Normalize close type to one of: SL, TP1, TP2, TP3, TP3_INSUFFICIENT, EMERGENCY, OTHER"""
    sl_types = {"CLOSED_SL", "SL", "GRID_SL"}
    tp1_types = {"CLOSED_TP1", "TP1"}
    tp2_types = {"CLOSED_TP2", "TP2"}
    tp3_types = {"CLOSED_TP3", "TP3"}
    if close_type in sl_types:
        return "SL"
    elif close_type in tp1_types:
        return "TP1"
    elif close_type in tp2_types:
        return "TP2"
    elif close_type in tp3_types:
        return "TP3"
    elif close_type == "CLOSED_TP3_INSUFFICIENT":
        return "TP3_INSUFFICIENT"
    elif close_type in {"EMERGENCY_CLOSE", "EMERGENCY_MANUAL"}:
        return "EMERGENCY"
    return "OTHER"


def generate_multiplier_labels(trade):
    """Generate optimal multiplier labels from trade outcome.

    Heuristics:
      SL hit → SL too tight → sl_mult > 1.0 (looser), size_mult < 1.0 (less risk)
      TP1 hit, low PnL → TP1 too tight → tp1_mult > 1.0 (wider)
      TP1 hit, high PnL → params good → ~1.0
      TP2/TP3 hit → params worked → ~1.0, maybe size up
      Emergency → very defensive
    + Market mode adjustment (BULL: be aggressive, BEAR: be defensive)
    """
    close_type = normalize_close_type(trade.get("closeType", ""))
    pnl = trade.get("pnlUSDT", 0)
    market_mode = trade.get("market_mode", 1)  # default LATERAL

    # Base multipliers (1.0 = keep current per-coin config)
    tp1_mult, tp2_mult, tp3_mult = 1.0, 1.0, 1.0
    sl_mult, size_mult = 1.0, 1.0

    if close_type == "SL":
        # SL was hit → too tight, make it looser; reduce size to limit downside
        sl_mult = 1.3
        size_mult = 0.8
    elif close_type == "TP1":
        if pnl < 0.5:
            # Low profit at TP1 → TP1 was too tight, widen it
            tp1_mult = 1.2
        else:
            # Decent profit at TP1 → params were fine
            tp1_mult = 1.0
            size_mult = 1.05
    elif close_type == "TP2":
        # TP2 hit → params good, slight size increase
        tp2_mult = 1.0
        size_mult = 1.05
    elif close_type in ("TP3", "TP3_INSUFFICIENT"):
        # TP3 hit → excellent, be more aggressive
        size_mult = 1.1
        tp3_mult = 1.0
    elif close_type == "EMERGENCY":
        # Emergency close → very defensive
        sl_mult = 1.5
        size_mult = 0.5
        tp1_mult = 0.8
    else:
        # OTHER: use PnL to adjust
        if pnl > 1.0:
            size_mult = 1.1
        else:
            size_mult = 0.9

    # Market mode adjustment
    if market_mode in BULL_MODES:
        # Bull market: let winners run (wider TPs), slightly tighter SL
        tp1_mult *= 1.15
        tp2_mult *= 1.2
        tp3_mult *= 1.1
        sl_mult *= 0.95
    elif market_mode in BEAR_MODES:
        # Bear market: take profits sooner, reduce size
        tp1_mult *= 0.85
        tp2_mult *= 0.8
        sl_mult *= 0.85
        size_mult *= 0.7

    # Clip to reasonable range [0.5, 2.0]
    mults = {
        "tp1_mult": tp1_mult,
        "tp2_mult": tp2_mult,
        "tp3_mult": tp3_mult,
        "sl_mult": sl_mult,
        "size_mult": size_mult,
    }
    for k in MULTIPLIER_TARGETS:
        mults[k] = np.clip(mults[k], 0.5, 2.0)

    return mults


# ════════════════════════════════════════════════════════
# DATA LOADING
# ════════════════════════════════════════════════════════

def load_trades():
    """Load trades from trade-history.json."""
    with open(TRADE_HISTORY) as f:
        hist = json.load(f)
    trades = hist["trades"]
    for t in trades:
        ts = t.get("timestamp", "")
        if ts:
            dt = pd.to_datetime(ts, format="mixed")
            if dt.tzinfo is not None:
                t["entry_dt"] = dt.tz_convert("UTC").tz_localize(None)
            else:
                t["entry_dt"] = dt
        else:
            t["entry_dt"] = None
    return trades


def download_klines(symbol, interval, days):
    """Download klines from Binance public API with pagination.

    Binance limits to 1000 candles per request → need multiple requests
    for 60 days of 5m data (~17K candles = ~17 requests).
    """
    import urllib.request
    import time as time_mod

    all_rows = []
    candles_per_request = 1000
    total_candles = days * 24 * 12  # days × 24h × 12 periods/hour (5m)
    requests_needed = (total_candles + candles_per_request - 1) // candles_per_request

    end_ts = None
    for req_num in range(max(requests_needed, 1)):
        params = f"?symbol={symbol}&interval={interval}&limit={candles_per_request}"
        if end_ts is not None:
            params += f"&endTime={end_ts - 1}"
        url = f"{BINANCE_URL}{params}"

        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=30) as resp:
                    data = json.loads(resp.read())
                break
            except Exception as e:
                if attempt < 2:
                    time_mod.sleep(2 ** attempt)
                else:
                    print(f"  {symbol} download failed after 3 retries: {e}")
                    data = []

        if not data:
            break

        all_rows.extend(data)
        if len(data) < candles_per_request:
            break  # last batch

        # Binance returns ascending by open_time: data[0]=oldest, data[-1]=newest
        # To get OLDER candles, set endTime to oldest candle in batch minus 1ms
        end_ts = int(data[0][0])
        if req_num % 5 == 0 or req_num == requests_needed - 1:
            print(f"  {symbol}: {len(all_rows)} candles ({req_num+1}/{requests_needed} reqs)")

        time_mod.sleep(0.1)  # rate limit

    if not all_rows:
        return None

    df = pd.DataFrame(all_rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "n_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("timestamp")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    return df


def download_all_coins(coins, days):
    """Download klines for all coins in parallel."""
    results = {}
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(download_klines, f"{c}USDT", "5m", days): c for c in coins}
        for future in as_completed(futures):
            coin = futures[future]
            try:
                df = future.result()
                if df is not None:
                    results[coin] = df
                    print(f"  {coin}: {len(df)} candles")
                else:
                    print(f"  {coin}: FAILED")
            except Exception as e:
                print(f"  {coin}: ERROR {e}")
    return results


def load_or_download_features():
    """Load or download candle data and compute features for all coins."""
    # Try existing CSVs first — must cover >= 30 days
    candle_data = {}
    for coin in COINS:
        csv_path = DATA_DIR / f"{coin}_USDT_5m.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                # Detect timestamp format: ms int or datetime string
                ts_col = df.iloc[:, 0]
                try:
                    df["timestamp"] = pd.to_datetime(ts_col, unit="ms")
                except (ValueError, TypeError):
                    df["timestamp"] = pd.to_datetime(ts_col)
                df = df.set_index("timestamp")
                for col in ["open", "high", "low", "close", "volume"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df[["open", "high", "low", "close", "volume"]].dropna()
                time_span = (df.index.max() - df.index.min()).days
                if len(df) > 100 and time_span >= 30:
                    candle_data[coin] = df
                    print(f"  {coin}: {len(df)} rows loaded from CSV ({time_span}d coverage)")
                    continue
                elif len(df) > 100:
                    print(f"  {coin}: CSV only {time_span}d coverage, will download 60d")
            except Exception as e:
                print(f"  {coin}: CSV load failed ({e}), will download")
        # Download if CSV failed or insufficient coverage
        try:
            df = download_klines(f"{coin}USDT", "5m", DAYS_DOWNLOAD)
            candle_data[coin] = df
        except Exception as e:
            print(f"  {coin}: DOWNLOAD FAILED ({e})")

    if "BTC" not in candle_data:
        print("  ERROR: No BTC data — cannot compute market context features")
        return {}

    btc_df = candle_data["BTC"]
    feature_data = {}
    for coin in COINS:
        if coin not in candle_data:
            continue
        df = compute_all_features(candle_data[coin].copy())
        df = add_btc_context(df, btc_df)
        feature_data[coin] = df
        print(f"  {coin}: {len(df)} rows, {len(df.columns)} cols")

    return feature_data


def build_training_dataset(trades, feature_data, selected_features):
    """Match trades to features and generate multiplier labels per coin."""
    datasets = {}
    for coin in COINS:
        if coin not in feature_data:
            continue
        features_df = feature_data[coin]

        # Get market_mode column for each trade
        feat_ts = features_df.index
        coin_trades = [t for t in trades if t.get("coin") == coin and t.get("entry_dt") is not None]
        matched = []
        for t in coin_trades:
            entry_time = t["entry_dt"]
            diffs = abs((feat_ts - entry_time).total_seconds())
            min_idx = diffs.argmin()
            if diffs[min_idx] <= 300:  # 5-min tolerance
                row = features_df.iloc[min_idx]
                features = {}
                for feat in selected_features:
                    val = row.get(feat, 0.0)
                    features[feat] = float(val) if not pd.isna(val) else 0.0
                # Add market_mode as a feature
                features["market_mode"] = int(row.get("market_mode", 1))
                features["fear_greed"] = float(row.get("fear_greed", 50))
                features["btc_ema_cross"] = float(row.get("btc_ema_cross", 0))

                # Generate labels
                t_copy = dict(t)
                t_copy["market_mode"] = int(row.get("market_mode", 1))
                labels = generate_multiplier_labels(t_copy)
                features.update(labels)
                features["entry_time"] = str(entry_time)
                matched.append(features)

        if len(matched) >= MIN_TRADES:
            datasets[coin] = pd.DataFrame(matched)
            print(f"  {coin}: {len(matched)} matched trades")
        elif matched:
            print(f"  {coin}: only {len(matched)} trades (need {MIN_TRADES}), skipping")
        else:
            print(f"  {coin}: no matches, skipping")

    return datasets


# ════════════════════════════════════════════════════════
# MODEL TRAINING
# ════════════════════════════════════════════════════════

def train_param_multiplier(datasets):
    """Train RandomForest regressor per coin for param multipliers."""
    results = {}
    tscv = TimeSeriesSplit(n_splits=min(N_SPLITS, MIN_TRADES))

    for coin in COINS:
        if coin not in datasets:
            continue
        df = datasets[coin]

        feature_cols = [c for c in df.columns if c not in MULTIPLIER_TARGETS + ["entry_time"]]
        X = df[feature_cols].fillna(0)
        y = df[MULTIPLIER_TARGETS]

        # TimeSeriesSplit CV for validation
        cv_mae_list = []
        cv_r2_list = []
        for train_idx, test_idx in tscv.split(X):
            X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
            y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
            scaler = StandardScaler()
            X_tr_s = scaler.fit_transform(X_tr)
            X_te_s = scaler.transform(X_te)
            model = MultiOutputRegressor(RandomForestRegressor(
                n_estimators=200, max_depth=6, max_features="log2",
                min_samples_leaf=5, random_state=123, n_jobs=-1,
                ccp_alpha=0.02
            ))
            model.fit(X_tr_s, y_tr)
            preds = model.predict(X_te_s)
            mae_per_target = mean_absolute_error(y_te, preds, multioutput="raw_values")
            cv_mae_list.append(mae_per_target)
            cv_r2_list.append(r2_score(y_te, preds, multioutput="raw_values"))

        # Final model on all data
        scaler_final = StandardScaler()
        X_scaled = scaler_final.fit_transform(X)
        model_final = MultiOutputRegressor(RandomForestRegressor(
            n_estimators=300, max_depth=8, max_features="log2",
            min_samples_leaf=3, random_state=123, n_jobs=-1,
            ccp_alpha=0.01
        ))
        model_final.fit(X_scaled, y)

        # Final metrics
        preds_final = model_final.predict(X_scaled)
        final_mae = mean_absolute_error(y, preds_final, multioutput="raw_values")
        final_r2 = r2_score(y, preds_final, multioutput="raw_values")

        # Per-target MAE
        mae_dict = {MULTIPLIER_TARGETS[i]: round(float(final_mae[i]), 4) for i in range(len(MULTIPLIER_TARGETS))}
        r2_dict = {MULTIPLIER_TARGETS[i]: round(float(final_r2[i]), 4) for i in range(len(MULTIPLIER_TARGETS))}

        # Label stats (for sanity check)
        label_stats = {}
        for tgt in MULTIPLIER_TARGETS:
            vals = y[tgt]
            label_stats[tgt] = {
                "min": round(float(vals.min()), 3),
                "max": round(float(vals.max()), 3),
                "mean": round(float(vals.mean()), 3),
                "median": round(float(vals.median()), 3),
            }

        results[coin] = {
            "model": model_final,
            "scaler": scaler_final,
            "feature_cols": feature_cols,
            "metrics": {
                "cv_mae_mean": round(float(np.mean(cv_mae_list)), 4) if cv_mae_list else 0,
                "final_mae_per_target": mae_dict,
                "final_r2_per_target": r2_dict,
                "n_trades": len(df),
            },
            "label_stats": label_stats,
        }
        print(f"  {coin}: trained ({len(df)} trades, MAE={np.mean(final_mae):.4f})")

    return results


# ════════════════════════════════════════════════════════
# MODEL EXPORT
# ════════════════════════════════════════════════════════

def export_models(results):
    """Export trained models + inference script to production."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Ensure PROD_MODELS_DIR has a param_multiplier subdirectory
    prod_dir = PROD_MODELS_DIR / "param_multipliers"
    prod_dir.mkdir(parents=True, exist_ok=True)

    summary = {}
    for coin, info in results.items():
        coin_dir = MODELS_DIR / coin
        coin_dir.mkdir(parents=True, exist_ok=True)

        # Export to jesse-research
        joblib.dump(info["model"], coin_dir / f"{coin}_param_mult_model.pkl")
        joblib.dump(info["scaler"], coin_dir / f"{coin}_param_mult_scaler.pkl")
        joblib.dump(info["feature_cols"], coin_dir / f"{coin}_param_mult_features.pkl")

        # Export to production
        joblib.dump(info["model"], prod_dir / f"{coin}_param_mult_model.pkl")
        joblib.dump(info["scaler"], prod_dir / f"{coin}_param_mult_scaler.pkl")
        joblib.dump(info["feature_cols"], prod_dir / f"{coin}_param_mult_features.pkl")

        metadata = {
            "coin": coin,
            "trained_at": datetime.now().isoformat(),
            "model_type": "RandomForestRegressor (MultiOutput)",
            "targets": MULTIPLIER_TARGETS,
            "label_type": "optimal_multipliers",
            "features_source": "fase5_51_features + btc_context",
            "metrics": info["metrics"],
            "label_stats": info["label_stats"],
            "is_optimized": True,
            "fase7_param_multiplier": True,
        }
        with open(coin_dir / f"{coin}_param_mult_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        with open(prod_dir / f"{coin}_param_mult_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        m = info["metrics"]
        print(f"  {coin}: exported to {coin_dir}")
        print(f"    Trades: {m['n_trades']}")
        print(f"    MAE per target: {m['final_mae_per_target']}")
        print(f"    Label stats: {json.dumps(info['label_stats'], default=str)}")

        summary[coin] = {
            "n_trades": m["n_trades"],
            "final_mae_per_target": m["final_mae_per_target"],
            "final_r2_per_target": m["final_r2_per_target"],
        }

    with open(MODELS_DIR / "param_multiplier_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n  Models: {MODELS_DIR}")
    print(f"  Production: {prod_dir}")
    print(f"  Deploy: models deployed to {prod_dir}")
    return summary


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  FASE 7: ML Param Multiplier Training (Option A)")
    print("  effective_param = per_coin_base × ml_multiplier")
    print("=" * 60)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Load selected features from Fase 5
    if FASE5_FEATURES_PKL.exists():
        selected_features = joblib.load(FASE5_FEATURES_PKL)
        print(f"\nFeatures: {len(selected_features)} (from Fase 5)")
    else:
        # Fallback: use all computed features
        print("\nWarning: Fase 5 features not found, using all features")

    # Load trades
    trades = load_trades()
    print(f"Trades: {len(trades)}")

    # Step 1: Load/download candle data and compute features
    print(f"\n{'─'*40}")
    print("  Step 1: Load candle data + compute features")
    print(f"{'─'*40}")
    feature_data = load_or_download_features()

    if not feature_data:
        print("  ERROR: No feature data available")
        return

    # Step 2: Match trades to features and generate labels
    print(f"\n{'─'*40}")
    print("  Step 2: Match trades + generate multiplier labels")
    print(f"{'─'*40}")

    # Need to handle selected_features
    if FASE5_FEATURES_PKL.exists():
        sf = joblib.load(FASE5_FEATURES_PKL)
    else:
        # Use all numeric columns except OHLCV and context
        first_coin = list(feature_data.keys())[0]
        sf = [c for c in feature_data[first_coin].columns
              if c not in ("open", "high", "low", "close", "volume",
                           "timestamp", "market_mode", "fear_greed", "btc_ema_cross")]

    datasets = build_training_dataset(trades, feature_data, sf)

    if not datasets:
        print("\n  ERROR: No training data generated")
        return

    # Step 3: Train models
    print(f"\n{'─'*40}")
    print("  Step 3: Train per-coin RandomForest regressors")
    print(f"{'─'*40}")
    results = train_param_multiplier(datasets)

    # Step 4: Export
    print(f"\n{'─'*40}")
    print("  Step 4: Export models")
    print(f"{'─'*40}")
    export_models(results)

    # Summary
    print(f"\n{'='*60}")
    print("  PARAM MULTIPLIER TRAINING COMPLETE")
    print(f"{'='*60}")
    for coin in COINS:
        if coin in results:
            m = results[coin]["metrics"]
            print(f"  {coin}: trades={m['n_trades']}")
    print(f"\n  Models: {MODELS_DIR}")
    print(f"  Production: {PROD_MODELS_DIR / 'param_multipliers'}")
    print(f"  Runtime: param-multiplier-inference.py")


if __name__ == "__main__":
    main()
