import yfinance as yf
import pandas as pd

def fetch_market_data(ticker="^NSEI", interval="1d", period="60d"):
    """
    Fetches historical data and converts it to IST timezone.
    """
    try:
        # Fetch data
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        
        if df.empty:
            return pd.DataFrame()

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 1. Handle Timezones (Crucial for removing gaps)
        # Yahoo Finance returns UTC. We check if timezone is set, then convert to IST.
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        
        # Convert to Indian Standard Time (Asia/Kolkata)
        df.index = df.index.tz_convert('Asia/Kolkata')
            
        return df
    except Exception as e:
        print(f"Error in data fetch: {e}")
        return pd.DataFrame()