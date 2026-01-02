"""
LangGraph Workflow Orchestration
Autonomous agent workflow for stock market scanning and trade setup detection.
"""

import logging
from typing import Dict, List, TypedDict, Annotated
from datetime import datetime, date
import uuid

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from agent.universe import load_universe
from agent.data_fetcher import fetch_multiple_symbols
from agent.indicators import compute_indicators, get_latest_indicators
from agent.setup_detector import detect_setups
from agent.evaluator import evaluate_multiple_setups
from agent.risk import calculate_risk_metrics
from agent.persister import persist_scan_results
from agent.notifier import send_notifications, log_summary

logger = logging.getLogger(__name__)


# ============================================================================
# STATE SCHEMA
# ============================================================================

class AgentState(TypedDict):
    """State passed between graph nodes."""
    
    # Identifiers
    scan_id: str
    scan_timestamp: datetime
    scan_type: str  # 'live' or 'backtest'
    scan_date: date  # For backtest mode
    
    # Data pipeline
    universe: List[str]
    market_data: Dict[str, tuple]  # symbol -> (dataframe, source)
    indicators: Dict[str, Dict]  # symbol -> indicator dict
    detected_setups: List[Dict]
    evaluated_setups: List[Dict]
    trade_candidates: List[Dict]
    
    # Metadata
    duration_seconds: float
    errors: List[str]
    metadata: Dict
    
    # Results
    persistence: Dict
    notifications: List[Dict]


# ============================================================================
# GRAPH NODES
# ============================================================================

def initialize_scan(state: AgentState) -> AgentState:
    """Initialize scan with ID and timestamp."""
    state['scan_id'] = f"scan_{uuid.uuid4().hex[:12]}"
    state['scan_timestamp'] = datetime.now()
    state['errors'] = []
    state['metadata'] = {}
    
    logger.info(f"Initialized scan: {state['scan_id']}")
    return state


def load_universe_node(state: AgentState) -> AgentState:
    """Load stock universe."""
    try:
        universe = load_universe()
        state['universe'] = universe
        logger.info(f"Loaded universe: {len(universe)} symbols")
    except Exception as e:
        logger.error(f"Error loading universe: {e}")
        state['errors'].append(f"Universe loading failed: {str(e)}")
        state['universe'] = []
    
    return state


def fetch_data_node(state: AgentState) -> AgentState:
    """Fetch market data for all symbols."""
    try:
        target_date = state.get('scan_date')
        
        logger.info(f"Fetching data for {len(state['universe'])} symbols...")
        market_data = fetch_multiple_symbols(
            symbols=state['universe'],
            timeframe='1d',
            target_date=target_date
        )
        
        # Filter out failed fetches
        successful_data = {
            symbol: (df, source)
            for symbol, (df, source) in market_data.items()
            if df is not None and not df.empty
        }
        
        state['market_data'] = successful_data
        
        failed = len(state['universe']) - len(successful_data)
        if failed > 0:
            logger.warning(f"Failed to fetch data for {failed} symbols")
        
        logger.info(f"Successfully fetched data for {len(successful_data)} symbols")
    
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        state['errors'].append(f"Data fetch failed: {str(e)}")
        state['market_data'] = {}
    
    return state


def compute_indicators_node(state: AgentState) -> AgentState:
    """Compute technical indicators."""
    try:
        indicators_dict = {}
        
        for symbol, (df, source) in state['market_data'].items():
            # Compute indicators on dataframe
            df_with_indicators = compute_indicators(df)
            
            # Extract latest values
            latest_indicators = get_latest_indicators(df_with_indicators)
            indicators_dict[symbol] = latest_indicators
            
            # Update dataframe in market_data
            state['market_data'][symbol] = (df_with_indicators, source)
        
        state['indicators'] = indicators_dict
        logger.info(f"Computed indicators for {len(indicators_dict)} symbols")
    
    except Exception as e:
        logger.error(f"Error computing indicators: {e}")
        state['errors'].append(f"Indicator computation failed: {str(e)}")
        state['indicators'] = {}
    
    return state


def detect_setups_node(state: AgentState) -> AgentState:
    """Detect trade setups using rule-based logic."""
    try:
        all_setups = []
        
        for symbol, (df, source) in state['market_data'].items():
            setups = detect_setups(symbol, df, timeframe='1d')
            all_setups.extend(setups)
        
        state['detected_setups'] = all_setups
        logger.info(f"Detected {len(all_setups)} total setups across all symbols")
    
    except Exception as e:
        logger.error(f"Error detecting setups: {e}")
        state['errors'].append(f"Setup detection failed: {str(e)}")
        state['detected_setups'] = []
    
    return state


def should_evaluate(state: AgentState) -> str:
    """
    Conditional routing: only evaluate if setups were detected.
    
    Returns:
        'evaluate' if setups found, 'skip' otherwise
    """
    if state['detected_setups']:
        logger.info(f"Proceeding to LLM evaluation for {len(state['detected_setups'])} setups")
        return 'evaluate'
    else:
        logger.info("No setups detected, skipping evaluation")
        return 'skip'


def evaluate_setups_node(state: AgentState) -> AgentState:
    """Evaluate setups using Ollama LLM."""
    try:
        # Group setups by symbol
        setups_by_symbol = {}
        for setup in state['detected_setups']:
            symbol = setup['symbol']
            if symbol not in setups_by_symbol:
                setups_by_symbol[symbol] = []
            setups_by_symbol[symbol].append(setup)
        
        # Extract dataframes for evaluation
        market_data_dfs = {
            symbol: df for symbol, (df, source) in state['market_data'].items()
        }
        
        # Evaluate
        evaluations = evaluate_multiple_setups(setups_by_symbol, market_data_dfs)
        
        state['evaluated_setups'] = evaluations
        logger.info(f"Completed LLM evaluation for {len(evaluations)} setups")
    
    except Exception as e:
        logger.error(f"Error evaluating setups: {e}")
        state['errors'].append(f"LLM evaluation failed: {str(e)}")
        state['evaluated_setups'] = []
    
    return state


def calculate_risk_node(state: AgentState) -> AgentState:
    """Calculate risk metrics for evaluated setups."""
    try:
        trade_candidates = []
        
        for evaluation in state['evaluated_setups']:
            symbol = evaluation['symbol']
            setup_type = evaluation['setup_type']
            
            # Find corresponding setup
            setup = None
            for s in state['detected_setups']:
                if s['symbol'] == symbol and s['setup_type'] == setup_type:
                    setup = s
                    break
            
            if not setup:
                logger.warning(f"No setup found for evaluation: {symbol} {setup_type}")
                continue
            
            # Get dataframe
            if symbol not in state['market_data']:
                logger.warning(f"No market data for {symbol}")
                continue
            
            df, _ = state['market_data'][symbol]
            
            # Calculate risk metrics
            risk_metrics = calculate_risk_metrics(
                symbol=symbol,
                setup=setup,
                evaluation=evaluation,
                df=df
            )
            
            # Merge all data
            candidate = {
                **setup,
                **evaluation,
                **risk_metrics,
            }
            
            trade_candidates.append(candidate)
        
        state['trade_candidates'] = trade_candidates
        logger.info(f"Calculated risk metrics for {len(trade_candidates)} candidates")
    
    except Exception as e:
        logger.error(f"Error calculating risk metrics: {e}")
        state['errors'].append(f"Risk calculation failed: {str(e)}")
        state['trade_candidates'] = []
    
    return state


def persist_data_node(state: AgentState) -> AgentState:
    """Persist scan results to database."""
    try:
        state = persist_scan_results(state)
    except Exception as e:
        logger.error(f"Error persisting data: {e}")
        state['errors'].append(f"Data persistence failed: {str(e)}")
    
    return state


def notify_node(state: AgentState) -> AgentState:
    """Send notifications for high-confidence setups."""
    try:
        state = send_notifications(state)
        log_summary(state)
    except Exception as e:
        logger.error(f"Error sending notifications: {e}")
        state['errors'].append(f"Notification failed: {str(e)}")
    
    return state


def skip_evaluation_node(state: AgentState) -> AgentState:
    """
    Skip evaluation path when no setups detected.
    Just log and pass through to persistence.
    """
    logger.info("Skipping evaluation and risk calculation (no setups detected)")
    state['evaluated_setups'] = []
    state['trade_candidates'] = []
    return state


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_agent_graph() -> StateGraph:
    """
    Create the LangGraph workflow.
    
    Workflow:
        START -> initialize -> universe -> fetcher -> indicators -> detector
              -> [conditional: if setups found]
                   YES -> evaluator -> risk -> persister -> notifier -> END
                   NO  -> skip_eval -> persister -> notifier -> END
    """
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("initialize", initialize_scan)
    workflow.add_node("universe", load_universe_node)
    workflow.add_node("fetcher", fetch_data_node)
    workflow.add_node("indicators", compute_indicators_node)
    workflow.add_node("detector", detect_setups_node)
    workflow.add_node("evaluator", evaluate_setups_node)
    workflow.add_node("risk", calculate_risk_node)
    workflow.add_node("skip_eval", skip_evaluation_node)
    workflow.add_node("persister", persist_data_node)
    workflow.add_node("notifier", notify_node)
    
    # Define edges
    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "universe")
    workflow.add_edge("universe", "fetcher")
    workflow.add_edge("fetcher", "indicators")
    workflow.add_edge("indicators", "detector")
    
    # Conditional routing after detection
    workflow.add_conditional_edges(
        "detector",
        should_evaluate,
        {
            "evaluate": "evaluator",
            "skip": "skip_eval"
        }
    )
    
    # Evaluation path
    workflow.add_edge("evaluator", "risk")
    workflow.add_edge("risk", "persister")
    
    # Skip path
    workflow.add_edge("skip_eval", "persister")
    
    # Final steps
    workflow.add_edge("persister", "notifier")
    workflow.add_edge("notifier", END)
    
    return workflow


def compile_graph():
    """Compile the graph for execution."""
    workflow = create_agent_graph()
    return workflow.compile()


# ============================================================================
# EXECUTION
# ============================================================================

def run_scan(scan_type: str = 'live', scan_date: date = None) -> Dict:
    """
    Execute a complete scan.
    
    Args:
        scan_type: 'live' or 'backtest'
        scan_date: Target date for backtest mode
    
    Returns:
        Final state dict
    """
    start_time = datetime.now()
    
    # Compile graph
    graph = compile_graph()
    
    # Initial state
    initial_state = {
        'scan_type': scan_type,
        'scan_date': scan_date,
    }
    
    # Run graph
    logger.info("Starting agent workflow...")
    final_state = graph.invoke(initial_state)
    
    # Calculate duration
    duration = (datetime.now() - start_time).total_seconds()
    final_state['duration_seconds'] = duration
    
    logger.info(f"✓ Agent workflow completed in {duration:.2f} seconds")
    
    return final_state
