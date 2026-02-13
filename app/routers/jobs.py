import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models import Job

router = APIRouter()


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_dict(job)


@router.get("/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE progress stream for a job."""
    async def event_generator():
        while True:
            async with async_session() as db:
                job = await db.get(Job, job_id)
                if not job:
                    yield _sse({"error": "Job not found"}, event="error")
                    return

                data = _job_dict(job)
                yield _sse(data)

                if job.status in ("completed", "failed"):
                    return

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(data: dict, event: str = "message") -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _job_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "stage": job.stage,
        "result_json": job.result_json,
        "error": job.error,
        "song_id": job.song_id,
    }
