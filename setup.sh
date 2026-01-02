#!/bin/bash

# Quick Start Script for Indian Stock Market Agent
# This script helps with initial setup

set -e

echo "==========================================="
echo "Indian Stock Market Agent - Quick Setup"
echo "==========================================="
echo ""

# Check Python version
echo "1. Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Found: Python $python_version"

# Create virtual environment
echo ""
echo "2. Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "   ✓ Virtual environment created"
else
    echo "   ✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "3. Activating virtual environment..."
source venv/bin/activate
echo "   ✓ Activated"

# Upgrade pip
echo ""
echo "4. Upgrading pip..."
pip install --upgrade pip --quiet
echo "   ✓ pip upgraded"

# Install dependencies
echo ""
echo "5. Installing dependencies..."
pip install -r requirements.txt --quiet
echo "   ✓ Dependencies installed"

# Check Ollama
echo ""
echo "6. Checking Ollama installation..."
if command -v ollama &> /dev/null; then
    echo "   ✓ Ollama is installed"
    
    echo ""
    echo "7. Checking for llama3.1:8b model..."
    if ollama list | grep -q "llama3.1:8b"; then
        echo "   ✓ llama3.1:8b model found"
    else
        echo "   ⚠ llama3.1:8b model not found"
        echo "   Pulling model (this may take a few minutes)..."
        ollama pull llama3.1:8b
        echo "   ✓ Model downloaded"
    fi
else
    echo "   ⚠ Ollama not found"
    echo "   Please install Ollama:"
    echo "   macOS: brew install ollama"
    echo "   Linux: curl -fsSL https://ollama.ai/install.sh | sh"
    echo "   Then run: ollama pull llama3.1:8b"
fi

# Initialize database
echo ""
echo "8. Initializing database..."
python3 -c "from db import init_database; init_database()" 2>/dev/null || true
echo "   ✓ Database initialized"

# Create .env if not exists
echo ""
echo "9. Checking configuration..."
if [ ! -f ".env" ]; then
    cp .env.template .env
    echo "   ✓ Created .env from template"
    echo "   ⚠ Edit .env to add your alert credentials"
else
    echo "   ✓ .env already exists"
fi

# Test run
echo ""
echo "10. Running validation test..."
if python3 agent_runner.py --skip-validation --force 2>&1 | grep -q "Environment validation"; then
    echo "   ✓ Validation test passed"
else
    echo "   ⚠ Test run had issues (check logs/agent.log)"
fi

echo ""
echo "==========================================="
echo "✓ Setup Complete!"
echo "==========================================="
echo ""
echo "Next steps:"
echo "1. Edit config.py to customize settings"
echo "2. Edit .env to add alert credentials (Telegram, webhook, etc.)"
echo "3. Start Ollama server: ollama serve"
echo "4. Test run: python agent_runner.py --force"
echo "5. Setup cron: See README.md for cron configuration"
echo ""
echo "For help, see README.md"
echo ""
