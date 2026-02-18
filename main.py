"""
=============================================================================
main.py
=============================================================================
Flask + SocketIO backend for the Stock Market Simulator.

API Endpoints:
  GET  /                        → Serve index.html
  GET  /partials/<name>.html    → Serve HTML partial fragments
  GET  /api/stock-data          → OHLCV + indicators (cached per constants)
  GET  /api/live-price          → Current price + intraday change
  GET  /api/sentiment-score     → Full sentiment analysis
  GET  /api/financial-ratios    → P/E, P/B, ROE, etc.
  GET  /api/pulse-news          → Zerodha Pulse headlines
  POST /api/chatbot             → Gemini AI stock assistant

WebSocket Events:
  activate_news  (client → server) : Start broadcasting news for a ticker
  new_news       (server → client) : Push latest headlines to all clients
=============================================================================
"""

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import google.generativeai as genai
import os
import threading
import time

# ── Our modules ───────────────────────────────────────────────────────────────
import data_manager
import strategies
import sentiment_analyzer
from news       import get_pulse_news
from live_price import fetch_intraday_df
from constants  import (
    SERVER_HOST, SERVER_PORT, DEBUG,
    CACHE_TTL_STOCK, CACHE_TTL_SENTIMENT, CACHE_TTL_RATIOS, CACHE_TTL_NEWS,
    DEFAULT_TICKER, DEFAULT_PERIOD, DEFAULT_INTERVAL,
    CHART_BG_COLOR,
)

# ─── App Initialisation ───────────────────────────────────────────────────────

app      = Flask(__name__, static_folder='static')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins='*')

# ─── Gemini AI Setup ──────────────────────────────────────────────────────────

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_client = genai.GenerativeModel('gemini-pro')
    print('[Gemini] API configured.')
else:
    gemini_client = None
    print('[Gemini] WARNING: GEMINI_API_KEY not set.')

# ─── In-Memory Caches ─────────────────────────────────────────────────────────

data_cache       = {}   # { "TICKER_period_interval": { data, last_update } }
sentiment_cache  = {}   # { "TICKER": { data, last_update } }
ratios_cache     = {}   # { "TICKER": { data, last_update } }
pulse_news_cache = {'data': None, 'last_update': None}

# ─── WebSocket State ──────────────────────────────────────────────────────────

news_thread      = None
news_thread_lock = threading.Lock()
active_tickers   = set()


# ─── Formatting Helpers ───────────────────────────────────────────────────────

def fmt_large(val) -> str:
    """Format large numbers with T/B/Cr suffixes for Market Cap display."""
    if val is None:
        return 'N/A'
    if val >= 1e12:  return f'₹{val / 1e12:.1f}T'
    if val >= 1e9:   return f'₹{val / 1e9:.1f}B'
    if val >= 1e7:   return f'₹{val / 1e7:.1f}Cr'
    return f'₹{val:,.0f}'


def fmt_pct(val) -> str:
    """Format a decimal fraction as a percentage string."""
    return 'N/A' if val is None else f'{val * 100:.2f}%'


def fmt_ratio(val) -> str:
    """Format a ratio to 2 decimal places."""
    return 'N/A' if val is None else f'{val:.2f}'


def nan_to_none(val):
    """Convert NaN/inf to None so the value serialises cleanly to JSON null."""
    if val is None:
        return None
    try:
        if pd.isna(val) or np.isinf(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


# ─── Cache Helper ─────────────────────────────────────────────────────────────

def _is_cache_fresh(cache_entry: dict, ttl_minutes: int) -> bool:
    """Return True if the cache entry exists and is within its TTL."""
    if not cache_entry or 'last_update' not in cache_entry:
        return False
    age = datetime.now() - cache_entry['last_update']
    return age < timedelta(minutes=ttl_minutes)


# ─── Background News Broadcaster ─────────────────────────────────────────────

def _broadcast_news_loop():
    """
    Background thread: fetch Pulse news every 2 minutes and broadcast
    to all connected WebSocket clients while any ticker is active.
    """
    while True:
        try:
            if active_tickers:
                print(f'[WS] Broadcasting news for {active_tickers}...')
                news_data = get_pulse_news()
                socketio.emit('new_news', news_data)
        except Exception as e:
            print(f'[WS] News broadcast error: {e}')
        time.sleep(120)


# ─── Static File Routes ───────────────────────────────────────────────────────

@app.route('/')
def serve_index():
    """Serve the main HTML page."""
    return send_from_directory('static', 'index.html')


@app.route('/style.css')
def serve_css():
    return send_from_directory('static', 'style.css')


@app.route('/partials/<path:filename>')
def serve_partial(filename: str):
    """Serve HTML partial fragments from static/partials/."""
    return send_from_directory('static/partials', filename)


@app.route('/static/<path:filename>')
def serve_static(filename: str):
    """Serve any file under static/ (css/, js/, partials/, etc.)."""
    return send_from_directory('static', filename)


# ─── Stock Data Endpoint ──────────────────────────────────────────────────────

def _build_stock_response(df: pd.DataFrame, ticker: str) -> dict:
    """
    Serialise an enriched OHLCV DataFrame to a JSON-safe dict.
    NaN values become None (→ JSON null) to avoid frontend parse errors.
    """
    def safe_col(col: str) -> list:
        if col not in df.columns:
            return []
        return [nan_to_none(x) for x in df[col].tolist()]

    return {
        'ticker':      ticker,
        'dates':       df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
        'open':        df['Open'].tolist(),
        'high':        df['High'].tolist(),
        'low':         df['Low'].tolist(),
        'close':       df['Close'].tolist(),
        'volume':      df['Volume'].tolist(),
        'sma_20':      safe_col('SMA_20'),
        'sma_50':      safe_col('SMA_50'),
        'rsi':         safe_col('RSI'),
        'macd':        safe_col('MACD'),
        'macd_signal': safe_col('MACD_Signal'),
        'macd_hist':   safe_col('MACD_Hist'),
        'bb_upper':    safe_col('BB_Upper'),
        'bb_middle':   safe_col('BB_Middle'),
        'bb_lower':    safe_col('BB_Lower'),
    }


@app.route('/api/stock-data')
def get_stock_data():
    """
    Fetch OHLCV + technical indicators for a ticker.

    Query params:
      ticker   : Stock symbol (default from constants)
      period   : yfinance period string
      interval : yfinance interval string

    Cache TTL: CACHE_TTL_STOCK minutes per (ticker, period, interval).
    """
    try:
        ticker   = request.args.get('ticker',   DEFAULT_TICKER)
        period   = request.args.get('period',   DEFAULT_PERIOD)
        interval = request.args.get('interval', DEFAULT_INTERVAL)
        cache_key = f"{ticker}_{period}_{interval}"

        # Cache lookup
        if cache_key in data_cache and _is_cache_fresh(data_cache[cache_key], CACHE_TTL_STOCK):
            df = data_cache[cache_key]['data']
        else:
            df = data_manager.fetch_market_data(ticker=ticker, period=period, interval=interval)
            data_cache[cache_key] = {'data': df, 'last_update': datetime.now()}

        if df.empty:
            return jsonify({'error': f'No data for {ticker}'}), 404

        df = strategies.apply_strategies(df)
        return jsonify(_build_stock_response(df, ticker))

    except Exception as e:
        print(f'[API] /api/stock-data error: {e}')
        return jsonify({'error': str(e)}), 500


# ─── Live Price Endpoint ──────────────────────────────────────────────────────

@app.route('/api/live-price')
def get_live_price():
    """
    Return current price and intraday change for a ticker.

    Query params:
      ticker : Stock symbol
    """
    try:
        ticker  = request.args.get('ticker', DEFAULT_TICKER)
        live_df = fetch_intraday_df(ticker)

        if live_df.empty:
            return jsonify({'error': 'No live data'}), 404

        current_price = float(live_df['Close'].iloc[-1])
        open_price    = float(live_df['Open'].iloc[0])
        change        = current_price - open_price
        change_pct    = (change / open_price) * 100

        return jsonify({
            'ticker':        ticker,
            'current_price': round(current_price, 2),
            'open':          round(open_price, 2),
            'high':          round(float(live_df['High'].max()), 2),
            'low':           round(float(live_df['Low'].min()), 2),
            'change':        round(change, 2),
            'change_pct':    round(change_pct, 2),
            'timestamp':     datetime.now().isoformat(),
        })

    except Exception as e:
        print(f'[API] /api/live-price error: {e}')
        return jsonify({'error': str(e)}), 500


# ─── Sentiment Score Endpoint ─────────────────────────────────────────────────

@app.route('/api/sentiment-score')
def get_sentiment_score():
    """
    Run the full sentiment analysis pipeline for a ticker.
    Cache TTL: CACHE_TTL_SENTIMENT minutes.

    Query params:
      ticker : Stock symbol
    """
    try:
        ticker = request.args.get('ticker', DEFAULT_TICKER)

        if ticker in sentiment_cache and _is_cache_fresh(sentiment_cache[ticker], CACHE_TTL_SENTIMENT):
            return jsonify(sentiment_cache[ticker]['data'])

        result = sentiment_analyzer.get_sentiment_score(ticker)
        sentiment_cache[ticker] = {'data': result, 'last_update': datetime.now()}
        return jsonify(result)

    except Exception as e:
        print(f'[API] /api/sentiment-score error: {e}')
        return jsonify({'error': str(e)}), 500


# ─── Financial Ratios Endpoint ────────────────────────────────────────────────

@app.route('/api/financial-ratios')
def get_financial_ratios():
    """
    Fetch fundamental financial ratios via yfinance.
    Cache TTL: CACHE_TTL_RATIOS minutes.

    Query params:
      ticker : Stock symbol
    """
    try:
        import yfinance as yf
        ticker = request.args.get('ticker', DEFAULT_TICKER)

        if ticker in ratios_cache and _is_cache_fresh(ratios_cache[ticker], CACHE_TTL_RATIOS):
            return jsonify(ratios_cache[ticker]['data'])

        info   = yf.Ticker(ticker).info
        ratios = {
            'pe_ratio':       fmt_ratio(info.get('trailingPE')),
            'pb_ratio':       fmt_ratio(info.get('priceToBook')),
            'debt_equity':    fmt_ratio(info.get('debtToEquity')),
            'market_cap':     fmt_large(info.get('marketCap')),
            'dividend_yield': fmt_pct(info.get('dividendYield')),
            'roe':            fmt_pct(info.get('returnOnEquity')),
            'eps':            fmt_ratio(info.get('trailingEps')),
            'book_value':     fmt_ratio(info.get('bookValue')),
        }
        result = {'ticker': ticker, 'ratios': ratios}
        ratios_cache[ticker] = {'data': result, 'last_update': datetime.now()}
        return jsonify(result)

    except Exception as e:
        print(f'[API] /api/financial-ratios error: {e}')
        return jsonify({'error': str(e)}), 500


# ─── Pulse News Endpoint ──────────────────────────────────────────────────────

@app.route('/api/pulse-news')
def get_pulse_news_endpoint():
    """
    Scrape and return Zerodha Pulse headlines.
    Cache TTL: CACHE_TTL_NEWS minutes.
    """
    try:
        if _is_cache_fresh(pulse_news_cache, CACHE_TTL_NEWS):
            return jsonify(pulse_news_cache['data'])

        result = get_pulse_news()
        pulse_news_cache['data']        = result
        pulse_news_cache['last_update'] = datetime.now()
        return jsonify(result)

    except Exception as e:
        print(f'[API] /api/pulse-news error: {e}')
        return jsonify({'error': str(e), 'headlines': []}), 500


# ─── Chatbot Endpoint ─────────────────────────────────────────────────────────

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    """
    Stock-focused AI chatbot powered by Google Gemini.
    Requires GEMINI_API_KEY environment variable.

    Request body: { "message": "..." }
    """
    try:
        if not gemini_client:
            return jsonify({'error': 'Gemini API not configured.'}), 500

        data         = request.get_json()
        user_message = (data.get('message', '') or '').strip()
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        system_ctx = (
            'You are a helpful stock market assistant. Answer questions about stocks, '
            'trading strategies, technical indicators, and financial concepts. '
            'Keep responses concise. For real-time prices, direct users to the chart.'
        )
        prompt   = f"{system_ctx}\n\nUser: {user_message}"
        response = gemini_client.generate_content(prompt)
        return jsonify({'response': response.text, 'success': True})

    except Exception as e:
        print(f'[API] /api/chatbot error: {e}')
        return jsonify({'error': str(e)}), 500


# ─── WebSocket Event Handlers ─────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    print('[WS] Client connected')


@socketio.on('activate_news')
def handle_activate_news(data: dict):
    """
    Register a ticker for news broadcasting and send an immediate update.
    Starts the background broadcaster thread if not already running.
    """
    ticker = data.get('ticker')
    if not ticker:
        return

    active_tickers.add(ticker)
    print(f'[WS] News activated for {ticker}')

    # Immediate news push to the requesting client
    try:
        emit('new_news', get_pulse_news())
    except Exception as e:
        print(f'[WS] Immediate news error: {e}')

    # Start background broadcaster if not running
    global news_thread
    with news_thread_lock:
        if news_thread is None or not news_thread.is_alive():
            news_thread = threading.Thread(target=_broadcast_news_loop, daemon=True)
            news_thread.start()
            print('[WS] News broadcaster started')


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=' * 60)
    print('  Stock Market Simulator — Flask + SocketIO')
    print(f'  http://127.0.0.1:{SERVER_PORT}/')
    print('=' * 60)
    socketio.run(
        app,
        debug=DEBUG,
        host=SERVER_HOST,
        port=SERVER_PORT,
        allow_unsafe_werkzeug=True
    )