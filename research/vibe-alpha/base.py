from __future__ import annotations

import numpy as np
import pandas as pd


def safe_div(num, denom):
    denom = denom.replace(0, np.nan)
    return num / denom


def rank(df: pd.DataFrame) -> pd.DataFrame:
    return df.rank(axis=1, pct=True) - 0.5


def signed_power(x: pd.DataFrame, p: float) -> pd.DataFrame:
    return x.pow(p) * np.sign(x)


def ts_argmax(df: pd.DataFrame, window: int) -> pd.DataFrame:
    return df.rolling(window, min_periods=window).apply(lambda x: x[::-1].argmax(), raw=True)


def ts_std(df: pd.DataFrame, window: int) -> pd.DataFrame:
    return df.rolling(window, min_periods=window).std(ddof=0)


def decay_linear(df: pd.DataFrame, window: int) -> pd.DataFrame:
    weights = np.arange(window, 0, -1)
    return df.rolling(window, min_periods=window).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)


def delta(df: pd.DataFrame, period: int = 1) -> pd.DataFrame:
    return df.diff(periods=period)


def ts_argmin(df: pd.DataFrame, window: int) -> pd.DataFrame:
    return df.rolling(window, min_periods=window).apply(lambda x: x[::-1].argmin(), raw=True)


def ts_corr(x: pd.DataFrame, y: pd.DataFrame, window: int) -> pd.DataFrame:
    return x.rolling(window, min_periods=window).corr(y)


def ts_cov(x: pd.DataFrame, y: pd.DataFrame, window: int) -> pd.DataFrame:
    return x.rolling(window, min_periods=window).cov(y)


def ts_max(df: pd.DataFrame, window: int) -> pd.DataFrame:
    return df.rolling(window, min_periods=window).max()


def ts_mean(df: pd.DataFrame, window: int) -> pd.DataFrame:
    return df.rolling(window, min_periods=window).mean()


def ts_min(df: pd.DataFrame, window: int) -> pd.DataFrame:
    return df.rolling(window, min_periods=window).min()


def ts_rank(df: pd.DataFrame, window: int) -> pd.DataFrame:
    return df.rolling(window, min_periods=window).rank(pct=True)


def scale(df: pd.DataFrame) -> pd.DataFrame:
    s = df.sum(axis=1)
    s = s.replace(0, np.nan)
    return df.div(s, axis=0)
