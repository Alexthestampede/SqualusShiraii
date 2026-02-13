import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Data directories
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
ART_DIR = DATA_DIR / "art"
PORTRAITS_DIR = DATA_DIR / "portraits"
VOICES_DIR = DATA_DIR / "voices"
EXPORTS_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "squalus.db"

# Presets
PRESETS_DIR = BASE_DIR / "presets"

# Samples (read-only source material)
SAMPLES_DIR = BASE_DIR / "samples"
LYRICS_PROMPT_PATH = SAMPLES_DIR / "LyricsGenPrompt.txt"

# Service defaults
ACESTEP_URL = os.environ.get("ACESTEP_URL", "http://127.0.0.1:8001")
GRPC_SERVER = os.environ.get("GRPC_SERVER", "192.168.2.150:7859")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
DEFAULT_ARTIST = os.environ.get("DEFAULT_ARTIST", "Squalus Shiraii")

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Ensure data directories exist
for d in [DATA_DIR, AUDIO_DIR, ART_DIR, PORTRAITS_DIR, VOICES_DIR, EXPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
