"""Qwen3-TTS integration - voice cloning, voice design, custom voices.

Manages model lifecycle: lazy load, GPU offload, coordinate via gpu_lock.
"""

import pickle
from pathlib import Path

import numpy as np
import soundfile as sf

from app.config import VOICES_DIR
from app.services.gpu_lock import gpu_lock

# Module-level model cache
_model = None
_model_type = None  # "base", "voice_design", "custom_voice"

# Real Qwen3-TTS model IDs keyed by (type, size)
_MODEL_MAP = {
    ("base", "0.6B"): "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    ("base", "1.7B"): "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    ("voice_design", "1.7B"): "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    ("custom_voice", "0.6B"): "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    ("custom_voice", "1.7B"): "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
}

# Default sizes per model type
_DEFAULT_SIZE = {
    "base": "0.6B",
    "voice_design": "1.7B",  # only 1.7B available
    "custom_voice": "0.6B",
}


async def _get_model_size() -> str:
    """Read tts_model_size from settings DB. Returns '0.6B' or '1.7B'."""
    try:
        from app.database import async_session
        from app.models import Setting
        async with async_session() as db:
            row = await db.get(Setting, "tts_model_size")
            if row and row.value in ("0.6B", "1.7B"):
                return row.value
    except Exception:
        pass
    return "0.6B"


def _resolve_model_name(model_type: str, size: str) -> str:
    """Pick the best available model ID for the given type and size."""
    key = (model_type, size)
    if key in _MODEL_MAP:
        return _MODEL_MAP[key]
    # Fall back to default size for this type
    default = _DEFAULT_SIZE.get(model_type, "0.6B")
    return _MODEL_MAP.get((model_type, default), _MODEL_MAP[("base", "0.6B")])


def _get_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda:0"
    except ImportError:
        pass
    return "cpu"


async def _ensure_model(model_type: str = "base"):
    """Load or switch TTS model, acquiring GPU lock."""
    global _model, _model_type

    size = await _get_model_size()

    if _model is not None and _model_type == model_type:
        return _model

    from qwen_tts import Qwen3TTSModel

    model_name = _resolve_model_name(model_type, size)

    # Offload old model
    if _model is not None:
        _offload_model()

    _model = Qwen3TTSModel.from_pretrained(model_name, device_map=_get_device())
    _model_type = model_type
    return _model


def _offload_model():
    """Move model to CPU / free GPU memory."""
    global _model, _model_type
    if _model is not None:
        try:
            import torch
            _model.to("cpu")
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
    _model = None
    _model_type = None


async def get_speakers() -> list[str]:
    """Return list of available preset speakers from the CustomVoice model."""
    return [
        "Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric",
        "Ryan", "Aiden", "Ono_Anna", "Sohee",
    ]


async def get_languages() -> list[str]:
    """Return list of supported languages."""
    return [
        "Auto", "Chinese", "English", "Japanese", "Korean",
        "German", "French", "Russian", "Portuguese", "Spanish", "Italian",
    ]


async def custom_voice(
    text: str,
    speaker: str,
    language: str = "Auto",
    instruct: str = "",
    output_path: str | Path = "",
) -> tuple[str, int]:
    """Generate speech using a preset speaker voice with optional style instruction."""
    async with gpu_lock:
        model = await _ensure_model("custom_voice")

        kwargs = dict(
            text=text,
            speaker=speaker,
            language=language,
            non_streaming_mode=True,
        )
        if instruct:
            kwargs["instruct"] = instruct

        wavs, sr = model.generate_custom_voice(**kwargs)

        if output_path:
            output_path = Path(output_path)
            sf.write(str(output_path), wavs[0], sr)
            return str(output_path), sr

        return wavs[0], sr


async def voice_clone(
    text: str,
    ref_audio_path: str,
    ref_text: str = "",
    language: str = "Auto",
    output_path: str | Path = "",
    voice_prompt_path: str | None = None,
) -> tuple[str, int]:
    """Generate speech with voice cloning.

    Args:
        text: Text to synthesize
        ref_audio_path: Path to reference audio file
        ref_text: Transcript of reference audio
        language: Target language code
        output_path: Where to save the output WAV
        voice_prompt_path: Optional pre-built voice clone prompt (pickle file)

    Returns:
        (output_path, sample_rate)
    """
    async with gpu_lock:
        model = await _ensure_model("base")

        voice_prompt = None
        if voice_prompt_path and Path(voice_prompt_path).exists():
            with open(voice_prompt_path, "rb") as f:
                voice_prompt = pickle.load(f)

        # If no ref_text provided, fall back to x-vector-only mode (speaker
        # embedding only, no in-context learning).  ICL mode is higher quality
        # but requires a transcript of the reference audio.
        use_xvector = not ref_text and not voice_prompt

        wavs, sr = model.generate_voice_clone(
            text=text,
            language=language,
            ref_audio=ref_audio_path if not voice_prompt else None,
            ref_text=ref_text if ref_text and not voice_prompt else None,
            x_vector_only_mode=use_xvector,
            voice_clone_prompt=voice_prompt,
            non_streaming_mode=True,
        )

        if output_path:
            output_path = Path(output_path)
            sf.write(str(output_path), wavs[0], sr)
            return str(output_path), sr

        return wavs[0], sr


async def voice_design(
    text: str,
    instruct: str,
    language: str = "Auto",
    output_path: str | Path = "",
) -> tuple[str, int]:
    """Generate speech from a style description."""
    async with gpu_lock:
        model = await _ensure_model("voice_design")

        wavs, sr = model.generate_voice_design(
            text=text,
            instruct=instruct,
            language=language,
            non_streaming_mode=True,
        )

        if output_path:
            output_path = Path(output_path)
            sf.write(str(output_path), wavs[0], sr)
            return str(output_path), sr

        return wavs[0], sr


async def build_voice_prompt(ref_audio_path: str, ref_text: str = "") -> list:
    """Pre-build a voice clone prompt from reference audio. Returns serializable prompt items."""
    async with gpu_lock:
        model = await _ensure_model("base")
        prompt_items = model.create_voice_clone_prompt(
            ref_audio=ref_audio_path,
            ref_text=ref_text or None,
        )
        return prompt_items


async def save_voice_prompt(prompt_items, persona_id: int) -> str:
    """Serialize voice prompt to disk."""
    path = VOICES_DIR / f"persona_{persona_id}.pkl"
    with open(path, "wb") as f:
        pickle.dump(prompt_items, f)
    return str(path)


async def offload():
    """Explicitly offload TTS model from GPU."""
    _offload_model()
