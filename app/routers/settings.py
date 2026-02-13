from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models import Setting

router = APIRouter()


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting))
    rows = result.scalars().all()
    return {r.key: r.value for r in rows}


@router.put("")
async def update_settings(body: dict, db: AsyncSession = Depends(get_db)):
    for key, value in body.items():
        existing = await db.get(Setting, key)
        if existing:
            existing.value = str(value)
        else:
            db.add(Setting(key=key, value=str(value)))
    await db.commit()
    return {"ok": True}


@router.get("/llm/models")
async def list_llm_models():
    """Discover available LLM models from the configured provider."""
    try:
        from modulle import create_ai_client

        async with async_session() as db:
            settings = {}
            for k in ["llm_provider", "llm_base_url", "llm_api_key"]:
                row = await db.get(Setting, k)
                settings[k] = row.value if row and row.value else ""

        provider = settings.get("llm_provider") or "ollama"
        base_url = settings.get("llm_base_url") or "http://localhost:11434"
        api_key = settings.get("llm_api_key") or None

        kwargs = {}
        if provider in ("ollama", "lm_studio"):
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key

        client, _, _ = create_ai_client(provider=provider, **kwargs)
        models = client.list_models()
        return models if models else []

    except ImportError:
        return {"error": "ModuLLe not installed"}
    except Exception as e:
        return {"error": str(e)}


def _readable_model_name(filename: str) -> str:
    """Turn a Draw Things filename into a human-readable name."""
    import re
    name = filename
    # Strip extension
    name = re.sub(r'\.(ckpt|safetensors|bin)$', '', name)
    # Strip quantisation suffixes
    name = re.sub(r'_(?:q[0-9]+p(?:_q[0-9]+p)?|f16|f32)$', '', name)
    # Replace underscores with spaces
    name = name.replace('_', ' ')
    # Capitalise first letter of each word
    name = name.title()
    return name


def _categorise_file(filename: str) -> str | None:
    """Return 'model', 'lora', 'vae', 'clip', 'ti', or None."""
    fl = filename.lower()
    if '_lora_' in fl:
        return 'lora'
    if '_vae_' in fl or fl.startswith('vae'):
        return 'vae'
    if '_clip_' in fl:
        return 'clip'
    if '_ti_' in fl:
        return 'ti'
    # Skip known non-model patterns
    if fl.startswith('blip') or fl.startswith('controlnet'):
        return None
    return 'model'


@router.get("/grpc/models")
async def list_grpc_models():
    """List available models on the Draw Things gRPC server."""
    try:
        from app.config import GRPC_SERVER
        from app.services.image import create_dt_client

        async with async_session() as db:
            row = await db.get(Setting, "grpc_server")
            server = row.value if row and row.value else GRPC_SERVER

        with create_dt_client(server) as client:
            reply = client.echo("test")
            models = []
            loras = []
            for f in sorted(reply.files):
                cat = _categorise_file(f)
                entry = {"file": f, "name": _readable_model_name(f)}
                if cat == 'model':
                    models.append(entry)
                elif cat == 'lora':
                    loras.append(entry)
            return {
                "connected": True,
                "server": server,
                "models": models,
                "loras": loras,
            }

    except Exception as e:
        return {"error": str(e)}
