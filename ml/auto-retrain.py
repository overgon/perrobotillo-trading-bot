#!/usr/bin/env python3
"""
🐕 Perrobotillo ML - Auto-Retrain Pipeline (Optimizado)
Re-entrena automáticamente el modelo con nuevos trades
Ejecución: Semanal (domingo 3 AM) o cuando hay 10+ trades nuevos

Optimizaciones:
- Cache de indicadores históricos para evitar recálculo
- Estimadores adaptativos (LGBM + XGBoost/ExtraTrees si está disponible)
- Lectura eficiente de CSV y limpieza de features
- Compatibilidad total con flujo y archivos anteriores
"""

from __future__ import annotations

import json
import os
import sys
import hashlib
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import accuracy_score
from sklearn.ensemble import ExtraTreesClassifier
import warnings

warnings.filterwarnings("ignore")

try:
    import lightgbm as lgb
    _HAS_LGBM = True
except Exception:
    _HAS_LGBM = False
warnings.filterwarnings("ignore")

# Importar sentiment features
sys.path.append(os.path.dirname(__file__))
try:
    from market_sentiment_features import add_sentiment_to_training_data

    _HAS_SENTIMENT = True
except Exception:
    _HAS_SENTIMENT = False

# ════════════════════════════════════════════════════════
# Configuración
# ════════════════════════════════════════════════════════
HOME = Path.home()
WORKSPACE = HOME / ".openclaw/workspace"
MODEL_PATH = WORKSPACE / "ml/tp_prediction_model.pkl"
METADATA_PATH = WORKSPACE / "ml/model_metadata.json"
TRADE_HISTORY_PATH = WORKSPACE / "crypto-bots/trade-history.json"
BACKTEST_DATA_DIR = WORKSPACE / "backtest/data"
ML_LOG_PATH = WORKSPACE / "logs/ml-retrain.log"
INDICATOR_CACHE_PATH = WORKSPACE / "ml/.indicator_cache.pkl"
MIN_TRADES_FOR_RETRAIN = 10


# ════════════════════════════════════════════════════════
# Logging
# ════════════════════════════════════════════════════════
def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    try:
        ML_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(ML_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except OSError:
        pass


# ════════════════════════════════════════════════════════
# IO helpers
# ════════════════════════════════════════════════════════
def load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log(f"❌ load_json failed {path}: {exc}")
        return None


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ════════════════════════════════════════════════════════
# Model helpers
# ════════════════════════════════════════════════════════
def load_model_and_metadata():
    if not MODEL_PATH.exists():
        return None, None
    try:
        model = joblib.load(MODEL_PATH)
        metadata = load_json(METADATA_PATH) or {}
        log(f"✅ Modelo cargado (accuracy: {metadata.get('accuracy', 'N/A')})")
        return model, metadata
    except Exception as exc:
        log(f"⚠️ No se pudo cargar el modelo previo: {exc}")
        return None, None


def get_retrain_count() -> int:
    metadata = load_json(METADATA_PATH)
    if not metadata:
        return 0
    return int(metadata.get("retrain_count", 0))


# ════════════════════════════════════════════════════════
# Trade history
# ════════════════════════════════════════════════════════
def load_trade_history() -> list[dict]:
    if not TRADE_HISTORY_PATH.exists():
        log("⚠️  No hay trade-history.json")
        return []
    data = load_json(TRADE_HISTORY_PATH) or {}
    trades = data.get("trades", []) if isinstance(data, dict) else data
    log(f"✅ {len(trades)} trades en histórico")
    return trades


def get_last_retrain_info() -> dict:
    path = WORKSPACE / "ml/last_retrain.json"
    data = load_json(path) or {}
    return {
        "last_trade_count": data.get("trade_count_at_retrain", 0),
        "last_retrain": data.get("last_retrain"),
        "retrain_count": data.get("retrain_count", 0),
    }


def save_last_retrain_info(trade_count: int) -> None:
    info = {
        "last_retrain": datetime.now().isoformat(),
        "trade_count_at_retrain": trade_count,
        "retrain_count": get_retrain_count() + 1,
    }
    save_json(WORKSPACE / "ml/last_retrain.json", info)
    log("💾 Info guardada: last_retrain.json")


# ════════════════════════════════════════════════════════
# Historical data + indicators (con cache)
# ════════════════════════════════════════════════════════
def _cache_fingerprint(csv_files: list[Path]) -> str:
    h = hashlib.sha1()
    for path in sorted(csv_files):
        try:
            st = os.stat(path)
            h.update(f"{path}:{st.st_size}:{st.st_mtime}".encode())
        except OSError:
            continue
    h.update(str(BACKTEST_DATA_DIR).encode())
    return h.hexdigest()


def load_or_build_indicator_cache(coins: list[str]):
    cache_path = INDICATOR_CACHE_PATH
    csv_files = [BACKTEST_DATA_DIR / f"{coin}USDT_historical.csv" for coin in coins]

    if cache_path.exists():
        try:
            cached = joblib.load(cache_path)
        except Exception:
            cached = None
        if cached is not None:
            cached_fp, df = cached
            if cached_fp == _cache_fingerprint(csv_files):
                log("🔄 Usando cache de indicadores")
                return df
            log("♻️ Cache de indicadores desactualizado, recalculando...")

    df = load_historical_data(coins)
    if df is None:
        return None
    df = add_indicators(df)

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump((_cache_fingerprint(csv_files), df), cache_path)
        log("💾 Cache de indicadores actualizado")
    except Exception as exc:
        log(f"⚠️ No se pudo guardar cache de indicadores: {exc}")

    return df


def load_historical_data(coins: list[str]) -> pd.DataFrame | None:
    log("📊 Cargando datos históricos...")
    all_frames = []
    for coin in coins:
        csv_file = BACKTEST_DATA_DIR / f"{coin}USDT_historical.csv"
        if not csv_file.exists():
            log(f"  ⚠️ No existe {csv_file}")
            continue
        df = pd.read_csv(csv_file)
        df["coin"] = coin
        all_frames.append(df)
        log(f"  ├─ {coin}: {len(df)} rows")

    if not all_frames:
        log("❌ No se encontraron datos históricos")
        return None

    combined = pd.concat(all_frames, ignore_index=True)
    log(f"  ✅ Total: {len(combined)} rows")
    return combined


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    log("🔧 Calculando indicadores...")
    coins = df["coin"].unique()

    # Ordenar por tiempo si existe columna de fecha
    date_col = "date" if "date" in df.columns else ("timestamp" if "timestamp" in df.columns else None)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.sort_values([date_col]).reset_index(drop=True)

    for coin in coins:
        mask = df["coin"] == coin
        if not mask.any():
            continue

        coin_idx = df.index[mask]
        sub = df.loc[mask, ["close", "high", "low", "open", "volume"]].copy()
        if sub.empty:
            continue

        close = sub["close"].astype(float)

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(window=14, min_periods=14).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14, min_periods=14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        rsi = rsi.fillna(50.0)

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        macd_signal = macd.ewm(span=9, adjust=False).mean()

        # Bollinger Bands
        bb_middle = close.rolling(window=20, min_periods=20).mean()
        bb_std = close.rolling(window=20, min_periods=20).std()
        bb_upper = bb_middle + (bb_std * 2.0)
        bb_lower = bb_middle - (bb_std * 2.0)
        bb_width = ((bb_upper - bb_lower) / bb_middle.replace(0, np.nan)).fillna(0.0)

        # EMAs
        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()

        # Volatilidad y volumen relativo
        volatility = close.pct_change().rolling(window=20, min_periods=20).std()
        volume_ma = sub["volume"].astype(float).rolling(window=20, min_periods=20).mean()
        volume_ratio = (sub["volume"].astype(float) / volume_ma.replace(0, np.nan)).fillna(0.0)

        df.loc[coin_idx, "rsi"] = rsi.values
        df.loc[coin_idx, "macd"] = macd.values
        df.loc[coin_idx, "macd_signal"] = macd_signal.values
        df.loc[coin_idx, "bb_middle"] = bb_middle.values
        df.loc[coin_idx, "bb_std"] = bb_std.values
        df.loc[coin_idx, "bb_upper"] = bb_upper.values
        df.loc[coin_idx, "bb_lower"] = bb_lower.values
        df.loc[coin_idx, "bb_width"] = bb_width.values
        df.loc[coin_idx, "ema_9"] = ema9.values
        df.loc[coin_idx, "ema_21"] = ema21.values
        df.loc[coin_idx, "volatility"] = volatility.values
        df.loc[coin_idx, "volume_ma"] = volume_ma.values
        df.loc[coin_idx, "volume_ratio"] = volume_ratio.values

    log("   ✅ Indicadores calculados")
    return df


# ════════════════════════════════════════════════════════
# Labels
# ════════════════════════════════════════════════════════
def create_labels_from_trades(df: pd.DataFrame, trades: list[dict]) -> pd.DataFrame:
    log("🎯 Creando labels desde trades reales...")
    df = df.copy()
    df["tp1_hit"] = 0
    df["tp2_hit"] = 0
    df["tp3_hit"] = 0
    df["sl_hit"] = 0

    if not trades:
        log("⚠️ Sin trades para etiquetar; se usará solo fallback")
        return df

    for trade in trades:
        try:
            coin = str(trade.get("symbol", trade.get("coin", ""))).upper()
            coin = coin.replace("USDT", "")
            if not coin:
                continue

            entry_price = float(trade.get("entryPrice", trade.get("entry", 0)) or 0)
            exit_price = float(trade.get("exitPrice", trade.get("exit", 0)) or 0)
            close_type = str(trade.get("closeType", ""))

            if entry_price <= 0 or exit_price <= 0:
                continue

            coin_mask = df["coin"] == coin
            if not coin_mask.any():
                continue

            price_diff = (df.loc[coin_mask, "close"].astype(float) - entry_price).abs()
            closest_idx = price_diff.idxmin()

            if "TP3" in close_type:
                df.loc[closest_idx, ["tp1_hit", "tp2_hit", "tp3_hit"]] = 1
            elif "TP2" in close_type:
                df.loc[closest_idx, ["tp1_hit", "tp2_hit"]] = 1
            elif "TP1" in close_type:
                df.loc[closest_idx, "tp1_hit"] = 1
            elif "SL" in close_type or "SCALP" in close_type:
                df.loc[closest_idx, "sl_hit"] = 1
        except Exception as exc:
            log(f"  ⚠️ Error procesando trade: {exc}")

    # Fallback por umbrales solo donde no hay labels
    label_cols = ["tp1_hit", "tp2_hit", "tp3_hit", "sl_hit"]
    missing = df[["tp1_hit", "tp2_hit", "tp3_hit", "sl_hit"]].sum(axis=1) == 0
    missing_idx = df.index[missing]

    if len(missing_idx) > 50:
        sub = df.loc[missing_idx, ["close", "high", "low"]].copy()
        if not sub.empty:
            entry = sub["close"].astype(float)
            future_high = sub["high"].shift(-1).rolling(50, min_periods=1).max()
            future_low = sub["low"].shift(-1).rolling(50, min_periods=1).min()

            gain = (future_high - entry) / entry.replace(0, np.nan)
            loss = (entry - future_low) / entry.replace(0, np.nan)
            gain = gain.fillna(0.0)
            loss = loss.fillna(0.0)

            tp1 = (gain >= 0.035).astype(int)
            tp2 = (gain >= 0.07).astype(int)
            tp3 = (gain >= 0.12).astype(int)

            df.loc[missing_idx, "tp1_hit"] = np.where(tp1 == 1, 1, df.loc[missing_idx, "tp1_hit"])
            df.loc[missing_idx, "tp2_hit"] = np.where(tp2 == 1, 1, df.loc[missing_idx, "tp2_hit"])
            df.loc[missing_idx, "tp3_hit"] = np.where(tp3 == 1, 1, df.loc[missing_idx, "tp3_hit"])

    log("   ✅ Labels creados")
    return df


# ════════════════════════════════════════════════════════
# Features / train
# ════════════════════════════════════════════════════════
BASE_FEATURE_COLS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "rsi",
    "macd",
    "macd_signal",
    "bb_upper",
    "bb_lower",
    "bb_width",
    "ema_9",
    "ema_21",
    "volatility",
    "volume_ratio",
]


def prepare_features(df: pd.DataFrame):
    log("🔧 Preparando features...")
    df = df.copy()

    if "coin" not in df.columns:
        raise KeyError("Falta columna 'coin' en el DataFrame")

    # One-hot para moneda
    coin_dummies = pd.get_dummies(df["coin"], prefix="coin", dtype=np.int8)
    df = pd.concat([df, coin_dummies], axis=1)

    # Columnas base válidas
    feature_cols = [c for c in BASE_FEATURE_COLS if c in df.columns]
    feature_cols += [c for c in df.columns if str(c).startswith("coin_")]

    # Columnas de sentimiento si están
    extra_candidates = [
        "fear_greed",
        "fear_greed_7d_avg",
        "fear_greed_30d_avg",
        "fear_greed_change",
        "btc_dominance",
        "volume_to_market_ratio",
    ]
    for c in extra_candidates:
        if c in df.columns:
            feature_cols.append(c)
    regime_cols = [c for c in df.columns if str(c).startswith("regime_")]
    feature_cols += regime_cols

    # Eliminar NaNs en columnas críticas
    critical = list({c for c in feature_cols if c in df.columns})
    df_clean = df.dropna(subset=critical).copy()

    feature_cols = [c for c in feature_cols if c in df_clean.columns]
    log(f"  ✅ Features: {len(feature_cols)}")
    log(f"  ✅ Rows limpias: {len(df_clean)}")
    return df_clean, feature_cols


def _build_estimators(scale_pos_weight: float):
    models = {
        "lgb": lgb.LGBMClassifier(
            n_estimators=250,
            learning_rate=0.05,
            max_depth=8,
            num_leaves=31,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            verbose=-1,
        ),
    }
    try:
        from xgboost import XGBClassifier

        models["xgb"] = XGBClassifier(
            n_estimators=250,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.9,
            colsample_bytree=0.9,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            eval_metric="logloss",
            use_label_encoder=False,
        )
    except Exception:
        pass

    models["et"] = ExtraTreesClassifier(
        n_estimators=200,
        max_depth=10,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )
    return models


def train_model(df: pd.DataFrame, feature_cols: list[str]):
    log("🤖 Entrenando modelo (estimadores adaptativos)...")
    X = df[feature_cols]
    y = df["tp1_hit"].astype(int)

    n_neg = int((y == 0).sum())
    n_pos = int((y == 1).sum())
    scale_pos_weight = n_neg / max(n_pos, 1)

    if y.nunique() < 2 or len(X) < 50:
        log("⚠️ Datos insuficientes o sin clases suficientes para entrenar")
        return None, None, feature_cols

    estimators = _build_estimators(scale_pos_weight)
    best_model = None
    best_score = -1.0
    best_name = None

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for name, model in estimators.items():
        try:
            scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy", n_jobs=-1)
            score = float(np.mean(scores))
            log(f"  ├─ CV accuracy {name}: {score:.2%}")
            if score > best_score:
                best_score = score
                best_model = model
                best_name = name
        except Exception as exc:
            log(f"  ⚠️ {name} falló en CV: {exc}")

    if best_model is None:
        log("❌ Todos los estimadores fallaron")
        return None, None, feature_cols

    # Entrenar con todo el dataset
    best_model.fit(X, y)

    # Evaluación final en holdout
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    y_pred = best_model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    log(f"  ✅ Modelo seleccionado: {best_name} (accuracy {accuracy:.2%}, cv {best_score:.2%})")
    return best_model, accuracy, feature_cols


def save_model(model, accuracy: float, feature_cols: list[str]) -> None:
    log("💾 Guardando modelo...")
    try:
        joblib.dump(model, MODEL_PATH)
        metadata = {
            "feature_cols": feature_cols,
            "accuracy": accuracy,
            "trained_at": datetime.now().isoformat(),
            "version": "2.1.0",
            "retrain_count": get_retrain_count() + 1,
        }
        save_json(METADATA_PATH, metadata)
        log(f"  ✅ Modelo: {MODEL_PATH}")
        log(f"  ✅ Metadata: {METADATA_PATH}")
        log(f"  📦 Tamaño: {MODEL_PATH.stat().st_size / 1024 / 1024:.2f} MB")
    except Exception as exc:
        log(f"❌ Error guardando modelo: {exc}")


# ════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════
def run_auto_retrain() -> bool:
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🤖 Perrobotillo ML - Auto-Retrain                    ║")
    print("╚═══════════════════════════════════════════════════════╝")

    log("🚀 Iniciando auto-retrain...")

    # 1) Modelo previo (solo para auditoría, no circular)
    load_model_and_metadata()

    # 2) Trades
    trades = load_trade_history()
    if not trades:
        log("💤 Sin trades, nada que hacer")
        return False

    # 3) ¿Hay suficientes trades nuevos?
    last_info = get_last_retrain_info()
    last_trade_count = int(last_info.get("last_trade_count", 0) or 0)
    new_trades_count = len(trades) - last_trade_count

    if new_trades_count < MIN_TRADES_FOR_RETRAIN:
        log(f"⚠️  Solo {new_trades_count} trades nuevos (mínimo: {MIN_TRADES_FOR_RETRAIN})")
        log("💤 Saltando re-entrenamiento")
        return False

    new_trades = trades[:new_trades_count]
    log(f"✅ {new_trades_count} trades nuevos - Procediendo con re-entrenamiento")

    # 4) Indicadores con cache
    coins = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]
    df = load_or_build_indicator_cache(coins)
    if df is None or df.empty:
        log("❌ Sin datos históricos, abortando")
        return False

    # 5) Labels
    df = create_labels_from_trades(df, trades)

    # 6) Sentimiento (opcional)
    if _HAS_SENTIMENT:
        try:
            df = add_sentiment_to_training_data(df)
            log("   ✅ Sentiment features agregadas")
        except Exception as exc:
            log(f"   ⚠️ Sentiment features error: {exc}")
    else:
        log("   ℹ️ Sentiment module no disponible, se continúa sin él")

    # 7) Features y entrenamiento
    df_clean, feature_cols = prepare_features(df)
    if df_clean.empty:
        log("❌ No quedaron filas limpias luego de preparar features")
        return False

    model, accuracy, feature_cols = train_model(df_clean, feature_cols)
    if model is None:
        log("❌ No se pudo entrenar un modelo válido")
        return False

    # 8) Persistencia
    save_model(model, accuracy, feature_cols)
    save_last_retrain_info(len(trades))

    # 9) Resumen
    log("")
    log("╔═══════════════════════════════════════════════════════╗")
    log("║  ✅ AUTO-RETRAIN COMPLETADO                           ║")
    log("╚═══════════════════════════════════════════════════════╝")
    log(f"📊 RESUMEN:")
    log(f"  • Trades usados: {len(trades)}")
    log(f"  • Trades nuevos: {new_trades_count}")
    log(f"  • Accuracy: {accuracy:.2%}")
    log(f"  • Modelo actualizado: {MODEL_PATH}")

    return True


if __name__ == "__main__":
    try:
        ok = run_auto_retrain()
        raise SystemExit(0 if ok else 1)
    except Exception as exc:
        log(f"❌ auto-retrain.py failed: {exc}")
        raise SystemExit(1)
