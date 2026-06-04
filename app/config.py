"""Central configuration. Loads .env once; everything imports `settings`."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
OUT_DIR = ROOT / "out"

load_dotenv(ROOT / ".env")


class Settings:
    # Model used by all PydanticAI agents (vision-capable; needed by the critic).
    model: str = os.getenv("MODEL", "openai:gpt-4o")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Saperly (phone carrier for AI agents).
    saperly_api_key: str = os.getenv("SAPERLY_API_KEY", "")
    saperly_phone: str = os.getenv("SAPERLY_PHONE_NUMBER", "")
    saperly_base: str = os.getenv("SAPERLY_BASE", "https://saperly.com/api/v1")
    saperly_line_id: str = os.getenv("SAPERLY_LINE_ID", "")  # auto-resolved if blank

    # Public base URL for the inbound-SMS webhook + render links (e.g. ngrok).
    public_url: str = os.getenv("PUBLIC_URL", "").rstrip("/")

    # Build <-> critic refinement loop cap.
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "3"))

    # Web reference grounding: search real photos + dimensions to model toward
    # reality. Keyless (DuckDuckGo). Set WEB_REFERENCE=0 to disable (faster).
    web_reference: bool = os.getenv("WEB_REFERENCE", "1").lower() not in ("0", "false", "no")
    reference_images: int = int(os.getenv("REFERENCE_IMAGES", "3"))  # max photos per object

    # User-photo intake: let the ViewPlanner ask the user (via an upload link) for
    # photos of objects whose exact look is personal/specific, then model toward
    # those photos instead of the web. Set PHOTO_INTAKE=0 to disable (tests/smoke).
    photo_intake: bool = os.getenv("PHOTO_INTAKE", "1").lower() not in ("0", "false", "no")

    # Live Blender with the BlenderMCP socket addon (text->3D via Hyper3D Rodin).
    blender_host: str = os.getenv("BLENDER_HOST", "127.0.0.1")
    blender_port: int = int(os.getenv("BLENDER_PORT", "9876"))
    # Command the BuilderAgent spawns as its MCP toolset (talks to the addon).
    blender_mcp_cmd: list[str] = (os.getenv("BLENDER_MCP_CMD", "uvx blender-mcp")).split()


settings = Settings()
