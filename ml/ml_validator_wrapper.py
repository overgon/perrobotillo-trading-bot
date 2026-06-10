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
from ml_pipeline import MLPipeline

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

MIN_CONFIDENCE = 60  # Mínimo % para aprobar trade
MODEL_DIR = Path("/home/overgon/.openclaw/workspace/ml/models_optimized")  # ✅ MODELOS OPTIMIZADOS

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
    
    # Cargar metadata del modelo
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Crear pipeline y hacer deploy
    pipeline = MLPipeline(coin=coin)
    prediction = pipeline.deploy_phase()
    
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
    
    # Check 1: Señal WAIT
    if prediction.get('signal') == 'WAIT':
        result['reason'] = 'ML recomienda esperar - oportunidad no óptima'
        return result
    
    # Check 2: Confianza mínima
    if prediction.get('confidence', 0) < min_conf:
        result['reason'] = f"Confianza muy baja ({prediction['confidence']:.1f}% < {min_conf}%)"
        return result
    
    # Check 3: Dirección coincide
    if direction == 'LONG' and prediction.get('signal') != 'LONG':
        result['reason'] = f"Señal ML no coincide (ML: {prediction['signal']}, Trade: {direction})"
        return result
    
    if direction == 'SHORT' and prediction.get('signal') != 'SHORT':
        result['reason'] = f"Señal ML no coincide (ML: {prediction['signal']}, Trade: {direction})"
        return result
    
    # ✅ APROBADO
    result['approved'] = True
    result['reason'] = f"ML aprobado ({prediction['confidence']:.1f}% confianza)"
    
    # Ajustar position size según confianza
    confidence = prediction['confidence']
    if confidence >= 80:
        result['position_size'] = 100  # Full position
    elif confidence >= 70:
        result['position_size'] = 75   # 75% position
    elif confidence >= 60:
        result['position_size'] = 50   # Half position
    else:
        result['position_size'] = 25   # Minimal position
    
    return result


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
