"""
Database schema and initialization for Indian Stock Market Swing Trade Agent
SQLite database for persisting scan results, setups, and evaluations.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from config import DB_PATH

logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE SCHEMA
# ============================================================================

SCHEMA_SQL = """
-- Agent run tracking
CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT UNIQUE NOT NULL,
    scan_timestamp DATETIME NOT NULL,
    scan_type TEXT NOT NULL,  -- 'live' or 'backtest'
    scan_date DATE,  -- For backtest mode
    universe_size INTEGER,
    stocks_fetched INTEGER,
    setups_detected INTEGER,
    setups_evaluated INTEGER,
    high_confidence_count INTEGER,
    duration_seconds REAL,
    status TEXT NOT NULL,  -- 'success', 'partial', 'failed'
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_timestamp 
    ON agent_runs(scan_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_scan_date 
    ON agent_runs(scan_date DESC);

-- Stock snapshots (OHLCV + indicators)
CREATE TABLE IF NOT EXISTS stock_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,  -- '1d' or '1wk'
    snapshot_date DATE NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    ema_20 REAL,
    ema_50 REAL,
    ema_200 REAL,
    rsi_14 REAL,
    macd REAL,
    macd_signal REAL,
    macd_histogram REAL,
    atr_14 REAL,
    volume_sma_20 REAL,
    volume_ratio REAL,
    bb_upper REAL,
    bb_middle REAL,
    bb_lower REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scan_id) REFERENCES agent_runs(scan_id),
    UNIQUE(scan_id, symbol, timeframe, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_date 
    ON stock_snapshots(symbol, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_scan_id 
    ON stock_snapshots(scan_id);

-- Detected trade setups (rule-based)
CREATE TABLE IF NOT EXISTS trade_setups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    setup_type TEXT NOT NULL,  -- 'BREAKOUT', 'PULLBACK', 'MOMENTUM', 'CONSOLIDATION'
    timeframe TEXT NOT NULL,
    detection_date DATE NOT NULL,
    current_price REAL NOT NULL,
    setup_score REAL,  -- 0-100 preliminary score
    trigger_price REAL,
    price_above_ema50 INTEGER,  -- Boolean as 0/1
    price_above_ema200 INTEGER,
    volume_spike INTEGER,
    rsi_in_range INTEGER,
    conditions_met TEXT,  -- JSON array of conditions
    raw_data TEXT,  -- JSON with full setup details
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scan_id) REFERENCES agent_runs(scan_id),
    UNIQUE(scan_id, symbol, setup_type)
);

CREATE INDEX IF NOT EXISTS idx_setups_symbol_date 
    ON trade_setups(symbol, detection_date DESC);
CREATE INDEX IF NOT EXISTS idx_setups_scan_id 
    ON trade_setups(scan_id);
CREATE INDEX IF NOT EXISTS idx_setups_score 
    ON trade_setups(setup_score DESC);

-- LLM evaluation results
CREATE TABLE IF NOT EXISTS evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT NOT NULL,
    setup_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    evaluation_timestamp DATETIME NOT NULL,
    setup_quality TEXT NOT NULL,  -- 'HIGH', 'MEDIUM', 'LOW'
    breakout_confirmation TEXT NOT NULL,  -- 'YES', 'NO'
    trend_strength TEXT NOT NULL,  -- 'STRONG', 'MODERATE', 'WEAK'
    confidence_score REAL,  -- 0-100
    reasoning TEXT,
    entry_range_low REAL,
    entry_range_high REAL,
    stop_loss REAL,
    target_1 REAL,
    target_2 REAL,
    risk_reward_ratio REAL,
    position_size INTEGER,
    position_value REAL,
    llm_response_raw TEXT,  -- Full JSON response
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scan_id) REFERENCES agent_runs(scan_id),
    FOREIGN KEY (setup_id) REFERENCES trade_setups(id),
    UNIQUE(scan_id, setup_id)
);

CREATE INDEX IF NOT EXISTS idx_evaluations_symbol 
    ON evaluation_results(symbol);
CREATE INDEX IF NOT EXISTS idx_evaluations_confidence 
    ON evaluation_results(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_evaluations_quality 
    ON evaluation_results(setup_quality);
CREATE INDEX IF NOT EXISTS idx_evaluations_timestamp 
    ON evaluation_results(evaluation_timestamp DESC);

-- Alert history
CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT NOT NULL,
    evaluation_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    alert_type TEXT NOT NULL,  -- 'webhook', 'telegram', 'email'
    confidence_score REAL,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    success INTEGER,  -- Boolean as 0/1
    error_message TEXT,
    FOREIGN KEY (scan_id) REFERENCES agent_runs(scan_id),
    FOREIGN KEY (evaluation_id) REFERENCES evaluation_results(id)
);

CREATE INDEX IF NOT EXISTS idx_alerts_symbol 
    ON alert_history(symbol, sent_at DESC);
"""


# ============================================================================
# DATABASE CONNECTION
# ============================================================================

@contextmanager
def get_db_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """
    Context manager for database connections.
    Ensures proper connection handling and cleanup.
    """
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_database(db_path: Path = DB_PATH) -> None:
    """
    Initialize the database with schema.
    Safe to call multiple times (CREATE IF NOT EXISTS).
    """
    try:
        with get_db_connection(db_path) as conn:
            conn.executescript(SCHEMA_SQL)
        logger.info(f"Database initialized successfully at {db_path}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_db_stats(db_path: Path = DB_PATH) -> dict:
    """
    Get database statistics.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        stats = {}
        tables = ['agent_runs', 'stock_snapshots', 'trade_setups', 
                  'evaluation_results', 'alert_history']
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]
        
        # Last scan info
        cursor.execute("""
            SELECT scan_timestamp, universe_size, setups_detected, high_confidence_count
            FROM agent_runs
            ORDER BY scan_timestamp DESC
            LIMIT 1
        """)
        last_scan = cursor.fetchone()
        if last_scan:
            stats['last_scan'] = dict(last_scan)
        
        return stats


def cleanup_old_data(days: int = 90, db_path: Path = DB_PATH) -> None:
    """
    Clean up data older than specified days.
    Useful for keeping database size manageable.
    """
    cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_date = cutoff_date.timestamp() - (days * 86400)
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Get old scan IDs
        cursor.execute("""
            SELECT scan_id FROM agent_runs
            WHERE scan_timestamp < datetime(?, 'unixepoch')
        """, (cutoff_date,))
        
        old_scan_ids = [row[0] for row in cursor.fetchall()]
        
        if not old_scan_ids:
            logger.info("No old data to clean up")
            return
        
        # Delete cascading data
        placeholders = ','.join(['?'] * len(old_scan_ids))
        
        for table in ['alert_history', 'evaluation_results', 
                      'trade_setups', 'stock_snapshots', 'agent_runs']:
            cursor.execute(
                f"DELETE FROM {table} WHERE scan_id IN ({placeholders})",
                old_scan_ids
            )
        
        deleted_count = len(old_scan_ids)
        logger.info(f"Cleaned up {deleted_count} old scan(s) and associated data")


# ============================================================================
# INITIALIZE ON IMPORT
# ============================================================================

# Auto-initialize database when module is imported
try:
    init_database()
except Exception as e:
    logger.warning(f"Could not auto-initialize database: {e}")
