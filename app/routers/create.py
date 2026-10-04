import asyncio
import json
import logging
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models import Song, Job, Setting, Persona
from app.config import AUDIO_DIR, DEFAULT_ARTIST
from app.services import music as music_svc
from app.services import yue2 as yue2_svc

log = logging.getLogger(__name__)

router = APIRouter()


async def _get_setting(key: str, default: str = "") -> str:
    async with async_session() as db:
        row = await db.get(Setting, key)
        return row.value if row and row.value else default


async def _run_generation(job_id: str, song_id: int, ace_params: dict):
    """Background task: submit to ACE-Step, poll, save result."""
    async with async_session() as db:
        job = await db.get(Job, job_id)

        try:
            # Update job status
            job.status = "running"
            job.stage = "Submitting to ACE-Step..."
            await db.commit()

            # Submit to ACE-Step
            submit_result = await music_svc.submit_task(ace_params)
            # Response may be wrapped: {"data": {"task_id": ...}, "code": 200}
            payload = submit_result.get("data", submit_result) if isinstance(submit_result, dict) else submit_result
            ace_task_id = payload.get("task_id") if isinstance(payload, dict) else None
            if not ace_task_id:
                raise RuntimeError(f"No task_id in ACE-Step response: {submit_result}")

            job.stage = "Generating music..."
            await db.commit()

            # Poll until done
            async def on_progress(result):
                progress_text = result.get("progress_text", "")
                parsed = result.get("result_parsed")
                if isinstance(parsed, list) and parsed:
                    p = parsed[0]
                    progress = p.get("progress", 0)
                    stage = p.get("stage", progress_text)
                    job.progress = float(progress)
                    job.stage = stage
                else:
                    job.stage = progress_text
                await db.commit()

            final = await music_svc.poll_until_done(ace_task_id, on_progress=on_progress)

            # Extract result
            parsed = final.get("result_parsed")
            if not isinstance(parsed, list) or not parsed:
                raise RuntimeError("No result data from ACE-Step")

            result_entry = parsed[0]
            audio_file = result_entry.get("file")
            if not audio_file:
                raise RuntimeError("No audio file in result")

            # Download audio to local storage
            audio_bytes = await music_svc.download_audio(audio_file)
            ext = Path(audio_file).suffix or ".mp3"
            local_name = f"{song_id}_{uuid.uuid4().hex[:8]}{ext}"
            local_path = AUDIO_DIR / local_name
            local_path.write_bytes(audio_bytes)

            # Update song
            song = await db.get(Song, song_id)
            song.audio_path = str(local_path)
            song.status = "completed"

            # Fill in metadata from result
            metas = result_entry.get("metas", {})
            if metas.get("bpm") and not song.bpm:
                song.bpm = int(metas["bpm"])
            if metas.get("keyscale") and not song.key_scale:
                song.key_scale = metas["keyscale"]
            if metas.get("timesignature") and not song.time_signature:
                song.time_signature = metas["timesignature"]
            if metas.get("duration") and not song.duration:
                song.duration = float(metas["duration"])
            if result_entry.get("lyrics") and not song.lyrics:
                song.lyrics = result_entry["lyrics"]
            if result_entry.get("prompt") and not song.caption:
                song.caption = result_entry["prompt"]

            # Update job
            job.status = "completed"
            job.progress = 1.0
            job.stage = "Done"
            job.result_json = json.dumps(result_entry)
            await db.commit()

        except Exception as e:
            log.exception("Job %s failed: %s", job_id, e)
            job.status = "failed"
            job.error = str(e)
            job.stage = "Failed"
            await db.commit()

            # Mark song as failed too
            song = await db.get(Song, song_id)
            if song:
                song.status = "failed"
                await db.commit()


@router.post("/simple")
async def create_simple(body: dict, bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Simple creation: description + optional styles + instrumental + engine."""
    description = body.get("description", "").strip()
    styles = body.get("styles", [])
    instrumental = body.get("instrumental", False)
    engine = body.get("engine", "acestep")

    if engine not in ("acestep", "yue2"):
        return {"error": f"Unknown engine: {engine}"}
    if not description:
        return {"error": "Description is required"}

    # Build caption from description + styles
    caption = description
    if styles:
        caption = ", ".join(styles) + ", " + description

    artist = await _get_setting("default_artist", DEFAULT_ARTIST)

    if engine == "yue2" and instrumental:
        # YuE2 is vocal-driven; instrumental tracks are an ACE-Step feature
        return {"error": "YuE2 does not support instrumental-only generation"}

    # Create song record
    song = Song(
        title=description[:60],
        artist=artist,
        caption=caption,
        instrumental=instrumental,
        engine=engine,
        status="generating",
    )
    db.add(song)
    await db.flush()

    # Create job
    job = Job(
        id=str(uuid.uuid4()),
        job_type="simple_create",
        status="pending",
        song_id=song.id,
    )
    db.add(job)
    await db.commit()

    if engine == "yue2":
        yue_params = {
            "style": caption,
            "lyrics": lyrics,
            "cot": "full",
            "preview": True,
        }
        # Simple mode has no real lyrics - have the LLM write them first
        yue_params["generate_lyrics_from"] = description if not lyrics else ""
        bg.add_task(_run_yue2_generation, job.id, song.id, yue_params)
        return {"job_id": job.id, "song_id": song.id}

    # Build ACE-Step params
    # Don't use sample_mode - it lets ACE-Step's LLM pick language/style freely.
    # Instead use use_format to enhance the caption while respecting vocal_language.
    ace_params = {
        "prompt": caption,
        "lyrics": "",
        "audio_duration": 120,
        "use_random_seed": True,
        "inference_steps": 8,
        "guidance_scale": 7.0,
        "vocal_language": "en",
        "use_format": True,
        "batch_size": 1,
    }

    bg.add_task(_run_generation, job.id, song.id, ace_params)

    return {"job_id": job.id, "song_id": song.id}


@router.post("/custom")
async def create_custom(body: dict, bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Custom creation: full params including lyrics, caption, BPM, key, etc."""
    lyrics = body.get("lyrics", "").strip()
    caption = body.get("caption", "").strip()
    instrumental = body.get("instrumental", False)
    persona_id = body.get("persona_id")
    engine = body.get("engine", "acestep")

    if engine not in ("acestep", "yue2"):
        return {"error": f"Unknown engine: {engine}"}
    if engine == "yue2" and instrumental:
        return {"error": "YuE2 does not support instrumental-only generation"}
    if not lyrics and not caption:
        return {"error": "Provide lyrics or a caption"}

    # Load persona if selected
    persona = None
    if persona_id:
        persona = await db.get(Persona, int(persona_id))

    artist = await _get_setting("default_artist", DEFAULT_ARTIST)

    # Incorporate persona description into the caption for vocal style guidance
    effective_caption = caption
    if persona and persona.description:
        if effective_caption:
            effective_caption = persona.description.strip() + ", " + effective_caption
        else:
            effective_caption = persona.description.strip()

    song = Song(
        title=body.get("title", "").strip() or "Untitled",
        artist=artist,
        caption=effective_caption,
        lyrics=lyrics,
        bpm=body.get("bpm"),
        key_scale=body.get("key_scale", ""),
        time_signature=body.get("time_signature", ""),
        vocal_language=body.get("vocal_language", "en"),
        instrumental=instrumental,
        persona_id=persona_id,
        engine=engine,
        status="generating",
    )
    db.add(song)
    await db.flush()

    job = Job(
        id=str(uuid.uuid4()),
        job_type="custom_create",
        status="pending",
        song_id=song.id,
    )
    db.add(job)
    await db.commit()

    if engine == "yue2":
        yue_params = {
            "style": effective_caption,
            "lyrics": lyrics,
            "cot": "full",
            "preview": bool(body.get("preview", True)),
        }
        if song.seed is not None:
            yue_params["seed"] = song.seed
        bg.add_task(_run_yue2_generation, job.id, song.id, yue_params)
        return {"job_id": job.id, "song_id": song.id}

    # Use more inference steps when reference audio is provided for better conditioning
    has_ref_audio = persona and persona.ref_audio_path and Path(persona.ref_audio_path).exists()
    steps = 20 if has_ref_audio else 8

    ace_params = {
        "prompt": effective_caption,
        "lyrics": lyrics,
        "vocal_language": body.get("vocal_language", "en"),
        "use_random_seed": True,
        "inference_steps": steps,
        "guidance_scale": 7.0,
        "batch_size": 1,
    }

    if body.get("bpm"):
        ace_params["bpm"] = int(body["bpm"])
    if body.get("duration"):
        ace_params["audio_duration"] = float(body["duration"])
    if body.get("key_scale"):
        ace_params["key_scale"] = body["key_scale"]
    if body.get("time_signature"):
        ace_params["time_signature"] = body["time_signature"]

    # Pass persona's reference audio for voice/style conditioning
    if has_ref_audio:
        ace_params["reference_audio_path"] = persona.ref_audio_path
        voice_strength = body.get("voice_strength", 0.5)
        # Clamp to valid range
        voice_strength = max(0.1, min(1.0, float(voice_strength)))
        ace_params["audio_cover_strength"] = voice_strength
        log.info("Using persona '%s' ref audio: %s (steps=%d, cover_strength=%.2f)",
                 persona.name, persona.ref_audio_path, steps, voice_strength)

    bg.add_task(_run_generation, job.id, song.id, ace_params)

    return {"job_id": job.id, "song_id": song.id}


async def _run_yue2_generation(job_id: str, song_id: int, params: dict):
    """Background: optionally LLM-write lyrics, submit to YuE2, poll, save result."""
    async with async_session() as db:
        job = await db.get(Job, job_id)
        try:
            job.status = "running"
            job.stage = "Writing lyrics..." if params.get("generate_lyrics_from") else "Submitting to YuE2..."
            await db.commit()

            # Simple mode: generate lyrics first so YuE2 has something to sing
            gen_from = params.pop("generate_lyrics_from", "")
            if gen_from:
                from app.services import lyrics as lyrics_svc

                lyr = await lyrics_svc.generate_lyrics(gen_from)
                if lyr.get("error") or not lyr.get("lyrics"):
                    raise RuntimeError(f"Lyrics generation failed: {lyr.get('error', 'empty response')}")
                params["lyrics"] = lyr["lyrics"]
                if lyr.get("caption") and not params.get("style"):
                    params["style"] = lyr["caption"]
                # Persist what the LLM wrote
                song = await db.get(Song, song_id)
                if song:
                    song.lyrics = lyr["lyrics"]
                    if lyr.get("caption") and not song.caption:
                        song.caption = lyr["caption"]
                    await db.commit()
                job.stage = "Submitting to YuE2..."
                await db.commit()

            async def on_progress(r):
                job.progress = float(r.get("progress", 0))
                job.stage = f"YuE2: {r.get('stage', '')}"
                await db.commit()

            final = await yue2_svc.run_generation(job_id, params, on_progress=on_progress)
            result = final.get("result", {})

            audio_bytes = await yue2_svc.download_audio(final["yue2_job_id"])

            local_name = f"{song_id}_{uuid.uuid4().hex[:8]}.flac"
            local_path = AUDIO_DIR / local_name
            local_path.write_bytes(audio_bytes)

            song = await db.get(Song, song_id)
            if song:
                song.audio_path = str(local_path)
                song.status = "completed"
                meta = yue2_svc.result_metadata(result)
                if meta.get("duration") and not song.duration:
                    song.duration = meta["duration"]
                job.result_json = json.dumps(
                    {"engine": "yue2", "yue2_job": final.get("yue2_job_id"),
                     "seconds": result.get("seconds"), "timing": result.get("timing")}
                )

            job.status = "completed"
            job.progress = 1.0
            job.stage = "Done"
            await db.commit()

        except Exception as e:
            log.exception("YuE2 job %s failed: %s", job_id, e)
            job.status = "failed"
            job.error = str(e)
            job.stage = "Failed"
            await db.commit()

            song = await db.get(Song, song_id)
            if song:
                song.status = "failed"
                await db.commit()
