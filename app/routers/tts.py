import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.config import VOICES_DIR

router = APIRouter()


@router.get("/speakers")
async def tts_speakers():
    """Return available preset speakers for custom voice mode."""
    from app.services import tts as tts_svc
    speakers = await tts_svc.get_speakers()
    languages = await tts_svc.get_languages()
    return {"speakers": speakers, "languages": languages}


@router.post("/custom-voice")
async def tts_custom_voice(body: dict):
    """Generate speech using a preset speaker with optional style instruction."""
    text = body.get("text", "")
    speaker = body.get("speaker", "")
    language = body.get("language", "Auto")
    instruct = body.get("instruct", "")

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    if not speaker:
        raise HTTPException(status_code=400, detail="Speaker is required")

    try:
        from app.services import tts as tts_svc
        filename = f"custom_{uuid.uuid4().hex[:8]}.wav"
        output_path = VOICES_DIR / filename
        path, sr = await tts_svc.custom_voice(
            text=text,
            speaker=speaker,
            language=language,
            instruct=instruct,
            output_path=output_path,
        )
        return {"filename": filename, "audio_path": str(path), "sample_rate": sr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS custom voice failed: {e}")


@router.post("/clone")
async def tts_clone(body: dict):
    """One-off voice clone: provide text + reference audio path."""
    text = body.get("text", "")
    ref_audio = body.get("ref_audio_path", "")
    ref_text = body.get("ref_text", "")
    language = body.get("language", "Auto")

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    if not ref_audio:
        raise HTTPException(status_code=400, detail="ref_audio_path is required")

    try:
        from app.services import tts as tts_svc
        filename = f"clone_{uuid.uuid4().hex[:8]}.wav"
        output_path = VOICES_DIR / filename
        path, sr = await tts_svc.voice_clone(
            text=text,
            ref_audio_path=ref_audio,
            ref_text=ref_text,
            language=language,
            output_path=output_path,
        )
        return {"filename": filename, "audio_path": str(path), "sample_rate": sr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS clone failed: {e}")


@router.post("/clone-upload")
async def tts_clone_upload(
    text: str = Form(...),
    ref_text: str = Form(""),
    language: str = Form("Auto"),
    ref_audio: UploadFile = File(...),
):
    """Voice clone with uploaded reference audio file."""
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        from app.services import tts as tts_svc

        # Save uploaded reference audio
        ref_filename = f"ref_{uuid.uuid4().hex[:8]}.wav"
        ref_path = VOICES_DIR / ref_filename
        content = await ref_audio.read()
        with open(ref_path, "wb") as f:
            f.write(content)

        filename = f"clone_{uuid.uuid4().hex[:8]}.wav"
        output_path = VOICES_DIR / filename
        path, sr = await tts_svc.voice_clone(
            text=text,
            ref_audio_path=str(ref_path),
            ref_text=ref_text,
            language=language,
            output_path=output_path,
        )
        return {"filename": filename, "audio_path": str(path), "sample_rate": sr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS clone failed: {e}")


@router.post("/design")
async def tts_design(body: dict):
    """Generate speech from a voice style description."""
    text = body.get("text", "")
    instruct = body.get("instruct", "")
    language = body.get("language", "Auto")

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    if not instruct:
        raise HTTPException(status_code=400, detail="Voice style instruction is required")

    try:
        from app.services import tts as tts_svc
        filename = f"design_{uuid.uuid4().hex[:8]}.wav"
        output_path = VOICES_DIR / filename
        path, sr = await tts_svc.voice_design(
            text=text,
            instruct=instruct,
            language=language,
            output_path=output_path,
        )
        return {"filename": filename, "audio_path": str(path), "sample_rate": sr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS design failed: {e}")


@router.get("/audio/{filename}")
async def tts_audio(filename: str):
    """Serve a generated WAV file."""
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = VOICES_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(str(path), media_type="audio/wav", filename=filename)
