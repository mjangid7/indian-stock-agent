"""
Market Data Fetcher
Fetches OHLCV data with jugaad-data (primary) and yfinance (fallback).
Implements caching and rate limiting.
"""

import logging
import time
import sqlite3
import json
from datetime import datetime, timedelta, date
from typing import Dict, Optional, Tuple
from pathlib import Path

import pandas as pd
import numpy as np

from config import DATA_CONFIG, CACHE_DIR

logger = logging.getLogger(__name__)

# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

CACHE_DB_PATH = CACHE_DIR / "market_data_cache.db"


def init_cache_db():
    """Initialize cache database."""
    conn = sqlite3.connect(str(CACHE_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data_cache (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            fetch_date DATE NOT NULL,
            data TEXT NOT NULL,
            cached_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, timeframe, fetch_date)
        )
    """)
    conn.commit()
    conn.close()


def get_cached_data(
    symbol: str,
    timeframe: str,
    target_date: date,
    ttl_seconds: int
) -> Optional[pd.DataFrame]:
    """Retrieve cached data if valid."""
    try:
        conn = sqlite3.connect(str(CACHE_DB_PATH))
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(seconds=ttl_seconds)
        
        cursor.execute("""
            SELECT data FROM market_data_cache
            WHERE symbol = ? AND timeframe = ? AND fetch_date = ?
            AND cached_at > ?
        """, (symbol, timeframe, target_date, cutoff))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data_dict = json.loads(row[0])
            df = pd.DataFrame(data_dict)
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
            logger.debug(f"Cache HIT: {symbol} {timeframe}")
            return df
        
        logger.debug(f"Cache MISS: {symbol} {timeframe}")
        return None
    
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
        return None


def cache_data(symbol: str, timeframe: str, target_date: date, df: pd.DataFrame):
    """Cache fetched data."""
    try:
        conn = sqlite3.connect(str(CACHE_DB_PATH))
        
        # Prepare data for JSON storage
        df_copy = df.copy()
        if df_copy.index.name == 'Date' or isinstance(df_copy.index, pd.DatetimeIndex):
            df_copy.reset_index(inplace=True)
            if 'Date' in df_copy.columns:
                df_copy['Date'] = df_copy['Date'].astype(str)
        
        data_json = df_copy.to_json(orient='records', date_format='iso')
        
        conn.execute("""
            INSERT OR REPLACE INTO market_data_cache 
            (symbol, timeframe, fetch_date, data, cached_at)
            VALUES (?, ?, ?, ?, ?)
        """, (symbol, timeframe, target_date, data_json, datetime.now()))
        
        conn.commit()
        conn.close()
        logger.debug(f"Cached: {symbol} {timeframe}")
    
    except Exception as e:
        logger.warning(f"Cache write error: {e}")


# ============================================================================
# DATA SOURCE: JUGAAD-DATA (PRIMARY)
# ============================================================================

def fetch_with_jugaad(
    symbol: str,
    start_date: date,
    end_date: date,
    timeframe: str = '1d'
) -> Optional[pd.DataFrame]:
    """
    Fetch data using jugaad-data (NSE-specific).
    
    Args:
        symbol: Stock symbol with .NS suffix
        start_date: Start date for data
        end_date: End date for data
        timeframe: '1d' or '1wk' (weekly not directly supported, will resample)
    
    Returns:
        DataFrame with OHLCV data or None
    """
    try:
        from jugaad_data.nse import stock_df
        
        # Remove .NS suffix for jugaad-data
        base_symbol = symbol.replace('.NS', '').replace('.BO', '')
        
        logger.debug(f"Fetching {base_symbol} with jugaad-data from {start_date} to {end_date}")
        
        # Fetch daily data
        df = stock_df(
            symbol=base_symbol,
            from_date=start_date,
            to_date=end_date,
            series="EQ"  # Equity series
        )
        
        if df is None or df.empty:
            logger.warning(f"jugaad-data returned empty for {symbol}")
            return None
        
        # Rename columns to standard format
        df = df.rename(columns={
            'DATE': 'Date',
            'OPEN': 'Open',
            'HIGH': 'High',
            'LOW': 'Low',
            'CLOSE': 'Close',
            'VOLUME': 'Volume',
            'PREV_CLOSE': 'Prev_Close',
        })
        
        # Set Date as index
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
        
        # Keep only OHLCV
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        # Convert to weekly if requested
        if timeframe == '1wk':
            df = df.resample('W').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
        
        logger.info(f"jugaad-data fetched {len(df)} bars for {symbol}")
        return df
    
    except ImportError:
        logger.error("jugaad-data not installed")
        return None
    except Exception as e:
        logger.warning(f"jugaad-data fetch failed for {symbol}: {e}")
        return None


# ============================================================================
# DATA SOURCE: YFINANCE (FALLBACK)
# ============================================================================

def fetch_with_yfinance(
    symbol: str,
    start_date: date,
    end_date: date,
    timeframe: str = '1d'
) -> Optional[pd.DataFrame]:
    """
    Fetch data using yfinance (fallback).
    
    Args:
        symbol: Stock symbol with .NS/.BO suffix
        start_date: Start date for data
        end_date: End date for data
        timeframe: '1d' or '1wk'
    
    Returns:
        DataFrame with OHLCV data or None
    """
    try:
        import yfinance as yf
        
        logger.debug(f"Fetching {symbol} with yfinance from {start_date} to {end_date}")
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start_date,
            end=end_date + timedelta(days=1),  # yfinance end is exclusive
            interval=timeframe
        )
        
        if df is None or df.empty:
            logger.warning(f"yfinance returned empty for {symbol}")
            return None
        
        # Keep only OHLCV
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        logger.info(f"yfinance fetched {len(df)} bars for {symbol}")
        return df
    
    except ImportError:
        logger.error("yfinance not installed")
        return None
    except Exception as e:
        logger.warning(f"yfinance fetch failed for {symbol}: {e}")
        return None


# ============================================================================
# UNIFIED FETCH WITH RETRY AND FALLBACK
# ============================================================================

def fetch_market_data(
    symbol: str,
    timeframe: str = '1d',
    lookback_days: Optional[int] = None,
    target_date: Optional[date] = None,
    use_cache: bool = True
) -> Tuple[Optional[pd.DataFrame], str]:
    """
    Fetch market data with retry, fallback, and caching.
    
    Args:
        symbol: Stock symbol with .NS/.BO suffix
        timeframe: '1d' or '1wk'
        lookback_days: Number of days to look back (default from config)
        target_date: For backtest mode, fetch data up to this date
        use_cache: Whether to use cached data
    
    Returns:
        Tuple of (DataFrame, source) where source is 'jugaad', 'yfinance', or 'cache'
    """
    if lookback_days is None:
        lookback_days = DATA_CONFIG['lookback_days']
    
    if target_date is None:
        target_date = date.today()
    
    start_date = target_date - timedelta(days=lookback_days)
    
    # Check cache first
    if use_cache:
        ttl = DATA_CONFIG['cache_ttl_daily'] if timeframe == '1d' else DATA_CONFIG['cache_ttl_weekly']
        cached_df = get_cached_data(symbol, timeframe, target_date, ttl)
        if cached_df is not None:
            return cached_df, 'cache'
    
    # Try jugaad-data with retries
    max_retries = DATA_CONFIG['max_retries']
    retry_delay = DATA_CONFIG['retry_delay']
    backoff = DATA_CONFIG['retry_backoff']
    
    for attempt in range(max_retries):
        df = fetch_with_jugaad(symbol, start_date, target_date, timeframe)
        if df is not None:
            cache_data(symbol, timeframe, target_date, df)
            return df, 'jugaad'
        
        if attempt < max_retries - 1:
            sleep_time = retry_delay * (backoff ** attempt)
            logger.debug(f"Retry {attempt + 1}/{max_retries} for {symbol} after {sleep_time}s")
            time.sleep(sleep_time)
    
    # Fallback to yfinance
    logger.info(f"Falling back to yfinance for {symbol}")
    for attempt in range(max_retries):
        df = fetch_with_yfinance(symbol, start_date, target_date, timeframe)
        if df is not None:
            cache_data(symbol, timeframe, target_date, df)
            return df, 'yfinance'
        
        if attempt < max_retries - 1:
            sleep_time = retry_delay * (backoff ** attempt)
            time.sleep(sleep_time)
    
    logger.error(f"All fetch attempts failed for {symbol}")
    return None, 'none'


def fetch_multiple_symbols(
    symbols: list,
    timeframe: str = '1d',
    target_date: Optional[date] = None
) -> Dict[str, Tuple[Optional[pd.DataFrame], str]]:
    """
    Fetch data for multiple symbols with rate limiting.
    
    Args:
        symbols: List of symbols to fetch
        timeframe: '1d' or '1wk'
        target_date: For backtest mode
    
    Returns:
        Dictionary mapping symbol to (DataFrame, source)
    """
    results = {}
    rate_limit = 1.0 / DATA_CONFIG['requests_per_second']
    
    for i, symbol in enumerate(symbols):
        if i > 0:
            time.sleep(rate_limit)
        
        df, source = fetch_market_data(symbol, timeframe, target_date=target_date)
        results[symbol] = (df, source)
        
        if df is not None:
            logger.info(f"[{i+1}/{len(symbols)}] Fetched {symbol} ({len(df)} bars, source: {source})")
        else:
            logger.warning(f"[{i+1}/{len(symbols)}] Failed to fetch {symbol}")
    
    return results


# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize cache database on import
try:
    init_cache_db()
except Exception as e:
    logger.warning(f"Could not initialize cache database: {e}")
