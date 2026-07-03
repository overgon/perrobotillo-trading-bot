"""Kakushadze Alpha #1 — momentum/vol conditional.

Logic: rank(ts_argmax(SignedPower((returns<0)?stddev(returns,20):close, 2.), 5)) - 0.5
Positive => bullish bias; negative => bearish bias.

Usage: compute(window_panel['close']) -> DataFrame of alpha scores.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from base import rank, signed_power, ts_argmax, ts_std

ALPHA_ID = "alpha101_001"
UNIVERSE = ["crypto"]
FREQUENCY = ["1d"]


def compute(panel: dict) -> pd.DataFrame:
    close = panel["close"]
    returns = close.pct_change()
    cond = (returns < 0).astype(float)
    x = ts_std(returns, 20) * cond + close * (1.0 - cond)
    out = rank(ts_argmax(signed_power(x, 2.0), 5)) - 0.5
    return out
