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
import google.genai as genai
import os
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import logging

# ─── Load Environment Variables ────────────────────────────────────────────────
load_dotenv()

# ─── Setup Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info('[Gemini] API configured successfully.')
        # Test the API key with a simple call
        test_response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents='Say "Hello" in one word.'
        )
        if test_response.text.strip():
            logger.info('[Gemini] API key validated successfully.')
        else:
            logger.warning('[Gemini] API key test returned empty response')
    except Exception as e:
        logger.error(f'[Gemini] API key validation failed: {e}')
        logger.warning('[Gemini] Please check your GEMINI_API_KEY in .env file')
        client = None
else:
    client = None
    logger.warning('[Gemini] WARNING: GEMINI_API_KEY not set in environment.')
    logger.info('[Gemini] Get your free API key from: https://aistudio.google.com/app/apikey')

# ─── Email Setup ──────────────────────────────────────────────────────────────

EMAIL_USER = os.getenv('EMAIL_USER', '')
EMAIL_PASS = os.getenv('EMAIL_PASS', '')  # App password for Gmail
EMAIL_TO = os.getenv('EMAIL_TO', '')  # User's email
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

if EMAIL_USER and EMAIL_PASS and EMAIL_TO:
    logger.info('[Email] Configured for sending reports.')
else:
    logger.warning('[Email] WARNING: Email credentials not set.')

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
                logger.info(f'[WS] Broadcasting news for {active_tickers}...')
                news_data = get_pulse_news()
                socketio.emit('new_news', news_data)
        except Exception as e:
            logger.error(f'[WS] News broadcast error: {e}')
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
        logger.error(f'[API] /api/stock-data error: {e}')
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
        logger.error(f'[API] /api/live-price error: {e}')
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
        logger.error(f'[API] /api/sentiment-score error: {e}')
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
        logger.error(f'[API] /api/financial-ratios error: {e}')
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
        logger.error(f'[API] /api/pulse-news error: {e}')
        return jsonify({'error': str(e), 'headlines': []}), 500


# ─── Gemini News Headlines Endpoint ───────────────────────────────────────────

@app.route('/api/gemini-news', methods=['GET'])
def get_gemini_news():
    """
    Get latest news for a company and process with Gemini AI.
    Extracts simple English headlines suitable for further processing.
    
    Query params:
      company : Company name (e.g., 'Apple')
      ticker  : Optional stock ticker (e.g., 'AAPL')
    
    Returns:
      JSON with simplified headlines, sentiment, and raw Gemini output for logging
    """
    try:
        company = request.args.get('company', 'UNKNOWN')
        ticker = request.args.get('ticker', '')
        
        # Import the news processing function
        from news import process_company_news_gemini
        
        logger.info(f'[Gemini News] Processing news for {company} (ticker: {ticker})')
        result = process_company_news_gemini(company, ticker)
        
        logger.info(f'[Gemini News] Result for {company}: {len(result.get("headlines", []))} headlines')
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f'[API] /api/gemini-news error: {e}')
        return jsonify({
            'status': 'error',
            'error': str(e),
            'company': request.args.get('company', 'UNKNOWN')
        }), 500


# ─── NIFTY Analysis and Email Functions ───────────────────────────────────────

def generate_nifty_report():
    """
    Generate a detailed buy/sell report for NIFTY using Gemini AI.
    """
    if not client:
        return "Gemini API not configured."

    try:
        # Fetch recent NIFTY data
        df = data_manager.fetch_market_data(ticker="^NSEI", interval="1d", period="60d")
        if df.empty:
            return "Unable to fetch NIFTY data."

        # Get current price and change
        current_price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
        change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close != 0 else 0

        # Simple trend analysis
        ma_20 = df['Close'].rolling(20).mean().iloc[-1]
        ma_50 = df['Close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else None

        # Volume analysis
        avg_volume = df['Volume'].mean()
        recent_volume = df['Volume'].iloc[-1]

        # Prepare data summary
        data_summary = f"""
        Current Price: {current_price:.2f}
        Change: {change_pct:.2f}%
        20-day MA: {ma_20:.2f}
        50-day MA: {ma_50:.2f if ma_50 else 'N/A'}
        Average Volume: {avg_volume:.0f}
        Recent Volume: {recent_volume:.0f}
        Data Points: {len(df)}
        """

        # Prepare prompt for Gemini
        prompt = f"""
        Analyze the NIFTY index and provide a detailed trading report:

        {data_summary}

        Historical data statistics:
        {df[['Open', 'High', 'Low', 'Close', 'Volume']].tail(10).to_string()}

        Please provide:
        1. Current market trend analysis
        2. Technical indicators interpretation (MA crossover, volume analysis)
        3. Support and resistance levels
        4. Risk assessment and market sentiment
        5. Clear BUY/SELL/HOLD recommendation with entry/exit points
        6. Short-term and long-term outlook

        Format as a professional trading report.
        """

        response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        return response.text

    except Exception as e:
        return f"Error generating report: {str(e)}"


def send_email_report(subject, body):
    """
    Send an email with the report.
    """
    if not EMAIL_USER or not EMAIL_PASS or not EMAIL_TO:
        logger.warning("[Email] Email not configured.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        text = msg.as_string()
        server.sendmail(EMAIL_USER, EMAIL_TO, text)
        server.quit()

        print("[Email] Report sent successfully.")
        return True

    except Exception as e:
        print(f"[Email] Error sending email: {e}")
        return False


# ─── Chatbot Endpoint ─────────────────────────────────────────────────────────

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    """
    Stock-focused AI chatbot powered by Google Gemini.
    Special commands: "send nifty report" to generate and email a report.

    Request body: { "message": "..." }
    """
    try:
        if not client:
            return jsonify({'error': 'Gemini API not configured.'}), 500
        data         = request.get_json()
        user_message = (data.get('message', '') or '').strip()
        print(user_message)
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        # Check for special commands
        if user_message.lower() in ['send nifty report', 'analyze nifty', 'nifty report']:
            report = generate_nifty_report()
            if send_email_report("NIFTY Trading Report", report):
                response_text = "NIFTY analysis report has been generated and sent to your email."
            else:
                response_text = "Report generated, but failed to send email. Report: " + report
            return jsonify({'response': response_text, 'success': True})

        system_ctx = (
            'You are a helpful stock market assistant. Answer questions about stocks, '
            'trading strategies, technical indicators, and financial concepts. '
            'Keep responses concise. For real-time prices, direct users to the chart. '
            'If asked for NIFTY analysis or report, suggest using "send nifty report" command.'
        )
        prompt   = f"{system_ctx}\n\nUser: {user_message}"
        response = client.models.generate_content(model='gemini-2.5-flash-lite', contents=prompt)
        
        # Log the raw Gemini output
        logger.info(f'[Chatbot] User message: {user_message}')
        logger.info(f'[Chatbot] Gemini raw response:\n{response.text}')
        
        return jsonify({'response': response.text, 'success': True})

    except Exception as e:
        logger.error(f'[API] /api/chatbot error: {e}')
        return jsonify({'error': str(e)}), 500


# ─── WebSocket Event Handlers ─────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    logger.info('[WS] Client connected')


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
        logger.error(f'[WS] Immediate news error: {e}')

    # Start background broadcaster if not running
    global news_thread
    with news_thread_lock:
        if news_thread is None or not news_thread.is_alive():
            news_thread = threading.Thread(target=_broadcast_news_loop, daemon=True)
            news_thread.start()
            print('[WS] News broadcaster started')


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    logger.info('=' * 60)
    logger.info('  Stock Market Simulator — Flask + SocketIO')
    logger.info(f'  http://127.0.0.1:{SERVER_PORT}/')
    logger.info('=' * 60)
    socketio.run(
        app,
        debug=DEBUG,
        host=SERVER_HOST,
        port=SERVER_PORT,
        allow_unsafe_werkzeug=True
    )