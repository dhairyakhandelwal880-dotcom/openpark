#!/usr/bin/env bash
# OpenPark - 1-Click Local Development & Server Launcher

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "============================================================"
echo "🚀 Starting OpenPark Unified Server (FastAPI + Web Client)"
echo "============================================================"

# Check if virtual environment exists
if [ -d "backend/venv" ]; then
    PYTHON_BIN="backend/venv/bin/python"
    UVICORN_BIN="backend/venv/bin/uvicorn"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
    UVICORN_BIN="uvicorn"
else
    echo "❌ Error: Python 3 not found. Please install Python 3.9+."
    exit 1
fi

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

echo "📡 Serving at: http://localhost:${PORT}/app/"
echo "📊 Dashboard at: http://localhost:${PORT}/dashboard/"
echo "📚 API Docs at:  http://localhost:${PORT}/docs"
echo "------------------------------------------------------------"
echo "Press Ctrl+C to stop the server."
echo "============================================================"

# Try to automatically open browser on macOS or Linux in background after 1s
(
  sleep 1.5
  if command -v open >/dev/null 2>&1; then
    open "http://localhost:${PORT}/app/"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:${PORT}/app/"
  fi
) &

exec "$UVICORN_BIN" backend.main:app --host "$HOST" --port "$PORT" --reload
