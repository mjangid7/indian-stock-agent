"""
Configuration for Indian Stock Market Swing Trade Research Agent
All runtime constants and settings are defined here.
"""

from typing import List, Dict, Any
from datetime import time
from pathlib import Path

# ============================================================================
# PROJECT PATHS
# ============================================================================

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "trade_agent.db"
LOG_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / ".cache"

# Create directories if they don't exist
LOG_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# ============================================================================
# MARKET CONFIGURATION
# ============================================================================

# NSE trading hours (IST)
MARKET_OPEN_TIME = time(9, 15)  # 9:15 AM
MARKET_CLOSE_TIME = time(15, 30)  # 3:30 PM

# Market days (0=Monday, 6=Sunday)
MARKET_DAYS = [0, 1, 2, 3, 4]  # Monday to Friday

# ============================================================================
# STOCK UNIVERSE
# ============================================================================

# NIFTY 50 stocks (NSE symbols)
NIFTY_50 = [
    "ADANIPORTS", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE",
    "BAJAJFINSV", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA",
    "COALINDIA", "DIVISLAB", "DRREDDY", "EICHERMOT", "GRASIM",
    "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO",
    "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY",
    "JSWSTEEL", "KOTAKBANK", "LT", "M&M", "MARUTI",
    "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE",
    "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS",
    "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN",
    "TRENT", "ULTRACEMCO", "WIPRO", "APOLLOHOSP", "ADANIENT"
]

# Add .NS suffix for NSE
NIFTY_50_NSE = [f"{symbol}.NS" for symbol in NIFTY_50]

# Default universe to scan
DEFAULT_UNIVERSE = NIFTY_50_NSE

# ============================================================================
# TECHNICAL INDICATOR PARAMETERS
# ============================================================================

INDICATORS = {
    "ema_short": 20,
    "ema_medium": 50,
    "ema_long": 200,
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_period": 14,
    "volume_sma": 20,
    "bollinger_period": 20,
    "bollinger_std": 2,
}

# ============================================================================
# SETUP DETECTION RULES
# ============================================================================

SETUP_RULES = {
    # Price must be above these EMAs
    "price_above_ema": [50, 200],
    
    # Volume spike threshold (e.g., 1.5 = 150% of average)
    "volume_spike_multiplier": 1.5,
    
    # RSI range for momentum setups
    "rsi_min": 55,
    "rsi_max": 70,
    
    # Minimum ATR (volatility filter)
    "min_atr_percent": 1.0,  # 1% of price
    
    # Breakout detection (lookback periods)
    "breakout_lookback": 20,
    
    # Pullback to EMA tolerance
    "pullback_tolerance_percent": 2.0,
    
    # Consolidation detection (price range compression)
    "consolidation_range_percent": 5.0,
    "consolidation_periods": 10,
    
    # Higher high / higher low structure
    "momentum_bars": 3,
}

# ============================================================================
# RISK MANAGEMENT
# ============================================================================

RISK_CONFIG = {
    # Default account size (for position sizing calculations)
    "default_account_size": 1000000,  # 10 lakhs
    
    # Risk per trade (% of account)
    "risk_per_trade_percent": 2.0,
    
    # Maximum position size (% of account)
    "max_position_percent": 20.0,
    
    # Stop loss calculation
    "stop_loss_atr_multiplier": 2.0,
    "stop_loss_min_percent": 2.0,  # Minimum 2% stop
    "stop_loss_max_percent": 8.0,  # Maximum 8% stop
    
    # Target calculation (R:R ratios)
    "target_ratios": [2.0, 3.0],  # 1:2 and 1:3 R:R
    
    # Entry range (% around current price)
    "entry_range_percent": 1.0,
}

# ============================================================================
# OLLAMA CONFIGURATION
# ============================================================================

OLLAMA_CONFIG = {
    "model": "llama3.1:8b",
    "base_url": "http://localhost:11434",
    "timeout": 60,  # seconds
    "temperature": 0,  # Deterministic output
    "num_ctx": 4096,  # Context window
}

# ============================================================================
# DATA FETCHING
# ============================================================================

DATA_CONFIG = {
    # Timeframes to fetch
    "timeframes": ["1d", "1wk"],
    
    # Lookback period for historical data
    "lookback_days": 365,
    
    # Cache TTL (time to live) in seconds
    "cache_ttl_daily": 86400,  # 24 hours
    "cache_ttl_weekly": 604800,  # 7 days
    
    # Retry configuration
    "max_retries": 3,
    "retry_delay": 2,  # seconds
    "retry_backoff": 2,  # exponential backoff multiplier
    
    # Rate limiting
    "requests_per_second": 2,
}

# ============================================================================
# ALERT CONFIGURATION
# ============================================================================

ALERT_CONFIG = {
    # Confidence threshold for alerts
    "min_confidence_for_alert": 80,  # percentage
    
    # Webhook URL (set to None to disable)
    "webhook_url": None,  # e.g., "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    
    # Telegram configuration (set to None to disable)
    "telegram_bot_token": None,  # Get from @BotFather
    "telegram_chat_id": None,  # Your chat ID
    
    # Email configuration (set to None to disable)
    "email_enabled": False,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": None,
    "smtp_password": None,
    "email_from": None,
    "email_to": [],
}

# ============================================================================
# LOGGING
# ============================================================================

LOGGING_CONFIG = {
    "level": "INFO",  # DEBUG, INFO, WARNING, ERROR
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": LOG_DIR / "agent.log",
    "max_bytes": 10485760,  # 10MB
    "backup_count": 5,
}

# ============================================================================
# LANGGRAPH STATE SCHEMA
# ============================================================================

# Define what gets passed between nodes
STATE_KEYS = [
    "scan_id",
    "scan_timestamp",
    "universe",
    "market_data",
    "indicators",
    "detected_setups",
    "evaluated_setups",
    "trade_candidates",
    "errors",
    "metadata",
]
