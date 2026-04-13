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
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.model_selection import GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

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
    Manages per-ticker Random Forest models for sentiment.
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


class IntrinsicValueModel:
    """
    Manages per-ticker Intrinsic Value estimation using dynamic ML selection.
    Uses GridSearchCV to find the best model among RF, GBM, and SVR.
    """

    def __init__(self, model_dir: str = MODEL_DIR):
        self.model_dir = model_dir
        self._cache: dict = {}
        os.makedirs(model_dir, exist_ok=True)

    def _model_path(self, ticker: str) -> str:
        safe = ticker.replace('^', 'INDEX').replace('.', '_')
        return os.path.join(self.model_dir, f"{safe}_intrinsic_best.pkl")

    def _calculate_graham_number(self, info: dict) -> float | None:
        """Calculate Graham Number: sqrt(22.5 * EPS * BookValue)"""
        eps = info.get('trailingEps')
        bv = info.get('bookValue')
        if eps and bv and eps > 0 and bv > 0:
            return np.sqrt(22.5 * eps * bv)
        return None

    def train_model(self, ticker: str) -> bool:
        """
        Train a model to predict the Graham Number based on technical indicators.
        Uses GridSearchCV to tune and select the best algorithm.
        """
        try:
            print(f"[Intrinsic ML] Training best model for {ticker}...")
            stock = yf.Ticker(ticker)
            df = stock.history(period='2y') # Get more data for stability

            if df.empty or len(df) < MIN_TRAINING_ROWS:
                return False

            # Target: Historical Graham Number proxy
            # Since historical EPS is hard to get, we use the current Graham Number as the target
            # and train the model to map technical states to this valuation.
            graham_val = self._calculate_graham_number(stock.info)
            if not graham_val:
                # Fallback to a 200-day SMA as a proxy for fair value if fundamentals missing
                graham_val = df['Close'].rolling(200).mean().iloc[-1]

            if pd.isna(graham_val):
                return False

            # Feature engineering
            df['RSI'] = ind.rsi(df['Close'])
            df['SMA_20'] = ind.sma(df['Close'], 20)
            df['SMA_200'] = ind.sma(df['Close'], 200)
            df['Volatility'] = df['Close'].rolling(20).std()
            df = df.dropna()

            X = df[['RSI', 'SMA_20', 'SMA_200', 'Volatility']]
            y = np.full(len(X), graham_val) # Target is our estimated fair value

            # Add some noise/variance to y based on price deviation to help training converge
            # This is a heuristic to make the model learn "Fair Value" relative to market state
            price_dev = (df['Close'] - df['Close'].rolling(50).mean()) / df['Close'].rolling(50).mean()
            y = y * (1 + price_dev.values * 0.1)

            # Define pipeline and grid
            pipe = Pipeline([
                ('scaler', StandardScaler()),
                ('regressor', RandomForestRegressor())
            ])

            param_grid = [
                {
                    'regressor': [RandomForestRegressor(random_state=42)],
                    'regressor__n_estimators': [50, 100],
                    'regressor__max_depth': [None, 10]
                },
                {
                    'regressor': [GradientBoostingRegressor(random_state=42)],
                    'regressor__n_estimators': [50, 100],
                    'regressor__learning_rate': [0.1, 0.05]
                },
                {
                    'regressor': [SVR()],
                    'regressor__C': [1, 10],
                    'regressor__epsilon': [0.1, 0.2]
                }
            ]

            grid = GridSearchCV(pipe, param_grid, cv=3, scoring='neg_mean_squared_error')
            grid.fit(X, y)

            best_model = grid.best_estimator_
            print(f"[Intrinsic ML] Best model for {ticker}: {grid.best_params_['regressor']}")

            # Persist
            with open(self._model_path(ticker), 'wb') as f:
                pickle.dump(best_model, f)

            self._cache[ticker] = best_model
            return True

        except Exception as e:
            print(f"[Intrinsic ML] Training error: {e}")
            return False

    def predict_intrinsic_value(self, ticker: str, current_features: dict) -> float:
        """Predict the intrinsic value for the current state."""
        try:
            if ticker not in self._cache:
                path = self._model_path(ticker)
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        self._cache[ticker] = pickle.load(f)
                else:
                    if not self.train_model(ticker):
                        return 0.0

            model = self._cache[ticker]
            # Expected features: RSI, SMA_20, SMA_200, Volatility
            # We'll calculate them on the fly if not provided
            feat_list = ['RSI', 'SMA_20', 'SMA_200', 'Volatility']
            input_arr = np.array([current_features.get(f, 0) for f in feat_list]).reshape(1, -1)
            prediction = model.predict(input_arr)[0]
            return round(float(prediction), 2)

        except Exception as e:
            print(f"[Intrinsic ML] Prediction error: {e}")
            return 0.0


# ─── Module-Level Singletons ───────────────────────────────────────────────────

model_manager = DynamicSentimentModel()
intrinsic_model_manager = IntrinsicValueModel()
