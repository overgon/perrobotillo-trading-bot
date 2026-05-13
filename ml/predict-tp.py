#!/usr/bin/env python3
"""
🐕 Perrobotillo ML - TP Prediction (Inference)
Predice probabilidad de TP en tiempo real usando datos de Binance
"""

import pandas as pd
import numpy as np
from binance.client import Client
import joblib
import json
import os
import sys
from datetime import datetime

# Configuración
MODEL_PATH = '/home/overgon/.openclaw/workspace/ml/tp_prediction_model.pkl'
METADATA_PATH = '/home/overgon/.openclaw/workspace/ml/model_metadata.json'
BINANCE_API_KEY = os.environ.get('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY = os.environ.get('BINANCE_SECRET_KEY', '')

def load_model():
    """Carga el modelo entrenado"""
    if not os.path.exists(MODEL_PATH):
        print(f"❌ Modelo no encontrado: {MODEL_PATH}")
        return None, None
    
    model = joblib.load(MODEL_PATH)
    
    with open(METADATA_PATH, 'r') as f:
        metadata = json.load(f)
    
    print(f"✅ Modelo cargado: {MODEL_PATH}")
    print(f"   Accuracy: {metadata.get('accuracy', 'N/A')}")
    
    return model, metadata

def get_current_market_data(coins=['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']):
    """Obtiene datos actuales de Binance"""
    print("\n📊 Obteniendo datos de mercado...")
    
    try:
        # Client sin API key para datos públicos
        client = Client()
        
        all_data = []
        
        for coin in coins:
            symbol = f"{coin}USDT"
            
            # Obtener últimas 100 velas de 1h
            klines = client.get_historical_klines(
                symbol=symbol,
                interval=Client.KLINE_INTERVAL_1HOUR,
                limit=100
            )
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'
            ])
            
            df['coin'] = coin
            df['close'] = df['close'].astype(float)
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            all_data.append(df)
        
        combined = pd.concat(all_data, ignore_index=True)
        print(f"   ✅ {len(combined)} velas obtenidas ({len(coins)} coins)")
        
        return combined
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def calculate_indicators(df):
    """Calcula indicadores técnicos"""
    print("\n🔧 Calculando indicadores...")
    
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
        
        # Actualizar DataFrame
        df.loc[mask, coin_df.columns] = coin_df.values
    
    print("   ✅ Indicadores calculados")
    return df

def predict_tp(model, metadata, df):
    """Predice probabilidad de TP para cada coin"""
    print("\n🎯 Prediciendo TP...")
    
    # Preparar features
    feature_cols = metadata['feature_cols']
    
    # One-hot encoding para coin
    df_with_dummies = pd.get_dummies(df, columns=['coin'], prefix='coin')
    
    # Asegurar que todas las columnas estén presentes
    for col in feature_cols:
        if col not in df_with_dummies.columns:
            df_with_dummies[col] = 0
    
    # Seleccionar solo las columnas del modelo
    X = df_with_dummies[feature_cols]
    
    # Predecir (última fila de cada coin = dato más reciente)
    predictions = {}
    
    for coin in df['coin'].unique():
        # Obtener última fila de esta coin
        coin_mask = df['coin'] == coin
        coin_data = X[coin_mask].iloc[-1:].dropna()
        
        if len(coin_data) > 0:
            # Predecir probabilidad
            proba = model.predict_proba(coin_data)[0]
            prob_tp1 = proba[1]  # Probabilidad de TP1
            
            predictions[coin] = {
                'prob_tp1': float(prob_tp1),
                'prediction': 'TP1_LIKELY' if prob_tp1 > 0.6 else 'TP1_UNLIKELY',
                'confidence': 'HIGH' if prob_tp1 > 0.7 or prob_tp1 < 0.3 else 'MEDIUM',
                'timestamp': datetime.now().isoformat()
            }
    
    print("   ✅ Predicciones generadas")
    return predictions

def get_tp_recommendation(prob_tp1):
    """Recomienda ajuste de TP basado en probabilidad"""
    if prob_tp1 > 0.75:
        return {
            'action': 'AGGRESSIVE',
            'tp1_pct': 4.0,
            'tp2_pct': 8.0,
            'tp3_pct': 15.0,
            'reason': 'Alta probabilidad de TP - ser agresivo'
        }
    elif prob_tp1 > 0.60:
        return {
            'action': 'NORMAL',
            'tp1_pct': 3.5,
            'tp2_pct': 7.0,
            'tp3_pct': 12.0,
            'reason': 'Probabilidad normal - mantener estrategia estándar'
        }
    elif prob_tp1 > 0.40:
        return {
            'action': 'CONSERVATIVE',
            'tp1_pct': 2.5,
            'tp2_pct': 5.0,
            'tp3_pct': 8.0,
            'reason': 'Probabilidad baja - ser conservador'
        }
    else:
        return {
            'action': 'DEFENSIVE',
            'tp1_pct': 2.0,
            'tp2_pct': 4.0,
            'tp3_pct': 6.0,
            'sl_pct': 8.0,
            'reason': 'Muy baja probabilidad - reducir exposición'
        }

def save_predictions(predictions, output_file='/home/overgon/.openclaw/workspace/ml/tp-predictions.json'):
    """Guarda predicciones en archivo"""
    with open(output_file, 'w') as f:
        json.dump(predictions, f, indent=2, default=str)
    
    print(f"\n💾 Predicciones guardadas: {output_file}")

def main():
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🤖 Perrobotillo ML - TP Prediction                   ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Cargar modelo
    model, metadata = load_model()
    if model is None:
        sys.exit(1)
    
    # 2. Obtener datos de mercado
    df = get_current_market_data()
    if df is None:
        sys.exit(1)
    
    # 3. Calcular indicadores
    df = calculate_indicators(df)
    
    # 4. Predecir
    predictions = predict_tp(model, metadata, df)
    
    # 5. Mostrar resultados
    print("\n╔═══════════════════════════════════════════════════════╗")
    print("║  📊 PREDICCIONES POR COIN                             ║")
    print("╚═══════════════════════════════════════════════════════╝")
    
    for coin, pred in sorted(predictions.items()):
        prob = pred['prob_tp1']
        confidence = pred['confidence']
        recommendation = get_tp_recommendation(prob)
        
        print(f"\n{coin}:")
        print(f"  Prob TP1: {prob:.1%}")
        print(f"  Confianza: {confidence}")
        print(f"  Predicción: {pred['prediction']}")
        print(f"  → Acción: {recommendation['action']}")
        print(f"     TP1: {recommendation['tp1_pct']}% | TP2: {recommendation['tp2_pct']}% | TP3: {recommendation['tp3_pct']}%")
        print(f"     Razón: {recommendation['reason']}")
    
    # 6. Guardar predicciones
    save_predictions(predictions)
    
    # 7. Output para integración con bot (JSON)
    output = {
        'timestamp': datetime.now().isoformat(),
        'predictions': predictions,
        'recommendations': {
            coin: get_tp_recommendation(pred['prob_tp1'])
            for coin, pred in predictions.items()
        }
    }
    
    # Guardar para que el bot lo lea
    with open('/home/overgon/.openclaw/workspace/ml/tp-recommendations.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n✅ Recomendaciones guardadas: /home/overgon/.openclaw/workspace/ml/tp-recommendations.json")
    
    return output

if __name__ == "__main__":
    main()
