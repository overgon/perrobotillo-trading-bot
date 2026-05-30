#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🧠 ML AUTO-RETRAIN - Weekly Model Retraining
# ════════════════════════════════════════════════════════
# Re-entrena el modelo ML validator cada domingo a las 3 AM
# usando:
# - Trades históricos del trade-history.json
# - Backtesting results
# - Nuevos trades de la semana
# 
# Author: Perrobotillo 🐕
# Version: 1.0.0
# ════════════════════════════════════════════════════════

import json
import os
import sys
from datetime import datetime, timedelta
import requests
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import talib

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
TRADE_HISTORY = f"{WORKSPACE}/crypto-bots/trade-history.json"
MODEL_FILE = f"{WORKSPACE}/ml/ml-validator-model.pkl"
MODEL_INFO = f"{WORKSPACE}/ml/ml-validator-model.json"
LOG_FILE = f"{WORKSPACE}/ml/ml-retrain.log"

def log(message):
    """Log message to file and stdout"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    
    with open(LOG_FILE, 'a') as f:
        f.write(log_msg + "\n")

def load_trade_history():
    """Cargar historial de trades"""
    if not os.path.exists(TRADE_HISTORY):
        log("❌ No trade history found")
        return []
    
    with open(TRADE_HISTORY, 'r') as f:
        data = json.load(f)
    
    trades = data.get('trades', [])
    log(f"📊 Cargados {len(trades)} trades históricos")
    
    return trades

def get_klines(symbol, interval='1h', limit=100):
    """Obtener velas de Binance"""
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit={limit}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'opens': np.array([float(d[1]) for d in data]),
                'highs': np.array([float(d[2]) for d in data]),
                'lows': np.array([float(d[3]) for d in data]),
                'closes': np.array([float(d[4]) for d in data]),
                'volumes': np.array([float(d[5]) for d in data])
            }
    except Exception as e:
        log(f"⚠️ Error getting klines for {symbol}: {e}")
    
    return None

def extract_features(symbol, timestamp=None):
    """Extraer features técnicos para un símbolo"""
    data = get_klines(symbol, interval='1h', limit=100)
    if not data:
        return None
    
    closes = data['closes']
    highs = data['highs']
    lows = data['lows']
    volumes = data['volumes']
    
    # RSI
    rsi = talib.RSI(closes, timeperiod=14)[-1]
    
    # MACD
    macd, signal, hist = talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
    macd_value = macd[-1]
    signal_value = signal[-1]
    macd_hist = hist[-1]
    
    # Volume ratio
    avg_volume = np.mean(volumes[:-1])
    current_volume = volumes[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
    
    # Trend
    sma_20 = talib.SMA(closes, timeperiod=20)[-1]
    sma_50 = talib.SMA(closes, timeperiod=50)[-1]
    trend_bullish = 1 if sma_20 > sma_50 else 0
    
    # Bollinger Bands
    upper, middle, lower = talib.BBANDS(closes, timeperiod=20)
    bb_position = (closes[-1] - lower[-1]) / (upper[-1] - lower[-1]) if (upper[-1] - lower[-1]) > 0 else 0.5
    
    # Volatility
    volatility = (highs[-1] - lows[-1]) / closes[-1] * 100
    
    return [
        rsi,
        macd_value,
        signal_value,
        macd_hist,
        volume_ratio,
        trend_bullish,
        bb_position,
        volatility
    ]

def prepare_training_data(trades):
    """Preparar datos para entrenamiento"""
    X = []
    y = []  # 1 = win, 0 = loss
    
    log("🔄 Preparando datos de entrenamiento...")
    
    for trade in trades:
        symbol = trade.get('symbol', '')
        pnl = trade.get('pnlUSDT', 0)
        
        # Skip trades sin P&L
        if pnl == 0 or pnl is None:
            continue
        
        # Extraer features (usando datos actuales como aproximación)
        features = extract_features(symbol)
        if features is None:
            continue
        
        X.append(features)
        
        # Label: 1 si fue win, 0 si fue loss
        y.append(1 if pnl > 0 else 0)
    
    log(f"✅ {len(X)} muestras preparadas")
    
    return np.array(X), np.array(y)

def train_model():
    """Entrenar nuevo modelo"""
    log("╔═══════════════════════════════════════════════════════╗")
    log("║  🧠 ML AUTO-RETRAIN - Starting Training               ║")
    log("╚═══════════════════════════════════════════════════════╝")
    
    # Cargar trades
    trades = load_trade_history()
    if len(trades) < 10:
        log("❌ Insuficientes trades para entrenar (mínimo 10)")
        return False
    
    # Preparar datos
    X, y = prepare_training_data(trades)
    
    if len(X) < 10:
        log("❌ Insuficientes features extraídas")
        return False
    
    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Entrenar Random Forest
    log("🎯 Entrenando Random Forest...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluar
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    log(f"✅ Modelo entrenado")
    log(f"📊 Accuracy: {accuracy * 100:.2f}%")
    log(f"📈 Samples: {len(X)} (train: {len(X_train)}, test: {len(X_test)})")
    
    # Guardar modelo
    import joblib
    joblib.dump(model, MODEL_FILE)
    log(f"💾 Modelo guardado en {MODEL_FILE}")
    
    # Guardar info del modelo
    model_info = {
        'type': 'RandomForest',
        'n_estimators': 100,
        'max_depth': 10,
        'accuracy': accuracy,
        'samples': len(X),
        'features': [
            'rsi', 'macd', 'signal', 'macd_hist',
            'volume_ratio', 'trend_bullish', 'bb_position', 'volatility'
        ],
        'trained_at': datetime.now().isoformat(),
        'trades_used': len(trades),
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'win_rate': sum(y) / len(y) * 100 if len(y) > 0 else 0
    }
    
    with open(MODEL_INFO, 'w') as f:
        json.dump(model_info, f, indent=2)
    
    log(f"📝 Info del modelo guardada")
    
    # Generar reporte para Telegram
    generate_telegram_report(model_info, y)
    
    log("")
    log("╔═══════════════════════════════════════════════════════╗")
    log("║  ✅ Training Complete - Model Ready                   ║")
    log("╚═══════════════════════════════════════════════════════╝")
    
    return True

def generate_telegram_report(model_info, y_labels):
    """Generar reporte detallado para enviar por Telegram"""
    
    # Calcular métricas adicionales
    total_trades = model_info['trades_used']
    wins = sum(y_labels)
    losses = len(y_labels) - wins
    win_rate = wins / len(y_labels) * 100 if len(y_labels) > 0 else 0
    
    # Leer modelo anterior si existe
    old_accuracy = 0
    if os.path.exists(MODEL_INFO):
        try:
            with open(MODEL_INFO, 'r') as f:
                old_info = json.load(f)
                old_accuracy = old_info.get('accuracy', 0)
        except:
            pass
    
    accuracy_change = (model_info['accuracy'] - old_accuracy) * 100
    accuracy_emoji = "📈" if accuracy_change > 0 else "📉" if accuracy_change < 0 else "➡️"
    
    report = f"""🧠 *ML Auto-Retrain Reporte*

✅ Re-entrenamiento completado
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 *Métricas del Modelo:*
{accuracy_emoji} Accuracy: {model_info['accuracy']*100:.1f}% ({'+' if accuracy_change > 0 else ''}{accuracy_change:.1f}%)
📈 Train samples: {model_info['train_samples']}
🧪 Test samples: {model_info['test_samples']}

💰 *Trades Históricos:*
Total: {total_trades}
Wins: {wins} ✅
Losses: {losses} ❌
Win Rate: {win_rate:.1f}%

🎯 *Features Usados:*
• RSI (14 periodos)
• MACD (12,26,9)
• Volume Ratio
• Trend (SMA 20/50)
• Bollinger Bands
• Volatility

⚙️ *Configuración:*
Modelo: Random Forest
Estimadores: {model_info['n_estimators']}
Max Depth: {model_info['max_depth']}

📁 *Archivos:*
Modelo: ml-validator-model.pkl
Info: ml-validator-model.json
Logs: ml-retrain.log

_Próximo re-entrenamiento: Domingo 3:00 AM_"""
    
    # Enviar a Telegram
    TELEGRAM_ENV = f"{WORKSPACE}/secrets/telegram.env"
    if os.path.exists(TELEGRAM_ENV):
        try:
            with open(TELEGRAM_ENV, 'r') as f:
                for line in f:
                    if line.startswith('TELEGRAM_BOT_TOKEN='):
                        tg_token = line.strip().split('=')[1]
                    elif line.startswith('TELEGRAM_CHAT_ID='):
                        tg_chat_id = line.strip().split('=')[1]
            
            import urllib.request
            import urllib.parse
            
            url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            data = urllib.parse.urlencode({
                'chat_id': tg_chat_id,
                'text': report,
                'parse_mode': 'Markdown'
            }).encode()
            
            urllib.request.urlopen(url, data, timeout=10)
            log("📱 Reporte enviado a Telegram")
        except Exception as e:
            log(f"⚠️ Error enviando Telegram: {e}")

if __name__ == "__main__":
    success = train_model()
    sys.exit(0 if success else 1)
