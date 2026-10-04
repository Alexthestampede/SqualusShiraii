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

# --------------------------------------------------------------------------
# ROCm environment setup (matches what start_*_rocm.bat does on Windows)
# --------------------------------------------------------------------------
if ! command -v nvidia-smi &>/dev/null && command -v rocm-smi &>/dev/null; then
    echo "ROCm detected - configuring AMD GPU environment..."

    # HSA_OVERRIDE_GFX_VERSION: required for consumer RDNA3 GPUs.
    # Auto-detect from rocminfo if not already set.
    if [ -z "${HSA_OVERRIDE_GFX_VERSION:-}" ]; then
        GFX_TARGET=$(rocminfo 2>/dev/null | grep -oP 'gfx\d+' | head -1 || true)
        case "$GFX_TARGET" in
            gfx1100) export HSA_OVERRIDE_GFX_VERSION=11.0.0 ;;  # RX 7900 XT/XTX
            gfx1101) export HSA_OVERRIDE_GFX_VERSION=11.0.1 ;;  # RX 7800 XT / 7700 XT
            gfx1102) export HSA_OVERRIDE_GFX_VERSION=11.0.2 ;;  # RX 7600
            gfx1150|gfx1151) export HSA_OVERRIDE_GFX_VERSION=11.0.0 ;;  # RDNA4
            *)
                echo "  NOTE: Unknown GFX target '$GFX_TARGET'. If GPU is not detected,"
                echo "  set HSA_OVERRIDE_GFX_VERSION manually (see ACE-Step docs)."
                ;;
        esac
        [ -n "${HSA_OVERRIDE_GFX_VERSION:-}" ] && \
            echo "  HSA_OVERRIDE_GFX_VERSION=$HSA_OVERRIDE_GFX_VERSION (auto-detected from $GFX_TARGET)"
    fi

    # Force PyTorch LM backend - vllm/nano-vllm requires CUDA flash-attn
    export ACESTEP_LM_BACKEND="${ACESTEP_LM_BACKEND:-pt}"

    # Prevent first-run VAE decode hang (MIOpen exhaustive search)
    export MIOPEN_FIND_MODE="${MIOPEN_FIND_MODE:-FAST}"

    # Avoid HuggingFace tokenizer fork warnings
    export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

    echo "  ACESTEP_LM_BACKEND=$ACESTEP_LM_BACKEND"
    echo "  MIOPEN_FIND_MODE=$MIOPEN_FIND_MODE"
fi

ACESTEP_PID=""
YUE2_PID=""
APP_PID=""

cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$APP_PID" ] && kill "$APP_PID" 2>/dev/null || true
    [ -n "$YUE2_PID" ] && kill "$YUE2_PID" 2>/dev/null || true
    [ -n "$ACESTEP_PID" ] && kill "$ACESTEP_PID" 2>/dev/null || true
    wait 2>/dev/null
    echo "Done."
}
trap cleanup SIGINT SIGTERM EXIT

# YuE2 (YuE2UI) on :7860 - auto-starts when its venv exists (installed via
# ./install.sh --with-yue2). The server is quick to start; the model itself
# lazy-loads on the first job. Disable with YUE2_ENABLED=0.
YUE2_ENABLED="${YUE2_ENABLED:-1}"
if [ "$YUE2_ENABLED" = "1" ]; then
    if [ -x "$ROOT/YuE2UI/.venv/bin/python" ]; then
        # Port must be free - a foreign/stray server on 7860 would silently
        # impersonate YuE2 while our process fails to bind underneath it.
        if curl -sf --max-time 2 http://127.0.0.1:7860/api/songs &>/dev/null; then
            echo "WARNING: something is already listening on :7860 (foreign YuE2 server?)."
            echo "  Not starting our own copy. Kill it first if unintended:"
            PID_7860=$(ss -ltnp 2>/dev/null | grep -oP '(?<=pid=)\d+(?=.*7860)' | head -1)
            [ -n "$PID_7860" ] && echo "  kill $PID_7860"
            YUE2_PID=""
        else
            echo "Starting YuE2 (YuE2UI) on :7860..."
            (
                cd "$ROOT/YuE2UI"
                # MIOpen: skip per-shape kernel search on first use (identical output)
                export MIOPEN_FIND_MODE="${MIOPEN_FIND_MODE:-FAST}"
                "$ROOT/YuE2UI/.venv/bin/python" server.py > "$ROOT/data/yue2.log" 2>&1 < /dev/null &
                echo $! > "$ROOT/data/yue2.pid"
            )
            YUE2_PID="$(cat "$ROOT/data/yue2.pid")"

            echo "Waiting for YuE2 API to be ready..."
            for i in $(seq 1 30); do
                if curl -sf http://127.0.0.1:7860/api/songs &>/dev/null; then
                    echo "YuE2 ready."
                    break
                fi
                if ! kill -0 "$YUE2_PID" 2>/dev/null; then
                    echo "WARNING: YuE2 process died - see data/yue2.log (continuing without it)."
                    YUE2_PID=""
                    break
                fi
                sleep 2
            done
        fi
    else
        echo "YuE2 not installed (./install.sh --with-yue2) - skipping. Continuing without it."
    fi
fi

# ACE-Step on :8001 - opt-in with ACESTEP_ENABLED=1. It loads its model at
# startup, which is slow; use it when you specifically want ACE-Step renders
# (also powers the lyrics /format endpoint).
ACESTEP_ENABLED="${ACESTEP_ENABLED:-0}"
ACESTEP_PID=""
if [ "$ACESTEP_ENABLED" = "1" ]; then
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
else
    echo "ACE-Step disabled (ACESTEP_ENABLED=1 to enable)."
fi

# Start Squalus Shiraii on :8000
echo "Starting Squalus Shiraii 🦈 on :8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
APP_PID=$!

echo ""
echo "=== Squalus Shiraii 🦈 running ==="
echo "  App:      http://localhost:8000"
[ -n "$YUE2_PID" ] && echo "  YuE2:     http://localhost:7860"
[ -n "$ACESTEP_PID" ] && echo "  ACE-Step: http://localhost:8001"
echo ""
echo "Press Ctrl+C to stop."

wait
