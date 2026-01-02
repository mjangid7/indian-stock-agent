"""
Setup Detector
Rule-based detection of swing trade setups (NO LLM here).
Identifies candidates for LLM evaluation.
"""

import logging
from typing import Dict, List, Optional
from datetime import date
import pandas as pd
import numpy as np

from config import SETUP_RULES, INDICATORS

logger = logging.getLogger(__name__)


class SetupType:
    """Setup type constants."""
    BREAKOUT = "BREAKOUT"
    PULLBACK = "PULLBACK"
    MOMENTUM = "MOMENTUM"
    CONSOLIDATION = "CONSOLIDATION"


def detect_setups(
    symbol: str,
    df: pd.DataFrame,
    timeframe: str = '1d'
) -> List[Dict]:
    """
    Detect swing trade setups using rule-based logic.
    
    Args:
        symbol: Stock symbol
        df: DataFrame with OHLCV and indicators
        timeframe: Timeframe of data
    
    Returns:
        List of detected setups (may be empty)
    """
    if df is None or df.empty or len(df) < 50:
        logger.warning(f"{symbol}: Insufficient data for setup detection")
        return []
    
    setups = []
    latest = df.iloc[-1]
    
    # ========================================================================
    # BASELINE FILTERS (must pass all)
    # ========================================================================
    
    baseline_checks = check_baseline_filters(df)
    if not baseline_checks['passed']:
        logger.debug(f"{symbol}: Failed baseline filters - {baseline_checks['failures']}")
        return []
    
    # ========================================================================
    # DETECT SPECIFIC SETUP TYPES
    # ========================================================================
    
    # 1. Breakout Setup
    breakout = detect_breakout(symbol, df, timeframe)
    if breakout:
        setups.append(breakout)
    
    # 2. Pullback to EMA Setup
    pullback = detect_pullback(symbol, df, timeframe)
    if pullback:
        setups.append(pullback)
    
    # 3. Momentum Continuation Setup
    momentum = detect_momentum(symbol, df, timeframe)
    if momentum:
        setups.append(momentum)
    
    # 4. Consolidation Breakout
    consolidation = detect_consolidation_breakout(symbol, df, timeframe)
    if consolidation:
        setups.append(consolidation)
    
    if setups:
        logger.info(f"{symbol}: Detected {len(setups)} setup(s)")
    
    return setups


def check_baseline_filters(df: pd.DataFrame) -> Dict:
    """
    Check baseline filters that all setups must pass.
    
    Returns:
        Dict with 'passed' (bool) and 'failures' (list)
    """
    failures = []
    latest = df.iloc[-1]
    
    # Get indicator column names
    ema_50_col = f'EMA_{INDICATORS["ema_medium"]}'
    ema_200_col = f'EMA_{INDICATORS["ema_long"]}'
    rsi_col = f'RSI_{INDICATORS["rsi_period"]}'
    
    # Filter 1: Price above EMAs (configurable)
    for ema_period in SETUP_RULES['price_above_ema']:
        ema_col = f'EMA_{ema_period}'
        if ema_col in df.columns:
            if not (latest['Close'] > latest[ema_col]):
                failures.append(f"price_below_ema_{ema_period}")
    
    # Filter 2: RSI in valid range
    if rsi_col in df.columns:
        rsi_value = latest[rsi_col]
        if not (SETUP_RULES['rsi_min'] <= rsi_value <= SETUP_RULES['rsi_max']):
            failures.append(f"rsi_out_of_range_{rsi_value:.1f}")
    
    # Filter 3: Minimum ATR (volatility)
    atr_col = f'ATR_{INDICATORS["atr_period"]}'
    if atr_col in df.columns and 'ATR_Percent' in df.columns:
        if latest['ATR_Percent'] < SETUP_RULES['min_atr_percent']:
            failures.append(f"atr_too_low_{latest['ATR_Percent']:.2f}%")
    
    # Filter 4: Volume spike
    if 'Volume_Ratio' in df.columns:
        if latest['Volume_Ratio'] < SETUP_RULES['volume_spike_multiplier']:
            failures.append(f"volume_low_{latest['Volume_Ratio']:.2f}x")
    
    return {
        'passed': len(failures) == 0,
        'failures': failures
    }


def detect_breakout(symbol: str, df: pd.DataFrame, timeframe: str) -> Optional[Dict]:
    """
    Detect range breakout setup.
    Price breaks above recent consolidation high with volume.
    """
    latest = df.iloc[-1]
    lookback = SETUP_RULES['breakout_lookback']
    
    # Check if current close is breaking above rolling high
    if 'Rolling_High_20' not in df.columns:
        return None
    
    recent_high = df['Rolling_High_20'].iloc[-2]  # Previous bar's rolling high
    current_close = latest['Close']
    
    # Breakout condition: close above recent high
    if current_close <= recent_high:
        return None
    
    # Additional confirmation: volume spike
    if 'Volume_Ratio' not in df.columns or latest['Volume_Ratio'] < 1.3:
        return None
    
    # Calculate breakout strength
    breakout_percent = ((current_close - recent_high) / recent_high) * 100
    
    setup = {
        'symbol': symbol,
        'setup_type': SetupType.BREAKOUT,
        'timeframe': timeframe,
        'detection_date': latest.name.date() if hasattr(latest.name, 'date') else date.today(),
        'current_price': float(current_close),
        'trigger_price': float(recent_high),
        'breakout_percent': float(breakout_percent),
        'volume_ratio': float(latest['Volume_Ratio']),
        'conditions_met': ['price_above_ema', 'volume_spike', 'breakout_confirmed'],
        'setup_score': calculate_setup_score(df, SetupType.BREAKOUT),
    }
    
    logger.info(f"{symbol}: BREAKOUT detected - {breakout_percent:.2f}% above {recent_high:.2f}")
    return setup


def detect_pullback(symbol: str, df: pd.DataFrame, timeframe: str) -> Optional[Dict]:
    """
    Detect pullback to EMA setup.
    Price pulls back to EMA50 in an uptrend, showing potential bounce.
    """
    latest = df.iloc[-1]
    ema_50_col = f'EMA_{INDICATORS["ema_medium"]}'
    
    if ema_50_col not in df.columns:
        return None
    
    ema_50 = latest[ema_50_col]
    current_close = latest['Close']
    
    # Calculate distance from EMA50
    distance_from_ema = ((current_close - ema_50) / ema_50) * 100
    
    # Pullback condition: price within tolerance of EMA50
    tolerance = SETUP_RULES['pullback_tolerance_percent']
    if not (-tolerance <= distance_from_ema <= tolerance):
        return None
    
    # Additional check: previous bars were in downtrend (pulling back)
    recent_bars = df.tail(5)
    if not (recent_bars['Close'].iloc[-2] < recent_bars['Close'].iloc[-5]):
        return None
    
    # Check for bounce signs (today's low touched/near EMA but closed higher)
    if latest['Low'] > ema_50 * 1.01:  # Didn't actually touch EMA
        return None
    
    setup = {
        'symbol': symbol,
        'setup_type': SetupType.PULLBACK,
        'timeframe': timeframe,
        'detection_date': latest.name.date() if hasattr(latest.name, 'date') else date.today(),
        'current_price': float(current_close),
        'trigger_price': float(ema_50),
        'distance_from_ema': float(distance_from_ema),
        'ema_value': float(ema_50),
        'conditions_met': ['price_near_ema50', 'pullback_structure', 'potential_bounce'],
        'setup_score': calculate_setup_score(df, SetupType.PULLBACK),
    }
    
    logger.info(f"{symbol}: PULLBACK detected - {distance_from_ema:.2f}% from EMA50")
    return setup


def detect_momentum(symbol: str, df: pd.DataFrame, timeframe: str) -> Optional[Dict]:
    """
    Detect momentum continuation setup.
    Series of higher highs and higher lows with strong MACD.
    """
    latest = df.iloc[-1]
    momentum_bars = SETUP_RULES['momentum_bars']
    
    if 'Higher_High' not in df.columns or 'Higher_Low' not in df.columns:
        return None
    
    # Check for consecutive higher highs and higher lows
    recent = df.tail(momentum_bars)
    higher_highs_count = recent['Higher_High'].sum()
    higher_lows_count = recent['Higher_Low'].sum()
    
    # Need at least 2 out of 3 bars showing momentum
    if higher_highs_count < 2 or higher_lows_count < 2:
        return None
    
    # MACD confirmation
    if 'MACD_histogram' in df.columns:
        if latest['MACD_histogram'] <= 0:
            return None
    
    # Calculate momentum strength
    price_change = ((latest['Close'] - df['Close'].iloc[-momentum_bars]) / df['Close'].iloc[-momentum_bars]) * 100
    
    setup = {
        'symbol': symbol,
        'setup_type': SetupType.MOMENTUM,
        'timeframe': timeframe,
        'detection_date': latest.name.date() if hasattr(latest.name, 'date') else date.today(),
        'current_price': float(latest['Close']),
        'price_change_percent': float(price_change),
        'higher_highs': int(higher_highs_count),
        'higher_lows': int(higher_lows_count),
        'macd_histogram': float(latest['MACD_histogram']) if 'MACD_histogram' in df.columns else 0,
        'conditions_met': ['higher_highs', 'higher_lows', 'macd_positive'],
        'setup_score': calculate_setup_score(df, SetupType.MOMENTUM),
    }
    
    logger.info(f"{symbol}: MOMENTUM detected - {price_change:.2f}% in {momentum_bars} bars")
    return setup


def detect_consolidation_breakout(symbol: str, df: pd.DataFrame, timeframe: str) -> Optional[Dict]:
    """
    Detect consolidation breakout setup.
    Price compressed in tight range, now breaking out.
    """
    latest = df.iloc[-1]
    periods = SETUP_RULES['consolidation_periods']
    range_pct = SETUP_RULES['consolidation_range_percent']
    
    if len(df) < periods + 5:
        return None
    
    # Analyze recent consolidation
    consolidation_window = df.tail(periods + 1).iloc[:-1]  # Exclude current bar
    high_in_range = consolidation_window['High'].max()
    low_in_range = consolidation_window['Low'].min()
    
    # Calculate range compression
    price_range = ((high_in_range - low_in_range) / low_in_range) * 100
    
    # Must be consolidating (tight range)
    if price_range > range_pct:
        return None
    
    # Current bar breaks out of range
    if latest['Close'] <= high_in_range:
        return None
    
    # Volume confirmation
    if 'Volume_Ratio' in df.columns and latest['Volume_Ratio'] < 1.2:
        return None
    
    setup = {
        'symbol': symbol,
        'setup_type': SetupType.CONSOLIDATION,
        'timeframe': timeframe,
        'detection_date': latest.name.date() if hasattr(latest.name, 'date') else date.today(),
        'current_price': float(latest['Close']),
        'consolidation_high': float(high_in_range),
        'consolidation_low': float(low_in_range),
        'range_percent': float(price_range),
        'breakout_percent': float(((latest['Close'] - high_in_range) / high_in_range) * 100),
        'conditions_met': ['tight_consolidation', 'breakout_confirmed', 'volume_spike'],
        'setup_score': calculate_setup_score(df, SetupType.CONSOLIDATION),
    }
    
    logger.info(f"{symbol}: CONSOLIDATION BREAKOUT detected - {price_range:.2f}% range")
    return setup


def calculate_setup_score(df: pd.DataFrame, setup_type: str) -> float:
    """
    Calculate preliminary setup score (0-100).
    
    This is a simple heuristic score before LLM evaluation.
    """
    score = 50.0  # Base score
    latest = df.iloc[-1]
    
    # Volume score (0-20 points)
    if 'Volume_Ratio' in df.columns:
        vol_ratio = latest['Volume_Ratio']
        volume_score = min(vol_ratio * 10, 20)
        score += volume_score
    
    # Trend alignment (0-20 points)
    ema_20_col = f'EMA_{INDICATORS["ema_short"]}'
    ema_50_col = f'EMA_{INDICATORS["ema_medium"]}'
    ema_200_col = f'EMA_{INDICATORS["ema_long"]}'
    
    if all(col in df.columns for col in [ema_20_col, ema_50_col, ema_200_col]):
        if latest[ema_20_col] > latest[ema_50_col] > latest[ema_200_col]:
            score += 20
        elif latest[ema_20_col] > latest[ema_50_col]:
            score += 10
    
    # RSI score (0-10 points)
    rsi_col = f'RSI_{INDICATORS["rsi_period"]}'
    if rsi_col in df.columns:
        rsi = latest[rsi_col]
        if 60 <= rsi <= 70:
            score += 10
        elif 55 <= rsi <= 75:
            score += 5
    
    # MACD alignment (0-10 points)
    if 'MACD_histogram' in df.columns:
        if latest['MACD_histogram'] > 0:
            score += 10
    
    return min(score, 100.0)
