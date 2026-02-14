# Squalus Shiraii

A web interface that brings ACE Step to a nicer UI, enhances it with support for external LLMs for lyrics generation, and adds cover art generation using Draw Things' gRPC server.

## Features

- **Web Interface** - Clean, user-friendly interface for ACE Step
- **External LLM Support** - Connect to any LLM provider (Ollama, OpenAI, etc.) for lyrics generation
- **Cover Art Generation** - Generate album artwork using Draw Things via gRPC
- **Multi-Platform Support** - Linux, macOS, and Windows
- **GPU Acceleration** - Supports NVIDIA, AMD (ROCm), and Apple Silicon; CPU-only mode available

## Quick Start

```bash
git clone --recursive https://github.com/Alexthestampede/SqualusShiraii
cd SqualusShiraii
./install.sh
./run.sh
```

The app will be available at http://localhost:8000

## Update

```bash
git pull
git submodule update --init --recursive
```

## Configuration

Optional environment variables:

```bash
export LLM_PROVIDER=ollama       # LLM provider for lyrics (default: ollama)
export LLM_BASE_URL=http://localhost:11434
export LLM_MODEL=llama3
export GRPC_SERVER=192.168.2.150:7859  # Draw Things server
export ACESTEP_URL=http://localhost:8001
```

## Platform Notes

- **Linux** - Full NVIDIA and AMD ROCm support
- **macOS** - Apple Silicon supported. ACE Step may run out of memory on models requiring more than 8GB VRAM
- **Windows** - NVIDIA CUDA supported; WSL2 recommended

## Current Limitations

- **Personas** - Currently not functional
- **Qwen3 TTS** - Planned, not currently in use

## Requirements

- Python 3.11
- Git
- ffmpeg

## Project

- Single developer project
- Report issues on GitHub
