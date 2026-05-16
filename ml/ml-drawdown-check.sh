#!/bin/bash
# ════════════════════════════════════════════════════════
# 🛡️ ML Drawdown Risk Checker
# ════════════════════════════════════════════════════════
# Obtiene nivel de riesgo desde ML + reglas hard-coded
# Uso: ./ml-drawdown-check.sh [SYMBOL]
# Output: RISK_LEVEL|ACTION|POSITION_SIZE|MESSAGE
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
ML_DIR="${SCRIPT_DIR}"
RECOMMENDATIONS_FILE="${ML_DIR}/drawdown-recommendations.json"

SYMBOL="${1:-BTC}"

# ════════════════════════════════════════════════════════
# 🛑 REGLAS DE EMERGENCIA (Hard-coded overrides)
# ════════════════════════════════════════════════════════
# Estas reglas disparan HIGH_RISK sin importar el ML
# porque el modelo no tiene suficientes samples de rachas extremas

# Extraer features directamente del histórico
python3 << 'PYEOF'
import json
import os
from datetime import datetime, timedelta, timezone

WORKSPACE = "/home/overgon/.openclaw/workspace"
TRADE_HISTORY = os.path.join(WORKSPACE, "crypto-bots", "trade-history.json")

# Cargar histórico
if not os.path.exists(TRADE_HISTORY):
    print("LOW_RISK|NORMAL|40|Sin histórico")
    exit(0)

with open(TRADE_HISTORY, 'r') as f:
    data = json.load(f)

trades = data.get('trades', [])
if not trades:
    print("LOW_RISK|NORMAL|40|Sin trades")
    exit(0)

# Parsear timestamps y ordenar
df_trades = []
for t in trades:
    try:
        ts_str = t['timestamp']
        # Manejar diferentes formatos
        if '+' not in ts_str and 'Z' not in ts_str:
            ts = datetime.fromisoformat(ts_str)
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        df_trades.append({
            'timestamp': ts,
            'pnl': float(t.get('pnlUSDT', 0)),
            'symbol': t.get('symbol', '')
        })
    except Exception as e:
        print(f"# Error parsing {t.get('timestamp', 'unknown')}: {e}", file=__import__('sys').stderr)
        pass

df_trades.sort(key=lambda x: x['timestamp'])
now = datetime.now(timezone.utc)

# Trades últimas 24h
trades_24h = [t for t in df_trades if t['timestamp'] >= (now - timedelta(hours=24))]

if len(trades_24h) < 3:
    # Muy pocos trades recientes, usar ML normal
    print("USE_ML")
    exit(0)

# Calcular features críticas
losses_24h = [t for t in trades_24h if t['pnl'] < 0]
loss_rate_24h = len(losses_24h) / len(trades_24h) if trades_24h else 0

# Racha de pérdidas consecutivas (últimos 10 trades)
recent = df_trades[-10:] if len(df_trades) >= 10 else df_trades
loss_streak = 0
current_streak = 0
for t in reversed(recent):
    if t['pnl'] < 0:
        current_streak += 1
        loss_streak = max(loss_streak, current_streak)
    else:
        current_streak = 0

# Drawdown 24h (pérdida acumulada)
drawdown_24h = abs(sum(t['pnl'] for t in losses_24h))

# ════════════════════════════════════════════════════════
# 🛑 UMBRALES DE EMERGENCIA
# ════════════════════════════════════════════════════════

# HIGH_RISK si:
# - loss_rate_24h > 80% Y más de 5 trades
# - loss_streak > 5
# - drawdown_24h > $50

if len(trades_24h) >= 5 and loss_rate_24h > 0.8:
    print(f"HIGH_RISK|PAUSE|0|Racha crítica: {int(loss_rate_24h*100)}% pérdidas en 24h ({len(trades_24h)} trades)")
    exit(0)

if loss_streak > 5:
    print(f"HIGH_RISK|PAUSE|0|Racha de {loss_streak} pérdidas consecutivas")
    exit(0)

if drawdown_24h > 50:
    print(f"HIGH_RISK|PAUSE|0|Drawdown 24h: ${drawdown_24h:.2f} (threshold $50)")
    exit(0)

# MEDIUM_RISK si:
# - loss_rate_24h > 50%
# - drawdown_24h > $25

if len(trades_24h) >= 3 and loss_rate_24h > 0.5:
    print(f"MEDIUM_RISK|REDUCE|20|Alta tasa de pérdidas: {int(loss_rate_24h*100)}% en 24h")
    exit(0)

if drawdown_24h > 25:
    print(f"MEDIUM_RISK|REDUCE|20|Drawdown 24h: ${drawdown_24h:.2f} (threshold $25)")
    exit(0)

# Si no dispara ninguna regla, usar ML normal
print("USE_ML")
PYEOF

ML_RESULT=$?

# Si el script Python imprimió una regla hard-coded, usarla
if [ $ML_RESULT -eq 0 ]; then
    # Ya se imprimió el resultado, salir
    exit 0
fi

# ════════════════════════════════════════════════════════
# 🧠 ML NORMAL (si no disparó ninguna regla de emergencia)
# ════════════════════════════════════════════════════════
# Usar modelo histórico (2.0.0) entrenado con 6 años de data

MODEL_FILE="${ML_DIR}/drawdown-predictor-historical.pkl"
METADATA_FILE="${ML_DIR}/drawdown-historical-metadata.json"

if [ -f "$MODEL_FILE" ]; then
    # Ejecutar predictor histórico
    python3 << PYEOF
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import joblib

MODEL_FILE = "$MODEL_FILE"
METADATA_FILE = "$METADATA_FILE"
WORKSPACE = "/home/overgon/.openclaw/workspace"
TRADE_HISTORY = os.path.join(WORKSPACE, "crypto-bots", "trade-history.json")

import os

# Cargar modelo
model = joblib.load(MODEL_FILE)
with open(METADATA_FILE, 'r') as f:
    metadata = json.load(f)

feature_cols = metadata['feature_cols']

# Cargar histórico real para features
if os.path.exists(TRADE_HISTORY):
    with open(TRADE_HISTORY, 'r') as f:
        data = json.load(f)
    trades = data.get('trades', [])
else:
    trades = []

# Calcular features actuales (mismo código que antes)
from datetime import timedelta

df_trades = []
for t in trades:
    try:
        ts_str = t['timestamp']
        if '+' not in ts_str and 'Z' not in ts_str:
            ts = datetime.fromisoformat(ts_str)
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        df_trades.append({
            'timestamp': ts,
            'pnl': float(t.get('pnlUSDT', 0)),
            'symbol': t.get('symbol', '')
        })
    except:
        pass

df_trades.sort(key=lambda x: x['timestamp'])
now = datetime.now(timezone.utc)

# Features 24h
trades_24h = [t for t in df_trades if t['timestamp'] >= (now - timedelta(hours=24))]
losses_24h = [t for t in trades_24h if t['pnl'] < 0]
loss_rate_24h = len(losses_24h) / len(trades_24h) if trades_24h else 0
drawdown_24h = abs(sum(t['pnl'] for t in losses_24h))

# Features 7d
trades_7d = [t for t in df_trades if t['timestamp'] >= (now - timedelta(days=7))]
losses_7d = [t for t in trades_7d if t['pnl'] < 0]
loss_rate_7d = len(losses_7d) / len(trades_7d) if trades_7d else 0
drawdown_7d = abs(sum(t['pnl'] for t in losses_7d))

# Loss streak
recent = df_trades[-10:] if len(df_trades) >= 10 else df_trades
loss_streak = 0
current_streak = 0
for t in reversed(recent):
    if t['pnl'] < 0:
        current_streak += 1
        loss_streak = max(loss_streak, current_streak)
    else:
        current_streak = 0

# avg_loss_size
avg_loss_size = abs(np.mean([t['pnl'] for t in losses_24h])) if losses_24h else 0
loss_volatility = abs(np.std([t['pnl'] for t in losses_7d])) if len(losses_7d) > 1 else 0

# Hora
hour = datetime.now().hour
hour_sin = np.sin(2 * np.pi * hour / 24)
hour_cos = np.cos(2 * np.pi * hour / 24)

# Symbol
symbol = '$SYMBOL'

# Features dict
features = {
    'loss_streak': loss_streak,
    'loss_rate_24h': loss_rate_24h,
    'loss_rate_7d': loss_rate_7d,
    'drawdown_24h': drawdown_24h,
    'drawdown_7d': drawdown_7d,
    'avg_loss_size': avg_loss_size,
    'loss_volatility': loss_volatility,
    'total_trades_24h': len(trades_24h),
    'total_trades_7d': len(trades_7d),
    'hour_sin': hour_sin,
    'hour_cos': hour_cos,
}

# One-hot encoding
for coin in ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']:
    features[f'coin_{coin}'] = 1 if coin == symbol else 0

# Predecir
df_features = pd.DataFrame([features])
for col in feature_cols:
    if col not in df_features.columns:
        df_features[col] = 0

X = df_features[feature_cols]
pred = model.predict(X)[0]
probs = model.predict_proba(X)[0]

# Mapear resultado
risk_map = {'HIGH_RISK': 'PAUSE', 'MEDIUM_RISK': 'REDUCE', 'LOW_RISK': 'NORMAL'}
pos_map = {'HIGH_RISK': 0, 'MEDIUM_RISK': 20, 'LOW_RISK': 40}
msg_map = {
    'HIGH_RISK': 'Riesgo alto - ML histórico recomienda pausar',
    'MEDIUM_RISK': 'Riesgo medio - ML histórico recomienda reducir',
    'LOW_RISK': 'Riesgo bajo - ML histórico permite operar'
}

action = risk_map.get(pred, 'NORMAL')
pos_size = pos_map.get(pred, 40)
msg = msg_map.get(pred, 'Riesgo desconocido')
confidence = max(probs)

print(f"{pred}|{action}|{pos_size}|{msg} (confianza: {confidence:.1%})")
PYEOF
else
    # Fallback al modelo original si no existe el histórico
    python3 "${ML_DIR}/drawdown-predictor.py" --predict "$SYMBOL" > /dev/null 2>&1
    
    if [ -f "$RECOMMENDATIONS_FILE" ]; then
        python3 << PYEOF
import json
with open('$RECOMMENDATIONS_FILE', 'r') as f:
    data = json.load(f)
pred = data['predictions'].get('$SYMBOL', {})
risk = pred.get('risk_level', 'LOW_RISK')
action = pred.get('action', 'NORMAL')
pos_size = pred.get('position_size', 40)
msg = pred.get('message', 'Riesgo bajo')
print(f"{risk}|{action}|{pos_size}|{msg}")
PYEOF
    else
        echo "LOW_RISK|NORMAL|40|Riesgo bajo"
    fi
fi
