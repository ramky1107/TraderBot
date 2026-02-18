"""
=============================================================================
strategies.py
=============================================================================
Thin wrapper: applies all technical indicators to a chart DataFrame.
All indicator math lives in indicators.py.

Provides:
  - apply_strategies(df) → df with indicator columns added

Used by:
  - main.py (/api/stock-data endpoint)
=============================================================================
"""

import pandas as pd
import indicators as ind


def apply_strategies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all technical indicator columns to an OHLCV DataFrame.

    Columns added:
      SMA_20, SMA_50, RSI, MACD, MACD_Signal, MACD_Hist,
      BB_Upper, BB_Middle, BB_Lower

    Args:
        df: DataFrame with at least 'Close' and 'Volume' columns.

    Returns:
        The same DataFrame with indicator columns added in-place.
    """
    if df.empty:
        return df

    close = df['Close']

    # ── Moving Averages ───────────────────────────────────────────────────────
    df['SMA_20'] = ind.sma(close, 20)
    df['SMA_50'] = ind.sma(close, 50)

    # ── RSI (14-period) ───────────────────────────────────────────────────────
    df['RSI'] = ind.rsi(close, period=14)

    # ── MACD (12/26/9) ────────────────────────────────────────────────────────
    macd_line, signal_line, histogram = ind.macd(close)
    df['MACD']        = macd_line
    df['MACD_Signal'] = signal_line
    df['MACD_Hist']   = histogram

    # ── Bollinger Bands (20-period, 2σ) ───────────────────────────────────────
    upper, middle, lower = ind.bollinger_bands(close)
    df['BB_Upper']  = upper
    df['BB_Middle'] = middle
    df['BB_Lower']  = lower

    return df