#!/usr/bin/env python3
"""
🐕 Perrobotillo ML - TP Prediction (Inference)
Predice probabilidad de TP en tiempo real usando datos de Binance
"""

import pandas as pd
import numpy as np
import joblib
import json
import os
import sys
import time
from datetime import datetime

from modules.binance_client_fallback import get_historical_klines, DEFAULT_SYMBOLS_BY_USDT

# Configuración
HOME = os.path.expandvars('$HOME')
MODEL_PATH = os.path.join(HOME, '.openclaw/workspace/ml/tp_prediction_model.pkl')
METADATA_PATH = os.path.join(HOME, '.openclaw/workspace/ml/model_metadata.json')
RECOMMENDATIONS_PATH = os.path.join(HOME, '.openclaw/workspace/ml/tp-recommendations.json')
PREDICTIONS_PATH = os.path.join(HOME, '.openclaw/workspace/ml/tp-predictions.json')


def _normalize_dataframe(df: pd.DataFrame, coin: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'
    ]
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['coin'] = coin
    return df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])


def calculate_indicators_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula indicadores técnicos en un solo paso por coin."""
    # RSI
    delta = df.groupby('coin')['close'].diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.groupby(df['coin']).transform(lambda x: x.rolling(14).mean())
    avg_loss = loss.groupby(df['coin']).transform(lambda x: x.rolling(14).mean())
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df['rsi'] = 100.0 - (100.0 / (1.0 + rs))

    close = df['close']
    # EMA y MACD
    ewm12 = close.groupby(df['coin']).transform(lambda x: x.ewm(span=12, adjust=False).mean())
    ewm26 = close.groupby(df['coin']).transform(lambda x: x.ewm(span=26, adjust=False).mean())
    df['macd'] = ewm12 - ewm26
    df['macd_signal'] = df['macd'].groupby(df['coin']).transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df['ema_9'] = close.groupby(df['coin']).transform(lambda x: x.ewm(span=9, adjust=False).mean())
    df['ema_21'] = close.groupby(df['coin']).transform(lambda x: x.ewm(span=21, adjust=False).mean())

    # Bollinger Bands
    bb_middle = close.groupby(df['coin']).transform(lambda x: x.rolling(20).mean())
    bb_std = close.groupby(df['coin']).transform(lambda x: x.rolling(20).std())
    df['bb_middle'] = bb_middle
    df['bb_std'] = bb_std
    df['bb_upper'] = bb_middle + bb_std * 2.0
    df['bb_lower'] = bb_middle - bb_std * 2.0
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / bb_middle.replace(0, np.nan)

    # Volatilidad y volumen relativo
    df['volatility'] = close.groupby(df['coin']).transform(lambda x: x.pct_change().rolling(20).std())
    vol_ma = df['volume'].groupby(df['coin']).transform(lambda x: x.rolling(20).mean())
    df['volume_ma'] = vol_ma
    df['volume_ratio'] = df['volume'] / vol_ma.replace(0, np.nan)

    return df


def load_model_and_metadata():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Modelo no encontrado: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    with open(METADATA_PATH, 'r') as f:
        metadata = json.load(f)
    return model, metadata


def build_feature_frame(df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
    df_with_dummies = pd.get_dummies(df, columns=['coin'], prefix='coin')
    for col in metadata['feature_cols']:
        if col not in df_with_dummies.columns:
            df_with_dummies[col] = 0.0
    return df_with_dummies[metadata['feature_cols']]


def predict_for_all(df: pd.DataFrame, feature_frame: pd.DataFrame, model) -> dict:
    predictions = {}
    for coin in df['coin'].unique():
        coin_mask = df['coin'] == coin
        coin_data = feature_frame[coin_mask].dropna()
        if coin_data.empty:
            continue
        latest = coin_data.iloc[-1:]
        proba = model.predict_proba(latest)[0]
        prob_tp1 = float(proba[1])
        predictions[coin] = {
            'prob_tp1': prob_tp1,
            'prediction': 'TP1_LIKELY' if prob_tp1 > 0.6 else 'TP1_UNLIKELY',
            'confidence': 'HIGH' if prob_tp1 > 0.7 or prob_tp1 < 0.3 else 'MEDIUM',
            'timestamp': datetime.now().isoformat(),
        }
    return predictions


def recommend(prob_tp1: float) -> dict:
    if prob_tp1 > 0.75:
        return {
            'action': 'AGGRESSIVE',
            'tp1_pct': 4.0,
            'tp2_pct': 8.0,
            'tp3_pct': 15.0,
            'reason': 'Alta probabilidad de TP - ser agresivo',
        }
    if prob_tp1 > 0.60:
        return {
            'action': 'NORMAL',
            'tp1_pct': 3.5,
            'tp2_pct': 7.0,
            'tp3_pct': 12.0,
            'reason': 'Probabilidad normal - mantener estrategia estándar',
        }
    if prob_tp1 > 0.40:
        return {
            'action': 'CONSERVATIVE',
            'tp1_pct': 2.5,
            'tp2_pct': 5.0,
            'tp3_pct': 8.0,
            'reason': 'Probabilidad baja - ser conservador',
        }
    return {
        'action': 'DEFENSIVE',
        'tp1_pct': 2.0,
        'tp2_pct': 4.0,
        'tp3_pct': 6.0,
        'sl_pct': 8.0,
        'reason': 'Muy baja probabilidad - reducir exposición',
    }


def save_json(path: str, payload) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, 'w') as f:
        json.dump(payload, f, indent=2, default=str)
    os.replace(tmp, path)


def parse_args():
    return ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']


def main():
    coins = parse_args()
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🤖 Perrobotillo ML - TP Prediction                   ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    start = time.time()
    try:
        model, metadata = load_model_and_metadata()
    except Exception as e:
        print(f"❌ No se pudo cargar el modelo: {e}")
        sys.exit(1)

    raw_frames = []
    t0 = time.time()
    for coin in coins:
        try:
            klines = get_historical_klines(
                symbol=f"{coin}USDT",
                interval='1h',
                limit=100,
            )
        except Exception as e:
            print(f"❌ Error obteniendo datos para {coin}: {e}")
            raise SystemExit(1)
        df_coin = _normalize_dataframe(pd.DataFrame(klines), coin)
        if df_coin.empty:
            print(f"❌ Datos vacíos para {coin}")
            raise SystemExit(1)
        raw_frames.append(df_coin)
    print(f"   ✅ {sum(len(x) for x in raw_frames)} velas obtenidas")

    df = pd.concat(raw_frames, ignore_index=True)
    df = calculate_indicators_vectorized(df)

    feature_frame = build_feature_frame(df, metadata)
    predictions = predict_for_all(df, feature_frame, model)
    if not predictions:
        print("❌ Sin predicciones")
        raise SystemExit(1)

    print("\n╔═══════════════════════════════════════════════════════╗")
    print("║  📊 PREDICCIONES POR COIN                             ║")
    print("╚═══════════════════════════════════════════════════════╝")

    for coin, pred in sorted(predictions.items()):
        rec = recommend(pred['prob_tp1'])
        print(f"\n{coin}:")
        print(f"  Prob TP1: {pred['prob_tp1']:.1%}")
        print(f"  Confianza: {pred['confidence']}")
        print(f"  Predicción: {pred['prediction']}")
        print(f"  → Acción: {rec['action']}")
        print(f"     TP1: {rec['tp1_pct']}% | TP2: {rec['tp2_pct']}% | TP3: {rec['tp3_pct']}%")
        print(f"     Razón: {rec['reason']}")

    save_json(PREDICTIONS_PATH, predictions)
    output = {
        'timestamp': datetime.now().isoformat(),
        'predictions': predictions,
        'recommendations': {coin: recommend(data['prob_tp1']) for coin, data in predictions.items()},
    }
    save_json(RECOMMENDATIONS_PATH, output)
    print(f"✅ Predicciones: {PREDICTIONS_PATH}")
    print(f"✅ Recomendaciones: {RECOMMENDATIONS_PATH}")
    print(f"⏱️ Tiempo={time.time() - start:.2f}s")


if __name__ == "__main__":
    main()
