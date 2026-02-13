"""MP3 export with ID3 tags via ffmpeg + mutagen."""

import subprocess
import shutil
from pathlib import Path

from app.config import EXPORTS_DIR


async def export_mp3(
    audio_path: str,
    output_path: str | Path | None = None,
    title: str = "",
    artist: str = "",
    lyrics: str = "",
    art_path: str | None = None,
) -> str:
    """Convert audio to MP3 and add ID3 metadata.

    Args:
        audio_path: Source audio file (WAV/MP3/etc)
        output_path: Destination. Auto-generated if None.
        title: Song title
        artist: Artist name
        lyrics: Lyrics text
        art_path: Album art image path

    Returns:
        Path to the exported MP3
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if output_path is None:
        safe_title = "".join(c for c in (title or "song") if c.isalnum() or c in " -_")[:50].strip()
        output_path = EXPORTS_DIR / f"{safe_title}.mp3"
    output_path = Path(output_path)

    # Convert to MP3 using ffmpeg
    if audio_path.suffix.lower() != ".mp3":
        cmd = [
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-codec:a", "libmp3lame",
            "-q:a", "2",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:500]}")
    else:
        shutil.copy2(audio_path, output_path)

    # Add ID3 tags with mutagen
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, USLT, APIC, ID3NoHeaderError

    try:
        audio = MP3(str(output_path), ID3=ID3)
    except ID3NoHeaderError:
        audio = MP3(str(output_path))

    if audio.tags is None:
        audio.add_tags()

    if title:
        audio.tags.add(TIT2(encoding=3, text=title))
    if artist:
        audio.tags.add(TPE1(encoding=3, text=artist))
    if lyrics:
        audio.tags.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))

    # Embed album art
    if art_path and Path(art_path).exists():
        art_data = Path(art_path).read_bytes()
        mime = "image/png" if art_path.endswith(".png") else "image/jpeg"
        audio.tags.add(APIC(
            encoding=3,
            mime=mime,
            type=3,  # Cover (front)
            desc="Cover",
            data=art_data,
        ))

    audio.save()
    return str(output_path)
