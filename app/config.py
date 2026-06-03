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

    # Live Blender with the BlenderMCP socket addon (text->3D via Hyper3D Rodin).
    blender_host: str = os.getenv("BLENDER_HOST", "127.0.0.1")
    blender_port: int = int(os.getenv("BLENDER_PORT", "9876"))
    # Command the BuilderAgent spawns as its MCP toolset (talks to the addon).
    blender_mcp_cmd: list[str] = (os.getenv("BLENDER_MCP_CMD", "uvx blender-mcp")).split()


settings = Settings()
