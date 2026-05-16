#!/usr/bin/env python3
"""
🧠 Position Size Optimizer - ML para optimizar tamaño de posición
Versión simplificada - usa solo trade history sin APIs externas
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import os
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = "/home/overgon/.openclaw/workspace"
ML_DIR = os.path.join(WORKSPACE, "ml")
CRYPTO_BOTS = os.path.join(WORKSPACE, "crypto-bots")

TRADE_HISTORY_FILE = os.path.join(CRYPTO_BOTS, "trade-history.json")
TRAINING_DATA_FILE = os.path.join(ML_DIR, "position-size-training.csv")
MODEL_FILE = os.path.join(ML_DIR, "position-size-optimizer.pkl")
RECOMMENDATIONS_FILE = os.path.join(ML_DIR, "position-size-recommendations.json")
METADATA_FILE = os.path.join(ML_DIR, "position-size-metadata.json")

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

POSITION_SIZES = {
    'HIGH': 50,
    'MEDIUM': 40,
    'LOW': 25
}

# ════════════════════════════════════════════════════════
# CARGAR HISTORIAL
# ════════════════════════════════════════════════════════

def load_trade_history():
    """Cargar historial de trades"""
    if not os.path.exists(TRADE_HISTORY_FILE):
        print(f"❌ No hay historial en {TRADE_HISTORY_FILE}")
        return None
    
    with open(TRADE_HISTORY_FILE, 'r') as f:
        data = json.load(f)
    
    trades = data.get('trades', [])
    print(f"✅ Cargados {len(trades)} trades del historial")
    
    return trades

# ════════════════════════════════════════════════════════
# CALCULAR FEATURES (sin APIs externas)
# ════════════════════════════════════════════════════════

def calculate_trade_features(trades, target_coin=None):
    """Calcular features basadas en historial de trades"""
    if not trades:
        return {}
    
    df = pd.DataFrame(trades)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', utc=True)
    df['pnlUSDT'] = df['pnlUSDT'].astype(float)
    
    features = {
        'win_rate_24h': 0,
        'win_rate_7d': 0,
        'total_trades_24h': 0,
        'total_trades_7d': 0,
        'avg_pnl_24h': 0,
        'avg_pnl_7d': 0,
        'consecutive_wins': 0,
        'consecutive_losses': 0,
        'max_drawdown': 0,
        'profit_factor': 0,
    }
    
    now = datetime.now(timezone.utc)
    
    # Trades últimas 24h
    trades_24h = df[df['timestamp'] >= (now - timedelta(hours=24))]
    if len(trades_24h) > 0:
        features['win_rate_24h'] = (trades_24h['pnlUSDT'] > 0).mean()
        features['total_trades_24h'] = len(trades_24h)
        features['avg_pnl_24h'] = trades_24h['pnlUSDT'].mean()
    
    # Trades últimos 7d
    trades_7d = df[df['timestamp'] >= (now - timedelta(days=7))]
    if len(trades_7d) > 0:
        features['win_rate_7d'] = (trades_7d['pnlUSDT'] > 0).mean()
        features['total_trades_7d'] = len(trades_7d)
        features['avg_pnl_7d'] = trades_7d['pnlUSDT'].mean()
    
    # Rachas (últimos 10 trades)
    recent = df.sort_values('timestamp', ascending=False).head(10)
    if len(recent) > 0:
        wins = (recent['pnlUSDT'] > 0).astype(int)
        
        current_streak = 0
        for win in wins:
            if win:
                current_streak += 1
                features['consecutive_wins'] = max(features['consecutive_wins'], current_streak)
            else:
                current_streak = 0
        
        current_streak = 0
        for win in wins:
            if not win:
                current_streak += 1
                features['consecutive_losses'] = max(features['consecutive_losses'], current_streak)
            else:
                current_streak = 0
    
    # Drawdown máximo
    recent_20 = df.sort_values('timestamp', ascending=False).head(20)
    if len(recent_20) > 0:
        cumulative = recent_20['pnlUSDT'].cumsum()
        peak = cumulative.cummax()
        drawdown = (peak - cumulative) / peak.abs().replace(0, 1)
        features['max_drawdown'] = drawdown.max() if not pd.isna(drawdown.max()) else 0
    
    # Profit factor
    gross_profit = trades_7d[trades_7d['pnlUSDT'] > 0]['pnlUSDT'].sum()
    gross_loss = abs(trades_7d[trades_7d['pnlUSDT'] < 0]['pnlUSDT'].sum())
    if gross_loss > 0:
        features['profit_factor'] = gross_profit / gross_loss
    else:
        features['profit_factor'] = gross_profit if gross_profit > 0 else 1
    
    # Features por coin
    if target_coin:
        coin_trades = df[df['symbol'] == target_coin]
        if len(coin_trades) > 0:
            features[f'{target_coin}_win_rate'] = (coin_trades['pnlUSDT'] > 0).mean()
            features[f'{target_coin}_avg_pnl'] = coin_trades['pnlUSDT'].mean()
            features[f'{target_coin}_trades'] = len(coin_trades)
        else:
            features[f'{target_coin}_win_rate'] = 0.5
            features[f'{target_coin}_avg_pnl'] = 0
            features[f'{target_coin}_trades'] = 0
    
    return features

def get_hour_feature():
    """Obtener hora actual como feature cíclica"""
    hour = datetime.now().hour
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    return {'hour_sin': hour_sin, 'hour_cos': hour_cos}

# ════════════════════════════════════════════════════════
# LABEL
# ════════════════════════════════════════════════════════

def label_position_size(trade):
    """
    Etiquetar qué position_size debería haberse usado
    """
    pnl = float(trade.get('pnlUSDT', 0))
    close_type = trade.get('closeType', '')
    timestamp = pd.to_datetime(trade.get('timestamp', datetime.now(timezone.utc)), format='mixed', utc=True)
    hour = timestamp.hour
    
    optimal_hours = [0, 1, 13, 14, 15, 16, 21, 22]
    
    if pnl > 0:
        if hour in optimal_hours:
            return 'HIGH'
        else:
            return 'MEDIUM'
    else:
        return 'LOW'

# ════════════════════════════════════════════════════════
# GENERAR DATA
# ════════════════════════════════════════════════════════

def generate_training_data():
    """Generar dataset de entrenamiento"""
    print("📊 Generando data de entrenamiento...")
    
    trades = load_trade_history()
    if not trades:
        return None
    
    data = []
    
    for i, trade in enumerate(trades):
        symbol = trade.get('symbol', 'BTC')
        
        # Features de trades
        trade_features = calculate_trade_features(trades, target_coin=symbol)
        
        # Hora del trade
        ts = pd.to_datetime(trade.get('timestamp', datetime.now(timezone.utc)), format='mixed', utc=True)
        hour = ts.hour
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        
        # Combinar features
        features = {
            **trade_features,
            'hour_sin': hour_sin,
            'hour_cos': hour_cos,
            'symbol': symbol
        }
        
        # Label
        label = label_position_size(trade)
        
        # One-hot encoding
        for coin in COINS:
            features[f'coin_{coin}'] = 1 if coin == symbol else 0
        
        features['label'] = label
        data.append(features)
    
    df = pd.DataFrame(data)
    df.to_csv(TRAINING_DATA_FILE, index=False)
    print(f"✅ Data guardada: {len(df)} filas")
    
    print("\nDistribución de labels:")
    print(df['label'].value_counts())
    
    return df

# ════════════════════════════════════════════════════════
# ENTRENAR
# ════════════════════════════════════════════════════════

def train_model(df=None):
    """Entrenar modelo"""
    
    if df is None:
        if not os.path.exists(TRAINING_DATA_FILE):
            print("❌ No hay data. Generando...")
            df = generate_training_data()
        else:
            df = pd.read_csv(TRAINING_DATA_FILE)
    
    if df is None or len(df) < 30:
        print("❌ Data insuficiente (< 30 samples)")
        return None
    
    feature_cols = [
        'win_rate_24h', 'win_rate_7d', 'total_trades_24h', 'total_trades_7d',
        'avg_pnl_24h', 'avg_pnl_7d', 'consecutive_wins', 'consecutive_losses',
        'max_drawdown', 'profit_factor',
        'hour_sin', 'hour_cos',
        'coin_BTC', 'coin_ETH', 'coin_BNB', 'coin_SOL',
        'coin_LINK', 'coin_XRP', 'coin_AVAX'
    ]
    
    feature_cols = [col for col in feature_cols if col in df.columns]
    
    X = df[feature_cols]
    y = df['label']
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print("🧠 Entrenando modelo (Gradient Boosting)...")
    model = GradientBoostingClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.1,
        random_state=42
    )
    
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n✅ Modelo entrenado - Accuracy: {accuracy:.2%}")
    print("\n" + classification_report(y_test, y_pred))
    
    joblib.dump(model, MODEL_FILE)
    
    metadata = {
        'accuracy': float(accuracy),
        'trained_at': datetime.now().isoformat(),
        'version': '1.0.0',
        'feature_cols': feature_cols,
        'classes': list(model.classes_),
        'n_samples': len(df),
        'position_sizes': POSITION_SIZES
    }
    
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✅ Modelo guardado: {MODEL_FILE}")
    
    return model

# ════════════════════════════════════════════════════════
# PREDECIR
# ════════════════════════════════════════════════════════

def predict_position_size(symbol='BTC'):
    """Predecir position size recomendado"""
    
    if not os.path.exists(MODEL_FILE):
        print("❌ No hay modelo. Entrenando...")
        model = train_model()
        if model is None:
            return None
    else:
        model = joblib.load(MODEL_FILE)
    
    with open(METADATA_FILE, 'r') as f:
        metadata = json.load(f)
    
    feature_cols = metadata['feature_cols']
    
    # Features actuales
    trades = load_trade_history()
    trade_features = calculate_trade_features(trades, target_coin=symbol) if trades else {}
    
    hour = datetime.now().hour
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    
    features = {
        **trade_features,
        'hour_sin': hour_sin,
        'hour_cos': hour_cos
    }
    
    for coin in COINS:
        features[f'coin_{coin}'] = 1 if coin == symbol else 0
    
    df_features = pd.DataFrame([features])
    
    for col in feature_cols:
        if col not in df_features.columns:
            df_features[col] = 0
    
    X = df_features[feature_cols]
    pred = model.predict(X)[0]
    probs = model.predict_proba(X)[0]
    
    confidence = float(max(probs))
    position_size = POSITION_SIZES.get(pred, 40)
    
    result = {
        'symbol': symbol,
        'recommendation': pred,
        'position_size': position_size,
        'confidence': round(confidence, 3),
        'probabilities': {
            cls: round(float(prob), 3)
            for cls, prob in zip(model.classes_, probs)
        },
        'features_used': {
            'win_rate_24h': trade_features.get('win_rate_24h', 0),
            'win_rate_7d': trade_features.get('win_rate_7d', 0),
            'hour': hour
        }
    }
    
    print(f"\n🎯 Predicción para {symbol}:")
    print(f"   Recomendación: {pred} ({position_size}%)")
    print(f"   Confianza: {confidence:.1%}")
    print(f"   Win rate 24h: {result['features_used']['win_rate_24h']:.1%}")
    print(f"   Win rate 7d: {result['features_used']['win_rate_7d']:.1%}")
    
    output = {
        'timestamp': datetime.now().isoformat(),
        'model_accuracy': metadata['accuracy'],
        'recommendations': {symbol: result}
    }
    
    with open(RECOMMENDATIONS_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Recomendaciones guardadas: {RECOMMENDATIONS_FILE}")
    
    return result

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Position Size Optimizer ML")
    parser.add_argument('--train', action='store_true', help='Entrenar modelo')
    parser.add_argument('--predict', type=str, help='Predecir para una coin')
    parser.add_argument('--data', action='store_true', help='Generar data')
    
    args = parser.parse_args()
    
    if args.train:
        train_model()
    elif args.data:
        generate_training_data()
    elif args.predict:
        predict_position_size(args.predict)
    else:
        print("╔═══════════════════════════════════════════════════════╗")
        print("║  🧠 POSITION SIZE OPTIMIZER - ML                      ║")
        print("╚═══════════════════════════════════════════════════════╝")
        print()
        
        if not os.path.exists(MODEL_FILE):
            train_model()
            print()
        
        for coin in COINS:
            print(f"\n{'='*50}")
            predict_position_size(coin)
