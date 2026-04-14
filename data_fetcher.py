"""
=============================================================================
data_fetcher.py
=============================================================================
Fetches data from multiple sources:
1. X (Twitter) using Tweepy (with credentials from .env)
2. Yahoo Finance (yfinance) for stock data
3. Filters holidays and weekends for consistent stock price display.
=============================================================================
"""

import os
import logging
from typing import List, Dict, Optional
import tweepy
import yfinance as yf
import pandas as pd
import pandas_market_calendars as mcal
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Credentials
X_BEARER_TOKEN = os.getenv('X_BEARER_TOKEN')
X_API_KEY = os.getenv('X_API_KEY')
X_API_SECRET = os.getenv('X_API_SECRET')
X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
X_ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')

DEFAULT_EXCHANGE = os.getenv('DEFAULT_EXCHANGE', 'NYSE')

class DataFetcher:
    """Handles all external data fetching requirements."""

    def __init__(self):
        self._setup_twitter()

    def _setup_twitter(self):
        """Initializes Tweepy client if credentials exist."""
        try:
            if X_BEARER_TOKEN:
                self.twitter_client = tweepy.Client(bearer_token=X_BEARER_TOKEN)
                logger.info("[Twitter] API client initialized.")
            else:
                self.twitter_client = None
                logger.warning("[Twitter] No Bearer Token found in .env. Skipping initialization.")
        except Exception as e:
            logger.error(f"[Twitter] Connection error: {e}")
            self.twitter_client = None

    def fetch_tweets(self, ticker: str, count: int = 10) -> List[str]:
        """Fetches recent tweets for a given ticker.
        
        Args:
            ticker: The stock ticker (e.g., 'AAPL' or '$AAPL').
            count: Number of tweets to fetch.
            
        Returns:
            List of tweet texts.
        """
        if not self.twitter_client:
            return ["No Twitter credentials found. Returning placeholder tweet."]

        try:
            query = f"${ticker} lang:en -is:retweet"
            response = self.twitter_client.search_recent_tweets(
                query=query, 
                max_results=count,
                tweet_fields=['text']
            )
            
            if response.data:
                return [tweet.text for tweet in response.data]
            return []
        except Exception as e:
            logger.error(f"[Twitter] Fetching error: {e}")
            return []

    def fetch_stock_data(self, ticker: str, period: str = '1y', interval: str = '1d') -> pd.DataFrame:
        """Fetches historical stock data and cleans it for trading days.
        
        Args:
            ticker: Stock symbol.
            period: Timeframe (e.g., '1y', 'max').
            interval: Frequency (e.g., '1d').
            
        Returns:
            DataFrame with OHLCV data.
        """
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False)
            if df.empty:
                return pd.DataFrame()

            # Flatten MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Ensure index is datetime
            df.index = pd.to_datetime(df.index)
            
            # Clean data: yfinance already excludes non-trading days by default for historical.
            # However, for 'display' we might want to ensure it explicitly.
            df = self._filter_trading_days(df)
            return df
        except Exception as e:
            logger.error(f"[Finance] Error fetching data for {ticker}: {e}")
            return pd.DataFrame()

    def _filter_trading_days(self, df: pd.DataFrame) -> pd.DataFrame:
        """Removes rows that are not on actual trading days (using market calendars)."""
        if df.empty: return df
        
        # Determine the calendar based on exchange (simplified for this package)
        try:
            cal = mcal.get_calendar(DEFAULT_EXCHANGE)
            start_date = df.index.min()
            end_date = df.index.max()
            schedule = cal.schedule(start_date=start_date, end_date=end_date)
            
            # Keep only indices that are in the schedule
            # Note: We use .date() comparison to avoid timezone issues.
            valid_dates = pd.to_datetime(schedule.index).date
            df = df[df.index.to_series().dt.date.isin(valid_dates)]
        except Exception as e:
            logger.warning(f"[Calendar] Could not filter using {DEFAULT_EXCHANGE} calendar: {e}")
            # Fallback: Just remove weekends
            df = df[df.index.dayofweek < 5]
            
        return df

    def get_stock_info(self, ticker: str) -> Dict:
        """Fetches fundamental data for intrinsic value calculation."""
        try:
            stock = yf.Ticker(ticker)
            return stock.info
        except Exception as e:
            logger.error(f"[Finance] Error fetching info for {ticker}: {e}")
            return {}
