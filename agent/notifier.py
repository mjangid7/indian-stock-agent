"""
Notification System
Sends alerts for high-confidence trade setups via webhook/Telegram/email.
"""

import logging
import json
from typing import Dict, List, Optional
import requests
from datetime import datetime

from config import ALERT_CONFIG
from agent.persister import save_alert_history

logger = logging.getLogger(__name__)


def send_notifications(state: Dict) -> Dict:
    """
    Send notifications for high-confidence setups.
    
    Args:
        state: LangGraph state with trade candidates
    
    Returns:
        Updated state with notification status
    """
    trade_candidates = state.get('trade_candidates', [])
    
    if not trade_candidates:
        logger.info("No trade candidates to notify")
        return state
    
    # Filter high-confidence setups
    high_confidence = [
        c for c in trade_candidates
        if c.get('confidence_score', 0) >= ALERT_CONFIG['min_confidence_for_alert']
    ]
    
    if not high_confidence:
        logger.info(f"No setups above {ALERT_CONFIG['min_confidence_for_alert']}% confidence threshold")
        return state
    
    logger.info(f"Sending alerts for {len(high_confidence)} high-confidence setup(s)")
    
    notification_results = []
    
    for candidate in high_confidence:
        # Send via webhook
        if ALERT_CONFIG['webhook_url']:
            success = send_webhook_alert(candidate, state['scan_id'])
            notification_results.append({
                'symbol': candidate['symbol'],
                'type': 'webhook',
                'success': success
            })
        
        # Send via Telegram
        if ALERT_CONFIG['telegram_bot_token'] and ALERT_CONFIG['telegram_chat_id']:
            success = send_telegram_alert(candidate, state['scan_id'])
            notification_results.append({
                'symbol': candidate['symbol'],
                'type': 'telegram',
                'success': success
            })
        
        # Send via Email
        if ALERT_CONFIG['email_enabled']:
            success = send_email_alert(candidate, state['scan_id'])
            notification_results.append({
                'symbol': candidate['symbol'],
                'type': 'email',
                'success': success
            })
    
    state['notifications'] = notification_results
    
    return state


# ============================================================================
# WEBHOOK NOTIFICATIONS
# ============================================================================

def send_webhook_alert(candidate: Dict, scan_id: str) -> bool:
    """
    Send alert via webhook (e.g., Slack, Discord, n8n).
    
    Args:
        candidate: Trade candidate dict
        scan_id: Scan identifier
    
    Returns:
        True if successful, False otherwise
    """
    try:
        url = ALERT_CONFIG['webhook_url']
        
        payload = {
            'text': format_alert_message(candidate),
            'candidate': candidate,
            'scan_id': scan_id,
            'timestamp': datetime.now().isoformat(),
        }
        
        response = requests.post(
            url,
            json=payload,
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code in [200, 201, 202, 204]:
            logger.info(f"✓ Webhook alert sent for {candidate['symbol']}")
            save_alert_history(
                scan_id=scan_id,
                evaluation_id=0,  # Would need to track this
                symbol=candidate['symbol'],
                alert_type='webhook',
                confidence_score=candidate['confidence_score'],
                success=True
            )
            return True
        else:
            logger.error(f"Webhook failed: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending webhook alert: {e}")
        return False


# ============================================================================
# TELEGRAM NOTIFICATIONS
# ============================================================================

def send_telegram_alert(candidate: Dict, scan_id: str) -> bool:
    """
    Send alert via Telegram bot.
    
    Args:
        candidate: Trade candidate dict
        scan_id: Scan identifier
    
    Returns:
        True if successful, False otherwise
    """
    try:
        bot_token = ALERT_CONFIG['telegram_bot_token']
        chat_id = ALERT_CONFIG['telegram_chat_id']
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        message = format_alert_message(candidate, format='telegram')
        
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown',
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✓ Telegram alert sent for {candidate['symbol']}")
            save_alert_history(
                scan_id=scan_id,
                evaluation_id=0,
                symbol=candidate['symbol'],
                alert_type='telegram',
                confidence_score=candidate['confidence_score'],
                success=True
            )
            return True
        else:
            logger.error(f"Telegram failed: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending Telegram alert: {e}")
        return False


# ============================================================================
# EMAIL NOTIFICATIONS
# ============================================================================

def send_email_alert(candidate: Dict, scan_id: str) -> bool:
    """
    Send alert via email.
    
    Args:
        candidate: Trade candidate dict
        scan_id: Scan identifier
    
    Returns:
        True if successful, False otherwise
    """
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        smtp_host = ALERT_CONFIG['smtp_host']
        smtp_port = ALERT_CONFIG['smtp_port']
        smtp_user = ALERT_CONFIG['smtp_user']
        smtp_password = ALERT_CONFIG['smtp_password']
        email_from = ALERT_CONFIG['email_from']
        email_to = ALERT_CONFIG['email_to']
        
        if not all([smtp_user, smtp_password, email_from, email_to]):
            logger.warning("Email configuration incomplete, skipping")
            return False
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = ', '.join(email_to)
        msg['Subject'] = f"🎯 Trade Setup Alert: {candidate['symbol']} ({candidate['confidence_score']:.0f}%)"
        
        body = format_alert_message(candidate, format='email')
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        logger.info(f"✓ Email alert sent for {candidate['symbol']}")
        save_alert_history(
            scan_id=scan_id,
            evaluation_id=0,
            symbol=candidate['symbol'],
            alert_type='email',
            confidence_score=candidate['confidence_score'],
            success=True
        )
        return True
    
    except ImportError:
        logger.error("Email modules not available")
        return False
    except Exception as e:
        logger.error(f"Error sending email alert: {e}")
        return False


# ============================================================================
# MESSAGE FORMATTING
# ============================================================================

def format_alert_message(candidate: Dict, format: str = 'text') -> str:
    """
    Format alert message for different notification channels.
    
    Args:
        candidate: Trade candidate dict
        format: 'text', 'telegram', or 'email'
    
    Returns:
        Formatted message string
    """
    symbol = candidate['symbol']
    setup_type = candidate.get('setup_type', 'UNKNOWN')
    confidence = candidate.get('confidence_score', 0)
    quality = candidate.get('setup_quality', 'UNKNOWN')
    
    entry_low = candidate.get('entry_range_low', 0)
    entry_high = candidate.get('entry_range_high', 0)
    stop_loss = candidate.get('stop_loss', 0)
    target_1 = candidate.get('target_1', 0)
    target_2 = candidate.get('target_2', 0)
    rr_ratio = candidate.get('risk_reward_ratio', 0)
    
    position_size = candidate.get('position_size', 0)
    position_value = candidate.get('position_value', 0)
    
    reasoning = candidate.get('reasoning', 'N/A')
    
    if format == 'telegram':
        message = f"""🎯 *TRADE SETUP ALERT*

📊 *{symbol}*
Setup Type: {setup_type}
Quality: {quality}
Confidence: *{confidence:.0f}%*

💰 *Trade Parameters:*
Entry Range: ₹{entry_low:.2f} - ₹{entry_high:.2f}
Stop Loss: ₹{stop_loss:.2f}
Target 1: ₹{target_1:.2f}
Target 2: ₹{target_2:.2f}
Risk:Reward: *1:{rr_ratio:.2f}*

📦 *Position Sizing:*
Shares: {position_size:,}
Value: ₹{position_value:,.0f}

📝 *Analysis:*
{reasoning}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    elif format == 'email':
        message = f"""TRADE SETUP ALERT
{'='*60}

SYMBOL: {symbol}
Setup Type: {setup_type}
Quality: {quality}
Confidence: {confidence:.0f}%

TRADE PARAMETERS:
-----------------
Entry Range: ₹{entry_low:.2f} - ₹{entry_high:.2f}
Stop Loss: ₹{stop_loss:.2f}
Target 1: ₹{target_1:.2f}
Target 2: ₹{target_2:.2f}
Risk:Reward Ratio: 1:{rr_ratio:.2f}

POSITION SIZING:
----------------
Shares: {position_size:,}
Position Value: ₹{position_value:,.0f}

ANALYSIS:
---------
{reasoning}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
This is an automated alert from Indian Stock Swing Trade Agent.
Do your own research before making any investment decisions.
"""
    
    else:  # text/webhook
        message = (
            f"🎯 TRADE ALERT: {symbol} | {setup_type} | {quality} Quality | "
            f"{confidence:.0f}% Confidence | Entry: ₹{entry_low:.2f}-₹{entry_high:.2f} | "
            f"SL: ₹{stop_loss:.2f} | T1: ₹{target_1:.2f} | R:R: 1:{rr_ratio:.2f}"
        )
    
    return message


def log_summary(state: Dict) -> None:
    """
    Log summary of the scan to console/file.
    
    Args:
        state: LangGraph state
    """
    logger.info("="*70)
    logger.info("SCAN SUMMARY")
    logger.info("="*70)
    logger.info(f"Scan ID: {state.get('scan_id', 'N/A')}")
    logger.info(f"Timestamp: {state.get('scan_timestamp', 'N/A')}")
    logger.info(f"Universe Size: {len(state.get('universe', []))}")
    logger.info(f"Stocks Fetched: {len(state.get('market_data', {}))}")
    logger.info(f"Setups Detected: {len(state.get('detected_setups', []))}")
    logger.info(f"Setups Evaluated: {len(state.get('evaluated_setups', []))}")
    logger.info(f"Trade Candidates: {len(state.get('trade_candidates', []))}")
    
    # High confidence count
    high_conf = sum(
        1 for c in state.get('trade_candidates', [])
        if c.get('confidence_score', 0) >= ALERT_CONFIG['min_confidence_for_alert']
    )
    logger.info(f"High Confidence (≥{ALERT_CONFIG['min_confidence_for_alert']}%): {high_conf}")
    
    if state.get('errors'):
        logger.warning(f"Errors: {len(state['errors'])}")
    
    logger.info("="*70)
    
    # List high-confidence setups
    if high_conf > 0:
        logger.info("\n🎯 HIGH CONFIDENCE SETUPS:")
        for candidate in state.get('trade_candidates', []):
            if candidate.get('confidence_score', 0) >= ALERT_CONFIG['min_confidence_for_alert']:
                logger.info(
                    f"  • {candidate['symbol']}: {candidate['setup_type']} | "
                    f"{candidate['confidence_score']:.0f}% | "
                    f"Entry: ₹{candidate.get('entry_range_low', 0):.2f}-₹{candidate.get('entry_range_high', 0):.2f} | "
                    f"R:R: 1:{candidate.get('risk_reward_ratio', 0):.2f}"
                )
