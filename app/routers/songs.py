from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Song, Persona
from app.config import AUDIO_DIR, ART_DIR, EXPORTS_DIR

router = APIRouter()


@router.get("")
async def list_songs(
    q: str = "",
    offset: int = 0,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Song).options(selectinload(Song.persona)).order_by(desc(Song.created_at))
    if q:
        stmt = stmt.where(Song.title.icontains(q) | Song.artist.icontains(q))
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    songs = result.scalars().all()
    return [_song_dict(s) for s in songs]


@router.get("/{song_id}")
async def get_song(song_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Song).options(selectinload(Song.persona)).where(Song.id == song_id)
    )
    song = result.scalar_one_or_none()
    if not song:
        raise HTTPException(404, "Song not found")
    return _song_dict(song)


@router.post("/{song_id}")
async def update_song(song_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    song = await db.get(Song, song_id)
    if not song:
        raise HTTPException(404, "Song not found")
    allowed = {"title", "artist", "caption", "lyrics", "bpm", "key_scale",
               "time_signature", "vocal_language", "instrumental"}
    for k, v in body.items():
        if k in allowed:
            setattr(song, k, v)
    await db.commit()
    await db.refresh(song)
    return _song_dict(song)


@router.delete("/{song_id}")
async def delete_song(song_id: int, db: AsyncSession = Depends(get_db)):
    song = await db.get(Song, song_id)
    if not song:
        raise HTTPException(404, "Song not found")
    await db.delete(song)
    await db.commit()
    return {"ok": True}


@router.get("/{song_id}/audio")
async def stream_audio(song_id: int, db: AsyncSession = Depends(get_db)):
    song = await db.get(Song, song_id)
    if not song or not song.audio_path:
        raise HTTPException(404, "Audio not found")
    return FileResponse(song.audio_path, media_type="audio/mpeg")


@router.get("/{song_id}/art")
async def serve_art(song_id: int, db: AsyncSession = Depends(get_db)):
    song = await db.get(Song, song_id)
    if not song or not song.art_path:
        raise HTTPException(404, "Art not found")
    return FileResponse(song.art_path, media_type="image/png")


@router.get("/{song_id}/export")
async def download_export(song_id: int, db: AsyncSession = Depends(get_db)):
    song = await db.get(Song, song_id)
    if not song or not song.audio_path:
        raise HTTPException(404, "Audio not found")

    # Generate export if not already done
    if not song.export_path or not Path(song.export_path).exists():
        try:
            from app.services.export import export_mp3
            path = await export_mp3(
                audio_path=song.audio_path,
                title=song.title,
                artist=song.artist,
                lyrics=song.lyrics,
                art_path=song.art_path,
            )
            song.export_path = path
            await db.commit()
        except Exception as e:
            raise HTTPException(500, f"Export failed: {e}")

    filename = f"{song.title or 'song'}.mp3"
    return FileResponse(song.export_path, media_type="audio/mpeg", filename=filename)


def _song_dict(s: Song) -> dict:
    d = {
        "id": s.id,
        "title": s.title,
        "artist": s.artist,
        "caption": s.caption,
        "lyrics": s.lyrics,
        "bpm": s.bpm,
        "key_scale": s.key_scale,
        "time_signature": s.time_signature,
        "duration": s.duration,
        "vocal_language": s.vocal_language,
        "instrumental": s.instrumental,
        "seed": s.seed,
        "has_audio": s.audio_path is not None,
        "has_art": s.art_path is not None,
        "has_export": s.export_path is not None,
        "persona_id": s.persona_id,
        "persona_name": None,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
    if s.persona_id and s.persona:
        d["persona_name"] = s.persona.name
    return d
