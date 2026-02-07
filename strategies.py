import pandas as pd

def apply_strategies(df):
    """
    Applies technical indicators to the DataFrame.
    """
    if df.empty:
        return df
    
    # Strategy 1: 20-Period Simple Moving Average (SMA)
    # Note: On a 1m chart, this is the average of the last 20 minutes.
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    
    # Future Strategy: Add RSI, MACD, etc. here
    # df['RSI'] = ...
    
    return df