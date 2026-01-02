# Indian Stock Market Swing Trade Research Agent

**Autonomous, background-running stock market research agent for NSE/BSE swing trading setups.**

This is NOT a chatbot or interactive UI. It's a fully autonomous agent that:
- Scans NIFTY 50 stocks for swing trade opportunities
- Analyzes technical indicators (EMA, RSI, MACD, ATR, Volume)
- Detects breakout, pullback, momentum, and consolidation setups
- Evaluates quality using Ollama LLM (llama3.1:8b)
- Calculates risk metrics (position sizing, stop loss, targets)
- Persists results to SQLite database
- Sends alerts for high-confidence setups (≥80%)
- Runs autonomously via cron every 15 minutes during market hours

---

## 🏗️ Architecture

```
indian-stock-agent/
├── agent/
│   ├── __init__.py
│   ├── universe.py          # Stock universe loader
│   ├── data_fetcher.py      # OHLCV fetcher (jugaad-data + yfinance)
│   ├── indicators.py        # Technical indicators (pandas-ta)
│   ├── setup_detector.py    # Rule-based setup detection
│   ├── evaluator.py         # LLM evaluation (Ollama)
│   ├── risk.py              # Risk management & position sizing
│   ├── persister.py         # SQLite persistence
│   └── notifier.py          # Alert system (webhook/Telegram/email)
├── graph.py                 # LangGraph orchestration
├── agent_runner.py          # Main entrypoint
├── config.py                # Configuration
├── db.py                    # Database schema
├── requirements.txt
├── logs/                    # Auto-created
└── README.md
```

### Workflow (LangGraph)

```
START → initialize → universe → fetcher → indicators → detector
                                    ↓
                        [if setups found?]
                        YES → evaluator → risk → persister → notifier → END
                        NO  → skip_eval → persister → notifier → END
```

---

## 📋 Prerequisites

### System Requirements
- **Python**: 3.10+
- **RAM**: 32GB recommended (for llama3.1:8b)
- **OS**: macOS, Linux, or Windows
- **Ollama**: Running locally

### Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai/download
```

### Pull LLM Model

```bash
ollama pull llama3.1:8b
```

Verify model is available:

```bash
ollama list
```

You should see `llama3.1:8b` in the list.

---

## 🚀 Installation

### 1. Clone/Create Project

```bash
mkdir indian-stock-agent
cd indian-stock-agent

# Copy all files from the generated structure
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Initialize Database

The database auto-initializes on first run, but you can test it:

```bash
python -c "from db import init_database, get_db_stats; init_database(); print(get_db_stats())"
```

### 5. Test Ollama Connection

```bash
python -c "from agent.evaluator import check_ollama_connection; print(check_ollama_connection())"
```

Should output: `True`

---

## ⚙️ Configuration

Edit `config.py` to customize:

### Stock Universe

```python
# Default: NIFTY 50
DEFAULT_UNIVERSE = NIFTY_50_NSE

# Or create custom list
CUSTOM_UNIVERSE = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
```

### Technical Indicators

```python
INDICATORS = {
    "ema_short": 20,
    "ema_medium": 50,
    "ema_long": 200,
    "rsi_period": 14,
    "atr_period": 14,
    # ... more
}
```

### Risk Management

```python
RISK_CONFIG = {
    "default_account_size": 1000000,  # ₹10 lakhs
    "risk_per_trade_percent": 2.0,
    "stop_loss_atr_multiplier": 2.0,
    "target_ratios": [2.0, 3.0],  # 1:2 and 1:3 R:R
}
```

### Alerts

```python
ALERT_CONFIG = {
    "min_confidence_for_alert": 80,  # Only alert ≥80% confidence
    
    # Webhook (e.g., n8n, Slack, Discord)
    "webhook_url": "https://your-webhook-url.com",
    
    # Telegram
    "telegram_bot_token": "YOUR_BOT_TOKEN",
    "telegram_chat_id": "YOUR_CHAT_ID",
    
    # Email
    "email_enabled": False,
    "smtp_host": "smtp.gmail.com",
    "smtp_user": "your-email@gmail.com",
    # ... more
}
```

---

## 🎯 Usage

### Manual Execution

#### Live Scan (checks market hours)

```bash
python agent_runner.py
```

#### Force Run (ignore market hours)

```bash
python agent_runner.py --force
```

#### Backtest Mode (historical date)

```bash
python agent_runner.py --backtest 2025-12-15
```

### Expected Output

```
======================================================================
INDIAN STOCK MARKET SWING TRADE RESEARCH AGENT
======================================================================
Started at: 2026-01-02 10:30:00

✓ Ollama connection OK
✓ Database OK - 5 previous scans
✓ Environment validation passed

Within market hours (IST: 10:30:00)
Running in LIVE mode

Starting agent workflow...
Loaded universe: 50 symbols
Fetching data for 50 symbols...
[1/50] Fetched RELIANCE.NS (365 bars, source: jugaad)
[2/50] Fetched TCS.NS (365 bars, source: cache)
...
Computed indicators for 50 symbols
Detected 12 total setups across all symbols
Proceeding to LLM evaluation for 12 setups

Evaluating RELIANCE.NS BREAKOUT setup with Ollama...
RELIANCE.NS: LLM Evaluation - HIGH quality, 85% confidence
...

✓ Agent workflow completed in 45.23 seconds

======================================================================
SCAN SUMMARY
======================================================================
Scan ID: scan_a3f9e2c1b5d8
Duration: 45.23 seconds
Stocks Scanned: 50
Data Fetched: 48
Setups Detected: 12
Setups Evaluated: 12
Trade Candidates: 12
High Confidence (≥80%): 5

🎯 HIGH CONFIDENCE SETUPS:
  • RELIANCE.NS: BREAKOUT | 85% | Entry: ₹2450-₹2475 | R:R: 1:2.3
  • TCS.NS: MOMENTUM | 82% | Entry: ₹3890-₹3920 | R:R: 1:2.8
  ...

✓ Results saved to database
✓ Sent 3 alerts
======================================================================
```

---

## ⏰ Cron Scheduling

### Setup Cron (Linux/macOS)

Edit crontab:

```bash
crontab -e
```

Add entry to run every 15 minutes during market hours (9:15 AM - 3:30 PM IST):

```cron
# Indian Stock Agent - Every 15 minutes during market hours (Mon-Fri)
*/15 9-15 * * 1-5 cd /path/to/indian-stock-agent && /path/to/venv/bin/python agent_runner.py >> logs/cron.log 2>&1
```

**Important**:
- Replace `/path/to/indian-stock-agent` with actual path
- Replace `/path/to/venv/bin/python` with your venv Python path
- Agent checks market hours internally, so it will exit gracefully outside trading times

### Verify Cron Setup

```bash
# List cron jobs
crontab -l

# Test manual run
cd /path/to/indian-stock-agent
source venv/bin/activate
python agent_runner.py --force
```

### Alternative: Systemd Service (Linux)

Create `/etc/systemd/system/stock-agent.service`:

```ini
[Unit]
Description=Indian Stock Market Research Agent
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/indian-stock-agent
ExecStart=/path/to/venv/bin/python agent_runner.py
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable stock-agent.service
sudo systemctl start stock-agent.service
sudo systemctl status stock-agent.service
```

---

## 📊 Database Schema

### Tables

1. **agent_runs** - Scan metadata and summary
2. **stock_snapshots** - OHLCV + indicators for each symbol
3. **trade_setups** - Detected setups (rule-based)
4. **evaluation_results** - LLM evaluations + risk metrics
5. **alert_history** - Alert delivery logs

### Query Examples

```bash
# Recent scans
sqlite3 trade_agent.db "SELECT scan_timestamp, setups_detected, high_confidence_count FROM agent_runs ORDER BY scan_timestamp DESC LIMIT 5;"

# High confidence setups
sqlite3 trade_agent.db "SELECT symbol, confidence_score, entry_range_low, target_1, risk_reward_ratio FROM evaluation_results WHERE confidence_score >= 80 ORDER BY confidence_score DESC;"
```

---

## 🔔 Alert Configuration

### Webhook (n8n / Zapier / Custom)

```python
ALERT_CONFIG = {
    "webhook_url": "https://your-n8n-instance.com/webhook/stock-alerts",
}
```

Payload sent:

```json
{
  "text": "🎯 TRADE ALERT: RELIANCE.NS | BREAKOUT | HIGH Quality | 85% Confidence...",
  "candidate": {
    "symbol": "RELIANCE.NS",
    "setup_type": "BREAKOUT",
    "confidence_score": 85,
    "entry_range_low": 2450,
    "stop_loss": 2380,
    "target_1": 2590,
    "risk_reward_ratio": 2.3,
    ...
  },
  "scan_id": "scan_a3f9e2c1b5d8",
  "timestamp": "2026-01-02T10:45:00"
}
```

### Telegram

1. Create bot with [@BotFather](https://t.me/BotFather)
2. Get your chat ID: send message to [@userinfobot](https://t.me/userinfobot)
3. Configure:

```python
ALERT_CONFIG = {
    "telegram_bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "telegram_chat_id": "987654321",
}
```

### Email (Gmail)

```python
ALERT_CONFIG = {
    "email_enabled": True,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "your-email@gmail.com",
    "smtp_password": "your-app-password",  # Use App Password, not regular password
    "email_from": "your-email@gmail.com",
    "email_to": ["recipient@example.com"],
}
```

For Gmail App Password: https://support.google.com/accounts/answer/185833

---

## 🧪 Testing & Validation

### Test Individual Components

```bash
# Test universe loading
python -c "from agent.universe import load_universe; print(len(load_universe()))"

# Test data fetch for single symbol
python -c "from agent.data_fetcher import fetch_market_data; df, src = fetch_market_data('RELIANCE.NS'); print(f'Fetched {len(df)} bars from {src}')"

# Test indicators
python -c "from agent.data_fetcher import fetch_market_data; from agent.indicators import compute_indicators; df, _ = fetch_market_data('TCS.NS'); result = compute_indicators(df); print(result.columns.tolist())"

# Test Ollama evaluation
python -c "from agent.evaluator import check_ollama_connection; print('Ollama OK' if check_ollama_connection() else 'Ollama Failed')"
```

### Run Backtest

Validate strategy on historical data:

```bash
# Test a known date
python agent_runner.py --backtest 2025-11-15
```

### Check Logs

```bash
tail -f logs/agent.log
```

---

## 📈 Output Format

High-confidence setups generate structured JSON:

```json
{
  "symbol": "RELIANCE.NS",
  "setup_type": "BREAKOUT",
  "timeframe": "1d",
  "setup_quality": "HIGH",
  "confidence_score": 85.0,
  "breakout_confirmation": "YES",
  "trend_strength": "STRONG",
  "current_price": 2462.50,
  "entry_range_low": 2450.00,
  "entry_range_high": 2475.00,
  "stop_loss": 2380.00,
  "target_1": 2590.00,
  "target_2": 2670.00,
  "risk_reward_ratio": 2.3,
  "risk_percent": 3.4,
  "position_size": 243,
  "position_value": 597000,
  "max_loss": 20000,
  "reasoning": "Strong breakout above 20-day consolidation with 1.8x volume spike. EMAs aligned bullishly (20>50>200). RSI at 65 showing momentum without overbought condition. MACD histogram positive and expanding."
}
```

---

## 🛠️ Troubleshooting

### Issue: "Ollama connection failed"

**Solution**:
```bash
# Start Ollama server
ollama serve

# Pull model
ollama pull llama3.1:8b

# Verify
ollama list
```

### Issue: "jugaad-data fetch failed"

**Solutions**:
1. NSE rate limiting - agent auto-retries and caches
2. Falls back to yfinance automatically
3. Check internet connection
4. Verify symbol format (must have `.NS` suffix)

### Issue: "Outside market hours"

**Solution**:
```bash
# Force run for testing
python agent_runner.py --force

# Or wait for market hours (9:15 AM - 3:30 PM IST Mon-Fri)
```

### Issue: "No setups detected"

**Causes**:
- Market conditions may not meet criteria
- All stocks passed baseline filters but no specific patterns
- Normal behavior - not every scan finds setups

**Solution**: Review `SETUP_RULES` in `config.py` if too strict

### Issue: Database locked

**Solution**:
```bash
# Kill any hanging processes
pkill -f agent_runner.py

# Check database
sqlite3 trade_agent.db "PRAGMA integrity_check;"
```

---

## 🔐 Security Notes

- **Never commit** API keys, tokens, or passwords to Git
- Use environment variables for sensitive config:

```python
import os

ALERT_CONFIG = {
    "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID"),
}
```

- Set in cron:

```cron
*/15 9-15 * * 1-5 TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy cd /path && python agent_runner.py
```

---

## 📚 Technical Details

### Strategy Components

1. **Baseline Filters** (must pass all):
   - Price above EMA 50 & 200
   - Volume > 1.5× 20-day average
   - RSI between 55-70
   - ATR > 1% of price

2. **Setup Types**:
   - **BREAKOUT**: Close above 20-day high + volume spike
   - **PULLBACK**: Price within 2% of EMA50, bouncing up
   - **MOMENTUM**: 3+ higher highs/lows, positive MACD
   - **CONSOLIDATION**: Tight range (<5%) then breakout

3. **LLM Evaluation**:
   - Ollama llama3.1:8b with `temperature=0`
   - Structured JSON output (Pydantic validation)
   - Assesses: quality, breakout confirmation, trend strength
   - Provides reasoning (2-3 sentences)

4. **Risk Management**:
   - Stop Loss: 2× ATR below entry (min 2%, max 8%)
   - Targets: 1:2 and 1:3 risk-reward ratios
   - Position Size: 2% account risk ÷ stop distance
   - Max Position: 20% of account

### Data Sources

1. **Primary**: jugaad-data
   - Built for NSE/BSE
   - Better caching
   - India-specific features

2. **Fallback**: yfinance
   - Global coverage
   - Automatic fallback on jugaad errors

### Caching

- Daily data: 24-hour TTL
- Weekly data: 7-day TTL
- SQLite cache: `.cache/market_data_cache.db`
- Speeds up re-scans and reduces API load

---

## 🚧 Limitations

- **Not financial advice** - For research/educational purposes only
- **No execution** - Does NOT place trades
- **Market data delays** - Depends on data source
- **LLM evaluation** - Qualitative, not guaranteed
- **NSE rate limits** - Handled with retries and caching

---

## 🔮 Future Enhancements

Potential extensions:

1. **Intraday scanning** - 5min / 15min timeframes
2. **Broker integration** - Paper trading (Zerodha, Upstox APIs)
3. **Backtesting engine** - Historical validation with metrics
4. **Web dashboard** - View results in browser (FastAPI + React)
5. **Options analysis** - Add F&O setups
6. **Sentiment integration** - News/Twitter sentiment
7. **Multi-universe** - NIFTY 500, sector-specific
8. **ML models** - Complement rule-based detection

---

## 📞 Support

For issues or questions:

1. Check logs: `logs/agent.log`
2. Review database: `sqlite3 trade_agent.db`
3. Test components individually (see Testing section)
4. Review configuration: `config.py`

---

## 📄 License

This project is for educational and research purposes.

**Disclaimer**: This software is provided "as is" without warranty. Not financial advice. Trading involves risk. Always do your own research and consult a financial advisor.

---

## 🎓 Learning Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Ollama Documentation](https://ollama.ai/docs)
- [pandas-ta Documentation](https://github.com/twopirllc/pandas-ta)
- [NSE India](https://www.nseindia.com/)
- [Swing Trading Basics](https://www.investopedia.com/terms/s/swingtrading.asp)

---

**Built with** 🇮🇳 **for Indian stock market swing traders**

*Version 1.0.0 - January 2026*
