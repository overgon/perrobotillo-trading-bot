#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - ML PIPELINE OPTIMIZADO (ANTI-OVERFITTING)
# ════════════════════════════════════════════════════════
# Versión optimizada para reducir overfitting detectado por Walk-Forward
# Inspirado en Intelligent Trading Bot best practices
# ════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
import os
import joblib
from typing import Dict, List, Tuple
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, mutual_info_classif
from imblearn.over_sampling import SMOTE
import warnings
warnings.filterwarnings('ignore')

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN ANTI-OVERFITTING
# ════════════════════════════════════════════════════════

WORKSPACE = Path(os.path.expanduser('~/.openclaw/workspace'))
ML_DIR = WORKSPACE / "ml"
MODELS_DIR = ML_DIR / "models_optimized"  # Carpeta separada para modelos optimizados
FEATURES_DIR = ML_DIR / "features"
REPORTS_DIR = ML_DIR / "reports"

for dir_path in [MODELS_DIR, FEATURES_DIR, REPORTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Parámetros optimizados para reducir overfitting
OPTIMIZED_CONFIG = {
    'max_features': 'sqrt',        # Menos features por árbol
    'max_depth': 8,                # Reducido de 10 a 8
    'min_samples_split': 20,       # Aumentado de 2 a 20 (más regularización)
    'min_samples_leaf': 10,        # Aumentado de 1 a 10
    'n_estimators': 150,           # Más estimators (pero más simples)
    'class_weight': 'balanced',
    'random_state': 42
}

# Overrides por moneda para casos con overfitting alto
COIN_CONFIG_OVERRIDES = {
    'LINK': {
        'max_depth': 6,                # Reducido de 7 → 6: menos capacidad de sobreajuste
        'min_samples_split': 50,       # Aumentado de 40 → 50: más regularización
        'min_samples_leaf': 25,        # Aumentado de 20 → 25: leaves más grandes
        'n_estimators': 300,           # Más árboles para estabilidad con profundidad reducida
        'max_features': 'log2',        # Menos features por árbol
        'max_leaf_nodes': 15,          # Reducido de 20 → 15: limitar complejidad
        'class_weight': 'balanced',
        'random_state': 123,           # Seed de diversidad
        'ccp_alpha': 0.02              # Endurecido de 0.01 → 0.02: pruning fuerte para LINK con 90 días
    },
    'XRP': {
        'max_depth': 6,
        'min_samples_split': 35,
        'min_samples_leaf': 20,
        'n_estimators': 200,
        'max_features': 'sqrt',
        'max_leaf_nodes': 30,
        'class_weight': 'balanced',
        'random_state': 42,
        'ccp_alpha': 0.003
    },
    'AVAX': {
        'max_depth': 5,                # Reducido de 7 → 5: depth muy controlada
        'min_samples_split': 50,       # Regularización alta
        'min_samples_leaf': 25,        # Leaves grandes
        'n_estimators': 300,           # Más árboles para estabilidad
        'max_features': 'log2',        # Menos features por árbol (vs sqrt)
        'max_leaf_nodes': 20,          # Limitar hojas
        'class_weight': 'balanced',
        'random_state': 42,
        'ccp_alpha': 0.02              # Pruning muy fuerte
    }
}

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX", "ZEC"]

# ════════════════════════════════════════════════════════
# OPTIMIZED ML PIPELINE
# ════════════════════════════════════════════════════════

class OptimizedMLPipeline:
    """
    ML Pipeline optimizado para reducir overfitting
    
    Mejoras vs versión anterior:
    1. Menor complejidad (max_depth: 8 vs 10)
    2. Más regularización (min_samples_split: 20 vs 2)
    3. Feature selection (SelectKBest)
    4. Cross-validation más estricto
    """
    
    def __init__(self, coin: str, use_feature_selection: bool = True):
        self.coin = coin.upper()
        self.use_feature_selection = use_feature_selection
        self.model = None
        self.scaler = StandardScaler()
        self.feature_selector = None
        self.selected_features = []
        
        # Paths específicos para modelos optimizados
        self.model_path = MODELS_DIR / f"{self.coin}_optimized_model.pkl"
        self.metadata_path = MODELS_DIR / f"{self.coin}_optimized_metadata.json"
    
    def load_data(self, days: int = 90, last_n: int | None = None) -> pd.DataFrame:
        """Cargar datos desde features generados
        
        Args:
          days: si last_n es None y days > 0, usa solo los últimos días por fecha.
          last_n: si se indica, mezcla esa ventana reciente priorizada y completa lo necesario para llegar a un mínimo viable.
        """
        
        features_file = FEATURES_DIR / f"{self.coin}_features.csv"
        
        if not features_file.exists():
            print(f"❌ No hay features para {self.coin}")
            return pd.DataFrame()
        
        df = pd.read_csv(features_file)
        
        # Intentar cortar por fecha si existe columna temporal
        time_col = None
        for col in ['timestamp', 'open_time', 'close_time', 'time', 'datetime']:
            if col in df.columns:
                time_col = col
                break
        
        if last_n is not None and last_n > 0:
            if time_col is not None:
                try:
                    time_vals = pd.to_datetime(df[time_col], errors='coerce')
                    latest_time = time_vals.dropna().max()
                    window = df.loc[time_vals >= latest_time - pd.Timedelta(minutes=5*1440*days) // days if days else latest_time - pd.to_timedelta(last_n, unit='m')]
                except Exception:
                    window = df.tail(last_n)
                
                needed = max(60, int(last_n * 1.5))
                df_recent = window.tail(last_n)
                df_backfill = df.iloc[:-len(df_recent)].tail(needed - len(df_recent))
                df = pd.concat([df_backfill, df_recent], ignore_index=True)
                print(f"✅ Ventana reciente: {len(df_recent)} samples + backfill {len(df_backfill)} = {len(df)} samples")
            else:
                df = pd.concat([df.iloc[:-last_n].tail(max(0, 60 - last_n)), df.tail(last_n)], ignore_index=True)
                print(f"✅ Últimos {last_n} samples usados con backfill mínimo: {len(df)} samples")
        elif time_col is not None:
            try:
                time_vals = pd.to_datetime(df[time_col], errors='coerce')
                latest_time = time_vals.dropna().max()
                cutoff = latest_time - pd.Timedelta(minutes=min(days, 60) * 1440)
                df = df.loc[time_vals >= cutoff].copy()
            except Exception:
                pass
            print(f"✅ Datos filtrados por ventana: {len(df)} samples")
        else:
            print(f"✅ {len(df)} samples cargados")
        
        return df
    
    def select_best_features(self, X: np.ndarray, y: np.ndarray, feature_names: List[str], k: int = None) -> List[int]:
        """
        Feature selection usando SelectKBest con mutual information
        
        k: Número de features a seleccionar (default: sqrt(n_features) o override por moneda)
        """
        
        n_features = X.shape[1]
        
        # Override por moneda: LINK usa features reducidas para mitigar overfitting
        coin_k_override = {'LINK': 5, 'XRP': 14}
        if k is None:
            k = coin_k_override.get(self.coin, int(np.sqrt(n_features)))
        
        print(f"\n🔍 FEATURE SELECTION")
        print(f"   Features originales: {n_features}")
        print(f"   Features a seleccionar: {k}")
        
        try:
            selector = SelectKBest(score_func=mutual_info_classif, k=k)
            selector.fit(X, y)
            
            # Obtener índices de features seleccionados
            selected_indices = np.where(selector.get_support())[0]
            
            print(f"   ✅ {len(selected_indices)} features seleccionados")
            
            # Mostrar top 10 features
            scores = selector.scores_[selected_indices]
            top_10 = selected_indices[np.argsort(scores)[-10:]]
            
            print(f"   Top features:")
            for i, idx in enumerate(top_10):
                print(f"      {i+1}. {feature_names[idx]} (score: {scores[i]:.4f})")
            
            return selected_indices.tolist()
            
        except Exception as e:
            print(f"⚠️  Error en feature selection: {e}")
            print(f"   Usando todos los features")
            return list(range(n_features))
    
    def train(self, df: pd.DataFrame, test_size: float = 0.2) -> Dict:
        """Entrenar modelo con configuración anti-overfitting"""
        
        print(f"\n{'='*60}")
        print(f"🧠 ENTRENAMIENTO OPTIMIZADO - {self.coin}")
        print(f"{'='*60}")
        
        if df is None or len(df) == 0:
            return {'error': 'No hay datos'}
        
        # Preparar datos
        feature_cols = [col for col in df.columns if col != 'label']
        X = df[feature_cols].values
        y = df['label'].values
        
        # Limpiar NaN
        mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
        X = X[mask]
        y = y[mask]
        feature_cols_clean = feature_cols
        
        print(f"\n📊 Datos limpios: {len(X)} samples, {len(feature_cols_clean)} features")
        
        # Feature selection (opcional)
        if self.use_feature_selection:
            # LINK: excluir features de volumen para reducir overfitting ruidoso
            if self.coin == 'LINK':
                vol_features = [c for c in feature_cols_clean if 'volume' in c.lower()]
                non_vol_features = [c for c in feature_cols_clean if c not in vol_features]
                if non_vol_features:
                    non_vol_idx = [feature_cols_clean.index(c) for c in non_vol_features]
                    X = X[:, non_vol_idx]
                    print(f"   🔧 LINK: excluyendo {len(vol_features)} features de volumen, usando {len(non_vol_features)} features de precio/indicadores")
                    
                    # LINK: usar 8 features críticas para 90 días (más datos = mejor señal con más features)
                    selected_indices = self.select_best_features(X, y, non_vol_features, k=8)
                    X = X[:, selected_indices]
                    self.selected_features = [non_vol_features[i] for i in selected_indices]
                else:
                    selected_indices = self.select_best_features(X, y, feature_cols_clean)
                    X = X[:, selected_indices]
                    self.selected_features = [feature_cols_clean[i] for i in selected_indices]
            else:
                selected_indices = self.select_best_features(X, y, feature_cols_clean)
                X = X[:, selected_indices]
                self.selected_features = [feature_cols_clean[i] for i in selected_indices]
            print(f"   Después de feature selection: {X.shape[1]} features")
        
        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        print(f"\n📈 Train: {len(X_train)} | Test: {len(X_test)}")
        
        # Escalar features
        print("\n⚖️  Escalando features...")
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Crear modelo optimizado
        print(f"\n🤖 Entrenando Random Forest optimizado...")
        config = COIN_CONFIG_OVERRIDES.get(self.coin, OPTIMIZED_CONFIG)
        print(f"   max_depth: {config.get('max_depth', OPTIMIZED_CONFIG['max_depth'])}")
        print(f"   min_samples_split: {config.get('min_samples_split', OPTIMIZED_CONFIG['min_samples_split'])}")
        print(f"   min_samples_leaf: {config.get('min_samples_leaf', OPTIMIZED_CONFIG['min_samples_leaf'])}")
        print(f"   max_features: {config.get('max_features', OPTIMIZED_CONFIG['max_features'])}")
        print(f"   n_estimators: {config.get('n_estimators', OPTIMIZED_CONFIG['n_estimators'])}")
        
        self.model = RandomForestClassifier(**config)
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluar
        print("\n📊 Evaluando...")
        y_pred = self.model.predict(X_test_scaled)
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, average='weighted', zero_division=0),
            'recall': recall_score(y_test, y_pred, average='weighted', zero_division=0),
            'f1': f1_score(y_test, y_pred, average='weighted', zero_division=0)
        }
        
        print(f"   Accuracy:  {metrics['accuracy']:.2%}")
        print(f"   Precision: {metrics['precision']:.2%}")
        print(f"   Recall:    {metrics['recall']:.2%}")
        print(f"   F1 Score:  {metrics['f1']:.2%}")
        
        # Cross-validation estricto (10 folds)
        print("\n🔄 Cross-validation (10 folds)...")
        cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=StratifiedKFold(10, shuffle=True, random_state=42))
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()
        
        print(f"   CV Score: {cv_mean:.2%} (+/- {cv_std:.2%})")
        metrics['cv_mean'] = cv_mean
        metrics['cv_std'] = cv_std
        
        # Medir overfitting usando CV como proxy de generalization score
        # Esto es más estable que train/test gap, especialmente para datasets imbalanced
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        overfitting_gap = train_score - cv_mean  # CV es mejor proxy para generalización

        print(f"\n📊 Overfitting Analysis (CV-adjusted):")
        print(f"   Train score: {train_score:.2%}")
        print(f"   Test score:  {test_score:.2%}")
        print(f"   CV score:    {cv_mean:.2%}")
        print(f"   Gap (train-CV): {overfitting_gap:.2%} ({'✅ OK' if overfitting_gap < 0.05 else '⚠️ Alto'})")
        
        metrics['train_score'] = train_score
        metrics['test_score'] = test_score
        metrics['overfitting_gap'] = overfitting_gap
        
        # Guardar modelo
        print(f"\n💾 Guardando modelo optimizado...")
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, MODELS_DIR / f"{self.coin}_scaler_optimized.pkl")
        
        if self.use_feature_selection:
            joblib.dump(self.selected_features, MODELS_DIR / f"{self.coin}_selected_features.pkl")
        
        # Metadata
        metadata = {
            'coin': self.coin,
            'trained_at': datetime.now().isoformat(),
            'config': config,  # ✅ Config actual (incluye overrides por moneda)
            'use_feature_selection': self.use_feature_selection,
            'n_features_original': len(feature_cols_clean),
            'n_features_selected': len(self.selected_features) if self.use_feature_selection else len(feature_cols_clean),
            'samples': len(X),
            'metrics': metrics,
            'is_optimized': True
        }
        
        with open(self.metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"   ✅ Modelo guardado en: {self.model_path}")
        
        return metrics


def run_optimized_training(coin: str, days: int = 90):
    """Ejecutar entrenamiento optimizado para una moneda"""
    
    print(f"\n{'='*60}")
    print(f"🚀 ENTRENAMIENTO OPTIMIZADO - {coin}")
    print(f"{'='*60}")
    
    pipeline = OptimizedMLPipeline(coin, use_feature_selection=True)
    
    # Cargar datos
    df = pipeline.load_data(days)
    
    if df is None or len(df) == 0:
        print(f"❌ No hay datos para {coin}")
        return None
    
    # Entrenar
    metrics = pipeline.train(df)
    
    if 'error' in metrics:
        print(f"❌ Error: {metrics['error']}")
        return None
    
    # Resumen final
    print(f"\n{'='*60}")
    print(f"🏆 RESUMEN - {coin} Optimizado")
    print(f"{'='*60}")
    print(f"Accuracy: {metrics['accuracy']:.2%}")
    print(f"F1 Score: {metrics['f1']:.2%}")
    print(f"CV Score: {metrics['cv_mean']:.2%} (+/- {metrics['cv_std']:.2%})")
    print(f"Overfitting Gap: {metrics['overfitting_gap']:.2%}")
    
    if metrics['overfitting_gap'] < 0.05:
        print(f"\n✅ OVERFITTING REDUCIDO EXITOSAMENTE")
    else:
        print(f"\n⚠️  Aún hay overfitting, considerar más regularización")
    
    print(f"{'='*60}\n")
    
    return metrics


def run_all_coins_optimized(days: int = 90):
    """Entrenar todas las monedas con configuración optimizada"""
    
    print(f"\n{'='*60}")
    print("🚀 ENTRENAMIENTO OPTIMIZADO - TODAS LAS MONEDAS")
    print(f"{'='*60}\n")
    
    results = {}
    
    for coin in COINS:
        try:
            metrics = run_optimized_training(coin, days)
            if metrics:
                results[coin] = metrics
        except Exception as e:
            print(f"❌ Error con {coin}: {str(e)}")
            continue
    
    # Resumen consolidado
    print(f"\n{'='*60}")
    print("📊 RESUMEN CONSOLIDADO - MODELOS OPTIMIZADOS")
    print(f"{'='*60}")
    print(f"{'Coin':<6} | {'Accuracy':<12} | {'F1 Score':<12} | {'Overfit Gap':<12} | {'Status'}")
    print("-"*70)
    
    for coin, metrics in results.items():
        accuracy = metrics['accuracy']
        f1 = metrics['f1']
        gap = metrics['overfitting_gap']
        status = "✅ OK" if gap < 0.05 else "⚠️ Overfit"
        
        print(f"{coin:<6} | {accuracy:>9.2%} | {f1:>9.2%} | {gap:>9.2%} | {status}")
    
    print(f"{'='*60}\n")
    
    return results


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    import os
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        run_all_coins_optimized(days)
    elif len(sys.argv) > 1:
        coin = sys.argv[1].upper()
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        run_optimized_training(coin, days)
    else:
        print("Uso: python3 ml_pipeline_optimized.py [--all|<COIN>] [days]")
        print("Ejemplo: python3 ml_pipeline_optimized.py BTC 90")
        print("Ejemplo: python3 ml_pipeline_optimized.py --all 60")
