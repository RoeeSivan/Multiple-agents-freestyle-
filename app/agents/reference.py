"""ReferenceAgent — researches a real object on the web to ground the model.

The builder otherwise models from imagination. This agent searches the web for
real product photos and real dimensions/facts of the requested object (for "a
MacBook" it finds actual MacBook photos and that it's ~0.31 m wide), so the
builder models toward reality and the critic compares the render to ground truth.
The real dimensions also feed the geometry audit's size check.

Keyless: DuckDuckGo via the `ddgs` package (fits the "no paid keys" ethos). The
whole thing degrades cleanly — any failure returns None and the pipeline builds
without grounding.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from ddgs import DDGS
from pydantic_ai import Agent, BinaryContent

from app.config import settings
from app.models import ObjectBrief, Reference

if TYPE_CHECKING:  # avoid a runtime import cycle (state imports models, not agents)
    from app.state import ObjectIntake

log = logging.getLogger("reference")


def image_content(path: str) -> BinaryContent:
    """Read a local image into a BinaryContent with the right media type."""
    ext = Path(path).suffix.lower()
    media = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    return BinaryContent(data=Path(path).read_bytes(), media_type=media)

SYSTEM_PROMPT = """\
You research a REAL object so a 3D modeler can build an accurate version of it.
Given an object (name + description), use your tools to gather ground truth:

1. search_images: find clean reference PHOTOS of the real object. Prefer plain-
   background product shots and clear full views; pick the 2-3 BEST that show the
   object's true shape/proportions/color. Avoid logos, collages, and cluttered
   scenes.
2. search_web: find the object's REAL dimensions and distinctive facts. Search
   e.g. "<object> dimensions" or "<object> size specs".

Then return a Reference with:
- image_urls: the 2-3 best full-size image URLs you chose (the 'image' field).
- real_dims_m: the object's real LONGEST dimension in METERS. Convert units
  (1 in = 0.0254 m, 1 cm = 0.01 m). For a generic object use a typical real size.
  Use 0 only if truly unknowable.
- facts: one or two sentences on real colors, materials, and key features that
  matter for modeling (e.g. "aluminum unibody, silver or space-grey, very thin").
- sources: the page URLs you used.

Be efficient — a couple of searches is enough. Always return a valid Reference.
"""

reference_agent = Agent(
    settings.model,
    output_type=Reference,
    system_prompt=SYSTEM_PROMPT,
    retries=2,
)


@reference_agent.tool_plain
def search_images(query: str) -> list[dict]:
    """Search the web for images. Returns [{title, image, source, width, height}]."""
    try:
        res = DDGS().images(query, max_results=8)
    except Exception as e:  # noqa: BLE001 — network/ratelimit; degrade to empty
        log.warning("image search failed for %r: %s", query, e)
        return []
    return [
        {
            "title": r.get("title", ""),
            "image": r.get("image", ""),
            "source": r.get("source", ""),
            "width": r.get("width", 0),
            "height": r.get("height", 0),
        }
        for r in res
        if r.get("image")
    ]


@reference_agent.tool_plain
def search_web(query: str) -> list[dict]:
    """Search the web for text. Returns [{title, snippet, url}]."""
    try:
        res = DDGS().text(query, max_results=5)
    except Exception as e:  # noqa: BLE001
        log.warning("web search failed for %r: %s", query, e)
        return []
    return [
        {"title": r.get("title", ""), "snippet": r.get("body", ""), "url": r.get("href", "")}
        for r in res
    ]


def _cache_key(brief: ObjectBrief) -> str:
    return hashlib.sha1(f"{brief.name}|{brief.description}".encode()).hexdigest()[:16]


async def _download_images(urls: list[str], dest: Path, key: str) -> list[str]:
    """Download up to `reference_images` images; return local paths (skip failures)."""
    dest.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for i, url in enumerate(urls[: settings.reference_images]):
            try:
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                ctype = r.headers.get("content-type", "")
                if not ctype.startswith("image/") or len(r.content) > 12_000_000:
                    continue
                ext = {"image/png": ".png", "image/webp": ".webp"}.get(ctype, ".jpg")
                p = dest / f"{key}_{i}{ext}"
                p.write_bytes(r.content)
                paths.append(str(p))
            except Exception as e:  # noqa: BLE001 — one bad URL shouldn't sink the rest
                log.warning("ref image download failed %s: %s", url, e)
    return paths


async def get_reference(brief: ObjectBrief, out_dir: Path) -> Reference | None:
    """Research one object on the web; return a Reference (or None on failure/disabled).

    Caches per object (name+description) under out_dir/refs/ so repeats are free.
    """
    if not settings.web_reference:
        return None

    refs_dir = Path(out_dir) / "refs"
    key = _cache_key(brief)
    cache_file = refs_dir / f"{key}.json"
    if cache_file.exists():
        try:
            ref = Reference.model_validate_json(cache_file.read_text())
            if all(Path(p).exists() for p in ref.images):
                return ref
        except Exception:  # noqa: BLE001 — bad cache, just re-fetch
            pass

    try:
        prompt = (
            f"Object name: {brief.name}\n"
            f"Description: {brief.description}\n"
            f"Planner size guess: {brief.approx_size_m} m (verify against real specs)."
        )
        result = await reference_agent.run(prompt)
        ref = result.output
        ref.object_name = brief.name
        ref.images = await _download_images(ref.image_urls, refs_dir, key)
        refs_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(ref.model_dump_json(indent=2))
        return ref
    except Exception as e:  # noqa: BLE001 — grounding is best-effort
        log.warning("reference lookup failed for %r: %s", brief.name, e)
        return None


def reference_from_photos(obj: "ObjectIntake") -> Reference:
    """Build a Reference from the user's own uploaded photos (photos-only path).

    The collected photos become the grounding images, each tagged with its view so
    the builder/critic know the angle. We deliberately leave `real_dims_m` at 0 (no
    web lookup) — size falls back to the planner's estimate. This Reference is keyed
    to ONE object only, so it never bleeds into another object's build.
    """
    views = [v for v in obj.views if v in obj.received and Path(obj.received[v]).exists()]
    label = obj.label or obj.name.replace("_", " ")
    angles = ", ".join(views) or "several angles"
    return Reference(
        object_name=obj.name,
        images=[obj.received[v] for v in views],
        image_labels=views,
        real_dims_m=0.0,
        facts=(
            f"These are the user's OWN photos of their actual {label} ({angles}). "
            "Match this specific object's real silhouette, proportions, parts, and "
            "dominant colors/materials exactly — it is the ground truth."
        ),
        sources=[],
    )
