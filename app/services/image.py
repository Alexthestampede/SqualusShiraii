"""Album art generation via DTgRPCconnector (Draw Things gRPC client)."""

import json
import logging
import ssl
import socket
import sys
from pathlib import Path

from app.config import PRESETS_DIR, ART_DIR, DATA_DIR, GRPC_SERVER
from app.database import async_session
from app.models import Setting

log = logging.getLogger(__name__)

# Cached cert path
_CERT_PATH = DATA_DIR / "dt_server_cert.pem"


def _fetch_server_cert(host: str, port: int) -> bytes | None:
    """Fetch the TLS certificate from a server using ssl module."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                der = ssock.getpeercert(binary_form=True)
                if der:
                    # Convert DER to PEM
                    import base64
                    b64 = base64.b64encode(der).decode("ascii")
                    lines = [b64[i:i+64] for i in range(0, len(b64), 64)]
                    pem = "-----BEGIN CERTIFICATE-----\n"
                    pem += "\n".join(lines)
                    pem += "\n-----END CERTIFICATE-----\n"
                    return pem.encode("ascii")
    except Exception as e:
        log.debug("Could not fetch TLS cert from %s:%d: %s", host, port, e)
    return None


def _get_cert_path(server: str) -> Path | None:
    """Get or auto-fetch the TLS cert for a Draw Things server.

    Returns the cert path if the server uses TLS, None if insecure works.
    """
    if _CERT_PATH.exists():
        return _CERT_PATH

    # Try to fetch and cache
    host, _, port_str = server.partition(":")
    port = int(port_str) if port_str else 7859
    pem = _fetch_server_cert(host, port)
    if pem:
        _CERT_PATH.write_bytes(pem)
        log.info("Cached Draw Things TLS cert at %s", _CERT_PATH)
        return _CERT_PATH
    return None


def create_dt_client(server: str):
    """Create a DrawThingsClient with auto TLS detection.

    Returns a DrawThingsClient (use as context manager).
    """
    from app.config import BASE_DIR
    dt_path = str(BASE_DIR / "DTgRPCconnector")
    if dt_path not in sys.path:
        sys.path.insert(0, dt_path)
    from drawthings_client import DrawThingsClient

    cert_path = _get_cert_path(server)
    if cert_path:
        return DrawThingsClient(
            server, insecure=False, verify_ssl=False,
            ssl_cert_path=str(cert_path),
        )
    return DrawThingsClient(server)


async def _get_grpc_settings() -> dict:
    async with async_session() as db:
        result = {}
        for k in ["grpc_server", "grpc_preset", "grpc_model",
                   "grpc_negative_prompt", "grpc_width", "grpc_height"]:
            row = await db.get(Setting, k)
            result[k] = row.value if row and row.value else ""
        return result


def _load_preset(name: str) -> dict | None:
    """Load a preset JSON from the presets directory."""
    for f in PRESETS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("name") == name or f.stem == name:
                return data
        except (json.JSONDecodeError, OSError):
            continue
    return None


def list_presets() -> list[dict]:
    """List all available presets."""
    presets = []
    for f in sorted(PRESETS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            presets.append({
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
                "file": f.name,
            })
        except (json.JSONDecodeError, OSError):
            continue
    return presets


_NEGATIVE_PROMPTS_DIR = PRESETS_DIR / "negative_prompts"


def list_negative_prompts() -> list[dict]:
    """List bundled negative prompt presets (from dtline)."""
    out = []
    if not _NEGATIVE_PROMPTS_DIR.exists():
        return out
    for f in sorted(_NEGATIVE_PROMPTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            out.append({
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
                "negative_prompt": data.get("negative_prompt", ""),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return out


def get_prompt_expander(preset_name: str) -> str:
    """Return the prompt-expander system prompt for a preset, if any.

    Ernie and Ideogram 4 need their input prompts pre-expanded by an LLM.
    """
    preset = _load_preset(preset_name)
    if not preset:
        return ""
    return preset.get("prompt_expander_system", "")


async def generate_art(
    prompt: str,
    output_path: str | Path,
    preset_name: str = "",
    model: str = "",
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
) -> str:
    """Generate album art. Returns the path to the saved image."""
    from app.config import BASE_DIR
    dt_path = str(BASE_DIR / "DTgRPCconnector")
    if dt_path not in sys.path:
        sys.path.insert(0, dt_path)

    from drawthings_client import ImageGenerationConfig

    settings = await _get_grpc_settings()
    server = settings.get("grpc_server") or GRPC_SERVER
    resolved_model = model or settings.get("grpc_model", "")

    if not resolved_model:
        raise ValueError(
            "No Draw Things model configured. Go to Settings and enter the model filename."
        )

    # Apply saved width/height from settings as defaults
    if width == 1024 and settings.get("grpc_width"):
        try:
            width = int(settings["grpc_width"])
        except ValueError:
            pass
    if height == 1024 and settings.get("grpc_height"):
        try:
            height = int(settings["grpc_height"])
        except ValueError:
            pass

    # Apply saved negative prompt as default
    if not negative_prompt:
        negative_prompt = settings.get("grpc_negative_prompt", "")

    # Load preset if specified
    preset = None
    preset_key = preset_name or settings.get("grpc_preset", "")
    if preset_key:
        preset = _load_preset(preset_key)

    # Build config from preset or defaults
    if preset:
        dtl = "recommended_steps" in preset  # dtline simplified schema
        def steps_default() -> int:
            return preset.get("recommended_steps", preset.get("steps", 16))
        def cfg_default() -> float:
            return preset.get("recommended_cfg", preset.get("guidanceScale", 5.0))
        sampler_val = preset.get("sampler", 10)
        config_kwargs = dict(
            model=resolved_model,
            steps=steps_default(),
            width=width,
            height=height,
            cfg_scale=cfg_default(),
            scheduler=_sampler_to_name(sampler_val),
            seed_mode=preset.get("seedMode", 2),
            clip_skip=preset.get("clip_skip", 1),
            shift=preset.get("shift", 1.0),
            sharpness=preset.get("sharpness", 0.0),
            hires_fix=preset.get("hiresFix", preset.get("hires_fix", False)),
            tiled_decoding=preset.get("tiledDecoding", preset.get("tiled_decoding", False)),
            tiled_diffusion=preset.get("tiledDiffusion", preset.get("tiled_diffusion", False)),
            mask_blur=preset.get("maskBlur", 2.5),
            mask_blur_outset=preset.get("maskBlurOutset", 0),
            preserve_original_after_inpaint=preset.get("preserveOriginalAfterInpaint", True),
            cfg_zero_star=preset.get("cfgZeroStar", False),
            cfg_zero_init_steps=preset.get("cfgZeroInitSteps", 0),
            tea_cache=preset.get("teaCache", False),
        )
        ss_gamma = preset.get("stochastic_sampling_gamma")
        if ss_gamma is not None:
            config_kwargs["stochastic_sampling_gamma"] = float(ss_gamma)
        rds = preset.get("resolutionDependentShift", preset.get("resolution_dependent_shift"))
        if rds is not None:
            config_kwargs["resolution_dependent_shift"] = bool(rds)
        loras = preset.get("loras") or []
        if loras and not dtl:
            config_kwargs["loras"] = [
                {"file": l["file"], "weight": float(l.get("weight", 1.0))} for l in loras
            ]
        config = ImageGenerationConfig(**config_kwargs)
    else:
        config = ImageGenerationConfig(
            model=resolved_model,
            steps=16,
            width=width,
            height=height,
            cfg_scale=5.0,
            scheduler="UniPC ays",
        )

    output_path = Path(output_path)

    with create_dt_client(server) as client:
        images = client.generate_image(
            prompt=prompt,
            config=config,
            negative_prompt=negative_prompt,
        )
        if images:
            from tensor_decoder import tensor_to_pil
            img = tensor_to_pil(images[0])
            img.save(str(output_path), format="PNG")
            return str(output_path)

    raise RuntimeError("No images generated")


# Map sampler int from DT presets to scheduler name
_SAMPLER_MAP = {
    0: "DPMPP2M Karras",
    1: "Euler A",
    2: "DDIM",
    3: "PLMS",
    4: "DPMPP SDE Karras",
    5: "UniPC",
    6: "LCM",
    7: "Euler A Substep",
    8: "DPMPP SDE Substep",
    9: "TCD",
    10: "Euler A Trailing",
    11: "DPMPP SDE Trailing",
    12: "DPMPP2M AYS",
    13: "Euler A AYS",
    14: "DPMPP SDE AYS",
    15: "DPMPP2M Trailing",
    16: "DDIM Trailing",
    17: "UniPC Trailing",
    18: "UniPC ays",
}


def _sampler_to_name(val) -> str:
    if isinstance(val, int):
        return _SAMPLER_MAP.get(val, "UniPC ays")
    return str(val) if val else "UniPC ays"
