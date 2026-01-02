#!/usr/bin/env python3
"""
Validation Script for Indian Stock Market Agent
Checks all components and prerequisites before deployment.
"""

import sys
import subprocess
from pathlib import Path
import importlib.util

def print_header(text):
    """Print formatted header."""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def print_check(name, status, message=""):
    """Print check result."""
    symbol = "✓" if status else "✗"
    status_text = "PASS" if status else "FAIL"
    print(f"{symbol} [{status_text}] {name}")
    if message:
        print(f"          {message}")

def check_python_version():
    """Check Python version."""
    version = sys.version_info
    is_valid = version.major == 3 and version.minor >= 10
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    print_check("Python Version", is_valid, f"Found: {version_str} (Required: 3.10+)")
    return is_valid

def check_file_exists(filepath, description):
    """Check if file exists."""
    exists = Path(filepath).exists()
    print_check(description, exists, f"Path: {filepath}")
    return exists

def check_module_import(module_name, package_name=None):
    """Check if Python module can be imported."""
    try:
        importlib.import_module(module_name)
        print_check(f"Module: {module_name}", True)
        return True
    except ImportError:
        pkg = package_name or module_name
        print_check(f"Module: {module_name}", False, f"Run: pip install {pkg}")
        return False

def check_ollama():
    """Check Ollama installation and model."""
    # Check if ollama command exists
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        ollama_installed = result.returncode == 0
        print_check("Ollama Installed", ollama_installed)
        
        if ollama_installed:
            # Check for llama3.1:8b model
            has_model = "llama3.1:8b" in result.stdout or "llama3.1" in result.stdout
            print_check("Model llama3.1:8b", has_model, 
                       "Run: ollama pull llama3.1:8b" if not has_model else "")
            return has_model
        return False
    except FileNotFoundError:
        print_check("Ollama Installed", False, "Install from: https://ollama.ai")
        return False
    except subprocess.TimeoutExpired:
        print_check("Ollama Installed", False, "Command timed out")
        return False
    except Exception as e:
        print_check("Ollama Installed", False, str(e))
        return False

def check_directory_structure():
    """Check project directory structure."""
    required_dirs = [
        "agent",
        "logs",
    ]
    
    all_exist = True
    for dir_name in required_dirs:
        exists = Path(dir_name).is_dir()
        print_check(f"Directory: {dir_name}/", exists)
        all_exist = all_exist and exists
    
    return all_exist

def check_agent_modules():
    """Check agent module files."""
    modules = [
        ("agent/__init__.py", "Agent Package Init"),
        ("agent/universe.py", "Universe Loader"),
        ("agent/data_fetcher.py", "Data Fetcher"),
        ("agent/indicators.py", "Indicators Engine"),
        ("agent/setup_detector.py", "Setup Detector"),
        ("agent/evaluator.py", "LLM Evaluator"),
        ("agent/risk.py", "Risk Engine"),
        ("agent/persister.py", "Data Persister"),
        ("agent/notifier.py", "Notifier"),
    ]
    
    all_exist = True
    for filepath, description in modules:
        exists = check_file_exists(filepath, description)
        all_exist = all_exist and exists
    
    return all_exist

def check_core_files():
    """Check core project files."""
    files = [
        ("config.py", "Configuration"),
        ("db.py", "Database Schema"),
        ("graph.py", "LangGraph Workflow"),
        ("agent_runner.py", "Main Entrypoint"),
        ("requirements.txt", "Dependencies"),
        ("README.md", "Documentation"),
    ]
    
    all_exist = True
    for filepath, description in files:
        exists = check_file_exists(filepath, description)
        all_exist = all_exist and exists
    
    return all_exist

def check_dependencies():
    """Check Python dependencies."""
    dependencies = [
        ("langgraph", None),
        ("langchain_core", "langchain-core"),
        ("jugaad_data", "jugaad-data"),
        ("yfinance", None),
        ("pandas_ta", "pandas-ta"),
        ("ollama", None),
        ("pydantic", None),
        ("pandas", None),
        ("numpy", None),
        ("requests", None),
        ("pytz", None),
    ]
    
    all_imported = True
    for module, package in dependencies:
        imported = check_module_import(module, package)
        all_imported = all_imported and imported
    
    return all_imported

def check_database():
    """Check database initialization."""
    try:
        sys.path.insert(0, str(Path.cwd()))
        from db import init_database, get_db_stats
        
        init_database()
        stats = get_db_stats()
        
        print_check("Database Init", True, f"Previous scans: {stats.get('agent_runs', 0)}")
        return True
    except Exception as e:
        print_check("Database Init", False, str(e))
        return False

def check_config():
    """Check configuration."""
    try:
        sys.path.insert(0, str(Path.cwd()))
        from config import DEFAULT_UNIVERSE, OLLAMA_CONFIG, ALERT_CONFIG
        
        print_check("Config Import", True)
        print_check("Universe Size", len(DEFAULT_UNIVERSE) > 0, 
                   f"Stocks: {len(DEFAULT_UNIVERSE)}")
        print_check("Ollama Model", True, 
                   f"Model: {OLLAMA_CONFIG.get('model', 'N/A')}")
        
        return True
    except Exception as e:
        print_check("Config Import", False, str(e))
        return False

def main():
    """Run all validation checks."""
    print_header("INDIAN STOCK MARKET AGENT - VALIDATION")
    
    print("\n📋 SYSTEM CHECKS")
    python_ok = check_python_version()
    
    print("\n📁 PROJECT STRUCTURE")
    dirs_ok = check_directory_structure()
    core_ok = check_core_files()
    agent_ok = check_agent_modules()
    
    print("\n📦 PYTHON DEPENDENCIES")
    deps_ok = check_dependencies()
    
    print("\n🤖 OLLAMA")
    ollama_ok = check_ollama()
    
    print("\n⚙️  CONFIGURATION")
    config_ok = check_config()
    
    print("\n💾 DATABASE")
    db_ok = check_database()
    
    # Overall summary
    print_header("VALIDATION SUMMARY")
    
    all_checks = [
        ("Python Version", python_ok),
        ("Project Structure", dirs_ok and core_ok and agent_ok),
        ("Dependencies", deps_ok),
        ("Ollama & Model", ollama_ok),
        ("Configuration", config_ok),
        ("Database", db_ok),
    ]
    
    passed = sum(1 for _, status in all_checks if status)
    total = len(all_checks)
    
    for name, status in all_checks:
        print_check(name, status)
    
    print(f"\n{passed}/{total} checks passed")
    
    if passed == total:
        print("\n✅ ALL CHECKS PASSED - Ready for deployment!")
        print("\nNext steps:")
        print("1. Configure alerts in config.py (webhook/Telegram/email)")
        print("2. Test run: python agent_runner.py --force")
        print("3. Setup cron: See cron.example for configuration")
        return 0
    else:
        print("\n⚠️  SOME CHECKS FAILED - Fix issues before deployment")
        print("\nCommon fixes:")
        print("- Install missing dependencies: pip install -r requirements.txt")
        print("- Install Ollama: https://ollama.ai")
        print("- Pull model: ollama pull llama3.1:8b")
        return 1

if __name__ == "__main__":
    sys.exit(main())
