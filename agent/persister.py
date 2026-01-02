"""
Data Persister
Saves scan results, setups, and evaluations to SQLite database.
"""

import logging
import json
import sqlite3
from datetime import datetime, date
from typing import Dict, List, Optional
from contextlib import contextmanager

from config import DB_PATH
from db import get_db_connection

logger = logging.getLogger(__name__)


def persist_scan_results(state: Dict) -> Dict:
    """
    Persist complete scan results to database.
    
    Args:
        state: LangGraph state containing all scan data
    
    Returns:
        Updated state with persistence status
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # ================================================================
            # 1. INSERT AGENT RUN
            # ================================================================
            
            run_data = {
                'scan_id': state['scan_id'],
                'scan_timestamp': state['scan_timestamp'],
                'scan_type': state.get('scan_type', 'live'),
                'scan_date': state.get('scan_date'),
                'universe_size': len(state.get('universe', [])),
                'stocks_fetched': len(state.get('market_data', {})),
                'setups_detected': len(state.get('detected_setups', [])),
                'setups_evaluated': len(state.get('evaluated_setups', [])),
                'high_confidence_count': sum(
                    1 for e in state.get('evaluated_setups', [])
                    if e.get('confidence_score', 0) >= 80
                ),
                'duration_seconds': state.get('duration_seconds', 0),
                'status': 'success' if not state.get('errors') else 'partial',
                'error_message': json.dumps(state.get('errors', [])) if state.get('errors') else None,
            }
            
            cursor.execute("""
                INSERT INTO agent_runs (
                    scan_id, scan_timestamp, scan_type, scan_date,
                    universe_size, stocks_fetched, setups_detected,
                    setups_evaluated, high_confidence_count,
                    duration_seconds, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_data['scan_id'],
                run_data['scan_timestamp'],
                run_data['scan_type'],
                run_data['scan_date'],
                run_data['universe_size'],
                run_data['stocks_fetched'],
                run_data['setups_detected'],
                run_data['setups_evaluated'],
                run_data['high_confidence_count'],
                run_data['duration_seconds'],
                run_data['status'],
                run_data['error_message'],
            ))
            
            logger.info(f"Persisted agent run: {state['scan_id']}")
            
            # ================================================================
            # 2. INSERT STOCK SNAPSHOTS
            # ================================================================
            
            snapshots_count = 0
            for symbol, snapshot_data in state.get('indicators', {}).items():
                if not snapshot_data:
                    continue
                
                cursor.execute("""
                    INSERT OR IGNORE INTO stock_snapshots (
                        scan_id, symbol, timeframe, snapshot_date,
                        open, high, low, close, volume,
                        ema_20, ema_50, ema_200,
                        rsi_14, macd, macd_signal, macd_histogram,
                        atr_14, volume_sma_20, volume_ratio,
                        bb_upper, bb_middle, bb_lower
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    state['scan_id'],
                    symbol,
                    '1d',
                    state.get('scan_date', date.today()),
                    snapshot_data.get('open', 0),
                    snapshot_data.get('high', 0),
                    snapshot_data.get('low', 0),
                    snapshot_data.get('close', 0),
                    snapshot_data.get('volume', 0),
                    snapshot_data.get('ema_20', 0),
                    snapshot_data.get('ema_50', 0),
                    snapshot_data.get('ema_200', 0),
                    snapshot_data.get('rsi_14', 0),
                    snapshot_data.get('macd', 0),
                    snapshot_data.get('macd_signal', 0),
                    snapshot_data.get('macd_histogram', 0),
                    snapshot_data.get('atr_14', 0),
                    snapshot_data.get('volume_sma_20', 0),
                    snapshot_data.get('volume_ratio', 0),
                    snapshot_data.get('bb_upper', 0),
                    snapshot_data.get('bb_mid', 0),
                    snapshot_data.get('bb_lower', 0),
                ))
                snapshots_count += 1
            
            logger.info(f"Persisted {snapshots_count} stock snapshots")
            
            # ================================================================
            # 3. INSERT TRADE SETUPS
            # ================================================================
            
            setup_id_map = {}
            for setup in state.get('detected_setups', []):
                cursor.execute("""
                    INSERT OR IGNORE INTO trade_setups (
                        scan_id, symbol, setup_type, timeframe, detection_date,
                        current_price, setup_score, trigger_price,
                        price_above_ema50, price_above_ema200, volume_spike,
                        rsi_in_range, conditions_met, raw_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    state['scan_id'],
                    setup['symbol'],
                    setup['setup_type'],
                    setup.get('timeframe', '1d'),
                    setup.get('detection_date', date.today()),
                    setup.get('current_price', 0),
                    setup.get('setup_score', 0),
                    setup.get('trigger_price'),
                    1,  # price_above_ema50 (assumed true if setup detected)
                    1,  # price_above_ema200
                    1,  # volume_spike
                    1,  # rsi_in_range
                    json.dumps(setup.get('conditions_met', [])),
                    json.dumps(setup, default=str),
                ))
                
                # Get the inserted ID
                setup_id = cursor.lastrowid
                key = f"{setup['symbol']}_{setup['setup_type']}"
                setup_id_map[key] = setup_id
            
            logger.info(f"Persisted {len(state.get('detected_setups', []))} trade setups")
            
            # ================================================================
            # 4. INSERT EVALUATION RESULTS
            # ================================================================
            
            evaluation_ids = []
            for eval_data in state.get('evaluated_setups', []):
                symbol = eval_data['symbol']
                setup_type = eval_data['setup_type']
                key = f"{symbol}_{setup_type}"
                
                setup_id = setup_id_map.get(key)
                if not setup_id:
                    logger.warning(f"No setup_id found for {key}")
                    continue
                
                # Get corresponding risk metrics
                risk_metrics = None
                for candidate in state.get('trade_candidates', []):
                    if candidate['symbol'] == symbol and candidate.get('setup_type') == setup_type:
                        risk_metrics = candidate
                        break
                
                cursor.execute("""
                    INSERT OR IGNORE INTO evaluation_results (
                        scan_id, setup_id, symbol, evaluation_timestamp,
                        setup_quality, breakout_confirmation, trend_strength,
                        confidence_score, reasoning,
                        entry_range_low, entry_range_high, stop_loss,
                        target_1, target_2, risk_reward_ratio,
                        position_size, position_value, llm_response_raw
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    state['scan_id'],
                    setup_id,
                    symbol,
                    datetime.now(),
                    eval_data.get('setup_quality', 'UNKNOWN'),
                    eval_data.get('breakout_confirmation', 'NO'),
                    eval_data.get('trend_strength', 'UNKNOWN'),
                    eval_data.get('confidence_score', 0),
                    eval_data.get('reasoning', ''),
                    risk_metrics.get('entry_range_low') if risk_metrics else None,
                    risk_metrics.get('entry_range_high') if risk_metrics else None,
                    risk_metrics.get('stop_loss') if risk_metrics else None,
                    risk_metrics.get('target_1') if risk_metrics else None,
                    risk_metrics.get('target_2') if risk_metrics else None,
                    risk_metrics.get('risk_reward_ratio') if risk_metrics else None,
                    risk_metrics.get('position_size') if risk_metrics else None,
                    risk_metrics.get('position_value') if risk_metrics else None,
                    eval_data.get('llm_response_raw', ''),
                ))
                
                evaluation_ids.append(cursor.lastrowid)
            
            logger.info(f"Persisted {len(evaluation_ids)} evaluation results")
            
            # Update state with persistence info
            state['persistence'] = {
                'success': True,
                'run_id': cursor.lastrowid,
                'snapshots_saved': snapshots_count,
                'setups_saved': len(setup_id_map),
                'evaluations_saved': len(evaluation_ids),
            }
            
            conn.commit()
            logger.info("✓ All scan results persisted successfully")
            
            return state
    
    except Exception as e:
        logger.error(f"Error persisting scan results: {e}")
        state['errors'] = state.get('errors', [])
        state['errors'].append(f"Persistence error: {str(e)}")
        state['persistence'] = {'success': False, 'error': str(e)}
        return state


def save_alert_history(
    scan_id: str,
    evaluation_id: int,
    symbol: str,
    alert_type: str,
    confidence_score: float,
    success: bool,
    error_message: Optional[str] = None
) -> None:
    """
    Save alert delivery history.
    
    Args:
        scan_id: Scan identifier
        evaluation_id: Evaluation record ID
        symbol: Stock symbol
        alert_type: 'webhook', 'telegram', or 'email'
        confidence_score: Confidence score of the setup
        success: Whether alert was sent successfully
        error_message: Error message if failed
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO alert_history (
                    scan_id, evaluation_id, symbol, alert_type,
                    confidence_score, success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                scan_id,
                evaluation_id,
                symbol,
                alert_type,
                confidence_score,
                1 if success else 0,
                error_message,
            ))
            
            conn.commit()
            logger.debug(f"Saved alert history for {symbol} ({alert_type})")
    
    except Exception as e:
        logger.error(f"Error saving alert history: {e}")


def get_recent_scans(limit: int = 10) -> List[Dict]:
    """
    Retrieve recent scan results.
    
    Args:
        limit: Number of recent scans to retrieve
    
    Returns:
        List of scan result dicts
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    scan_id, scan_timestamp, scan_type, scan_date,
                    universe_size, stocks_fetched, setups_detected,
                    setups_evaluated, high_confidence_count,
                    duration_seconds, status
                FROM agent_runs
                ORDER BY scan_timestamp DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    except Exception as e:
        logger.error(f"Error retrieving recent scans: {e}")
        return []


def get_high_confidence_setups(
    min_confidence: float = 80,
    days: int = 7
) -> List[Dict]:
    """
    Retrieve high-confidence setups from recent scans.
    
    Args:
        min_confidence: Minimum confidence score
        days: Look back this many days
    
    Returns:
        List of setup dicts
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    e.symbol, e.setup_quality, e.confidence_score,
                    e.entry_range_low, e.entry_range_high,
                    e.stop_loss, e.target_1, e.target_2,
                    e.risk_reward_ratio, e.reasoning,
                    ar.scan_timestamp
                FROM evaluation_results e
                JOIN agent_runs ar ON e.scan_id = ar.scan_id
                WHERE e.confidence_score >= ?
                AND ar.scan_timestamp >= datetime('now', ? || ' days')
                ORDER BY e.confidence_score DESC, ar.scan_timestamp DESC
            """, (min_confidence, -days))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    except Exception as e:
        logger.error(f"Error retrieving high-confidence setups: {e}")
        return []
