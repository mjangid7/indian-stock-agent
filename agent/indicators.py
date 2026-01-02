"""
Technical Indicators Engine
Computes all technical indicators using pandas-ta.
"""

import logging
from typing import Dict, Optional
import pandas as pd
import numpy as np

from config import INDICATORS

logger = logging.getLogger(__name__)


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all technical indicators on OHLCV data.
    
    Args:
        df: DataFrame with OHLCV columns
    
    Returns:
        DataFrame with indicators added as new columns
    """
    if df is None or df.empty:
        logger.warning("Cannot compute indicators on empty dataframe")
        return df
    
    try:
        import pandas_ta as ta
        
        df = df.copy()
        
        # Ensure proper column names
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing required columns. Have: {df.columns.tolist()}")
            return df
        
        # ====================================================================
        # EXPONENTIAL MOVING AVERAGES
        # ====================================================================
        
        df[f'EMA_{INDICATORS["ema_short"]}'] = ta.ema(
            df['Close'],
            length=INDICATORS["ema_short"]
        )
        
        df[f'EMA_{INDICATORS["ema_medium"]}'] = ta.ema(
            df['Close'],
            length=INDICATORS["ema_medium"]
        )
        
        df[f'EMA_{INDICATORS["ema_long"]}'] = ta.ema(
            df['Close'],
            length=INDICATORS["ema_long"]
        )
        
        # ====================================================================
        # RSI (Relative Strength Index)
        # ====================================================================
        
        df[f'RSI_{INDICATORS["rsi_period"]}'] = ta.rsi(
            df['Close'],
            length=INDICATORS["rsi_period"]
        )
        
        # ====================================================================
        # MACD (Moving Average Convergence Divergence)
        # ====================================================================
        
        macd = ta.macd(
            df['Close'],
            fast=INDICATORS["macd_fast"],
            slow=INDICATORS["macd_slow"],
            signal=INDICATORS["macd_signal"]
        )
        
        if macd is not None and not macd.empty:
            df['MACD'] = macd.iloc[:, 0]
            df['MACD_signal'] = macd.iloc[:, 1]
            df['MACD_histogram'] = macd.iloc[:, 2]
        
        # ====================================================================
        # ATR (Average True Range)
        # ====================================================================
        
        df[f'ATR_{INDICATORS["atr_period"]}'] = ta.atr(
            df['High'],
            df['Low'],
            df['Close'],
            length=INDICATORS["atr_period"]
        )
        
        # ====================================================================
        # VOLUME INDICATORS
        # ====================================================================
        
        # Volume SMA
        df[f'Volume_SMA_{INDICATORS["volume_sma"]}'] = ta.sma(
            df['Volume'],
            length=INDICATORS["volume_sma"]
        )
        
        # Volume ratio (current vs average)
        df['Volume_Ratio'] = df['Volume'] / df[f'Volume_SMA_{INDICATORS["volume_sma"]}']
        
        # ====================================================================
        # BOLLINGER BANDS
        # ====================================================================
        
        bbands = ta.bbands(
            df['Close'],
            length=INDICATORS["bollinger_period"],
            std=INDICATORS["bollinger_std"]
        )
        
        if bbands is not None and not bbands.empty:
            df['BB_Lower'] = bbands.iloc[:, 0]
            df['BB_Mid'] = bbands.iloc[:, 1]
            df['BB_Upper'] = bbands.iloc[:, 2]
        
        # ====================================================================
        # CUSTOM INDICATORS
        # ====================================================================
        
        # Price position relative to EMA50
        if f'EMA_{INDICATORS["ema_medium"]}' in df.columns:
            df['Price_Above_EMA50'] = df['Close'] > df[f'EMA_{INDICATORS["ema_medium"]}']
        
        # Price position relative to EMA200
        if f'EMA_{INDICATORS["ema_long"]}' in df.columns:
            df['Price_Above_EMA200'] = df['Close'] > df[f'EMA_{INDICATORS["ema_long"]}']
        
        # Volume spike detection
        df['Volume_Spike'] = df['Volume_Ratio'] > 1.5
        
        # ATR as percentage of price
        df['ATR_Percent'] = (df[f'ATR_{INDICATORS["atr_period"]}'] / df['Close']) * 100
        
        # Higher highs / higher lows (simple momentum indicator)
        df['Higher_High'] = df['High'] > df['High'].shift(1)
        df['Higher_Low'] = df['Low'] > df['Low'].shift(1)
        
        # Rolling highs and lows (for breakout detection)
        df['Rolling_High_20'] = df['High'].rolling(window=20).max()
        df['Rolling_Low_20'] = df['Low'].rolling(window=20).min()
        
        logger.debug(f"Computed indicators: {len(df)} bars")
        return df
    
    except ImportError:
        logger.error("pandas-ta not installed. Run: pip install pandas-ta")
        return df
    except Exception as e:
        logger.error(f"Error computing indicators: {e}")
        return df


def get_latest_indicators(df: pd.DataFrame) -> Dict[str, float]:
    """
    Extract latest indicator values as a dictionary.
    
    Args:
        df: DataFrame with computed indicators
    
    Returns:
        Dictionary of indicator name to value
    """
    if df is None or df.empty:
        return {}
    
    latest = df.iloc[-1]
    
    indicators_dict = {
        'close': float(latest.get('Close', 0)),
        'volume': float(latest.get('Volume', 0)),
        'ema_20': float(latest.get(f'EMA_{INDICATORS["ema_short"]}', 0)),
        'ema_50': float(latest.get(f'EMA_{INDICATORS["ema_medium"]}', 0)),
        'ema_200': float(latest.get(f'EMA_{INDICATORS["ema_long"]}', 0)),
        'rsi_14': float(latest.get(f'RSI_{INDICATORS["rsi_period"]}', 0)),
        'macd': float(latest.get('MACD', 0)),
        'macd_signal': float(latest.get('MACD_signal', 0)),
        'macd_histogram': float(latest.get('MACD_histogram', 0)),
        'atr_14': float(latest.get(f'ATR_{INDICATORS["atr_period"]}', 0)),
        'volume_sma_20': float(latest.get(f'Volume_SMA_{INDICATORS["volume_sma"]}', 0)),
        'volume_ratio': float(latest.get('Volume_Ratio', 0)),
        'atr_percent': float(latest.get('ATR_Percent', 0)),
        'bb_upper': float(latest.get('BB_Upper', 0)),
        'bb_mid': float(latest.get('BB_Mid', 0)),
        'bb_lower': float(latest.get('BB_Lower', 0)),
        'rolling_high_20': float(latest.get('Rolling_High_20', 0)),
        'rolling_low_20': float(latest.get('Rolling_Low_20', 0)),
    }
    
    # Replace NaN with 0
    indicators_dict = {k: (v if not np.isnan(v) else 0.0) for k, v in indicators_dict.items()}
    
    return indicators_dict


def check_indicator_health(df: pd.DataFrame) -> Dict[str, bool]:
    """
    Check if indicators are properly computed (not all NaN).
    
    Args:
        df: DataFrame with indicators
    
    Returns:
        Dictionary of indicator health checks
    """
    health = {}
    
    indicator_cols = [
        f'EMA_{INDICATORS["ema_short"]}',
        f'EMA_{INDICATORS["ema_medium"]}',
        f'EMA_{INDICATORS["ema_long"]}',
        f'RSI_{INDICATORS["rsi_period"]}',
        'MACD',
        f'ATR_{INDICATORS["atr_period"]}',
    ]
    
    for col in indicator_cols:
        if col in df.columns:
            health[col] = not df[col].isna().all()
        else:
            health[col] = False
    
    return health
