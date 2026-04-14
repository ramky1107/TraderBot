"""
=============================================================================
constants.py
=============================================================================
Application-wide constants.
Import this module wherever you need a shared configuration value.

Usage:
    from constants import SERVER_PORT, CACHE_TTL_STOCK
=============================================================================
"""

# ─── Server ───────────────────────────────────────────────────────────────────

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8050
DEBUG       = True

# ─── Cache TTLs (in minutes) ──────────────────────────────────────────────────

CACHE_TTL_STOCK     = 60    # Stock OHLCV data cache (1 hour)
CACHE_TTL_SENTIMENT = 5     # Sentiment score cache (5 minutes)
CACHE_TTL_RATIOS    = 10    # Financial ratios cache (10 minutes)
CACHE_TTL_NEWS      = 5     # News cache (5 minutes)

# ─── Sentiment Score Caps ─────────────────────────────────────────────────────

TECH_SCORE_CAP = 50    # Technical indicators max contribution
NEWS_SCORE_CAP = 30    # News sentiment max contribution
LIVE_SCORE_CAP = 20    # Live price action max contribution

# ─── RSI Thresholds ───────────────────────────────────────────────────────────

RSI_OVERSOLD_EXTREME   = 20
RSI_OVERSOLD           = 30
RSI_OVERSOLD_MILD      = 40
RSI_OVERBOUGHT_MILD    = 60
RSI_OVERBOUGHT         = 70
RSI_OVERBOUGHT_EXTREME = 80

# ─── Minimum Data Requirements ────────────────────────────────────────────────

MIN_ROWS_FOR_INDICATORS = 50    # Minimum DataFrame rows for reliable indicators
MIN_TRAINING_ROWS       = 50    # Minimum rows to train the AI model

# ─── Chart Theme ─────────────────────────────────────────────────────────────

CHART_BG_COLOR   = '#000000'   # Midnight black
CHART_GRID_COLOR = '#1a1a2e'   # Subtle dark grid lines
CHART_TEXT_COLOR = '#D1D4DC'   # Light grey text

# ─── Default Ticker ───────────────────────────────────────────────────────────

DEFAULT_TICKER   = '^NSEI'
DEFAULT_PERIOD   = '5d'
DEFAULT_INTERVAL = '1d'

# ─── Legacy (kept for backward compatibility) ─────────────────────────────────

testCompany          = 'AAPL.us'
testCompanyYFinance  = 'AAPL'
duration             = '1mo'
interval             = '1h'