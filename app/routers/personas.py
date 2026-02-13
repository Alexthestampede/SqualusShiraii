import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Persona
from app.config import PORTRAITS_DIR, VOICES_DIR

router = APIRouter()


@router.get("")
async def list_personas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Persona).order_by(Persona.name))
    personas = result.scalars().all()
    return [_persona_dict(p) for p in personas]


@router.post("")
async def create_persona(
    name: str = Form(...),
    description: str = Form(""),
    ref_text: str = Form(""),
    ref_audio: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    persona = Persona(name=name, description=description, ref_text=ref_text)
    db.add(persona)
    await db.flush()

    # Save reference audio if uploaded
    if ref_audio:
        ext = Path(ref_audio.filename).suffix or ".wav"
        audio_path = VOICES_DIR / f"ref_{persona.id}_{uuid.uuid4().hex[:6]}{ext}"
        content = await ref_audio.read()
        audio_path.write_bytes(content)
        persona.ref_audio_path = str(audio_path)

        # Build voice clone prompt
        try:
            from app.services import tts as tts_svc
            prompt_items = await tts_svc.build_voice_prompt(str(audio_path), ref_text)
            vp_path = await tts_svc.save_voice_prompt(prompt_items, persona.id)
            persona.voice_prompt_path = vp_path
        except Exception:
            pass  # TTS may not be available yet

    await db.commit()
    await db.refresh(persona)
    return _persona_dict(persona)


@router.get("/{persona_id}")
async def get_persona(persona_id: int, db: AsyncSession = Depends(get_db)):
    persona = await db.get(Persona, persona_id)
    if not persona:
        raise HTTPException(404, "Persona not found")
    return _persona_dict(persona)


@router.put("/{persona_id}")
async def update_persona(persona_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    persona = await db.get(Persona, persona_id)
    if not persona:
        raise HTTPException(404, "Persona not found")
    allowed = {"name", "description", "ref_text"}
    for k, v in body.items():
        if k in allowed:
            setattr(persona, k, v)
    await db.commit()
    await db.refresh(persona)
    return _persona_dict(persona)


@router.delete("/{persona_id}")
async def delete_persona(persona_id: int, db: AsyncSession = Depends(get_db)):
    persona = await db.get(Persona, persona_id)
    if not persona:
        raise HTTPException(404, "Persona not found")
    # Clean up files
    for path_attr in ("portrait_path", "voice_prompt_path", "ref_audio_path"):
        path = getattr(persona, path_attr)
        if path and Path(path).exists():
            Path(path).unlink(missing_ok=True)
    await db.delete(persona)
    await db.commit()
    return {"ok": True}


@router.get("/{persona_id}/portrait")
async def get_portrait(persona_id: int, db: AsyncSession = Depends(get_db)):
    persona = await db.get(Persona, persona_id)
    if not persona or not persona.portrait_path:
        raise HTTPException(404, "Portrait not found")
    return FileResponse(persona.portrait_path)


@router.post("/{persona_id}/generate-portrait")
async def generate_portrait(persona_id: int, body: dict = {}, db: AsyncSession = Depends(get_db)):
    """Generate a portrait for a persona using Draw Things."""
    persona = await db.get(Persona, persona_id)
    if not persona:
        raise HTTPException(404, "Persona not found")

    prompt = body.get("prompt", "")
    if not prompt:
        prompt = f"Portrait of {persona.name}. {persona.description}. character portrait, artistic, high quality"

    output_path = PORTRAITS_DIR / f"persona_{persona_id}_{uuid.uuid4().hex[:6]}.png"

    try:
        from app.services import image as image_svc
        path = await image_svc.generate_art(
            prompt=prompt,
            output_path=output_path,
            width=512,
            height=512,
        )
        persona.portrait_path = path
        await db.commit()
        return {"path": path}
    except Exception as e:
        return {"error": f"Portrait generation failed: {e}"}


@router.post("/{persona_id}/preview-voice")
async def preview_voice(persona_id: int, body: dict = {}, db: AsyncSession = Depends(get_db)):
    """Generate a voice preview for a persona."""
    persona = await db.get(Persona, persona_id)
    if not persona:
        raise HTTPException(404, "Persona not found")

    text = body.get("text", "Hello, this is a voice preview for this persona.")
    language = body.get("language", "en")

    if not persona.ref_audio_path:
        return {"error": "No reference audio uploaded for this persona"}

    try:
        from app.services import tts as tts_svc
        output_path = VOICES_DIR / f"preview_{persona_id}_{uuid.uuid4().hex[:6]}.wav"
        path, sr = await tts_svc.voice_clone(
            text=text,
            ref_audio_path=persona.ref_audio_path,
            ref_text=persona.ref_text or "",
            language=language,
            output_path=output_path,
            voice_prompt_path=persona.voice_prompt_path,
        )
        return {"audio_path": str(path), "sample_rate": sr}
    except Exception as e:
        return {"error": f"Voice preview failed: {e}"}


def _persona_dict(p: Persona) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "has_portrait": p.portrait_path is not None,
        "has_voice": p.voice_prompt_path is not None,
        "has_ref_audio": p.ref_audio_path is not None,
        "ref_text": p.ref_text,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
