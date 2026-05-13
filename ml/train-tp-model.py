#!/usr/bin/env python3
"""
🐕 Perrobotillo ML - TP Prediction Model Trainer
Entrena modelo usando datos históricos existentes de backtest
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import lightgbm as lgb
import joblib
import json
import os
import warnings
warnings.filterwarnings('ignore')

# Configuración
DATA_DIR = '/home/overgon/.openclaw/workspace/backtest/data'
ML_DIR = '/home/overgon/.openclaw/workspace/ml'
TRADE_HISTORY = '/home/overgon/.openclaw/workspace/crypto-bots/trade-history.json'

def load_historical_data():
    """Carga datos históricos de todas las coins"""
    print("\n📊 Cargando datos históricos...")
    
    coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
    all_data = []
    
    for coin in coins:
        try:
            # Intentar cargar CSV histórico
            csv_file = f"{DATA_DIR}/{coin}USDT_historical.csv"
            if os.path.exists(csv_file):
                df = pd.read_csv(csv_file)
                df['coin'] = coin
                all_data.append(df)
                print(f"  ✅ {coin}: {len(df)} rows")
            else:
                print(f"  ⚠️  {coin}: No encontrado")
        except Exception as e:
            print(f"  ❌ {coin}: Error - {e}")
    
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        print(f"\n📈 Total: {len(combined)} rows, {len(coins)} coins")
        return combined
    else:
        print("❌ No se encontraron datos")
        return None

def add_technical_indicators(df):
    """Agrega indicadores técnicos si no existen"""
    print("\n🔧 Calculando indicadores técnicos...")
    
    # Verificar si ya existen columnas
    if 'rsi' in df.columns:
        print("  ✅ Indicadores ya existen")
        return df
    
    # Calcular indicadores por coin
    for coin in df['coin'].unique():
        mask = df['coin'] == coin
        coin_df = df.loc[mask].copy()
        
        # RSI
        delta = coin_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        coin_df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = coin_df['close'].ewm(span=12, adjust=False).mean()
        exp2 = coin_df['close'].ewm(span=26, adjust=False).mean()
        coin_df['macd'] = exp1 - exp2
        coin_df['macd_signal'] = coin_df['macd'].ewm(span=9, adjust=False).mean()
        
        # Bollinger Bands
        coin_df['bb_middle'] = coin_df['close'].rolling(window=20).mean()
        coin_df['bb_std'] = coin_df['close'].rolling(window=20).std()
        coin_df['bb_upper'] = coin_df['bb_middle'] + (coin_df['bb_std'] * 2)
        coin_df['bb_lower'] = coin_df['bb_middle'] - (coin_df['bb_std'] * 2)
        coin_df['bb_width'] = (coin_df['bb_upper'] - coin_df['bb_lower']) / coin_df['bb_middle']
        
        # EMAs
        coin_df['ema_9'] = coin_df['close'].ewm(span=9, adjust=False).mean()
        coin_df['ema_21'] = coin_df['close'].ewm(span=21, adjust=False).mean()
        
        # Volatilidad
        coin_df['volatility'] = coin_df['close'].pct_change().rolling(window=20).std()
        
        # Volumen relativo
        coin_df['volume_ma'] = coin_df['volume'].rolling(window=20).mean()
        coin_df['volume_ratio'] = coin_df['volume'] / coin_df['volume_ma']
        
        # Actualizar DataFrame principal
        df.loc[mask, coin_df.columns] = coin_df.values
    
    print("  ✅ Indicadores calculados")
    return df

def load_trade_history():
    """Carga trades reales para validación"""
    print("\n📊 Cargando trades reales...")
    
    try:
        with open(TRADE_HISTORY, 'r') as f:
            trades = json.load(f)
        
        print(f"  ✅ {len(trades)} trades reales encontrados")
        
        # Convertir a DataFrame
        df_trades = pd.DataFrame(trades)
        return df_trades
    except Exception as e:
        print(f"  ⚠️  Error: {e}")
        return None

def create_labels_from_trades(df, trades_df):
    """
    Crea labels basados en trades reales
    Usamos los trades del bot como ground truth
    """
    print("\n🎯 Creando labels desde trades reales...")
    
    # Inicializar labels
    df['tp1_hit'] = 0
    df['tp2_hit'] = 0
    df['tp3_hit'] = 0
    df['sl_hit'] = 0
    
    if trades_df is None:
        print("  ⚠️  No hay trades reales, usando estrategia fija")
        # Fallback: labels basados en umbrales fijos
        for i in range(len(df) - 50):
            entry = df.iloc[i]['close']
            future_high = df.iloc[i+1:i+51]['high'].max()
            future_low = df.iloc[i+1:i+51]['low'].min()
            
            gain = (future_high - entry) / entry
            loss = (entry - future_low) / entry
            
            if gain >= 0.12:  # TP3
                df.iloc[i, df.columns.get_loc('tp3_hit')] = 1
                df.iloc[i, df.columns.get_loc('tp2_hit')] = 1
                df.iloc[i, df.columns.get_loc('tp1_hit')] = 1
            elif gain >= 0.07:  # TP2
                df.iloc[i, df.columns.get_loc('tp2_hit')] = 1
                df.iloc[i, df.columns.get_loc('tp1_hit')] = 1
            elif gain >= 0.035:  # TP1
                df.iloc[i, df.columns.get_loc('tp1_hit')] = 1
            
            if loss >= 0.10:  # SL
                df.iloc[i, df.columns.get_loc('sl_hit')] = 1
        
        print(f"  ✅ Labels creados (estrategia fija)")
    else:
        # Usar trades reales
        # Esto es más complejo - matching por timestamp y coin
        print("  ⚠️  Matching con trades reales (implementación futura)")
        # Por ahora usamos fallback
        create_labels_from_trades(df, None)
    
    return df

def prepare_features(df):
    """Prepara features para el modelo"""
    print("\n🔧 Preparando features...")
    
    feature_cols = [
        'open', 'high', 'low', 'close', 'volume',
        'rsi', 'macd', 'macd_signal',
        'bb_upper', 'bb_lower', 'bb_width',
        'ema_9', 'ema_21',
        'volatility', 'volume_ratio'
    ]
    
    # One-hot encoding para coin
    df_with_dummies = pd.get_dummies(df, columns=['coin'], prefix='coin')
    
    # Eliminar rows con NaN
    df_clean = df_with_dummies.dropna()
    
    # Eliminar columnas no usadas
    feature_cols_extended = [col for col in feature_cols if col in df_clean.columns]
    feature_cols_extended += [col for col in df_clean.columns if col.startswith('coin_')]
    
    print(f"  ✅ Features: {len(feature_cols_extended)}")
    print(f"  ✅ Rows limpias: {len(df_clean)}")
    
    return df_clean, feature_cols_extended

def train_model(df, feature_cols):
    """Entrena modelo LightGBM"""
    print("\n🤖 Entrenando modelo LightGBM...")
    
    # Features y labels
    X = df[feature_cols]
    y = df['tp1_hit']  # Predecir si alcanza TP1
    
    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"  ├─ Train: {len(X_train)} samples")
    print(f"  └─ Test: {len(X_test)} samples")
    
    # Configurar modelo
    model = lgb.LGBMClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=6,
        num_leaves=31,
        random_state=42,
        verbose=-1
    )
    
    # Entrenar
    print("  ├─ Entrenando...")
    model.fit(X_train, y_train)
    
    # Evaluar
    print("  ├─ Evaluando...")
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"  ├─ Accuracy: {accuracy:.2%}")
    
    # Cross-validation
    print("  ├─ Cross-validation (5-fold)...")
    cv_scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')
    print(f"  │  CV scores: {cv_scores}")
    print(f"  │  Mean CV: {cv_scores.mean():.2%} (+/- {cv_scores.std()*2:.2%})")
    
    # Feature importance
    print("\n  📊 Feature Importance (top 10):")
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for idx, row in importance.head(10).iterrows():
        print(f"    • {row['feature']}: {row['importance']:.2f}")
    
    return model, accuracy, cv_scores.mean()

def save_model(model, feature_cols, accuracy):
    """Guarda modelo entrenado"""
    print("\n💾 Guardando modelo...")
    
    os.makedirs(ML_DIR, exist_ok=True)
    
    # Guardar modelo
    model_file = f"{ML_DIR}/tp_prediction_model.pkl"
    joblib.dump(model, model_file)
    print(f"  ✅ Modelo: {model_file}")
    
    # Guardar metadata
    metadata = {
        'feature_cols': feature_cols,
        'accuracy': accuracy,
        'trained_at': pd.Timestamp.now().isoformat(),
        'version': '1.0.0'
    }
    
    metadata_file = f"{ML_DIR}/model_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"  ✅ Metadata: {metadata_file}")
    
    # Guardar scaler/normalization si es necesario
    print(f"\n📦 Tamaño del modelo: {os.path.getsize(model_file) / 1024 / 1024:.2f} MB")

def main():
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🤖 Perrobotillo ML - TP Model Trainer                ║")
    print("╚═══════════════════════════════════════════════════════╝")
    
    # 1. Cargar datos históricos
    df = load_historical_data()
    if df is None:
        return
    
    # 2. Agregar indicadores técnicos
    df = add_technical_indicators(df)
    
    # 3. Cargar trades reales
    trades_df = load_trade_history()
    
    # 4. Crear labels
    df = create_labels_from_trades(df, trades_df)
    
    # 5. Preparar features
    df_clean, feature_cols = prepare_features(df)
    
    # 6. Entrenar modelo
    model, accuracy, cv_accuracy = train_model(df_clean, feature_cols)
    
    # 7. Guardar modelo
    save_model(model, feature_cols, accuracy)
    
    # 8. Resumen final
    print("\n╔═══════════════════════════════════════════════════════╗")
    print("║  ✅ ENTRENAMIENTO COMPLETADO                          ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print(f"\n📊 RESUMEN:")
    print(f"  • Accuracy: {accuracy:.2%}")
    print(f"  • CV Accuracy: {cv_accuracy:.2%}")
    print(f"  • Features: {len(feature_cols)}")
    print(f"  • Modelo: tp_prediction_model.pkl")
    print(f"\n🎯 PRÓXIMO PASO:")
    print(f"  • Integrar con bot principal")
    print(f"  • TP dinámico basado en predicciones")

if __name__ == "__main__":
    main()
