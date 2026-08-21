#!/usr/bin/env python3
"""Rediseño features LINK: eliminar volumen, entrenar RF regularizado"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

FEATURES = "/home/overgon/.openclaw/workspace/ml/features/LINK_features.csv"
MODELS = "/home/overgon/.openclaw/workspace/ml/models_optimized"

df = pd.read_csv(FEATURES)
feature_cols = [c for c in df.columns if c != 'label']
X = df[feature_cols].values
y = df['label'].values
mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
X, y = X[mask], y[mask]

# Eliminar volumen
vol_features = [c for c in feature_cols if 'volume' in c.lower()]
non_vol = [c for c in feature_cols if c not in vol_features]
keep_idx = [feature_cols.index(c) for c in non_vol]
X = X[:, keep_idx]
print(f"LINK sin volumen: {X.shape[1]} features")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

model = RandomForestClassifier(
    max_depth=6,
    min_samples_split=30,
    min_samples_leaf=15,
    n_estimators=200,
    max_features='sqrt',
    class_weight='balanced',
    random_state=42
)
model.fit(X_train_s, y_train)
train_acc = model.score(X_train_s, y_train)
test_acc = model.score(X_test_s, y_test)
gap = train_acc - test_acc
print(f"LINK no-vol -> train={train_acc:.2%}, test={test_acc:.2%}, gap={gap:.2%}")

joblib.dump(model, f"{MODELS}/LINK_optimized_model.pkl")
joblib.dump(scaler, f"{MODELS}/LINK_scaler_optimized.pkl")
joblib.dump(non_vol, f"{MODELS}/LINK_selected_features.pkl")
print("✅ Modelo LINK guardado sin volumen")
