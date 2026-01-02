"""
Stock Universe Loader
Loads and validates the stock universe for scanning.
"""

import logging
from typing import List, Optional
from config import DEFAULT_UNIVERSE, NIFTY_50_NSE

logger = logging.getLogger(__name__)


def load_universe(
    universe_name: Optional[str] = None,
    custom_symbols: Optional[List[str]] = None
) -> List[str]:
    """
    Load stock universe for scanning.
    
    Args:
        universe_name: 'NIFTY50' or None for default
        custom_symbols: Optional list of custom symbols (must have .NS suffix)
    
    Returns:
        List of symbols with .NS suffix for NSE
    """
    if custom_symbols:
        # Validate custom symbols
        validated = []
        for symbol in custom_symbols:
            if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
                logger.warning(f"Symbol {symbol} missing .NS/.BO suffix, adding .NS")
                symbol = f"{symbol}.NS"
            validated.append(symbol)
        
        logger.info(f"Loaded custom universe: {len(validated)} symbols")
        return validated
    
    # Load predefined universe
    if universe_name == 'NIFTY50' or universe_name is None:
        universe = DEFAULT_UNIVERSE.copy()
        logger.info(f"Loaded NIFTY 50 universe: {len(universe)} symbols")
        return universe
    
    # Fallback
    logger.warning(f"Unknown universe '{universe_name}', using default")
    return DEFAULT_UNIVERSE.copy()


def validate_symbol(symbol: str) -> bool:
    """
    Validate that a symbol has proper NSE/BSE suffix.
    
    Args:
        symbol: Stock symbol to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not symbol:
        return False
    
    if symbol.endswith('.NS') or symbol.endswith('.BO'):
        return True
    
    return False


def get_base_symbol(symbol: str) -> str:
    """
    Extract base symbol without exchange suffix.
    
    Args:
        symbol: Full symbol like 'RELIANCE.NS'
    
    Returns:
        Base symbol like 'RELIANCE'
    """
    if '.' in symbol:
        return symbol.split('.')[0]
    return symbol


def format_symbol_for_display(symbol: str) -> str:
    """
    Format symbol for logging and display.
    
    Args:
        symbol: Full symbol like 'RELIANCE.NS'
    
    Returns:
        Formatted string like 'RELIANCE (NSE)'
    """
    if symbol.endswith('.NS'):
        return f"{get_base_symbol(symbol)} (NSE)"
    elif symbol.endswith('.BO'):
        return f"{get_base_symbol(symbol)} (BSE)"
    return symbol
