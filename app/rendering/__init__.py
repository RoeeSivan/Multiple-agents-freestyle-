"""Geometry backend: deterministic Blender MCP socket I/O.

`blender_io` drives the live Blender over the BlenderMCP socket — it runs the
builder's bpy code, renders the critic's multi-view PNGs + the hero shot, and
exports a game-ready .glb. `geometry_audit` measures the built scene with no LLM.
"""
from app.rendering import blender_io, geometry_audit

__all__ = ["blender_io", "geometry_audit"]
