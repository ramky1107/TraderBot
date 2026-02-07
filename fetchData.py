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
    Fetch OHLCV data from Stooq and return a clean pandas DataFrame.

    Parameters:
        symbol   : e.g. 'aapl.us', 'msft.us', 'spx'
        interval : 'd' (daily), 'w' (weekly), 'm' (monthly)

    Returns:
        DataFrame indexed by Date with columns:
        Open, High, Low, Close, Volume
    """
    url = f"https://stooq.pl/q/d/l/?s={symbol}&i={interval}"
    params = {
        "s": symbol.lower(),
        "i": interval
    }

    df = pd.read_csv(url)
    df.rename(
        columns={
            "Data": "Date",
            "Otwarcie": "Open",
            "Najwyzszy": "High",
            "Najnizszy": "Low",
            "Zamkniecie": "Close",
            "Wolumen": "Volume",
        },
        inplace=True,
    )

    if df.empty:
        raise ValueError(f"No data returned for symbol: {symbol}")

    # Normalize
    print (df.tail())
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    df.sort_index(inplace=True)

    return df

def getLiveStatus(companySymbol):
    return fetch_stooq(symbol= companySymbol, interval='d')

def getYFinanceLiveStatus():
    # Create a Ticker object for AAPL
    aapl = yf.Ticker("AAPL")

    # Fetch historical data (e.g., last 1 year)
    # Periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max [7]
    aapl_hist = aapl.history(period="1y")

    # Display the first few rows
    print(aapl_hist.head())
