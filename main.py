from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import data_manager
import strategies
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
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

if __name__ == '__main__':
    print("Starting Flask Server...")
    print("Open your browser and go to http://127.0.0.1:8050/")
    app.run(debug=True, host='0.0.0.0', port=8050)