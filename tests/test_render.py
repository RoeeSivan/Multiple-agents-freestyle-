"""Render test — needs the bundled Chromium (no network/API). Proves the core
contract: a SceneSpec produces a non-empty PNG and a valid binary .glb.
"""
import pytest

from app.models import Obj, SceneSpec
from app.rendering import render_scene


@pytest.mark.asyncio
async def test_render_produces_png_and_valid_glb(tmp_path):
    spec = SceneSpec(
        objects=[Obj(name="cube", shape="box", position=(0, 0.5, 0), color="#ff0000")]
    )
    res = await render_scene(spec, tmp_path, "t")

    assert res.png.exists() and res.png.stat().st_size > 1000

    glb = res.glb.read_bytes()
    assert glb[:4] == b"glTF"  # binary glTF magic
    assert len(glb) > 100
