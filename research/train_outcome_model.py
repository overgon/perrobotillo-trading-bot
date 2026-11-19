#!/usr/bin/env python3
"""
Paso 2 de #77: modelo de outcome (¿entrar o no?) en vez de dirección.

Label: resultado REAL del grid del bot (TP1 1.8% / TP2 3.5% / TP3 5.5%, SL 2.5%
con breakeven tras TP1) sobre velas 5m, a partir del cierre de cada vela 1h.
  1 si el P&L neto del grid > 0, 0 si no.

Features (solo pasadas, al cierre de la vela 1h): retornos 1/4/12/24h, RSI14,
MACD histograma, distancia a EMA20/50/200, ATR%, ancho Bollinger, distancia a
máximos/mínimos 50, ratio de volumen, retorno de BTC 24h, hora, one-hot de moneda.

Validacion: walk-forward (3 ventanas) con embargo de 48h. Se reporta AUC, MCC,
calibracion y el P&L de "entrar solo si el modelo dice 1" vs baseline.

Uso: venv/bin/python3 research/train_outcome_model.py
"""
import numpy as np
import pandas as pd
from pathlib import Path

DATA = Path('/home/overgon/work/perrobotillo-trading-bot/backtest/data')
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC']
TP1, TP2, TP3 = 0.018, 0.035, 0.055
SL = 0.025
COST = 0.0015
HORIZON_H = 48          # ventana maxima del trade
COST_ROUND = COST


# ════════════════════════════════════════════════════════
# LABEL: outcome real del grid
# ════════════════════════════════════════════════════════
def grid_outcome(high, low, close, px):
    """Devuelve (P&L neto del grid, indice de la vela 5m donde cerro el trade)."""
    qty, pnl = 1.0, 0.0
    sl = px * (1 - SL)
    lv = [px * (1 + TP1), px * (1 + TP2), px * (1 + TP3)]
    pays = [TP1, TP2, TP3]
    li = 0
    end_i = len(high) - 1
    for i in range(len(high)):
        if qty > 0 and low[i] <= sl:
            pnl += qty * (sl / px - 1)
            qty = 0.0
            end_i = i
            break
        while li < 3 and qty > 0 and high[i] >= lv[li]:
            take = min(1 / 3, qty)
            pnl += take * pays[li]
            qty -= take
            li += 1
            if li == 1:
                sl = px
        if qty <= 0:
            end_i = i
            break
    if qty > 0:
        pnl += qty * (close[-1] / px - 1)
    return pnl - COST_ROUND, end_i


def build_samples(coin, non_overlapping=True):
    df = pd.read_csv(DATA / f'{coin}_5m.csv', parse_dates=['timestamp']).sort_values('timestamp').set_index('timestamp')
    h = df.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min',
                               'close': 'last', 'volume': 'sum'}).dropna()
    c = h['close']
    r = c.pct_change()

    feat = pd.DataFrame(index=h.index)
    for n in (1, 4, 12, 24):
        feat[f'ret_{n}h'] = c.pct_change(n)
    feat['rsi14'] = rsi(c, 14)
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    feat['macd_hist'] = (ema12 - ema26) - (ema12 - ema26).ewm(span=9, adjust=False).mean()
    for n in (20, 50, 200):
        feat[f'dist_ema{n}'] = c / c.ewm(span=n, adjust=False).mean() - 1
    tr = pd.concat([h['high'] - h['low'], c - h['low'].shift(1).fillna(c), h['high'].shift(1).fillna(c) - c], axis=1).max(axis=1)
    feat['atr_pct'] = tr.rolling(14).mean() / c
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    feat['bb_width'] = (c.rolling(20).std() * 4) / ma
    feat['dist_high50'] = c / h['high'].rolling(50).max() - 1
    feat['dist_low50'] = c / h['low'].rolling(50).min() - 1
    feat['vol_ratio'] = h['volume'] / h['volume'].rolling(20).mean()
    feat['hour_sin'] = np.sin(2 * np.pi * h.index.hour / 24)
    feat['hour_cos'] = np.cos(2 * np.pi * h.index.hour / 24)
    feat['coin'] = coin

    # label con la ventana 5m siguiente
    m5 = df[['high', 'low', 'close']].to_numpy()
    m5t = df.index
    labels = np.full(len(h), np.nan)
    pnls = np.full(len(h), np.nan)
    skip_until = 0
    for i in range(len(h)):
        if non_overlapping and i < skip_until:
            continue
        t0 = np.searchsorted(m5t.values, np.datetime64(h.index[i]), side='right')
        w = m5[t0:t0 + HORIZON_H * 12]
        if len(w) < 12:
            continue
        pnl, end_i = grid_outcome(w[:, 0], w[:, 1], w[:, 2], c.iloc[i])
        pnls[i] = pnl
        labels[i] = 1.0 if pnl > 0 else 0.0
        if non_overlapping:
            # en vivo el bot no solapa posiciones: salta hasta el cierre real del trade
            skip_until = max(skip_until, i + 1 + end_i // 12)
    feat['y'] = labels
    feat['ret'] = pnls
    return feat


def rsi(c, n=14):
    d = c.diff()
    g = d.clip(lower=0).rolling(n).mean()
    l = (-d.clip(upper=0)).rolling(n).mean().replace(0, 1e-9)
    return 100 - 100 / (1 + g / l)


# ════════════════════════════════════════════════════════
# WALK-FORWARD
# ════════════════════════════════════════════════════════
def main():
    frames = [build_samples(c) for c in COINS]
    df = pd.concat(frames)
    # contexto BTC: mismo timestamp en todas las monedas
    df['btc_ret_24h'] = df.index.map(frames[0]['ret_24h'])
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    for coin in COINS:
        df[f'c_{coin}'] = (df['coin'] == coin).astype(int)
    feat_cols = [c for c in df.columns if c not in ('y', 'ret', 'coin')]
    print(f"muestras: {len(df)} | features: {len(feat_cols)} | positivos: {int(df['y'].sum())} "
          f"({df['y'].mean()*100:.1f}%)\n")

    n = len(df)
    folds = [(0.00, 0.50, 0.55, 0.70), (0.15, 0.65, 0.70, 0.85), (0.30, 0.80, 0.85, 1.00)]
    embargo = HORIZON_H  # horas

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import roc_auc_score, matthews_corrcoef, accuracy_score, confusion_matrix

    all_true, all_prob = [], []
    gated_rets, base_rets = [], []
    for k, (a, b, c_, d) in enumerate(folds, 1):
        tr = df.iloc[int(a * n):int(b * n) - embargo]
        te = df.iloc[int(c_ * n):int(d * n)]
        Xtr, ytr = tr[feat_cols].to_numpy(), tr['y'].to_numpy()
        Xte, yte = te[feat_cols].to_numpy(), te['y'].to_numpy()
        m = RandomForestClassifier(n_estimators=400, max_depth=8, min_samples_leaf=20,
                                   class_weight='balanced', random_state=42, n_jobs=-1)
        m.fit(Xtr, ytr)
        prob = m.predict_proba(Xte)[:, 1]
        all_true.append(yte); all_prob.append(prob)
        gate = prob > 0.5
        gated_rets.extend(te['ret'].to_numpy()[gate])
        base_rets.extend(te['ret'].to_numpy())
        auc = roc_auc_score(yte, prob)
        mcc = matthews_corrcoef(yte, (prob > 0.5).astype(int))
        print(f"fold {k}: train={len(tr)} test={len(te)}  AUC={auc:.3f}  MCC={mcc:+.3f}  "
              f"acc={accuracy_score(yte,(prob>0.5).astype(int)):.3f}")

    yte = np.concatenate(all_true); prob = np.concatenate(all_prob)
    print(f"\n=== POOLED ===")
    print(f"AUC  = {roc_auc_score(yte, prob):.3f}")
    print(f"MCC  = {matthews_corrcoef(yte, (prob>0.5).astype(int)):+.3f}")
    print(f"confusion (0.5): \n{confusion_matrix(yte, (prob>0.5).astype(int))}")
    print("\ncalibracion (prob -> tasa real de exito):")
    for lo, hi in [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]:
        m = (prob >= lo) & (prob < hi)
        if m.sum():
            print(f"  [{lo:.1f},{hi:.1f})  n={m.sum():5d}  real={yte[m].mean()*100:5.1f}%")

    # importancias (modelo entrenado con todo el dataset)
    from sklearn.ensemble import RandomForestClassifier
    mfull = RandomForestClassifier(n_estimators=400, max_depth=8, min_samples_leaf=20,
                                   class_weight='balanced', random_state=42, n_jobs=-1)
    mfull.fit(df[feat_cols].to_numpy(), df['y'].to_numpy())
    imp = pd.Series(mfull.feature_importances_, index=feat_cols).sort_values(ascending=False)
    print("\n=== features mas importantes ===")
    for name, v in imp.head(15).items():
        print(f"  {name:16s} {v:.4f}")

    # P&L de "entrar solo si el modelo dice 1" vs baseline (solo folds de test)
    print("\n=== P&L gated (frac 10%, solo ventanas de test) ===")
    g, b = np.array(gated_rets), np.array(base_rets)
    eq_g = np.cumprod(1 + 0.10 * g)
    eq_b = np.cumprod(1 + 0.10 * b)
    print(f"  baseline: trades={len(b):5d}  wr={100*(b>0).mean():5.1f}%  avg={b.mean()*100:+.3f}%  total={100*(eq_b[-1]-1):+7.1f}%")
    print(f"  gated   : trades={len(g):5d}  wr={100*(g>0).mean():5.1f}%  avg={g.mean()*100:+.3f}%  total={100*(eq_g[-1]-1):+7.1f}%")


if __name__ == '__main__':
    main()
