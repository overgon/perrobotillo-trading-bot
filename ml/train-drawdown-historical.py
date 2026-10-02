#!/usr/bin/env python3
"""
🧠 ML Drawdown Predictor - Entrenamiento con Data Histórica (6 años)

Simula la estrategia actual del bot sobre datos históricos de Binance
para generar miles de samples de entrenamiento incluyendo crisis reales.

Data sources:
- backtest/data/*_historical.csv (6 años de velas 1h)
- Estrategia: FASE 1 v2.1 actual (TP1:2%, TP2:4%, TP3:6%, SL:4-8%)

Output:
- drawdown-training-historical.csv (dataset completo)
- drawdown-predictor.pkl (modelo re-entrenado)
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
BACKTEST_DATA = os.path.join(WORKSPACE, "backtest", "data")

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

# Estrategia actual del bot (FASE 1 v2.1)
STRATEGY = {
    'TP1': 0.02,      # 2%
    'TP2': 0.04,      # 4%
    'TP3': 0.06,      # 6%
    'STOP_LOSS': 0.04, # 4% (BEAR mode)
    'MAX_SLOTS': 3,
    'POSITION_SIZE': 0.40,  # 40% del capital por trade
}

OUTPUT_TRAINING = os.path.join(ML_DIR, "drawdown-training-historical.csv")
OUTPUT_MODEL = os.path.join(ML_DIR, "drawdown-predictor-historical.pkl")
OUTPUT_METADATA = os.path.join(ML_DIR, "drawdown-historical-metadata.json")

# ════════════════════════════════════════════════════════
# SIMULADOR DE ESTRATEGIA
# ════════════════════════════════════════════════════════

class Slot:
    def __init__(self, slot_id, entry_price, quantity, timestamp):
        self.slot_id = slot_id
        self.entry_price = entry_price
        self.quantity = quantity
        self.timestamp = timestamp
        self.status = "ACTIVE"
        self.tp1_done = False
        self.tp2_done = False
        self.tp3_done = False

def simulate_strategy_on_data(df, symbol, initial_capital=1000):
    """
    Simula la estrategia del bot sobre data histórica de velas.
    
    Returns:
        list: Lista de trades con timestamp, pnl, close_type
    """
    trades = []
    capital = initial_capital
    slots = {}  # slot_id -> Slot object
    next_slot_id = 1
    
    # Parámetros de la estrategia
    tp1_pct = STRATEGY['TP1']
    tp2_pct = STRATEGY['TP2']
    tp3_pct = STRATEGY['TP3']
    sl_pct = STRATEGY['STOP_LOSS']
    max_slots = STRATEGY['MAX_SLOTS']
    position_size = STRATEGY['POSITION_SIZE']
    
    for idx, row in df.iterrows():
        timestamp = row['timestamp']
        open_price = row['open']
        high = row['high']
        low = row['low']
        close = row['close']
        
        # 1. Verificar cierre de slots activos (TP/SL)
        slots_to_close = []
        
        for slot_id, slot in slots.items():
            if slot.status != "ACTIVE":
                continue
            
            # Calcular precios objetivo
            tp1_price = slot.entry_price * (1 + tp1_pct)
            tp2_price = slot.entry_price * (1 + tp2_pct)
            tp3_price = slot.entry_price * (1 + tp3_pct)
            sl_price = slot.entry_price * (1 - sl_pct)
            
            # Verificar si tocó SL primero (prioridad)
            if low <= sl_price:
                slots_to_close.append((slot_id, 'SL', sl_price))
                continue
            
            # Verificar TPs en orden
            if high >= tp3_price:
                slots_to_close.append((slot_id, 'TP3', tp3_price))
            elif high >= tp2_price:
                slots_to_close.append((slot_id, 'TP2', tp2_price))
            elif high >= tp1_price:
                slots_to_close.append((slot_id, 'TP1', tp1_price))
        
        # Ejecutar cierres
        for slot_id, close_type, exit_price in slots_to_close:
            slot = slots[slot_id]
            
            # Calcular PnL
            if close_type == 'SL':
                pnl_pct = -sl_pct
            else:
                pnl_pct = (exit_price - slot.entry_price) / slot.entry_price
            
            pnl_usdt = slot.quantity * (exit_price - slot.entry_price)
            
            trades.append({
                'symbol': symbol,
                'slot_id': slot_id,
                'timestamp': timestamp,
                'entry_price': slot.entry_price,
                'exit_price': exit_price,
                'quantity': slot.quantity,
                'close_type': close_type,
                'pnl_usdt': pnl_usdt,
                'pnl_pct': pnl_pct
            })
            
            slot.status = "CLOSED"
            capital += pnl_usdt
            
            # Eliminar slot cerrado
            del slots[slot_id]
        
        # 2. Verificar si podemos abrir nuevos slots
        active_count = len([s for s in slots.values() if s.status == "ACTIVE"])
        
        if active_count < max_slots and capital > 10:
            # Señal de entrada simple: comprar en cada vela (simplificación)
            # En realidad aquí iría la lógica de entry del bot
            position_value = capital * position_size / (max_slots - active_count)
            quantity = position_value / open_price
            
            if quantity > 0 and open_price > 0:
                slot_id = next_slot_id
                next_slot_id += 1
                
                slots[slot_id] = Slot(slot_id, open_price, quantity, timestamp)
    
    return trades, capital

# ════════════════════════════════════════════════════════
# GENERAR FEATURES DE RIESGO
# ════════════════════════════════════════════════════════

def calculate_risk_features_at_time(trades_before, symbol):
    """Calcular features de riesgo en un punto del tiempo"""
    
    if not trades_before:
        return {
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
    
    df = pd.DataFrame(trades_before)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', utc=True)
    df['pnl_usdt'] = df['pnl_usdt'].astype(float)
    df['is_loss'] = df['pnl_usdt'] < 0
    
    features = {}
    
    # Trades últimas 24h
    now = df['timestamp'].max()
    trades_24h = df[df['timestamp'] >= (now - timedelta(hours=24))]
    
    if len(trades_24h) > 0:
        features['loss_rate_24h'] = trades_24h['is_loss'].mean()
        features['total_trades_24h'] = len(trades_24h)
        features['drawdown_24h'] = abs(trades_24h[trades_24h['pnl_usdt'] < 0]['pnl_usdt'].sum())
        
        losses_24h = trades_24h[trades_24h['pnl_usdt'] < 0]['pnl_usdt']
        features['avg_loss_size'] = abs(losses_24h.mean()) if len(losses_24h) > 0 else 0
    else:
        features['loss_rate_24h'] = 0
        features['total_trades_24h'] = 0
        features['drawdown_24h'] = 0
        features['avg_loss_size'] = 0
    
    # Trades últimos 7d
    trades_7d = df[df['timestamp'] >= (now - timedelta(days=7))]
    
    if len(trades_7d) > 0:
        features['loss_rate_7d'] = trades_7d['is_loss'].mean()
        features['total_trades_7d'] = len(trades_7d)
        features['drawdown_7d'] = abs(trades_7d[trades_7d['pnl_usdt'] < 0]['pnl_usdt'].sum())
        
        losses_7d = trades_7d[trades_7d['pnl_usdt'] < 0]['pnl_usdt']
        features['loss_volatility'] = abs(losses_7d.std()) if len(losses_7d) > 1 else 0
    else:
        features['loss_rate_7d'] = 0
        features['total_trades_7d'] = 0
        features['drawdown_7d'] = 0
        features['loss_volatility'] = 0
    
    # Racha de pérdidas (últimos 10 trades)
    recent = df.sort_values('timestamp', ascending=False).head(10)
    loss_streak = 0
    current_streak = 0
    
    for _, row in recent.iterrows():
        if row['is_loss']:
            current_streak += 1
            loss_streak = max(loss_streak, current_streak)
        else:
            current_streak = 0
    
    features['loss_streak'] = loss_streak
    
    return features

def label_risk_level(trade):
    """
    Etiquetar nivel de riesgo basado en el resultado del trade.
    
    HIGH_RISK: El trade fue pérdida (el modelo debería haber pausado)
    MEDIUM_RISK: Ganancia muy pequeña (<1%)
    LOW_RISK: Ganancia normal
    """
    pnl = float(trade.get('pnl_usdt', 0))
    
    if pnl < 0:
        return 'HIGH_RISK'
    elif pnl < 1:  # Ganancia < $1
        return 'MEDIUM_RISK'
    else:
        return 'LOW_RISK'

# ════════════════════════════════════════════════════════
# GENERAR DATASET COMPLETO
# ════════════════════════════════════════════════════════

def generate_historical_dataset():
    """Generar dataset completo con data histórica de 6 años"""
    
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🧠 ML DRAWDOWN PREDICTOR - ENTRENAMIENTO HISTÓRICO  ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    
    all_trades = []
    
    # Cargar data histórica de cada coin
    for coin in COINS:
        csv_file = os.path.join(BACKTEST_DATA, f"{coin}USDT_historical.csv")
        
        if not os.path.exists(csv_file):
            print(f"⚠️  No encontrado: {csv_file}")
            continue
        
        print(f"📊 Procesando {coin}...")
        
        # Leer CSV
        df = pd.read_csv(csv_file)
        
        # Normalizar columnas
        df.columns = df.columns.str.lower().str.strip()
        
        # Asegurar columnas requeridas
        required_cols = ['timestamp', 'open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            print(f"   ❌ Columnas faltantes en {coin}")
            continue
        
        # Parsear timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', utc=True)
        
        # Simular estrategia
        trades, final_capital = simulate_strategy_on_data(df, coin)
        
        print(f"   ✅ {len(trades)} trades simulados")
        print(f"   💰 Capital final: ${final_capital:.2f}")
        
        all_trades.extend(trades)
    
    if not all_trades:
        print("❌ No se generaron trades")
        return None
    
    print(f"\n📈 Total trades simulados: {len(all_trades)}")
    
    # Ordenar por timestamp
    all_trades.sort(key=lambda x: x['timestamp'])
    
    # Generar dataset de entrenamiento
    print("\n🔨 Generando features de entrenamiento...")
    
    training_data = []
    
    for i, trade in enumerate(all_trades):
        # Trades ANTES de este trade (para calcular features)
        trades_before = all_trades[:i]
        
        # Calcular features
        features = calculate_risk_features_at_time(trades_before, trade['symbol'])
        
        # Hora del trade (feature cíclica)
        ts = pd.to_datetime(trade['timestamp'], format='mixed', utc=True)
        hour = ts.hour
        features['hour_sin'] = np.sin(2 * np.pi * hour / 24)
        features['hour_cos'] = np.cos(2 * np.pi * hour / 24)
        
        # One-hot encoding para symbol
        for c in COINS:
            features[f'coin_{c}'] = 1 if c == trade['symbol'] else 0
        
        # Label basado en resultado del trade
        features['label'] = label_risk_level(trade)
        
        # Metadata del trade
        features['symbol'] = trade['symbol']
        features['pnl_usdt'] = trade['pnl_usdt']
        features['close_type'] = trade['close_type']
        
        training_data.append(features)
    
    df_training = pd.DataFrame(training_data)
    df_training.to_csv(OUTPUT_TRAINING, index=False)
    
    print(f"\n✅ Dataset guardado: {OUTPUT_TRAINING}")
    print(f"   Filas: {len(df_training)}")
    
    # Distribución de labels
    print("\n📊 Distribución de labels:")
    label_counts = df_training['label'].value_counts()
    for label, count in label_counts.items():
        pct = count / len(df_training) * 100
        print(f"   {label}: {count} ({pct:.1f}%)")
    
    return df_training

# ════════════════════════════════════════════════════════
# ENTRENAR MODELO
# ════════════════════════════════════════════════════════

def train_model(df=None):
    """Entrenar modelo con dataset histórico"""
    
    if df is None:
        if os.path.exists(OUTPUT_TRAINING):
            df = pd.read_csv(OUTPUT_TRAINING)
        else:
            print("❌ No hay dataset. Generando...")
            df = generate_historical_dataset()
    
    if df is None or len(df) < 100:
        print("❌ Dataset insuficiente (< 100 samples)")
        return None
    
    # Features para el modelo
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
    
    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"\n🧠 Entrenando Random Forest...")
    print(f"   Train: {len(X_train)} samples")
    print(f"   Test: {len(X_test)} samples")
    
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluación
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
    recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
    
    print(f"\n✅ Modelo entrenado")
    print(f"   Accuracy: {accuracy:.2%}")
    print(f"   Precision: {precision:.2%}")
    print(f"   Recall: {recall:.2%}")
    
    print("\n📊 Classification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # Guardar modelo
    joblib.dump(model, OUTPUT_MODEL)
    print(f"\n✅ Modelo guardado: {OUTPUT_MODEL}")
    
    # Metadata
    metadata = {
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'trained_at': datetime.now().isoformat(),
        'version': '2.0.0-historical',
        'feature_cols': feature_cols,
        'classes': list(model.classes_),
        'n_samples': len(df),
        'n_trades_simulated': len(df),
        'data_source': '6-year Binance historical data',
        'strategy': 'FASE 1 v2.1 (current)'
    }
    
    with open(OUTPUT_METADATA, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Metadata guardada: {OUTPUT_METADATA}")
    
    return model

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ML Drawdown Predictor - Historical Training")
    parser.add_argument('--generate', action='store_true', help='Generar dataset histórico')
    parser.add_argument('--train', action='store_true', help='Entrenar modelo')
    parser.add_argument('--full', action='store_true', help='Generar + entrenar')
    
    args = parser.parse_args()
    
    if args.full or (args.generate and args.train):
        df = generate_historical_dataset()
        if df is not None:
            train_model(df)
    elif args.generate:
        generate_historical_dataset()
    elif args.train:
        train_model()
    else:
        print("╔═══════════════════════════════════════════════════════╗")
        print("║  🧠 ML DRAWDOWN PREDICTOR - HISTORICAL TRAINING      ║")
        print("╚═══════════════════════════════════════════════════════╝")
        print()
        print("Uso:")
        print("  python3 train-drawdown-historical.py --generate  # Generar dataset")
        print("  python3 train-drawdown-historical.py --train     # Entrenar modelo")
        print("  python3 train-drawdown-historical.py --full      # Generar + entrenar")
        print()
        print("Data source: backtest/data/*_historical.csv (6 años)")
        print("Strategy: FASE 1 v2.1 actual")
