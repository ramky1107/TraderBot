"""
=============================================================================
sentiment_analyzer.py
=============================================================================
Thin orchestrator: combines all analysis components into one result dict.

This module is intentionally minimal — all heavy logic lives in:
  - ai_model.py   : Random Forest prediction
  - scorer.py     : Technical indicator scoring
  - news.py       : News sentiment analysis
  - live_price.py : Intraday price action scoring
  - indicators.py : Raw indicator math

Public API:
  get_sentiment_score(ticker) → dict
=============================================================================
"""

import traceback
from datetime import datetime

import numpy as np
import yfinance as yf
import pandas as pd

# Import from our new focused modules
from ai_model   import model_manager
from scorer     import calculate_technical_score, calculate_confidence_score
from news       import fetch_news_sentiment
from live_price import calculate_live_price_score


# ─── Label Helper ─────────────────────────────────────────────────────────────

def _score_to_label(score: int) -> str:
    """
    Map a numeric score to a human-readable sentiment label.

    Thresholds:
      ≥ 60  → Very Bullish
      ≥ 30  → Bullish
      ≥ 10  → Slightly Bullish
      ≥ -10 → Neutral
      ≥ -30 → Slightly Bearish
      ≥ -60 → Bearish
      < -60 → Very Bearish
    """
    if score >= 60:  return 'Very Bullish'
    if score >= 30:  return 'Bullish'
    if score >= 10:  return 'Slightly Bullish'
    if score >= -10: return 'Neutral'
    if score >= -30: return 'Slightly Bearish'
    if score >= -60: return 'Bearish'
    return 'Very Bearish'


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def get_sentiment_score(ticker: str) -> dict:
    """
    Orchestrate all four analysis components and return a comprehensive
    result dict for the API to serve.

    Steps:
      1. Fetch 5Y daily data for technical analysis + AI model features
      2. Run AI model prediction (Random Forest)
      3. Run rule-based technical scoring (RSI, MACD, SMA, Momentum, Volatility)
      4. Fetch and score news sentiment
      5. Fetch and score live intraday price action
      6. Combine scores, calculate confidence, aggregate signals

    Result structure:
    {
      ticker, score, label, confidence,
      technical: { score, details, signals, dynamic_prediction },
      news:      { score, headlines, status },
      live:      { score, details },
      signals:   [ ...all detected signal strings... ],
      timestamp
    }
    """
    # Safe default result — returned as-is if everything fails
    result: dict = {
        'ticker':     ticker,
        'score':      0,
        'label':      'Neutral',
        'confidence': 0,
        'technical':  {'score': 0, 'details': {}, 'signals': [], 'dynamic_prediction': 0},
        'news':       {'score': 0, 'headlines': [], 'status': ''},
        'live':       {'score': 0, 'details': {}},
        'signals':    [],
        'timestamp':  datetime.now().isoformat(),
    }

    try:
        all_signals: list[str] = []
        tech_score  = 0.0
        tech_details: dict = {}
        data_rows   = 0

        # ── Step 1: Fetch 5Y daily historical data ────────────────────────────
        print(f"[Sentiment] Fetching 5Y data for {ticker}...")
        hist_df = yf.download(ticker, period='5y', interval='1d', progress=False)

        if not hist_df.empty:
            # Flatten MultiIndex columns (yfinance quirk)
            if isinstance(hist_df.columns, pd.MultiIndex):
                hist_df.columns = hist_df.columns.get_level_values(0)

            data_rows = len(hist_df)

            # ── Step 2: AI model prediction ───────────────────────────────────
            features      = model_manager.extract_current_features(hist_df)
            dynamic_score = model_manager.predict_score(ticker, features)

            # ── Step 3: Rule-based technical scoring ──────────────────────────
            tech_score, tech_details, tech_signals = calculate_technical_score(hist_df)
            all_signals.extend(tech_signals)

            result['technical'] = {
                'score':              tech_score,
                'details':            tech_details,
                'signals':            tech_signals,
                'dynamic_prediction': dynamic_score,
            }

            # Use the AI prediction as the primary technical component
            tech_score = dynamic_score
        else:
            print(f"[Sentiment] No historical data for {ticker}")

        # ── Step 4: News sentiment ─────────────────────────────────────────────
        print(f"[Sentiment] Fetching news for {ticker}...")
        news_score, headlines, news_status, news_count = fetch_news_sentiment(ticker)
        result['news'] = {
            'score':     news_score,
            'headlines': headlines[:10],   # Top 10 to the frontend
            'status':    news_status,
        }

        # ── Step 5: Live intraday price action ────────────────────────────────
        print(f"[Sentiment] Fetching live price for {ticker}...")
        live_score, price_details, live_available = calculate_live_price_score(ticker)
        result['live'] = {'score': live_score, 'details': price_details}

        # ── Step 6: Combine scores ────────────────────────────────────────────
        total_score      = int(np.clip(tech_score + news_score + live_score, -100, 100))
        result['score']  = total_score
        result['label']  = _score_to_label(total_score)

        # ── Step 7: Confidence ────────────────────────────────────────────────
        result['confidence'] = calculate_confidence_score(
            tech_details=tech_details,
            news_count=news_count,
            live_data_available=live_available,
            data_rows=data_rows,
        )

        # ── Step 8: Aggregate all signals for the action bar ──────────────────
        result['signals'] = all_signals

        print(
            f"[Sentiment] {ticker}: Score={total_score} "
            f"({result['label']}) | Confidence={result['confidence']}%"
        )

    except Exception as e:
        print(f"[Sentiment] Unhandled error for {ticker}: {e}")
        traceback.print_exc()
        result['error'] = str(e)

    return result
