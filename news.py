"""
=============================================================================
news.py
=============================================================================
News scraping and keyword-based sentiment analysis.

Provides:
  - get_pulse_news()       : Scrape Zerodha Pulse for market headlines
  - fetch_news_sentiment() : Analyze yfinance news headlines for a ticker

Used by:
  - main.py              (for the /api/pulse-news endpoint)
  - sentiment_analyzer.py (for the news component of the sentiment score)
=============================================================================
"""

import traceback
import numpy as np
import requests as http_requests
import yfinance as yf
from bs4 import BeautifulSoup

# ─── Sentiment Keyword Lists ──────────────────────────────────────────────────

# Words that suggest bullish market sentiment
BULLISH_KEYWORDS = [
    'surge', 'rally', 'gain', 'rise', 'jump', 'soar', 'record',
    'strong', 'beat', 'exceed', 'upgrade', 'buy', 'growth',
    'profit', 'earnings beat', 'outperform', 'bullish', 'positive',
    'high', 'boost', 'up', 'recover', 'breakout', 'momentum',
    'expansion', 'optimistic', 'innovative', 'opportunity',
    'dividend', 'stock split', 'acquisition',
]

# Words that suggest bearish market sentiment
BEARISH_KEYWORDS = [
    'fall', 'drop', 'decline', 'crash', 'plunge', 'loss',
    'weak', 'miss', 'downgrade', 'sell', 'warning', 'concern',
    'risk', 'bearish', 'negative', 'low', 'cut', 'down',
    'recession', 'lawsuit', 'investigation', 'fraud', 'debt',
    'layoff', 'bankruptcy', 'default', 'penalty', 'shortage',
    'overvalued', 'bubble', 'correction',
]

# Maximum score contribution from news component
NEWS_SCORE_CAP = 30


# ─── Headline Classifier ──────────────────────────────────────────────────────

def _classify_headline(title: str) -> tuple[int, str]:
    """
    Classify a single headline as bullish, bearish, or neutral using keyword
    matching. Returns (net_score, label).

    Args:
        title: Raw headline text.

    Returns:
        Tuple of (net_keyword_count, label) where label is
        'positive', 'negative', or 'neutral'.
    """
    text       = title.lower()
    bull_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
    bear_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text)
    net        = bull_count - bear_count
    label      = 'positive' if net > 0 else ('negative' if net < 0 else 'neutral')
    return net, label


# ─── yfinance News Sentiment ──────────────────────────────────────────────────

def fetch_news_sentiment(ticker: str) -> tuple[float, list[dict], str, int]:
    """
    Fetch recent news for `ticker` via yfinance and run keyword-based
    sentiment analysis on up to 15 headlines.

    Args:
        ticker: Stock symbol (e.g. 'RELIANCE.NS').

    Returns:
        Tuple of:
          - news_score    : float in [-30, +30]
          - headlines     : list of dicts {title, publisher, sentiment, url}
          - status_msg    : human-readable status string
          - article_count : number of articles analyzed (used for confidence)
    """
    try:
        stock = yf.Ticker(ticker)
        news  = stock.news

        if not news:
            return 0.0, [], "No news available", 0

        total_sentiment = 0
        headlines: list[dict] = []

        # Analyze up to 15 most recent articles
        for item in news[:15]:
            title     = item.get('title', '') or ''
            publisher = item.get('publisher', '') or ''
            net, label = _classify_headline(title)
            total_sentiment += net
            headlines.append({
                'title':     title,
                'publisher': publisher,
                'sentiment': label,
                'url':       item.get('link', '#'),
            })

        analyzed = len(headlines)
        if analyzed == 0:
            return 0.0, [], "No analyzable news", 0

        # Normalize: average sentiment per article, scaled to ±30
        avg_sentiment = total_sentiment / analyzed
        news_score    = float(np.clip(avg_sentiment * 10, -NEWS_SCORE_CAP, NEWS_SCORE_CAP))

        return round(news_score, 2), headlines, f"Analyzed {analyzed} articles", analyzed

    except Exception as e:
        print(f"[News] Sentiment error for {ticker}: {e}")
        traceback.print_exc()
        return 0.0, [], f"Error: {str(e)}", 0


# ─── Zerodha Pulse Scraper ────────────────────────────────────────────────────

_PULSE_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}


def _scrape_pulse_structured(soup: BeautifulSoup) -> list[dict]:
    """
    Try to extract headlines from known Zerodha Pulse CSS selectors.
    Returns up to 15 headline dicts.
    """
    headlines: list[dict] = []
    items = soup.select('.feed-item, li.box, .item, article')

    for item in items[:15]:
        title_el  = item.find('a') or item
        title     = title_el.get_text(strip=True)
        href      = title_el.get('href', '') if title_el.name == 'a' else ''
        pub_el    = item.find(class_='publisher') or item.find(class_='source')
        publisher = pub_el.get_text(strip=True) if pub_el else 'Pulse'

        if title and len(title) > 10:
            headlines.append({'title': title[:150], 'url': href, 'publisher': publisher})

    return headlines


def _scrape_pulse_fallback(soup: BeautifulSoup) -> list[dict]:
    """
    Fallback scraper: extract any <a> tag with text longer than 30 chars.
    Used when the structured scraper finds no items.
    """
    headlines: list[dict] = []
    for a_tag in soup.find_all('a', href=True)[:30]:
        title = a_tag.get_text(strip=True)
        href  = a_tag.get('href', '')
        if title and len(title) > 30:
            headlines.append({'title': title[:150], 'url': href, 'publisher': 'Pulse'})
            if len(headlines) >= 15:
                break
    return headlines


def get_pulse_news() -> dict:
    """
    Scrape the Zerodha Pulse homepage for market headlines.
    Tries structured CSS selectors first, falls back to link extraction.

    Returns:
        Dict with keys 'headlines' (list of dicts) and 'source' (str).
    """
    resp = http_requests.get(
        'https://pulse.zerodha.com/',
        headers=_PULSE_HEADERS,
        timeout=10
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'lxml')

    headlines = _scrape_pulse_structured(soup)
    if not headlines:
        headlines = _scrape_pulse_fallback(soup)

    return {'headlines': headlines, 'source': 'Zerodha Pulse'}
