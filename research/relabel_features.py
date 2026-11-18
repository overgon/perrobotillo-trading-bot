#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
# Recalcula el label de ml/features/{COIN}_features.csv con un criterio más
# sensible que el original (lookforward=5, threshold=0.5%), que dejaba el
# dataset 98% en WAIT y hacía que el modelo solo supiera decir WAIT.
#
# Criterio por defecto: lookforward=12 (1h en velas de 5m), threshold=0.3%.
#
# Uso:
#   python3 research/relabel_features.py                 # las 8 monedas
#   python3 research/relabel_features.py --coins BTC,ETH --lookforward 12 --threshold 0.003
# ═══════════════════════════════════════════════════════════════════════════

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEATURES_DIR = ROOT / 'ml' / 'features'
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC']


def relabel(coin: str, lookforward: int, threshold: float) -> dict:
    path = FEATURES_DIR / f'{coin}_features.csv'
    if not path.exists():
        print(f"  ❌ {coin}: no existe {path.name}")
        return {}

    df = pd.read_csv(path)
    before = df['label'].value_counts().to_dict()

    close = df['close']
    future_return = close.shift(-lookforward) / close - 1
    df['label'] = np.where(future_return > threshold, 1,
                           np.where(future_return < -threshold, 2, 0)).astype(int)
    df = df.iloc[:-lookforward]  # las últimas filas no tienen futuro

    df.to_csv(path, index=False)
    after = df['label']. value_counts().to_dict()
    tot = len(df) or 1
    print(f"  ✅ {coin}: {len(df)} filas | WAIT {after.get(0,0)/tot:.1%} "
          f"LONG {after.get(1,0)/tot:.1%} SHORT {after.get(2,0)/tot:.1%} "
          f"(antes: {before})")
    return after


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--coins', default='ALL')
    ap.add_argument('--lookforward', type=int, default=12)
    ap.add_argument('--threshold', type=float, default=0.003)
    args = ap.parse_args()

    coins = COINS if args.coins.upper() == 'ALL' else [c.strip().upper() for c in args.coins.split(',')]
    print(f"=== Recalculo de labels (lookforward={args.lookforward}, threshold={args.threshold}) ===")

    for coin in coins:
        try:
            relabel(coin, args.lookforward, args.threshold)
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ {coin}: {type(exc).__name__}: {exc}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
