#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
# JESSE ML — Entrenamiento del ML de Perrobotillo (gather + train)
#
# Flujo:
#   1. GATHER: corre el backtest de la estrategia `perrobotillo` en modo
#      gather (JESSE_ML_MODE=gather) y recoge features + labels por vela.
#   2. TRAIN: entrena un clasificador sklearn (binario: price_direction) con
#      split temporal y validación, y guarda modelo + scaler + importancia.
#
# Uso (raíz del proyecto, venv-jesse):
#   venv-jesse/bin/python3 research/jesse_ml_train.py --coins BTC --start 2025-11-01 --end 2026-11-01
#   venv-jesse/bin/python3 research/jesse_ml_train.py --coins ALL --start 2024-11-01 --end 2026-11-01
#
# Salida: strategies/perrobotillo/ml_data/{COIN}_data.csv, model_{COIN}/, metrics_{COIN}.json
# ═══════════════════════════════════════════════════════════════════════════

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault('JESSE_ML_MODE', 'gather')
sys.path.insert(0, '/home')

import importlib  # noqa: E402

import numpy as np  # noqa: E402

_jb = importlib.import_module('jesse.research.backtest')
_ml = importlib.import_module('jesse.research.ml')
from jesse.research import get_candles  # noqa: E402
from jesse.research.ml import train_model  # noqa: E402

EXCHANGE = 'Binance Spot'
STRATEGY = 'perrobotillo'
ML_DIR = Path('strategies/perrobotillo/ml_data')
DEFAULT_COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC']

# Jesse 3.6.1: gather_ml_data() lee router.routes[0].strategy._ml_data_points
# DESPUÉS de que _isolated_backtest haya hecho reset_config()+router._reset(),
# así que siempre obtiene una lista vacía. Capturamos los puntos justo antes del
# reset y los usamos en su lugar.
_CAPTURED = {}


def install_ml_capture() -> None:
    if getattr(_jb, '_perrobotillo_capture_installed', False):
        return
    original_reset = _jb._reset_research_runtime_state

    def capturing_reset():
        try:
            if _jb.router.routes:
                strategy = _jb.router.routes[0].strategy
                points = getattr(strategy, '_ml_data_points', None)
                if points:
                    _CAPTURED['data_points'] = [dict(p) for p in points]
        except Exception:  # noqa: BLE001
            pass
        original_reset()

    _jb._reset_research_runtime_state = capturing_reset
    _jb._perrobotillo_capture_installed = True


def disable_expensive_reports() -> None:
    """Desactiva los reportes que re-entrenan modelos por cada feature.

    - `_compute_feature_importance`: RFE con SVC lineal (51 fits) + CV con SVC RBF.
    - `_compute_feature_impact`: re-entrena el estimador por cada feature.
    No cambian el modelo ni las métricas; solo el detalle de importancia por feature.
    """
    _ml._compute_feature_importance = lambda *args, **kwargs: {}
    _ml._compute_feature_impact = lambda *args, **kwargs: {}


def make_estimator(kind: str):
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    if kind == 'rf':
        return RandomForestClassifier(n_estimators=400, max_depth=8, class_weight='balanced',
                                      random_state=42, n_jobs=-1)
    if kind == 'gbm':
        return GradientBoostingClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                                          random_state=42)
    if kind == 'lr':
        return LogisticRegression(max_iter=2000, class_weight='balanced')
    raise ValueError(f"modelo desconocido: {kind}")


def build_config(warmup: int) -> dict:
    return {
        'starting_balance': 10_000.0,
        'fee': 0.001,
        'type': 'spot',
        'simulation_model': 'spot',
        'annualization': 365,
        'exchange': EXCHANGE,
        'warm_up_candles': warmup,
    }


def sanitize_data_points(data_points: list) -> list:
    """Reemplaza NaN/inf/None de las features por la mediana de cada columna.

    train_model() usa SVC para la importancia de features y no acepta NaN.
    """
    import math

    names = sorted({k for p in data_points for k in p.get('features', {})})
    median = {}
    for name in names:
        vals = []
        for p in data_points:
            try:
                v = float(p['features'].get(name, 0.0))
            except (TypeError, ValueError):
                continue
            if math.isfinite(v):
                vals.append(v)
        median[name] = float(np.median(vals)) if vals else 0.0

    clean = []
    for p in data_points:
        feats = {}
        for name in names:
            try:
                v = float(p['features'].get(name, 0.0))
            except (TypeError, ValueError):
                v = median[name]
            feats[name] = v if math.isfinite(v) else median[name]
        clean.append({'time': p['time'], 'features': feats, 'label': p['label']})
    return clean


def fetch_candles(symbol: str, start_ms: int, end_ms: int) -> np.ndarray:
    c = get_candles(EXCHANGE, symbol, '1m', start_ms, end_ms)
    if isinstance(c, tuple):
        c = c[1]
    if c is None or len(c) == 0:
        raise RuntimeError(f"sin velas para {symbol} en el rango pedido")
    return c


def train_coin(coin: str, start_ms: int, end_ms: int, warmup: int, test_ratio: float,
               model_kind: str, verbose: bool) -> dict:
    symbol = f'{coin}-USDT'
    print(f"\n{'=' * 60}\n🤖 {symbol}\n{'=' * 60}")

    # El backtest en 1h consume velas 1m; el warmup se resta del inicio.
    warm_ms = warmup * 3_600_000
    candles_main = fetch_candles(symbol, start_ms - warm_ms, end_ms)
    candles_dict = {f'{EXCHANGE}-{symbol}': {'exchange': EXCHANGE, 'symbol': symbol, 'candles': candles_main}}

    # Data route: BTC alimenta la detección de mercado de la estrategia.
    if symbol != 'BTC-USDT':
        btc = fetch_candles('BTC-USDT', start_ms - warm_ms, end_ms)
        candles_dict[f'{EXCHANGE}-BTC-USDT'] = {'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'candles': btc}

    routes = [{'exchange': EXCHANGE, 'symbol': symbol, 'timeframe': '1h',
               'strategy': STRATEGY, 'stake': 1000.0}]
    data_routes = [{'exchange': EXCHANGE, 'symbol': 'BTC-USDT', 'timeframe': '1h'}]

    csv_path = ML_DIR / f'{coin}_data.csv'
    install_ml_capture()
    _CAPTURED.pop('data_points', None)

    bt = _jb.backtest(build_config(warmup), routes, data_routes, candles_dict, fast_mode=True)
    data_points = [p for p in _CAPTURED.get('data_points', []) if p.get('label') is not None]
    if not data_points:
        raise RuntimeError('gather no produjo datos (¿estrategia en modo trade?)')
    data_points = sanitize_data_points(data_points)
    _ml._write_csv(data_points, str(csv_path))

    out_dir = ML_DIR / f'model_{coin}'
    out_dir.mkdir(parents=True, exist_ok=True)
    result = train_model(data_points, make_estimator(model_kind), task='binary',
                         test_ratio=test_ratio, save_to=str(out_dir), verbose=verbose, name=coin)

    metrics = {
        'coin': coin,
        'model': model_kind,
        'label': 'price_direction',
        'n_samples': len(data_points),
        'n_features': len(result.get('feature_names', [])),
        'train_test': result.get('train_test_info'),
        'metrics': result.get('metrics'),
        'class_weights': result.get('class_weights'),
        'backtest_metrics': bt.get('metrics'),
        'created_at': datetime.now().isoformat(),
    }
    (ML_DIR / f'metrics_{coin}.json').write_text(json.dumps(metrics, indent=2, default=float))
    print(f"  💾 {csv_path} | modelo en {out_dir} | metrics_{coin}.json")
    return metrics


def main() -> None:
    ap = argparse.ArgumentParser(description='Entrena el ML de Perrobotillo con Jesse')
    ap.add_argument('--coins', default='ALL', help='BTC,ETH,... o ALL')
    ap.add_argument('--start', required=True, help='YYYY-MM-DD')
    ap.add_argument('--end', default=datetime.now().strftime('%Y-%m-%d'), help='YYYY-MM-DD')
    ap.add_argument('--warmup', type=int, default=200, help='velas 1h de calentamiento')
    ap.add_argument('--test-ratio', type=float, default=0.2)
    ap.add_argument('--model', default='rf', choices=['rf', 'gbm', 'lr'])
    ap.add_argument('--fast', action='store_true', help='omite el reporte costoso de importancia por feature')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    coins = DEFAULT_COINS if args.coins.upper() == 'ALL' else [c.strip().upper() for c in args.coins.split(',')]
    start_ms = int(datetime.strptime(args.start, '%Y-%m-%d').timestamp() * 1000)
    end_ms = int(datetime.strptime(args.end, '%Y-%m-%d').timestamp() * 1000)
    ML_DIR.mkdir(parents=True, exist_ok=True)
    install_ml_capture()
    if args.fast:
        disable_expensive_reports()

    print(f"=== Jesse ML train ===\nMonedas: {coins}\nPeriodo: {args.start} → {args.end} | modelo: {args.model}")

    summary = {}
    for coin in coins:
        try:
            summary[coin] = train_coin(coin, start_ms, end_ms, args.warmup,
                                       args.test_ratio, args.model, verbose=not args.quiet)
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ {coin}: {type(exc).__name__}: {exc}")
            summary[coin] = {'error': f'{type(exc).__name__}: {exc}'}

    (ML_DIR / 'training_summary.json').write_text(json.dumps(summary, indent=2, default=float))
    ok = [c for c, v in summary.items() if 'error' not in v]
    bad = [c for c, v in summary.items() if 'error' in v]
    print(f"\n=== Resumen ===\n  ✅ {ok}\n  ❌ {bad}\n  → {ML_DIR / 'training_summary.json'}")


if __name__ == '__main__':
    main()
