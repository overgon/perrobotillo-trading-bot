#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🧠 ML VALIDATOR - Pre-Trade Validation System
# ════════════════════════════════════════════════════════
# Valida si es buen momento para abrir trades usando:
# - Reglas técnicas (RSI, MACD, Volume, Trend)
# - Market Regime Detection
# - Risk Assessment
# 
# Author: Perrobotillo 🐕
# Version: 1.0.0
# ════════════════════════════════════════════════════════

import json
import os
import sys
import requests
from datetime import datetime, timedelta
import talib
import numpy as np

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
CONFIG_FILE = f"{WORKSPACE}/ml/ml-validator-config.json"
MODEL_FILE = f"{WORKSPACE}/ml/ml-validator-model.json"
HISTORY_FILE = f"{WORKSPACE}/crypto-bots/trade-history.json"

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "enabled": True,
    "min_confidence": 50,  # Mínimo % para aprobar trade
    "reduce_position_below": 70,  # Reducir posición si confianza < 70%
    "position_reduction_percent": 50,  # Reducir a 50% si confianza baja
    
    # Thresholds por tipo de trade
    "thresholds": {
        "SCALP": {
            "min_confidence": 60,
            "max_risk": "HIGH"
        },
        "NORMAL": {
            "min_confidence": 65,
            "max_risk": "MEDIUM"
        },
        "SWING": {
            "min_confidence": 75,
            "max_risk": "LOW"
        }
    },
    
    # Indicadores técnicos
    "indicators": {
        "rsi": {
            "overbought": 70,
            "oversold": 30,
            "neutral_low": 40,
            "neutral_high": 60
        },
        "macd": {
            "bullish_threshold": 0,
            "bearish_threshold": 0
        },
        "volume": {
            "min_volume_ratio": 1.2  # Volume debe ser 20% arriba del promedio
        }
    }
}

# ════════════════════════════════════════════════════════
# CARGAR CONFIGURACIÓN
# ════════════════════════════════════════════════════════

def load_config():
    """Cargar configuración o crear defaults"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG

# ════════════════════════════════════════════════════════
# OBTENER DATOS DE BINANCE
# ════════════════════════════════════════════════════════

def get_klines(symbol, interval='1h', limit=100):
    """Obtener velas de Binance"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit={limit}"
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        return {
            'timestamps': [int(d[0]) for d in data],
            'opens': np.array([float(d[1]) for d in data]),
            'highs': np.array([float(d[2]) for d in data]),
            'lows': np.array([float(d[3]) for d in data]),
            'closes': np.array([float(d[4]) for d in data]),
            'volumes': np.array([float(d[5]) for d in data])
        }
    return None

def get_market_regime(symbol):
    """Detectar market regime (BULL/BEAR/LATERAL/LATERAL_BULL)"""
    data = get_klines(symbol, interval='4h', limit=50)
    if not data:
        return "UNKNOWN", 0
    
    closes = data['closes']
    
    # Calcular trend
    sma_20 = talib.SMA(closes, timeperiod=20)[-1]
    sma_50 = talib.SMA(closes, timeperiod=50)[-1]
    current_price = closes[-1]
    
    # Determinar regime
    if current_price > sma_20 > sma_50:
        return "BULL", 0.8
    elif current_price < sma_20 < sma_50:
        return "BEAR", 0.8
    elif current_price > sma_20 and sma_20 <= sma_50:
        return "LATERAL_BULL", 0.7
    else:
        return "LATERAL", 0.6

# ════════════════════════════════════════════════════════
# CALCULAR INDICADORES TÉCNICOS
# ════════════════════════════════════════════════════════

def calculate_indicators(symbol):
    """Calcular todos los indicadores técnicos"""
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
    
    # Volume promedio
    avg_volume = np.mean(volumes[:-1])
    current_volume = volumes[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
    
    # Trend (SMA crossover)
    sma_20 = talib.SMA(closes, timeperiod=20)[-1]
    sma_50 = talib.SMA(closes, timeperiod=50)[-1]
    trend_bullish = sma_20 > sma_50
    
    # Bollinger Bands
    upper, middle, lower = talib.BBANDS(closes, timeperiod=20)
    bb_position = (closes[-1] - lower[-1]) / (upper[-1] - lower[-1]) if (upper[-1] - lower[-1]) > 0 else 0.5
    
    return {
        'rsi': rsi,
        'macd': macd_value,
        'macd_signal': signal_value,
        'macd_hist': macd_hist,
        'volume_ratio': volume_ratio,
        'trend_bullish': trend_bullish,
        'bb_position': bb_position,
        'current_price': closes[-1],
        'sma_20': sma_20,
        'sma_50': sma_50
    }

# ════════════════════════════════════════════════════════
# VALIDADOR PRINCIPAL
# ════════════════════════════════════════════════════════

def validate_trade(symbol, trade_type="NORMAL", direction="LONG"):
    """
    Validar si es buen momento para abrir un trade
    
    Returns: dict con:
        - approved: bool
        - confidence: int (0-100)
        - direction: str (LONG/SHORT/SKIP)
        - type: str (SCALP/NORMAL/SWING)
        - position_size_percent: int
        - risk_level: str (LOW/MED/HIGH)
        - market_regime: str
        - reason: str
    """
    
    config = load_config()
    
    if not config.get('enabled', True):
        return {
            'approved': True,
            'confidence': 100,
            'reason': 'ML Validator disabled'
        }
    
    # Calcular indicadores
    indicators = calculate_indicators(symbol)
    if not indicators:
        return {
            'approved': False,
            'confidence': 0,
            'reason': 'No data available'
        }
    
    # Detectar market regime
    market_regime, regime_confidence = get_market_regime(symbol)
    
    # ════════════════════════════════════════════════════
    # SISTEMA DE SCORING
    # ════════════════════════════════════════════════════
    
    score = 0
    max_score = 100
    reasons = []
    
    # 1. RSI Scoring (25 puntos)
    rsi = indicators['rsi']
    rsi_config = config['indicators']['rsi']
    
    if direction == "LONG":
        if rsi < rsi_config['oversold']:
            score += 25  # Muy oversold - excelente para LONG
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi < rsi_config['neutral_low']:
            score += 20  # Bueno para LONG
            reasons.append(f"RSI bajo ({rsi:.1f})")
        elif rsi < rsi_config['neutral_high']:
            score += 10  # Neutral
            reasons.append(f"RSI neutral ({rsi:.1f})")
        elif rsi > rsi_config['overbought']:
            score -= 10  # Overbought - malo para LONG
            reasons.append(f"RSI overbought ({rsi:.1f})")
    else:  # SHORT
        if rsi > rsi_config['overbought']:
            score += 25
            reasons.append(f"RSI overbought ({rsi:.1f})")
        elif rsi > rsi_config['neutral_high']:
            score += 20
            reasons.append(f"RSI alto ({rsi:.1f})")
    
    # 2. MACD Scoring (25 puntos)
    macd_hist = indicators['macd_hist']
    if direction == "LONG":
        if macd_hist > 0:
            score += 25
            reasons.append("MACD bullish")
        else:
            score -= 10
            reasons.append("MACD bearish")
    else:  # SHORT
        if macd_hist < 0:
            score += 25
            reasons.append("MACD bearish")
        else:
            score -= 10
            reasons.append("MACD bullish")
    
    # 3. Trend Scoring (20 puntos)
    trend_bullish = indicators['trend_bullish']
    if direction == "LONG" and trend_bullish:
        score += 20
        reasons.append("Trend bullish")
    elif direction == "SHORT" and not trend_bullish:
        score += 20
        reasons.append("Trend bearish")
    else:
        score -= 5
        reasons.append("Trend contrario")
    
    # 4. Volume Scoring (15 puntos)
    volume_ratio = indicators['volume_ratio']
    min_volume = config['indicators']['volume']['min_volume_ratio']
    
    if volume_ratio >= min_volume:
        score += 15
        reasons.append(f"Volume alto ({volume_ratio:.2f}x)")
    elif volume_ratio >= 1.0:
        score += 8
        reasons.append(f"Volume normal ({volume_ratio:.2f}x)")
    else:
        score -= 5
        reasons.append(f"Volume bajo ({volume_ratio:.2f}x)")
    
    # 5. Bollinger Bands Scoring (15 puntos)
    bb_position = indicators['bb_position']
    if direction == "LONG":
        if bb_position < 0.2:
            score += 15  # Precio cerca de banda inferior
            reasons.append("BB: precio en banda inferior")
        elif bb_position < 0.5:
            score += 8
            reasons.append("BB: precio en mitad inferior")
    else:  # SHORT
        if bb_position > 0.8:
            score += 15  # Precio cerca de banda superior
            reasons.append("BB: precio en banda superior")
        elif bb_position > 0.5:
            score += 8
            reasons.append("BB: precio en mitad superior")
    
    # ════════════════════════════════════════════════════
    # CALCULAR CONFIANZA FINAL
    # ════════════════════════════════════════════════════
    
    confidence = max(0, min(100, score))
    
    # Ajustar según market regime
    if market_regime == "BULL" and direction == "LONG":
        confidence = min(100, confidence + 5)
    elif market_regime == "BEAR" and direction == "SHORT":
        confidence = min(100, confidence + 5)
    elif market_regime == "LATERAL_BULL" and direction == "LONG":
        # Regla 2/3 filtros: tender + RSI/Volumen medios-altos en lateral alcista
        trend_ok = indicators.get('trend_bullish', False)
        rsi_ok = 45 <= rsi <= 75
        vol_ok = volume_ratio >= 1.0
        strong_filters = sum([trend_ok, rsi_ok, vol_ok])
        if strong_filters >= 2:
            confidence = min(100, confidence + 10)
            reasons.append("LATERAL_BULL override: 2/3 filtros OK")
        else:
            confidence = max(0, confidence - 5)
            reasons.append("LATERAL_BULL: filtros insuficientes")
    elif market_regime == "LATERAL":
        confidence = max(0, confidence - 5)  # Lateral es más riesgoso
    
    # ════════════════════════════════════════════════════
    # DETERMINAR APROBACIÓN Y POSITION SIZE
    # ════════════════════════════════════════════════════
    
    threshold_config = config['thresholds'].get(trade_type, config['thresholds']['NORMAL'])
    min_conf = threshold_config.get('min_confidence', config['min_confidence'])
    
    approved = confidence >= min_conf
    
    # Position size basado en confianza
    position_percent = 40  # Default 40%
    if confidence < config['reduce_position_below']:
        position_percent = int(40 * (config['position_reduction_percent'] / 100))
        reasons.append(f"Posición reducida a {position_percent}%")
    
    # Risk level
    if confidence >= 80:
        risk_level = "LOW"
    elif confidence >= 60:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"
    
    # ════════════════════════════════════════════════════
    # RESULTADO FINAL
    # ════════════════════════════════════════════════════
    
    result = {
        'approved': approved,
        'confidence': confidence,
        'direction': direction if approved else "SKIP",
        'type': trade_type,
        'position_size_percent': position_percent if approved else 0,
        'risk_level': risk_level,
        'market_regime': market_regime,
        'reason': "; ".join(reasons[:3]),  # Top 3 razones
        'indicators': indicators,
        'timestamp': datetime.now().isoformat()
    }
    
    # Log resultado
    log_validation(symbol, result)
    
    return result

def log_validation(symbol, result):
    """Guardar validación en log"""
    log_file = f"{WORKSPACE}/ml/ml-validator-log.json"
    
    logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
        except:
            pass
    
    logs.append({
        'symbol': symbol,
        'result': result,
        'timestamp': datetime.now().isoformat()
    })
    
    # Mantener últimos 100 logs
    logs = logs[-100:]
    
    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=2, default=str)

# ════════════════════════════════════════════════════════
# MAIN (Testing)
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python ml-validator.py <SYMBOL> [TYPE] [DIRECTION]")
        print("Ejemplo: python ml-validator.py BTC NORMAL LONG")
        sys.exit(1)
    
    symbol = sys.argv[1]
    trade_type = sys.argv[2] if len(sys.argv) > 2 else "NORMAL"
    direction = sys.argv[3] if len(sys.argv) > 3 else "LONG"
    
    print(f"🧠 ML Validator - {symbol} {trade_type} {direction}")
    print("=" * 50)
    
    result = validate_trade(symbol, trade_type, direction)
    
    print(f"Aprobado: {'✅ SÍ' if result['approved'] else '❌ NO'}")
    print(f"Confianza: {result['confidence']}%")
    print(f"Dirección: {result['direction']}")
    print(f"Tamaño posición: {result['position_size_percent']}%")
    print(f"Nivel riesgo: {result['risk_level']}")
    print(f"Market regime: {result['market_regime']}")
    print(f"Razones: {result['reason']}")
    print("=" * 50)
