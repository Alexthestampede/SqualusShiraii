from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Squalus Shiraii", lifespan=lifespan)

# --- Routers (added as phases are built) ---
from app.routers import songs, create, lyrics, music, art, personas, tts, jobs, settings  # noqa: E402

app.include_router(songs.router, prefix="/api/songs", tags=["songs"])
app.include_router(create.router, prefix="/api/create", tags=["create"])
app.include_router(lyrics.router, prefix="/api/lyrics", tags=["lyrics"])
app.include_router(music.router, prefix="/api/music", tags=["music"])
app.include_router(art.router, prefix="/api/art", tags=["art"])
app.include_router(personas.router, prefix="/api/personas", tags=["personas"])
app.include_router(tts.router, prefix="/api/tts", tags=["tts"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.json")
async def manifest():
    return FileResponse(STATIC_DIR / "manifest.json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")
