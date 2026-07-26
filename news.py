"""
=============================================================================
news.py
=============================================================================
News scraping and keyword-based sentiment analysis.

Provides:
  - get_pulse_news()              : Scrape Zerodha Pulse for market headlines
  - fetch_news_sentiment()        : Analyze yfinance news headlines for a ticker
  - get_gemini_news_headlines()   : Use Gemini AI to simplify and process news
  - process_company_news_gemini() : Process company-specific news via Gemini

Used by:
  - main.py              (for the /api/pulse-news endpoint and news processing)
  - sentiment_analyzer.py (for the news component of the sentiment score)
=============================================================================
"""

import traceback
import time
import numpy as np
import requests as http_requests
import yfinance as yf
from bs4 import BeautifulSoup
import os
import logging
import json
from urllib.parse import urlparse
from dotenv import load_dotenv

try:
    import google.genai as genai
except Exception:  # pragma: no cover - optional dependency fallback
    genai = None

# ─── Load Environment Variables & Configure Gemini ──────────────────────────────
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
USE_GEMINI_NEWS = os.getenv('USE_GEMINI_NEWS', 'True').lower() == 'true'
MAX_HEADLINES = int(os.getenv('MAX_HEADLINES_PER_COMPANY', '5'))
GEMINI_NEWS_MODEL = os.getenv('GEMINI_NEWS_MODEL', 'gemini-1.5-flash')

# Configure Gemini
if GEMINI_API_KEY:
    logger.info('[Gemini] News module configured with API key.')
else:
    logger.warning('[Gemini] API key not found. Gemini news processing disabled.')

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

def build_market_news_url(company_url: str) -> str:
    """Build the Groww market-news URL for a company page link."""
    if not company_url:
        return ''
    company_url = company_url.rstrip('/')
    if company_url.endswith('/market-news'):
        return company_url
    return f'{company_url}/market-news'


def _classify_headline(title: str) -> tuple[int, str]:
    """
    Classify a single headline as bullish, bearish, or neutral using keyword matching.
    Returns a score and a label for the headline sentiment.

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
    Fetch recent news for a ticker through yfinance and score the headlines.
    This provides a lightweight sentiment signal for the stock.

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
    Extract headlines from known Zerodha Pulse CSS selectors.
    Returns up to 15 headline entries for display or analysis.
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
    Fall back to generic link extraction when the structured scraper finds no items.
    This keeps the news collection logic resilient.
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
    The function tries structured selectors first and falls back to generic link parsing.

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


# ─── Groww Feed Parsing ───────────────────────────────────────────────────────

GROWW_FEED_URL = 'https://groww.in/v2/api/feed/public?page=1&publisherId=stocknewssummary&size=50'
GROWW_FEED_CACHE: dict = {'items': [], 'fetched_at': 0.0}
GROWW_PAGE_CACHE: dict = {}


def fetch_groww_news(page: int = 1, size: int = 50) -> list[dict]:
    """Fetch recent stock-news-summary items from Groww's public feed with short caching."""
    now = time.time()
    if now - GROWW_FEED_CACHE['fetched_at'] < 300 and GROWW_FEED_CACHE['items']:
        return GROWW_FEED_CACHE['items']

    try:
        url = GROWW_FEED_URL.replace('page=1', f'page={page}').replace('size=50', f'size={size}')
        resp = http_requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        feed = payload.get('feed', []) if isinstance(payload, dict) else []
        items = []
        for entry in feed:
            data = entry.get('data', {}) or {}
            cta = (data.get('cta') or [{}])[0] if data.get('cta') else {}
            title = data.get('title') or entry.get('title') or ''
            body = data.get('body') or ''
            company_name = cta.get('ctaText') or entry.get('name') or ''
            company_url = cta.get('ctaUrl') or ''
            if title:
                items.append({
                    'company': company_name,
                    'title': title,
                    'body': body,
                    'ctaUrl': company_url,
                    'marketNewsUrl': build_market_news_url(company_url),
                    'publishedAt': entry.get('publishedAt'),
                })
        GROWW_FEED_CACHE['items'] = items
        GROWW_FEED_CACHE['fetched_at'] = now
        return items
    except Exception as exc:
        logger.warning(f'[Groww] Failed to fetch feed: {exc}')
        return GROWW_FEED_CACHE['items'] or []


def derive_outlook_from_news(company: str, title: str, body: str, page_excerpt: str = '') -> dict:
    """Convert Groww news text into a simple bullish, bearish, mixed, or neutral trading outlook."""
    text = ' '.join([company or '', title or '', body or '', page_excerpt or '']).lower()

    bullish_hits = [kw for kw in ['profit', 'strong', 'rise', 'rally', 'beat', 'record', 'growth', 'upgrade', 'order', 'surge', 'gain', 'outperform', 'expansion', 'dividend', 'acquisition'] if kw in text]
    bearish_hits = [kw for kw in ['loss', 'fall', 'decline', 'drop', 'warn', 'risk', 'cut', 'miss', 'downgrade', 'fraud', 'bankruptcy', 'default', 'penalty', 'lawsuit', 'recession', 'weak', 'shortage'] if kw in text]

    if bullish_hits and not bearish_hits:
        sentiment = 'bullish'
    elif bearish_hits and not bullish_hits:
        sentiment = 'bearish'
    elif bullish_hits and bearish_hits:
        sentiment = 'mixed'
    else:
        sentiment = 'neutral'

    if sentiment == 'bullish':
        summary = f"{company or 'The company'} is bullish from the latest headlines, with constructive catalysts that could support a positive intraday bias."
        day_trade_plan = 'Watch for a breakout above the opening range and keep a tight stop if the move fails; prefer buying on strength with a defined risk.'
    elif sentiment == 'bearish':
        summary = f"{company or 'The company'} is bearish from the latest headlines, and the stock could remain under pressure today."
        day_trade_plan = 'Watch for a breakdown below support and avoid aggressive longs until price stabilizes; prefer short setups only if momentum confirms.'
    elif sentiment == 'mixed':
        summary = f"{company or 'The company'} is mixed from the latest headlines, so the near-term move is likely to be choppy."
        day_trade_plan = 'Trade the range until a clear breakout or breakdown appears; keep position size small and use strict stops.'
    else:
        summary = f"{company or 'The company'} is neutral from the latest headlines, with no clear directional catalyst yet."
        day_trade_plan = 'Stay in a wait-and-watch mode and focus on price action around key support and resistance levels.'

    return {
        'company': company or 'Unknown',
        'sentiment': sentiment,
        'summary': summary,
        'day_trade_plan': day_trade_plan,
        'bias': 'positive' if sentiment == 'bullish' else 'negative' if sentiment == 'bearish' else 'neutral',
        'signals': {
            'bullish_hits': bullish_hits[:5],
            'bearish_hits': bearish_hits[:5],
        },
    }


def _fetch_market_news_excerpt(company_url: str) -> str:
    """Fetch a short excerpt from the Groww market-news page for extra context."""
    if not company_url:
        return ''
    market_news_url = build_market_news_url(company_url)
    if not market_news_url:
        return ''

    cache_key = market_news_url
    now = time.time()
    if cache_key in GROWW_PAGE_CACHE and now - GROWW_PAGE_CACHE[cache_key]['fetched_at'] < 600:
        return GROWW_PAGE_CACHE[cache_key]['excerpt']

    try:
        response = http_requests.get(market_news_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        meta_description = soup.find('meta', attrs={'name': 'description'})
        if meta_description and meta_description.get('content'):
            excerpt = meta_description['content'][:500]
        else:
            title = soup.title.get_text(' ', strip=True) if soup.title else ''
            text = ' '.join(soup.stripped_strings)
            excerpt = ' '.join([title, text])[:500]
        GROWW_PAGE_CACHE[cache_key] = {'excerpt': excerpt, 'fetched_at': now}
        return excerpt
    except Exception as exc:
        logger.warning(f'[Groww] Failed to fetch market-news page excerpt: {exc}')
        return GROWW_PAGE_CACHE.get(cache_key, {}).get('excerpt', '')


def get_groww_company_outlook(company: str, company_url: str = '', page_excerpt: str = '') -> dict:
    """Fetch Groww feed items for a company and build a concise trading outlook."""
    items = fetch_groww_news()
    matching = []
    for item in items:
        if company and company.lower() in (item.get('company') or '').lower():
            matching.append(item)
        elif company_url and company_url.lower() in (item.get('ctaUrl') or '').lower():
            matching.append(item)

    if not page_excerpt and company_url:
        page_excerpt = _fetch_market_news_excerpt(company_url)

    if matching:
        item = matching[0]
        return derive_outlook_from_news(
            company=item.get('company') or company,
            title=item.get('title', ''),
            body=item.get('body', ''),
            page_excerpt=page_excerpt,
        )

    if items:
        first_item = items[0]
        return derive_outlook_from_news(
            company=company or first_item.get('company', ''),
            title=first_item.get('title', ''),
            body=first_item.get('body', ''),
            page_excerpt=page_excerpt,
        )

    return derive_outlook_from_news(company=company, title='', body='', page_excerpt=page_excerpt)


# ─── Gemini AI News Processing ───────────────────────────────────────────────────

def get_gemini_news_headlines(company: str, headlines: list[str] | list[dict]) -> dict:
    """
    Use Google Gemini to simplify and summarize news headlines for a company.
    Returns headlines in simple English suitable for further processing.

    Args:
        company: Company name or stock ticker (e.g., 'Apple', 'AAPL')
        headlines: List of headline strings or dicts with 'title' key

    Returns:
        Dict with:
          - 'company': Company name
          - 'headlines': List of simplified headline strings
          - 'summary': Brief summary of the news sentiment
          - 'status': Processing status message
          - 'raw_output': Full Gemini response for logging
    """
    if not USE_GEMINI_NEWS or not GEMINI_API_KEY or genai is None:
        logger.warning(f'[Gemini News] Disabled for {company}. Set USE_GEMINI_NEWS=True and GEMINI_API_KEY, and ensure google-genai is installed.')
        return {
            'company': company,
            'headlines': [],
            'summary': 'Gemini news processing disabled',
            'status': 'disabled',
            'raw_output': '',
        }

    try:
        # Extract headlines text
        headline_texts = []
        if headlines:
            for h in headlines[:MAX_HEADLINES]:
                if isinstance(h, dict):
                    headline_texts.append(h.get('title', str(h)))
                else:
                    headline_texts.append(str(h))

        if not headline_texts:
            return {
                'company': company,
                'headlines': [],
                'summary': 'No headlines provided',
                'status': 'empty',
                'raw_output': '',
            }

        # Prepare headlines for Gemini
        headlines_str = '\n'.join(f'- {h}' for h in headline_texts)

        # Prompt for Gemini
        prompt = f"""You are a financial news analyst. Process the following news headlines for {company} and provide:

HEADLINES:
{headlines_str}

TASK:
1. Extract the key headlines and rewrite them in simple, clear English (max 15 words each)
2. Ensure each headline is factual and easy to understand
3. Identify overall sentiment (bullish/bearish/neutral)
4. Provide a brief summary (2-3 sentences)

FORMAT YOUR RESPONSE AS:
HEADLINES:
- Headline 1
- Headline 2
- Headline 3

SENTIMENT: [bullish/bearish/neutral]
SUMMARY: [2-3 sentence summary]
"""

        # Call Gemini API
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_NEWS_MODEL,
            contents=prompt
        )

        raw_output = response.text
        logger.info(f'[Gemini News] Raw output for {company}:\n{raw_output}')

        # Parse response
        lines = raw_output.split('\n')
        simplified_headlines = []
        sentiment = 'neutral'
        summary = ''

        in_headlines_section = False
        in_summary_section = False

        for line in lines:
            line_lower = line.lower().strip()

            if 'headlines:' in line_lower:
                in_headlines_section = True
                in_summary_section = False
                continue

            if 'sentiment:' in line_lower:
                # Extract sentiment
                sentiment = line_lower.replace('sentiment:', '').strip().split()[0]
                in_headlines_section = False
                in_summary_section = False
                continue

            if 'summary:' in line_lower:
                in_headlines_section = False
                in_summary_section = True
                # Get text after "SUMMARY:"
                parts = line.split(':', 1)
                if len(parts) > 1:
                    summary += parts[1].strip() + ' '
                continue

            # Collect headlines
            if in_headlines_section and line.strip().startswith('-'):
                headline = line.strip()[1:].strip()
                if headline and len(headline) > 5:
                    simplified_headlines.append(headline)

            # Collect summary
            if in_summary_section and line.strip():
                summary += line.strip() + ' '

        # Ensure we have at least one headline
        if not simplified_headlines and headline_texts:
            simplified_headlines = headline_texts[:MAX_HEADLINES]

        result = {
            'company': company,
            'headlines': simplified_headlines[:MAX_HEADLINES],
            'summary': summary.strip()[:200],
            'sentiment': sentiment,
            'status': 'success',
            'raw_output': raw_output,
        }

        logger.info(f'[Gemini News] Processed {company}: {len(simplified_headlines)} headlines extracted')
        return result

    except Exception as e:
        logger.error(f'[Gemini News] Error processing {company}: {str(e)}')
        logger.exception(e)
        return {
            'company': company,
            'headlines': [],
            'summary': f'Error: {str(e)}',
            'status': 'error',
            'raw_output': f'Error: {str(e)}',
        }


def process_company_news_gemini(company: str, ticker: str | None = None) -> dict:
    """
    Fetch the latest news for a company and process it with Gemini for easier reading.

    Args:
        company: Company name (e.g., 'Apple')
        ticker: Optional stock ticker (e.g., 'AAPL'). If provided, fetches yfinance news.

    Returns:
        Dict with processed headlines and analysis
    """
    if not USE_GEMINI_NEWS:
        logger.warning('[Gemini News] Processing disabled.')
        return {'status': 'disabled', 'company': company}

    try:
        headlines = []

        # Try to fetch from yfinance if ticker provided
        if ticker:
            try:
                stock = yf.Ticker(ticker)
                news = stock.news
                if news:
                    headlines = [item.get('title', '') for item in news[:MAX_HEADLINES]]
                    logger.info(f'[Gemini News] Fetched {len(headlines)} headlines from yfinance for {ticker}')
            except Exception as e:
                logger.warning(f'[Gemini News] Could not fetch yfinance news for {ticker}: {e}')

        # If no news from yfinance, create placeholder
        if not headlines:
            headlines = [f'No recent news found for {company}']

        # Process with Gemini
        result = get_gemini_news_headlines(company, headlines)
        return result

    except Exception as e:
        logger.error(f'[Gemini News] Error in process_company_news_gemini: {e}')
        return {
            'status': 'error',
            'company': company,
            'error': str(e),
        }