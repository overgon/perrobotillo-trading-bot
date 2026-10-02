"""Fallback minimal de datos públicos para predict-tp.py."""
import time, json, os
from datetime import datetime


def _parse_iso(ts):
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def load_cached_klines(symbol, max_age_hours=1):
    base = os.path.join(os.path.expanduser('~'), '.openclaw/workspace/ml/cached_klines')
    path = os.path.join(base, f"{symbol}_1h.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        rows = []
        updated = data.get('updatedAt')
        ts = _parse_iso(updated) if updated else None
        if ts and (datetime.now() - ts).total_seconds() <= max_age_hours * 3600:
            rows = data.get('rows', [])
    except Exception:
        rows = []
    return rows


def save_cached_klines(symbol, rows):
    base = os.path.join(os.path.expanduser('~'), '.openclaw/workspace/ml/cached_klines')
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, f"{symbol}_1h.json")
    payload = {
        'symbol': symbol,
        'interval': '1h',
        'updatedAt': datetime.now().isoformat(),
        'rows': rows,
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, default=str)


def get_historical_klines(symbol, interval='1h', limit=100):
    rows = load_cached_klines(symbol)
    if not rows:
        return []
    if len(rows) > limit:
        rows = rows[-limit:]
    return rows


DEFAULT_SYMBOLS_BY_USDT = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'LINKUSDT', 'XRPUSDT', 'AVAXUSDT'
]


def get_symbols():
    return list(DEFAULT_SYMBOLS_BY_USDT)
