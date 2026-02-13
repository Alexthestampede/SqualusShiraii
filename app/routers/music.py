import uuid
import json

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models import Song, Job
from app.config import AUDIO_DIR
from app.services import music as music_svc

router = APIRouter()


@router.post("/generate")
async def generate_music(body: dict, bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Direct music generation - submit arbitrary params to ACE-Step."""
    song_id = body.pop("song_id", None)

    job = Job(
        id=str(uuid.uuid4()),
        job_type="music_generate",
        status="pending",
        song_id=song_id,
    )
    db.add(job)
    await db.commit()

    bg.add_task(_run_music_job, job.id, song_id, body)
    return {"job_id": job.id}


@router.post("/repaint")
async def repaint_music(body: dict, bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Repaint a section of an existing song."""
    song_id = body.get("song_id")
    if not song_id:
        return {"error": "song_id is required"}

    song = await db.get(Song, song_id)
    if not song or not song.audio_path:
        return {"error": "Song or audio not found"}

    ace_params = {
        "prompt": body.get("caption", song.caption or ""),
        "lyrics": body.get("lyrics", song.lyrics or ""),
        "src_audio_path": song.audio_path,
        "repainting_start": float(body.get("start", 0)),
        "repainting_end": float(body.get("end", song.duration or 30)),
        "vocal_language": song.vocal_language or "en",
        "inference_steps": 8,
        "guidance_scale": 7.0,
    }

    job = Job(
        id=str(uuid.uuid4()),
        job_type="music_repaint",
        status="pending",
        song_id=song_id,
    )
    db.add(job)
    await db.commit()

    bg.add_task(_run_music_job, job.id, song_id, ace_params)
    return {"job_id": job.id}


async def _run_music_job(job_id: str, song_id: int | None, params: dict):
    """Background: submit, poll, update job."""
    async with async_session() as db:
        job = await db.get(Job, job_id)
        try:
            job.status = "running"
            job.stage = "Submitting..."
            await db.commit()

            result = await music_svc.submit_task(params)
            ace_task_id = result.get("task_id")
            if not ace_task_id:
                raise RuntimeError("No task_id from ACE-Step")

            async def on_progress(r):
                parsed = r.get("result_parsed")
                if isinstance(parsed, list) and parsed:
                    p = parsed[0]
                    job.progress = float(p.get("progress", 0))
                    job.stage = p.get("stage", r.get("progress_text", ""))
                else:
                    job.stage = r.get("progress_text", "Processing...")
                await db.commit()

            final = await music_svc.poll_until_done(ace_task_id, on_progress=on_progress)

            parsed = final.get("result_parsed")
            if isinstance(parsed, list) and parsed:
                audio_file = parsed[0].get("file")
                if audio_file and song_id:
                    from pathlib import Path
                    audio_bytes = await music_svc.download_audio(audio_file)
                    ext = Path(audio_file).suffix or ".mp3"
                    local_name = f"{song_id}_{uuid.uuid4().hex[:8]}{ext}"
                    local_path = AUDIO_DIR / local_name
                    local_path.write_bytes(audio_bytes)

                    song = await db.get(Song, song_id)
                    if song:
                        song.audio_path = str(local_path)
                        song.status = "completed"

                job.result_json = json.dumps(parsed[0])

            job.status = "completed"
            job.progress = 1.0
            job.stage = "Done"
            await db.commit()

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            await db.commit()
