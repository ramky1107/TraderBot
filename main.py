"""
=============================================================================
main.py
=============================================================================
The central entry point for the TraderBot.
Connects the DataFetcher, SentimentEngine, and ValuationEngine.
Provides both CLI and Web API interfaces.
=============================================================================
"""

import os
import logging
from typing import Dict
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our new rewritten modules (gracefully degrade if optional packages are absent)
try:
    from data_fetcher import DataFetcher
except Exception as exc:
    logger.warning(f"DataFetcher import unavailable: {exc}")
    DataFetcher = None

try:
    from sentiment_engine import SentimentEngine
except Exception as exc:
    logger.warning(f"SentimentEngine import unavailable: {exc}")
    SentimentEngine = None

try:
    from valuation_engine import ValuationEngine
except Exception as exc:
    logger.warning(f"ValuationEngine import unavailable: {exc}")
    ValuationEngine = None

# ── Our modules ───────────────────────────────────────────────────────────────
try:
    import data_manager
except Exception as exc:
    logger.warning(f"data_manager import unavailable: {exc}")
    data_manager = None

try:
    import strategies
except Exception as exc:
    logger.warning(f"strategies import unavailable: {exc}")
    strategies = None

try:
    import sentiment_analyzer
except Exception as exc:
    logger.warning(f"sentiment_analyzer import unavailable: {exc}")
    sentiment_analyzer = None

try:
    from news import get_pulse_news, get_groww_company_outlook
except Exception as exc:
    logger.warning(f"news import unavailable: {exc}")
    get_pulse_news = None
    get_groww_company_outlook = None

try:
    from live_price import fetch_intraday_df
except Exception as exc:
    logger.warning(f"live_price import unavailable: {exc}")
    fetch_intraday_df = None

from constants import (
    SERVER_HOST, SERVER_PORT, DEBUG,
    CACHE_TTL_STOCK, CACHE_TTL_SENTIMENT, CACHE_TTL_RATIOS, CACHE_TTL_NEWS,
    DEFAULT_TICKER, DEFAULT_PERIOD, DEFAULT_INTERVAL,
    CHART_BG_COLOR,
)

# Initialize components
data_fetcher = DataFetcher() if DataFetcher is not None else None
sentiment_engine = SentimentEngine() if SentimentEngine is not None else None
valuation_engine = ValuationEngine() if ValuationEngine is not None else None


# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='static')
CORS(app)

# Try to init SocketIO if ENABLE_SOCKETIO env var is set and package is available
ENABLE_SOCKETIO = os.getenv('ENABLE_SOCKETIO', 'False').lower() == 'true'
socketio = None
if ENABLE_SOCKETIO:
    try:
        from flask_socketio import SocketIO, emit
        socketio = SocketIO(app, cors_allowed_origins='*')
        logger.info('Flask-SocketIO initialized (enabled by ENABLE_SOCKETIO).')
    except Exception:
        socketio = None
        logger.warning('flask_socketio present but failed to initialize; socket.io endpoints will be degraded.')
else:
    logger.info('Socket.IO support disabled (set ENABLE_SOCKETIO=True to enable).')

# ─── Core Logic ─────────────────────────────────────────────────────────────

def analyze_ticker(ticker: str) -> Dict:
    """Run the full stock-analysis pipeline for a ticker and return a summary payload."""
    logger.info(f"Analyzing ticker: {ticker}")

    if data_fetcher is None or sentiment_engine is None or valuation_engine is None:
        return {
            'ticker': ticker,
            'current_price': None,
            'intrinsic_price': None,
            'diff_percent': None,
            'sentiment_score': 0.0,
            'analyzed_tweets': [],
            'status': 'degraded',
            'message': 'Optional analysis dependencies are unavailable; the Groww endpoint remains available.'
        }

    # 1. Fetch Data
    df = data_fetcher.fetch_stock_data(ticker)
    info = data_fetcher.get_stock_info(ticker)
    current_price = info.get('currentPrice') or (df['Close'].iloc[-1] if not df.empty else 0.0)

    # 2. Sentiment Analysis (X/Twitter + Ollama)
    tweets = data_fetcher.fetch_tweets(ticker, count=10)
    analyzed_tweets = sentiment_engine.batch_analyze(tweets)
    sentiment_score = sentiment_engine.get_aggregate_score(analyzed_tweets)

    # 3. Valuation Analysis (Intrinsic Price)
    intrinsic_price, diff_percent = valuation_engine.calculate_intrinsic_value(info, current_price)

    return {
        'ticker': ticker,
        'current_price': round(current_price, 2),
        'intrinsic_price': intrinsic_price,
        'diff_percent': diff_percent,
        'sentiment_score': sentiment_score,
        'analyzed_tweets': analyzed_tweets[:5],
        'status': 'success'
    }

# ─── Web API Endpoints ──────────────────────────────────────────────────────

@app.route('/')
def index():
    """Serve the main dashboard page for the web UI."""
    return render_template('index.html')

@app.route('/api/analyze/<ticker>')
def api_analyze(ticker: str):
    """Expose the stock-analysis workflow through a JSON API endpoint."""
    try:
        result = analyze_ticker(ticker.upper())
        return jsonify(result)
    except Exception as e:
        logger.error(f"API Error for {ticker}: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/api/history/<ticker>')
def api_history(ticker: str):
    """Return cleaned historical price data formatted for charting."""
    try:
        df = data_fetcher.fetch_stock_data(ticker.upper())
        if df.empty:
            return jsonify({'error': 'No data found'}), 404
        
        # Prepare data for Chart.js or similar
        history = {
            'dates': df.index.strftime('%Y-%m-%d').tolist(),
            'prices': df['Close'].tolist()
        }
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/groww-news-outlook')
def api_groww_news_outlook():
    """Return a short trading outlook created from Groww news content."""
    try:
        company = request.args.get('company', '').strip()
        company_url = request.args.get('company_url', '').strip()
        page_excerpt = request.args.get('page_excerpt', '').strip()
        outlook = get_groww_company_outlook(company=company, company_url=company_url, page_excerpt=page_excerpt)
        return jsonify(outlook)
    except Exception as e:
        logger.error(f"Groww outlook API error: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/partials/<path:filename>')
def serve_partial(filename: str):
    """Serve HTML partial fragments from the frontend template directory."""
    try:
        return send_from_directory('static/partials', filename)
    except Exception as e:
        logger.warning(f"Partial not found: {filename} - {e}")
        return ("", 404)


@app.route('/favicon.ico')
def favicon():
    """Return the site favicon when available and avoid noisy missing-file errors."""
    try:
        return send_from_directory('static', 'favicon.ico')
    except Exception:
        return ('', 204)


@app.route('/api/stock-data')
def api_stock_data():
    """Return OHLCV data plus optional strategy overlays for the frontend chart view.

    Query params: ticker, period, interval
    """
    ticker = request.args.get('ticker', '').upper()
    period = request.args.get('period', '1mo')
    interval = request.args.get('interval', '1d')

    if not ticker:
        return jsonify({'error': 'ticker required'}), 400

    if data_fetcher is None:
        return jsonify({'error': 'DataFetcher unavailable on this instance'}), 503

    try:
        df = data_fetcher.fetch_stock_data(ticker, period=period, interval=interval)
        if df.empty:
            return jsonify({'error': f'No data for {ticker}'}), 404

        # Apply strategies if available
        if strategies is not None:
            try:
                df = strategies.apply_strategies(df)
            except Exception:
                pass

        # Simple serialisation
        return jsonify({
            'ticker': ticker,
            'dates': [d.strftime('%Y-%m-%d %H:%M:%S') for d in df.index],
            'open': df['Open'].tolist(),
            'high': df['High'].tolist(),
            'low': df['Low'].tolist(),
            'close': df['Close'].tolist(),
            'volume': df['Volume'].tolist(),
        })
    except Exception as e:
        logger.error(f"/api/stock-data error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/live-price')
def api_live_price():
    """Return a lightweight live-price summary for the current ticker selection."""
    ticker = request.args.get('ticker', '').upper()
    if not ticker:
        return jsonify({'error': 'ticker required'}), 400

    if data_fetcher is None:
        return jsonify({'error': 'DataFetcher unavailable on this instance'}), 503

    try:
        # Fetch recent intraday / daily data to approximate live price
        df = data_fetcher.fetch_stock_data(ticker, period='5d', interval='1d')
        if df.empty:
            return jsonify({'error': 'No live data'}), 404

        current_price = float(df['Close'].iloc[-1])
        open_price = float(df['Open'].iloc[0]) if len(df) > 0 else current_price
        change = current_price - open_price
        change_pct = (change / open_price) * 100 if open_price != 0 else 0

        return jsonify({
            'ticker': ticker,
            'current_price': round(current_price, 2),
            'open': round(open_price, 2),
            'high': round(float(df['High'].max()), 2),
            'low': round(float(df['Low'].min()), 2),
            'change': round(change, 2),
            'change_pct': round(change_pct, 2),
            'timestamp': '',
        })
    except Exception as e:
        logger.error(f"/api/live-price error: {e}")
        return jsonify({'error': str(e)}), 500


# ─── Financial Ratios Endpoint ──────────────────────────────────────────────
@app.route('/api/financial-ratios')
def api_financial_ratios():
    """Return commonly used valuation ratios for a requested ticker."""
    ticker = request.args.get('ticker', '').upper()
    if not ticker:
        return jsonify({'error': 'ticker required'}), 400

    try:
        import yfinance as yf
        if data_fetcher is not None:
            info = data_fetcher.get_stock_info(ticker)
        else:
            info = yf.Ticker(ticker).info

        ratios = {
            'pe_ratio': info.get('trailingPE'),
            'pb_ratio': info.get('priceToBook'),
            'debt_equity': info.get('debtToEquity'),
            'market_cap': info.get('marketCap'),
            'dividend_yield': info.get('dividendYield'),
            'roe': info.get('returnOnEquity'),
            'eps': info.get('trailingEps'),
            'book_value': info.get('bookValue'),
        }
        return jsonify({'ticker': ticker, 'ratios': ratios})
    except Exception as e:
        logger.error(f"/api/financial-ratios error: {e}")
        return jsonify({'error': str(e)}), 500


# ─── Sentiment Score Endpoint (basic) ───────────────────────────────────────
@app.route('/api/sentiment-score')
def api_sentiment_score():
    """Return a news-driven sentiment score for the requested ticker."""
    ticker = request.args.get('ticker', '').upper()
    if not ticker:
        return jsonify({'error': 'ticker required'}), 400

    try:
        # Use news.fetch_news_sentiment if available
        from news import fetch_news_sentiment
        score, headlines, status, count = fetch_news_sentiment(ticker)
        return jsonify({
            'ticker': ticker,
            'news_score': score,
            'headlines': headlines,
            'status': status,
            'article_count': count,
        })
    except Exception as e:
        logger.error(f"/api/sentiment-score error: {e}")
        return jsonify({'error': str(e)}), 500


# ─── Socket.IO fallback when flask-socketio not installed ───────────────────
if socketio is None:
    @app.route('/socket.io/')
    def socketio_fallback():
        """Respond to Socket.IO polling probes so missing Socket.IO support does not raise noise."""
        return ('', 200)

# ─── Execution ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # If run directly, start the Flask server
    port = int(os.getenv('SERVER_PORT', 8050))
    logger.info(f"Starting TraderBot Server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
