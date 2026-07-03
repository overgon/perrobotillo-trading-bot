from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from alpha101_001 import compute as compute_001
from alpha101_054 import compute as compute_054
from base import rank

UNIVERSE = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
BINANCE = "https://api.binance.com/api/v3/klines"
SECRETS = "/home/overgon/.openclaw/secrets/binance.env"


def load_env() -> dict[str, str]:
    env = {}
    with open(SECRETS, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip().strip("\"'")
    return env


def fetch_klines(symbol: str, interval: str = "1d", limit: int = 365) -> pd.DataFrame:
    import subprocess, json
    url = f"{BINANCE}?symbol={symbol}&interval={interval}&limit={limit}"
    out = subprocess.check_output(["curl", "-s", url], text=True)
    data = json.loads(out)
    df = pd.DataFrame(data, columns=[
        "open_time","open","high","low","close","volume","close_time",
        "qav","count","taker_buy_base","taker_buy_quote","ignore"
    ])
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df = df.set_index("open_time")[["open","high","low","close","volume"]].sort_index()
    return df


def build_panel(symbols: list[str], days: int = 365) -> dict[str, pd.DataFrame]:
    panel: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = fetch_klines(sym, "1d", min(days, 1000))
        df = df.loc[df.index >= (datetime.now(timezone.utc) - timedelta(days=days))]
        panel[sym] = df
    return panel


def align_panel(panel: dict[str, pd.DataFrame], symbols: list[str]) -> dict[str, pd.DataFrame]:
    closes = pd.concat({sym: panel[sym]["close"] for sym in symbols}, axis=1).sort_index()
    closes = closes.ffill().bfill()
    panel["close"] = closes
    highs = pd.concat({sym: panel[sym]["high"] for sym in symbols}, axis=1).reindex(closes.index).ffill().bfill()
    panel["high"] = highs
    lows = pd.concat({sym: panel[sym]["low"] for sym in symbols}, axis=1).reindex(closes.index).ffill().bfill()
    panel["low"] = lows
    opens = pd.concat({sym: panel[sym]["open"] for sym in symbols}, axis=1).reindex(closes.index).ffill().bfill()
    panel["open"] = opens
    return panel


def forward_returns(close: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    return close.shift(-horizon).pct_change(horizon)


def ic_series(alpha: pd.DataFrame, fwd: pd.DataFrame) -> pd.Series:
    if alpha.shape != fwd.shape:
        return pd.Series(dtype=float)
    cols = alpha.columns.intersection(fwd.columns)
    a = alpha.loc[fwd.index, cols]
    b = fwd[cols]
    def _ic(row):
        ra = row[:len(cols)].rank()
        rb = row[len(cols):].rank()
        if ra.isna().all() or rb.isna().all():
            return np.nan
        return ra.corr(rb)
    joined = pd.concat([a, b], axis=1)
    if joined.empty:
        return pd.Series(dtype=float)
    return joined.apply(_ic, axis=1)


@dataclass
class AlphaResult:
    alpha_id: str
    mean_ic: float
    std_ic: float
    ir: float
    positive_days: float
    total_days: int


def score_alpha(name: str, compute_fn, panel: dict[str, pd.DataFrame], horizon: int = 5) -> AlphaResult:
    alpha = compute_fn(panel)
    fwd = forward_returns(panel["close"], horizon=horizon)
    series = ic_series(alpha, fwd).dropna()
    if series.empty:
        return AlphaResult(name, float("nan"), float("nan"), float("nan"), 0.0, 0)
    mean = float(series.mean())
    std = float(series.std(ddof=0))
    ir = mean / std if std > 1e-12 else float("inf") if mean > 0 else float("-inf") if mean < 0 else 0.0
    pos = float((series > 0).mean())
    return AlphaResult(name, mean, std, ir, pos, int(series.count()))


def main():
    print("Fetching panel...")
    panel = build_panel(UNIVERSE, days=365)
    panel = align_panel(panel, UNIVERSE)
    print("Panel ready:", {k: v.shape for k, v in panel.items()})
    candidates = [("alpha101_001", compute_001), ("alpha101_054", compute_054)]
    results = []
    for name, fn in candidates:
        res = score_alpha(name, fn, panel, horizon=5)
        results.append(res)
        print(json.dumps({
            "alpha_id": res.alpha_id,
            "mean_ic": round(res.mean_ic, 4) if np.isfinite(res.mean_ic) else None,
            "std_ic": round(res.std_ic, 4) if np.isfinite(res.std_ic) else None,
            "ir": round(res.ir, 4) if np.isfinite(res.ir) else None,
            "positive_days": round(res.positive_days, 2),
            "total_days": res.total_days,
        }, ensure_ascii=False))
    print("Done.")


if __name__ == "__main__":
    main()
