"""ViewPlanner — decides, per object, whether to ask the user for photos.

Sits between the PlannerAgent (text -> BuildSpec) and the BuilderAgent. For each
object in the plan it decides, IN ISOLATION, whether the user's own photos would
beat a generic web image — and if so, which views (front/back/side/top) to
request and the friendly one-line message to ask for each.

Why per-object: a request like "my desk chair next to a soccer ball" should ask
for the chair (personal, specific) but not the ball (any web image is fine). One
object's need never implies another's — the agent judges each on its own.
"""
from __future__ import annotations

from pydantic_ai import Agent

from app.config import settings
from app.models import BuildSpec, ObjectViews, PhotoPlan

SYSTEM_PROMPT = """\
You decide whether a 3D modeler should ask the USER for real photos of an object,
or just model it from a generic web reference. You are given a build plan with one
or more objects. Judge EACH object completely on its own — one object needing
photos says nothing about another.

Set needs_photos = TRUE for an object when the user clearly means a SPECIFIC,
PERSONAL, or NON-GENERIC item whose exact look matters and varies a lot between
instances — e.g. "my desk chair", "this lamp", "my dog", a custom/handmade or
unusual object. The user's own photos let the modeler match THEIR object.

Set needs_photos = FALSE when any decent web image would do — generic, standardized,
or iconic objects (a soccer ball, a coffee mug, a standard cube, a banana, a
typical office chair with no personal qualifier). Don't ask for photos you don't
need.

When needs_photos is TRUE, choose 2-4 VIEWS that actually disambiguate the shape,
in capture order. Use only these keys: "front", "back", "side", "top". Most objects
need front + back + side; add "top" only if the top genuinely matters. For each
view write ONE short, friendly SMS-style request that names the object and the
angle, e.g. "Great! Send me a photo of the wooden chair from the front." Keep
`views` and `prompts` the same length and aligned.

When needs_photos is FALSE, leave views and prompts empty.

Return a PhotoPlan with exactly one ObjectViews per object in the plan, using each
object's name verbatim.
"""

photoplan_agent = Agent(
    settings.model,
    output_type=PhotoPlan,
    system_prompt=SYSTEM_PROMPT,
    retries=2,
)


def _sanitize(plan: PhotoPlan, spec: BuildSpec) -> PhotoPlan:
    """Keep only real objects, dedupe/clip views, and align prompts to views."""
    valid = {o.name for o in spec.objects}
    allowed = ("front", "back", "side", "top")
    out: list[ObjectViews] = []
    for ov in plan.objects:
        if ov.object_name not in valid:
            continue
        # Normalize views: known keys only, de-duplicated, capped at 4.
        views: list[str] = []
        for v in ov.views:
            k = v.strip().lower()
            if k in allowed and k not in views:
                views.append(k)
        views = views[:4]
        needs = bool(ov.needs_photos and views)
        if not needs:
            out.append(ObjectViews(object_name=ov.object_name, needs_photos=False))
            continue
        # Align prompts to views; synthesize a default for any missing one.
        prompts = list(ov.prompts)[: len(views)]
        label = ov.object_name.replace("_", " ")
        while len(prompts) < len(views):
            v = views[len(prompts)]
            prompts.append(f"Send me a photo of the {label} from the {v}.")
        out.append(
            ObjectViews(object_name=ov.object_name, needs_photos=True, views=views, prompts=prompts)
        )
    return PhotoPlan(objects=out)


async def plan_views(spec: BuildSpec) -> PhotoPlan:
    """Decide per object whether to request user photos and which views."""
    if not spec.objects:
        return PhotoPlan()
    lines = [
        f"- {o.name}: {o.description}" + (f" (size ~{o.approx_size_m} m)" if o.approx_size_m else "")
        for o in spec.objects
    ]
    prompt = "Objects in this build:\n" + "\n".join(lines) + "\n\nDecide per object."
    result = await photoplan_agent.run(prompt)
    return _sanitize(result.output, spec)
