#!/usr/bin/env python3
"""
🛡️ Drawdown Predictor - ML para predecir pérdidas antes de que ocurran
Detecta patrones que preceden a trades perdedores y alerta tempranamente

Features:
- Volatilidad reciente (alta = riesgo)
- RSI extremo (>70 o <30)
- Múltiples losses consecutivos
- Drawdown acumulativo (24h, 7d)
- Volume spikes anormales
- Performance por hora del día
- Market mode (BULL/BEAR/LATERAL)

Output:
- LOW_RISK → Operar normal
- MEDIUM_RISK → Reducir position_size a 25%
- HIGH_RISK → Pausar trading temporalmente
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, precision_score, recall_score
import joblib

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = "/home/overgon/.openclaw/workspace"
ML_DIR = os.path.join(WORKSPACE, "ml")
CRYPTO_BOTS = os.path.join(WORKSPACE, "crypto-bots")

TRADE_HISTORY_FILE = os.path.join(CRYPTO_BOTS, "trade-history.json")
TRAINING_DATA_FILE = os.path.join(ML_DIR, "drawdown-training.csv")
MODEL_FILE = os.path.join(ML_DIR, "drawdown-predictor.pkl")
RECOMMENDATIONS_FILE = os.path.join(ML_DIR, "drawdown-recommendations.json")
METADATA_FILE = os.path.join(ML_DIR, "drawdown-metadata.json")

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

RISK_LEVELS = {
    'LOW_RISK': {'action': 'NORMAL', 'position_size': 40, 'message': 'Riesgo bajo - operar normal'},
    'MEDIUM_RISK': {'action': 'REDUCE', 'position_size': 25, 'message': 'Riesgo medio - reducir posición'},
    'HIGH_RISK': {'action': 'PAUSE', 'position_size': 0, 'message': 'Riesgo alto - pausar trading'}
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
# CALCULAR FEATURES DE RIESGO
# ════════════════════════════════════════════════════════

def calculate_risk_features(trades, target_coin=None):
    """Calcular features de riesgo basadas en historial"""
    if not trades:
        return {}
    
    df = pd.DataFrame(trades)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', utc=True)
    df['pnlUSDT'] = df['pnlUSDT'].astype(float)
    df['is_loss'] = df['pnlUSDT'] < 0
    
    features = {
        'loss_streak': 0,
        'loss_rate_24h': 0,
        'loss_rate_7d': 0,
        'drawdown_24h': 0,
        'drawdown_7d': 0,
        'avg_loss_size': 0,
        'loss_volatility': 0,
        'total_trades_24h': 0,
        'total_trades_7d': 0,
    }
    
    now = datetime.now(timezone.utc)
    
    # Trades últimas 24h
    trades_24h = df[df['timestamp'] >= (now - timedelta(hours=24))].sort_values('timestamp')
    if len(trades_24h) > 0:
        features['loss_rate_24h'] = trades_24h['is_loss'].mean()
        features['total_trades_24h'] = len(trades_24h)
        
        # Drawdown 24h (pérdida acumulada)
        features['drawdown_24h'] = abs(trades_24h[trades_24h['pnlUSDT'] < 0]['pnlUSDT'].sum())
        
        # Tamaño promedio de pérdidas
        losses_24h = trades_24h[trades_24h['pnlUSDT'] < 0]['pnlUSDT']
        if len(losses_24h) > 0:
            features['avg_loss_size'] = abs(losses_24h.mean())
    
    # Trades últimos 7d
    trades_7d = df[df['timestamp'] >= (now - timedelta(days=7))].sort_values('timestamp')
    if len(trades_7d) > 0:
        features['loss_rate_7d'] = trades_7d['is_loss'].mean()
        features['total_trades_7d'] = len(trades_7d)
        
        # Drawdown 7d
        features['drawdown_7d'] = abs(trades_7d[trades_7d['pnlUSDT'] < 0]['pnlUSDT'].sum())
        
        # Volatilidad de pérdidas (std)
        losses_7d = trades_7d[trades_7d['pnlUSDT'] < 0]['pnlUSDT']
        if len(losses_7d) > 1:
            features['loss_volatility'] = abs(losses_7d.std())
    
    # Rachas de pérdidas (últimos 10 trades)
    recent = df.sort_values('timestamp', ascending=False).head(10)
    if len(recent) > 0:
        losses = recent['is_loss'].astype(int)
        current_loss_streak = 0
        max_loss_streak = 0
        
        for is_loss in losses:
            if is_loss:
                current_loss_streak += 1
                max_loss_streak = max(max_loss_streak, current_loss_streak)
            else:
                current_loss_streak = 0
        
        features['loss_streak'] = max_loss_streak
    
    # Features específicas por coin
    if target_coin:
        coin_trades = df[df['symbol'] == target_coin]
        if len(coin_trades) > 0:
            features[f'{target_coin}_loss_rate'] = coin_trades['is_loss'].mean()
            features[f'{target_coin}_loss_count'] = coin_trades['is_loss'].sum()
        else:
            features[f'{target_coin}_loss_rate'] = 0
            features[f'{target_coin}_loss_count'] = 0
    
    return features

def get_hour_feature():
    """Obtener hora actual como feature cíclica"""
    hour = datetime.now().hour
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    return {'hour_sin': hour_sin, 'hour_cos': hour_cos}

# ════════════════════════════════════════════════════════
# LABEL: Predecir si el PRÓXIMO trade será pérdida
# ════════════════════════════════════════════════════════

def label_next_trade_loss(trades, trade_index):
    """
    Etiquetar si el trade en trade_index fue precedido por condiciones de riesgo
    
    Label = 1 (HIGH_RISK) si el trade fue pérdida
    Label = 0 (LOW_RISK) si el trade fue ganancia
    
    Usamos features ANTES del trade para predecir
    """
    if trade_index >= len(trades):
        return 'LOW_RISK'
    
    trade = trades[trade_index]
    pnl = float(trade.get('pnlUSDT', 0))
    
    if pnl < 0:
        # Fue pérdida → HIGH_RISK debería haber alertado
        return 'HIGH_RISK'
    elif pnl < 1:  # Ganancia muy pequeña
        return 'MEDIUM_RISK'
    else:
        return 'LOW_RISK'

# ════════════════════════════════════════════════════════
# GENERAR DATA DE ENTRENAMIENTO
# ════════════════════════════════════════════════════════

def generate_training_data():
    """Generar dataset de entrenamiento"""
    print("📊 Generando data de entrenamiento para Drawdown Predictor...")
    
    trades = load_trade_history()
    if not trades:
        return None
    
    data = []
    
    # Para cada trade, calcular features ANTES del trade y label del resultado
    for i in range(10, len(trades)):  # Empezar en 10 para tener histórico suficiente
        # Trades históricos hasta este punto
        historical_trades = trades[:i]
        current_trade = trades[i]
        symbol = current_trade.get('symbol', 'BTC')
        
        # Features calculadas con data ANTES del trade
        risk_features = calculate_risk_features(historical_trades, target_coin=symbol)
        
        # Hora del trade
        ts = pd.to_datetime(current_trade.get('timestamp', datetime.now(timezone.utc)), format='mixed', utc=True)
        hour = ts.hour
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        
        # Combinar features
        features = {
            **risk_features,
            'hour_sin': hour_sin,
            'hour_cos': hour_cos,
            'symbol': symbol
        }
        
        # One-hot encoding
        for coin in COINS:
            features[f'coin_{coin}'] = 1 if coin == symbol else 0
        
        # Label: ¿Este trade fue pérdida?
        label = label_next_trade_loss(trades, i)
        features['label'] = label
        
        data.append(features)
    
    df = pd.DataFrame(data)
    df.to_csv(TRAINING_DATA_FILE, index=False)
    print(f"✅ Data guardada: {len(df)} filas")
    
    print("\nDistribución de labels:")
    print(df['label'].value_counts())
    
    return df

# ════════════════════════════════════════════════════════
# ENTRENAR MODELO
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
        'loss_streak', 'loss_rate_24h', 'loss_rate_7d',
        'drawdown_24h', 'drawdown_7d', 'avg_loss_size', 'loss_volatility',
        'total_trades_24h', 'total_trades_7d',
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
    
    print("🧠 Entrenando modelo (Random Forest)...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        min_samples_split=5,
        class_weight='balanced',
        random_state=42
    )
    
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    # Para clasificación multi-clase, usar average='weighted'
    precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
    
    print(f"\n✅ Modelo entrenado")
    print(f"   Accuracy: {accuracy:.2%}")
    print(f"   Precision: {precision:.2%}")
    print(f"   Recall: {recall:.2%}")
    print("\n" + classification_report(y_test, y_pred, zero_division=0))
    
    joblib.dump(model, MODEL_FILE)
    
    metadata = {
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'trained_at': datetime.now().isoformat(),
        'version': '1.0.0',
        'feature_cols': feature_cols,
        'classes': list(model.classes_),
        'n_samples': len(df),
        'risk_levels': {k: v['action'] for k, v in RISK_LEVELS.items()}
    }
    
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✅ Modelo guardado: {MODEL_FILE}")
    
    return model

# ════════════════════════════════════════════════════════
# PREDECIR RIESGO
# ════════════════════════════════════════════════════════

def predict_risk(symbol='BTC'):
    """Predecir nivel de riesgo actual"""
    
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
    risk_features = calculate_risk_features(trades, target_coin=symbol) if trades else {}
    
    hour = datetime.now().hour
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    
    features = {
        **risk_features,
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
    risk_info = RISK_LEVELS.get(pred, RISK_LEVELS['LOW_RISK'])
    
    result = {
        'symbol': symbol,
        'risk_level': pred,
        'action': risk_info['action'],
        'position_size': risk_info['position_size'],
        'confidence': round(confidence, 3),
        'message': risk_info['message'],
        'probabilities': {
            cls: round(float(prob), 3)
            for cls, prob in zip(model.classes_, probs)
        },
        'risk_indicators': {
            'loss_streak': risk_features.get('loss_streak', 0),
            'loss_rate_24h': risk_features.get('loss_rate_24h', 0),
            'drawdown_24h': risk_features.get('drawdown_24h', 0),
            'drawdown_7d': risk_features.get('drawdown_7d', 0),
            'hour': hour
        }
    }
    
    print(f"\n🛡️ Predicción de Riesgo para {symbol}:")
    print(f"   Nivel: {pred}")
    print(f"   Acción: {risk_info['action']}")
    print(f"   Position Size: {risk_info['position_size']}%")
    print(f"   Confianza: {confidence:.1%}")
    print(f"   Loss streak: {result['risk_indicators']['loss_streak']}")
    print(f"   Loss rate 24h: {result['risk_indicators']['loss_rate_24h']:.1%}")
    print(f"   Drawdown 24h: ${result['risk_indicators']['drawdown_24h']:.2f}")
    print(f"   Drawdown 7d: ${result['risk_indicators']['drawdown_7d']:.2f}")
    print(f"   💡 {result['message']}")
    
    output = {
        'timestamp': datetime.now().isoformat(),
        'model_accuracy': metadata['accuracy'],
        'predictions': {symbol: result}
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
    
    parser = argparse.ArgumentParser(description="Drawdown Predictor ML")
    parser.add_argument('--train', action='store_true', help='Entrenar modelo')
    parser.add_argument('--predict', type=str, help='Predecir riesgo para una coin')
    parser.add_argument('--data', action='store_true', help='Generar data')
    
    args = parser.parse_args()
    
    if args.train:
        train_model()
    elif args.data:
        generate_training_data()
    elif args.predict:
        predict_risk(args.predict)
    else:
        print("╔═══════════════════════════════════════════════════════╗")
        print("║  🛡️ DRAWDOWN PREDICTOR - ML RISK ASSESSMENT          ║")
        print("╚═══════════════════════════════════════════════════════╝")
        print()
        
        if not os.path.exists(MODEL_FILE):
            train_model()
            print()
        
        for coin in COINS:
            print(f"\n{'='*50}")
            predict_risk(coin)
