from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import data_manager
import strategies
import json
from datetime import datetime, timedelta
import pandas as pd

app = Flask(__name__, static_folder='static')
CORS(app)

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
                # Fetch only today's data (1d period, 1m interval for live updates)
                live_df = data_manager.fetch_market_data(ticker=ticker, period="1d", interval="1m")
                
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
        
        # Prepare response data
        response_data = {
            'ticker': ticker,
            'dates': df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'open': df['Open'].tolist(),
            'high': df['High'].tolist(),
            'low': df['Low'].tolist(),
            'close': df['Close'].tolist(),
            'volume': df['Volume'].tolist(),
            'sma_20': df['SMA_20'].fillna(0).tolist() if 'SMA_20' in df.columns else [],
            'rsi': df['RSI'].fillna(0).tolist() if 'RSI' in df.columns else []
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in API: {str(e)}")  # Debug logging
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting Flask Server...")
    print("Open your browser and go to http://127.0.0.1:8050/")
    app.run(debug=True, host='0.0.0.0', port=8050)