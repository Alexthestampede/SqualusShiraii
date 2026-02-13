"""Lyrics & prompt generation via ModuLLe."""

from app.config import LYRICS_PROMPT_PATH
from app.database import async_session
from app.models import Setting


def _read_system_prompt() -> str:
    """Read the lyrics generation system prompt."""
    if LYRICS_PROMPT_PATH.exists():
        return LYRICS_PROMPT_PATH.read_text(encoding="utf-8")
    return "You are an expert songwriter. Write creative, well-structured lyrics."


async def _get_llm_settings() -> dict:
    """Read LLM settings from DB."""
    async with async_session() as db:
        keys = ["llm_provider", "llm_base_url", "llm_api_key", "llm_model"]
        result = {}
        for k in keys:
            row = await db.get(Setting, k)
            result[k] = row.value if row and row.value else ""
        return result


async def generate_lyrics(description: str, instrumental: bool = False) -> dict:
    """Generate lyrics from a text description using ModuLLe.

    Returns dict with keys: lyrics, caption, bpm, key_scale, time_signature, duration
    """
    from modulle import create_ai_client

    settings = await _get_llm_settings()

    provider = settings.get("llm_provider") or "ollama"
    base_url = settings.get("llm_base_url") or "http://localhost:11434"
    api_key = settings.get("llm_api_key") or None
    model = settings.get("llm_model") or None

    kwargs = {}
    if provider in ("ollama", "lm_studio"):
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key

    client, text_processor, _ = create_ai_client(
        provider=provider,
        text_model=model,
        **kwargs,
    )

    system_prompt = _read_system_prompt()

    if instrumental:
        user_prompt = (
            f"Create an instrumental track based on this description: {description}\n\n"
            "Remember: for instrumental tracks, the Lyrics field should contain ONLY "
            "structure tags with NO text lines."
        )
    else:
        user_prompt = f"Create a song based on this description: {description}"

    raw = text_processor.generate(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.8,
    )

    if not raw:
        return {"error": "LLM returned empty response"}

    return _parse_llm_response(raw)


def _parse_llm_response(raw: str) -> dict:
    """Parse the structured LLM response into components."""
    result = {
        "lyrics": "",
        "caption": "",
        "bpm": None,
        "key_scale": "",
        "time_signature": "",
        "duration": None,
        "raw": raw,
    }

    sections = {}
    current_key = None
    current_lines = []

    for line in raw.split("\n"):
        stripped = line.strip()

        # Detect section headers
        lower = stripped.lower()
        if lower.startswith("caption") or lower.startswith("**caption"):
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = "caption"
            current_lines = []
            continue
        elif lower.startswith("lyrics") or lower.startswith("**lyrics"):
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = "lyrics"
            current_lines = []
            continue
        elif lower.startswith("beats per minute") or lower.startswith("**beats per minute"):
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = "bpm"
            current_lines = []
            continue
        elif lower.startswith("duration") or lower.startswith("**duration"):
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = "duration"
            current_lines = []
            continue
        elif lower.startswith("timesignature") or lower.startswith("**timesignature"):
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = "time_signature"
            current_lines = []
            continue
        elif lower.startswith("keyscale") or lower.startswith("**keyscale"):
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = "key_scale"
            current_lines = []
            continue
        elif stripped == "---":
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = None
            current_lines = []
            continue

        # Skip code fences
        if stripped.startswith("```"):
            continue

        if current_key:
            current_lines.append(line)

    # Flush last section
    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()

    # Map to result
    if "caption" in sections:
        result["caption"] = sections["caption"]
    if "lyrics" in sections:
        result["lyrics"] = sections["lyrics"]
    if "bpm" in sections:
        try:
            result["bpm"] = int("".join(c for c in sections["bpm"] if c.isdigit())[:3])
        except (ValueError, IndexError):
            pass
    if "duration" in sections:
        try:
            result["duration"] = float("".join(c for c in sections["duration"] if c.isdigit() or c == ".")[:6])
        except (ValueError, IndexError):
            pass
    if "time_signature" in sections:
        result["time_signature"] = sections["time_signature"].strip()
    if "key_scale" in sections:
        result["key_scale"] = sections["key_scale"].strip()

    return result


_ART_PROMPT_SYSTEM = """You are an expert at writing image generation prompts for album cover art.

Given information about a song (title, style/caption, lyrics, mood), write a single vivid,
descriptive prompt for generating the album cover image.

Rules:
- Output ONLY the image prompt, nothing else. No preamble, no explanation.
- Focus on visual elements: scene, colors, composition, lighting, texture, art style.
- Do NOT mention audio, music, vocals, singing, or sound - this is for a visual image.
- Do NOT include the song title as text in the image.
- Capture the mood and atmosphere of the song through visual metaphor.
- Keep it under 120 words.
- End with style/quality keywords like: album cover art, high quality, detailed"""


async def generate_art_prompt(
    title: str = "",
    caption: str = "",
    lyrics: str = "",
    persona_name: str = "",
) -> str:
    """Use the LLM to craft a visual prompt for album art based on song metadata."""
    from modulle import create_ai_client

    settings = await _get_llm_settings()

    provider = settings.get("llm_provider") or "ollama"
    base_url = settings.get("llm_base_url") or "http://localhost:11434"
    api_key = settings.get("llm_api_key") or None
    model = settings.get("llm_model") or None

    kwargs = {}
    if provider in ("ollama", "lm_studio"):
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key

    client, text_processor, _ = create_ai_client(
        provider=provider,
        text_model=model,
        **kwargs,
    )

    # Build context from song metadata
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if caption:
        parts.append(f"Style/mood: {caption}")
    if persona_name:
        parts.append(f"Artist persona: {persona_name}")
    if lyrics:
        # Truncate lyrics to first ~500 chars to avoid flooding the context
        snippet = lyrics[:500]
        if len(lyrics) > 500:
            snippet += "..."
        parts.append(f"Lyrics excerpt:\n{snippet}")

    user_prompt = "Write an album cover art prompt for this song:\n\n" + "\n".join(parts)

    raw = text_processor.generate(
        prompt=user_prompt,
        system_prompt=_ART_PROMPT_SYSTEM,
        temperature=0.9,
    )

    return (raw or "Abstract album cover art, vivid colors, high quality").strip()
