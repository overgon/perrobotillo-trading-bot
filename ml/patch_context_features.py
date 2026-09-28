#!/usr/bin/env python3
"""
Agregar las 4 features faltantes (btc_ema_cross, fear_greed, market_mode,
confidence_score) a los CSVs de features existentes.

Logica idéntica a PerrobotilloStrategy Fase 4 Optuna (ema_fast=12, ema_slow=140,
rsi_ob=75, rsi_os=30, min_adx=20).
"""

import pandas as pd
import numpy as np
import os
import warnings
warnings.filterwarnings("ignore")

WORKSPACE = "/home/overgon/.openclaw/workspace"
DATA_DIR = f"{WORKSPACE}/backtest/data"
FEATURES_DIR = f"{WORKSPACE}/ml/features"
COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]


def compute_rsi_ewm(prices, period=14):
    """Wilder RSI (alpha=1/period)."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def compute_btc_context(btc_5m):
    """Resample BTC 5m to 1h, compute EMA20/EMA50/RSI/price, map to 5m."""
    btc_5m = btc_5m.sort_index()
    close_1h = btc_5m["close"].resample("1h").last().dropna()
    ema20_1h = close_1h.ewm(span=20, adjust=False).mean()
    ema50_1h = close_1h.ewm(span=50, adjust=False).mean()
    rsi_1h = compute_rsi_ewm(close_1h, 14)

    idx = btc_5m.index
    ema20 = ema20_1h.reindex(idx, method="ffill").fillna(0).values
    ema50 = ema50_1h.reindex(idx, method="ffill").fillna(0).values
    rsi = rsi_1h.reindex(idx, method="ffill").fillna(50).values
    close = close_1h.reindex(idx, method="ffill").fillna(0).values
    return {"ema20": ema20, "ema50": ema50, "rsi": rsi, "price": close, "cross": ema20 - ema50}


def align_n(values, n):
    """Truncate or right-pad with last value to match n rows."""
    if len(values) < n:
        return np.concatenate([values, np.full(n - len(values), values[-1])])
    return values[:n]


def add_btc_context_features(coin, df):
    """Add 4 missing BTC context features to a coin's DataFrame."""
    print(f"\n  - {coin}: computing BTC context...")
    n = len(df)

    btc_file = f"{DATA_DIR}/BTC_USDT_5m.csv"
    btc_5m = pd.read_csv(btc_file, parse_dates=["timestamp"])
    btc_5m = btc_5m.set_index("timestamp")
    ctx = compute_btc_context(btc_5m)

    ema20 = align_n(ctx["ema20"], n)
    ema50 = align_n(ctx["ema50"], n)
    btc_rsi = align_n(ctx["rsi"], n)
    btc_price = align_n(ctx["price"], n)
    cross = align_n(ctx["cross"], n)

    # 1. btc_ema_cross
    df["btc_ema_cross"] = cross

    # 2. fear_greed (0-100)
    fg = np.full(n, 50.0)
    bullish = (btc_price > ema20) & (ema20 > ema50)
    bearish = (btc_price < ema20) & (ema20 < ema50)
    fg[bullish] += 20
    fg[bearish] -= 20
    fg[btc_rsi > 70] += 10
    fg[btc_rsi < 30] -= 10
    fg[cross > 0] += 5
    fg[cross <= 0] -= 5
    df["fear_greed"] = np.clip(fg, 0, 100)

    # 3. market_mode (0-5)
    mode = np.full(n, 1, dtype=int)
    mode[btc_rsi > 70] = 4
    mode[btc_rsi < 30] = 3
    mode[(fg < 40) & (btc_price < ema20)] = 0
    mode[(fg > 60) & (btc_price > ema20)] = 2
    mode[(btc_price > ema20) & (fg >= 40) & (fg <= 60)] = 5
    df["market_mode"] = mode

    # 4. confidence_score (ML proxy, 0-100)
    ema_fast = df["ema_12"].values if "ema_12" in df.columns else np.zeros(n)
    ema_slow = df["close"].ewm(span=140, adjust=False).mean().values
    rsi_val = df["rsi"].values if "rsi" in df.columns else np.full(n, 50)
    vol_ratio = df["volume_ratio"].values if "volume_ratio" in df.columns else np.ones(n)
    adx_val = df["adx"].values if "adx" in df.columns else np.zeros(n)

    score = np.full(n, 50.0)
    score[ema_fast > ema_slow] += 15
    score[ema_fast <= ema_slow] -= 15
    score[(rsi_val > 30) & (rsi_val < 75)] += 10
    score[rsi_val > 75] -= 20
    score[rsi_val < 30] -= 10
    score[vol_ratio >= 1.0] += 5
    score[vol_ratio < 1.0] -= 5
    score[adx_val > 20] += 8
    score[adx_val <= 20] -= 3
    bullish_btc = btc_price > ema20
    score[bullish_btc] += 7
    score[~bullish_btc] -= 10
    score[fg > 60] += 5
    score[fg < 40] -= 10
    df["confidence_score"] = np.clip(score, 0, 100)

    return df


def main():
    print("=" * 60)
    print("  BTC Context Feature Patcher - Fase 5 Deployment")
    print("=" * 60)
    for coin in COINS:
        csv_path = f"{FEATURES_DIR}/{coin}_features.csv"
        if not os.path.exists(csv_path):
            print(f"  [PASS] {csv_path} no existe")
            continue
        df = pd.read_csv(csv_path)
        df = add_btc_context_features(coin, df)
        df.to_csv(csv_path, index=False)
        print(f"  OK {coin}: {len(df)} rows x {len(df.columns)} cols")
        for feat in ["btc_ema_cross", "fear_greed", "market_mode", "confidence_score"]:
            vals = df[feat].dropna()
            print(f"    {feat}: min={vals.min():.4f}, max={vals.max():.4f}, mean={vals.mean():.4f}")
    print(f"\n{'='*60}")
    print("  Listo. Todas las monedas tienen market context features.")
    print("=" * 60)


if __name__ == "__main__":
    main()
