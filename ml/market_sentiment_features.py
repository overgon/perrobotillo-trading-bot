#!/usr/bin/env python3
"""
📊 Market Sentiment Features - Colector de datos de sentimiento
Agrega features de sentimiento al dataset de entrenamiento del ML
"""

import json
import os
from datetime import datetime, timezone, timedelta
import urllib.request
import pandas as pd

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = "/home/overgon/.openclaw/workspace"
BACKTEST_DATA_DIR = f"{WORKSPACE}/backtest/data"
SENTIMENT_OUTPUT = f"{WORKSPACE}/ml/sentiment-features.json"

# ════════════════════════════════════════════════════════
# FUENTES DE DATOS DE SENTIMIENTO
# ════════════════════════════════════════════════════════

def get_fear_greed_historical():
    """
    Obtiene Fear & Greed Index histórico (últimos 90 días)
    Fuente: alternative.me
    """
    try:
        # Alternative.me solo da datos recientes, usamos múltiples llamadas
        url = "https://api.alternative.me/fng/?limit=90"
        req = urllib.request.urlopen(url, timeout=10)
        data = json.loads(req.read())
        
        sentiment_data = []
        for entry in data['data']:
            timestamp = datetime.fromtimestamp(int(entry['timestamp']))
            sentiment_data.append({
                'date': timestamp.strftime('%Y-%m-%d'),
                'value': int(entry['value']),
                'classification': entry['value_classification']
            })
        
        print(f"✅ Fear & Greed: {len(sentiment_data)} días obtenidos")
        return sentiment_data
    
    except Exception as e:
        print(f"⚠️ Fear & Greed error: {e}")
        return []

def get_btc_dominance():
    """
    Obtiene BTC Dominance histórico
    Fuente: CoinGecko API
    """
    try:
        # CoinGecko no tiene historical dominance gratis, usamos valor actual
        url = "https://api.coingecko.com/api/v3/global"
        req = urllib.request.urlopen(url, timeout=10)
        data = json.loads(req.read())
        
        market_cap_percentage = data['data']['market_cap_percentage']
        btc_dominance = market_cap_percentage.get('btc', 50.0)
        
        print(f"✅ BTC Dominance: {btc_dominance:.2f}%")
        return {'btc_dominance': btc_dominance, 'date': datetime.now().strftime('%Y-%m-%d')}
    
    except Exception as e:
        print(f"⚠️ BTC Dominance error: {e}")
        return {'btc_dominance': 50.0, 'date': datetime.now().strftime('%Y-%m-%d')}

def get_crypto_market_cap_trend():
    """
    Calcula tendencia del market cap crypto total
    """
    try:
        url = "https://api.coingecko.com/api/v3/global"
        req = urllib.request.urlopen(url, timeout=10)
        data = json.loads(req.read())
        
        total_market_cap = data['data']['total_market_cap']['usd']
        total_volume = data['data']['total_volume']['usd']
        
        # Volume to Market Cap ratio (indica actividad del mercado)
        volume_ratio = total_volume / total_market_cap if total_market_cap > 0 else 0
        
        print(f"✅ Market Cap Trend: ${total_market_cap/1e9:.1f}B, Vol Ratio: {volume_ratio:.4f}")
        return {
            'total_market_cap': total_market_cap,
            'total_volume': total_volume,
            'volume_to_market_ratio': volume_ratio,
            'date': datetime.now().strftime('%Y-%m-%d')
        }
    
    except Exception as e:
        print(f"⚠️ Market Cap error: {e}")
        return {
            'total_market_cap': 2.5e12,
            'total_volume': 100e9,
            'volume_to_market_ratio': 0.04,
            'date': datetime.now().strftime('%Y-%m-%d')
        }

def calculate_sentiment_features():
    """
    Colecta y calcula todas las features de sentimiento
    """
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  📊 MARKET SENTIMENT FEATURES COLLECTOR               ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    
    # 1. Fear & Greed histórico
    fg_data = get_fear_greed_historical()
    
    # 2. BTC Dominance
    dominance_data = get_btc_dominance()
    
    # 3. Market Cap trends
    market_cap_data = get_crypto_market_cap_trend()
    
    # Consolidar resultados
    result = {
        'collected_at': datetime.now(timezone.utc).isoformat(),
        'fear_greed': fg_data,
        'btc_dominance': dominance_data,
        'market_cap': market_cap_data,
        'features_summary': {
            'fg_current': fg_data[0]['value'] if fg_data else 50,
            'fg_7d_avg': sum(d['value'] for d in fg_data[:7]) / 7 if fg_data else 50,
            'fg_30d_avg': sum(d['value'] for d in fg_data[:30]) / 30 if fg_data else 50,
            'btc_dominance': dominance_data['btc_dominance'],
            'volume_to_market_ratio': market_cap_data['volume_to_market_ratio']
        }
    }
    
    # Guardar resultado
    with open(SENTIMENT_OUTPUT, 'w') as f:
        json.dump(result, f, indent=2)
    
    print()
    print(f"💾 Datos guardados: {SENTIMENT_OUTPUT}")
    print()
    print("📊 RESUMEN:")
    print(f"  • F&G Actual: {result['features_summary']['fg_current']}")
    print(f"  • F&G Promedio 7d: {result['features_summary']['fg_7d_avg']:.1f}")
    print(f"  • F&G Promedio 30d: {result['features_summary']['fg_30d_avg']:.1f}")
    print(f"  • BTC Dominance: {result['features_summary']['btc_dominance']:.2f}%")
    print(f"  • Volume/Market Ratio: {result['features_summary']['volume_to_market_ratio']:.4f}")
    
    return result

# ════════════════════════════════════════════════════════
# INTEGRACIÓN CON AUTO-RETRAIN
# ════════════════════════════════════════════════════════

def add_sentiment_to_training_data(df):
    """
    Agrega features de sentimiento al DataFrame de entrenamiento
    
    Args:
        df: DataFrame con datos históricos (debe tener columna 'date' o 'timestamp')
    
    Returns:
        DataFrame con columns adicionales de sentimiento
    """
    print("🔧 Agregando sentiment features al dataset...")
    
    # Cargar sentiment data
    if not os.path.exists(SENTIMENT_OUTPUT):
        print("⚠️ No hay sentiment data disponible, ejecutando collector...")
        calculate_sentiment_features()
    
    with open(SENTIMENT_OUTPUT, 'r') as f:
        sentiment_data = json.load(f)
    
    # Crear DataFrame de Fear & Greed
    fg_df = pd.DataFrame(sentiment_data['fear_greed'])
    fg_df['date'] = pd.to_datetime(fg_df['date'])
    fg_df = fg_df.rename(columns={'value': 'fear_greed'})
    
    # Determinar nombre de columna de fecha en el dataset
    date_col = None
    if 'date' in df.columns:
        date_col = 'date'
    elif 'timestamp' in df.columns:
        date_col = 'timestamp'
    else:
        raise KeyError("No se encontró columna 'date' ni 'timestamp' en el DataFrame")
    
    # Convertir columna de fecha a datetime
    df[date_col] = pd.to_datetime(df[date_col])
    
    # Extraer solo la fecha (YYYY-MM-DD) para match con F&G data
    df['date_only'] = df[date_col].dt.date
    fg_df['date_only'] = fg_df['date'].dt.date
    
    # Merge con datos históricos usando date_only
    df = df.merge(fg_df[['date_only', 'fear_greed']], on='date_only', how='left')
    
    # Eliminar columna temporal
    df = df.drop(columns=['date_only'])
    
    # Forward fill para días sin datos
    df['fear_greed'] = df['fear_greed'].ffill().bfill()
    
    # Agregar features derivadas
    df['fear_greed_7d_avg'] = df['fear_greed'].rolling(window=7).mean()
    df['fear_greed_30d_avg'] = df['fear_greed'].rolling(window=30).mean()
    df['fear_greed_change'] = df['fear_greed'].diff()
    
    # BTC Dominance (valor constante hasta que se actualice)
    df['btc_dominance'] = sentiment_data['features_summary']['btc_dominance']
    
    # Volume to Market Ratio
    df['volume_to_market_ratio'] = sentiment_data['features_summary']['volume_to_market_ratio']
    
    # Market regime classification basado en F&G
    def classify_regime(fg):
        if pd.isna(fg):
            return 'NEUTRAL'
        elif fg < 25:
            return 'EXTREME_FEAR'
        elif fg < 40:
            return 'FEAR'
        elif fg < 60:
            return 'NEUTRAL'
        elif fg < 75:
            return 'GREED'
        else:
            return 'EXTREME_GREED'
    
    df['market_regime'] = df['fear_greed'].apply(classify_regime)
    
    # One-hot encoding para market regime
    regime_dummies = pd.get_dummies(df['market_regime'], prefix='regime')
    df = pd.concat([df, regime_dummies], axis=1)
    
    print(f"   ✅ Features agregadas: fear_greed, fear_greed_7d_avg, fear_greed_30d_avg,")
    print(f"                          fear_greed_change, btc_dominance, volume_to_market_ratio,")
    print(f"                          market_regime (one-hot)")
    
    return df

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    calculate_sentiment_features()
    print()
    print("✨ Para usar en auto-retrain.py, importar:")
    print("   from ml.market-sentiment-features import add_sentiment_to_training_data")
    print("   df = add_sentiment_to_training_data(df)")
