#!/usr/bin/env python3
"""
🧠 Market Classifier - ML Validation for Auto-Adjust Strategy
Entrena un modelo para clasificar: BULL / BEAR / LATERAL

Features:
- RSI, MACD, Bollinger Bands, EMAs
- Volume ratios, volatility
- Price action (higher highs/lows)
- Fear & Greed Index

Output: market-predictions.json con clasificación y confianza
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib
import os
import sys

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = "/home/overgon/.openclaw/workspace"
ML_DIR = os.path.join(WORKSPACE, "ml")
DATA_FILE = os.path.join(ML_DIR, "market-training-data.csv")
MODEL_FILE = os.path.join(ML_DIR, "market-classifier.pkl")
PREDICTIONS_FILE = os.path.join(ML_DIR, "market-predictions.json")
METADATA_FILE = os.path.join(ML_DIR, "market-model-metadata.json")

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]
BINANCE = "https://api.binance.com/api/v3"

# ════════════════════════════════════════════════════════
# OBTENER DATOS DE MERCADO
# ════════════════════════════════════════════════════════

def get_klines(symbol, interval="1h", limit=100):
    """Obtener velas de Binance"""
    try:
        url = f"{BINANCE}/klines"
        params = {
            "symbol": f"{symbol}USDT",
            "interval": interval,
            "limit": limit
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        return df
    except Exception as e:
        print(f"❌ Error obteniendo klines {symbol}: {e}")
        return None

def get_fear_greed():
    """Obtener Fear & Greed Index"""
    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=5)
        data = response.json()
        return int(data['data'][0]['value'])
    except:
        return 50  # Neutral por default

# ════════════════════════════════════════════════════════
# CALCULAR INDICADORES TÉCNICOS
# ════════════════════════════════════════════════════════

def calculate_rsi(prices, period=14):
    """Calcular RSI"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calcular MACD"""
    exp1 = prices.ewm(span=fast, adjust=False).mean()
    exp2 = prices.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calcular Bollinger Bands"""
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower

def calculate_ema(prices, period):
    """Calcular EMA"""
    return prices.ewm(span=period, adjust=False).mean()

def extract_features(df, symbol):
    """Extraer features del DataFrame"""
    if df is None or len(df) < 50:
        return None
    
    prices = df['close']
    
    # RSI
    df['rsi'] = calculate_rsi(prices)
    
    # MACD
    df['macd'], df['macd_signal'] = calculate_macd(prices)
    
    # Bollinger Bands
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = calculate_bollinger_bands(prices)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    
    # EMAs
    df['ema_9'] = calculate_ema(prices, 9)
    df['ema_21'] = calculate_ema(prices, 21)
    
    # Volatilidad
    df['volatility'] = prices.pct_change().rolling(window=20).std()
    
    # Volume ratio
    df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=20).mean()
    
    # Price action (higher highs / lower lows)
    df['price_trend'] = prices.pct_change(periods=10)
    
    # EMA crossover
    df['ema_cross'] = (df['ema_9'] - df['ema_21']) / df['ema_21']
    
    # Posición en BB
    df['bb_position'] = (prices - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # Fear & Greed (mismo para todas las coins)
    df['fear_greed'] = get_fear_greed()
    
    # Coin one-hot encoding
    for coin in COINS:
        df[f'coin_{coin}'] = 1 if coin == symbol else 0
    
    # Drop NaN rows
    df = df.dropna()
    
    return df

# ════════════════════════════════════════════════════════
# GENERAR DATA DE ENTRENAMIENTO
# ════════════════════════════════════════════════════════

def label_market_mode(df):
    """
    Etiquetar cada fila como BULL/BEAR/LATERAL/LATERAL_BULL basado en price action
    
    Reglas:
    - BULL: price_trend > 2% y RSI > 55 y ema_9 > ema_21
    - BEAR: price_trend < -2% y RSI < 45 y ema_9 < ema_21
    - LATERAL_BULL: RSI 40-70 y precio en mitad superior de BB
    - LATERAL: todo lo demás
    """
    labels = []
    
    for idx, row in df.iterrows():
        trend = row.get('price_trend', 0)
        rsi = row.get('rsi', 50)
        ema_cross = row.get('ema_cross', 0)
        bb_position = row.get('bb_position', 0.5)
        
        if trend > 0.02 and rsi > 55 and ema_cross > 0:
            labels.append('BULL')
        elif trend < -0.02 and rsi < 45 and ema_cross < 0:
            labels.append('BEAR')
        elif 40 <= rsi <= 70 and bb_position >= 0.3:
            labels.append('LATERAL_BULL')
        else:
            labels.append('LATERAL')
    
    return labels

def generate_training_data():
    """Generar dataset de entrenamiento"""
    print("📊 Generando data de entrenamiento...")
    
    all_data = []
    
    for coin in COINS:
        print(f"   Procesando {coin}...")
        df = get_klines(coin, interval="1h", limit=500)
        
        if df is None:
            continue
        
        df = extract_features(df, coin)
        
        if df is None or len(df) < 50:
            continue
        
        # Etiquetar
        df['market_mode'] = label_market_mode(df)
        
        all_data.append(df)
    
    if not all_data:
        print("❌ No se pudo generar data")
        return None
    
    # Combinar todos los datos
    combined = pd.concat(all_data, ignore_index=True)
    
    # Etiquetar antes de guardar/cachear para persistir LATERAL_BULL
    combined['market_mode'] = label_market_mode(combined)
    
    # Guardar
    combined.to_csv(DATA_FILE, index=False)
    print(f"✅ Data guardada: {len(combined)} filas")
    print('Label counts:', combined['market_mode'].value_counts().to_dict())
    
    return combined

# ════════════════════════════════════════════════════════
# ENTRENAR MODELO
# ════════════════════════════════════════════════════════

def train_model(df=None):
    """Entrenar modelo de clasificación"""
    
    if df is None:
        if not os.path.exists(DATA_FILE):
            print("❌ No hay data de entrenamiento. Generando...")
            df = generate_training_data()
        else:
            df = pd.read_csv(DATA_FILE)
    
    if df is None or len(df) < 100:
        print("❌ Data insuficiente para entrenar")
        return None
    
    # Features
    feature_cols = [
        'rsi', 'macd', 'macd_signal', 'bb_width', 'bb_position',
        'ema_9', 'ema_21', 'volatility', 'volume_ratio', 'price_trend',
        'ema_cross', 'fear_greed',
        'coin_BTC', 'coin_ETH', 'coin_BNB', 'coin_SOL', 
        'coin_LINK', 'coin_XRP', 'coin_AVAX'
    ]
    
    # Filtrar columnas que existen
    feature_cols = [col for col in feature_cols if col in df.columns]
    
    X = df[feature_cols]
    y = df['market_mode']
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Random Forest Classifier
    print("🧠 Entrenando modelo...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        class_weight='balanced',
        random_state=42
    )
    
    model.fit(X_train, y_train)
    
    # Evaluación
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"✅ Modelo entrenado - Accuracy: {accuracy:.2%}")
    print("\n" + classification_report(y_test, y_pred))
    
    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 5 features:")
    print(importance.head())
    
    # Guardar modelo
    joblib.dump(model, MODEL_FILE)
    
    # Guardar metadata
    metadata = {
        'accuracy': float(accuracy),
        'trained_at': datetime.now().isoformat(),
        'version': '1.0.0',
        'feature_cols': feature_cols,
        'classes': list(model.classes_),
        'n_samples': len(df)
    }
    
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✅ Modelo guardado: {MODEL_FILE}")
    
    return model

# ════════════════════════════════════════════════════════
# PREDECIR MODO DE MERCADO
# ════════════════════════════════════════════════════════

def predict_market_mode():
    """Predecir modo de mercado para todas las coins"""
    
    # Cargar modelo
    if not os.path.exists(MODEL_FILE):
        print("❌ No hay modelo entrenado. Entrenando...")
        model = train_model()
        if model is None:
            return None
    else:
        model = joblib.load(MODEL_FILE)
    
    # Cargar metadata
    with open(METADATA_FILE, 'r') as f:
        metadata = json.load(f)
    
    feature_cols = metadata['feature_cols']
    
    # Predecir para cada coin
    predictions = {}
    
    for coin in COINS:
        print(f"   Prediciendo {coin}...")
        df = get_klines(coin, interval="1h", limit=50)
        
        if df is None:
            continue
        
        df = extract_features(df, coin)
        
        if df is None or len(df) < 1:
            continue
        
        # Usar última fila
        features = df[feature_cols].iloc[-1:].fillna(0)
        
        # Predicción y probabilidades
        pred = model.predict(features)[0]
        probs = model.predict_proba(features)[0]
        
        # Máxima confianza
        confidence = float(max(probs))
        
        predictions[coin] = {
            'market_mode': pred,
            'confidence': round(confidence, 3),
            'probabilities': {
                cls: round(float(prob), 3) 
                for cls, prob in zip(model.classes_, probs)
            }
        }
        
        print(f"   {coin}: {pred} ({confidence:.1%} confianza)")
    
    # Guardar predicciones
    output = {
        'timestamp': datetime.now().isoformat(),
        'model_accuracy': metadata['accuracy'],
        'predictions': predictions
    }
    
    with open(PREDICTIONS_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Predicciones guardadas: {PREDICTIONS_FILE}")
    
    return output

# ════════════════════════════════════════════════════════
# VALIDAR VS AUTO-ADJUST
# ════════════════════════════════════════════════════════

def validate_vs_auto_adjust():
    """Comparar predicción ML vs Auto-Adjust"""
    
    # Cargar predicciones ML
    if not os.path.exists(PREDICTIONS_FILE):
        print("❌ No hay predicciones ML")
        return None
    
    with open(PREDICTIONS_FILE, 'r') as f:
        ml_preds = json.load(f)
    
    # Cargar configuración de Auto-Adjust
    config_file = os.path.join(WORKSPACE, "crypto-bots/market-mode.conf")
    
    if not os.path.exists(config_file):
        print("⚠️ Auto-Adjust no ha generado configuración aún")
        return ml_preds
    
    # Leer market-mode.conf
    auto_adjust_mode = None
    with open(config_file, 'r') as f:
        for line in f:
            if line.startswith('MARKET_MODE='):
                auto_adjust_mode = line.strip().split('=')[1].strip('"')
                break
    
    if auto_adjust_mode is None:
        print("⚠️ No se encontró MARKET_MODE en auto-adjust")
        return ml_preds
    
    print(f"\n🔍 Validación:")
    print(f"   Auto-Adjust: {auto_adjust_mode}")
    
    # Comparar con ML (usar BTC como referencia principal)
    btc_ml = ml_preds['predictions'].get('BTC', {})
    ml_mode = btc_ml.get('market_mode', 'UNKNOWN')
    ml_confidence = btc_ml.get('confidence', 0)
    
    print(f"   ML (BTC): {ml_mode} ({ml_confidence:.1%} confianza)")
    
    # Determinar si hay discrepancia
    if ml_mode != auto_adjust_mode:
        if ml_confidence > 0.80:
            print(f"\n⚠️ DISCREPANCIA DETECTADA")
            print(f"   ML tiene {ml_confidence:.1%} confianza → Usar ML")
            ml_preds['recommended_mode'] = ml_mode
            ml_preds['discrepancy'] = True
            ml_preds['reason'] = f"ML {ml_mode} vs Auto-Adjust {auto_adjust_mode}"
        else:
            print(f"\n⚠️ DISCREPANCIA (baja confianza ML)")
            print(f"   Usar Auto-Adjust por seguridad")
            ml_preds['recommended_mode'] = auto_adjust_mode
            ml_preds['discrepancy'] = True
            ml_preds['reason'] = f"ML confianza < 80%"
    else:
        print(f"\n✅ ACUERDO: {ml_mode}")
        ml_preds['recommended_mode'] = ml_mode
        ml_preds['discrepancy'] = False
    
    # Actualizar archivo
    with open(PREDICTIONS_FILE, 'w') as f:
        json.dump(ml_preds, f, indent=2)
    
    return ml_preds

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Market Classifier ML")
    parser.add_argument('--train', action='store_true', help='Entrenar modelo')
    parser.add_argument('--predict', action='store_true', help='Predecir modo actual')
    parser.add_argument('--validate', action='store_true', help='Validar vs Auto-Adjust')
    parser.add_argument('--data', action='store_true', help='Generar data de entrenamiento')
    
    args = parser.parse_args()
    
    if args.train:
        train_model()
    elif args.data:
        generate_training_data()
    elif args.predict:
        predict_market_mode()
    elif args.validate:
        validate_vs_auto_adjust()
    else:
        # Default: predecir y validar
        print("╔═══════════════════════════════════════════════════════╗")
        print("║  🧠 MARKET CLASSIFIER - ML VALIDATION                 ║")
        print("╚═══════════════════════════════════════════════════════╝")
        print()
        
        predict_market_mode()
        validate_vs_auto_adjust()
