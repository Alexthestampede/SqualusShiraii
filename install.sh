#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== Squalus Shiraii 🦈 Installer ==="

# Check system deps
for cmd in ffmpeg git; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: $cmd is required but not found."
        exit 1
    fi
done

# ACE-Step requires Python 3.11 exactly. Find it.
PYTHON=""
for candidate in python3.11 python311; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$(command -v "$candidate")"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "ERROR: Python 3.11 is required (ACE-Step is pinned to ==3.11.*)."
    echo ""
    echo "Your system has:"
    ls /usr/bin/python3.* 2>/dev/null || true
    echo ""
    echo "Install Python 3.11 with:"
    echo "  sudo dnf install python3.11 python3.11-devel"
    echo ""
    echo "Then re-run this script."
    exit 1
fi

PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')
echo "Using Python: $PYTHON ($PY_VERSION)"

# Create venv with Python 3.11
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment with Python 3.11..."
    "$PYTHON" -m venv .venv
else
    # Verify existing venv is 3.11
    VENV_PY=$(".venv/bin/python3" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [ "$VENV_PY" != "3.11" ]; then
        echo "Existing venv is Python $VENV_PY, need 3.11. Recreating..."
        rm -rf .venv
        "$PYTHON" -m venv .venv
    fi
fi

source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Detect GPU and install PyTorch
echo "Detecting GPU..."
IS_ROCM=0
if command -v rocm-smi &>/dev/null; then
    IS_ROCM=1
    echo "ROCm detected - installing PyTorch for ROCm"
    pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/rocm6.3
elif command -v nvidia-smi &>/dev/null; then
    echo "NVIDIA detected - installing PyTorch for CUDA"
    pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu128
else
    echo "No GPU detected - installing CPU PyTorch"
    pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cpu
fi

# --------------------------------------------------------------------------
# ACE-Step's pyproject.toml is written for `uv`, not `pip`:
#   - torch is pinned to +cu128 builds via [tool.uv.sources] index
#   - nano-vllm is a local path via [tool.uv.sources]
# pip can't resolve either. So we install them ourselves, then use --no-deps
# for ACE-Step and install its remaining deps from a curated list.
# --------------------------------------------------------------------------

# nano-vllm (ACE-Step bundled dependency)
echo "Installing nano-vllm..."
if [ "$IS_ROCM" -eq 1 ]; then
    # On ROCm: flash-attn wheels are CUDA-only. Skip it - SDPA fallback works.
    pip install --no-deps -e "$ROOT/ACE-Step-1.5/acestep/third_parts/nano-vllm"
    pip install xxhash transformers "triton>=3.0.0"
else
    pip install -e "$ROOT/ACE-Step-1.5/acestep/third_parts/nano-vllm"
fi

# ACE-Step itself (--no-deps to skip uv-only torch pins)
echo "Installing ACE-Step..."
pip install --no-deps -e "$ROOT/ACE-Step-1.5"

# ACE-Step's actual runtime deps (minus torch/nano-vllm, already installed)
echo "Installing ACE-Step dependencies..."
pip install \
    "transformers>=4.51.0,<4.58.0" \
    diffusers \
    "gradio==6.2.0" \
    "matplotlib>=3.7.5" \
    "scipy>=1.10.1" \
    "soundfile>=0.13.1" \
    "loguru>=0.7.3" \
    "einops>=0.8.1" \
    "accelerate>=1.12.0" \
    "fastapi>=0.110.0" \
    diskcache \
    "uvicorn[standard]>=0.27.0" \
    "numba>=0.63.1" \
    "vector-quantize-pytorch>=1.27.15" \
    "torchcodec>=0.9.1" \
    "torchao>=0.14.1,<0.16.0" \
    toml \
    "peft>=0.18.0" \
    lycoris-lora \
    "lightning>=2.0.0" \
    "tensorboard>=2.20.0" \
    modelscope \
    "typer-slim>=0.21.1"

echo "Installing remaining support libraries..."
pip install -e "$ROOT/ModuLLe"
pip install -e "$ROOT/Qwen3-TTS"

# DTgRPCconnector is not a pip package (no setup.py/pyproject.toml).
# It's imported at runtime via sys.path. Just install its dependencies.
echo "Installing DTgRPCconnector dependencies..."
pip install grpcio flatbuffers Pillow

# Install app requirements
echo "Installing app requirements..."
pip install -r "$ROOT/requirements.txt"

# ROCm cleanup: flash-attn ships CUDA-only binaries (libcudart.so.12).
# It gets pulled in transitively by diffusers but is not needed -
# PyTorch's built-in SDPA is used instead on ROCm.
if [ "$IS_ROCM" -eq 1 ]; then
    echo "ROCm: removing CUDA-only flash-attn (SDPA fallback will be used)..."
    pip uninstall -y flash-attn 2>/dev/null || true
fi

# Download ACE-Step models
echo "Downloading ACE-Step models..."
if command -v acestep-download &>/dev/null; then
    acestep-download
else
    echo "WARNING: acestep-download not found, skip model download. Run manually later."
fi

# Create data directories
echo "Creating data directories..."
mkdir -p "$ROOT/data"/{audio,art,portraits,voices,exports}

# Copy presets
echo "Copying presets..."
mkdir -p "$ROOT/presets"
if [ -d "$ROOT/samples/DTpresets" ]; then
    cp -r "$ROOT/samples/DTpresets/"*.json "$ROOT/presets/" 2>/dev/null || true
fi

echo ""
echo "=== Installation complete ==="
echo "Run: ./run.sh"
