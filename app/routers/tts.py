import uuid

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import VOICES_DIR

router = APIRouter()


@router.post("/clone")
async def tts_clone(body: dict):
    """One-off voice clone: provide text + reference audio path."""
    text = body.get("text", "")
    ref_audio = body.get("ref_audio_path", "")
    ref_text = body.get("ref_text", "")
    language = body.get("language", "en")

    if not text:
        return {"error": "Text is required"}
    if not ref_audio:
        return {"error": "ref_audio_path is required"}

    try:
        from app.services import tts as tts_svc
        output_path = VOICES_DIR / f"clone_{uuid.uuid4().hex[:8]}.wav"
        path, sr = await tts_svc.voice_clone(
            text=text,
            ref_audio_path=ref_audio,
            ref_text=ref_text,
            language=language,
            output_path=output_path,
        )
        return {"audio_path": str(path), "sample_rate": sr}
    except Exception as e:
        return {"error": f"TTS clone failed: {e}"}


@router.post("/design")
async def tts_design(body: dict):
    """Generate speech from a voice style description."""
    text = body.get("text", "")
    instruct = body.get("instruct", "")
    language = body.get("language", "en")

    if not text:
        return {"error": "Text is required"}
    if not instruct:
        return {"error": "Voice style instruction is required"}

    try:
        from app.services import tts as tts_svc
        output_path = VOICES_DIR / f"design_{uuid.uuid4().hex[:8]}.wav"
        path, sr = await tts_svc.voice_design(
            text=text,
            instruct=instruct,
            language=language,
            output_path=output_path,
        )
        return {"audio_path": str(path), "sample_rate": sr}
    except Exception as e:
        return {"error": f"TTS design failed: {e}"}
