"""YuE2 (YuE2UI) music generation client - talks to the YuE2UI server on port 7860."""

import asyncio
import json
import logging

import httpx

from app.config import YUE2_URL

log = logging.getLogger(__name__)

# YuE2 stages: "loading model" -> "reusing saved plan"/"planning score" ->
# "generating song" -> "synthesizing audio" -> "decoding audio" -> "done"
_STAGE_PROGRESS = {
    "loading model": 0.05,
    "reusing saved plan": 0.15,
    "planning score": 0.2,
    "generating song": 0.35,
    "synthesizing audio": 0.7,
    "decoding audio": 0.9,
    "done": 1.0,
}


async def get_yue2_url() -> str:
    """Get the YuE2UI URL, checking settings DB first."""
    from app.database import async_session
    from app.models import Setting
    async with async_session() as db:
        row = await db.get(Setting, "yue2_url")
        return row.value if row and row.value else YUE2_URL


async def health_check() -> bool:
    """YuE2UI has no /health; /api/songs is cheap and always exists."""
    url = await get_yue2_url()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{url}/api/songs")
            return r.status_code == 200
    except Exception:
        return False


async def submit_generation(params: dict) -> str:
    """Submit a generation request. Returns job_id."""
    url = await get_yue2_url()
    body = {
        "style": params.get("style", ""),
        "lyrics": params.get("lyrics", ""),
        "cot": params.get("cot", "full"),
        "preview": bool(params.get("preview", True)),
    }
    if params.get("seed") is not None:
        body["seed"] = int(params["seed"])
    if params.get("guidance") is not None:
        body["guidance"] = float(params["guidance"])

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{url}/api/generate", json=body)
        r.raise_for_status()
        data = r.json()
        job_id = data.get("id")
        if not job_id:
            raise RuntimeError(f"No job id from YuE2UI: {data}")
        log.info("YuE2UI job submitted: %s", job_id)
        return job_id


async def query_job(job_id: str) -> dict:
    """Poll a YuE2UI job. Returns status dict."""
    url = await get_yue2_url()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{url}/api/jobs/{job_id}")
        r.raise_for_status()
        return r.json()


async def download_audio(job_id: str) -> bytes:
    """Download the generated FLAC from YuE2UI."""
    url = await get_yue2_url()
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.get(f"{url}/api/jobs/{job_id}/audio")
        r.raise_for_status()
        return r.content


async def poll_until_done(job_id: str, on_progress=None, timeout_seconds: int = 3600) -> dict:
    """Poll YuE2UI until job finishes. Returns final status dict."""
    elapsed = 0
    interval = 3
    consecutive_errors = 0
    max_consecutive_errors = 10

    while elapsed < timeout_seconds:
        try:
            result = await query_job(job_id)
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            log.warning("YuE2UI poll error (%d/%d): %s", consecutive_errors, max_consecutive_errors, e)
            if consecutive_errors >= max_consecutive_errors:
                raise RuntimeError(
                    f"Lost contact with YuE2UI after {max_consecutive_errors} poll failures: {e}"
                )
            await asyncio.sleep(interval)
            elapsed += interval
            continue

        status = result.get("status", "")

        if on_progress:
            try:
                await on_progress(result)
            except Exception:
                pass

        if status == "done":
            return result
        elif status == "error":
            raise RuntimeError(result.get("error", "YuE2 generation failed"))

        await asyncio.sleep(interval)
        elapsed += interval

    raise TimeoutError(f"YuE2 generation timed out after {timeout_seconds}s")


async def run_generation(job_id: str, params: dict, on_progress=None) -> dict:
    """High level helper: submit + poll. Maps Squalus job progress onto YuE2 stages."""
    yue_job_id = await submit_generation(params)

    async def progress(r):
        stage = r.get("stage", "")
        mapped = _STAGE_PROGRESS.get(stage, 0.1)
        # semantic token count gives a rough signal during the long generating phase
        if stage == "generating song" and r.get("tokens"):
            tokens = int(r.get("tokens", 0))
            mapped = min(0.7, 0.15 + tokens / 600.0)
        if on_progress:
            await on_progress({"progress": mapped, "stage": stage})

    final = await poll_until_done(yue_job_id, on_progress=progress)
    return {"result": final.get("result", {}), "yue2_job_id": yue_job_id}


def result_metadata(result: dict) -> dict:
    """Extract usable metadata from a YuE2UI result block for Song fields."""
    meta = {}
    sec = result.get("seconds")
    if isinstance(sec, (int, float)):
        meta["duration"] = float(sec)
    if result.get("abc"):
        meta["lyrics"] = result["abc"]
    return meta