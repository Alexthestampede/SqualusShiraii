from fastapi import APIRouter

from app.services import lyrics as lyrics_svc
from app.services import music as music_svc

router = APIRouter()


@router.post("/generate")
async def generate_lyrics(body: dict):
    """Generate lyrics from a description using ModuLLe LLM."""
    description = body.get("description", "").strip()
    if not description:
        return {"error": "Description is required"}

    instrumental = body.get("instrumental", False)

    try:
        result = await lyrics_svc.generate_lyrics(description, instrumental=instrumental)
        return result
    except ImportError:
        return {"error": "ModuLLe not installed. Check install.sh ran correctly."}
    except Exception as e:
        return {"error": f"Lyrics generation failed: {e}"}


@router.post("/format")
async def format_lyrics(body: dict):
    """Format/enhance lyrics using ACE-Step's /format_input endpoint."""
    prompt = body.get("caption", body.get("prompt", ""))
    lyrics = body.get("lyrics", "")

    if not lyrics and not prompt:
        return {"error": "Provide lyrics or a caption to format"}

    params = {}
    if body.get("duration"):
        params["duration"] = float(body["duration"])
    if body.get("bpm"):
        params["bpm"] = int(body["bpm"])
    if body.get("key_scale"):
        params["key"] = body["key_scale"]
    if body.get("time_signature"):
        params["time_signature"] = body["time_signature"]
    if body.get("vocal_language"):
        params["language"] = body["vocal_language"]

    try:
        result = await music_svc.format_input(prompt, lyrics, params or None)
        return result
    except Exception as e:
        return {"error": f"Format failed: {e}"}
