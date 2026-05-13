#!/usr/bin/env python3
"""
🐕 Perrobotillo ML - Data Collector
Recolecta datos históricos de Binance para entrenar modelo de TP prediction
"""

import pandas as pd
import numpy as np
from binance.client import Client
from datetime import datetime, timedelta
import json
import os

# Configuración
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
INTERVALS = ['5m', '15m', '1h']
DAYS_BACK = 90  # 3 meses de datos

def get_historical_data(symbol, interval, days):
    """Obtiene datos históricos de Binance"""
    client = Client()  # Sin API key para datos públicos
    
    klines = client.get_historical_klines(
        symbol=symbol,
        interval=interval,
        start_str=f"{days} days ago UTC"
    )
    
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'
    ])
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['open'] = df['open'].astype(float)
    df['volume'] = df['volume'].astype(float)
    
    return df

def add_technical_indicators(df):
    """Agrega indicadores técnicos"""
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
    df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    
    # EMAs
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # Volatilidad
    df['volatility'] = df['close'].pct_change().rolling(window=20).std()
    
    # Volumen relativo
    df['volume_ma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    
    return df

def create_labels(df, tp1_pct=0.035, tp2_pct=0.07, tp3_pct=0.12, sl_pct=0.10):
    """
    Crea labels para clasificación
    ¿El precio alcanzó TP1/TP2/TP3 antes de SL?
    """
    df['tp1_hit'] = 0
    df['tp2_hit'] = 0
    df['tp3_hit'] = 0
    df['sl_hit'] = 0
    
    for i in range(len(df) - 1):
        entry_price = df.iloc[i]['close']
        
        # Buscar máximo y mínimo en las próximas N velas
        lookforward = 50  # ~12 horas en 15m
        future_high = df.iloc[i+1:i+1+lookforward]['high'].max()
        future_low = df.iloc[i+1:i+1+lookforward]['low'].min()
        
        # Calcular porcentajes
        gain_pct = (future_high - entry_price) / entry_price
        loss_pct = (entry_price - future_low) / entry_price
        
        # Labels
        if gain_pct >= tp3_pct:
            df.iloc[i, df.columns.get_loc('tp3_hit')] = 1
            df.iloc[i, df.columns.get_loc('tp2_hit')] = 1
            df.iloc[i, df.columns.get_loc('tp1_hit')] = 1
        elif gain_pct >= tp2_pct:
            df.iloc[i, df.columns.get_loc('tp2_hit')] = 1
            df.iloc[i, df.columns.get_loc('tp1_hit')] = 1
        elif gain_pct >= tp1_pct:
            df.iloc[i, df.columns.get_loc('tp1_hit')] = 1
        
        if loss_pct >= sl_pct:
            df.iloc[i, df.columns.get_loc('sl_hit')] = 1
    
    return df

def main():
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🤖 Perrobotillo ML - Data Collector                  ║")
    print("╚═══════════════════════════════════════════════════════╝")
    
    os.makedirs('/home/overgon/.openclaw/workspace/ml/data', exist_ok=True)
    
    for coin in COINS:
        print(f"\n📊 Procesando {coin}USDT...")
        symbol = f"{coin}USDT"
        
        for interval in INTERVALS:
            print(f"  ├─ Intervalo: {interval}")
            
            try:
                df = get_historical_data(symbol, interval, DAYS_BACK)
                print(f"  │  Velas obtenidas: {len(df)}")
                
                df = add_technical_indicators(df)
                df = create_labels(df)
                
                # Guardar
                filename = f"/home/overgon/.openclaw/workspace/ml/data/{symbol}_{interval}_raw.csv"
                df.to_csv(filename, index=False)
                print(f"  └─ ✅ Guardado: {filename}")
                
            except Exception as e:
                print(f"  └─ ❌ Error: {e}")
    
    print("\n✅ Recolección completada!")

if __name__ == "__main__":
    main()
