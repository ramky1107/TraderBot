"""
Sentiment Analyzer Module
Generates a score from -100 (very bearish) to +100 (very bullish)
based on:
  1. Technical time-series analysis (5 years of daily data)
  2. News sentiment indicators
  3. Live market price movement (1-minute intervals)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import traceback


# ─── Technical Analysis Score (weight: -50 to +50) ───────────────────────────

def _calculate_rsi(series, period=14):
    """Calculate RSI for a given price series."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _calculate_macd(series, fast=12, slow=26, signal=9):
    """Calculate MACD, signal line, and histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_technical_score(df):
    """
    Analyze 5 years of historical data using multiple technical indicators.
    Returns a score from -50 to +50.
    """
    if df.empty or len(df) < 50:
        return 0, {}

    close = df['Close'].copy()
    scores = {}

    # 1. RSI Score (-10 to +10)
    rsi = _calculate_rsi(close)
    current_rsi = rsi.iloc[-1]
    if pd.isna(current_rsi):
        rsi_score = 0
    elif current_rsi < 20:
        rsi_score = 10     # Extremely oversold → bullish reversal
    elif current_rsi < 30:
        rsi_score = 7      # Oversold → bullish
    elif current_rsi < 40:
        rsi_score = 3
    elif current_rsi < 60:
        rsi_score = 0      # Neutral
    elif current_rsi < 70:
        rsi_score = -3
    elif current_rsi < 80:
        rsi_score = -7     # Overbought → bearish
    else:
        rsi_score = -10    # Extremely overbought → bearish reversal
    scores['rsi'] = round(rsi_score, 2)

    # 2. Moving Average Trend Score (-10 to +10)
    sma_20 = close.rolling(20).mean()
    sma_50 = close.rolling(50).mean()
    sma_200 = close.rolling(200).mean()
    current_price = close.iloc[-1]

    ma_score = 0
    if not pd.isna(sma_20.iloc[-1]):
        ma_score += 2.5 if current_price > sma_20.iloc[-1] else -2.5
    if not pd.isna(sma_50.iloc[-1]):
        ma_score += 2.5 if current_price > sma_50.iloc[-1] else -2.5
    if not pd.isna(sma_200.iloc[-1]):
        ma_score += 2.5 if current_price > sma_200.iloc[-1] else -2.5
    # Golden cross / death cross
    if not pd.isna(sma_50.iloc[-1]) and not pd.isna(sma_200.iloc[-1]):
        ma_score += 2.5 if sma_50.iloc[-1] > sma_200.iloc[-1] else -2.5
    scores['moving_avg'] = round(ma_score, 2)

    # 3. MACD Score (-10 to +10)
    macd_line, signal_line, histogram = _calculate_macd(close)
    macd_val = macd_line.iloc[-1]
    signal_val = signal_line.iloc[-1]
    hist_val = histogram.iloc[-1]

    macd_score = 0
    if not pd.isna(macd_val) and not pd.isna(signal_val):
        # MACD above signal = bullish
        macd_score += 5 if macd_val > signal_val else -5
        # Histogram growing = momentum
        if len(histogram) >= 2 and not pd.isna(histogram.iloc[-2]):
            macd_score += 5 if hist_val > histogram.iloc[-2] else -5
    scores['macd'] = round(macd_score, 2)

    # 4. Price Momentum Score (-10 to +10)
    momentum_score = 0
    if len(close) >= 5:
        ret_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100
        momentum_score += np.clip(ret_5d * 2, -3, 3)
    if len(close) >= 20:
        ret_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100
        momentum_score += np.clip(ret_20d, -3, 3)
    if len(close) >= 60:
        ret_60d = (close.iloc[-1] / close.iloc[-60] - 1) * 100
        momentum_score += np.clip(ret_60d * 0.5, -4, 4)
    scores['momentum'] = round(float(momentum_score), 2)

    # 5. Volatility Score (-10 to +10)
    if len(close) >= 20:
        returns = close.pct_change().dropna()
        recent_vol = returns.iloc[-20:].std() * np.sqrt(252) * 100
        long_vol = returns.std() * np.sqrt(252) * 100
        # Low vol relative to history = bullish, high vol = bearish
        vol_ratio = recent_vol / long_vol if long_vol > 0 else 1
        vol_score = np.clip((1 - vol_ratio) * 10, -10, 10)
    else:
        vol_score = 0
    scores['volatility'] = round(float(vol_score), 2)

    total = rsi_score + ma_score + macd_score + momentum_score + vol_score
    total = np.clip(total, -50, 50)
    return round(float(total), 2), scores


# ─── News Sentiment Score (weight: -30 to +30) ──────────────────────────────

def fetch_news_sentiment(ticker):
    """
    Fetch news sentiment using yfinance's built-in news API.
    Returns a score from -30 to +30 and a list of headlines.
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.news

        if not news:
            return 0, [], "No news available"

        # Simple keyword-based sentiment analysis
        bullish_keywords = [
            'surge', 'rally', 'gain', 'rise', 'jump', 'soar', 'record',
            'strong', 'beat', 'exceed', 'upgrade', 'buy', 'growth',
            'profit', 'earnings beat', 'outperform', 'bullish', 'positive',
            'high', 'boost', 'up', 'recover', 'breakout', 'momentum',
            'expansion', 'optimistic', 'innovative', 'opportunity',
            'dividend', 'stock split', 'acquisition'
        ]
        bearish_keywords = [
            'fall', 'drop', 'decline', 'crash', 'plunge', 'loss',
            'weak', 'miss', 'downgrade', 'sell', 'warning', 'concern',
            'risk', 'bearish', 'negative', 'low', 'cut', 'down',
            'recession', 'lawsuit', 'investigation', 'fraud', 'debt',
            'layoff', 'bankruptcy', 'default', 'penalty', 'shortage',
            'overvalued', 'bubble', 'correction'
        ]

        total_sentiment = 0
        headlines = []
        analyzed_count = 0

        for item in news[:15]:   # Analyze up to 15 recent articles
            title = item.get('title', '') or ''
            # yfinance news items can also have 'relatedTickers'
            publisher = item.get('publisher', '') or ''
            headline_text = title.lower()

            bull_count = sum(1 for kw in bullish_keywords if kw in headline_text)
            bear_count = sum(1 for kw in bearish_keywords if kw in headline_text)

            sentiment = bull_count - bear_count
            total_sentiment += sentiment
            analyzed_count += 1

            sentiment_label = 'positive' if sentiment > 0 else ('negative' if sentiment < 0 else 'neutral')
            headlines.append({
                'title': title,
                'publisher': publisher,
                'sentiment': sentiment_label
            })

        if analyzed_count == 0:
            return 0, headlines, "No analyzable news"

        # Normalize to -30 to +30 range
        avg_sentiment = total_sentiment / analyzed_count
        news_score = np.clip(avg_sentiment * 10, -30, 30)

        return round(float(news_score), 2), headlines, f"Analyzed {analyzed_count} articles"

    except Exception as e:
        print(f"News sentiment error: {e}")
        traceback.print_exc()
        return 0, [], f"Error: {str(e)}"


# ─── Live Price Score (weight: -20 to +20) ────────────────────────────────────

def calculate_live_price_score(ticker):
    """
    Analyze live price using 1-minute interval data.
    Returns a score from -20 to +20 and price details.
    """
    try:
        # Fetch 1-day of 1-minute data
        live_df = yf.download(ticker, period="1d", interval="1m", progress=False)

        if live_df.empty or len(live_df) < 5:
            # Fallback: use 5-day at 5-minute interval
            live_df = yf.download(ticker, period="5d", interval="5m", progress=False)

        if live_df.empty:
            return 0, {}

        # Flatten MultiIndex if present
        if isinstance(live_df.columns, pd.MultiIndex):
            live_df.columns = live_df.columns.get_level_values(0)

        close = live_df['Close']
        current_price = float(close.iloc[-1])
        open_price = float(live_df['Open'].iloc[0])

        # Intraday return
        intraday_return = ((current_price - open_price) / open_price) * 100

        # Short-term momentum (last 30 bars)
        if len(close) >= 30:
            short_ma = float(close.iloc[-10:].mean())
            med_ma = float(close.iloc[-30:].mean())
            short_trend = ((short_ma - med_ma) / med_ma) * 100
        else:
            short_trend = 0

        # VWAP comparison
        if 'Volume' in live_df.columns:
            vwap = float((live_df['Close'] * live_df['Volume']).sum() / live_df['Volume'].sum())
            vwap_diff = ((current_price - vwap) / vwap) * 100
        else:
            vwap = current_price
            vwap_diff = 0

        # Calculate score
        live_score = 0
        live_score += np.clip(intraday_return * 5, -8, 8)       # Intraday return
        live_score += np.clip(short_trend * 10, -6, 6)          # Short-term trend
        live_score += np.clip(vwap_diff * 5, -6, 6)             # VWAP position

        live_score = np.clip(live_score, -20, 20)

        price_details = {
            'current_price': round(current_price, 2),
            'open_price': round(open_price, 2),
            'intraday_return': round(intraday_return, 2),
            'vwap': round(vwap, 2),
            'short_trend': round(short_trend, 4)
        }

        return round(float(live_score), 2), price_details

    except Exception as e:
        print(f"Live price score error: {e}")
        traceback.print_exc()
        return 0, {}


# ─── Main Combined Score ──────────────────────────────────────────────────────

def get_sentiment_score(ticker):
    """
    Main function: combines technical, news, and live price analysis.
    Returns a comprehensive sentiment score from -100 to +100.
    """
    result = {
        'ticker': ticker,
        'score': 0,
        'label': 'Neutral',
        'technical': {'score': 0, 'details': {}},
        'news': {'score': 0, 'headlines': [], 'status': ''},
        'live': {'score': 0, 'details': {}},
        'timestamp': datetime.now().isoformat()
    }

    try:
        # 1. Fetch 5 years of historical data for technical analysis
        print(f"[Sentiment] Fetching 5-year data for {ticker}...")
        hist_df = yf.download(ticker, period="5y", interval="1d", progress=False)

        if not hist_df.empty:
            if isinstance(hist_df.columns, pd.MultiIndex):
                hist_df.columns = hist_df.columns.get_level_values(0)
            tech_score, tech_details = calculate_technical_score(hist_df)
            result['technical'] = {'score': tech_score, 'details': tech_details}
        else:
            tech_score = 0

        # 2. News sentiment
        print(f"[Sentiment] Fetching news for {ticker}...")
        news_score, headlines, news_status = fetch_news_sentiment(ticker)
        result['news'] = {
            'score': news_score,
            'headlines': headlines[:10],  # Send top 10 to frontend
            'status': news_status
        }

        # 3. Live price analysis (1-minute intervals)
        print(f"[Sentiment] Fetching live price for {ticker}...")
        live_score, price_details = calculate_live_price_score(ticker)
        result['live'] = {'score': live_score, 'details': price_details}

        # 4. Combine scores
        total_score = tech_score + news_score + live_score
        total_score = int(np.clip(total_score, -100, 100))
        result['score'] = total_score

        # 5. Label
        if total_score >= 60:
            result['label'] = 'Very Bullish'
        elif total_score >= 30:
            result['label'] = 'Bullish'
        elif total_score >= 10:
            result['label'] = 'Slightly Bullish'
        elif total_score >= -10:
            result['label'] = 'Neutral'
        elif total_score >= -30:
            result['label'] = 'Slightly Bearish'
        elif total_score >= -60:
            result['label'] = 'Bearish'
        else:
            result['label'] = 'Very Bearish'

        print(f"[Sentiment] {ticker}: Score={total_score} ({result['label']})")

    except Exception as e:
        print(f"[Sentiment] Error for {ticker}: {e}")
        traceback.print_exc()
        result['error'] = str(e)

    return result
