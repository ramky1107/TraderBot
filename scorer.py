"""
=============================================================================
scorer.py
=============================================================================
Rule-based technical scoring functions.
Each function converts a raw indicator value into a sentiment score
and a list of detected signal strings (shown in the UI action bar).

Provides:
  - score_rsi()              : RSI → score + signals
  - score_moving_averages()  : SMA crossovers → score + signals
  - score_macd()             : MACD crossover + histogram → score + signals
  - score_momentum()         : Multi-period momentum → score + signals
  - score_volatility()       : Relative volatility → score + signals
  - calculate_technical_score(): Orchestrates all sub-scorers
  - calculate_confidence_score(): Data quality + signal agreement → 0-100

Used by:
  - sentiment_analyzer.py
=============================================================================
"""

import numpy as np
import pandas as pd

import indicators as ind

# ─── Score Caps ───────────────────────────────────────────────────────────────

TECH_SCORE_CAP = 50   # Technical indicators max contribution to total score

# ─── RSI Thresholds ───────────────────────────────────────────────────────────

RSI_OVERSOLD_EXTREME   = 20
RSI_OVERSOLD           = 30
RSI_OVERSOLD_MILD      = 40
RSI_OVERBOUGHT_MILD    = 60
RSI_OVERBOUGHT         = 70
RSI_OVERBOUGHT_EXTREME = 80

# Minimum rows needed for reliable indicator calculations
MIN_ROWS = 50


# ─── RSI Scorer ───────────────────────────────────────────────────────────────

def score_rsi(rsi_value: float) -> tuple[float, list[str]]:
    """
    Convert an RSI reading into a score (-10 to +10) and detected signals.

    Contrarian logic: extreme readings get the strongest scores because
    they indicate potential reversals.

    Args:
        rsi_value: Current RSI value (0–100).

    Returns:
        Tuple of (score, signals[]).
    """
    signals: list[str] = []

    if pd.isna(rsi_value):
        return 0.0, signals

    if rsi_value < RSI_OVERSOLD_EXTREME:
        signals.append("🟢 RSI Extremely Oversold (<20)")
        return 10.0, signals
    elif rsi_value < RSI_OVERSOLD:
        signals.append("🟢 RSI Oversold (<30)")
        return 7.0, signals
    elif rsi_value < RSI_OVERSOLD_MILD:
        return 3.0, signals
    elif rsi_value < RSI_OVERBOUGHT_MILD:
        return 0.0, signals   # Neutral zone
    elif rsi_value < RSI_OVERBOUGHT:
        return -3.0, signals
    elif rsi_value < RSI_OVERBOUGHT_EXTREME:
        signals.append("🔴 RSI Overbought (>70)")
        return -7.0, signals
    else:
        signals.append("🔴 RSI Extremely Overbought (>80)")
        return -10.0, signals


# ─── Moving Average Scorer ────────────────────────────────────────────────────

def score_moving_averages(
    close: pd.Series,
    sma_20: pd.Series,
    sma_50: pd.Series,
    sma_200: pd.Series
) -> tuple[float, list[str]]:
    """
    Score based on price position relative to moving averages and
    Golden/Death Cross detection.

    Scoring (2.5 pts each):
      - Price above SMA20, SMA50, SMA200
      - SMA50 above SMA200 (Golden Cross) vs below (Death Cross)

    Args:
        close:   Closing price series.
        sma_20:  20-period SMA series.
        sma_50:  50-period SMA series.
        sma_200: 200-period SMA series.

    Returns:
        Tuple of (score in [-10, +10], signals[]).
    """
    signals: list[str] = []
    score   = 0.0
    price   = ind.safe_last(close)

    # Price vs each moving average (2.5 pts each)
    for sma_series, label in [(sma_20, 'SMA20'), (sma_50, 'SMA50'), (sma_200, 'SMA200')]:
        sma_val = ind.safe_last(sma_series, default=float('nan'))
        if not pd.isna(sma_val) and sma_val > 0:
            if price > sma_val:
                score += 2.5
            else:
                score -= 2.5

    # Golden Cross / Death Cross (SMA50 vs SMA200)
    sma50_val  = ind.safe_last(sma_50, default=float('nan'))
    sma200_val = ind.safe_last(sma_200, default=float('nan'))
    if not pd.isna(sma50_val) and not pd.isna(sma200_val) and sma200_val > 0:
        if sma50_val > sma200_val:
            score += 2.5
            signals.append("🟢 Golden Cross (SMA50 > SMA200)")
        else:
            score -= 2.5
            signals.append("🔴 Death Cross (SMA50 < SMA200)")

    return round(score, 2), signals


# ─── MACD Scorer ──────────────────────────────────────────────────────────────

def score_macd(
    macd_line: pd.Series,
    signal_line: pd.Series,
    histogram: pd.Series
) -> tuple[float, list[str]]:
    """
    Score based on MACD crossover and histogram momentum.

    Components:
      - MACD above/below signal line: ±5 pts
      - Histogram growing vs shrinking (momentum acceleration): ±5 pts

    Args:
        macd_line:   MACD line series.
        signal_line: Signal line series.
        histogram:   MACD histogram series.

    Returns:
        Tuple of (score in [-10, +10], signals[]).
    """
    signals: list[str] = []
    score   = 0.0

    macd_val   = ind.safe_last(macd_line, default=float('nan'))
    signal_val = ind.safe_last(signal_line, default=float('nan'))
    hist_val   = ind.safe_last(histogram, default=float('nan'))

    if pd.isna(macd_val) or pd.isna(signal_val):
        return 0.0, signals

    # MACD line vs signal line
    if macd_val > signal_val:
        score += 5.0
        signals.append("🟢 MACD Bullish Crossover")
    else:
        score -= 5.0
        signals.append("🔴 MACD Bearish Crossover")

    # Histogram momentum: is the move accelerating?
    if len(histogram) >= 2 and not pd.isna(hist_val):
        prev_hist = histogram.iloc[-2]
        if not pd.isna(prev_hist):
            if hist_val > prev_hist:
                score += 5.0
                signals.append("📈 MACD Momentum Increasing")
            else:
                score -= 5.0

    return round(score, 2), signals


# ─── Momentum Scorer ──────────────────────────────────────────────────────────

def score_momentum(close: pd.Series) -> tuple[float, list[str]]:
    """
    Score based on price momentum over 5, 20, and 60-day windows.

    Components:
      - 5-day return:  capped at ±3 pts
      - 20-day return: capped at ±3 pts
      - 60-day return: capped at ±4 pts

    Args:
        close: Closing price series.

    Returns:
        Tuple of (score in [-10, +10], signals[]).
    """
    signals: list[str] = []
    score   = 0.0
    n       = len(close)

    # 5-day momentum
    if n >= 5:
        ret_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100
        score += float(np.clip(ret_5d * 2, -3, 3))
        if ret_5d > 3:
            signals.append("🟢 Strong 5-Day Momentum")
        elif ret_5d < -3:
            signals.append("🔴 Weak 5-Day Momentum")

    # 20-day momentum
    if n >= 20:
        ret_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100
        score += float(np.clip(ret_20d, -3, 3))

    # 60-day momentum (longer-term trend)
    if n >= 60:
        ret_60d = (close.iloc[-1] / close.iloc[-60] - 1) * 100
        score += float(np.clip(ret_60d * 0.5, -4, 4))

    return round(score, 2), signals


# ─── Volatility Scorer ────────────────────────────────────────────────────────

def score_volatility(close: pd.Series) -> tuple[float, list[str]]:
    """
    Score based on recent volatility relative to historical volatility.

    Low recent volatility → calm market → bullish bias.
    High recent volatility → uncertainty → bearish bias.

    Args:
        close: Closing price series.

    Returns:
        Tuple of (score in [-10, +10], signals[]).
    """
    signals: list[str] = []
    score   = 0.0

    if len(close) < 20:
        return 0.0, signals

    returns      = close.pct_change().dropna()
    recent_vol   = returns.iloc[-20:].std() * np.sqrt(252) * 100   # annualised %
    historic_vol = returns.std() * np.sqrt(252) * 100

    if historic_vol > 0:
        vol_ratio = recent_vol / historic_vol
        score     = float(np.clip((1 - vol_ratio) * 10, -10, 10))

        if vol_ratio > 1.5:
            signals.append("⚠️ High Volatility Detected")
        elif vol_ratio < 0.7:
            signals.append("🟢 Low Volatility (Stable)")

    return round(score, 2), signals


# ─── Technical Score Orchestrator ─────────────────────────────────────────────

def calculate_technical_score(df: pd.DataFrame) -> tuple[float, dict, list[str]]:
    """
    Orchestrate all technical sub-scorers and aggregate into a single score.

    Args:
        df: OHLCV DataFrame (needs at least 'Close' column).

    Returns:
        Tuple of:
          - total_score : float in [-50, +50]
          - details     : dict with individual component scores and RSI value
          - signals     : list of detected signal strings for the UI action bar
    """
    if df.empty or len(df) < MIN_ROWS:
        return 0.0, {}, []

    close       = df['Close'].copy()
    all_signals: list[str] = []

    # ── RSI ──────────────────────────────────────────────────────────────────
    rsi_series  = ind.rsi(close)
    rsi_val     = ind.safe_last(rsi_series, default=float('nan'))
    rsi_score, rsi_sigs = score_rsi(rsi_val)
    all_signals.extend(rsi_sigs)

    # ── Moving Averages ───────────────────────────────────────────────────────
    sma_20  = ind.sma(close, 20)
    sma_50  = ind.sma(close, 50)
    sma_200 = ind.sma(close, 200)
    ma_score, ma_sigs = score_moving_averages(close, sma_20, sma_50, sma_200)
    all_signals.extend(ma_sigs)

    # ── MACD ─────────────────────────────────────────────────────────────────
    macd_line, signal_line, histogram = ind.macd(close)
    macd_score, macd_sigs = score_macd(macd_line, signal_line, histogram)
    all_signals.extend(macd_sigs)

    # ── Momentum ─────────────────────────────────────────────────────────────
    mom_score, mom_sigs = score_momentum(close)
    all_signals.extend(mom_sigs)

    # ── Volatility ────────────────────────────────────────────────────────────
    vol_score, vol_sigs = score_volatility(close)
    all_signals.extend(vol_sigs)

    # ── Aggregate ─────────────────────────────────────────────────────────────
    total = float(np.clip(
        rsi_score + ma_score + macd_score + mom_score + vol_score,
        -TECH_SCORE_CAP,
        TECH_SCORE_CAP
    ))

    details = {
        'rsi':        round(rsi_score, 2),
        'moving_avg': round(ma_score, 2),
        'macd':       round(macd_score, 2),
        'momentum':   round(mom_score, 2),
        'volatility': round(vol_score, 2),
        'rsi_value':  round(rsi_val, 2) if not pd.isna(rsi_val) else None,
    }

    return round(total, 2), details, all_signals


# ─── Confidence Score ─────────────────────────────────────────────────────────

def calculate_confidence_score(
    tech_details: dict,
    news_count: int,
    live_data_available: bool,
    data_rows: int
) -> int:
    """
    Calculate a confidence score (0–100) representing how reliable the
    overall sentiment score is.

    Factors:
      - Data quantity  : more historical rows → higher confidence (up to 30 pts)
      - Signal agreement: RSI, MACD, MA all agree direction → higher (up to 40 pts)
      - News coverage  : more articles analyzed → higher (up to 20 pts)
      - Live data      : intraday data available → +10 pts

    Args:
        tech_details:        Dict from calculate_technical_score().
        news_count:          Number of news articles analyzed.
        live_data_available: Whether intraday data was successfully fetched.
        data_rows:           Number of rows in the historical DataFrame.

    Returns:
        Confidence score as int in [0, 100].
    """
    confidence = 0

    # Data quantity (up to 30 pts)
    if data_rows >= 500:
        confidence += 30
    elif data_rows >= 200:
        confidence += 20
    elif data_rows >= 50:
        confidence += 10

    # Signal agreement (up to 40 pts)
    rsi_dir  = 1 if tech_details.get('rsi', 0) > 0 else -1
    macd_dir = 1 if tech_details.get('macd', 0) > 0 else -1
    ma_dir   = 1 if tech_details.get('moving_avg', 0) > 0 else -1
    mom_dir  = 1 if tech_details.get('momentum', 0) > 0 else -1

    agreement = sum([
        rsi_dir == macd_dir,
        rsi_dir == ma_dir,
        rsi_dir == mom_dir,
    ])
    confidence += int((agreement / 3) * 40)

    # News coverage (up to 20 pts)
    if news_count >= 10:
        confidence += 20
    elif news_count >= 5:
        confidence += 10
    elif news_count >= 1:
        confidence += 5

    # Live data (up to 10 pts)
    if live_data_available:
        confidence += 10

    return min(confidence, 100)
