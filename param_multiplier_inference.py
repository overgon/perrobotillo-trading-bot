#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# param-multiplier-inference.py — Runtime inference for param multipliers
#
# Called by: trading bot (pre-trade) + dashboard API (/api/param-multipliers)
#
# Flow:
#   1. Load latest 5m candle data per coin (from CSV or download)
#   2. Compute 51 Fase 5 features + BTC context
#   3. Per coin: load model + scaler + feature cols → predict multipliers
#   4. Output JSON: {coin: {tp1_mult, tp2_mult, tp3_mult, sl_mult, size_mult}}
#
# effective_param = per_coin_base × multiplier
#
# Firma: Perrobotron Aterrorrizar!!
# ═══════════════════════════════════════════════════════════════════════════

import json
import sys
import os
import joblib
import warnings
from pathlib import Path
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np

# Reuse feature computation from fase7_train
sys.path.insert(0, "/home/overgon/jesse-research")
sys.path.insert(0, "/home/overgon/jesse-research")
from fase7_train import (
    compute_all_features,
    add_btc_context,
    rsi_ewm,
    bollinger_bands,
    macd_line,
    atr,
    download_klines,
)

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
DATA_DIR = WORKSPACE / "backtest" / "data"
PROD_MODELS_DIR = WORKSPACE / "ml" / "models_optimized" / "param_multipliers"
TRADING_BOT_DIR = WORKSPACE / "crypto-bots"
COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]
BINANCE_URL = "https://api.binance.com/api/v3/klines"

# Multiplier targets in order
MULTIPLIER_TARGETS = ["tp1_mult", "tp2_mult", "tp3_mult", "sl_mult", "size_mult"]

# Default multipliers (neutral, no adjustment) when no model available
DEFAULT_MULTIPLIERS = {
    "tp1_mult": 1.0, "tp2_mult": 1.0, "tp3_mult": 1.0,
    "sl_mult": 1.0, "size_mult": 1.0,
}


def load_latest_candles(coin, days=3):
    """Load latest candle data for a coin. Tries CSV first, falls back to download."""
    csv_path = DATA_DIR / f"{coin}_USDT_5m.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
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
            if len(df) > 50:
                return df.tail(100)  # last 100 rows
        except Exception:
            pass

    # Download last N days
    try:
        df = download_klines(f"{coin}USDT", "5m", days)
        return df.tail(100)
    except Exception:
        return None


def compute_current_features(coin, candle_data_all):
    """Compute features for the latest candle of a coin."""
    if coin not in candle_data_all:
        return None

    df = candle_data_all[coin].copy()
    df = compute_all_features(df)

    # Add BTC context if we have BTC data
    if "BTC" in candle_data_all:
        df = add_btc_context(df, candle_data_all["BTC"])

    # Return the latest row's features
    latest = df.iloc[-1:].copy()
    return latest


def predict_multipliers(coin, features_df, selected_features):
    """Load model and predict multipliers for a coin."""
    model_path = PROD_MODELS_DIR / f"{coin}_param_mult_model.pkl"
    scaler_path = PROD_MODELS_DIR / f"{coin}_param_mult_scaler.pkl"
    features_path = PROD_MODELS_DIR / f"{coin}_param_mult_features.pkl"

    if not all(p.exists() for p in [model_path, scaler_path, features_path]):
        return DEFAULT_MULTIPLIERS.copy()

    # Load model artifacts
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    feature_cols = joblib.load(features_path)

    # Extract selected features from latest candle
    X = features_df[feature_cols].fillna(0).tail(1)
    X_scaled = scaler.transform(X)

    # Predict
    preds = model.predict(X_scaled)[0]

    # Build output dict
    result = {}
    for i, target in enumerate(MULTIPLIER_TARGETS):
        val = float(preds[i])
        result[target] = round(val, 4)

    return result


def get_current_multipliers():
    """Get current param multipliers for all coins.

    Called by trading bot + dashboard API.
    Returns: {coin: {tp1_mult, tp2_mult, tp3_mult, sl_mult, size_mult}}
    """
    # Load latest candle data for all coins (parallel)
    from concurrent.futures import ThreadPoolExecutor, as_completed

    candle_data = {}
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(load_latest_candles, c): c for c in COINS}
        for future in as_completed(futures):
            coin = futures[future]
            try:
                df = future.result()
                if df is not None:
                    candle_data[coin] = df
            except Exception:
                pass

    # Compute features for each coin
    result = {}
    for coin in COINS:
        if coin not in candle_data:
            result[coin] = DEFAULT_MULTIPLIERS.copy()
            continue

        features_df = compute_current_features(coin, candle_data)
        if features_df is None or len(features_df) == 0:
            result[coin] = DEFAULT_MULTIPLIERS.copy()
            continue

        # Load selected features from Fase 5 (use any coin's pkl — same features)
        feat_path = PROD_MODELS_DIR / "BTC_param_mult_features.pkl"
        if not feat_path.exists():
            feat_path = PROD_MODELS_DIR / "LINK_param_mult_features.pkl"
        if feat_path.exists():
            selected_features = joblib.load(feat_path)
        else:
            # Fallback: use all feature columns
            selected_features = [c for c in features_df.columns
                                 if c not in ("open", "high", "low", "close", "volume", "timestamp")]

        multipliers = predict_multipliers(coin, features_df, selected_features)
        result[coin] = multipliers

    return result


def compute_effective_config(per_coin_base, multipliers):
    """Apply multipliers to per-coin config to get effective params.
    
    Args:
        per_coin_base: {TP1, TP2, TP3, STOP_LOSS, POSITION_SIZE, ...} from per-coin-config.env
        multipliers: {tp1_mult, tp2_mult, tp3_mult, sl_mult, size_mult} from ML model
    
    Returns:
        {TP1_eff, TP2_eff, TP3_eff, STOP_LOSS_eff, POSITION_SIZE_eff, ...}
    """
    effective = dict(per_coin_base)
    if "TP1" in per_coin_base:
        effective["TP1_eff"] = round(per_coin_base["TP1"] * multipliers.get("tp1_mult", 1.0), 4)
    if "TP2" in per_coin_base:
        effective["TP2_eff"] = round(per_coin_base["TP2"] * multipliers.get("tp2_mult", 1.0), 4)
    if "TP3" in per_coin_base:
        effective["TP3_eff"] = round(per_coin_base["TP3"] * multipliers.get("tp3_mult", 1.0), 4)
    if "STOP_LOSS" in per_coin_base:
        effective["STOP_LOSS_eff"] = round(per_coin_base["STOP_LOSS"] * multipliers.get("sl_mult", 1.0), 4)
    if "POSITION_SIZE" in per_coin_base:
        effective["POSITION_SIZE_eff"] = round(per_coin_base["POSITION_SIZE"] * multipliers.get("size_mult", 1.0), 2)
    return effective


if __name__ == "__main__":
    # Quick CLI: print multipliers for all coins
    multipliers = get_current_multipliers()
    print(json.dumps(multipliers, indent=2, default=str))
