#!/usr/bin/env python3
"""
Paso 1 de #77: medir el fallback tecnico ANTES de tocar nada.

Simula entradas con la regla del fallback sobre velas 1h (derivadas de 5m reales)
y resuelve cada trade con TP1/SL sobre las velas 5m. Una posicion por moneda.

Compara 3 variantes:
  baseline : siempre entra (sin filtro)
  fijo     : precio > SMA20 y RSI < 70 (el fallback viejo)
  dinamico : regido por regime (BULL/LATERAL/BEAR) con umbrales y posicion adaptados

Regime historico (proxy): EMA50 vs EMA200 en 1h.
Coste: 0.15% redondo (0.10% fee + 5 bps slippage), como en el baseline del CI.
"""
import numpy as np
import pandas as pd
from pathlib import Path

DATA = Path('/home/overgon/work/perrobotillo-trading-bot/backtest/data')
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC']
TP = 0.018      # TP1
SL = 0.025      # SL
COST = 0.0015   # 0.15% redondo
MAX_BARS = 288  # 48h en velas 5m

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
    df = pd.read_csv(DATA / f'{coin}_5m.csv', parse_dates=['timestamp']).sort_values('timestamp')
    df = df.set_index('timestamp')
    h = df.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min',
                               'close': 'last', 'volume': 'sum'}).dropna()
    return df, h


def regime_series(h):
    e50 = h['close'].ewm(span=50, adjust=False).mean()
    e200 = h['close'].ewm(span=200, adjust=False).mean()
    reg = np.where(e50 > e200 * 1.005, 'BULL', np.where(e50 < e200 * 0.995, 'BEAR', 'LATERAL'))
    return pd.Series(reg, index=h.index)


def simulate(h, m5, variant, regime):
    """Devuelve lista de retornos netos de cada trade."""
    closes = h['close'].to_numpy()
    regs = regime.to_numpy()
    rets = []
    i = 200  # arranca tras el warmup de EMA200
    n = len(h)
    while i < n - 1:
        px = closes[i]
        reg = regs[i] if variant == 'dinamico' else None

        if variant == 'baseline':
            enter = True
        else:
            if variant == 'fijo':
                sma = closes[i - 20:i].mean()
                r = rsi(closes[:i + 1])
                enter = (px > sma) and (r < 70)
            else:  # dinamico
                p = REGIMES[reg]
                sma = closes[i - p['sma']:i].mean()
                r = rsi(closes[:i + 1])
                enter = (px > sma) and (p['rsi_min'] <= r <= p['rsi_max'])

        if not enter:
            i += 1
            continue

        # resuelve el trade sobre velas 5m desde el CIERRE de la vela 1h (i+1h)
        t0 = h.index[i]
        m = m5[m5.index > t0].head(MAX_BARS)
        if len(m) < 2:
            break
        hit = None
        for _, bar in m.iterrows():
            if bar['low'] <= px * (1 - SL):
                hit = -SL
                break
            if bar['high'] >= px * (1 + TP):
                hit = TP
                break
        if hit is None:
            hit = float(m['close'].iloc[-1] / px - 1)  # cierra a mercado a las 48h
        rets.append(hit - COST)
        # evita solapamiento: avanza hasta el fin de este trade
        i = int(np.searchsorted(h.index.values, np.datetime64(m.index[-1]))) + 1
    return rets


def stats(rets, frac=0.10):
    if not rets:
        return dict(trades=0, wr=0.0, avg=0.0, pf=0.0, total=0.0, mdd=0.0)
    a = np.array(rets)
    wins = a[a > 0]
    losses = a[a <= 0]
    eq = np.cumprod(1 + frac * a)          # fraccion fijo de capital por trade
    peak = np.maximum.accumulate(eq)
    mdd = float(np.min((eq - peak) / peak))
    be_wr = SL / (TP + SL) * 100           # win rate de equilibrio sin coste
    return dict(
        trades=len(a),
        wr=float(len(wins) / len(a) * 100),
        avg=float(a.mean() * 100),
        pf=float(wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float('inf'),
        total=float((eq[-1] - 1) * 100),
        mdd=mdd * 100,
        be_wr=be_wr,
    )


rows = []
for coin in COINS:
    m5, h = load(coin)
    regime = regime_series(h)
    for variant in ['baseline', 'fijo', 'dinamico']:
        rets = simulate(h, m5, variant, regime)
        s = stats(rets)
        s['coin'] = coin
        s['variant'] = variant
        rows.append(s)

df = pd.DataFrame(rows)
print(f"Win rate de equilibrio (TP {TP*100:.1f}% / SL {SL*100:.1f}%) = {SL/(TP+SL)*100:.1f}% sin coste\n")
for variant in ['baseline', 'fijo', 'dinamico']:
    sub = df[df['variant'] == variant]
    agg = dict(
        trades=int(sub['trades'].sum()),
        wr=round(sub['wr'].mean(), 1),
        avg=round(sub['avg'].mean(), 3),
        pf=round(sub['pf'].replace([np.inf], np.nan).mean(), 2),
        total=round(sub['total'].sum(), 1),
        mdd=round(sub['mdd'].min(), 1),
    )
    print(f"{variant:9s} trades={agg['trades']:5d}  wr={agg['wr']:5.1f}%  avg={agg['avg']:+.3f}%  "
          f"pf={agg['pf']:5.2f}  total(frac 10%)={agg['total']:+7.1f}%  mdd={agg['mdd']}%")

print("\n=== por moneda (dinamico vs fijo) ===")
piv = df.pivot(index='coin', columns='variant', values=['trades', 'wr', 'total'])
print(piv.to_string())
