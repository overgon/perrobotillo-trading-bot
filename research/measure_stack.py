#!/usr/bin/env python3
"""
Paso 3 de #77: medir el STACK fallback (gate) + modelo de outcome (tamano).

Variantes, todas sobre las mismas ventanas de test del walk-forward:
  baseline   : entra en cada vela 1h, tamano 10%
  fallback   : solo si el fallback dinamico aprueba, tamano 10%
  stack      : fallback + tamano = 10% * prob del modelo
  stack_piso : fallback + tamano = 10% * max(prob, 0.30)

El modelo se entrena en la ventana de train de cada fold (sin filtrar al test).
"""
import numpy as np
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_outcome_model import build_samples, rsi, COINS

REG = {
    'BULL':    {'sma': 20, 'lo': 40, 'hi': 72},
    'LATERAL': {'sma': 20, 'lo': 35, 'hi': 62},
    'BEAR':    {'sma': 50, 'lo': 25, 'hi': 55},
}
BASE = 0.10        # fraccion de capital por trade (TRADE_PERCENT del bot)
HORIZON_H = 48
FOLDS = [(0.00, 0.50, 0.55, 0.70), (0.15, 0.65, 0.70, 0.85), (0.30, 0.80, 0.85, 1.00)]
EMBARGO = HORIZON_H


def regime_series(h):
    e50 = h['close'].ewm(span=50, adjust=False).mean()
    e200 = h['close'].ewm(span=200, adjust=False).mean()
    return pd.Series(np.where(e50 > e200 * 1.005, 'BULL',
                               np.where(e50 < e200 * 0.995, 'BEAR', 'LATERAL')), index=h.index)


def fallback_signal(closes, i, reg):
    p = REG[reg]
    sma = closes[i - p['sma']:i].mean()
    r = float(rsi(pd.Series(closes[:i + 1])).iloc[-1])
    return (closes[i] > sma) and (p['lo'] <= r <= p['hi'])


def main():
    from sklearn.ensemble import RandomForestClassifier

    frames, closes_map, reg_map = [], {}, {}
    for coin in COINS:
        feat = build_samples(coin)
        frames.append(feat)
        df = pd.read_csv(Path('/home/overgon/work/perrobotillo-trading-bot/backtest/data') / f'{coin}_5m.csv',
                         parse_dates=['timestamp']).sort_values('timestamp').set_index('timestamp')
        h = df.resample('1h').agg({'close': 'last'}).dropna()
        closes_map[coin] = h['close']
        reg_map[coin] = regime_series(h)

    df = pd.concat(frames)
    df['btc_ret_24h'] = df.index.map(frames[0]['ret_24h'])
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    for c in COINS:
        df[f'c_{c}'] = (df['coin'] == c).astype(int)
    feat_cols = [c for c in df.columns if c not in ('y', 'ret', 'coin')]
    n = len(df)

    agg = {k: [] for k in ['baseline', 'fallback', 'stack', 'stack_piso']}
    for a, b, c_, d in FOLDS:
        tr = df.iloc[int(a * n):int(b * n) - EMBARGO]
        te = df.iloc[int(c_ * n):int(d * n)]
        m = RandomForestClassifier(n_estimators=400, max_depth=8, min_samples_leaf=20,
                                   class_weight='balanced', random_state=42, n_jobs=-1)
        m.fit(tr[feat_cols].to_numpy(), tr['y'].to_numpy())
        prob = m.predict_proba(te[feat_cols].to_numpy())[:, 1]
        rets = te['ret'].to_numpy()
        coins = te['coin'].to_numpy()
        idx = te.index

        sig = np.zeros(len(te), dtype=bool)
        for j in range(len(te)):
            s = closes_map[coins[j]]
            pos = s.index.get_loc(idx[j])
            reg = reg_map[coins[j]].iloc[pos]
            sig[j] = fallback_signal(s.to_numpy(), pos, reg)

        for name, mult in [('baseline', np.ones(len(te))),
                           ('fallback', sig.astype(float)),
                           ('stack', sig * prob),
                           ('stack_piso', sig * np.maximum(prob, 0.30))]:
            r = rets * (BASE * mult)
            agg[name].extend(r.tolist())

    print("=== STACK fallback + modelo (fraccion base 10%, ventanas de test) ===\n")
    for name, r in agg.items():
        r = np.array(r)
        traded = r[r != 0]
        eq = np.cumprod(1 + r) if len(r) else np.array([1.0])
        peak = np.maximum.accumulate(eq)
        mdd = float(np.min((eq - peak) / peak)) * 100 if len(eq) else 0.0
        print(f"{name:11s} trades={len(traded):5d}  wr={100*(traded>0).mean() if len(traded) else 0:5.1f}%  "
              f"avg={traded.mean()*100 if len(traded) else 0:+.3f}%  total={100*(eq[-1]-1):+7.1f}%  mdd={mdd:+.1f}%")


if __name__ == '__main__':
    main()
