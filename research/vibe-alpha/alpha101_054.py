"""Kakushadze Alpha #54 — intraday reversal.

Logic: -1 * ((low-close)*(open^5)) / ((low-high)*(close^5))
Positive => reversal up bias.

Usage: compute(window_panel['open','high','low','close']) -> DataFrame.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from base import rank, safe_div, signed_power

ALPHA_ID = "alpha101_054"
UNIVERSE = ["crypto"]
FREQUENCY = ["1d"]


def compute(panel: dict) -> pd.DataFrame:
    close = panel["close"]
    open_ = panel["open"]
    high = panel["high"]
    low = panel["low"]
    num = (low - close) * open_.pow(5)
    denom = (low - high) * close.pow(5)
    out = -1.0 * safe_div(num, denom)
    return out
