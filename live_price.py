"""
=============================================================================
live_price.py
=============================================================================
Intraday price fetching and live price action scoring.

Provides:
  - fetch_intraday_df()        : Download today's 1m (or 5m fallback) data
  - calculate_live_price_score(): Score intraday trend + VWAP deviation

Used by:
  - sentiment_analyzer.py (live component of the sentiment score)
  - main.py               (for the /api/live-price endpoint)
=============================================================================
"""

import traceback
import numpy as np
import pandas as pd
import yfinance as yf

from indicators import vwap

# Maximum score contribution from the live price component
LIVE_SCORE_CAP = 20


# ─── Intraday Data Fetcher ────────────────────────────────────────────────────

def fetch_intraday_df(ticker: str) -> pd.DataFrame:
    """
    Fetch intraday OHLCV data for today.

    Primary:  1-minute bars for the current session.
    Fallback: 5-minute bars over the last 5 days (used when 1m data is sparse).

    Args:
        ticker: Stock symbol.

    Returns:
        DataFrame with OHLCV columns, or empty DataFrame on failure.
    """
    # Primary attempt: 1-minute data for today
    df = yf.download(ticker, period='1d', interval='1m', progress=False)

    if not df.empty and len(df) >= 5:
        # Flatten MultiIndex columns (yfinance quirk)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df

    # Fallback: 5-minute data over 5 days
    print(f"[LivePrice] 1m data insufficient for {ticker}, falling back to 5m/5d")
    df = yf.download(ticker, period='5d', interval='5m', progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


# ─── Live Price Score ─────────────────────────────────────────────────────────

def calculate_live_price_score(ticker: str) -> tuple[float, dict, bool]:
    """
    Analyze intraday price action and return a sentiment score from -20 to +20.

    Scoring components:
      - Intraday return (open → current close): up to ±8 pts
      - Short-term trend (10-bar MA vs 30-bar MA):  up to ±6 pts
      - VWAP deviation (price vs VWAP):              up to ±6 pts

    Args:
        ticker: Stock symbol.

    Returns:
        Tuple of:
          - live_score        : float in [-20, +20]
          - price_details     : dict with price metrics for the UI
          - data_available    : bool (False if no intraday data found)
    """
    try:
        live_df = fetch_intraday_df(ticker)

        if live_df.empty:
            return 0.0, {}, False

        close         = live_df['Close']
        current_price = float(close.iloc[-1])
        open_price    = float(live_df['Open'].iloc[0])

        # ── Component 1: Intraday return (open → now) ────────────────────────
        # Scale: 1% move → 5 pts, capped at ±8
        intraday_return = ((current_price - open_price) / open_price) * 100
        intraday_pts    = float(np.clip(intraday_return * 5, -8, 8))

        # ── Component 2: Short-term trend (10-bar MA vs 30-bar MA) ───────────
        # Positive when recent average is above the medium-term average
        short_trend     = 0.0
        short_trend_pts = 0.0
        if len(close) >= 30:
            short_ma        = float(close.iloc[-10:].mean())
            med_ma          = float(close.iloc[-30:].mean())
            short_trend     = ((short_ma - med_ma) / med_ma) * 100
            short_trend_pts = float(np.clip(short_trend * 10, -6, 6))

        # ── Component 3: VWAP deviation ──────────────────────────────────────
        # Positive when price is above VWAP (institutional support)
        session_vwap = vwap(live_df)
        vwap_diff    = ((current_price - session_vwap) / session_vwap) * 100
        vwap_pts     = float(np.clip(vwap_diff * 5, -6, 6))

        # ── Aggregate and clamp ───────────────────────────────────────────────
        live_score = float(np.clip(
            intraday_pts + short_trend_pts + vwap_pts,
            -LIVE_SCORE_CAP,
            LIVE_SCORE_CAP
        ))

        price_details = {
            'current_price':   round(current_price, 2),
            'open_price':      round(open_price, 2),
            'intraday_return': round(intraday_return, 2),
            'vwap':            round(session_vwap, 2),
            'vwap_diff_pct':   round(vwap_diff, 3),
            'short_trend_pct': round(short_trend, 4),
        }

        return round(live_score, 2), price_details, True

    except Exception as e:
        print(f"[LivePrice] Error for {ticker}: {e}")
        traceback.print_exc()
        return 0.0, {}, False
