#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
# Genera ml/market-training-data.csv desde las velas de la DB de Jesse.
#
# El market-classifier del bot (ml/market-classifier.py) necesita un CSV con
# las features de cada moneda + la etiqueta `market_mode`. Este script lo
# construye con las velas 1h ya importadas en Jesse (en vez de la API de
# Binance), reutilizando extract_features()/label_market_mode() del propio
# market-classifier.
#
# Uso (venv-jesse):
#   venv-jesse/bin/python3 research/export_market_training_data.py --hours 1000
# ═══════════════════════════════════════════════════════════════════════════

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))
sys.path.insert(0, '/home')

import pandas as pd  # noqa: E402
from jesse.research import get_candles  # noqa: E402

# el archivo se llama market-classifier.py (con guion): cargar por ruta
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location('market_classifier', ROOT / 'ml' / 'market-classifier.py')
mc = importlib.util.module_from_spec(_spec)
sys.modules['market_classifier'] = mc
_spec.loader.exec_module(mc)

EXCHANGE = 'Binance Spot'


def candles_to_df(symbol: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    c = get_candles(EXCHANGE, symbol, '1h', start_ms, end_ms)
    if isinstance(c, tuple):
        c = c[1]
    if c is None or len(c) == 0:
        raise RuntimeError(f'sin velas para {symbol}')
    df = pd.DataFrame(c, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    # Jesse 3.6: [timestamp, open, high, low, close, volume] — ya en orden de columnas
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--hours', type=int, default=1000, help='velas 1h por moneda')
    ap.add_argument('--out', default=str(ROOT / 'ml' / 'market-training-data.csv'))
    args = ap.parse_args()

    end = datetime.now()
    start = end - timedelta(hours=args.hours)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    print(f"=== market-training-data desde Jesse ===\nMonedas: {mc.COINS} | {args.hours} velas 1h c/u\n")

    frames = []
    for coin in mc.COINS:
        try:
            df = candles_to_df(f'{coin}-USDT', start_ms, end_ms)
            df = mc.extract_features(df, coin)
            if df is None or len(df) < 50:
                print(f"  ⚠️  {coin}: sin datos suficientes")
                continue
            df['market_mode'] = mc.label_market_mode(df)
            print(f"  ✅ {coin}: {len(df)} filas")
            frames.append(df)
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ {coin}: {type(exc).__name__}: {exc}")

    if not frames:
        print("❌ No se generó data")
        return 1

    combined = pd.concat(frames, ignore_index=True)
    combined['market_mode'] = mc.label_market_mode(combined)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.out, index=False)
    print(f"\n✅ {args.out}: {len(combined)} filas")
    print("   labels:", combined['market_mode'].value_counts().to_dict())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
