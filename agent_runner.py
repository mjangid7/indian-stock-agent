"""
Agent Runner - Main Entrypoint
Executes the autonomous stock market research agent.
"""

import logging
import sys
import argparse
from datetime import datetime, time as dt_time, date
from pathlib import Path
import pytz

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    LOGGING_CONFIG, MARKET_OPEN_TIME, MARKET_CLOSE_TIME, 
    MARKET_DAYS, LOG_DIR
)
from agent.evaluator import check_ollama_connection
from graph import run_scan
from db import init_database, get_db_stats


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, LOGGING_CONFIG['level']),
        format=LOGGING_CONFIG['format'],
        handlers=[
            logging.FileHandler(LOGGING_CONFIG['log_file']),
            logging.StreamHandler(sys.stdout)
        ]
    )


logger = logging.getLogger(__name__)


# ============================================================================
# MARKET HOURS CHECK
# ============================================================================

def is_market_hours() -> bool:
    """
    Check if current time is within NSE trading hours (IST).
    
    Returns:
        True if within market hours, False otherwise
    """
    # Get current time in IST
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    
    # Check day of week (0=Monday, 6=Sunday)
    if now_ist.weekday() not in MARKET_DAYS:
        logger.info(f"Outside market days (current: {now_ist.strftime('%A')})")
        return False
    
    # Check time
    current_time = now_ist.time()
    
    if MARKET_OPEN_TIME <= current_time <= MARKET_CLOSE_TIME:
        logger.info(f"Within market hours (IST: {now_ist.strftime('%H:%M:%S')})")
        return True
    else:
        logger.info(f"Outside market hours (IST: {now_ist.strftime('%H:%M:%S')})")
        return False


# ============================================================================
# VALIDATION
# ============================================================================

def validate_environment() -> bool:
    """
    Validate that all prerequisites are met.
    
    Returns:
        True if valid, False otherwise
    """
    logger.info("Validating environment...")
    
    # Check Ollama connection
    if not check_ollama_connection():
        logger.error("❌ Ollama validation failed")
        logger.info("Make sure Ollama is running: ollama serve")
        logger.info("And model is pulled: ollama pull llama3.1:8b")
        return False
    
    logger.info("✓ Ollama connection OK")
    
    # Check database
    try:
        init_database()
        stats = get_db_stats()
        logger.info(f"✓ Database OK - {stats.get('agent_runs', 0)} previous scans")
    except Exception as e:
        logger.error(f"❌ Database validation failed: {e}")
        return False
    
    # Check log directory
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"✓ Created log directory: {LOG_DIR}")
    
    logger.info("✓ Environment validation passed")
    return True


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Indian Stock Market Swing Trade Research Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run live scan (checks market hours)
  python agent_runner.py
  
  # Run backtest for a specific date
  python agent_runner.py --backtest 2025-12-15
  
  # Force run outside market hours
  python agent_runner.py --force
"""
    )
    
    parser.add_argument(
        '--backtest',
        type=str,
        metavar='YYYY-MM-DD',
        help='Run backtest for specific date (skips market hours check)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force run even outside market hours'
    )
    
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip environment validation (not recommended)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    logger.info("="*70)
    logger.info("INDIAN STOCK MARKET SWING TRADE RESEARCH AGENT")
    logger.info("="*70)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Validate environment
    if not args.skip_validation:
        if not validate_environment():
            logger.error("Environment validation failed. Exiting.")
            sys.exit(1)
    
    # Determine scan type and date
    if args.backtest:
        try:
            scan_date = datetime.strptime(args.backtest, '%Y-%m-%d').date()
            scan_type = 'backtest'
            logger.info(f"Running in BACKTEST mode for date: {scan_date}")
        except ValueError:
            logger.error(f"Invalid date format: {args.backtest}. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        scan_date = None
        scan_type = 'live'
        logger.info("Running in LIVE mode")
        
        # Check market hours (unless forced or backtest)
        if not args.force:
            if not is_market_hours():
                logger.info("Outside market hours. Use --force to run anyway.")
                logger.info("Exiting gracefully.")
                sys.exit(0)
    
    # Run the agent
    try:
        logger.info("Starting agent scan...")
        final_state = run_scan(scan_type=scan_type, scan_date=scan_date)
        
        # Check for errors
        if final_state.get('errors'):
            logger.warning(f"Scan completed with {len(final_state['errors'])} errors")
            for error in final_state['errors']:
                logger.error(f"  • {error}")
        else:
            logger.info("✓ Scan completed successfully with no errors")
        
        # Print summary
        logger.info("="*70)
        logger.info("RESULTS SUMMARY")
        logger.info("="*70)
        logger.info(f"Scan ID: {final_state.get('scan_id', 'N/A')}")
        logger.info(f"Duration: {final_state.get('duration_seconds', 0):.2f} seconds")
        logger.info(f"Stocks Scanned: {len(final_state.get('universe', []))}")
        logger.info(f"Data Fetched: {len(final_state.get('market_data', {}))}")
        logger.info(f"Setups Detected: {len(final_state.get('detected_setups', []))}")
        logger.info(f"Setups Evaluated: {len(final_state.get('evaluated_setups', []))}")
        logger.info(f"Trade Candidates: {len(final_state.get('trade_candidates', []))}")
        
        # High confidence setups
        high_conf = sum(
            1 for c in final_state.get('trade_candidates', [])
            if c.get('confidence_score', 0) >= 80
        )
        logger.info(f"High Confidence (≥80%): {high_conf}")
        
        if final_state.get('persistence', {}).get('success'):
            logger.info("✓ Results saved to database")
        
        if final_state.get('notifications'):
            logger.info(f"✓ Sent {len(final_state['notifications'])} alerts")
        
        logger.info("="*70)
        logger.info(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*70)
        
        sys.exit(0)
    
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
