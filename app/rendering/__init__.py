"""Geometry backend: deterministic Blender MCP socket I/O.

`blender_io` hosts the Hyper3D Rodin (text->mesh) + PolyHaven pipeline, takes the
viewport screenshot for the VisionCritic, and exports a game-ready .glb.

The legacy headless Three.js renderer (`renderer.py` + `web/scene.html`) is kept
on disk for reference but is no longer wired in — it rendered the old primitive
`SceneSpec`, which the Blender backend replaced.
"""
from app.rendering import blender_io, geometry_audit

__all__ = ["blender_io", "geometry_audit"]
