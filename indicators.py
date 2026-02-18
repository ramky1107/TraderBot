"""
=============================================================================
indicators.py
=============================================================================
Pure technical indicator calculations.
All functions are stateless — they take a pd.Series or pd.DataFrame and
return a pd.Series (or tuple of Series).

Used by:
  - scorer.py      (for sentiment scoring)
  - strategies.py  (for enriching chart data before serving to frontend)
  - ai_model.py    (for building ML feature vectors)
=============================================================================
"""

import numpy as np
import pandas as pd


# ─── RSI ──────────────────────────────────────────────────────────────────────

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index (RSI).

    Measures the speed and magnitude of recent price changes.
      RSI > 70  → overbought (potential sell signal)
      RSI < 30  → oversold  (potential buy signal)

    Args:
        close:  Closing price series.
        period: Lookback window (default 14).

    Returns:
        pd.Series of RSI values (NaN for first `period` rows).
    """
    delta = close.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs    = gain / loss
    return 100.0 - (100.0 / (1.0 + rs))


# ─── Moving Averages ──────────────────────────────────────────────────────────

def sma(close: pd.Series, period: int) -> pd.Series:
    """
    Simple Moving Average over `period` bars.

    Args:
        close:  Closing price series.
        period: Rolling window size.

    Returns:
        pd.Series of SMA values.
    """
    return close.rolling(window=period).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    """
    Exponential Moving Average with the given span.

    Args:
        close: Closing price series.
        span:  EMA span (roughly equivalent to a 2*span-1 SMA).

    Returns:
        pd.Series of EMA values.
    """
    return close.ewm(span=span, adjust=False).mean()


# ─── MACD ─────────────────────────────────────────────────────────────────────

def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Moving Average Convergence Divergence (MACD).

    MACD Line   = EMA(fast) − EMA(slow)
    Signal Line = EMA(MACD, signal_period)
    Histogram   = MACD Line − Signal Line

    A MACD line crossing above the signal line is bullish;
    crossing below is bearish.

    Args:
        close:         Closing price series.
        fast:          Fast EMA span (default 12).
        slow:          Slow EMA span (default 26).
        signal_period: Signal line EMA span (default 9).

    Returns:
        Tuple of (macd_line, signal_line, histogram) as pd.Series.
        Returns zero-filled series if data is too short.
    """
    if len(close) < slow:
        # Not enough data — return zeroed series to avoid downstream errors
        zeros = pd.Series([0.0] * len(close), index=close.index)
        return zeros, zeros, zeros

    ema_fast    = close.ewm(span=fast, adjust=False).mean()
    ema_slow    = close.ewm(span=slow, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


# ─── Bollinger Bands ──────────────────────────────────────────────────────────

def bollinger_bands(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands.

    Upper Band = SMA(period) + num_std × σ
    Lower Band = SMA(period) − num_std × σ

    Price near the upper band → potentially overbought.
    Price near the lower band → potentially oversold.

    Args:
        close:   Closing price series.
        period:  Rolling window (default 20).
        num_std: Standard deviation multiplier (default 2).

    Returns:
        Tuple of (upper_band, middle_band, lower_band) as pd.Series.
    """
    middle = close.rolling(window=period).mean()
    std    = close.rolling(window=period).std()
    upper  = middle + (num_std * std)
    lower  = middle - (num_std * std)
    return upper, middle, lower


# ─── Momentum ─────────────────────────────────────────────────────────────────

def momentum(close: pd.Series, period: int = 5) -> pd.Series:
    """
    Price momentum: percentage change over `period` bars.

    Args:
        close:  Closing price series.
        period: Lookback window (default 5).

    Returns:
        pd.Series of percentage returns.
    """
    return close.pct_change(periods=period)


# ─── Volatility ───────────────────────────────────────────────────────────────

def annualised_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    """
    Rolling annualised volatility (standard deviation of daily returns × √252).

    Args:
        close:  Closing price series.
        window: Rolling window in bars (default 20).

    Returns:
        pd.Series of annualised volatility values (as a fraction, e.g. 0.25 = 25%).
    """
    daily_returns = close.pct_change()
    return daily_returns.rolling(window=window).std() * np.sqrt(252)


# ─── VWAP ─────────────────────────────────────────────────────────────────────

def vwap(df: pd.DataFrame) -> float:
    """
    Volume-Weighted Average Price for the entire session in `df`.

    VWAP = Σ(Close × Volume) / Σ(Volume)

    Args:
        df: DataFrame with 'Close' and 'Volume' columns.

    Returns:
        VWAP as a float. Falls back to simple mean if volume is zero.
    """
    total_volume = df['Volume'].sum() if 'Volume' in df.columns else 0
    if total_volume == 0:
        return float(df['Close'].mean())
    return float((df['Close'] * df['Volume']).sum() / total_volume)


# ─── Safe Last Value ──────────────────────────────────────────────────────────

def safe_last(series: pd.Series, default: float = 0.0) -> float:
    """
    Safely retrieve the last non-NaN value from a Series.

    Args:
        series:  Input Series.
        default: Value to return if series is empty or last value is NaN.

    Returns:
        Last value as float, or `default`.
    """
    if not isinstance(series, pd.Series) or series.empty:
        return default
    val = series.iloc[-1]
    return default if pd.isna(val) else float(val)
