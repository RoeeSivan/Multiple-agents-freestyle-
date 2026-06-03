"""Blender backend test — needs a live Blender with the BlenderMCP addon.

Skips automatically when the addon socket isn't reachable, so the suite stays
green offline/CI. Uses a primitive cube (NOT Hyper3D Rodin) so it costs no
generation credits while still proving the core contract: the scene renders to a
non-empty PNG and exports a valid binary .glb.

Note: this mutates the live Blender scene (it clears it and adds a cube).
"""
import pytest

from app.rendering import blender_io

pytestmark = pytest.mark.skipif(
    not blender_io.reachable(),
    reason="Blender MCP addon not reachable on the configured port",
)


def test_blender_render_and_glb(tmp_path):
    blender_io.clear_scene()
    blender_io.run_code(
        """
import bpy
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
bpy.context.active_object.name = "t_cube"
print("OK")
"""
    )

    png = tmp_path / "t.png"
    glb = tmp_path / "t.glb"
    blender_io.render_png(png)
    blender_io.export_glb(glb)

    assert png.exists() and png.stat().st_size > 1000

    data = glb.read_bytes()
    assert data[:4] == b"glTF"  # binary glTF magic
    assert len(data) > 100
