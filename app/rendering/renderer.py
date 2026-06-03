"""Headless Three.js renderer — LEGACY / reference only.

Loads web/scene.html in bundled Chromium, injects a primitive scene dict,
screenshots the canvas to PNG, and exports the content group to a binary .glb.

This was the original geometry backend. It has been superseded by the Blender
MCP backend (app/rendering/blender_io.py) and is no longer wired into the
pipeline; it expects the old primitive scene shape, not the current BuildSpec.
Kept on disk for reference.
"""
from __future__ import annotations

import base64
import contextlib
import functools
import http.server
import socketserver
import threading
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import async_playwright

from app.config import WEB_DIR

# Chromium flags so headless WebGL works even without a GPU (software fallback).
_GL_FLAGS = [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--ignore-gpu-blocklist",
    "--enable-webgl",
]


@dataclass
class RenderResult:
    png: Path
    glb: Path


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # silence per-request stderr logging
        pass


@contextlib.contextmanager
def _serve(directory: Path):
    """Serve `directory` over http on an ephemeral localhost port.

    ES modules + importmap are CORS-blocked over file://, so the scene must load
    over http for the vendored three.js imports to resolve.
    """
    handler = functools.partial(_QuietHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield port
    finally:
        httpd.shutdown()
        httpd.server_close()


async def render_scene(spec: dict, out_dir: Path, basename: str = "model") -> RenderResult:
    """Render a primitive scene `dict` to PNG + glb, returning their paths."""
    spec_dict = spec.model_dump() if hasattr(spec, "model_dump") else spec
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{basename}.png"
    glb_path = out_dir / f"{basename}.glb"

    with _serve(WEB_DIR) as port:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=_GL_FLAGS)
            page = await browser.new_page(viewport={"width": 1024, "height": 768})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: m.type == "error" and errors.append(m.text))

            await page.goto(f"http://127.0.0.1:{port}/scene.html")
            await page.wait_for_function("window.sceneReady === true", timeout=15000)

            await page.evaluate("(s) => window.buildScene(s)", spec_dict)
            try:
                await page.wait_for_function("window.renderReady === true", timeout=15000)
            except Exception as exc:  # surface WebGL/scene errors instead of a blank frame
                await browser.close()
                raise RuntimeError(f"render failed; page errors: {errors}") from exc

            canvas = await page.query_selector("#c")
            await canvas.screenshot(path=str(png_path))

            glb_b64 = await page.evaluate("() => window.exportGLB()")
            glb_path.write_bytes(base64.b64decode(glb_b64))

            await browser.close()

    return RenderResult(png=png_path, glb=glb_path)
