"""Headless Three.js rendering (PNG screenshot + game-ready .glb export)."""
from app.rendering.renderer import RenderResult, render_scene

__all__ = ["render_scene", "RenderResult"]
