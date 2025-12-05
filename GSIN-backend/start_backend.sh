#!/bin/bash
# GSIN Backend Startup Script
# This ensures the backend runs with the correct Python environment

cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

# Verify packages are installed
echo "Checking packages..."
python3 -c "import sentry_sdk; import redis; import alpaca_trade_api; print('✅ All packages available')" 2>&1 || {
    echo "⚠️  Installing missing packages..."
    pip install -r requirements.txt
}

# Start backend with venv Python
echo "Starting GSIN Backend..."
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

