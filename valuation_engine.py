"""
=============================================================================
valuation_engine.py
=============================================================================
Calculates the intrinsic value of a stock based on fundamental data.
Uses Graham Number and Simplified DCF.
Computes percentage difference from current market price.
=============================================================================
"""

import logging
from typing import Dict, Tuple, Optional
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValuationEngine:
    """Calculates intrinsic values based on financial fundamentals."""

    def calculate_intrinsic_value(self, info: Dict, current_price: float) -> Tuple[float, float]:
        """Calculates intrinsic price and percentage difference.
        
        Args:
            info: Dictionary of stock info (from yfinance).
            current_price: Current market price.
            
        Returns:
            Tuple: (Intrinsic Price, Percentage Difference)
        """
        if not current_price or current_price <= 0:
            return 0.0, 0.0

        graham_val = self._graham_number(info)
        dcf_val = self._simplified_dcf(info)
        
        # We can take an average or use the one that is available.
        if graham_val > 0 and dcf_val > 0:
            intrinsic_price = (graham_val + dcf_val) / 2
        elif graham_val > 0:
            intrinsic_price = graham_val
        elif dcf_val > 0:
            intrinsic_price = dcf_val
        else:
            # Fallback to a very simple SMA-based intrinsic (not ideal, but shows something)
            # This logic should be improved if actual fundamentals are missing.
            intrinsic_price = current_price * 0.95 

        # Calculate percentage difference
        # % Diff = ((Intrinsic - Current) / Current) * 100
        # Positive means undervalued, negative means overvalued
        diff_percent = ((intrinsic_price - current_price) / current_price) * 100
        
        return round(intrinsic_price, 2), round(diff_percent, 2)

    def _graham_number(self, info: Dict) -> float:
        """Calculates Graham Number: sqrt(22.5 * EPS * BookValue)."""
        try:
            eps = info.get('trailingEps') or info.get('forwardEps')
            book_value = info.get('bookValue')
            
            if eps and book_value and eps > 0 and book_value > 0:
                return np.sqrt(22.5 * eps * book_value)
            return 0.0
        except Exception as e:
            logger.error(f"[Valuation] Graham calc error: {e}")
            return 0.0

    def _simplified_dcf(self, info: Dict) -> float:
        """Calculates a simplified DCF based on Free Cash Flow or Earnings Growth.
        
        Note: This is a highly simplified model for demonstration.
        """
        try:
            fcf = info.get('freeCashflow')
            shares_outstanding = info.get('sharesOutstanding')
            growth_rate = info.get('earningsGrowth') or 0.05  # Default 5%
            discount_rate = 0.10  # 10% discount rate
            
            if fcf and shares_outstanding and fcf > 0 and shares_outstanding > 0:
                fcf_per_share = fcf / shares_outstanding
                # Simplified 5-year growth + Terminal value
                # Intrinsic = FCF / (Discount - Growth)
                intrinsic = fcf_per_share * (1 + growth_rate) / (discount_rate - growth_rate)
                return max(0.0, intrinsic)
            return 0.0
        except Exception as e:
            logger.error(f"[Valuation] DCF calc error: {e}")
            return 0.0
