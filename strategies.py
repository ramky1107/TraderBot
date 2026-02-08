import pandas as pd

def calculate_rsi(series, period=14):
    """
    Calculate RSI (Relative Strength Index) for a given series.
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def apply_strategies(df):
    """
    Applies technical indicators to the DataFrame.
    """
    if df.empty:
        return df
    
    # Strategy 1: 20-Period Simple Moving Average (SMA)
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    
    # Strategy 2: RSI (Relative Strength Index)
    df['RSI'] = calculate_rsi(df['Close'], period=14)
    
    return df