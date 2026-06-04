"""Orchestration: the multi-agent build loop (the "brain").

Coordinates the agents in a programmatic hand-off (a PydanticAI multi-agent
pattern): PlannerAgent turns the request into a typed BuildSpec -> BuilderAgent
realizes it in a live Blender (Hyper3D Rodin meshes + PolyHaven) -> we render the
viewport -> VisionCritic judges the image -> if not good enough, its feedback
goes back to the BuilderAgent to refine the live scene. Repeats up to
`max_iterations`.

There is one Blender with one scene, so the whole Blender interaction is
serialized behind `_BUILD_LOCK`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from app.agents.builder import build_scene
from app.agents.critic import critique_render
from app.agents.intent import build_spec
from app.agents.reference import get_reference
from app.config import OUT_DIR, settings
from app.models import BuildReport, BuildSpec, Critique, GeometryAudit, Reference
from app.rendering import blender_io
from app.rendering.geometry_audit import audit_scene

# One Blender, one live scene -> only one build may touch it at a time.
_BUILD_LOCK = asyncio.Lock()


@dataclass
class BuildResult:
    spec: BuildSpec
    report: BuildReport
    png: Path
    glb: Path
    iterations: int
    critique: Critique | None  # final critic verdict (None if loop disabled)
    audit: GeometryAudit | None = None  # final deterministic geometry audit
    references: dict[str, Reference] | None = None  # web grounding per object name


def _merge_feedback(audit: GeometryAudit, critique: Critique | None) -> str:
    """Combine deterministic audit problems + perceptual critic notes for the builder."""
    parts: list[str] = []
    if audit.problems:
        parts.append(
            "MEASURED geometry problems (fix these precisely):\n- "
            + "\n- ".join(audit.problems)
        )
    if critique and critique.patch_instructions:
        parts.append("VISUAL review notes:\n" + critique.patch_instructions)
    return "\n\n".join(parts)


async def build_3d(
    request: str,
    current: BuildSpec | None = None,
    out_dir: Path = OUT_DIR,
    basename: str = "model",
    max_iterations: int | None = None,
    refine: bool = True,
) -> BuildResult:
    """Build (or edit) a 3D scene from `request`, refining via the critic loop."""
    max_iter = max_iterations if max_iterations is not None else settings.max_iterations
    is_edit = current is not None

    # Planning needs no Blender, so do it before grabbing the lock.
    spec = await build_spec(request, current)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{basename}.png"
    glb_path = out_dir / f"{basename}.glb"

    # Ground each object on real web photos + dimensions (best-effort; None on
    # failure/disabled). real_dims_m becomes the audit's size target. Also Blender-
    # free, so do it before grabbing the lock; lookups run concurrently.
    references: dict[str, Reference] = {}
    if settings.web_reference:
        results = await asyncio.gather(*[get_reference(b, out_dir) for b in spec.objects])
        references = {b.name: r for b, r in zip(spec.objects, results)}
    size_targets = {n: r.real_dims_m for n, r in references.items() if r and r.real_dims_m > 0}

    async with _BUILD_LOCK:
        if not is_edit:
            await asyncio.to_thread(blender_io.clear_scene)

        report = await build_scene(spec, is_edit=is_edit, references=references)
        iterations = 1
        critique: Critique | None = None
        audit: GeometryAudit | None = None

        if refine:
            audit = await asyncio.to_thread(audit_scene, spec, size_targets)
            views = await asyncio.to_thread(blender_io.render_views, out_dir)
            while iterations < max_iter:
                critique = await critique_render(request, spec, views, references)
                # Converge only when BOTH the eye and the measurements agree.
                if critique.matches_request and audit.ok:
                    break
                feedback = _merge_feedback(audit, critique)
                if not feedback:
                    break
                report = await build_scene(spec, feedback=feedback)
                audit = await asyncio.to_thread(audit_scene, spec, size_targets)
                views = await asyncio.to_thread(blender_io.render_views, out_dir)
                iterations += 1

        # Hero shot for the SMS preview + the final game-ready export.
        await asyncio.to_thread(blender_io.render_png, png_path)
        await asyncio.to_thread(blender_io.export_glb, glb_path)

    return BuildResult(spec, report, png_path, glb_path, iterations, critique, audit, references)
