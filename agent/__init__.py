"""
Indian Stock Market Swing Trade Research Agent
Autonomous agent for detecting high-probability swing trade setups.
"""

__version__ = "1.0.0"
__author__ = "Quant Engineering Team"

from .universe import load_universe
from .data_fetcher import fetch_market_data
from .indicators import compute_indicators
from .setup_detector import detect_setups
from .evaluator import evaluate_setup
from .risk import calculate_risk_metrics
from .persister import persist_scan_results
from .notifier import send_notifications

__all__ = [
    "load_universe",
    "fetch_market_data",
    "compute_indicators",
    "detect_setups",
    "evaluate_setup",
    "calculate_risk_metrics",
    "persist_scan_results",
    "send_notifications",
]
