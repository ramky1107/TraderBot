from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import data_manager
import strategies
import sentiment_analyzer
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests as http_requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os

app = Flask(__name__, static_folder='static')
CORS(app)

# Initialize Gemini API (Free tier - no billing)
# Get API key from environment variable or use a default (you should set GEMINI_API_KEY)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro')
else:
    gemini_model = None
    print("WARNING: GEMINI_API_KEY not set. Chatbot will not work.")

# Cache for historical data
data_cache = {}
# Cache for sentiment scores (avoid re-computing too often)
sentiment_cache = {}

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('static', 'index.html')

@app.route('/style.css')
def serve_css():
    """Serve CSS file"""
    return send_from_directory('static', 'style.css')

@app.route('/app.js')
def serve_js():
    """Serve JavaScript file"""
    return send_from_directory('static', 'app.js')

@app.route('/api/stock-data')
def get_stock_data():
    """API endpoint to fetch stock data with caching"""
    try:
        ticker = request.args.get('ticker', '^NSEI')
        
        # Check if we have cached historical data for this ticker
        if ticker in data_cache:
            cached_data = data_cache[ticker]
            last_update = cached_data['last_update']
            
            # If cache is less than 1 hour old, fetch only latest data
            if datetime.now() - last_update < timedelta(hours=1):
                # Fetch recent data with same interval (1d) to avoid mixing intervals
                live_df = data_manager.fetch_market_data(ticker=ticker, period="5d", interval="1d")
                
                if not live_df.empty:
                    # Merge with historical data
                    historical_df = cached_data['data']
                    
                    # Combine: keep historical + add new live data
                    combined_df = pd.concat([historical_df, live_df])
                    combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
                    combined_df = combined_df.sort_index()
                    
                    # Keep only last 60 days (make cutoff_date timezone-aware)
                    cutoff_date = pd.Timestamp.now(tz='Asia/Kolkata') - timedelta(days=60)
                    combined_df = combined_df[combined_df.index >= cutoff_date]
                    
                    # Update cache
                    data_cache[ticker] = {
                        'data': combined_df,
                        'last_update': datetime.now()
                    }
                    
                    df = combined_df
                else:
                    # Use cached data if live fetch fails
                    df = cached_data['data']
            else:
                # Cache is old, fetch full historical data
                df = data_manager.fetch_market_data(ticker=ticker, period="60d", interval="1d")
                data_cache[ticker] = {
                    'data': df,
                    'last_update': datetime.now()
                }
        else:
            # No cache, fetch full historical data
            df = data_manager.fetch_market_data(ticker=ticker, period="60d", interval="1d")
            data_cache[ticker] = {
                'data': df,
                'last_update': datetime.now()
            }
        
        if df.empty:
            return jsonify({'error': 'No data available for this ticker'}), 404
        
        # Apply strategies
        df = strategies.apply_strategies(df)
        
        # Prepare response data (convert NaN to None for valid JSON)
        response_data = {
            'ticker': ticker,
            'dates': df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'open': df['Open'].tolist(),
            'high': df['High'].tolist(),
            'low': df['Low'].tolist(),
            'close': df['Close'].tolist(),
            'volume': df['Volume'].tolist(),
            'sma_20': [None if pd.isna(x) else x for x in df['SMA_20']] if 'SMA_20' in df.columns else [],
            'rsi': [None if pd.isna(x) else x for x in df['RSI']] if 'RSI' in df.columns else []
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in API: {str(e)}")  # Debug logging
        return jsonify({'error': str(e)}), 500

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    """API endpoint for stock-related chatbot queries using free Gemini API"""
    try:
        if not gemini_model:
            return jsonify({'error': 'Gemini API not configured. Please set GEMINI_API_KEY environment variable.'}), 500
        
        data = request.get_json()
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Add context to make responses stock-focused
        context = """You are a helpful stock market assistant. Answer questions about stocks, 
        trading strategies, technical indicators, market analysis, and financial concepts. 
        Keep responses concise and informative. If asked about specific stock prices or real-time data, 
        remind users to check the chart or use the ticker search feature."""
        
        full_prompt = f"{context}\n\nUser question: {user_message}"
        
        # Generate response using Gemini (free tier)
        response = gemini_model.generate_content(full_prompt)
        
        return jsonify({
            'response': response.text,
            'success': True
        })
        
    except Exception as e:
        print(f"Chatbot error: {str(e)}")
        return jsonify({'error': f'Failed to get response: {str(e)}'}), 500

@app.route('/api/sentiment-score')
def get_sentiment_score():
    """API endpoint to get sentiment score for a ticker"""
    try:
        ticker = request.args.get('ticker', '^NSEI')
        
        # Check cache (5-minute TTL)
        if ticker in sentiment_cache:
            cached = sentiment_cache[ticker]
            if datetime.now() - cached['last_update'] < timedelta(minutes=5):
                return jsonify(cached['data'])
        
        # Calculate sentiment score
        result = sentiment_analyzer.get_sentiment_score(ticker)
        
        # Cache the result
        sentiment_cache[ticker] = {
            'data': result,
            'last_update': datetime.now()
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Sentiment score error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/live-price')
def get_live_price():
    """API endpoint to get live price data (1-minute intervals)"""
    try:
        ticker = request.args.get('ticker', '^NSEI')
        
        import yfinance as yf
        live_df = yf.download(ticker, period="1d", interval="1m", progress=False)
        
        if live_df.empty:
            return jsonify({'error': 'No live data available'}), 404
        
        # Flatten MultiIndex if present
        if isinstance(live_df.columns, pd.MultiIndex):
            live_df.columns = live_df.columns.get_level_values(0)
        
        current_price = float(live_df['Close'].iloc[-1])
        open_price = float(live_df['Open'].iloc[0])
        high_price = float(live_df['High'].max())
        low_price = float(live_df['Low'].min())
        change = current_price - open_price
        change_pct = (change / open_price) * 100
        
        return jsonify({
            'ticker': ticker,
            'current_price': round(current_price, 2),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'change': round(change, 2),
            'change_pct': round(change_pct, 2),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Live price error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Cache for financial ratios
ratios_cache = {}

@app.route('/api/financial-ratios')
def get_financial_ratios():
    """API endpoint to get financial ratios for a ticker via yfinance"""
    try:
        ticker = request.args.get('ticker', '^NSEI')
        
        # Check cache (10-minute TTL)
        if ticker in ratios_cache:
            cached = ratios_cache[ticker]
            if datetime.now() - cached['last_update'] < timedelta(minutes=10):
                return jsonify(cached['data'])
        
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info
        
        def fmt_large(val):
            """Format large numbers with T/B/Cr suffix"""
            if val is None:
                return 'N/A'
            if val >= 1e12:
                return f'₹{val/1e12:.1f}T'
            elif val >= 1e9:
                return f'₹{val/1e9:.1f}B'
            elif val >= 1e7:
                return f'₹{val/1e7:.1f}Cr'
            else:
                return f'₹{val:,.0f}'
        
        def fmt_pct(val):
            if val is None:
                return 'N/A'
            return f'{val*100:.2f}%'
        
        def fmt_ratio(val):
            if val is None:
                return 'N/A'
            return f'{val:.2f}'
        
        ratios = {
            'pe_ratio': fmt_ratio(info.get('trailingPE')),
            'pb_ratio': fmt_ratio(info.get('priceToBook')),
            'debt_equity': fmt_ratio(info.get('debtToEquity')),
            'market_cap': fmt_large(info.get('marketCap')),
            'dividend_yield': fmt_pct(info.get('dividendYield')),
            'roe': fmt_pct(info.get('returnOnEquity')),
            'eps': fmt_ratio(info.get('trailingEps')),
            'book_value': fmt_ratio(info.get('bookValue')),
        }
        
        result = {'ticker': ticker, 'ratios': ratios}
        
        # Cache
        ratios_cache[ticker] = {
            'data': result,
            'last_update': datetime.now()
        }
        
        return jsonify(result)
    
    except Exception as e:
        print(f"Financial ratios error: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Cache for pulse news
pulse_news_cache = {'data': None, 'last_update': None}

@app.route('/api/pulse-news')
def get_pulse_news():
    """API endpoint to scrape latest business news from Zerodha Pulse"""
    try:
        # Check cache (5-minute TTL)
        if pulse_news_cache['data'] and pulse_news_cache['last_update']:
            if datetime.now() - pulse_news_cache['last_update'] < timedelta(minutes=5):
                return jsonify(pulse_news_cache['data'])
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        resp = http_requests.get('https://pulse.zerodha.com/', headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        headlines = []
        # Pulse uses <li> elements with class 'box item' or similar structures
        items = soup.select('.feed-item, li.box, .item, article')
        
        if not items:
            # Fallback: try to find all links that look like news articles
            items = soup.find_all('a', href=True)
            for a_tag in items:
                title = a_tag.get_text(strip=True)
                href = a_tag.get('href', '')
                if title and len(title) > 30 and ('http' in href or href.startswith('/')):
                    # Try to extract publisher from the URL
                    publisher = ''
                    if 'economictimes' in href:
                        publisher = 'Economic Times'
                    elif 'business-standard' in href:
                        publisher = 'Business Standard'
                    elif 'ndtvprofit' in href or 'ndtv' in href:
                        publisher = 'NDTV Profit'
                    elif 'thehindu' in href:
                        publisher = 'The Hindu'
                    elif 'livemint' in href:
                        publisher = 'LiveMint'
                    elif 'moneycontrol' in href:
                        publisher = 'MoneyControl'
                    elif 'zeebiz' in href:
                        publisher = 'Zee Business'
                    elif 'finshots' in href:
                        publisher = 'Finshots'
                    
                    headlines.append({
                        'title': title[:150],
                        'url': href,
                        'publisher': publisher
                    })
                    if len(headlines) >= 15:
                        break
        else:
            for item in items[:15]:
                title_el = item.find('a') or item
                title = title_el.get_text(strip=True)
                href = title_el.get('href', '') if title_el.name == 'a' else ''
                publisher_el = item.find(class_='publisher') or item.find(class_='source')
                publisher = publisher_el.get_text(strip=True) if publisher_el else ''
                
                if title and len(title) > 10:
                    headlines.append({
                        'title': title[:150],
                        'url': href,
                        'publisher': publisher
                    })
        
        result = {'headlines': headlines, 'source': 'Zerodha Pulse'}
        
        # Cache
        pulse_news_cache['data'] = result
        pulse_news_cache['last_update'] = datetime.now()
        
        return jsonify(result)
    
    except Exception as e:
        print(f"Pulse news error: {str(e)}")
        return jsonify({'error': str(e), 'headlines': []}), 500


if __name__ == '__main__':
    print("Starting Flask Server...")
    print("Open your browser and go to http://127.0.0.1:8050/")
    app.run(debug=True, host='0.0.0.0', port=8050)