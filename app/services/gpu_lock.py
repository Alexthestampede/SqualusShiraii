"""VRAM mutex - ensures only one heavy GPU operation runs at a time.

ACE-Step runs as a separate process with --offload_to_cpu, so it manages its own VRAM.
Qwen3-TTS loads in-process and needs explicit coordination.
This lock prevents TTS and any future in-process GPU work from colliding.
"""

import asyncio

gpu_lock = asyncio.Lock()
