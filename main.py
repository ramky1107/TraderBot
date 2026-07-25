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
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from dotenv import load_dotenv

# Import our new rewritten modules
from data_fetcher import DataFetcher
from sentiment_engine import SentimentEngine
from valuation_engine import ValuationEngine

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

<<<<<<< HEAD
# ── Our modules ───────────────────────────────────────────────────────────────
import data_manager
import strategies
import sentiment_analyzer
from news       import get_pulse_news, get_groww_company_outlook
from live_price import fetch_intraday_df
from constants  import (
    SERVER_HOST, SERVER_PORT, DEBUG,
    CACHE_TTL_STOCK, CACHE_TTL_SENTIMENT, CACHE_TTL_RATIOS, CACHE_TTL_NEWS,
    DEFAULT_TICKER, DEFAULT_PERIOD, DEFAULT_INTERVAL,
    CHART_BG_COLOR,
)
=======
# Initialize components
data_fetcher = DataFetcher()
sentiment_engine = SentimentEngine()
valuation_engine = ValuationEngine()
>>>>>>> refs/remotes/origin/main

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='static')
CORS(app)

# ─── Core Logic ─────────────────────────────────────────────────────────────

def analyze_ticker(ticker: str) -> Dict:
    """Orchestrates the analysis of a given stock ticker."""
    logger.info(f"Analyzing ticker: {ticker}")
    
    # 1. Fetch Data
    # Get stock history (excluding holidays/weekends)
    df = data_fetcher.fetch_stock_data(ticker)
    # Get stock fundamental info
    info = data_fetcher.get_stock_info(ticker)
    # Get current price
    current_price = info.get('currentPrice') or (df['Close'].iloc[-1] if not df.empty else 0.0)
    
    # 2. Sentiment Analysis (X/Twitter + Ollama)
    tweets = data_fetcher.fetch_tweets(ticker, count=10)
    analyzed_tweets = sentiment_engine.batch_analyze(tweets)
    sentiment_score = sentiment_engine.get_aggregate_score(analyzed_tweets)
    
    # 3. Valuation Analysis (Intrinsic Price)
    intrinsic_price, diff_percent = valuation_engine.calculate_intrinsic_value(info, current_price)
    
    # 4. Prepare Response
    result = {
        'ticker': ticker,
        'current_price': round(current_price, 2),
        'intrinsic_price': intrinsic_price,
        'diff_percent': diff_percent,
        'sentiment_score': sentiment_score,
        'analyzed_tweets': analyzed_tweets[:5], # Send a few for display
        'status': 'success'
    }
    
    return result

# ─── Web API Endpoints ──────────────────────────────────────────────────────

@app.route('/')
def index():
    """Serves the main dashboard."""
    return render_template('index.html')

@app.route('/api/analyze/<ticker>')
def api_analyze(ticker: str):
    """Endpoint for ticker analysis."""
    try:
        result = analyze_ticker(ticker.upper())
        return jsonify(result)
    except Exception as e:
        logger.error(f"API Error for {ticker}: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/api/history/<ticker>')
def api_history(ticker: str):
    """Endpoint for historical price data (cleaned for display)."""
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

# ─── Execution ─────────────────────────────────────────────────────────────

<<<<<<< HEAD
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

@app.route('/api/groww-news-outlook', methods=['GET'])
def get_groww_news_outlook():
    """Return a day-trading outlook generated from the latest Groww news feed."""
    try:
        company = request.args.get('company', '').strip()
        company_url = request.args.get('company_url', '').strip()
        page_excerpt = request.args.get('page_excerpt', '').strip()
        result = get_groww_company_outlook(company=company, company_url=company_url, page_excerpt=page_excerpt)
        return jsonify(result)
    except Exception as e:
        logger.error(f'[API] /api/groww-news-outlook error: {e}')
        return jsonify({'status': 'error', 'error': str(e)}), 500


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
=======
if __name__ == "__main__":
    # If run directly, start the Flask server
    port = int(os.getenv('SERVER_PORT', 8050))
    logger.info(f"Starting TraderBot Server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
>>>>>>> refs/remotes/origin/main
