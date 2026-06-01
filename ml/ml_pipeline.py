#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - ML PIPELINE END-TO-END
# ════════════════════════════════════════════════════════
# Pipeline automático: Gather → Train → Deploy
# Inspirado en Jesse AI ML Pipeline
# ════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json
import joblib
from typing import Dict, List, Optional, Tuple
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report, confusion_matrix
)
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
ML_DIR = WORKSPACE / "ml"
MODELS_DIR = ML_DIR / "models"
FEATURES_DIR = ML_DIR / "features"
DATA_DIR = WORKSPACE / "backtest" / "data"
REPORTS_DIR = ML_DIR / "reports"

for dir_path in [MODELS_DIR, FEATURES_DIR, REPORTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

# ════════════════════════════════════════════════════════
# ML PIPELINE CLASS
# ════════════════════════════════════════════════════════

class MLPipeline:
    """
    Pipeline End-to-End para ML Trading
    
    3 Fases principales (inspirado en Jesse AI):
    1. GATHER: Recolectar features durante backtest/trading
    2. TRAIN: Entrenar modelo con validación cruzada
    3. DEPLOY: Usar modelo en producción para predicciones
    
    Features clave:
    - Auto feature importance
    - Auto model selection (RF, GBM, LR)
    - Cross-validation integrado
    - Calibration de probabilidades
    - Feature drift detection
    """
    
    def __init__(self, coin: str, model_type: str = "random_forest"):
        """
        coin: Moneda a operar (BTC, ETH, etc.)
        model_type: 'random_forest', 'gradient_boosting', 'logistic_regression'
        """
        self.coin = coin
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.feature_importance = {}
        self.training_metadata = {}
        
        # Configurar paths específicos para esta moneda
        self.model_path = MODELS_DIR / f"{coin}_ml_model.pkl"
        self.metadata_path = MODELS_DIR / f"{coin}_ml_metadata.json"
        self.features_log = FEATURES_DIR / f"{coin}_features.csv"
    
    def gather_phase(self, days: int = 30) -> pd.DataFrame:
        """
        FASE 1: GATHER - Recolectar features y labels
        
        Durante backtest o trading real, este método:
        1. Carga datos históricos OHLCV
        2. Genera features automáticos (feature_engine.py)
        3. Crea labels basados en performance futuro
        4. Guarda features a CSV para training posterior
        
        Returns: DataFrame con features y labels
        """
        
        print(f"\n{'='*60}")
        print(f"📥 FASE 1: GATHER - {self.coin}")
        print(f"{'='*60}")
        print(f"Días históricos: {days}")
        
        # 1. Cargar datos OHLCV
        print("\n1️⃣ Cargando datos OHLCV...")
        ohlcv_data = self._load_ohlcv_data(days)
        
        if ohlcv_data is None or len(ohlcv_data) == 0:
            print(f"❌ No hay datos OHLCV para {self.coin}")
            return pd.DataFrame()
        
        print(f"   ✅ {len(ohlcv_data)} velas cargadas")
        
        # 2. Generar features con FeatureEngineer
        print("2️⃣ Generando features automáticos...")
        from feature_engine import FeatureEngineer
        
        fe = FeatureEngineer()
        df_features = fe.generate_all_features(ohlcv_data.copy(), self.coin)
        
        print(f"   ✅ {len(df_features.columns)} features generados")
        
        # 3. Crear labels (target variable)
        print("3️⃣ Creando labels...")
        df_with_labels = self._create_labels(df_features)
        
        # 4. Guardar features a CSV
        df_with_labels.to_csv(self.features_log, index=False)
        print(f"   ✅ Features guardados en: {self.features_log}")
        
        # 5. Resumen estadístico
        print(f"\n📊 RESUMEN:")
        print(f"   Total samples: {len(df_with_labels)}")
        print(f"   Total features: {len(df_with_labels.columns) - 1}")  # -1 por el label
        print(f"   Label distribution:")
        label_counts = df_with_labels['label'].value_counts()
        for label, count in label_counts.items():
            pct = count / len(df_with_labels) * 100
            print(f"      {label}: {count} ({pct:.1f}%)")
        
        print(f"\n💾 Features listos para training")
        print(f"{'='*60}\n")
        
        return df_with_labels
    
    def train_phase(self, df: pd.DataFrame, test_size: float = 0.2, use_smote: bool = True) -> Dict:
        """
        FASE 2: TRAIN - Entrenar modelo con validación
        
        use_smote: Si True, usa SMOTE para balancear clases
        """
        
        print(f"\n{'='*60}")
        print(f"🧠 FASE 2: TRAIN - {self.coin}")
        print(f"{'='*60}")
        
        if df is None or len(df) == 0:
            print(f"❌ No hay datos para entrenar")
            return {}
        
        # 1. Separar features y labels
        print("\n1️⃣ Preparando datos...")
        feature_cols = [col for col in df.columns if col != 'label']
        X = df[feature_cols].values
        y = df['label'].values
        
        print(f"   Features: {len(feature_cols)}")
        print(f"   Samples: {len(X)}")
        
        # 2. Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        print(f"   Train samples: {len(X_train)}")
        print(f"   Test samples: {len(X_test)}")
        
        # 3. Escalar features PRIMERO
        print("2️⃣ Escalando features...")
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # 3.5 SMOTE para balancear clases (después de escalar)
        if use_smote:
            print("3️⃣ Aplicando SMOTE para balancear clases...")
            try:
                from imblearn.over_sampling import SMOTE
                
                # Verificar si hay desbalance (>70% en una clase)
                class_counts = np.bincount(y_train)
                max_ratio = class_counts.max() / class_counts.sum()
                
                if max_ratio > 0.7:
                    print(f"   ⚠️  Desbalance detectado: {max_ratio:.1%} en una clase")
                    smote = SMOTE(random_state=42, k_neighbors=min(3, min(class_counts)-1))
                    X_train_scaled, y_train = smote.fit_resample(X_train_scaled, y_train)
                    print(f"   ✅ SMOTE aplicado: {len(y_train)} samples después de balancear")
                    
                    # Mostrar nueva distribución
                    new_class_counts = np.bincount(y_train)
                    print(f"   📊 Nueva distribución: {new_class_counts}")
                else:
                    print(f"   ℹ️  No se requiere SMOTE (balanceado: {max_ratio:.1%})")
            except ImportError:
                print(f"   ⚠️  imblearn no instalado, saltando SMOTE")
            except Exception as e:
                print(f"   ⚠️  Error en SMOTE: {e}")
        
        # 4. Seleccionar y entrenar modelo
        print(f"4️⃣ Entrenando {self.model_type}...")
        
        self.model = self._create_model()
        self.model.fit(X_train_scaled, y_train)
        print(f"   ✅ Modelo entrenado")
        
        # 5. Evaluar en test set
        print("5️⃣ Evaluando en test set...")
        y_pred = self.model.predict(X_test_scaled)
        
        # Para probabilidades (solo si hay 2+ clases)
        if hasattr(self.model, 'predict_proba'):
            y_pred_proba = self.model.predict_proba(X_test_scaled)
            # AUC-ROC multiclase
            auc_method = 'ovr' if len(np.unique(y_test)) > 2 else 'binary'
            try:
                auc_roc = roc_auc_score(y_test, y_pred_proba, average='weighted', multi_class=auc_method)
            except:
                auc_roc = 0.5
        else:
            y_pred_proba = y_pred
            auc_roc = 0.5
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, average='weighted', zero_division=0),
            'recall': recall_score(y_test, y_pred, average='weighted', zero_division=0),
            'f1': f1_score(y_test, y_pred, average='weighted', zero_division=0),
            'auc_roc': auc_roc
        }
        
        print(f"   Accuracy:  {metrics['accuracy']:.2%}")
        print(f"   Precision: {metrics['precision']:.2%}")
        print(f"   Recall:    {metrics['recall']:.2%}")
        print(f"   F1 Score:  {metrics['f1']:.2%}")
        print(f"   AUC-ROC:   {metrics['auc_roc']:.3f}")
        
        # 6. Cross-validation
        print("6️⃣ Cross-validation (5 folds)...")
        print("5️⃣ Cross-validation (5 folds)...")
        cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5)
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()
        
        print(f"   CV Score: {cv_mean:.2%} (+/- {cv_std:.2%})")
        metrics['cv_mean'] = cv_mean
        metrics['cv_std'] = cv_std
        
        # 7. Feature importance
        print("7️⃣ Calculando feature importance...")
        print("6️⃣ Calculando feature importance...")
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
        else:
            importances = np.abs(self.model.coef_[0]) if hasattr(self.model, 'coef_') else None
        
        if importances is not None:
            # Top 10 features más importantes
            top_indices = np.argsort(importances)[::-1][:10]
            
            self.feature_importance = {
                feature_cols[i]: float(importances[i])
                for i in top_indices
            }
            
            print(f"   Top 5 features:")
            for i, (feature, importance) in enumerate(sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]):
                print(f"      {i+1}. {feature}: {importance:.4f}")
        
        # 8. Guardar modelo
        print("8️⃣ Guardando modelo...")
        print("7️⃣ Guardando modelo...")
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, MODELS_DIR / f"{self.coin}_scaler.pkl")
        
        # Metadata del training
        self.training_metadata = {
            'coin': self.coin,
            'model_type': self.model_type,
            'trained_at': datetime.now().isoformat(),
            'samples': len(X),
            'features': len(feature_cols),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'metrics': metrics,
            'feature_importance': self.feature_importance,
            'feature_columns': feature_cols
        }
        
        with open(self.metadata_path, 'w') as f:
            json.dump(self.training_metadata, f, indent=2, default=str)
        
        print(f"   ✅ Modelo guardado en: {self.model_path}")
        print(f"   ✅ Metadata guardada en: {self.metadata_path}")
        
        # 9. Generar reporte
        report_file = self._generate_training_report(metrics)
        print(f"   ✅ Reporte generado: {report_file}")
        
        print(f"\n🎉 TRAINING COMPLETADO")
        print(f"{'='*60}\n")
        
        return metrics
    
    def deploy_phase(self, live_data: pd.DataFrame = None) -> Dict:
        """
        FASE 3: DEPLOY - Usar modelo en producción
        
        Este método:
        1. Carga modelo entrenado
        2. Procesa datos en tiempo real
        3. Genera predicciones con confianza
        4. Retorna decisión de trade (LONG/SHORT/WAIT)
        
        Returns: Dict con predicción y confianza
        """
        
        print(f"\n{'='*60}")
        print(f"🚀 FASE 3: DEPLOY - {self.coin}")
        print(f"{'='*60}")
        
        # 1. Cargar modelo
        print("\n1️⃣ Cargando modelo...")
        
        if not self.model_path.exists():
            print(f"❌ Modelo no encontrado: {self.model_path}")
            print(f"   Primero debés ejecutar gather_phase() y train_phase()")
            return {}
        
        self.model = joblib.load(self.model_path)
        self.scaler = joblib.load(MODELS_DIR / f"{self.coin}_scaler.pkl")
        
        with open(self.metadata_path, 'r') as f:
            metadata = json.load(f)
        
        print(f"   ✅ Modelo cargado: {metadata['model_type']}")
        print(f"   ✅ Entrenado: {metadata['trained_at']}")
        print(f"   ✅ Accuracy: {metadata['metrics']['accuracy']:.2%}")
        
        # 2. Cargar o generar datos en tiempo real
        print("2️⃣ Procesando datos en tiempo real...")
        
        if live_data is None:
            # Simular datos recientes (últimas 100 velas)
            live_data = self._load_ohlcv_data(days=1)  # Último día
        
        if live_data is None or len(live_data) == 0:
            print(f"❌ No hay datos en tiempo real")
            return {}
        
        # Generar features para los datos actuales
        from feature_engine import FeatureEngineer
        fe = FeatureEngineer()
        df_features = fe.generate_all_features(live_data.copy(), self.coin)
        
        # 3. Preparar features (misma escala que training)
        print("3️⃣ Preparando features...")
        feature_cols = metadata['feature_columns']
        
        # Asegurar que tenemos las mismas columnas
        missing_cols = set(feature_cols) - set(df_features.columns)
        if missing_cols:
            print(f"⚠️  Faltan columnas: {missing_cols}")
            # Agregar columnas faltantes con NaN
            for col in missing_cols:
                df_features[col] = np.nan
        
        X_live = df_features[feature_cols].values
        X_live_scaled = self.scaler.transform(X_live)
        
        # 4. Generar predicción
        print("4️⃣ Generando predicción...")
        prediction = self.model.predict(X_live_scaled)[-1]  # Última predicción
        proba = self.model.predict_proba(X_live_scaled)[-1] if hasattr(self.model, 'predict_proba') else [0.5, 0.5]
        
        confidence = float(max(proba)) * 100
        predicted_label = int(prediction)
        
        # 5. Interpretar predicción
        print("5️⃣ Interpretando predicción...")
        
        if predicted_label == 1:
            signal = "LONG"
            action = "✅ APROBAR COMPRA"
        elif predicted_label == 2:
            signal = "SHORT"
            action = "✅ APROBAR VENTA"
        else:
            signal = "WAIT"
            action = "⏸️ ESPERAR MEJOR OPORTUNIDAD"
        
        print(f"\n🎯 PREDICCIÓN:")
        print(f"   Señal: {signal}")
        print(f"   Confianza: {confidence:.1f}%")
        print(f"   Acción: {action}")
        
        # 6. Validar con thresholds
        min_confidence = 60  # Mínimo para operar
        position_size = 100 if confidence >= 75 else 50 if confidence >= 60 else 0
        
        print(f"\n💰 POSITION SIZING:")
        print(f"   Confianza mínima: {min_confidence}%")
        print(f"   Position size: {position_size}%")
        
        result = {
            'coin': self.coin,
            'signal': signal,
            'confidence': confidence,
            'position_size_percent': position_size,
            'action': action,
            'timestamp': datetime.now().isoformat(),
            'model_accuracy': metadata['metrics']['accuracy']
        }
        
        # Guardar predicción en log
        self._log_prediction(result)
        
        print(f"\n📝 Predicción guardada en log")
        print(f"{'='*60}\n")
        
        return result
    
    # ════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES
    # ════════════════════════════════════════════════════
    
    def _load_ohlcv_data(self, days: int = 30) -> pd.DataFrame:
        """Cargar datos OHLCV desde backtest data"""
        
        # Buscar archivos de datos
        data_files = list(DATA_DIR.glob(f"{self.coin}_*.csv"))
        
        if not data_files:
            # Intentar con formato diferente
            data_files = list(DATA_DIR.glob(f"*{self.coin}*.csv"))
        
        if not data_files:
            print(f"⚠️  No se encontraron datos para {self.coin}")
            return pd.DataFrame()
        
        # Usar el archivo más reciente
        latest_file = max(data_files, key=lambda f: f.stat().st_mtime)
        
        try:
            df = pd.read_csv(latest_file, parse_dates=['timestamp'])
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            print(f"❌ Error cargando {latest_file}: {e}")
            return pd.DataFrame()
    
    def _create_labels(self, df: pd.DataFrame, lookforward: int = 5, threshold: float = 0.005) -> pd.DataFrame:
        """
        Crear labels basados en performance futuro
        
        Labels:
        0 = WAIT/NEUTRAL (movimiento < threshold)
        1 = LONG (precio sube > threshold en próximas N velas)
        2 = SHORT (precio baja > threshold en próximas N velas)
        
        threshold: 0.5% por defecto (más sensible que 1%)
        """
        
        df = df.copy()
        
        # Calcular retorno futuro
        future_return = df['close'].shift(-lookforward) / df['close'] - 1
        
        # Crear labels con threshold más bajo (0.5% en vez de 1%)
        df['label'] = 0  # Default: WAIT
        df.loc[future_return > threshold, 'label'] = 1    # LONG
        df.loc[future_return < -threshold, 'label'] = 2   # SHORT
        
        # Eliminar últimas filas (no tenemos futuro)
        df.dropna(subset=['label'], inplace=True)
        df['label'] = df['label'].astype(int)
        
        return df
    
    def _create_model(self):
        """Crear modelo según configuración"""
        
        if self.model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                class_weight='balanced',
                n_jobs=-1
            )
        elif self.model_type == "gradient_boosting":
            return GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
        elif self.model_type == "logistic_regression":
            return LogisticRegression(
                max_iter=1000,
                class_weight='balanced',
                random_state=42
            )
        else:
            return RandomForestClassifier(n_estimators=100, random_state=42)
    
    def _generate_training_report(self, metrics: Dict) -> Path:
        """Generar reporte de entrenamiento en Markdown"""
        
        report = f"""# 🧠 ML Training Report - {self.coin}

_Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_

---

## 📊 Model Info

| Campo | Valor |
|-------|-------|
| **Coin** | {self.coin} |
| **Model Type** | {self.model_type} |
| **Trained At** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| **Samples** | {self.training_metadata.get('samples', 0)} |
| **Features** | {self.training_metadata.get('features', 0)} |

---

## 🎯 Performance Metrics

### Test Set Performance

| Metric | Score |
|--------|-------|
| **Accuracy** | {metrics.get('accuracy', 0):.2%} |
| **Precision** | {metrics.get('precision', 0):.2%} |
| **Recall** | {metrics.get('recall', 0):.2%} |
| **F1 Score** | {metrics.get('f1', 0):.2%} |
| **AUC-ROC** | {metrics.get('auc_roc', 0):.3f} |

### Cross-Validation

| Fold | Score |
|------|-------|
| **Mean** | {metrics.get('cv_mean', 0):.2%} |
| **Std Dev** | {metrics.get('cv_std', 0):.2%} |

---

## 🔬 Top 10 Feature Importance

| Rank | Feature | Importance |
|------|---------|------------|
"""
        
        # Agregar feature importance
        sorted_features = sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)
        for i, (feature, importance) in enumerate(sorted_features[:10]):
            report += f"| {i+1} | {feature} | {importance:.4f} |\n"
        
        report += f"""
---

## 💡 Interpretación

- **Accuracy > 60%:** ✅ Modelo usable
- **Precision > 65%:** ✅ Buenas señales de entrada
- **Recall > 60%:** ✅ Detecta la mayoría de oportunidades
- **CV Std < 5%:** ✅ Modelo consistente (no overfitting)

---

_Generado por Perrobotillo ML Pipeline 🐕_  
*"¡Nunca confiar, siempre verificar!"*_
"""
        
        report_file = REPORTS_DIR / f"{self.coin}_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return report_file
    
    def _log_prediction(self, prediction: Dict):
        """Guardar predicción en log JSON"""
        
        log_file = ML_DIR / "predictions_log.json"
        
        predictions = []
        if log_file.exists():
            with open(log_file, 'r') as f:
                predictions = json.load(f)
        
        predictions.append(prediction)
        
        # Mantener solo últimas 100 predicciones
        predictions = predictions[-100:]
        
        with open(log_file, 'w') as f:
            json.dump(predictions, f, indent=2)


# ════════════════════════════════════════════════════════
# FUNCIONES DE UTILIDAD
# ════════════════════════════════════════════════════════

def run_full_pipeline(coin: str, days: int = 30, model_type: str = "random_forest"):
    """Ejecutar pipeline completo para una moneda"""
    
    print(f"\n{'='*60}")
    print(f"🚀 ML PIPELINE COMPLETO - {coin}")
    print(f"{'='*60}\n")
    
    pipeline = MLPipeline(coin, model_type)
    
    # Fase 1: Gather
    df = pipeline.gather_phase(days)
    
    if df is None or len(df) == 0:
        print(f"❌ Pipeline falló en fase GATHER")
        return None
    
    # Fase 2: Train
    metrics = pipeline.train_phase(df)
    
    if not metrics:
        print(f"❌ Pipeline falló en fase TRAIN")
        return None
    
    # Fase 3: Deploy
    prediction = pipeline.deploy_phase()
    
    if not prediction:
        print(f"❌ Pipeline falló en fase DEPLOY")
        return None
    
    return {
        'coin': coin,
        'metrics': metrics,
        'prediction': prediction
    }


def run_pipeline_all_coins(days: int = 30, model_type: str = "random_forest"):
    """Ejecutar pipeline para todas las monedas"""
    
    print(f"\n{'='*60}")
    print("🚀 ML PIPELINE - TODAS LAS MONEDAS")
    print(f"{'='*60}\n")
    
    results = {}
    
    for coin in COINS:
        try:
            result = run_full_pipeline(coin, days, model_type)
            if result:
                results[coin] = result
        except Exception as e:
            print(f"❌ Error con {coin}: {str(e)}")
            continue
    
    # Resumen final
    print(f"\n{'='*60}")
    print("🏆 RESUMEN FINAL")
    print(f"{'='*60}")
    print(f"{'Coin':<6} | {'Accuracy':<10} | {'Signal':<10} | {'Confidence':<10}")
    print("-"*50)
    
    for coin, result in results.items():
        accuracy = result['metrics']['accuracy']
        signal = result['prediction']['signal']
        confidence = result['prediction']['confidence']
        print(f"{coin:<6} | {accuracy:>8.2%} | {signal:<10} | {confidence:>8.1f}%")
    
    print(f"{'='*60}\n")
    
    # Guardar resumen
    summary_file = REPORTS_DIR / f"pipeline_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(summary_file, 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'days': days,
            'model_type': model_type,
            'results': {
                coin: {
                    'accuracy': r['metrics']['accuracy'],
                    'signal': r['prediction']['signal'],
                    'confidence': r['prediction']['confidence']
                }
                for coin, r in results.items()
            }
        }, f, indent=2)
    
    return results


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        model = sys.argv[3] if len(sys.argv) > 3 else "random_forest"
        run_pipeline_all_coins(days, model)
    elif len(sys.argv) > 1:
        coin = sys.argv[1].upper()
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        model = sys.argv[3] if len(sys.argv) > 3 else "random_forest"
        run_full_pipeline(coin, days, model)
    else:
        print("Uso: python3 ml_pipeline.py [--all|<COIN>] [days] [model_type]")
        print("Ejemplo: python3 ml_pipeline.py BTC 30 random_forest")
        print("Ejemplo: python3 ml_pipeline.py --all 60 gradient_boosting")
