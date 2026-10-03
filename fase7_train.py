#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# fase7_train.py — Fase 7: Trade-Level ML Retraining
#
# Re-entrena modelos ML usando TRADE-LEVEL labels (is_profitable)
# en lugar de candle-level labels (price_direction) de Fase 5.
#
# Pipeline:
#   1. Download fresh 5m candle data from Binance public API (no keys)
#   2. Compute 51 features per coin (pandas/numpy, NO talib)
#   3. Match production trades by entry timestamp
#   4. Label: is_profitable = 1 if pnlUSDT > 0, else 0
#   5. Train RandomForest + LogisticRegression (TimeSeriesSplit CV)
#   6. Export models to fase7_models/{coin}/ and deploy to production
#
# Refs: issue #44 (Fase 7 — production model improvement)
# Firma: Perrobotron Aterrorrizar!!
# ═══════════════════════════════════════════════════════════════════════════

import json
import urllib.request
import pandas as pd
import numpy as np
import joblib
import warnings
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

# ════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
TRADE_HISTORY = WORKSPACE / "crypto-bots" / "trade-history.json"
PROD_MODELS_DIR = WORKSPACE / "ml" / "models_optimized"
MODELS_DIR = Path("/home/overgon/jesse-research/fase7_models")
DATA_DIR = WORKSPACE / "backtest" / "data"

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]
BINANCE_URL = "https://api.binance.com/api/v3/klines"

# Fase 5 selected features (51) — same feature set
FASE5_FEATURES_PKL = PROD_MODELS_DIR / "LINK_selected_features.pkl"

# RF hyperparameters from Fase 5
RF_PARAMS = {
    "n_estimators": 300, "max_depth": 6, "max_features": "log2",
    "min_samples_split": 50, "min_samples_leaf": 25,
    "class_weight": "balanced", "random_state": 123, "n_jobs": -1, "ccp_alpha": 0.02,
}

N_SPLITS = 5
MIN_TRADES = 5
DAYS_TO_DOWNLOAD = 60  # 60 days ≈ 17K candles/coin (~30 trades/coin)


# ════════════════════════════════════════════════════════
# INDICATORS (pandas/numpy — no talib)
# ════════════════════════════════════════════════════════

def rsi_ewm(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    alpha = 1.0 / period
    return 100 - (100 / (1 + gain.ewm(alpha=alpha, adjust=False).mean() /
                 (loss.ewm(alpha=alpha, adjust=False).mean() + 1e-10)))


def macd_line(close, fast=12, slow=26, signal=9):
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    macd = ema_f - ema_s
    sig = macd.ewm(span=signal, adjust=False).mean()
    return macd, sig, macd - sig


def bollinger_bands(close, period=20, mult=2.0):
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper, lower = sma + mult * std, sma - mult * std
    return upper, sma, lower, (close - lower) / (upper - lower + 1e-10), (upper - lower) / sma


def atr(high, low, close, period=14):
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/period, adjust=False).mean()


def adx(high, low, close, period=14):
    dm_plus = high.diff().where((high.diff() > 0) & (high.diff() > low.diff()), 0)
    dm_minus = (-low.diff()).where((low.diff() < 0) & (high.diff() < low.diff()), 0)
    tr_val = atr(high, low, close, period)
    di_plus = (dm_plus.ewm(alpha=1.0/period, adjust=False).mean() / (tr_val + 1e-10)) * 100
    di_minus = (dm_minus.ewm(alpha=1.0/period, adjust=False).mean() / (tr_val + 1e-10)) * 100
    dx = (abs(di_plus - di_minus) / (di_plus + di_minus + 1e-10)) * 100
    return dx.ewm(alpha=1.0/period, adjust=False).mean()


def stochastic(high, low, close, k=14, d=3):
    ll = low.rolling(k).min()
    hh = high.rolling(k).max()
    slowk = ((close - ll) / (hh - ll + 1e-10)) * 100
    return slowk, slowk.rolling(d).mean()


def cci(high, low, close, period=20):
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(period).mean()
    md = (tp - sma_tp).abs().rolling(period).mean()
    return (tp - sma_tp) / (md * 0.015 + 1e-10)


def willr(high, low, close, period=14):
    ll = low.rolling(period).min()
    hh = high.rolling(period).max()
    return -100 * ((hh - close) / (hh - ll + 1e-10))


def compute_all_features(df):
    """Compute the 51 Fase 5 features from OHLCV DataFrame."""
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]
    df["rsi"] = rsi_ewm(c, 14)
    m, ms, mh = macd_line(c)
    df["macd"], df["macdsignal"], df["macdhist"] = m, ms, mh
    bu, bm, bl, bp, bw = bollinger_bands(c)
    df["bb_upper"], df["bb_middle"], df["bb_lower"] = bu, bm, bl
    df["bb_percent"], df["bb_width"] = bp, bw
    df["sma_20"], df["sma_50"] = c.rolling(20).mean(), c.rolling(50).mean()
    df["ema_12"] = c.ewm(span=12, adjust=False).mean()
    df["ema_26"] = c.ewm(span=26, adjust=False).mean()
    df["atr"] = atr(h, l, c, 14)
    df["adx"] = adx(h, l, c, 14)
    sk, sd = stochastic(h, l, c)
    df["slowk"], df["slowd"] = sk, sd
    df["cci"] = cci(h, l, c)
    df["willr"] = willr(h, l, c)
    df["momentum"] = c.diff(10)
    df["roc"] = ((c - c.shift(10)) / c.shift(10)) * 100
    df["price_change_1h"] = c.pct_change(12) * 100
    df["volatility_20"] = c.pct_change().rolling(20).std()

    # OBV
    obv = pd.Series(0.0, index=df.index)
    for i in range(1, len(df)):
        if c.iloc[i] > c.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + v.iloc[i]
        elif c.iloc[i] < c.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - v.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]
    df["obv"] = obv
    df["obv_sma"] = obv.rolling(20).mean()
    df["volume_ratio"] = v / (v.rolling(20).mean() + 1e-10)

    df["rsi_lag_1"] = df["rsi"].shift(1)
    df["rsi_lag_2"] = df["rsi"].shift(2)
    df["rsi_diff_1"] = df["rsi"].diff(1)

    for w in [5, 10, 20]:
        df[f"volume_min_{w}"] = v.rolling(w).min()
        df[f"volume_max_{w}"] = v.rolling(w).max()
        df[f"volume_median_{w}"] = v.rolling(w).median()
        df[f"close_min_{w}"] = c.rolling(w).min()
        df[f"close_max_{w}"] = c.rolling(w).max()
        df[f"close_median_{w}"] = c.rolling(w).median()

    df["open"], df["high"], df["low"], df["close"], df["volume"] = o, h, l, c, v
    return df


def add_btc_context(df_coin, btc_df):
    """Add BTC context features: btc_ema_cross, fear_greed, market_mode, confidence_score."""
    n = len(df_coin)
    btc = btc_df.sort_index()
    btc_1h = btc.resample("1h").agg({"open": "first", "high": "max", "low": "min",
                                      "close": "last", "volume": "sum"}).dropna()
    close_1h = btc_1h["close"]
    ema20_1h = close_1h.ewm(span=20, adjust=False).mean()
    ema50_1h = close_1h.ewm(span=50, adjust=False).mean()
    rsi_1h = rsi_ewm(close_1h, 14)

    idx = df_coin.index
    e20 = ema20_1h.reindex(idx, method="ffill").fillna(0).values
    e50 = ema50_1h.reindex(idx, method="ffill").fillna(0).values
    br = rsi_1h.reindex(idx, method="ffill").fillna(50).values
    bp = close_1h.reindex(idx, method="ffill").fillna(0).values

    def align(arr):
        if len(arr) < n:
            return np.concatenate([arr, np.full(n - len(arr), arr[-1] if len(arr) > 0 else 0)])
        return arr[:n]

    e20, e50 = align(e20), align(e50)
    br, bp = align(br), align(bp)
    cross = e20 - e50

    df_coin["btc_ema_cross"] = cross
    fg = np.full(n, 50.0)
    bullish = (bp > e20) & (e20 > e50)
    bearish = (bp < e20) & (e20 < e50)
    fg[bullish] += 20; fg[bearish] -= 20
    fg[br > 70] += 10; fg[br < 30] -= 10
    fg[cross > 0] += 5; fg[cross <= 0] -= 5
    df_coin["fear_greed"] = np.clip(fg, 0, 100)

    mode = np.full(n, 1, dtype=int)
    mode[br > 70] = 4; mode[br < 30] = 3
    mode[(fg < 40) & (bp < e20)] = 0
    mode[(fg > 60) & (bp > e20)] = 2
    mode[(bp > e20) & (fg >= 40) & (fg <= 60)] = 5
    df_coin["market_mode"] = mode

    ema_fast = df_coin["ema_12"].values if "ema_12" in df_coin.columns else np.zeros(n)
    ema_slow = df_coin["close"].ewm(span=140, adjust=False).mean().values
    rsi_val = df_coin["rsi"].values if "rsi" in df_coin.columns else np.full(n, 50)
    vol_ratio = df_coin["volume_ratio"].values if "volume_ratio" in df_coin.columns else np.ones(n)
    adx_val = df_coin["adx"].values if "adx" in df_coin.columns else np.zeros(n)

    score = np.full(n, 50.0)
    score[ema_fast > ema_slow] += 15; score[ema_fast <= ema_slow] -= 15
    score[(rsi_val > 30) & (rsi_val < 75)] += 10
    score[rsi_val > 75] -= 20; score[rsi_val < 30] -= 10
    score[vol_ratio >= 1.0] += 5; score[vol_ratio < 1.0] -= 5
    score[adx_val > 20] += 8; score[adx_val <= 20] -= 3
    score[(bp > e20)] += 7; score[~(bp > e20)] -= 10
    score[fg > 60] += 5; score[fg < 40] -= 10
    df_coin["confidence_score"] = np.clip(score, 0, 100)
    return df_coin


# ════════════════════════════════════════════════════════
# DATA DOWNLOAD (Binance public API)
# ════════════════════════════════════════════════════════

def download_klines(symbol, interval="5m", days=60):
    """Download kline data from Binance public API (all pages)."""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    all_candles = []
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)

    while start_ts < end_ts:
        url = f"{BINANCE_URL}?symbol={symbol}&interval={interval}&startTime={start_ts}&endTime={end_ts}&limit=1000"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read())
            if not data:
                break
            all_candles.extend(data)
            start_ts = data[-1][6] + 1
            if len(data) < 1000:
                break
        except Exception:
            break

    if not all_candles:
        return None

    df = pd.DataFrame(all_candles, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_vol", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
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
                    print(f"  {coin}: {len(df)} candles downloaded")
                else:
                    print(f"  {coin}: FAILED")
            except Exception as e:
                print(f"  {coin}: ERROR {e}")
    return results


# ════════════════════════════════════════════════════════
# TRADE MATCHING
# ════════════════════════════════════════════════════════

def load_trades():
    with open(TRADE_HISTORY) as f:
        hist = json.load(f)
    trades = hist["trades"]
    for t in trades:
        ts = t.get("timestamp", "")
        if ts:
            dt = pd.to_datetime(ts, format='mixed')
            if dt.tzinfo is not None:
                # tz-aware (e.g. -06:00 CST) → convert to UTC
                t["entry_dt"] = dt.tz_convert('UTC').tz_localize(None)
            else:
                # tz-naive assumed UTC (Binance candles are UTC)
                t["entry_dt"] = dt
        else:
            t["entry_dt"] = None
        t["is_profitable"] = 1 if t.get("pnlUSDT", 0) > 0 else 0
    return trades


def match_trades_to_features(trades, features_df, coin, selected_features):
    matched = []
    coin_trades = [t for t in trades if t["coin"] == coin and t["entry_dt"] is not None]
    feat_ts = features_df.index

    for t in coin_trades:
        entry_time = t["entry_dt"]
        diffs = abs((feat_ts - entry_time).total_seconds())
        min_idx = diffs.argmin()
        min_diff = diffs[min_idx]
        if min_diff <= 300:  # 5 min tolerance
            row = features_df.iloc[min_idx]
            features = {}
            for feat in selected_features:
                val = row.get(feat, 0.0)
                features[feat] = float(val) if not pd.isna(val) else 0.0
            features["is_profitable"] = t["is_profitable"]
            features["entry_time"] = str(entry_time)
            features["pnlUSDT"] = t.get("pnlUSDT", 0)
            matched.append(features)
    return pd.DataFrame(matched)


# ════════════════════════════════════════════════════════
# MODEL TRAINING
# ════════════════════════════════════════════════════════

def train_and_validate(X, y):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

    # Use StratifiedKFold(shuffle=True) — same approach as ml_pipeline_optimized.py
    # which trained ZEC successfully. TimeSeriesSplit creates single-class folds
    # with small trade datasets (24-59 trades), causing crashes + unreliable metrics.
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=42)
    rf_preds, lr_preds, all_actuals = [], [], []

    # CV for BOTH models — same folds, same scaler fit on train fold
    for train_idx, test_idx in skf.split(X, y):
        X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_te_s = scaler.transform(X_te)

        # RF
        rf = RandomForestClassifier(**RF_PARAMS)
        rf.fit(X_tr_s, y_tr)
        rf_preds.extend(rf.predict(X_te_s))

        # LR
        lr = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=123)
        lr.fit(X_tr_s, y_tr)
        lr_preds.extend(lr.predict(X_te_s))

        all_actuals.extend(y_te)

    # CV metrics — BOTH models evaluated the same way
    rf_cv = {
        "accuracy": accuracy_score(all_actuals, rf_preds),
        "precision": precision_score(all_actuals, rf_preds, zero_division=0),
        "recall": recall_score(all_actuals, rf_preds, zero_division=0),
        "f1": f1_score(all_actuals, rf_preds, zero_division=0),
    }
    lr_cv = {
        "accuracy": accuracy_score(all_actuals, lr_preds),
        "precision": precision_score(all_actuals, lr_preds, zero_division=0),
        "recall": recall_score(all_actuals, lr_preds, zero_division=0),
        "f1": f1_score(all_actuals, lr_preds, zero_division=0),
    }

    print(f"   RF CV:  acc={rf_cv['accuracy']:.4f} prec={rf_cv['precision']:.4f} "
          f"rec={rf_cv['recall']:.4f} f1={rf_cv['f1']:.4f}")
    print(f"   LR CV:  acc={lr_cv['accuracy']:.4f} prec={lr_cv['precision']:.4f} "
          f"rec={lr_cv['recall']:.4f} f1={lr_cv['f1']:.4f}")

    # Final models — trained on full scaled data
    scaler_final = StandardScaler()
    X_scaled = scaler_final.fit_transform(X)
    rf_final = RandomForestClassifier(**RF_PARAMS)
    rf_final.fit(X_scaled, y)
    lr_final = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=123)
    lr_final.fit(X_scaled, y)

    rf_train_acc = accuracy_score(y, rf_final.predict(X_scaled))
    lr_train_acc = accuracy_score(y, lr_final.predict(X_scaled))

    results = {
        "random_forest": {"model": rf_final, "scaler": scaler_final,
            "accuracy": rf_cv["accuracy"], "precision": rf_cv["precision"],
            "recall": rf_cv["recall"], "f1": rf_cv["f1"],
            "train_acc": rf_train_acc, "overfitting_gap": rf_train_acc - rf_cv["accuracy"]},
        "logistic_regression": {"model": lr_final, "scaler": scaler_final,
            "accuracy": lr_cv["accuracy"], "precision": lr_cv["precision"],
            "recall": lr_cv["recall"], "f1": lr_cv["f1"],
            "train_acc": lr_train_acc, "overfitting_gap": lr_train_acc - lr_cv["accuracy"]},
    }

    # Selection: use CV F1 as primary metric; require precision>0 AND recall>0
    rf_ok = rf_cv["precision"] > 0 and rf_cv["recall"] > 0
    lr_ok = lr_cv["precision"] > 0 and lr_cv["recall"] > 0

    if not rf_ok and not lr_ok:
        best = "random_forest"  # RF more robust to degenerate cases
        print("   ⚠️ Neither model has precision>0 & recall>0 — defaulting to RF")
    elif lr_ok and lr_cv["f1"] > rf_cv["f1"]:
        best = "logistic_regression"
        print(f"   ✅ LR selected: F1={lr_cv['f1']:.4f} > RF F1={rf_cv['f1']:.4f}")
    else:
        best = "random_forest"
        print(f"   ✅ RF selected: F1={rf_cv['f1']:.4f} >= LR F1={lr_cv['f1']:.4f}")

    return results, best


def export_models(coin, results, best, selected_features):
    coin_dir = MODELS_DIR / coin
    coin_dir.mkdir(parents=True, exist_ok=True)
    r = results[best]
    joblib.dump(r["model"], coin_dir / f"{coin}_optimized_model.pkl")
    joblib.dump(r["scaler"], coin_dir / f"{coin}_scaler_optimized.pkl")
    joblib.dump(selected_features, coin_dir / f"{coin}_selected_features.pkl")

    metadata = {
        "coin": coin, "trained_at": datetime.now().isoformat(),
        "model_type": best, "label_type": "is_profitable", "fase": 7,
        "metrics": {
            "accuracy": round(r.get("accuracy", 0), 4),
            "precision": round(r.get("precision", 0), 4),
            "recall": round(r.get("recall", 0), 4),
            "f1": round(r.get("f1", 0), 4),
            "train_accuracy": round(r.get("train_acc", 0), 4),
            "overfitting_gap": round(r.get("overfitting_gap", 0), 4),
        },
        "is_optimized": True, "fase7": True,
        "all_models": {k: {"accuracy": round(v.get("accuracy",0),4),
                          "precision": round(v.get("precision",0),4),
                          "recall": round(v.get("recall",0),4),
                          "f1": round(v.get("f1",0),4)} for k,v in results.items()},
    }
    with open(coin_dir / f"{coin}_optimized_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"    Exportado {coin}: {best} acc={metadata['metrics']['accuracy']:.4f} gap={metadata['metrics']['overfitting_gap']:.4f}")


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  FASE 7: Trade-Level ML Retraining (is_profitable)")
    print("=" * 60)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    selected_features = joblib.load(FASE5_FEATURES_PKL)
    print(f"\nFeatures: {len(selected_features)} (from Fase 5)")

    trades = load_trades()
    print(f"Trades: {len(trades)} (Apr 23 - Sep 28, 2026)")

    # Step 1: Download fresh 5m data
    print(f"\n{'─'*40}")
    print("  Step 1: Download fresh 5m candle data (Binance API, parallel)")
    print(f"{'─'*40}")
    candle_data = download_all_coins(COINS, DAYS_TO_DOWNLOAD)

    if "BTC" not in candle_data:
        print("  ERROR: No BTC data — cannot compute market context features")
        return

    btc_df = candle_data["BTC"]

    # Step 2: Compute features
    print(f"\n{'─'*40}")
    print("  Step 2: Compute 51 features per coin")
    print(f"{'─'*40}")
    feature_data = {}
    for coin in COINS:
        if coin not in candle_data:
            continue
        df = compute_all_features(candle_data[coin].copy())
        df = add_btc_context(df, btc_df)
        feature_data[coin] = df
        print(f"  {coin}: {len(df)} rows, {len(df.columns)} cols")

    # Step 3-5: Match trades, train, export
    summary = {}
    for coin in COINS:
        if coin not in feature_data:
            continue
        print(f"\n{'─'*40}")
        print(f"  Training {coin}...")
        print(f"{'─'*40}")

        matched = match_trades_to_features(trades, feature_data[coin], coin, selected_features)
        if len(matched) < MIN_TRADES:
            print(f"  SKIP {coin}: {len(matched)} trades (<{MIN_TRADES})")
            continue

        winrate = matched["is_profitable"].mean()
        print(f"  Matched: {len(matched)} trades, winrate={winrate:.1%}")

        # Sort chronologically — TimeSeriesSplit assumes temporal order
        matched = matched.sort_values("entry_time").reset_index(drop=True)

        X = matched[selected_features].fillna(0)
        y = matched["is_profitable"]
        results, best = train_and_validate(X, y)
        export_models(coin, results, best, selected_features)

        summary[coin] = {
            "model": best,
            "accuracy": round(results[best].get("accuracy", 0), 4),
            "precision": round(results[best].get("precision", 0), 4),
            "recall": round(results[best].get("recall", 0), 4),
            "f1": round(results[best].get("f1", 0), 4),
            "gap": round(results[best].get("overfitting_gap", 0), 4),
            "n_trades": len(matched),
            "winrate": round(float(winrate), 4),
        }

    with open(MODELS_DIR / "fase7_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print("  FASE 7 COMPLETE")
    print(f"{'='*60}")
    for coin, info in summary.items():
        print(f"  {coin}: {info['model']} acc={info['accuracy']:.4f} f1={info['f1']:.4f} prec={info['precision']:.4f} rec={info['recall']:.4f} trades={info['n_trades']}")
    print(f"\n  Models: {MODELS_DIR}")
    print(f"  Deploy: cp fase7_models/{{coin}}/*.pkl -> {PROD_MODELS_DIR}/")


if __name__ == "__main__":
    main()
