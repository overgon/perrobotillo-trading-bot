#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - WALK-FORWARD BACKTEST
# ════════════════════════════════════════════════════════
# Walk-forward optimization para reducir overfitting
# Inspirado en Intelligent Trading Bot
# ════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import warnings
warnings.filterwarnings('ignore')

# Custom JSON encoder for numpy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
BACKTEST_DIR = WORKSPACE / "backtest"
REPORTS_DIR = BACKTEST_DIR / "walk_forward_reports"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

# ════════════════════════════════════════════════════════
# WALK-FORWARD BACKTEST ENGINE
# ════════════════════════════════════════════════════════

class WalkForwardBacktest:
    """
    Walk-forward backtesting para evaluar robustez de modelos ML
    
    Proceso:
    1. Dividir datos en N ventanas consecutivas
    2. Para cada ventana:
       - Train en período X
       - Test en período X+1 (fuera de muestra)
       - Calcular métricas
    3. Promediar métricas de todas las ventanas
    4. Evaluar consistencia del modelo
    
    Si el modelo es consistente en todas las ventanas → ROBUSTO
    Si el modelo varía mucho entre ventanas → OVERFITTING
    """
    
    def __init__(self, coin: str, n_splits: int = 5):
        """
        coin: Moneda a backtestear
        n_splits: Número de ventanas walk-forward (default 5)
        """
        self.coin = coin.upper()
        self.n_splits = n_splits
        self.results = []
        
        print(f"\n{'='*60}")
        print(f"🚶 WALK-FORWARD BACKTEST - {self.coin}")
        print(f"{'='*60}")
        print(f"Número de splits: {n_splits}")
    
    def load_data(self, days: int = 90) -> pd.DataFrame:
        """Cargar datos OHLCV + features"""
        
        print(f"\n📥 Cargando {days} días de datos...")
        
        # Intentar cargar features ya generados por ml_pipeline
        features_file = WORKSPACE / "ml" / "features" / f"{self.coin}_features.csv"
        
        if features_file.exists():
            df = pd.read_csv(features_file, parse_dates=['timestamp'] if 'timestamp' in open(features_file).readline() else None)
            print(f"   ✅ Features cargados: {len(df)} samples")
            return df
        
        # Si no existen, cargar datos básicos
        data_file = WORKSPACE / "backtest" / "data" / f"{self.coin}_*.csv"
        data_files = list(WORKSPACE.glob(str(data_file)))
        
        if not data_files:
            print(f"❌ No se encontraron datos para {self.coin}")
            return pd.DataFrame()
        
        latest_file = max(data_files, key=lambda f: f.stat().st_mtime)
        df = pd.read_csv(latest_file)
        
        print(f"   ✅ Datos cargados: {len(df)} velas")
        
        return df
    
    def generate_walk_forward_splits(self, df: pd.DataFrame) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Generar splits walk-forward
        
        Returns: Lista de tuples (train_df, test_df)
        """
        
        n_samples = len(df)
        
        if n_samples < self.n_splits * 100:
            print(f"⚠️  Insuficientes datos ({n_samples}) para {self.n_splits} splits")
            print(f"   Se requieren al menos {self.n_splits * 100} samples")
            return []
        
        # Calcular tamaño de cada ventana
        window_size = n_samples // (self.n_splits + 1)
        
        print(f"\n📊 Generando {self.n_splits} ventanas walk-forward:")
        print(f"   Total samples: {n_samples}")
        print(f"   Window size: {window_size} samples")
        
        splits = []
        
        for i in range(self.n_splits):
            # Train: desde inicio hasta ventana i
            train_end = (i + 1) * window_size
            # Test: ventana i+1
            test_start = train_end
            test_end = test_start + window_size
            
            if test_end > n_samples:
                break
            
            train_df = df.iloc[:train_end].copy()
            test_df = df.iloc[test_start:test_end].copy()
            
            splits.append((train_df, test_df))
            
            print(f"   Split {i+1}: Train {len(train_df)} | Test {len(test_df)}")
        
        return splits
    
    def prepare_features_and_labels(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Preparar features (X) y labels (y)"""
        
        if 'label' not in df.columns:
            print("⚠️  No hay columna 'label', creando labels simples...")
            # Crear labels basados en retorno futuro
            if 'close' in df.columns:
                future_return = df['close'].shift(-5) / df['close'] - 1
                df['label'] = 0
                df.loc[future_return > 0.005, 'label'] = 1
                df.loc[future_return < -0.005, 'label'] = 2
                df.dropna(subset=['label'], inplace=True)
                df['label'] = df['label'].astype(int)
        
        # Separar features y labels
        feature_cols = [col for col in df.columns if col != 'label']
        
        # Eliminar columnas no numéricas o con muchos NaN
        feature_cols = [col for col in feature_cols if df[col].dtype in [np.float64, np.int64, float, int]]
        
        X = df[feature_cols].values
        y = df['label'].values
        
        # Eliminar rows con NaN
        mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
        X = X[mask]
        y = y[mask]
        
        return X, y, feature_cols
    
    def run_walk_forward(self, df: pd.DataFrame) -> Dict:
        """
        Ejecutar walk-forward backtest completo
        
        Returns: Dict con resultados de todos los splits
        """
        
        # Generar splits
        splits = self.generate_walk_forward_splits(df)
        
        if not splits:
            return {'error': 'No se pudieron generar splits'}
        
        all_metrics = []
        
        print(f"\n{'='*60}")
        print(f"🔄 EJECUTANDO WALK-FORWARD BACKTEST")
        print(f"{'='*60}\n")
        
        for i, (train_df, test_df) in enumerate(splits, 1):
            print(f"\n--- Split {i}/{len(splits)} ---")
            
            try:
                # Preparar datos
                X_train, y_train, feature_cols = self.prepare_features_and_labels(train_df)
                X_test, y_test, _ = self.prepare_features_and_labels(test_df)
                
                if len(X_train) == 0 or len(X_test) == 0:
                    print(f"⚠️  Datos vacíos después de limpiar NaN")
                    continue
                
                # Entrenar modelo
                model = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    random_state=42,
                    class_weight='balanced',
                    n_jobs=-1
                )
                
                model.fit(X_train, y_train)
                
                # Predecir en test
                y_pred = model.predict(X_test)
                
                # Calcular métricas
                metrics = {
                    'split': i,
                    'train_samples': len(X_train),
                    'test_samples': len(X_test),
                    'accuracy': accuracy_score(y_test, y_pred),
                    'precision': precision_score(y_test, y_pred, average='weighted', zero_division=0),
                    'recall': recall_score(y_test, y_pred, average='weighted', zero_division=0),
                    'f1': f1_score(y_test, y_pred, average='weighted', zero_division=0)
                }
                
                all_metrics.append(metrics)
                
                print(f"   Accuracy:  {metrics['accuracy']:.2%}")
                print(f"   Precision: {metrics['precision']:.2%}")
                print(f"   Recall:    {metrics['recall']:.2%}")
                print(f"   F1 Score:  {metrics['f1']:.2%}")
                
            except Exception as e:
                print(f"❌ Error en split {i}: {str(e)}")
                continue
        
        # Calcular estadísticas agregadas
        if not all_metrics:
            return {'error': 'No se completó ningún split'}
        
        results_df = pd.DataFrame(all_metrics)
        
        summary = {
            'coin': self.coin,
            'n_splits': len(all_metrics),
            'splits_completed': len(all_metrics),
            'metrics_by_split': all_metrics,
            'summary': {
                'accuracy_mean': results_df['accuracy'].mean(),
                'accuracy_std': results_df['accuracy'].std(),
                'precision_mean': results_df['precision'].mean(),
                'precision_std': results_df['precision'].std(),
                'recall_mean': results_df['recall'].mean(),
                'recall_std': results_df['recall'].std(),
                'f1_mean': results_df['f1'].mean(),
                'f1_std': results_df['f1'].std()
            },
            'consistency_score': self._calculate_consistency_score(results_df)
        }
        
        return summary
    
    def _calculate_consistency_score(self, results_df: pd.DataFrame) -> Dict:
        """
        Calcular score de consistencia del modelo
        
        Un modelo consistente tiene baja desviación estándar entre splits
        """
        
        accuracy_std = results_df['accuracy'].std()
        f1_std = results_df['f1'].std()
        
        # Score de consistencia (0-100%)
        # Menor std = más consistente
        consistency_accuracy = max(0, 100 - (accuracy_std * 100 * 5))
        consistency_f1 = max(0, 100 - (f1_std * 100 * 5))
        
        # Determinar si hay overfitting
        is_overfitting = accuracy_std > 0.05 or f1_std > 0.05
        
        return {
            'accuracy_consistency': consistency_accuracy,
            'f1_consistency': consistency_f1,
            'overall_consistency': (consistency_accuracy + consistency_f1) / 2,
            'is_overfitting': is_overfitting,
            'interpretation': self._interpret_consistency(consistency_accuracy, is_overfitting)
        }
    
    def _interpret_consistency(self, consistency: float, is_overfitting: bool) -> str:
        """Interpretar score de consistencia"""
        
        if is_overfitting:
            return "⚠️ POSIBLE OVERFITTING - El modelo varía mucho entre ventanas"
        elif consistency >= 80:
            return "✅ MUY CONSISTENTE - Modelo robusto"
        elif consistency >= 60:
            return "✅ CONSISTENTE - Modelo aceptablemente robusto"
        else:
            return "⚠️ POCO CONSISTENTE - Revisar features o parámetros"
    
    def generate_report(self, summary: Dict) -> Path:
        """Generar reporte en Markdown"""
        
        report = f"""# 🚶 Walk-Forward Backtest Report - {self.coin}

_Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_

---

## 📊 Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Moneda** | {self.coin} |
| **N° Splits** | {summary['n_splits']} |
| **Splits Completados** | {summary['splits_completed']} |
| **Consistencia General** | {summary['consistency_score']['overall_consistency']:.1f}% |
| **Overfitting Detectado** | {'⚠️ SÍ' if summary['consistency_score']['is_overfitting'] else '✅ NO'} |

---

## 🎯 Métricas por Split

| Split | Accuracy | Precision | Recall | F1 Score |
|-------|----------|-----------|--------|----------|
"""
        
        # Agregar métricas por split
        for split_metrics in summary['metrics_by_split']:
            report += f"| {split_metrics['split']} | {split_metrics['accuracy']:.2%} | {split_metrics['precision']:.2%} | {split_metrics['recall']:.2%} | {split_metrics['f1']:.2%} |\n"
        
        report += f"""
---

## 📈 Estadísticas Agregadas

### Accuracy
- **Media:** {summary['summary']['accuracy_mean']:.2%}
- **Desviación Std:** {summary['summary']['accuracy_std']:.2%}
- **Consistencia:** {summary['consistency_score']['accuracy_consistency']:.1f}%

### F1 Score
- **Media:** {summary['summary']['f1_mean']:.2%}
- **Desviación Std:** {summary['summary']['f1_std']:.2%}
- **Consistencia:** {summary['consistency_score']['f1_consistency']:.1f}%

---

## 🔍 Interpretación

{summary['consistency_score']['interpretation']}

### Criterios de Evaluación:

| Consistencia | Interpretación | Acción Recomendada |
|--------------|----------------|---------------------|
| >80% | ✅ Muy consistente | Modelo listo para producción |
| 60-80% | ✅ Consistente | Aceptable, monitorear |
| 40-60% | ⚠️ Poco consistente | Revisar features/parámetros |
| <40% | ❌ Inconsistente | Re-entrenar o cambiar modelo |

---

## 💡 Recomendaciones

{'**✅ MODELO ROBUSTO** - Las métricas son consistentes entre ventanas. El modelo no muestra overfitting y puede usarse en producción.' if not summary['consistency_score']['is_overfitting'] else '**⚠️ POSIBLE OVERFITTING** - Las métricas varían significativamente entre ventanas. Se recomienda:'}

{'- ✅ Proceder con producción' if not summary['consistency_score']['is_overfitting'] else '- Reducir complejidad del modelo (menos features, menor max_depth)'}
{'- Monitorear performance en vivo' if not summary['consistency_score']['is_overfitting'] else '- Aumentar datos de entrenamiento'}
{'' if not summary['consistency_score']['is_overfitting'] else '- Considerar regularización más fuerte'}
{'' if not summary['consistency_score']['is_overfitting'] else '- Validar con Monte Carlo analysis'}

---

## 📝 Notas Técnicas

- **Walk-forward splits:** {summary['n_splits']} ventanas consecutivas
- **Train size:** ~{summary['metrics_by_split'][0]['train_samples'] if summary['metrics_by_split'] else 'N/A'} samples por split
- **Test size:** ~{summary['metrics_by_split'][0]['test_samples'] if summary['metrics_by_split'] else 'N/A'} samples por split
- **Modelo:** Random Forest (100 estimators, max_depth=10)
- **Clases balanceadas:** Sí (class_weight='balanced')

---

_Generado por Perrobotillo Walk-Forward Backtest Engine 🐕_  
*"¡Nunca confiar, siempre verificar!"*_
"""
        
        # Guardar reporte
        report_file = REPORTS_DIR / f"walk_forward_{self.coin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n💾 Reporte guardado en: {report_file}")
        
        # Guardar resumen JSON también
        json_file = REPORTS_DIR / f"walk_forward_{self.coin}_summary.json"
        
        with open(json_file, 'w') as f:
            json.dump(summary, f, indent=2, cls=NumpyEncoder)
        
        return report_file


# ════════════════════════════════════════════════════════
# FUNCIONES DE UTILIDAD
# ════════════════════════════════════════════════════════

def run_walk_forward_for_coin(coin: str, days: int = 90, n_splits: int = 5):
    """Ejecutar walk-forward backtest para una moneda"""
    
    engine = WalkForwardBacktest(coin, n_splits)
    
    # Cargar datos
    df = engine.load_data(days)
    
    if df is None or len(df) == 0:
        print(f"❌ No hay datos para {coin}")
        return None
    
    # Ejecutar walk-forward
    summary = engine.run_walk_forward(df)
    
    if 'error' in summary:
        print(f"❌ Error: {summary['error']}")
        return None
    
    # Generar reporte
    report_file = engine.generate_report(summary)
    
    # Imprimir resumen final
    print(f"\n{'='*60}")
    print(f"🏆 RESUMEN FINAL - {coin}")
    print(f"{'='*60}")
    print(f"Accuracy Media: {summary['summary']['accuracy_mean']:.2%} (+/- {summary['summary']['accuracy_std']:.2%})")
    print(f"F1 Score Medio: {summary['summary']['f1_mean']:.2%} (+/- {summary['summary']['f1_std']:.2%})")
    print(f"Consistencia: {summary['consistency_score']['overall_consistency']:.1f}%")
    print(f"Overfitting: {'⚠️ DETECTADO' if summary['consistency_score']['is_overfitting'] else '✅ NO DETECTADO'}")
    print(f"{'='*60}\n")
    
    return summary


def run_walk_forward_all_coins(days: int = 90, n_splits: int = 5):
    """Ejecutar walk-forward para todas las monedas"""
    
    print(f"\n{'='*60}")
    print("🚶 WALK-FORWARD BACKTEST - TODAS LAS MONEDAS")
    print(f"{'='*60}\n")
    
    all_results = {}
    
    for coin in COINS:
        try:
            result = run_walk_forward_for_coin(coin, days, n_splits)
            if result:
                all_results[coin] = result
        except Exception as e:
            print(f"❌ Error con {coin}: {str(e)}")
            continue
    
    # Resumen final consolidado
    print(f"\n{'='*60}")
    print("📊 RESUMEN CONSOLIDADO")
    print(f"{'='*60}")
    print(f"{'Coin':<6} | {'Accuracy':<12} | {'F1 Score':<12} | {'Consistencia':<12} | {'Status'}")
    print("-"*70)
    
    for coin, result in all_results.items():
        accuracy = result['summary']['accuracy_mean']
        f1 = result['summary']['f1_mean']
        consistency = result['consistency_score']['overall_consistency']
        status = "✅ OK" if not result['consistency_score']['is_overfitting'] else "⚠️ Overfit"
        
        print(f"{coin:<6} | {accuracy:>9.2%} | {f1:>9.2%} | {consistency:>9.1f}% | {status}")
    
    print(f"{'='*60}\n")
    
    # Guardar resumen consolidado
    summary_file = REPORTS_DIR / f"walk_forward_summary_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(summary_file, 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'days': days,
            'n_splits': n_splits,
            'results': {
                coin: {
                    'accuracy_mean': r['summary']['accuracy_mean'],
                    'f1_mean': r['summary']['f1_mean'],
                    'consistency': r['consistency_score']['overall_consistency'],
                    'is_overfitting': bool(r['consistency_score']['is_overfitting'])
                }
                for coin, r in all_results.items()
            }
        }, f, indent=2, cls=NumpyEncoder)
    
    return all_results


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        splits = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        run_walk_forward_all_coins(days, splits)
    elif len(sys.argv) > 1:
        coin = sys.argv[1].upper()
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        splits = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        run_walk_forward_for_coin(coin, days, splits)
    else:
        print("Uso: python3 walk_forward_backtest.py [--all|<COIN>] [days] [n_splits]")
        print("Ejemplo: python3 walk_forward_backtest.py BTC 90 5")
        print("Ejemplo: python3 walk_forward_backtest.py --all 60 5")
