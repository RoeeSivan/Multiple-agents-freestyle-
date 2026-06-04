"""Offline tests for the web reference agent (no network / API).

Exercises the disabled path, the media-type helper, and the cache hit (which must
return WITHOUT calling the agent or the network).
"""
import asyncio

import pytest

from app.agents import reference as refmod
from app.agents.reference import _cache_key, get_reference, image_content
from app.models import ObjectBrief, Reference


def _brief():
    return ObjectBrief(name="macbook", description="a silver MacBook Pro", approx_size_m=0.3)


def test_image_content_media_types(tmp_path):
    for ext, expected in ((".png", "image/png"), (".webp", "image/webp"), (".jpg", "image/jpeg")):
        p = tmp_path / f"x{ext}"
        p.write_bytes(b"\x89fake")
        assert image_content(str(p)).media_type == expected


def test_disabled_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(refmod.settings, "web_reference", False)
    assert asyncio.run(get_reference(_brief(), tmp_path)) is None


def test_cache_hit_skips_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(refmod.settings, "web_reference", True)
    brief = _brief()
    refs = tmp_path / "refs"
    refs.mkdir(parents=True)
    img = refs / "img0.jpg"
    img.write_bytes(b"\xff\xd8fakejpeg")
    cached = Reference(
        object_name="macbook", real_dims_m=0.3557, facts="aluminum",
        images=[str(img)], sources=["https://example.com"],
    )
    (refs / f"{_cache_key(brief)}.json").write_text(cached.model_dump_json())

    # If the cache is honored, the agent is never invoked.
    async def _boom(*a, **k):
        raise AssertionError("agent should not run on a cache hit")

    monkeypatch.setattr(refmod.reference_agent, "run", _boom)
    ref = asyncio.run(get_reference(brief, tmp_path))
    assert ref is not None and ref.real_dims_m == 0.3557 and ref.images == [str(img)]


def test_stale_cache_missing_image_refetches(tmp_path, monkeypatch):
    # Cache points at a now-deleted image -> must fall through (here: to a stub agent).
    monkeypatch.setattr(refmod.settings, "web_reference", True)
    brief = _brief()
    refs = tmp_path / "refs"
    refs.mkdir(parents=True)
    stale = Reference(object_name="macbook", images=[str(refs / "gone.jpg")])
    (refs / f"{_cache_key(brief)}.json").write_text(stale.model_dump_json())

    class _Res:
        output = Reference(object_name="macbook", real_dims_m=0.35, image_urls=[])

    async def _stub(*a, **k):
        return _Res()

    monkeypatch.setattr(refmod.reference_agent, "run", _stub)
    ref = asyncio.run(get_reference(brief, tmp_path))
    assert ref is not None and ref.real_dims_m == 0.35  # came from the re-fetch
