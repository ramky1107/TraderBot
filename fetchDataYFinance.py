import pandas as pd
from datetime import datetime
import constants
import time
from typing import Literal
import yfinance as yf

def fetch_stooq(
    symbol: str,
    interval: Literal["d", "w", "m"] = "d"
) -> pd.DataFrame:
    """
    Fetch OHLCV data via yfinance and return a clean pandas DataFrame.

    Parameters:
        symbol   : e.g. 'AAPL', 'MSFT', '^GSPC'
        interval : 'd' (daily), 'w' (weekly), 'm' (monthly)

    Returns:
        DataFrame indexed by Date with columns:
        Open, High, Low, Close, Volume
    """
    interval_map = {
        "d": "1d",
        "w": "1wk",
        "m": "1mo",
    }
    yf_interval = interval_map.get(interval)
    if yf_interval is None:
        raise ValueError(f"Unsupported interval: {interval}")

    df = yf.download(symbol, interval=yf_interval, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for symbol: {symbol}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if "Adj Close" in df.columns:
        df = df.drop(columns=["Adj Close"])

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])

    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    df.sort_index(inplace=True)

    return df

def getLiveStatus(companySymbol):
    return fetch_stooq(symbol= companySymbol, interval='d')