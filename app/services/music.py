"""ACE-Step HTTP client - talks to the ACE-Step API on localhost:8001."""

import json
import asyncio
import logging
import httpx

from app.config import ACESTEP_URL

log = logging.getLogger(__name__)


async def get_acestep_url() -> str:
    """Get the ACE-Step URL, checking settings DB first."""
    from app.database import async_session
    from app.models import Setting
    async with async_session() as db:
        row = await db.get(Setting, "acestep_url")
        return row.value if row and row.value else ACESTEP_URL


async def health_check() -> bool:
    url = await get_acestep_url()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{url}/health")
            return r.status_code == 200
    except Exception:
        return False


async def submit_task(params: dict) -> dict:
    """Submit a music generation task to ACE-Step. Returns {task_id, status, queue_position}.

    If reference_audio_path is present, switches to multipart form upload
    because ACE-Step rejects absolute file paths outside its temp directory.
    """
    url = await get_acestep_url()
    ref_audio = params.pop("reference_audio_path", None)

    from pathlib import Path

    async with httpx.AsyncClient(timeout=120) as client:
        if ref_audio:
            audio_path = Path(ref_audio)
            if not audio_path.exists():
                log.error("Reference audio file not found: %s", ref_audio)
                ref_audio = None

        if ref_audio:
            audio_path = Path(ref_audio)
            audio_bytes = audio_path.read_bytes()
            mime = "audio/wav" if audio_path.suffix.lower() == ".wav" else "audio/mpeg"
            files = {"ref_audio": (audio_path.name, audio_bytes, mime)}
            log.info("Uploading reference audio: %s (%d bytes, %s)", audio_path.name, len(audio_bytes), mime)
            # Build form data with proper type handling
            form_data = {}
            for k, v in params.items():
                if v is None:
                    continue
                if isinstance(v, bool):
                    form_data[k] = "true" if v else "false"
                else:
                    form_data[k] = str(v)
            log.info("Multipart form fields: %s", {k: v for k, v in form_data.items() if k != "lyrics"})
            r = await client.post(f"{url}/release_task", data=form_data, files=files)
        else:
            log.info("Submitting without reference audio (JSON mode)")
            r = await client.post(f"{url}/release_task", json=params)

        r.raise_for_status()
        data = r.json()
        log.info("ACE-Step /release_task response: %s", data)
        return data


async def query_result(task_id: str) -> dict:
    """Poll ACE-Step for task result. Returns the first result entry."""
    url = await get_acestep_url()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{url}/query_result", json={"task_id_list": [task_id]})
        r.raise_for_status()
        data = r.json()
        # Unwrap {"data": [...], "code": 200} envelope if present
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        if isinstance(data, list) and data:
            entry = data[0]
            # Parse result JSON string if present
            if isinstance(entry.get("result"), str) and entry["result"]:
                try:
                    entry["result_parsed"] = json.loads(entry["result"])
                except json.JSONDecodeError:
                    entry["result_parsed"] = None
            return entry
        return {"status": 0, "progress_text": "Waiting..."}


async def format_input(prompt: str, lyrics: str, params: dict | None = None) -> dict:
    """Use ACE-Step's /format_input to enhance lyrics/caption with LLM."""
    url = await get_acestep_url()
    body = {"prompt": prompt, "lyrics": lyrics}
    if params:
        body["param_obj"] = params
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{url}/format_input", json=body)
        r.raise_for_status()
        return r.json()


async def get_audio_url(file_path: str) -> str:
    """Build the URL to stream an audio file from ACE-Step."""
    url = await get_acestep_url()
    return f"{url}/v1/audio?path={file_path}"


async def download_audio(file_ref: str) -> bytes:
    """Download audio bytes from ACE-Step.

    file_ref may be:
      - A URL path like "/v1/audio?path=/home/.../foo.mp3"
      - A raw file path like "/home/.../foo.mp3"
    """
    base = await get_acestep_url()
    if file_ref.startswith("/v1/") or file_ref.startswith("http"):
        # Already a URL path - just prepend the base
        download_url = f"{base}{file_ref}" if file_ref.startswith("/") else file_ref
    else:
        # Raw file path - use the /v1/audio endpoint
        download_url = f"{base}/v1/audio?path={file_ref}"

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.get(download_url)
        r.raise_for_status()
        return r.content


async def poll_until_done(task_id: str, on_progress=None, timeout_seconds: int = 900) -> dict:
    """Poll ACE-Step until task completes or fails. Returns final result entry.

    Individual poll failures are tolerated (logged and retried) - only consecutive
    failures beyond a threshold will abort the job.
    """
    elapsed = 0
    interval = 3
    consecutive_errors = 0
    max_consecutive_errors = 10

    while elapsed < timeout_seconds:
        try:
            result = await query_result(task_id)
            consecutive_errors = 0  # reset on success
        except Exception as e:
            consecutive_errors += 1
            log.warning("Poll error (%d/%d): %s", consecutive_errors, max_consecutive_errors, e)
            if consecutive_errors >= max_consecutive_errors:
                raise RuntimeError(
                    f"Lost contact with ACE-Step after {max_consecutive_errors} consecutive poll failures: {e}"
                )
            await asyncio.sleep(interval)
            elapsed += interval
            continue

        status = result.get("status", 0)

        if on_progress:
            try:
                await on_progress(result)
            except Exception:
                pass  # don't let a progress update crash the job

        if status == 1:  # success
            return result
        elif status == 2:  # failed
            raise RuntimeError(result.get("progress_text", "Generation failed"))

        await asyncio.sleep(interval)
        elapsed += interval

    raise TimeoutError(f"Music generation timed out after {timeout_seconds}s")
