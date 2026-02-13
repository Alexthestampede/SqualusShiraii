import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.database import get_db
from app.models import Song
from app.config import ART_DIR
from app.services import image as image_svc

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate")
async def generate_art(body: dict, db: AsyncSession = Depends(get_db)):
    """Generate album art for a song."""
    song_id = body.get("song_id")
    prompt = body.get("prompt", "")
    preset_name = body.get("preset", "")
    model = body.get("model", "")
    negative_prompt = body.get("negative_prompt", "")

    song = None
    if song_id:
        result = await db.execute(
            select(Song).options(selectinload(Song.persona)).where(Song.id == song_id)
        )
        song = result.scalar_one_or_none()
        if not song:
            return {"error": "Song not found"}
        # Use LLM to craft a visual prompt from song metadata
        if not prompt:
            try:
                from app.services.lyrics import generate_art_prompt
                persona_name = song.persona.name if song.persona else ""
                prompt = await generate_art_prompt(
                    title=song.title or "",
                    caption=song.caption or "",
                    lyrics=song.lyrics or "",
                    persona_name=persona_name,
                )
                log.info("LLM art prompt: %s", prompt)
            except Exception as e:
                log.warning("LLM art prompt failed (%s), using fallback", e)
                # Fallback to basic prompt
                if song.caption:
                    prompt = f"Album art for: {song.caption}, album cover art, high quality"
                else:
                    prompt = f"Album art for: {song.title or 'music'}, album cover art, high quality"

    if not prompt:
        return {"error": "Provide a prompt or song_id"}

    output_name = f"{song_id or 'art'}_{uuid.uuid4().hex[:8]}.png"
    output_path = ART_DIR / output_name

    try:
        path = await image_svc.generate_art(
            prompt=prompt,
            output_path=output_path,
            preset_name=preset_name,
            model=model,
            negative_prompt=negative_prompt,
            width=1024,
            height=1024,
        )

        if song:
            song.art_path = path
            await db.commit()

        return {"path": path, "song_id": song_id}
    except ImportError as e:
        return {"error": f"DTgRPCconnector not available: {e}"}
    except Exception as e:
        return {"error": f"Art generation failed: {e}"}


@router.get("/presets")
async def list_presets():
    """List available image generation presets."""
    return image_svc.list_presets()
