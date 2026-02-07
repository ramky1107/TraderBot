import yfinance as yf
import pandas as pd

def fetch_market_data(ticker="^NSEI", interval="1m", period="5d"):
    """
    Fetches historical data for the given ticker.
    
    Args:
        ticker (str): Symbol (e.g., '^NSEI' for Nifty 50).
        interval (str): Data granularity (e.g., '1m', '5m').
        period (str): Duration of data (e.g., '1d', '5d', '1mo').
                      Note: 1m data is limited to 7d max on free tier.
    """
    try:
        # Fetch data
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        
        if df.empty:
            return pd.DataFrame()

        # Flatten MultiIndex columns if present (common in new yfinance versions)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Ensure index is timezone-aware or localized to avoid plot issues
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
            
        return df
    except Exception as e:
        print(f"Error in data fetch: {e}")
        return pd.DataFrame()