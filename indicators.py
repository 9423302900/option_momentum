# indicators.py
import pandas as pd
import numpy as np

def ema(series: pd.Series, length: int):
    return series.ewm(span=length, adjust=False).mean()

def rsi(series: pd.Series, length: int = 5):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/length, adjust=False).mean()
    ma_down = down.ewm(alpha=1/length, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def atr(df: pd.DataFrame, length: int = 14):
    # df must contain columns: high, low, close
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

def volume_spike(volume_series: pd.Series, lookback: int = 10, multiplier: float = 1.5):
    baseline = volume_series.rolling(lookback).mean()
    return volume_series > baseline * multiplier

def compute_all(df: pd.DataFrame):
    """
    Expect df indexed in chronological order (old -> new) with columns:
    ['open','high','low','close','volume']
    Returns df with indicators appended.
    """
    df = df.copy()
    df['ema9'] = ema(df['close'], 9)
    df['ema21'] = ema(df['close'], 21)
    df['rsi5'] = rsi(df['close'], 5)
    df['atr14'] = atr(df, 14)
    df['atr14_ma'] = df['atr14'].rolling(14).mean()
    df['atr_spike'] = df['atr14'] > df['atr14_ma'] * 1.2
    df['vol_spike'] = volume_spike(df['volume'], lookback=10, multiplier=1.5)
    return df

