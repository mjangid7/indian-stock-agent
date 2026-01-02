"""
LLM Evaluator
Uses Ollama to evaluate detected setups qualitatively.
Returns structured JSON output with setup quality assessment.
"""

import logging
import json
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
import pandas as pd

from config import OLLAMA_CONFIG

logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC MODELS FOR STRUCTURED OUTPUT
# ============================================================================

class SetupEvaluation(BaseModel):
    """Structured output from LLM evaluation."""
    
    setup_quality: str = Field(
        ...,
        description="Overall setup quality: HIGH, MEDIUM, or LOW",
        pattern="^(HIGH|MEDIUM|LOW)$"
    )
    
    breakout_confirmation: str = Field(
        ...,
        description="Is breakout confirmed: YES or NO",
        pattern="^(YES|NO)$"
    )
    
    trend_strength: str = Field(
        ...,
        description="Trend strength: STRONG, MODERATE, or WEAK",
        pattern="^(STRONG|MODERATE|WEAK)$"
    )
    
    confidence_score: float = Field(
        ...,
        description="Confidence score from 0 to 100",
        ge=0,
        le=100
    )
    
    reasoning: str = Field(
        ...,
        description="Brief explanation (2-3 sentences) of the evaluation",
        max_length=500
    )


# ============================================================================
# LLM PROMPT CONSTRUCTION
# ============================================================================

def build_evaluation_prompt(
    symbol: str,
    setup: Dict,
    indicators: Dict,
    recent_bars: pd.DataFrame
) -> str:
    """
    Build detailed prompt for LLM evaluation.
    
    Args:
        symbol: Stock symbol
        setup: Detected setup dict from setup_detector
        indicators: Latest indicator values
        recent_bars: Last 20 bars of price data
    
    Returns:
        Formatted prompt string
    """
    # Format recent price action
    recent_data = []
    for idx, row in recent_bars.tail(10).iterrows():
        date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
        recent_data.append(
            f"{date_str}: O:{row['Open']:.2f} H:{row['High']:.2f} "
            f"L:{row['Low']:.2f} C:{row['Close']:.2f} V:{int(row['Volume']):,}"
        )
    
    recent_price_action = "\n".join(recent_data)
    
    prompt = f"""You are a senior technical analyst evaluating a swing trade setup for {symbol} (Indian stock, NSE).

SETUP TYPE: {setup['setup_type']}
CURRENT PRICE: ₹{setup['current_price']:.2f}
TIMEFRAME: {setup['timeframe']}

TECHNICAL INDICATORS (Latest):
- EMA 20: ₹{indicators.get('ema_20', 0):.2f}
- EMA 50: ₹{indicators.get('ema_50', 0):.2f}
- EMA 200: ₹{indicators.get('ema_200', 0):.2f}
- RSI(14): {indicators.get('rsi_14', 0):.2f}
- MACD: {indicators.get('macd', 0):.2f}
- MACD Signal: {indicators.get('macd_signal', 0):.2f}
- MACD Histogram: {indicators.get('macd_histogram', 0):.2f}
- ATR(14): ₹{indicators.get('atr_14', 0):.2f} ({indicators.get('atr_percent', 0):.2f}%)
- Volume Ratio: {indicators.get('volume_ratio', 0):.2f}x average

SETUP DETAILS:
{json.dumps(setup, indent=2, default=str)}

RECENT PRICE ACTION (Last 10 bars):
{recent_price_action}

EVALUATION TASK:
Analyze this swing trade setup and provide your assessment in the following JSON format:

{{
  "setup_quality": "HIGH|MEDIUM|LOW",
  "breakout_confirmation": "YES|NO",
  "trend_strength": "STRONG|MODERATE|WEAK",
  "confidence_score": <0-100>,
  "reasoning": "<2-3 sentence explanation>"
}}

Consider:
1. Is the breakout/setup genuine with volume confirmation?
2. Are EMAs aligned properly for uptrend continuation?
3. Is RSI in healthy zone (not overbought/oversold)?
4. Is MACD supporting the move?
5. Does recent price action show strength?
6. What is the overall risk-reward potential?

Respond ONLY with the JSON object, no additional text."""
    
    return prompt


# ============================================================================
# OLLAMA CLIENT
# ============================================================================

def call_ollama(prompt: str) -> Optional[str]:
    """
    Call Ollama API with the evaluation prompt.
    
    Args:
        prompt: Formatted prompt string
    
    Returns:
        Raw response text or None on error
    """
    try:
        import ollama
        
        response = ollama.chat(
            model=OLLAMA_CONFIG['model'],
            messages=[{
                'role': 'user',
                'content': prompt
            }],
            format=SetupEvaluation.model_json_schema(),
            options={
                'temperature': OLLAMA_CONFIG['temperature'],
                'num_ctx': OLLAMA_CONFIG['num_ctx'],
            }
        )
        
        if response and 'message' in response:
            content = response['message']['content']
            logger.debug(f"Ollama response received: {len(content)} chars")
            return content
        
        logger.error("Ollama response missing content")
        return None
    
    except ImportError:
        logger.error("ollama package not installed. Run: pip install ollama")
        return None
    except Exception as e:
        logger.error(f"Ollama API error: {e}")
        return None


def parse_llm_response(response_text: str) -> Optional[SetupEvaluation]:
    """
    Parse and validate LLM response using Pydantic.
    
    Args:
        response_text: Raw JSON response from LLM
    
    Returns:
        SetupEvaluation object or None
    """
    try:
        # Try to parse JSON
        response_json = json.loads(response_text)
        
        # Validate with Pydantic
        evaluation = SetupEvaluation(**response_json)
        
        logger.debug(f"Parsed evaluation: {evaluation.setup_quality} quality, "
                    f"{evaluation.confidence_score}% confidence")
        return evaluation
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.debug(f"Raw response: {response_text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Failed to validate LLM response: {e}")
        return None


# ============================================================================
# MAIN EVALUATION FUNCTION
# ============================================================================

def evaluate_setup(
    symbol: str,
    setup: Dict,
    df: pd.DataFrame
) -> Optional[Dict]:
    """
    Evaluate a detected setup using Ollama LLM.
    
    Args:
        symbol: Stock symbol
        setup: Setup dict from setup_detector
        df: Full DataFrame with indicators
    
    Returns:
        Evaluation result dict or None
    """
    try:
        # Get latest indicators
        from agent.indicators import get_latest_indicators
        indicators = get_latest_indicators(df)
        
        # Get recent bars for context
        recent_bars = df.tail(20)
        
        # Build prompt
        prompt = build_evaluation_prompt(symbol, setup, indicators, recent_bars)
        
        # Call Ollama
        logger.info(f"Evaluating {symbol} {setup['setup_type']} setup with Ollama...")
        response_text = call_ollama(prompt)
        
        if not response_text:
            logger.error(f"No response from Ollama for {symbol}")
            return None
        
        # Parse response
        evaluation = parse_llm_response(response_text)
        
        if not evaluation:
            logger.error(f"Failed to parse evaluation for {symbol}")
            return None
        
        # Convert to dict and add metadata
        result = {
            'symbol': symbol,
            'setup_type': setup['setup_type'],
            'setup_quality': evaluation.setup_quality,
            'breakout_confirmation': evaluation.breakout_confirmation,
            'trend_strength': evaluation.trend_strength,
            'confidence_score': evaluation.confidence_score,
            'reasoning': evaluation.reasoning,
            'llm_model': OLLAMA_CONFIG['model'],
            'llm_response_raw': response_text,
        }
        
        logger.info(f"{symbol}: LLM Evaluation - {evaluation.setup_quality} quality, "
                   f"{evaluation.confidence_score:.0f}% confidence")
        
        return result
    
    except Exception as e:
        logger.error(f"Error evaluating {symbol}: {e}")
        return None


def evaluate_multiple_setups(
    setups_by_symbol: Dict[str, List[Dict]],
    market_data: Dict[str, pd.DataFrame]
) -> List[Dict]:
    """
    Evaluate multiple setups in batch.
    
    Args:
        setups_by_symbol: Dict mapping symbol to list of setups
        market_data: Dict mapping symbol to DataFrame
    
    Returns:
        List of evaluation results
    """
    all_evaluations = []
    
    for symbol, setups in setups_by_symbol.items():
        if symbol not in market_data:
            logger.warning(f"No market data for {symbol}, skipping evaluation")
            continue
        
        df = market_data[symbol]
        
        for setup in setups:
            evaluation = evaluate_setup(symbol, setup, df)
            if evaluation:
                all_evaluations.append(evaluation)
    
    return all_evaluations


# ============================================================================
# OLLAMA CONNECTIVITY CHECK
# ============================================================================

def check_ollama_connection() -> bool:
    """
    Check if Ollama is running and model is available.
    
    Returns:
        True if connected, False otherwise
    """
    try:
        import ollama
        
        # List available models
        models = ollama.list()
        
        if not models or not hasattr(models, 'models'):
            logger.error("Ollama is running but no models found")
            return False
        
        # Check if our model is available
        model_names = [m.model for m in models.models]
        target_model = OLLAMA_CONFIG['model']
        
        if not any(target_model in name for name in model_names):
            logger.error(f"Model '{target_model}' not found. Available: {model_names}")
            logger.info(f"Run: ollama pull {target_model}")
            return False
        
        logger.info(f"Ollama connection OK - {target_model} available")
        return True
    
    except ImportError:
        logger.error("ollama package not installed")
        return False
    except Exception as e:
        logger.error(f"Ollama connection failed: {e}")
        logger.info("Make sure Ollama is running: ollama serve")
        return False
