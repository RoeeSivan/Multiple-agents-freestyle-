"""Orchestration: the multi-agent build loop.

Coordinates the agents in a programmatic hand-off (a PydanticAI multi-agent
pattern): IntentAgent proposes a SceneSpec -> renderer draws it -> VisionCritic
judges the image -> if not good enough, its feedback goes back to IntentAgent.
Repeats up to `max_iterations`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.agents.critic import critique_render
from app.agents.intent import build_spec
from app.config import OUT_DIR, settings
from app.models import Critique, SceneSpec
from app.rendering import RenderResult, render_scene


@dataclass
class BuildResult:
    spec: SceneSpec
    render: RenderResult
    iterations: int
    critique: Critique | None  # final critic verdict (None if loop disabled)


async def build_3d(
    request: str,
    current: SceneSpec | None = None,
    out_dir: Path = OUT_DIR,
    basename: str = "model",
    max_iterations: int | None = None,
    refine: bool = True,
) -> BuildResult:
    """Build (or edit) a 3D scene from `request`, refining via the critic loop."""
    max_iter = max_iterations if max_iterations is not None else settings.max_iterations

    spec = await build_spec(request, current)
    render = await render_scene(spec, out_dir, basename)
    iterations = 1
    critique: Critique | None = None

    if not refine:
        return BuildResult(spec, render, iterations, None)

    while iterations < max_iter:
        critique = await critique_render(request, spec, render.png)
        if critique.matches_request:
            break
        # Hand the critic's feedback back to the designer and re-render.
        spec = await build_spec(critique.patch_instructions, current=spec)
        render = await render_scene(spec, out_dir, basename)
        iterations += 1

    return BuildResult(spec, render, iterations, critique)
