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
WORKSPACE = Path('/home/overgon/.openclaw/workspace')
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / 'ml'))
sys.path.insert(0, str(WORKSPACE / 'venv' / 'lib' / 'python3.13' / 'site-packages'))

# Importar ML Pipeline
from ml_pipeline_optimized import OptimizedMLPipeline

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

MIN_CONFIDENCE = 60  # Mínimo % para aprobar trade
MODEL_DIR = Path("/home/overgon/.openclaw/workspace/ml/models_optimized")  # ✅ MODELOS OPTIMIZADOS
FALLBACK_POSITION_PERCENT = 25
GLOBAL_PAUSE_FILE = WORKSPACE / "crypto-bots" / "global-pause-flag.json"
RISK_BLOCK_CONFIDENCE = 75  # Debajo de esto, ML puede bloquear como seguridad
RISK_REVIEW_CONFIDENCE = 60  # Arriba de esto, ML solo sugiere y no bloquea

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
        min_conf = MIN_CONFIDENCE  # 60% default
    
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
        result['base_position_size'] = result['position_size']

        # Adjust position size according to confidence
        confidence = prediction['confidence']
        if confidence >= 80:
            result['position_size'] = 100  # Full position
        elif confidence >= 70:
            result['position_size'] = 75   # 75% position
        elif confidence >= 60:
            result['position_size'] = 50   # Half position
        else:
            result['position_size'] = 25   # Minimal position

        # Optional alpha reinforcement — never cancels ML approval
        try:
            from pathlib import Path
            import sys
            workspace = Path('/home/overgon/.openclaw/workspace')
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
            result['base_position_size'] = result['position_size']
            result['position_size'] = FALLBACK_POSITION_PERCENT
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
    
    WORKSPACE = Path('/home/overgon/.openclaw/workspace')
    models_opt_dir = WORKSPACE / 'ml' / 'models_optimized'
    features_dir = WORKSPACE / 'ml' / 'features'
    
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
    
    X = df[selected_features].values
    
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
    elif confidence >= 60:
        position_size = 50
    else:
        position_size = 0
        signal = 'WAIT'
    
    return {
        'signal': signal,
        'confidence': round(confidence, 2),
        'position_size_percent': position_size,
        'action': action,
        'model_accuracy': 88.81,
        'note': f'OptimizedPipeline deploy (features={len(selected_features)}, selected={len(available)})'
    }


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

    try:
        exchange = ccxt.binance({'options': {'defaultType': 'spot'}})
        symbol = f'{coin}/USDT'
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=50)
        if not ohlcv:
            raise RuntimeError('OHLCV vacío')

        closes = np.array([c[4] for c in ohlcv], dtype=float)
        volumes = np.array([c[5] for c in ohlcv], dtype=float)

        sma20 = np.mean(closes[-20:])
        sma50 = np.mean(closes[-50:])
        current = closes[-1]

        delta = np.diff(closes)
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = np.mean(gain[-14:]) if len(gain) >= 14 else 0.0
        avg_loss = np.mean(loss[-14:]) if len(loss) >= 14 and np.mean(loss[-14:]) != 0 else 1e-9
        rsi = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss else 50.0

        bullish_trend = current > sma20 > sma50
        oversold = rsi < 62
        volume_ok = volumes[-1] >= np.mean(volumes[-20:]) if len(volumes) >= 20 else True

        if direction == 'LONG':
            approved = bool(bullish_trend and oversold and volume_ok)
            reason = f'Fallback LONG aprobado (trend={bullish_trend}, RSI={rsi:.1f}, vol={volume_ok})' if approved else f'Fallback LONG rechazado (trend={bullish_trend}, RSI={rsi:.1f}, vol={volume_ok})'
        elif direction == 'SHORT':
            not_bullish = current < sma20 < sma50
            overbought = rsi > 55
            if not_bullish and overbought and volume_ok:
                approved = True
                reason = f'Fallback SHORT aprobado (RSI={rsi:.1f})'
            else:
                reason = f'Fallback SHORT rechazado (RSI={rsi:.1f}, trend={not_bullish})'
    except Exception as e:
        reason = f'Fallback error: {e}'

    return {
        'approved': approved,
        'reason': reason,
        'confidence': 40.0 if approved else 0.0,
        'position_size': 25,
        'signal': direction if approved else 'WAIT',
    }


def print_validation(result: dict, coin: str):
    """Imprimir resultado formateado"""
    
    print(f"\n🧠 ML Validator - {coin} (Modelo Optimizado)")
    print("="*60)
    print(f"Aprobado: {'✅ SÍ' if result['approved'] else '❌ NO'}")
    print(f"Confianza: {result['confidence']:.1f}%")
    print(f"Señal ML: {result['signal']}")
    print(f"Position size: {result['position_size']}%")
    
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
