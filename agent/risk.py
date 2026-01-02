"""
Risk Management Engine
Calculates position sizing, stop loss, targets, and risk-reward ratios.
"""

import logging
from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np

from config import RISK_CONFIG, INDICATORS

logger = logging.getLogger(__name__)


def calculate_risk_metrics(
    symbol: str,
    setup: Dict,
    evaluation: Dict,
    df: pd.DataFrame,
    account_size: Optional[float] = None
) -> Dict:
    """
    Calculate complete risk metrics for a trade setup.
    
    Args:
        symbol: Stock symbol
        setup: Setup dict from detector
        evaluation: Evaluation dict from LLM
        df: DataFrame with indicators
        account_size: Account size in INR (default from config)
    
    Returns:
        Dict with risk metrics
    """
    if account_size is None:
        account_size = RISK_CONFIG['default_account_size']
    
    current_price = setup['current_price']
    latest = df.iloc[-1]
    
    # ========================================================================
    # STOP LOSS CALCULATION
    # ========================================================================
    
    stop_loss = calculate_stop_loss(df, current_price)
    
    # ========================================================================
    # ENTRY RANGE
    # ========================================================================
    
    entry_low, entry_high = calculate_entry_range(current_price)
    entry_mid = (entry_low + entry_high) / 2
    
    # ========================================================================
    # TARGET CALCULATION
    # ========================================================================
    
    targets = calculate_targets(entry_mid, stop_loss)
    
    # ========================================================================
    # RISK-REWARD RATIO
    # ========================================================================
    
    risk_amount = entry_mid - stop_loss
    reward_amount = targets[0] - entry_mid
    risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
    
    # ========================================================================
    # POSITION SIZING
    # ========================================================================
    
    position_size, position_value = calculate_position_size(
        account_size=account_size,
        entry_price=entry_mid,
        stop_loss=stop_loss
    )
    
    # ========================================================================
    # RISK PERCENTAGE
    # ========================================================================
    
    risk_percent = (risk_amount / entry_mid) * 100
    max_loss = position_size * risk_amount
    max_loss_percent = (max_loss / account_size) * 100
    
    # ========================================================================
    # COMPILE METRICS
    # ========================================================================
    
    metrics = {
        'symbol': symbol,
        'entry_range_low': float(entry_low),
        'entry_range_high': float(entry_high),
        'entry_mid': float(entry_mid),
        'stop_loss': float(stop_loss),
        'target_1': float(targets[0]),
        'target_2': float(targets[1]) if len(targets) > 1 else float(targets[0]),
        'risk_amount': float(risk_amount),
        'reward_amount': float(reward_amount),
        'risk_reward_ratio': float(risk_reward_ratio),
        'risk_percent': float(risk_percent),
        'position_size': int(position_size),
        'position_value': float(position_value),
        'max_loss': float(max_loss),
        'max_loss_percent': float(max_loss_percent),
        'potential_gain_1': float((targets[0] - entry_mid) * position_size),
        'potential_gain_2': float((targets[1] - entry_mid) * position_size) if len(targets) > 1 else 0,
    }
    
    logger.info(f"{symbol}: Risk metrics - Entry: ₹{entry_mid:.2f}, "
               f"SL: ₹{stop_loss:.2f}, T1: ₹{targets[0]:.2f}, R:R: {risk_reward_ratio:.2f}")
    
    return metrics


def calculate_stop_loss(df: pd.DataFrame, entry_price: float) -> float:
    """
    Calculate stop loss using ATR-based method.
    
    Args:
        df: DataFrame with indicators
        entry_price: Entry price
    
    Returns:
        Stop loss price
    """
    latest = df.iloc[-1]
    atr_col = f'ATR_{INDICATORS["atr_period"]}'
    
    if atr_col not in df.columns:
        logger.warning("ATR not available, using percentage-based stop loss")
        stop_loss = entry_price * (1 - RISK_CONFIG['stop_loss_min_percent'] / 100)
        return stop_loss
    
    atr_value = latest[atr_col]
    
    # ATR-based stop loss
    atr_multiplier = RISK_CONFIG['stop_loss_atr_multiplier']
    stop_loss_atr = entry_price - (atr_multiplier * atr_value)
    
    # Calculate as percentage
    stop_loss_percent = ((entry_price - stop_loss_atr) / entry_price) * 100
    
    # Apply min/max constraints
    min_stop_pct = RISK_CONFIG['stop_loss_min_percent']
    max_stop_pct = RISK_CONFIG['stop_loss_max_percent']
    
    if stop_loss_percent < min_stop_pct:
        stop_loss = entry_price * (1 - min_stop_pct / 100)
        logger.debug(f"Stop loss adjusted to minimum {min_stop_pct}%")
    elif stop_loss_percent > max_stop_pct:
        stop_loss = entry_price * (1 - max_stop_pct / 100)
        logger.debug(f"Stop loss capped at maximum {max_stop_pct}%")
    else:
        stop_loss = stop_loss_atr
    
    return stop_loss


def calculate_entry_range(current_price: float) -> Tuple[float, float]:
    """
    Calculate entry range around current price.
    
    Args:
        current_price: Current market price
    
    Returns:
        Tuple of (entry_low, entry_high)
    """
    range_pct = RISK_CONFIG['entry_range_percent'] / 100
    
    entry_low = current_price * (1 - range_pct)
    entry_high = current_price * (1 + range_pct)
    
    return entry_low, entry_high


def calculate_targets(entry_price: float, stop_loss: float) -> list:
    """
    Calculate target prices based on risk-reward ratios.
    
    Args:
        entry_price: Entry price
        stop_loss: Stop loss price
    
    Returns:
        List of target prices
    """
    risk = entry_price - stop_loss
    
    targets = []
    for ratio in RISK_CONFIG['target_ratios']:
        target = entry_price + (risk * ratio)
        targets.append(target)
    
    return targets


def calculate_position_size(
    account_size: float,
    entry_price: float,
    stop_loss: float
) -> Tuple[int, float]:
    """
    Calculate position size based on risk management rules.
    
    Args:
        account_size: Total account size in INR
        entry_price: Entry price
        stop_loss: Stop loss price
    
    Returns:
        Tuple of (position_size_shares, position_value)
    """
    # Maximum risk per trade
    max_risk_amount = account_size * (RISK_CONFIG['risk_per_trade_percent'] / 100)
    
    # Risk per share
    risk_per_share = entry_price - stop_loss
    
    if risk_per_share <= 0:
        logger.warning("Invalid risk calculation (risk_per_share <= 0)")
        return 0, 0.0
    
    # Position size based on risk
    position_size = max_risk_amount / risk_per_share
    
    # Calculate position value
    position_value = position_size * entry_price
    
    # Apply maximum position limit
    max_position_value = account_size * (RISK_CONFIG['max_position_percent'] / 100)
    
    if position_value > max_position_value:
        position_size = max_position_value / entry_price
        position_value = max_position_value
        logger.debug(f"Position size capped at {RISK_CONFIG['max_position_percent']}% of account")
    
    # Round to integer shares
    position_size = int(position_size)
    position_value = position_size * entry_price
    
    return position_size, position_value


def validate_risk_reward(risk_reward_ratio: float) -> bool:
    """
    Validate if risk-reward ratio meets minimum criteria.
    
    Args:
        risk_reward_ratio: Calculated R:R ratio
    
    Returns:
        True if acceptable, False otherwise
    """
    min_rr = min(RISK_CONFIG['target_ratios'])
    
    if risk_reward_ratio < min_rr:
        logger.warning(f"Risk-reward ratio {risk_reward_ratio:.2f} below minimum {min_rr}")
        return False
    
    return True


def format_risk_summary(metrics: Dict) -> str:
    """
    Format risk metrics as human-readable string.
    
    Args:
        metrics: Risk metrics dict
    
    Returns:
        Formatted summary string
    """
    summary = f"""
Risk Management Summary for {metrics['symbol']}:

Entry Range: ₹{metrics['entry_range_low']:.2f} - ₹{metrics['entry_range_high']:.2f}
Stop Loss: ₹{metrics['stop_loss']:.2f} ({metrics['risk_percent']:.2f}% risk)

Targets:
  T1: ₹{metrics['target_1']:.2f} (Gain: ₹{metrics['potential_gain_1']:,.0f})
  T2: ₹{metrics['target_2']:.2f} (Gain: ₹{metrics['potential_gain_2']:,.0f})

Risk-Reward Ratio: 1:{metrics['risk_reward_ratio']:.2f}

Position Sizing:
  Shares: {metrics['position_size']:,}
  Position Value: ₹{metrics['position_value']:,.0f}
  Max Loss: ₹{metrics['max_loss']:,.0f} ({metrics['max_loss_percent']:.2f}% of account)
"""
    return summary.strip()
