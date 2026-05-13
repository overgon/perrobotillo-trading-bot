#!/usr/bin/env python3
"""
🐕 Perrobotillo ML - Auto-Retrain Pipeline
Re-entrena automáticamente el modelo con nuevos trades
Ejecución: Semanal (domingo 3 AM) o cuando hay 10+ trades nuevos
"""

import pandas as pd
import numpy as np
import joblib
import json
import os
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import lightgbm as lgb
import warnings
warnings.filterwarnings('ignore')

# Configuración
MODEL_PATH = '/home/overgon/.openclaw/workspace/ml/tp_prediction_model.pkl'
METADATA_PATH = '/home/overgon/.openclaw/workspace/ml/model_metadata.json'
TRADE_HISTORY_PATH = '/home/overgon/.openclaw/workspace/crypto-bots/trade-history.json'
BACKTEST_DATA_DIR = '/home/overgon/.openclaw/workspace/backtest/data'
ML_LOG_PATH = '/home/overgon/.openclaw/logs/ml-retrain.log'
MIN_TRADES_FOR_RETRAIN = 10  # Mínimo trades nuevos para re-entrenar

def log(message):
    """Loguea mensaje"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    
    os.makedirs(os.path.dirname(ML_LOG_PATH), exist_ok=True)
    with open(ML_LOG_PATH, 'a') as f:
        f.write(log_msg + '\n')

def load_current_model():
    """Carga el modelo actual"""
    if not os.path.exists(MODEL_PATH):
        log("❌ No hay modelo existente")
        return None, None
    
    model = joblib.load(MODEL_PATH)
    with open(METADATA_PATH, 'r') as f:
        metadata = json.load(f)
    
    log(f"✅ Modelo cargado (accuracy: {metadata.get('accuracy', 'N/A')})")
    return model, metadata

def load_trade_history():
    """Carga histórico de trades"""
    if not os.path.exists(TRADE_HISTORY_PATH):
        log("⚠️  No hay trade-history.json")
        return []
    
    with open(TRADE_HISTORY_PATH, 'r') as f:
        trades = json.load(f)
    
    log(f"✅ {len(trades)} trades en histórico")
    return trades

def get_new_trades(trades, last_retrain_count):
    """Obtiene trades nuevos desde último re-entrenamiento"""
    new_trades = trades[last_retrain_count:]
    log(f"🆕 {len(new_trades)} trades nuevos desde último re-entrenamiento")
    return new_trades

def load_historical_data():
    """Carga datos históricos de backtest"""
    log("📊 Cargando datos históricos...")
    
    coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
    all_data = []
    
    for coin in coins:
        csv_file = f"{BACKTEST_DATA_DIR}/{coin}USDT_historical.csv"
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            df['coin'] = coin
            all_data.append(df)
            log(f"  ├─ {coin}: {len(df)} rows")
    
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        log(f"  ✅ Total: {len(combined)} rows")
        return combined
    else:
        log("❌ No se encontraron datos históricos")
        return None

def add_indicators(df):
    """Calcula indicadores técnicos"""
    log("🔧 Calculando indicadores...")
    
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
        
        df.loc[mask, coin_df.columns] = coin_df.values
    
    log("   ✅ Indicadores calculados")
    return df

def create_labels_from_trades(df, trades):
    """Crea labels basados en trades reales"""
    log("🎯 Creando labels desde trades reales...")
    
    df['tp1_hit'] = 0
    df['tp2_hit'] = 0
    df['tp3_hit'] = 0
    df['sl_hit'] = 0
    
    # Por cada trade real, marcar el punto de entry en los datos históricos
    for trade in trades:
        try:
            coin = trade.get('symbol', trade.get('coin', ''))
            entry_price = float(trade.get('entryPrice', trade.get('entry', 0)))
            exit_price = float(trade.get('exitPrice', trade.get('exit', 0)))
            close_type = trade.get('closeType', '')
            
            # Buscar fila más cercana al entry en los datos históricos
            coin_mask = df['coin'] == coin
            coin_df = df[coin_mask]
            
            if len(coin_df) == 0:
                continue
            
            # Encontrar índice más cercano al precio de entry
            price_diff = (coin_df['close'] - entry_price).abs()
            closest_idx = price_diff.idxmin()
            
            # Marcar labels según close_type
            if 'TP1' in close_type:
                df.loc[closest_idx, 'tp1_hit'] = 1
            elif 'TP2' in close_type:
                df.loc[closest_idx, 'tp1_hit'] = 1
                df.loc[closest_idx, 'tp2_hit'] = 1
            elif 'TP3' in close_type:
                df.loc[closest_idx, 'tp1_hit'] = 1
                df.loc[closest_idx, 'tp2_hit'] = 1
                df.loc[closest_idx, 'tp3_hit'] = 1
            elif 'SL' in close_type:
                df.loc[closest_idx, 'sl_hit'] = 1
        
        except Exception as e:
            log(f"  ⚠️  Error procesando trade: {e}")
    
    # Fallback: labels basados en umbrales para datos sin trades
    for i in range(len(df) - 50):
        if df.iloc[i]['tp1_hit'] == 0:  # Si no tiene label de trade real
            entry = df.iloc[i]['close']
            future_high = df.iloc[i+1:i+51]['high'].max()
            future_low = df.iloc[i+1:i+51]['low'].min()
            
            gain = (future_high - entry) / entry
            loss = (entry - future_low) / entry
            
            if gain >= 0.12:
                df.iloc[i, df.columns.get_loc('tp1_hit')] = 1
                df.iloc[i, df.columns.get_loc('tp2_hit')] = 1
                df.iloc[i, df.columns.get_loc('tp3_hit')] = 1
            elif gain >= 0.07:
                df.iloc[i, df.columns.get_loc('tp1_hit')] = 1
                df.iloc[i, df.columns.get_loc('tp2_hit')] = 1
            elif gain >= 0.035:
                df.iloc[i, df.columns.get_loc('tp1_hit')] = 1
    
    log(f"   ✅ Labels creados")
    return df

def prepare_features(df):
    """Prepara features para entrenamiento"""
    log("🔧 Preparando features...")
    
    feature_cols = [
        'open', 'high', 'low', 'close', 'volume',
        'rsi', 'macd', 'macd_signal',
        'bb_upper', 'bb_lower', 'bb_width',
        'ema_9', 'ema_21',
        'volatility', 'volume_ratio'
    ]
    
    # One-hot encoding
    df_with_dummies = pd.get_dummies(df, columns=['coin'], prefix='coin')
    
    # Drop NaN
    df_clean = df_with_dummies.dropna()
    
    # Feature columns extendidas
    feature_cols_extended = [col for col in feature_cols if col in df_clean.columns]
    feature_cols_extended += [col for col in df_clean.columns if col.startswith('coin_')]
    
    log(f"  ✅ Features: {len(feature_cols_extended)}")
    log(f"  ✅ Rows limpias: {len(df_clean)}")
    
    return df_clean, feature_cols_extended

def train_model(df, feature_cols):
    """Entrena nuevo modelo"""
    log("🤖 Entrenando modelo...")
    
    X = df[feature_cols]
    y = df['tp1_hit']
    
    # Class weights para datos desbalanceados
    n_neg = (y == 0).sum()
    n_pos = (y == 1).sum()
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    log(f"  ├─ Train: {len(X_train)} samples")
    log(f"  └─ Test: {len(X_test)} samples")
    
    # Modelo con class weights
    model = lgb.LGBMClassifier(
        n_estimators=150,
        learning_rate=0.05,
        max_depth=8,
        num_leaves=31,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        verbose=-1
    )
    
    log("  ├─ Entrenando...")
    model.fit(X_train, y_train)
    
    log("  ├─ Evaluando...")
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    log(f"  ├─ Accuracy: {accuracy:.2%}")
    
    # Feature importance
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    log("  ├─ Top 3 features:")
    for idx, row in importance.head(3).iterrows():
        log(f"  │  • {row['feature']}: {row['importance']:.2f}")
    
    return model, accuracy, feature_cols

def save_model(model, accuracy, feature_cols):
    """Guarda nuevo modelo"""
    log("💾 Guardando modelo...")
    
    joblib.dump(model, MODEL_PATH)
    log(f"  ✅ Modelo: {MODEL_PATH}")
    
    metadata = {
        'feature_cols': feature_cols,
        'accuracy': accuracy,
        'trained_at': datetime.now().isoformat(),
        'version': '2.0.0',
        'retrain_count': get_retrain_count() + 1
    }
    
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    log(f"  ✅ Metadata: {METADATA_PATH}")
    log(f"  📦 Tamaño: {os.path.getsize(MODEL_PATH) / 1024 / 1024:.2f} MB")

def get_retrain_count():
    """Obtiene número de re-entrenamientos"""
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, 'r') as f:
            metadata = json.load(f)
            return metadata.get('retrain_count', 0)
    return 0

def save_last_retrain_info(trade_count):
    """Guarda información del último re-entrenamiento"""
    info = {
        'last_retrain': datetime.now().isoformat(),
        'trade_count_at_retrain': trade_count,
        'retrain_count': get_retrain_count() + 1
    }
    
    with open('/home/overgon/.openclaw/workspace/ml/last_retrain.json', 'w') as f:
        json.dump(info, f, indent=2)
    
    log(f"💾 Info guardada: last_retrain.json")

def main():
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🤖 Perrobotillo ML - Auto-Retrain                    ║")
    print("╚═══════════════════════════════════════════════════════╝")
    
    log(f"🚀 Iniciando auto-retrain...")
    
    # 1. Verificar si hay modelo existente
    model, old_metadata = load_current_model()
    
    # 2. Cargar trades
    trades = load_trade_history()
    
    # 3. Verificar si hay suficientes trades nuevos
    last_retrain_info_path = '/home/overgon/.openclaw/workspace/ml/last_retrain.json'
    last_trade_count = 0
    
    if os.path.exists(last_retrain_info_path):
        with open(last_retrain_info_path, 'r') as f:
            last_info = json.load(f)
            last_trade_count = last_info.get('trade_count_at_retrain', 0)
    
    new_trades_count = len(trades) - last_trade_count
    
    if new_trades_count < MIN_TRADES_FOR_RETRAIN:
        log(f"⚠️  Solo {new_trades_count} trades nuevos (mínimo: {MIN_TRADES_FOR_RETRAIN})")
        log(f"💤 Saltando re-entrenamiento")
        return
    
    log(f"✅ {new_trades_count} trades nuevos - Procediendo con re-entrenamiento")
    
    # 4. Cargar datos históricos
    df = load_historical_data()
    if df is None:
        return
    
    # 5. Calcular indicadores
    df = add_indicators(df)
    
    # 6. Crear labels con trades reales
    df = create_labels_from_trades(df, trades)
    
    # 7. Preparar features
    df_clean, feature_cols = prepare_features(df)
    
    # 8. Entrenar modelo
    model, accuracy, feature_cols = train_model(df_clean, feature_cols)
    
    # 9. Guardar modelo
    save_model(model, accuracy, feature_cols)
    
    # 10. Guardar info del re-entrenamiento
    save_last_retrain_info(len(trades))
    
    # Resumen final
    log("")
    log("╔═══════════════════════════════════════════════════════╗")
    log("║  ✅ AUTO-RETRAIN COMPLETADO                           ║")
    log("╚═══════════════════════════════════════════════════════╝")
    log(f"\n📊 RESUMEN:")
    log(f"  • Trades usados: {len(trades)}")
    log(f"  • Trades nuevos: {new_trades_count}")
    log(f"  • Accuracy: {accuracy:.2%}")
    log(f"  • Modelo actualizado: tp_prediction_model.pkl")
    
    # Enviar notificación por Telegram (opcional)
    # send_telegram_notification(accuracy, new_trades_count)

if __name__ == "__main__":
    main()
