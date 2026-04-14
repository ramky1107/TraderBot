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

# Initialize components
data_fetcher = DataFetcher()
sentiment_engine = SentimentEngine()
valuation_engine = ValuationEngine()

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

if __name__ == "__main__":
    # If run directly, start the Flask server
    port = int(os.getenv('SERVER_PORT', 8050))
    logger.info(f"Starting TraderBot Server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
