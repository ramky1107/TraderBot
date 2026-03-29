"""
=============================================================================
ai_model.py
=============================================================================
Random Forest model manager for per-ticker sentiment prediction.

The model is trained on 1 year of daily OHLCV data and predicts the
next-day percentage return. That prediction is then mapped to a score
in [-100, +100].

Models are persisted to disk (./models/<TICKER>_rf.pkl) so they don't
need to be retrained on every request.

Provides:
  - DynamicSentimentModel class
  - module-level singleton: `model_manager`

Used by:
  - sentiment_analyzer.py
=============================================================================
"""

import os
import pickle
import traceback

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.ensemble import RandomForestRegressor

import indicators as ind

# ─── Configuration ────────────────────────────────────────────────────────────

# Directory where trained models are saved
MODEL_DIR = 'models'

# Minimum rows of historical data required to train a model
MIN_TRAINING_ROWS = 50

# Feature columns the model expects — must match training order exactly
FEATURE_COLUMNS = ['RSI', 'SMA_20', 'SMA_50', 'MACD', 'Vol_Delta', 'Momentum']


# ─── Model Manager ────────────────────────────────────────────────────────────

class DynamicSentimentModel:
    """
    Manages per-ticker Random Forest models.

    Lifecycle:
      1. predict_score() is called with current feature values.
      2. If no model exists on disk, train_model() is called first.
      3. The trained model is cached in memory and on disk.
      4. Subsequent calls use the in-memory cache (fast path).
    """

    def __init__(self, model_dir: str = MODEL_DIR):
        self.model_dir = model_dir
        # In-memory cache: {ticker: trained_model}
        self._cache: dict = {}
        os.makedirs(model_dir, exist_ok=True)

    # ── Paths ─────────────────────────────────────────────────────────────────

    def _model_path(self, ticker: str) -> str:
        """Return the file path for a ticker's saved model pickle."""
        safe = ticker.replace('^', 'INDEX').replace('.', '_')
        return os.path.join(self.model_dir, f"{safe}_rf.pkl")

    # ── Feature Engineering ───────────────────────────────────────────────────

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all feature columns from raw OHLCV data.
        Modifies `df` in-place and returns it.
        """
        close = df['Close']

        df['RSI']       = ind.rsi(close)
        df['SMA_20']    = ind.sma(close, 20)
        df['SMA_50']    = ind.sma(close, 50)
        macd_line, _, _ = ind.macd(close)
        df['MACD']      = macd_line
        df['Vol_Delta'] = df['Volume'].pct_change()
        df['Momentum']  = ind.momentum(close, period=5)

        return df

    # ── Training ──────────────────────────────────────────────────────────────

    def train_model(self, ticker: str) -> bool:
        """
        Download 1 year of daily data, compute features, and train a
        RandomForestRegressor to predict next-day percentage return.

        Saves the model to disk on success.

        Args:
            ticker: Stock symbol.

        Returns:
            True if training succeeded, False otherwise.
        """
        try:
            print(f"[AI Model] Training for {ticker}...")
            df = yf.download(ticker, period='1y', interval='1d', progress=False)

            if df.empty or len(df) < MIN_TRAINING_ROWS:
                print(f"[AI Model] Insufficient data for {ticker} ({len(df)} rows)")
                return False

            # Flatten MultiIndex columns (yfinance quirk)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = self._build_features(df)

            # Target: next-day percentage return
            df['Target'] = df['Close'].shift(-1).pct_change() * 100
            df = df.dropna()

            if len(df) < 20:
                print(f"[AI Model] Not enough clean rows for {ticker} after dropna")
                return False

            X = df[FEATURE_COLUMNS]
            y = df['Target']

            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X, y)

            # Persist to disk
            with open(self._model_path(ticker), 'wb') as f:
                pickle.dump(model, f)

            # Cache in memory
            self._cache[ticker] = model
            print(f"[AI Model] Training complete for {ticker}")
            return True

        except Exception as e:
            print(f"[AI Model] Training error for {ticker}: {e}")
            traceback.print_exc()
            return False

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict_score(self, ticker: str, current_features: dict) -> float:
        """
        Predict a sentiment score for the current market state.

        Maps the predicted next-day % return to [-100, +100]:
          predicted_return × 50 (so a 2% move → score of ±100).

        Args:
            ticker:           Stock symbol.
            current_features: Dict with keys matching FEATURE_COLUMNS.

        Returns:
            Score as float in [-100, +100], or 0.0 on failure.
        """
        try:
            # Load from disk if not in memory cache
            if ticker not in self._cache:
                path = self._model_path(ticker)
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        self._cache[ticker] = pickle.load(f)
                    print(f"[AI Model] Loaded cached model for {ticker}")
                else:
                    # No model on disk — train one now
                    if not self.train_model(ticker):
                        return 0.0

            model = self._cache[ticker]

            # Validate all features are present
            missing = [f for f in FEATURE_COLUMNS if f not in current_features]
            if missing:
                print(f"[AI Model] Missing features for {ticker}: {missing}")
                return 0.0

            input_arr      = np.array([current_features[f] for f in FEATURE_COLUMNS]).reshape(1, -1)
            predicted_return = model.predict(input_arr)[0]

            score = float(np.clip(predicted_return * 50, -100, 100))
            print(f"[AI Model] {ticker}: predicted={predicted_return:.3f}%, score={score:.1f}")
            return round(score, 2)

        except Exception as e:
            print(f"[AI Model] Prediction error for {ticker}: {e}")
            traceback.print_exc()
            return 0.0

    # ── Feature Extraction Helper ─────────────────────────────────────────────

    def extract_current_features(self, hist_df: pd.DataFrame) -> dict:
        """
        Compute the feature values for the most recent row of historical data.
        Used to build the input vector for predict_score().

        Args:
            hist_df: Historical OHLCV DataFrame.

        Returns:
            Dict matching FEATURE_COLUMNS.
        """
        close = hist_df['Close']

        rsi_val     = ind.safe_last(ind.rsi(close), default=50.0)
        sma_20_val  = ind.safe_last(ind.sma(close, 20), default=0.0)
        sma_50_val  = ind.safe_last(ind.sma(close, 50), default=0.0)
        macd_line, _, _ = ind.macd(close)
        macd_val    = ind.safe_last(macd_line, default=0.0)
        vol_delta   = ind.safe_last(hist_df['Volume'].pct_change(), default=0.0)
        mom_val     = ind.safe_last(ind.momentum(close, period=5), default=0.0)

        return {
            'RSI':       rsi_val,
            'SMA_20':    sma_20_val,
            'SMA_50':    sma_50_val,
            'MACD':      macd_val,
            'Vol_Delta': vol_delta,
            'Momentum':  mom_val,
        }


# ─── Module-Level Singleton ───────────────────────────────────────────────────
# Shared across all API requests so models are only loaded/trained once.

model_manager = DynamicSentimentModel()
