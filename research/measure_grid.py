#!/usr/bin/env python3
"""
Paso 1b de #77: misma comparacion pero con el pago REAL del grid del bot
(TP1 1.8% / TP2 3.5% / TP3 5.5%, SL 2.5% con breakeven tras TP1), no solo TP1-or-SL.
"""
import numpy as np
import pandas as pd
from pathlib import Path

DATA = Path('/home/overgon/work/perrobotillo-trading-bot/backtest/data')
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC']
TP1, TP2, TP3 = 0.018, 0.035, 0.055
SL = 0.025
COST = 0.0015
MAX_BARS = 288

REGIMES = {
    'BULL':    {'sma': 20, 'rsi_min': 40, 'rsi_max': 72},
    'LATERAL': {'sma': 20, 'rsi_min': 35, 'rsi_max': 62},
    'BEAR':    {'sma': 50, 'rsi_min': 25, 'rsi_max': 55},
}


def rsi(closes, n=14):
    d = np.diff(closes)
    g = np.where(d > 0, d, 0.0)
    l = np.where(d < 0, -d, 0.0)
    ag = np.mean(g[-n:]) if len(g) >= n else 0.0
    al = np.mean(l[-n:]) if len(l) >= n else 1e-9
    return 100 - 100 / (1 + ag / al) if al else 50.0


def load(coin):
    df = pd.read_csv(DATA / f'{coin}_5m.csv', parse_dates=['timestamp']).sort_values('timestamp').set_index('timestamp')
    h = df.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
    return df, h


def regime_series(h):
    e50 = h['close'].ewm(span=50, adjust=False).mean()
    e200 = h['close'].ewm(span=200, adjust=False).mean()
    return pd.Series(np.where(e50 > e200 * 1.005, 'BULL', np.where(e50 < e200 * 0.995, 'BEAR', 'LATERAL')), index=h.index)


def grid_return(m, px):
    """Pago del grid: 1/3 en TP1, 1/3 en TP2, 1/3 en TP3; SL -2.5% (breakeven tras TP1)."""
    qty, pnl = 1.0, 0.0
    sl = px * (1 - SL)
    levels = [px * (1 + TP1), px * (1 + TP2), px * (1 + TP3)]
    pays = [TP1, TP2, TP3]
    li = 0
    last = m['close'].iloc[-1]
    for _, bar in m.iterrows():
        if qty > 0 and bar['low'] <= sl:
            pnl += qty * (sl / px - 1)
            qty = 0.0
            break
        while li < 3 and qty > 0 and bar['high'] >= levels[li]:
            take = min(1 / 3, qty)
            pnl += take * pays[li]
            qty -= take
            li += 1
            if li == 1:
                sl = px          # breakeven tras TP1
        if qty <= 0:
            break
    if qty > 0:
        pnl += qty * (last / px - 1)
    return pnl - COST


def simulate(h, m5, variant, regime):
    closes = h['close'].to_numpy()
    regs = regime.to_numpy()
    rets = []
    i = 200
    n = len(h)
    while i < n - 1:
        px = closes[i]
        if variant == 'baseline':
            enter = True
        elif variant == 'fijo':
            enter = (px > closes[i - 20:i].mean()) and (rsi(closes[:i + 1]) < 70)
        else:
            p = REGIMES[regs[i]]
            enter = (px > closes[i - p['sma']:i].mean()) and (p['rsi_min'] <= rsi(closes[:i + 1]) <= p['rsi_max'])
        if not enter:
            i += 1
            continue
        m = m5[m5.index > h.index[i]].head(MAX_BARS)
        if len(m) < 2:
            break
        rets.append(grid_return(m, px))
        i = int(np.searchsorted(h.index.values, np.datetime64(m.index[-1]))) + 1
    return rets


def stats(rets, frac=0.10):
    if not rets:
        return dict(trades=0, wr=0.0, avg=0.0, pf=0.0, total=0.0)
    a = np.array(rets)
    wins, losses = a[a > 0], a[a <= 0]
    eq = np.cumprod(1 + frac * a)
    return dict(trades=len(a), wr=float(len(wins) / len(a) * 100), avg=float(a.mean() * 100),
                pf=float(wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float('inf'),
                total=float((eq[-1] - 1) * 100))


rows = []
for coin in COINS:
    m5, h = load(coin)
    reg = regime_series(h)
    for v in ['baseline', 'fijo', 'dinamico']:
        s = stats(simulate(h, m5, v, reg))
        s['coin'], s['variant'] = coin, v
        rows.append(s)

df = pd.DataFrame(rows)
print("=== PAGO REAL DEL GRID (TP1/TP2/TP3 + SL, 95 dias, coste 0.15%) ===\n")
for v in ['baseline', 'fijo', 'dinamico']:
    sub = df[df['variant'] == v]
    print(f"{v:9s} trades={int(sub['trades'].sum()):5d}  wr={sub['wr'].mean():5.1f}%  "
          f"avg={sub['avg'].mean():+.3f}%  pf={sub['pf'].replace([np.inf], np.nan).mean():5.2f}  "
          f"total(frac 10%)={sub['total'].sum():+7.1f}%")
print("\n=== por moneda (total frac 10%) ===")
print(df.pivot(index='coin', columns='variant', values='total').round(2).to_string())
print("\n=== por moneda (win rate) ===")
print(df.pivot(index='coin', columns='variant', values='wr').round(1).to_string())
