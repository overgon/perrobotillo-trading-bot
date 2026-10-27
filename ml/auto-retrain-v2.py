#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - AUTO RETRAIN V2 (ML PIPELINE)
# ════════════════════════════════════════════════════════
# Re-entrenamiento automático semanal usando ML Pipeline
# Inspirado en Jesse AI auto-retrain
# ════════════════════════════════════════════════════════

import sys
import os
import json
from pathlib import Path
from datetime import datetime
import logging

# Agregar path al workspace
sys.path.append(os.path.join(os.path.expanduser('~'), '.openclaw', 'workspace', 'ml'))

from ml_pipeline import run_pipeline_all_coins

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = Path(os.path.expanduser('~/.openclaw/workspace'))
LOGS_DIR = WORKSPACE / "logs"
MODELS_DIR = WORKSPACE / "ml" / "models_optimized"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'ml-auto-retrain.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Parámetros de entrenamiento
DAYS_HISTORICAL = 90  # Aumentado de 60 → 90: LINK/XRP necesitan más samples con 216 features
MODEL_TYPE = "random_forest"  # random_forest, gradient_boosting, logistic_regression
USE_SMOTE = False  # SMOTE causó severe overfitting en LINK (7.18% -> 29.75%). Usar class_weight='balanced' en su lugar.

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX", "ZEC"]

# ZEC needs more samples due to sparse production trades (43 vs 60+ for other coins)
# Uses backtest-augmented features CSV + larger training window
COIN_MIN_SAMPLES = {
    'ZEC': 500,  # 500 recent + 750 backfill = 1250 samples (vs default 60)
    # Others use default max(60, last_n * 1.5)
}

# ════════════════════════════════════════════════════════
# AUTO RETRAIN
# ════════════════════════════════════════════════════════

def check_if_retrain_needed(coin: str) -> bool:
    """
    Verificar si es necesario re-entrenar
    
    Criterios:
    1. Modelo no existe → re-entrenar
    2. Modelo > 7 días → re-entrenar
    3. Accuracy < 85% → re-entrenar urgente
    4. Nuevos trades >= 10 desde último entrenamiento → re-entrenar
    """
    
    metadata_path = MODELS_DIR / f"{coin}_optimized_metadata.json"
    metadata_path_legacy = MODELS_DIR / f"{coin}_ml_metadata.json"
    
    # 1. Modelo no existe
    if not metadata_path.exists() and not metadata_path_legacy.exists():
        logger.info(f"{coin}: Modelo no existe, re-entrenando")
        return True
    
    chosen = metadata_path if metadata_path.exists() else metadata_path_legacy
    with open(chosen, 'r') as f:
        metadata = json.load(f)
    
    # 2. Verificar edad del modelo
    trained_at = datetime.fromisoformat(metadata['trained_at'])
    days_old = (datetime.now() - trained_at).days
    
    if days_old > 7:
        logger.info(f"{coin}: Modelo tiene {days_old} días, re-entrenando")
        return True
    
    # 3. Verificar métrica principal de metadata o fallback a accuracy
    metric_key = metadata.get('primary_metric', 'accuracy')
    current_metric = metadata.get('metrics', {}).get(metric_key, metadata.get('metrics', {}).get('accuracy', 0))
    threshold = 0.80 if metric_key == 'f1_macro' else 0.85
    if current_metric < threshold:
        logger.warning(f"{coin}: {metric_key}={current_metric:.2%} < {threshold:.0%}, re-entrenando urgente")
        return True
    
    # 3b. Verificar overfitting gap como criterio de re-entrenamiento
    overfitting_gap = metadata.get('metrics', {}).get('overfitting_gap', 0)
    if overfitting_gap > 0.08:  # Gap > 8%
        logger.warning(f"{coin}: overfitting gap={overfitting_gap:.2%} > 8%, re-entrenando urgente")
        return True
    
    # 4. Verificar trades nuevos desde último entrenamiento
    try:
        last_count = metadata.get('last_trade_count', metadata.get('samples', 0))
    except Exception:
        last_count = 0
    
    trade_history_path = WORKSPACE / "crypto-bots/trade-history.json"
    current_count = 0
    if trade_history_path.exists():
        with open(trade_history_path, 'r') as f:
            current_count = len(json.load(f).get('trades', []))
    
    new_trades = max(0, current_count - last_count)
    if new_trades >= 10:
        logger.info(f"{coin}: {new_trades} trades nuevos desde último entrenamiento, re-entrenando")
        return True
    
    metric_label = metadata.get('primary_metric', 'accuracy')
    metric_val = metadata.get('metrics', {}).get(metric_label, metadata.get('metrics', {}).get('accuracy', 0))
    logger.info(f"{coin}: Modelo OK ({metric_label}: {metric_val:.2%}, edad: {days_old} días, nuevos: {new_trades})")
    return False


def run_auto_retrain():
    """Ejecutar re-entrenamiento automático"""
    
    logger.info("="*60)
    logger.info("🧠 AUTO RETRAIN INICIADO (Modelos Optimizados)")
    logger.info(f"Días históricos: {DAYS_HISTORICAL}")
    logger.info(f"Modelo: {MODEL_TYPE}")
    logger.info(f"SMOTE: {USE_SMOTE}")
    logger.info("="*60)
    
    results = {}
    
    for coin in COINS:
        try:
            # Verificar si necesita re-entrenar
            needs_retrain = check_if_retrain_needed(coin)
            
            if not needs_retrain:
                logger.info(f"⏭️  {coin}: Saltando (modelo reciente y preciso)")
                results[coin] = {'status': 'skipped', 'reason': 'modelo_ok'}
                continue
            
            # Re-entrenar
            logger.info(f"\n🚀 {coin}: Iniciando re-entrenamiento...")
            
            from ml_pipeline_optimized import OptimizedMLPipeline  # ✅ VERSIÓN OPTIMIZADA
            
            pipeline = OptimizedMLPipeline(coin, use_feature_selection=True)  # ✅ Pipeline optimizado
            
            # Cargar datos: priorizar ventana reciente cuando hay trades nuevos
            kwargs = {'days': DAYS_HISTORICAL}
            current_count = 0
            try:
                with open(MODELS_DIR / f"{coin}_optimized_metadata.json") as f:
                    last_count = json.load(f).get('last_trade_count', 0)
                trade_history_path = WORKSPACE / "crypto-bots/trade-history.json"
                if trade_history_path.exists():
                    with open(trade_history_path) as f:
                        current_count = len(json.load(f).get('trades', []))
                new_trades = current_count - last_count
                if new_trades > 0:
                    kwargs['last_n'] = new_trades
                # ZEC override: use minimum sample count (backtest-augmented)
                if coin in COIN_MIN_SAMPLES:
                    min_s = COIN_MIN_SAMPLES[coin]
                    kwargs['last_n'] = max(new_trades, min_s)
                    logger.info(f"{coin}: Using min_samples={min_s} (backtest-augmented features)")
            except Exception:
                if coin in COIN_MIN_SAMPLES:
                    kwargs['last_n'] = COIN_MIN_SAMPLES[coin]
                    kwargs.pop('days', None)
            df = pipeline.load_data(**kwargs)
            
            if df is None or len(df) == 0:
                logger.error(f"{coin}: No hay datos para entrenar")
                results[coin] = {'status': 'failed', 'reason': 'no_data'}
                continue
            
            # Entrenar
            metrics = pipeline.train(df, test_size=0.2)
            
            if not metrics or 'accuracy' not in metrics:
                logger.error(f"{coin}: Error en training")
                results[coin] = {'status': 'failed', 'reason': 'train_error'}
                continue
            
            # Guardar conteo de trades usados para umbral de "nuevos trades"
            try:
                model_info_path = MODELS_DIR / f"{coin}_optimized_metadata.json"
                if model_info_path.exists():
                    with open(model_info_path, 'r') as f:
                        meta = json.load(f)
                    meta['last_trade_count'] = current_count
                    with open(model_info_path, 'w') as f:
                        json.dump(meta, f, indent=2)
            except Exception:
                pass
            
            # Éxito
            logger.info(f"✅ {coin}: Re-entrenamiento completado")
            logger.info(f"   Accuracy: {metrics.get('accuracy', 0):.2%}")
            logger.info(f"   CV: {metrics.get('cv_mean', 0):.2%} (+/- {metrics.get('cv_std', 0):.2%})")
            logger.info(f"   Overfitting gap: {metrics.get('overfitting_gap', 0):.2%}")
            
            results[coin] = {
                'status': 'success',
                'accuracy': metrics.get('accuracy', 0),
                'cv_mean': metrics.get('cv_mean', 0),
                'cv_std': metrics.get('cv_std', 0),
                'overfitting_gap': metrics.get('overfitting_gap', 0),
                'signal': 'N/A',
                'confidence': 0.0
            }
            
        except Exception as e:
            logger.error(f"{coin}: Error inesperado - {str(e)}")
            results[coin] = {'status': 'failed', 'reason': str(e)}
    
    # Resumen final
    logger.info("\n" + "="*60)
    logger.info("🏆 RESUMEN AUTO RETRAIN")
    logger.info("="*60)
    
    success_count = sum(1 for r in results.values() if r['status'] == 'success')
    skipped_count = sum(1 for r in results.values() if r['status'] == 'skipped')
    failed_count = sum(1 for r in results.values() if r['status'] == 'failed')
    
    logger.info(f"Exitosos: {success_count}")
    logger.info(f"Saltados: {skipped_count}")
    logger.info(f"Fallidos: {failed_count}")
    logger.info("="*60)
    
    # Guardar resumen
    summary_file = LOGS_DIR / f"auto-retrain-summary-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(summary_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'days_historical': DAYS_HISTORICAL,
            'model_type': MODEL_TYPE,
            'use_smote': USE_SMOTE,
            'results': results
        }, f, indent=2)
    
    logger.info(f"📝 Resumen guardado en: {summary_file}")
    
    return results


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("\n" + "="*60)
    logger.info(f"🐕 Perrobotillo Auto-Retrain v2")
    logger.info(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60 + "\n")
    
    results = run_auto_retrain()
    
    # Exit code según resultados
    failed = sum(1 for r in results.values() if r['status'] == 'failed')
    
    if failed > 0:
        logger.warning(f"\n⚠️  {failed} monedas fallaron en re-entrenamiento")
        sys.exit(1)
    else:
        logger.info("\n✅ Todas las monedas re-entrenadas exitosamente")
        sys.exit(0)
