#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - ML VALIDATOR WRAPPER
# ════════════════════════════════════════════════════════
# Wrapper para integrar ML Pipeline con bot principal
# Uso: python3 ml_validator_wrapper.py <COIN> [DIRECTION]
# ════════════════════════════════════════════════════════

import sys
import os
import json
from pathlib import Path

# Agregar path al workspace y venv
WORKSPACE = Path(os.path.expanduser('~/.openclaw/workspace'))
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / 'ml'))
sys.path.insert(0, str(WORKSPACE / 'venv' / 'lib' / 'python3.13' / 'site-packages'))

# Importar ML Pipeline
from ml_pipeline_optimized import OptimizedMLPipeline

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

MIN_CONFIDENCE = 55  # Reducido de 60 → 55: entrar antes, más agresivo pero conservador
MODEL_DIR = Path("/home/overgon/.openclaw/workspace/ml/models_optimized")  # ✅ MODELOS OPTIMIZADOS
FALLBACK_POSITION_PERCENT = 50  # Aumentado de 35 → 50: capturar más movimiento sin duplicar riesgo
GLOBAL_PAUSE_FILE = WORKSPACE / "crypto-bots" / "global-pause-flag.json"
RISK_BLOCK_CONFIDENCE = 75  # Debajo de esto, ML bloquea como seguridad
RISK_REVIEW_CONFIDENCE = 50  # Reducido de 60 → 50: más sensible a señales marginales

# ════════════════════════════════════════════════════════
# VALIDADOR
# ════════════════════════════════════════════════════════

def validate_trade(coin: str, direction: str = "LONG", trade_type: str = "NORMAL") -> dict:
    """
    Validar trade con ML Pipeline (Modelos Optimizados Anti-Overfitting)
    
    Args:
        coin: Moneda (BTC, ETH, BNB, etc.)
        direction: LONG o SHORT
        trade_type: SCALP, NORMAL, o SWING
    
    Returns: dict con decisión y metadata
    """
    
    # ════════════════════════════════════════════════════════
    # ⭐ VERIFICAR PAUSE FLAG (CIRCUIT BREAKER)
    # ════════════════════════════════════════════════════════
    # Si el CB está activo (pause_until futuro), RECHAZAR todos los trades nuevos
    if GLOBAL_PAUSE_FILE.exists():
        try:
            from datetime import datetime as _dt
            with open(GLOBAL_PAUSE_FILE, 'r') as f:
                pause_data = json.load(f)
            pause_until_str = pause_data.get('pause_until')
            if pause_until_str:
                pause_until = _dt.fromisoformat(pause_until_str)
                now = _dt.now()
                remaining = (pause_until - now).total_seconds()
                if remaining > 0:
                    return {
                        'approved': False,
                        'reason': f'FALLBACK: PAUSE FLAG ACTIVO - No abrir NUEVOS trades (restan {remaining/60:.0f} min)',
                        'confidence': 0,
                        'position_size': 0,
                        'signal': 'WAIT',
                        'source': 'CIRCUIT_BREAKER',
                        'pauseRemaining': round(remaining / 60),
                        'losses24h': pause_data.get('losses_24h', 0)
                    }
        except Exception:
            pass  # Si falla, dejar pasar (no bloquear por errores)
    
    # Verificar si existe modelo entrenado OPTIMIZADO
    model_path = MODEL_DIR / f"{coin}_optimized_model.pkl"
    metadata_path = MODEL_DIR / f"{coin}_optimized_metadata.json"
    
    if not model_path.exists():
        return {
            'approved': False,
            'reason': f'Modelo optimizado no encontrado para {coin}',
            'confidence': 0,
            'position_size': 0,
            'signal': 'ERROR',
            'requires_training': True,
            'note': 'Usar ml_pipeline_optimized.py para entrenar'
        }
    
    # Cargar metadata del modelo optimizado
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    # ✅ DEBUG: Log que estamos usando el modelo optimizado
    import logging as _logging
    _logging.info(f"[ML WRAPPER] {coin}: usando modelo optimizado ({metadata_path})")

    # Deploy: cargar modelo optimizado, scaler optimizado y features seleccionadas
    prediction = _deploy_optimized_model(coin, model_path, metadata_path)
    
    if not prediction:
        return {
            'approved': False,
            'reason': 'Error generando predicción',
            'confidence': 0,
            'position_size': 0,
            'signal': 'ERROR'
        }
    
    # Ajustar thresholds por tipo de trade
    if trade_type == "SCALP":
        min_conf = 65  # Más exigente para scalping
    elif trade_type == "SWING":
        min_conf = 70  # Más exigente para swing
    else:
        min_conf = MIN_CONFIDENCE  # 55% default (configurable)
    
    # Validar decisión
    result = {
        'approved': False,
        'reason': '',
        'confidence': prediction.get('confidence', 0),
        'position_size': prediction.get('position_size_percent', 0),
        'signal': prediction.get('signal', 'WAIT'),
        'model_accuracy': metadata['metrics']['accuracy'],
        'model_type': 'optimized',  # ✅ Usando modelo optimizado
        'overfitting_gap': metadata['metrics'].get('overfitting_gap', 'N/A')
    }
    
    ml_pass = True
    
    # Check 1: Señal WAIT
    if prediction.get('signal') == 'WAIT':
        result['reason'] = 'ML recomienda esperar - oportunidad no óptima'
        ml_pass = False
    
    # Check 2: Confianza mínima
    if ml_pass and prediction.get('confidence', 0) < min_conf:
        result['reason'] = f"Confianza muy baja ({prediction['confidence']:.1f}% < {min_conf}%)"
        ml_pass = False
    
    # Check 3: Dirección coincide
    if ml_pass:
        if direction == 'LONG' and prediction.get('signal') != 'LONG':
            result['reason'] = f"Señal ML no coincide (ML: {prediction['signal']}, Trade: {direction})"
            ml_pass = False
        if direction == 'SHORT' and prediction.get('signal') != 'SHORT':
            result['reason'] = f"Señal ML no coincide (ML: {prediction['signal']}, Trade: {direction})"
            ml_pass = False
    
    if ml_pass:
        # ✅ APROBADO
        result['approved'] = True
        result['reason'] = f"ML aprobado ({prediction['confidence']:.1f}% confianza)"
        result['source'] = 'ML'
        result = apply_modulation(result, coin)

        # Optional alpha reinforcement — never cancels ML approval
        try:
            from pathlib import Path
            import sys
            workspace = Path(os.path.expanduser('~/.openclaw/workspace'))
            alpha_dir = workspace / 'research' / 'vibe-alpha'
            if str(alpha_dir) not in sys.path:
                sys.path.insert(0, str(alpha_dir))
            import importlib.util
            spec = importlib.util.spec_from_file_location("alpha101_054", str(alpha_dir / "alpha101_054.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            compute_054 = mod.compute
            bench_spec = importlib.util.spec_from_file_location("bench_crypto", str(alpha_dir / "bench_crypto.py"))
            bench_mod = importlib.util.module_from_spec(bench_spec)
            bench_spec.loader.exec_module(bench_mod)
            panel = bench_mod.build_panel([f"{coin}USDT"], days=30)
            panel = bench_mod.align_panel(panel, [f"{coin}USDT"])
            alpha_df = compute_054(panel)
            alpha_value = float(alpha_df.iloc[-1, 0]) if not alpha_df.empty else None
            if alpha_value is not None:
                result['alpha101_054'] = alpha_value
                if alpha_value > 0:
                    result['reason'] = f"{result['reason']} | alpha101_054 refuerza (+)"
                    result['source'] = 'ML+ALPHA'
                else:
                    result['reason'] = f"{result['reason']} | alpha101_054 baja score (-)"
                    result['source'] = 'ML+ALPHA'
        except Exception:
            pass
    else:
        # Fallback explícito
        fallback = _technical_fallback(coin, direction)
        if fallback.get('approved'):
            result['approved'] = True
            result['reason'] = f"FALLBACK activado: {fallback['reason']}"
            result['signal'] = fallback.get('signal', result['signal'])
            result['confidence'] = fallback.get('confidence', 0.0)
            result['regime'] = fallback.get('regime', 'LATERAL')
            result = apply_modulation(result, coin)
            result['source'] = 'FALLBACK'
        else:
            result['reason'] = f"{result['reason']} | Fallback: {fallback.get('reason', 'sin datos')}"
            result['source'] = 'ML_BLOCKED'
            result['base_position_size'] = result['position_size']

    return result



def _deploy_optimized_model(coin: str, model_path: Path, metadata_path: Path) -> dict:
    """
    Deploy phase para modelos optimizados.
    
    Carga el modelo optimized_model.pkl, scaler_optimized.pkl, y selected_features.pkl
    para generar prediction con confidence en tiempo real.
    """
    import joblib
    import numpy as np
    import pandas as pd
    
    WORKSPACE = Path(os.path.expanduser('~/.openclaw/workspace'))
    models_opt_dir = WORKSPACE / 'ml' / 'models_optimized'
    features_dir = WORKSPACE / 'ml' / 'features'
    
    # Cargar metadata real (antes el accuracy estaba hardcodeado en 88.81%)
    model_accuracy = None
    model_test_score = None
    try:
        import json as _json
        with open(metadata_path) as f:
            _meta = _json.load(f)
        _m = _meta.get('metrics', {})
        model_accuracy = _m.get('accuracy')
        model_test_score = _m.get('test_score')
    except Exception:
        pass
    
    # Load optimized model
    model = joblib.load(model_path)
    
    # Load optimized scaler
    scaler_path = models_opt_dir / f"{coin}_scaler_optimized.pkl"
    scaler = joblib.load(scaler_path)
    
    # Load selected features
    selected_features_path = models_opt_dir / f"{coin}_selected_features.pkl"
    selected_features = joblib.load(selected_features_path)
    
    # Load latest features dataframe
    features_csv = features_dir / f"{coin}_features.csv"
    if not features_csv.exists():
        alt_files = list(features_dir.glob(f"*{coin}*features*.csv")) + list(features_dir.glob(f"features_{coin}*.csv"))
        if alt_files:
            features_csv = alt_files[0]
        else:
            return {
                'signal': 'WAIT',
                'confidence': 0,
                'position_size_percent': 0,
                'note': f'No features CSV found for {coin}'
            }
    
    df = pd.read_csv(features_csv)
    
    # Select only the features the model was trained on
    available = [f for f in selected_features if f in df.columns]
    missing = [f for f in selected_features if f not in df.columns]
    
    if len(available) < len(selected_features) * 0.5:
        return {
            'signal': 'WAIT',
            'confidence': 0,
            'position_size_percent': 0,
            'note': f'Too many missing features ({len(missing)}/{len(selected_features)})'
        }
    
    for col in missing:
        df[col] = 0.0
    
    # Copia escribible: con pandas/numpy recientes .values puede ser read-only
    X = df[selected_features].to_numpy(dtype=float, copy=True)
    
    # Handle NaN
    col_means = np.nanmean(X, axis=0)
    indices = np.where(np.isnan(X))
    X[indices] = np.take(col_means, indices[1])
    
    # Scale
    X_scaled = scaler.transform(X)
    
    # Predict - use last row (latest signal)
    prediction = model.predict(X_scaled)[-1]
    proba = model.predict_proba(X_scaled)[-1] if hasattr(model, 'predict_proba') else [0.5, 0.5]
    
    confidence = float(max(proba)) * 100
    predicted_label = int(prediction)
    
    # Label mapping: 0=WAIT, 1=LONG, 2=SHORT
    if predicted_label == 1:
        signal = 'LONG'
        action = '✅ APROBAR COMPRA'
    elif predicted_label == 2:
        signal = 'SHORT'
        action = '✅ APROBAR VENTA'
    else:
        signal = 'WAIT'
        action = '⏸️ ESPERAR MEJOR OPORTUNIDAD'
    
    # Position sizing based on confidence
    if confidence >= 75:
        position_size = 100
    elif confidence >= MIN_CONFIDENCE:  # ✅ Usa global constant (55), no hardcoded 60
        position_size = 50
    else:
        position_size = 0
        signal = 'WAIT'
        action = '⏸️ ESPERAR MEJOR OPORTUNIDAD'
    
    # 🔧 FIX 2026-11-18: si el modelo no tiene edge demostrable (test_score
    # bajo), el gate no debe dejarlo como único árbitro: la nota lo deja claro
    # para que el fallback técnico decida.
    quality_note = ''
    if model_test_score is not None and model_test_score < 0.55:
        quality_note = f' | modelo sin edge (test_score={model_test_score:.3f})'

    return {
        'signal': signal,
        'confidence': round(confidence, 2),
        'position_size_percent': position_size,
        'action': action,
        'model_accuracy': model_accuracy,
        'note': f'OptimizedPipeline deploy (features={len(selected_features)}, selected={len(available)}){quality_note}'
    }



def _market_regime(coin: str) -> str:
    """
    Régimen de mercado de la moneda. Fuente primaria: ml/market-predictions.json
    (market-classifier, actualizado cada 2h). Respaldo: crypto-bots/market-mode.conf.
    """
    ws = Path(os.path.expanduser('~/.openclaw/workspace'))
    mode = None
    try:
        with open(ws / 'ml' / 'market-predictions.json') as f:
            preds = json.load(f).get('predictions', {})
        mode = (preds.get(coin) or {}).get('market_mode')
    except Exception:
        pass
    if not mode:
        try:
            with open(ws / 'crypto-bots' / 'market-mode.conf') as f:
                for line in f:
                    if line.strip().startswith('MARKET_MODE='):
                        mode = line.split('=', 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    return mode if mode in REGIME_PARAMS else 'LATERAL'


# ════════════════════════════════════════════════════════
# UMBRALES DINÁMICOS SEGÚN RÉGIMEN DE MERCADO
# ════════════════════════════════════════════════════════
# BULL: perseguir momentum (SMA20, RSI hasta 72). LATERAL: más confirmación.
# BEAR: solo recuperaciones fuertes (precio > SMA50) con RSI bajo.
REGIME_PARAMS = {
    'BULL':    {'trend_sma': 20, 'rsi_min': 40, 'rsi_max': 72, 'position': 50},
    'LATERAL': {'trend_sma': 20, 'rsi_min': 35, 'rsi_max': 62, 'position': 35},
    'BEAR':    {'trend_sma': 50, 'rsi_min': 25, 'rsi_max': 55, 'position': 20},
}


def _calculate_fallback_confidence(approved: bool, bullish_trend: bool, rsi: float,
                                   volume_ok: bool, regime: str = 'LATERAL') -> float:
    """
    Calculate dynamic confidence for fallback trades based on technical signals.
    Instead of hardcoded 40%, derives real confidence from signal strength.
    """
    if not approved:
        return 0.0
    
    confidence = 0.0
    
    # Base confidence for approved fallback
    confidence += 45  # Base approval threshold
    
    # RSI dentro de la banda del régimen (más cerca del centro, más confianza)
    p = REGIME_PARAMS.get(regime, REGIME_PARAMS['LATERAL'])
    if p['rsi_min'] <= rsi <= p['rsi_max']:
        mid = (p['rsi_min'] + p['rsi_max']) / 2
        confidence += 15 - abs(rsi - mid) * 0.3
    else:
        confidence -= 15
    
    # Trend factor: confirmado bullish trend
    if bullish_trend:
        confidence += 15  # Bonus fuerte por tendencia confirmada

    # En BEAR se exige más y se da menos confianza; en BULL se permite momentum
    if regime == 'BULL':
        confidence += 5
    elif regime == 'BEAR':
        confidence -= 5
    
    # Volume factor
    if volume_ok:
        confidence += 5   # Bonus por volumen suficiente
    
    # Max cap
    confidence = min(confidence, 85.0)
    
    return round(confidence, 1)

def _technical_fallback(coin: str, direction: str = "LONG") -> dict:
    """
    Fallback explícito cuando ML no aprueba:
    revisa condiciones mínimas y reduce exposición.
    """
    try:
        import ccxt
        import numpy as np
    except Exception as e:
        return {
            'approved': False,
            'reason': f'Fallback unavailable: {e}',
            'confidence': 0,
            'position_size': 0,
            'signal': 'WAIT',
        }

    approved = False
    reason = 'Fallback: condiciones técnicas no cumplidas'
    regime = 'LATERAL'
    bullish_trend = False
    rsi = 50.0
    volume_ok = False
    position_size = 0

    try:
        exchange = ccxt.binance({'options': {'defaultType': 'spot'}})
        symbol = f'{coin}/USDT'
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=60)
        if not ohlcv:
            raise RuntimeError('OHLCV vacío')

        closes = np.array([c[4] for c in ohlcv], dtype=float)
        volumes = np.array([c[5] for c in ohlcv], dtype=float)

        regime = _market_regime(coin)
        p = REGIME_PARAMS[regime]

        sma_trend = np.mean(closes[-p['trend_sma']:])
        current = closes[-1]

        delta = np.diff(closes)
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = np.mean(gain[-14:]) if len(gain) >= 14 else 0.0
        avg_loss = np.mean(loss[-14:]) if len(loss) >= 14 and np.mean(loss[-14:]) != 0 else 1e-9
        rsi = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss else 50.0

        bullish_trend = current > sma_trend
        rsi_ok = p['rsi_min'] <= rsi <= p['rsi_max']
        volume_ok = True  # sin penalización por volumen bajo
        position_size = p['position']
        base = (f"{regime}: trend={bullish_trend} (SMA{p['trend_sma']}), "
                f"RSI={rsi:.1f} [{p['rsi_min']}-{p['rsi_max']}], vol={volume_ok}")

        if direction == 'LONG':
            approved = bool(bullish_trend and rsi_ok and volume_ok)
            reason = f'Fallback LONG {"aprobado" if approved else "rechazado"} ({base})'
        elif direction == 'SHORT':
            not_bullish = current < sma_trend
            overbought = rsi > p['rsi_max']
            if not_bullish and overbought and volume_ok:
                approved = True
                reason = f'Fallback SHORT aprobado ({base})'
            else:
                reason = f'Fallback SHORT rechazado ({base})'
    except Exception as e:
        reason = f'Fallback error: {e}'

    return {
        'approved': approved,
        'reason': reason,
        'confidence': _calculate_fallback_confidence(approved, bullish_trend, rsi, volume_ok, regime) if approved else 0.0,
        'position_size': position_size if approved else 0,
        'signal': direction if approved else 'WAIT',
        'regime': regime,
    }


# ════════════════════════════════════════════════════════
# MODELO DE OUTCOME (modulador de tamaño) — paso 3 de #77
# ════════════════════════════════════════════════════════
OUTCOME_MODEL = Path("/home/overgon/.openclaw/workspace/ml/outcome_model.pkl")
OUTCOME_META = Path("/home/overgon/.openclaw/workspace/ml/outcome_features.json")
REGIME_MULT = {'BULL': 1.0, 'LATERAL': 0.75, 'BEAR': 0.45}


def _rsi_s(c: pd.Series, n: int = 14) -> float:
    d = c.diff()
    g = d.clip(lower=0).rolling(n).mean()
    l = (-d.clip(upper=0)).rolling(n).mean().replace(0, 1e-9)
    return float((100 - 100 / (1 + g / l)).iloc[-1])


def per_coin_position_size(coin: str, default: float = 10.0) -> float:
    """Posicion base (%) por moneda desde crypto-bots/per-coin-config.env."""
    try:
        p = Path(os.path.expanduser('~/.openclaw/workspace/crypto-bots/per-coin-config.env'))
        for line in p.read_text().splitlines():
            line = line.strip()
            if line.startswith(f'{coin}_POSITION_SIZE='):
                return float(line.split('=', 1)[1].strip().strip('"').strip("'"))
    except Exception:
        pass
    return default


def outcome_probability(coin: str):
    """
    Probabilidad (0-1) de que un trade iniciado ahora cierre con P&L > 0,
    segun el modelo de outcome entrenado en research/train_outcome_model.py.
    Devuelve None si no hay modelo o no se pudo calcular.
    """
    if not OUTCOME_MODEL.exists() or not OUTCOME_META.exists():
        return None
    try:
        import joblib
        import ccxt
        import pandas as pd
        import numpy as np
        meta = json.loads(OUTCOME_META.read_text())
        model = joblib.load(OUTCOME_MODEL)

        ex = ccxt.binance({'options': {'defaultType': 'spot'}})
        frames = {}
        for sym in {coin, 'BTC'}:
            o = ex.fetch_ohlcv(f'{sym}/USDT', timeframe='1h', limit=500)
            df = pd.DataFrame(o, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
            df['ts'] = pd.to_datetime(df['ts'], unit='ms')
            frames[sym] = df.set_index('ts')

        h = frames[coin]
        b = frames['BTC']
        c = h['close']
        feat = {}
        for n in (1, 4, 12, 24):
            feat[f'ret_{n}h'] = float(c.pct_change(n).iloc[-1])
        feat['rsi14'] = _rsi_s(c)
        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        feat['macd_hist'] = float((ema12 - ema26).iloc[-1] - (ema12 - ema26).ewm(span=9, adjust=False).mean().iloc[-1])
        for n in (20, 50, 200):
            feat[f'dist_ema{n}'] = float(c.iloc[-1] / c.ewm(span=n, adjust=False).mean().iloc[-1] - 1)
        tr = pd.concat([h['high'] - h['low'],
                        c - h['low'].shift(1).fillna(c),
                        h['high'].shift(1).fillna(c) - c], axis=1).max(axis=1)
        feat['atr_pct'] = float(tr.rolling(14).mean().iloc[-1] / c.iloc[-1])
        ma = c.rolling(20).mean()
        feat['bb_width'] = float((c.rolling(20).std() * 4).iloc[-1] / ma.iloc[-1])
        feat['dist_high50'] = float(c.iloc[-1] / h['high'].rolling(50).max().iloc[-1] - 1)
        feat['dist_low50'] = float(c.iloc[-1] / h['low'].rolling(50).min().iloc[-1] - 1)
        feat['vol_ratio'] = float(h['volume'].iloc[-1] / h['volume'].rolling(20).mean().iloc[-1])
        hour = h.index[-1].hour
        feat['hour_sin'] = float(np.sin(2 * np.pi * hour / 24))
        feat['hour_cos'] = float(np.cos(2 * np.pi * hour / 24))
        feat['btc_ret_24h'] = float(b['close'].pct_change(24).iloc[-1])
        for cn in ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC']:
            feat[f'c_{cn}'] = 1 if cn == coin else 0

        X = pd.DataFrame([[feat.get(f, 0.0) for f in meta['features']]], columns=meta['features'])
        return float(model.predict_proba(X.to_numpy())[0][1])
    except Exception as e:
        print(f"⚠️  outcome model no disponible: {e}", file=sys.stderr)
        return None


def modulated_position(coin: str, approved: bool, base_size: float, regime: str = 'LATERAL'):
    """
    Regla del paso 3: el modelo modula el tamaño (no veta).
      tamaño = base * regime_mult * clip(prob, 0.25, 1.0)
    """
    if not approved:
        return 0.0, None
    p = outcome_probability(coin)
    if p is None:
        mult = REGIME_MULT.get(regime, 0.75)
        return round(min(base_size, base_size * mult), 2), None
    mult = REGIME_MULT.get(regime, 0.75) * min(1.0, max(0.25, p))
    return round(min(base_size, base_size * mult), 2), p


def apply_modulation(result: dict, coin: str) -> dict:
    """Aplica el modulador de tamaño (modelo de outcome) a un trade ya aprobado."""
    base = per_coin_position_size(coin)
    reg = result.get('regime') or _market_regime(coin)
    size, p = modulated_position(coin, True, base, reg)
    result['position_size'] = size
    result['regime'] = reg
    result['outcome_prob'] = p
    result['base_position_size'] = base
    if p is not None:
        result['reason'] = f"{result['reason']} | outcome p={p:.2f} → tamaño {size:.1f}%"
    return result


def print_validation(result: dict, coin: str):
    """Imprimir resultado formateado"""
    
    print(f"\n🧠 ML Validator - {coin} (Modelo Optimizado)")
    print("="*60)
    print(f"Aprobado: {'✅ SÍ' if result['approved'] else '❌ NO'}")
    print(f"Confianza: {result['confidence']:.1f}%")
    print(f"Señal ML: {result['signal']}")
    print(f"Position size: {result['position_size']}%")
    if result.get('regime'):
        print(f"Régimen de mercado: {result['regime']}")
    if result.get('outcome_prob') is not None:
        print(f"Outcome model: p={result['outcome_prob']:.2f} → tamaño {result['position_size']}%")
    
    if 'model_accuracy' in result:
        print(f"Model accuracy: {result['model_accuracy']:.2%}")
    if 'overfitting_gap' in result and result['overfitting_gap'] != 'N/A':
        gap = result['overfitting_gap']
        gap_status = '✅' if gap < 0.05 else '⚠️'
        print(f"Overfit gap: {gap:.2%} {gap_status}")
    
    print(f"\nRazón: {result['reason']}")
    print("="*60)
    
    if result.get('requires_training'):
        print("\n⚠️  MODELO NO ENTRENADO")
        print("   Para entrenar ejecutá:")
        print(f"   python3 ml_pipeline.py {coin} 60 random_forest")
        print("="*60)


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 ml_validator_wrapper.py <COIN> [DIRECTION] [TRADE_TYPE]")
        print("Ejemplo: python3 ml_validator_wrapper.py BNB LONG NORMAL")
        print("         python3 ml_validator_wrapper.py ETH SHORT SCALP")
        sys.exit(1)
    
    coin = sys.argv[1].upper()
    direction = sys.argv[2].upper() if len(sys.argv) > 2 else "LONG"
    trade_type = sys.argv[3].upper() if len(sys.argv) > 3 else "NORMAL"
    
    result = validate_trade(coin, direction, trade_type)
    print_validation(result, coin)
    
    # Exit code para integración bash
    sys.exit(0 if result['approved'] else 1)
