#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Activate venv
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "ERROR: .venv not found. Run ./install.sh first."
    exit 1
fi

ACESTEP_PID=""
APP_PID=""

cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$APP_PID" ] && kill "$APP_PID" 2>/dev/null || true
    [ -n "$ACESTEP_PID" ] && kill "$ACESTEP_PID" 2>/dev/null || true
    wait 2>/dev/null
    echo "Done."
}
trap cleanup SIGINT SIGTERM EXIT

# Start ACE-Step API on :8001
echo "Starting ACE-Step API on :8001..."
acestep-api --host 127.0.0.1 --port 8001 &
ACESTEP_PID=$!

# Wait for ACE-Step health check
echo "Waiting for ACE-Step to be ready..."
for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:8001/health &>/dev/null; then
        echo "ACE-Step ready."
        break
    fi
    if ! kill -0 "$ACESTEP_PID" 2>/dev/null; then
        echo "ERROR: ACE-Step process died."
        exit 1
    fi
    sleep 2
done

# Start Squalus Shiraii on :8000
echo "Starting Squalus Shiraii 🦈 on :8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
APP_PID=$!

echo ""
echo "=== Squalus Shiraii 🦈 running ==="
echo "  App:      http://localhost:8000"
echo "  ACE-Step: http://localhost:8001"
echo ""
echo "Press Ctrl+C to stop."

wait
