"""VWAP / EMA / ATR indicator calculations (pandas, no MT5 dependency)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def typical_price(df: pd.DataFrame) -> pd.Series:
    return (df["high"] + df["low"] + df["close"]) / 3.0


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """Daily-session VWAP (resets at each new calendar day in the data's tz).

    Uses typical price x tick_volume. Bars with zero volume inherit the
    previous VWAP value instead of dividing by zero.
    """
    tp = typical_price(df)
    vol = df["tick_volume"].fillna(0).astype(float)
    day = pd.to_datetime(df["time"]).dt.date
    cum_pv = (tp * vol).groupby(day).cumsum()
    cum_v = vol.groupby(day).cumsum()
    vwap = cum_pv / cum_v.replace(0, np.nan)
    return vwap.ffill().bfill()


def rolling_vwap(df: pd.DataFrame, period: int = 50) -> pd.Series:
    tp = typical_price(df)
    vol = df["tick_volume"].fillna(0).astype(float).replace(0, 1e-9)
    pv = (tp * vol).rolling(period, min_periods=1).sum()
    vv = vol.rolling(period, min_periods=1).sum()
    return pv / vv


def add_indicators(df: pd.DataFrame, ema_period: int = 9, atr_period: int = 14,
                   vwap_mode: str = "session", vwap_rolling_period: int = 50) -> pd.DataFrame:
    """Return a copy of df with ema9, atr, vwap columns appended."""
    out = df.copy().reset_index(drop=True)
    out["ema9"] = ema(out["close"], ema_period)
    out["atr"] = atr(out, atr_period)
    if vwap_mode == "rolling":
        out["vwap"] = rolling_vwap(out, vwap_rolling_period)
    else:
        out["vwap"] = session_vwap(out)
    return out
